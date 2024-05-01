"""
Application handlers.
"""

import concurrent.futures
import copy
import json
import math
import os
import warnings
from datetime import datetime, timedelta
from typing import Any, Callable, Union

import google.api_core.exceptions
import google.api_core.retry
import numpy as np
import pandas as pd
import redis
from google.cloud import pubsub_v1  # type: ignore
from pycontrails.core.flight import Flight
from pycontrails.physics import geo
from redis.backoff import ExponentialBackoff
from redis.retry import Retry

from lib.log import format_traceback, logger
from lib.schemas import (
    SpireFlightInfo,
    SpireWaypointPositional,
    SpireWaypointsRecord,
    WaypointCache,
)


class PubSubSubscriptionHandler:
    """
    Handler for managing consumption and marshalling of jobs from a pubsub subscription queue.
    """

    # the number of seconds the subscriber client will hang, waiting for available messages
    MSG_WAIT_TIME_SEC = 60.0

    def __init__(self, subscription: str):
        """
        Parameters
        ----------
        subscription
            The fully-qualified URI for the pubsub subscription.
            e.g. 'projects/contrails-301217/subscriptions/api-preprocessor-sub-dev'
        """
        self.subscription = subscription
        self._client = None
        self._ack_id: Union[None, str] = None

    def __enter__(self):
        """
        Initialize pubsub client to be used across this class instance's lifecycle.
        """
        self._client = pubsub_v1.SubscriberClient()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """
        Ensure client connection to pubsub is closed.
        """
        self.close()

    def fetch(self) -> tuple[SpireWaypointsRecord, str]:
        """
        Fetch a message from the subscription queue.
        This method will hang and wait until a message is available.
        This method, in case of exception, will hang, backoff and retry indefinitely.

        Returns
        -------
        str
            The dequeued message from the pubsub subscription.
        str
            The ordering key for the fetched record.
        """
        if self._ack_id is not None:
            raise RuntimeError("fetch called multiple times without acking message")

        if not self._client:
            self._client = pubsub_v1.SubscriberClient()
            warnings.warn(
                "pubsub subscriber client initialized. "
                "connection will remain open until close()."
            )

        while True:
            logger.info(f"fetching message from {self.subscription}")
            resp = self._client.pull(
                request={"subscription": self.subscription, "max_messages": 1},
                timeout=self.MSG_WAIT_TIME_SEC,
            )

            if len(resp.received_messages) == 0:
                # it is possible there are no messages available,
                # or, pubsub returned zero when there are in fact some messages to fetch on retry
                logger.info("zero messages received.")
                continue
            msg = resp.received_messages[0]
            self._ack_id = msg.ack_id
            ordering_key = msg.message.ordering_key
            logger.info(
                f"received 1 message from {self.subscription}. "
                f"published_time: {msg.message.publish_time}, "
                f"message_id: {msg.message.message_id}"
            )
            return SpireWaypointsRecord.from_utf8_json(msg.message.data), ordering_key

    def ack(self):
        """
        Acknowledge the outstanding message presently handled by the instance of this class.
        """
        if not self._ack_id:
            raise ValueError(
                "ack_id is not set. call fetch(). "
                "handler instance must be handling an outstanding message."
            )
        self._client.acknowledge(
            request={"subscription": self.subscription, "ack_ids": [self._ack_id]},
            timeout=30,
        )
        logger.info("successfully ack'ed message.")
        self._ack_id = None

    def close(self):
        """
        Close pubsub client connection.
        """
        self._client.close()


class PubSubPublishHandler:
    def __init__(self, topic_id: str, ordered_queue: bool) -> None:
        self._topic_id = topic_id

        self._publisher = pubsub_v1.PublisherClient(
            # Batch settings increase payload size to execute fewer, larger requests.
            # See: https://cloud.google.com/pubsub/docs/batch-messaging
            batch_settings=pubsub_v1.types.BatchSettings(
                max_messages=1000,
                max_bytes=20 * 1000 * 1000,  # 20 MB max server-side request size
                max_latency=0.1,  # default: 10 ms
            ),
            publisher_options=pubsub_v1.types.PublisherOptions(
                enable_message_ordering=ordered_queue,
                # Flow control applies rate limits by blocking any time the staged data
                # exceeds the following settings. Once the records are received by GCP
                # PubSub, additional publish calls are unblocked.
                # See: https://cloud.google.com/pubsub/docs/flow-control-messages
                flow_control=pubsub_v1.types.PublishFlowControl(
                    message_limit=100 * 1000,
                    byte_limit=1024 * 1024 * 1024,  # 1 GiB
                    limit_exceeded_behavior=pubsub_v1.types.LimitExceededBehavior.BLOCK,
                ),
                # Retry defaults depend on gRPC method, see default for publish here:
                # https://github.com/googleapis/python-pubsub/blob/ff229a5fdd4deaff0ac97c74f313d04b62720ff7/google/pubsub_v1/services/publisher/transports/base.py#L164-L183
                retry=google.api_core.retry.Retry(
                    initial=0.1,
                    maximum=10,
                    multiplier=2,
                    predicate=google.api_core.retry.if_exception_type(
                        google.api_core.exceptions.Aborted,
                        google.api_core.exceptions.Cancelled,
                        google.api_core.exceptions.DeadlineExceeded,
                        google.api_core.exceptions.InternalServerError,
                        google.api_core.exceptions.ResourceExhausted,
                        google.api_core.exceptions.ServiceUnavailable,
                        google.api_core.exceptions.Unknown,
                    ),
                ),
            ),
        )

        self._publish_futures: list[concurrent.futures.Future] = []

    def publish_async(
        self,
        data: bytes,
        timeout_seconds: float,
        ordering_key: str = "",
        log_context: dict[str, Any] | None = None,
    ) -> None:
        """Add data to the current publish batch.

        Batches are pushed asynchronously to GCP PubSub in a separate thread. To wait
        for one or more publish calls until they have been received by the server, call
        wait_for_publish.

        Parameters
        ----------
        data
            byte encoded string payload
        ordering_key
            payloads sharing the same ordering_key are guaranteed to be delivered to
            consumers in the order they are published. the publisher client,
            and the subscription bound to the receiving topic,
            must be configured to use ordered messages.
        timeout_seconds
            timeout applied to each gRPC call to the PubSub API
        metadata
            any additional k-vs that contextualize the publish event.
            these will be added as context to the publisher callback,
            which includes them in any failure logs.
        """
        future: concurrent.futures.Future = self._publisher.publish(
            topic=self._topic_id,
            data=data,
            ordering_key=ordering_key,
            timeout=timeout_seconds,
        )

        done_callback = self._done_callback_factory(log_context)
        future.add_done_callback(done_callback)
        self._publish_futures.append(future)

    def wait_for_publish(self, timeout_seconds: float | None = None) -> None:
        """Block until all current publish batches are received by server.

        Parameters
        ----------
        timeout_seconds
            Duration to wait for all publish jobs to complete. If timeout_seconds is
            exceeded, the process will be force exited with os._exit(1).
        """
        _, not_done = concurrent.futures.wait(
            self._publish_futures,
            timeout=timeout_seconds,
        )

        # Exit if any publish futures have not completed before configured timeout.
        #
        # We cannot raise an exception or invoke sys.exit from the parent while child
        # threads are still running, because cpython configures a shutdown handler to
        # wait for spawned threads to complete before exiting:
        # https://github.com/python/cpython/blob/8f25cc992021d6ffc62bb110545b97a92f7cb295/Lib/concurrent/futures/thread.py#L18-L37
        #
        # Errors in child threads trigger a separate exit using a future done_callback.
        if not_done:
            logger.error("Futures did not complete before timeout: %s", not_done)
            os._exit(1)

        # All futures completed without error, reset pending futures state.
        self._publish_futures = []

    @staticmethod
    def _done_callback_factory(
        log_context: dict[str, Any] | None,
    ) -> Callable[[concurrent.futures.Future], None]:
        """
        returns a function to use as a callback.
        Constructs a log message annotating with any k-vs passed to this method.
        """
        msg = ""
        if log_context:
            for k, v in log_context.items():
                msg += f" {k}={v} "

        def _exit_on_error(future: concurrent.futures.Future) -> None:
            """Re-raise any exceptions raised by the future's execution thread.

            This should be registered as a callback that will only be invoked when the future
            has already completed using:
                future.add_done_callback(_raise_exception_if_failed)
            """
            try:
                future.result(timeout=0)
            except Exception:
                logger.error(
                    f"Publish future failed: {msg}. Unhandled exception:"
                    + format_traceback()
                )
                os._exit(1)

        return _exit_on_error


class CacheHandler:
    """
    Handler for interfacing with the remote cache.
    The remote cache stores the (2) last-known waypoints on a per flight-instance basis.
    """

    KEY_EXPIRY_SEC = 18 * 60 * 60  # seconds before a key expires

    def __init__(self, host: str, port: int):
        """
        Parameters
        ----------
        host
            the remote Redis host address (ipv4)
        port
            the remote Redis host port
        """
        self._host = host
        self._port = port

    def pull(self, key: str) -> list[WaypointCache.Waypoint]:
        """
        Parameters
        ----------
        key
            redis key corresponding to the target cache k-v
        """
        redis_retry = Retry(ExponentialBackoff(), 8)
        redis_client = redis.Redis(
            host=self._host,
            port=self._port,
            retry=redis_retry,
            retry_on_timeout=True,
            socket_timeout=1,
        )
        cache_resp = redis_client.hgetall(key)
        return WaypointCache.from_flatmap(cache_resp)

    def push(self, cache_entry: WaypointCache):
        """
        Parameters
        ----------
        cache_entry:
            A WaypointCache object.
            Contains the key to use for the redis index.
            Contains the last two known waypoints for the flight instance.
        """
        redis_retry = Retry(ExponentialBackoff(), 3)
        redis_client = redis.Redis(
            host=self._host,
            port=self._port,
            retry=redis_retry,
            retry_on_timeout=True,
            socket_timeout=1,
        )
        try:
            # try writing single record w/ expiry as an atomic transaction
            transaction = redis_client.pipeline()
            transaction.hset(cache_entry.key, mapping=cache_entry.to_flatmap())
            transaction.expire(cache_entry.key, self.KEY_EXPIRY_SEC)
            transaction.execute()
        finally:
            redis_client.connection_pool.disconnect()


class ValidationHandler:
    """
    Handler for managing data validation of the cached waypoints and the batch window records.

    The raw cache object and batch window records are passed to the handler.
    Validated entities are retrieved from the handler.
    """

    IN_FLIGHT_SPEED_THRESHOLD_KPH = 200  # aircraft in flight if moving at this speed
    LANDING_TO_TAKEOFF_DELAY_HR = 0.25  # minimum period between landing and takeoff

    def __init__(
        self, cache: list[WaypointCache.Waypoint], new_waypoints: SpireWaypointsRecord
    ):
        self._records: list[SpireWaypointPositional] = new_waypoints.records
        self._flight_info: SpireFlightInfo = new_waypoints.flight_info
        self._cached_records: list[SpireWaypointPositional] = [
            SpireWaypointsRecord.from_waypoint_cache(w)[1] for w in cache
        ]
        self._cached_flight_ids: list[str] = [
            SpireWaypointsRecord.from_waypoint_cache(w)[0] for w in cache
        ]

        self.max_cached_ts: datetime | None
        self.min_records_ts: datetime
        if self._cached_records:
            self.max_cached_ts = datetime.fromisoformat(
                self._cached_records[-1].timestamp
            )
        else:
            self.max_cached_ts = None
        self.min_records_ts = datetime.fromisoformat(self._records[0].timestamp)

    def correct_temporal_order(self) -> bool:
        """
        Verifies that the batch window of records trails the cached records in time.
        If the maximum cached timestamp is due to the previous iteration's interpolation,
        then the new records should trail by at least 1 minutes from the cache ts.
        Failure to meet this criteria may indicate out-of-order delivery of records.
        """

        # possible out-of-order delivery
        if self.max_cached_ts and self.min_records_ts < (
            self.max_cached_ts + timedelta(seconds=60)
        ):
            return False
        else:
            return True

    def verify_gt_1min_span(self) -> bool:
        """
        Verifies that the cache->records spans at least a 1-minute interval.
        If the total time spanned does not exceed 1 minute, this returns false, else true.

        This verification is relevant as resampling of records that don't span >1min
        will result in an empty list of resampled records.

        this is not desirable behavior, but expected behavior from pycontrails.Flight.resample_and_fill()
        ref, root: https://github.com/contrailcirrus/pycontrails/blame/7feed97d3e0eec5f7236d79122a5c11054d24fd5/pycontrails/core/flight.py#L2069

        """

        rht_unix = datetime.fromisoformat(self.records[-1].timestamp).timestamp()

        if self.cached_records:
            lht_unix = datetime.fromisoformat(
                self.cached_records[0].timestamp
            ).timestamp()
        else:
            lht_unix = datetime.fromisoformat(self.records[0].timestamp).timestamp()
        time_span_sec = rht_unix - lht_unix

        if time_span_sec <= 60:
            return False
        return True

    @property
    def cached_records(self) -> list[SpireWaypointPositional]:
        """
        A validated instance of cache record(s).

        Possible cases:
        - (A) if the cache is from a different flight-instance (based on the flight_id comparison)
            then return an empty cache object.
        - (B) if `(A)` is uncheckable due to no flight_id in the records batch window,
            then infer if batch window is from the same flight-instance, and if not,
            then return an empty cache object, If yes, return cache.
        """
        if not self._cached_records:
            return []

        if (
            self._flight_info.flight_id
            and self._flight_info.flight_id == self._cached_flight_ids[-1]
        ):
            # case (A)
            return self._cached_records

        # TODO: self.max_cached_ts could be None
        cache_to_records_elapsed_hr = (
            self.min_records_ts - self.max_cached_ts
        ).seconds / 3600
        if cache_to_records_elapsed_hr < self.LANDING_TO_TAKEOFF_DELAY_HR:
            return self._cached_records

        cache_to_records_distance_km = 0.001 * math.sqrt(
            (
                0.3048
                * (
                    self._records[0].altitude_baro
                    - self._cached_records[-1].altitude_baro
                )
            )
            ** 2
            + geo.haversine(
                lons1=np.array(self._records[0].longitude),
                lats1=np.array(self._records[0].latitude),
                lons0=np.array(self._records[0].longitude),
                lats0=np.array(self._records[0].latitude),
            )
            ** 2
        )
        cache_to_records_avg_kph = (
            cache_to_records_distance_km / cache_to_records_elapsed_hr
        )
        # different flight instance if avg speed too low to be flying between cache and records
        if cache_to_records_avg_kph <= self.IN_FLIGHT_SPEED_THRESHOLD_KPH:
            # case (B)
            logger.info(
                f"new flight instance inferred for icao_address {self._flight_info.icao_address} "
                f"at {self.min_records_ts.isoformat()}. invalidating cache."
            )
            return []
        else:
            return self._cached_records

    @property
    def flight_info(self):
        """
        A validated flight info instance.

        Possible cases:
        - (A) if the batch window of records provides a fully-formed SpireFlightInfo instance
            w/ valid flight_id,
            then this method simply returns that SpireFlightInfo instance
        - (A) if the batch window of records does not specify a flight_id
            (e.g. satellite observation),
            then a flight_id will be assigned from cache (provided it is the same flight instance)

        - (C) if case `(B)`, accept no flight_id is available in cache (different flight instance),
            then no flight_info instance will be returned
        """

        if self._flight_info.flight_id:
            # case (A)
            return self._flight_info
        elif self.cached_records:  # note: checks that validated cache records exist
            # case (B)
            fi = copy.copy(self._flight_info)
            fi.flight_id = self._cached_flight_ids[-1]
            return fi
        else:
            # case (C)
            return None

    @property
    def records(self):
        return self._records


class ResampleHandler:
    """
    Handles interpolation & data model coercing for a sequence of waypoints for a flight instance.
    This handler takes:
     (A) a sample of waypoints within a closed time window, and
     (B) 1 or 2 waypoints** at some time prior to (A) (cached waypoints)
         (**these are the waypoints from the right-hand-side of the previous window)

     BB......................A.AA.AAA

    Work includes:
    - intra-window interpolation; i.e. interpolation within the window (A)
    - inter-window interpolation; i.e. backward interpolation between A_0 and B
    """

    FLIGHT_LEVELS = [
        270,
        280,
        290,
        300,
        310,
        320,
        330,
        340,
        350,
        360,
        370,
        380,
        390,
        400,
        410,
        420,
        430,
        440,
    ]

    def __init__(
        self,
        cache: list[SpireWaypointPositional],
        records_window: list[SpireWaypointPositional],
    ):
        """
        Parameters
        ----------
        cache
            one or two waypoints that are retrieved from cache -- historical records
        records_window
            a series of waypoints, belonging to a time window,
            delivered from a windowed batch stream (temporally contiguous) -- present records
        """
        self._waypoints_df_resampled: pd.DataFrame | None = None

        # column names as expected by Flight (pycontrails.core.flight)
        pycontrails_name_map = {"altitude_baro": "altitude_ft", "timestamp": "time"}

        df_cached = pd.DataFrame(cache)
        if not df_cached.empty:
            df_cached.rename(columns=pycontrails_name_map, inplace=True)
            # note: pycontrails resample_and_fill returns df w/ naive timestamps, hence:
            df_cached["time"] = pd.to_datetime(df_cached["time"]).apply(
                lambda r: r.tz_localize(None)
            )
            self._max_cache_ts = df_cached["time"].max()
        else:
            self._max_cache_ts = pd.to_datetime("1970")

        df_records = pd.DataFrame(records_window)
        df_records.rename(
            columns={"altitude_baro": "altitude_ft", "timestamp": "time"}, inplace=True
        )
        df_records["time"] = pd.to_datetime(df_records["time"]).apply(
            lambda r: r.tz_localize(None)
        )

        if df_records["time"].duplicated().sum():
            logger.warning("duplicated waypoints found in cache+records.")
            df_records.drop_duplicates(["time"], inplace=True)

        self._min_records_ts = df_records["time"].min()

        self._waypoints_df = pd.concat([df_cached, df_records])

    def interpolate(self):
        """
        Run minute interpolation within the records time window, and backwards between
        the first index of the records time window and the cached waypoints.
        """
        pyc_flight = Flight(self._waypoints_df)
        flight_resampled: pd.DataFrame = pyc_flight.resample_and_fill().dataframe

        # add imputation flags
        flight_resampled["imputed"] = True
        is_cached = flight_resampled["time"] <= self._max_cache_ts
        is_records_window = flight_resampled["time"] >= self._min_records_ts
        flight_resampled.loc[(is_cached | is_records_window), "imputed"] = False

        # compute the altitude_ft from altitude (note: pycontrails Flight operates on altitude [m])
        flight_resampled.loc[:, "altitude_ft"] = (
            flight_resampled["altitude"] * 3.28
        ).astype(int)

        flight_resampled["flight_level"] = flight_resampled["altitude_ft"].apply(
            self.altitude_ft_to_flight_level
        )

        # flight_resampled at this point will include minute data
        # the first row will match what was pulled from cache
        # the last row will have a timestamp that is the bottom of the minute
        # for the right-most minutes data in the spire waypoints record window ingested from pubsub
        # -------------------

        # Cleanup
        flight_resampled.drop(columns=["altitude"], inplace=True)

        self._waypoints_df_resampled = flight_resampled
        return self

    @property
    def waypoints_resampled(self) -> list[SpireWaypointPositional]:
        """
        Returns
        -------
        List of SpireWaypointPositional objects, representing the resampled waypoints
        between the cached waypoints and the records waypoints passed to this handler.
        """
        if not isinstance(self._waypoints_df_resampled, pd.DataFrame):
            raise ValueError(
                "interpolate() must be run before fetching the resampled waypoints."
            )

        waypoints: list[SpireWaypointPositional] = []
        for _, r in self._waypoints_df_resampled.iterrows():
            wp = SpireWaypointPositional(
                ingestion_time=None,
                timestamp=r["time"].strftime("%Y-%m-%dT%H:%M:%SZ"),
                latitude=r["latitude"],
                longitude=r["longitude"],
                collection_type=None,
                altitude_baro=r["altitude_ft"],
                imputed=r["imputed"],
                flight_level=r["flight_level"],
            )
            waypoints.append(wp)
        return waypoints

    @classmethod
    def altitude_ft_to_flight_level(cls, alt_ft: int):
        """
        Converts altitude in feet MSL to flight level (100s of ft), snapped to the nearest level.
        """
        diff = lambda i: abs(cls.FLIGHT_LEVELS[i] - alt_ft // 100)  # noqa:E731
        min_ix = min(range(len(cls.FLIGHT_LEVELS)), key=diff)
        return cls.FLIGHT_LEVELS[min_ix]


class PerfModelLookup:
    """
    Simple wrapper to serve up the performance model lookup table.

    The performance model lookup table provides a master reference
    between an icao aircraft type identifier, and
    1) our specified cocip performance model,
    2) the engine type to use with that aircraft type.
    """

    PERF_LOOKUP_FP = "lib/perf_model_aircraft_lookup_no_bada_041824.json"

    lookup: dict[str, dict[str, str]]
    with open(PERF_LOOKUP_FP, "r") as fp:
        lookup = json.load(fp)

    @property
    def aircraft_type_icao(self) -> list[str]:
        """
        returns the supported aircraft types in the perf lookup
        """
        return list(self.lookup.keys())

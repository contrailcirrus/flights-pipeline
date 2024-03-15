"""
Application handlers.
"""

import copy
import math
import time
from threading import Thread
from typing import Union

import numpy as np
import pandas as pd
from datetime import datetime

from pycontrails.physics import geo

from lib.log import logger, format_traceback
from lib.schemas import (
    SpireWaypointsRecord,
    SpireWaypointPositional,
    SpireFlightInfo,
)
from lib.schemas import WaypointCache

from google.api_core import retry
from google.cloud import pubsub_v1
from pycontrails.core.flight import Flight
import redis
from redis.retry import Retry
from redis.backoff import ExponentialBackoff

import warnings


class PubSubSubscriptionHandler:
    """
    Handler for managing consumption and marshalling of jobs from a pubsub subscription queue.
    """

    # the number of seconds the subscriber client will hang, waiting for available messages
    MSG_WAIT_TIME_SEC = 60.0
    ACK_EXTENSION_SEC: int = 300

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
        self._kill_ack_manager = False
        self._ack_manager = Thread(target=self._ack_management_worker, daemon=True)
        self._ack_manager.start()

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

    def _ack_management_worker(self):
        """
        Extends the ack deadline for the currently outstanding message.
        """
        logger.info("starting ack lease management worker...")
        while not self._kill_ack_manager:
            time.sleep(self.ACK_EXTENSION_SEC // 2)
            if self._ack_id:
                logger.info(
                    f"extending ack deadline on ack_id: {self._ack_id[0:-150]}..."
                )
                try:
                    self._client.modify_ack_deadline(
                        request={
                            "subscription": self.subscription,
                            "ack_ids": [self._ack_id],
                            "ack_deadline_seconds": self.ACK_EXTENSION_SEC,
                        }
                    )
                except Exception:
                    logger.error(
                        f"failed to extend ack deadline for message. "
                        f"traceback: {format_traceback()}"
                    )
        logger.info("terminated ack lease management worker")

    def fetch(self) -> SpireWaypointsRecord:
        """
        Fetch a message from the subscription queue.
        This method will hang and wait until a message is available.
        This method, in case of exception, will hang, backoff and retry indefinitely.

        Returns
        -------
        str
            The dequeued message from the pubsub subscription.
        """
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
                retry=retry.Retry(timeout=30.0),
                timeout=self.MSG_WAIT_TIME_SEC,
            )

            if len(resp.received_messages) == 0:
                # it is possible there are no messages available,
                # or, pubsub returned zero when there are in fact some messages to fetch on retry
                logger.info("zero messages received.")
                continue
            msg = resp.received_messages[0]
            self._ack_id = msg.ack_id
            logger.info(
                f"received 1 message from {self.subscription}. "
                f"published_time: {msg.message.publish_time}, "
                f"message_id: {msg.message.message_id}"
            )
            return SpireWaypointsRecord.from_utf8_json(msg.message.data)

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
            retry=retry.Retry(timeout=30.0),
        )
        logger.info("successfully ack'ed message.")
        self._ack_id = None

    def close(self):
        """
        Close pubsub client connection.
        """
        self._kill_ack_manager = True
        self._client.close()


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

    def pull(self, key: str) -> list[WaypointCache]:
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

        self._max_cached_ts: datetime | None
        self._min_records_ts: datetime
        if self._cached_records:
            self._max_cached_ts = datetime.fromisoformat(
                self._cached_records[-1].timestamp
            )
        else:
            self._max_cached_ts = None
        self._min_records_ts = datetime.fromisoformat(self._records[0].timestamp)

        # raise on instantiation if data is invalid (possible out-of-order)
        self._verify_temporal_order()

    def _verify_temporal_order(self):
        """
        Verifies that the batch window of records trails the cached records in time.
        Failure to meet this criteria may indicate out-of-order delivery of records.
        """

        # possible out-of-order delivery
        if self._max_cached_ts and self._min_records_ts < self._max_cached_ts:
            raise Exception(
                f"records must have timestamp after cached timestamp. "
                f"received records for icao_address {self._flight_info.icao_address} "
                f"with timestamp {self._min_records_ts.isoformat()} occurring before "
                f"cached timestamp {self._max_cached_ts.isoformat()}"
            )

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

        cache_to_records_elapsed_hr = (
            self._min_records_ts - self._max_cached_ts
        ).seconds / 3600
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
        if (
            cache_to_records_elapsed_hr >= self.LANDING_TO_TAKEOFF_DELAY_HR
            and cache_to_records_avg_kph <= self.IN_FLIGHT_SPEED_THRESHOLD_KPH
        ):
            # case (B)
            logger.info(
                f"new flight instance inferred for icao_address {self._flight_info.icao_address} "
                f"at {self._min_records_ts.isoformat()}. invalidating cache."
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
        df_cached.rename(pycontrails_name_map, inplace=True)
        # note: pycontrails resample_and_fill returns df w/ naive timestamps, hence:
        df_cached["time"] = pd.to_datetime(df_cached["time"]).apply(
            lambda r: r.tz_localize(None)
        )
        self._max_cache_ts = df_cached["time"].max()

        df_records = pd.DataFrame(records_window)
        df_records.rename(
            columns={"altitude_baro": "altitude_ft", "timestamp": "time"}, inplace=True
        )
        df_records["time"] = pd.to_datetime(df_records["time"]).apply(
            lambda r: r.tz_localize(None)
        )
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

    @property
    def waypoints_resampled(self) -> list[SpireWaypointPositional]:
        """
        Returns
        -------
        List of SpireWaypointPositional objects, representing the resampled waypoints
        between the cached waypoints and the records waypoints passed to this handler.
        """
        if not self._waypoints_df_resampled:
            raise ValueError(
                "interpolate() must be run before fetching the resampled waypoints."
            )

        waypoints: list[SpireWaypointPositional] = []
        for _, r in self._waypoints_df_resampled.iterrows():
            wp = SpireWaypointPositional(
                timestamp=r["time"].strftime("%Y-%m-%dT%H:%M:%SZ"),
                latitude=r["latitude"],
                longitude=r["longitude"],
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

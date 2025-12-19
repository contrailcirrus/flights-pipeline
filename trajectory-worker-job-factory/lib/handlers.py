"""
Application handlers.
"""

import io

import asyncio
import concurrent.futures
import google.api_core.exceptions
import google.api_core.retry
import google.auth
import httpx
import os
import pandas as pd
import redis
import sys
import threading
from collections.abc import Iterator
from dataclasses import dataclass
from google.cloud import pubsub_v1, bigquery, storage  # type: ignore
from pycontrails import Flight
from redis.backoff import ExponentialBackoff
from redis.retry import Retry
from typing import Any, Callable

import lib.environment as env
from lib.exceptions import (
    BadTrajectoryException,
)
from lib.helpers import key_max_value_count
from lib.log import format_traceback, logger
from lib.schemas import SpireWaypointPositional, AirlineDayFlightsProgressMarker
from lib.utils import sigterm_manager


@dataclass(frozen=True)
class Message:
    data: bytes
    ack_id: str
    ordering_key: str


class PubSubSubscriptionHandler:
    """
    Handler for managing consumption and marshalling of jobs from a pubsub subscription queue.
    """

    def __init__(
        self,
        subscription: str,
        ack_extension_sec: float = 30,
        pull_timeout_sec: float = 60.0,
    ):
        """
        Parameters
        ----------
        subscription
            The fully-qualified URI for the pubsub subscription.
            e.g. 'projects/contrails-301217/subscriptions/api-preprocessor-sub-dev'
        ack_extension_sec
            Seconds the lease management thread will periodically extend the ack
            deadline for outstanding messages.
        pull_timeout_sec
            Seconds the subscriber client will block for messages before retrying.
        """
        self.subscription = subscription
        self.pull_timeout_sec = pull_timeout_sec
        self.ack_extension_sec = ack_extension_sec

        self._client = pubsub_v1.SubscriberClient()

        self._outstanding_messages: set[Message] = set()

    def _fetch(self) -> Message:
        """Fetch a message from the subscription queue.

        This method will hang and wait until a message is available. If an exception is
        raised, it will retry indefinitely.

        Returns
        -------
        Message
            The dequeued message from the pubsub subscription.
        """
        while True:
            if sigterm_manager.should_exit:
                sys.exit(0)
            logger.debug(f"fetching message from {self.subscription}")

            resp = self._client.pull(
                request={"subscription": self.subscription, "max_messages": 1},
                timeout=self.pull_timeout_sec,  # default: 60
                retry=google.api_core.retry.Retry(
                    initial=0.1,  # default: 0.1
                    maximum=60.0,  # default: 60
                    multiplier=1.3,  # default: 1.3
                    predicate=google.api_core.retry.if_exception_type(
                        # Non-default exceptions:
                        google.api_core.exceptions.DeadlineExceeded,
                        # Default exceptions:
                        google.api_core.exceptions.Aborted,
                        google.api_core.exceptions.InternalServerError,
                        google.api_core.exceptions.ServiceUnavailable,
                        google.api_core.exceptions.Unknown,
                    ),
                    deadline=60.0,  # default: 60
                ),
            )

            if len(resp.received_messages) == 0:
                # it is possible there are no messages available,
                # or, pubsub returned zero when there are in fact some messages
                logger.info("zero messages received.")
                continue

            pubsub_msg = resp.received_messages[0]
            logger.debug(
                f"received 1 message from {self.subscription}. "
                f"published_time: {pubsub_msg.message.publish_time}, "
                f"message_id: {pubsub_msg.message.message_id}"
            )

            message = Message(
                data=pubsub_msg.message.data,
                ack_id=pubsub_msg.ack_id,
                ordering_key=pubsub_msg.message.ordering_key,
            )
            return message

    def subscribe(self) -> Iterator[Message]:
        """Yields messages from the subscription.

        This method returns an iterator to loop over messages in the subscription. While
        iterating over the result, a sidecar thread will periodically extend the ack
        deadlines associated with outstanding messages to avoid redelivery while work
        is in progress.
        """
        # Start lease manager thread to periodically extend ack deadline.
        exit_when_set = threading.Event()
        lease_manager = threading.Thread(
            target=self._ack_management_worker,
            kwargs=dict(exit_when_set=exit_when_set),
            daemon=True,
        )
        lease_manager.start()

        try:
            while True:
                message = self._fetch()
                self._outstanding_messages.add(message)
                yield message
                # Guard against user failing to call ack() or nack()
                if message in self._outstanding_messages:
                    logger.warning(f"message was never ack'ed or nack'ed: {message}")
                    self._outstanding_messages.discard(message)
        except GeneratorExit:
            pass

        # Signal lease manager thread exit
        exit_when_set.set()
        # Block until lease manager thread exits
        lease_manager.join()

    def ack(self, message: Message):
        """Acknowledge the message to remove from the queue."""
        # Stop extending lease before server-side ack. This avoids cases where the lease
        # management worker fails to extend the ack deadline for an already ack'ed
        # message, at the cost of a small probability of redelivery.
        try:
            self._outstanding_messages.remove(message)
        except KeyError:
            logger.warning(f"message ack'ed or nack'ed multiple times: {message}")

        self._client.acknowledge(
            request={"subscription": self.subscription, "ack_ids": [message.ack_id]},
            timeout=30.0,  # default: 60
            retry=google.api_core.retry.Retry(
                initial=0.1,  # default: 0.1
                maximum=60.0,  # default: 60
                multiplier=1.3,  # default: 1.3
                predicate=google.api_core.retry.if_exception_type(
                    # Non-default exceptions:
                    google.api_core.exceptions.DeadlineExceeded,
                    # Default exceptions:
                    google.api_core.exceptions.ServiceUnavailable,
                ),
            ),
        )
        logger.debug("successfully ack'ed message.")

    def nack(self, message: Message):
        """Not-acknowledge the message to stop extending ack deadline.

        Does not nack the message server-side, so the message will be retried based on
        the server-side redelivery configuration rather than immediately redelivered to
        another worker.
        """
        try:
            self._outstanding_messages.remove(message)
        except KeyError:
            logger.warning(f"message ack'ed or nack'ed multiple times: {message}")

    def _ack_management_worker(self, exit_when_set: threading.Event):
        """
        Extends the ack deadline for the currently outstanding message.
        """
        logger.debug("starting ack lease management worker...")
        while True:
            should_exit = exit_when_set.wait(self.ack_extension_sec / 2)
            if should_exit:
                break

            # Avoid iterating over a mutable set.
            messages = self._outstanding_messages.copy()
            for message in messages:
                ack_id = message.ack_id
                logger.debug(f"extending ack deadline on ack_id: {ack_id[0:-150]}...")
                try:
                    self._client.modify_ack_deadline(
                        request={
                            "subscription": self.subscription,
                            "ack_ids": [ack_id],
                            "ack_deadline_seconds": self.ack_extension_sec,
                        }
                    )
                except Exception:
                    logger.warning(
                        "failed to extend ack deadline for message. "
                        f"traceback: {format_traceback()}"
                    )

        logger.debug("terminated ack lease management worker")


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
                    message_limit=1000,
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


class BigQueryHandler:
    def __init__(self):
        self._client = (
            bigquery.Client()
        )  # assume caller's identify from local gcloud certs

    def query(
        self, query_str: str, job_config: bigquery.QueryJobConfig
    ) -> pd.DataFrame:
        """
        Queries the BigQuery API.

        Parameters
        ----------
        query_str
            string representation of the SQL query to dispatch
        job_config
            job configuration, including parametrized values in the query (if any)

        Returns
        -------
        dataframe with one row per waypoint
        """

        query_job = self._client.query(query_str, job_config=job_config)
        rows = query_job.result()  # block until query is available
        return rows.to_dataframe()

    @staticmethod
    def import_query(filename: str) -> str:
        """
        Import a query as a single string with inline \n
        """
        with open(filename, "r") as fp:
            return fp.read()


class SpireApiHandler:
    """
    Handler for managing the fetch of ADS-B data from the Spire API endpoint of contrails.org
    """

    URI_BASE = "https://api.contrails.org/v1/adsb/telemetry"
    API_CONCURRENCY = 4  # concurrency with which to fetch data from telemetry API

    def fetch_airline_days(
        self, days: list[str], airline_iata: str, prune: bool = False
    ):
        """
        Fetch data from contrails.org Spire ADS-B API for specified days and airline.

                Parameters
        ----------
        days
            list of target days for flights; fmt "%Y-%m-%d"
        airline_iata
            airline iata designator for which to fetch ads-b
        prune
            if true, 12 hours will be pruned from the left-hand-side of the first day in the list,
            and 7 hours will be pruned from the right-hand-side of the last day in the list.

        Returns
        -------
        pd.Dataframe
            telemetry data for the target airline and day
        """

        if len(days) < 2 and prune:
            raise NotImplementedError(
                "cannot prune when number of days provided is fewer than 3."
            )

        datetime_hourly_strs: list[str] = []
        for day in days:
            for hr in range(0, 24):
                datetime_hourly_strs.append(f"{day}T{hr:02}")

        if prune:
            datetime_hourly_strs = datetime_hourly_strs[12:-7]

        df = asyncio.run(
            self.fetch_airline_uris(
                datetime_hourly_strs,
                airline_iata,
                concurrency=self.API_CONCURRENCY,
            )
        )

        return df

    @classmethod
    async def _fetch_airline_telemetry(
        cls,
        semaphore: asyncio.locks.Semaphore,
        time: str,
        airline_iata: str,
    ) -> pd.DataFrame:
        """
        Call the provided uri, subset for the target airline,
        and return content as pandas dataframe.

        Parameters
        ----------
        semaphore
            a semaphore object for rate limiting async

        times
            list of target times. fmt: "%Y-%m-%dT%H"

        airline_iata
            the airline iata code upon which to filter the response content

        Returns
        -------
        pd.DataFrame
            telemetry content for the given airline day
        """

        header = {"x-api-key": env.CONTRAILS_API_KEY}
        params = {"date": time}

        async with semaphore, httpx.AsyncClient() as client:
            r = await client.get(
                cls.URI_BASE,
                params=params,
                headers=header,
                timeout=120,
            )
            r.raise_for_status()

        # write out response content as parquet file
        df = pd.read_parquet(io.BytesIO(r.content))
        return df[df["airline_iata"] == airline_iata]

    async def fetch_airline_uris(
        self, times: list[str], airline_iata: str, concurrency: int
    ):
        """
        Run the fetch_target_hour() function for each time in the times list.

        Parameters
        ----------
        times
            list of target times. fmt: "%Y-%m-%dT%H"

        airline_iata
            airline iata code upon which to filter results

        concurrency
            max concurrency for REST calls to API
        """
        sem_lock = asyncio.Semaphore(concurrency)

        routines = [
            self._fetch_airline_telemetry(sem_lock, datehour, airline_iata)
            for datehour in times
        ]
        results: list[pd.DataFrame]
        results = await asyncio.gather(*routines)
        df_all = pd.concat(results)
        return df_all


class CloudStorageHandler:
    """
    Handler for managing the fetch of ADS-B data from the Spire raw Parquet file cache.
    """

    GCS_BUCKET_SPIRE_CACHE = "contrails-301217-spire-cache-prod"

    def __init__(self):
        self._client = storage.Client()
        self._bucket = self._client.bucket(self.GCS_BUCKET_SPIRE_CACHE)

    def fetch_airline_days(
        self, days: list[str], airline_iata: str, prune: bool = False
    ) -> pd.DataFrame:
        """
        Fetch data from GCS for a given airline, over the specified days.

        Parameters
        ----------
        days
            list of target days for flights; fmt "%Y-%m-%d"
        airline_iata
            airline iata designator for which to fetch ads-b
        prune
            if true, 12 hours will be pruned from the left-hand-side of the first day in the list,
            and 7 hours will be pruned from the right-hand-side of the last day in the list.

        Returns
        -------
        pd.Dataframe
            telemetry data for the target airline and day
        """

        if len(days) < 2 and prune:
            raise NotImplementedError(
                "cannot prune when number of days provided is fewer than 3."
            )

        datetime_hourly_strs: list[str] = []
        for day in days:
            for hr in range(0, 24):
                datetime_hourly_strs.append(f"{day}T{hr:02}")

        if prune:
            datetime_hourly_strs = datetime_hourly_strs[12:-7]

        bq_blob_uri_prefixes = [
            f"hourly/{datetime_hr}" for datetime_hr in datetime_hourly_strs
        ]

        # map of hourly prefix to GCS blob objects available for that prefix
        bq_blob_map: dict[str, list[storage.blob.Blob]] = dict()
        for uri_prefix in bq_blob_uri_prefixes:
            bq_blob_map.update(
                {uri_prefix: list(self._bucket.list_blobs(prefix=f"{uri_prefix}/"))}
            )

        # confirm that all target data is available
        for k, blob_lst in bq_blob_map.items():
            if not blob_lst:
                raise FileNotFoundError(f"No ADS-B files found in GCS with prefix: {k}")

        # fetch all ads-b data from target blobs, and subset to only the target airline_iata
        df_parts: list[pd.DataFrame] = []
        # iterate serially here (since we subset on airline iata to keep mem footprint low
        # on each iteration)
        for (
            k,
            _,
        ) in bq_blob_map.items():  # load all pq shards in subdir at once into a df
            uri = f"gs://{self._bucket.name}/{k}"
            logger.info("fetching " + uri)
            df = pd.read_parquet(uri)
            df = df[df["airline_iata"] == airline_iata]
            df_parts.append(df)
        df = pd.concat(df_parts)
        return df


class HealTrajectoryHandler:
    """
    Takes a dataset with a single flight trajectory (single flight_id)
    and applies a ruleset to heal quality issues with trajectories.
    """

    def __init__(self, min_speed_m_s, max_speed_m_s):
        self._df: pd.DataFrame | None = None
        self._min_speed_m_s = min_speed_m_s
        self._max_speed_m_s = max_speed_m_s
        self._max_speed_filter_iterations = 5

    def set(self, trajectory: pd.DataFrame):
        """
        Sets a target trajectory into this handler's state.

        Parameters
        ----------
        trajectory
            A dataset with one flight trajectory.
            Each trajectory is identified by its flight_id.
            Dataset must include columns matching those in the BQ table `spire_flights_raw_prod`
        """
        if len(trajectory) == 0:
            raise BadTrajectoryException("flight trajectory is empty.")
        if len(trajectory["flight_id"].unique()) > 1:
            raise Exception(
                "dataset passed to handler must be for a single flight instance ("
                "flight_id)."
            )
        self._df = trajectory.copy(deep=True)

    def unset(self):
        """
        Pops a trajectory from this handler's state.
        """
        self._df = None

    @staticmethod
    def _get_priority_map(df: pd.DataFrame, cols: list) -> dict:
        """
        Given a dataframe and list of columns,
        return a mapping of the column name to the value of highest count in the column.

        Parameters
        ----------
        df
            A pandas dataframe
        cols
            Names of columns for evaluation. e.g. col=["callsign", "airline_iata"]

        Returns
        ----------
        A dict with mapping of cols to value of highest count
        e.g.
        {"callsign": None, "airline_iata": AA}
        """

        resp = {}
        for col in cols:
            prio_val = key_max_value_count(df, col)
            resp.update({col: prio_val})
        return resp

    @staticmethod
    def _dataframe_convert_types(df: pd.DataFrame) -> pd.DataFrame:
        """
        Attempt to convert types for each dataframe column to expected type.
        Implicitly also checks for existence of expected columns.
        """
        cols = {
            "icao_address": str,
            "flight_id": str,
            "callsign": str,
            "tail_number": str,
            "flight_number": str,
            "aircraft_type_icao": str,
            "airline_iata": str,
            "departure_airport_icao": str,
            "departure_scheduled_time": "datetime64[ns, UTC]",
            "arrival_airport_icao": str,
            "arrival_scheduled_time": "datetime64[ns, UTC]",
            "timestamp": "datetime64[ns, UTC]",
            "latitude": float,
            "longitude": float,
            "collection_type": str,
            "altitude_baro": int,
        }
        return df.astype(cols)

    @staticmethod
    def _filter_speeds(
        df: pd.DataFrame, min_speed_m_s: float, max_speed_m_s: float
    ) -> pd.DataFrame:
        """
        Filter data points to keep only those with speeds between the allowed min and
        max. Expects the "timestamp" column of the input df to be sorted and unique.
        """
        # create a new df for computing ground speed
        speed_df = df[["timestamp", "latitude", "longitude"]]
        speed_df.rename(columns={"timestamp": "time"}, inplace=True)
        speed_df["altitude"] = None  # dummy, not used in ground speed calculation
        speed_df["ground_speed_m_s"] = Flight(speed_df).segment_groundspeed()

        # The `shift()` method is used to offset the "ground_speed_m_s" column by 1,
        # so data points on both sides of an invalid speed are dropped.
        valid_speed_idx = speed_df["ground_speed_m_s"].between(
            min_speed_m_s, max_speed_m_s, inclusive="neither"
        ) & speed_df["ground_speed_m_s"].shift(1).between(
            min_speed_m_s, max_speed_m_s, inclusive="neither"
        )
        return df[valid_speed_idx]

    def heal(self) -> pd.DataFrame:
        """
        Manipulate trajectories with qaqc heuristics.

        Returns
        -------
        Dataset mirroring initiated dataset, with manipulations applied.
        """

        try:
            self._df = self._dataframe_convert_types(self._df)
            self._df.replace("nan", None, inplace=True)
            self._df.replace("None", None, inplace=True)
        except KeyError as e:
            raise KeyError(
                "flight trajectory dataframe is missing an expected column."
            ) from e

        # --------------
        # update dataset so the following target keys are uniform/distinct for a given flight
        # --------------
        target_cols = [
            "callsign",
            "flight_number",
            "arrival_airport_icao",
            "departure_airport_icao",
            "airline_iata",
        ]

        priority_values = self._get_priority_map(self._df, target_cols)

        # fill any null values with our priority values
        for col, val in priority_values.items():
            if val:
                self._df[col] = self._df[col].fillna(val)

        # drop any rows where our column values don't match the priority value
        for col, val in priority_values.items():
            if val:
                keep_filter = self._df[col] == val
                self._df = self._df[keep_filter]
                drop_cnt = (~keep_filter).sum()
                if drop_cnt:
                    logger.info(
                        f"dropping {drop_cnt} values not matching:{val} for field: {col}."
                    )

        # --------------
        # Drop data points where computed ground speed is too slow or too fast. The
        # "too slow" case is often taxiing. The "too fast" case is often caused by
        # small misalignments between receiver timestamps.
        # --------------
        self._df.sort_values(by="timestamp", ascending=True, inplace=True)
        self._df.drop_duplicates(["timestamp"], inplace=True)

        # Iteratively apply the speed filter, to cover cases where (for example) two
        # points with invalid speeds have a third point between them. The middle point
        # would not be dropped in a single iteration, but may be dropped in a second
        # one.
        iterations = self._max_speed_filter_iterations
        while iterations:
            prev_len = len(self._df)
            self._df = self._filter_speeds(
                self._df, self._min_speed_m_s, self._max_speed_m_s
            )
            # stop filtering once no data points are dropped
            if len(self._df) == prev_len:
                break
            iterations -= 1

        self._df.reset_index(drop=True, inplace=True)
        if len(self._df) == 0:
            raise BadTrajectoryException("flight trajectory is empty.")
        return self._df


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
        200,
        210,
        220,
        230,
        240,
        250,
        260,
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

    def __init__(self):
        self._min_records_ts: pd.Timestamp | None = None
        self._waypoints_df: pd.DataFrame | None = None
        self._waypoints_df_resampled: pd.DataFrame | None = None

    def set(self, records_window: list[SpireWaypointPositional]):
        """
        sets the following into this handler's state:
        - _min_records_ts
        - _waypoints_df
        """
        df_records = pd.DataFrame(records_window)
        df_records.rename(
            columns={"altitude_baro": "altitude_ft", "timestamp": "time"}, inplace=True
        )
        df_records["time"] = pd.to_datetime(df_records["time"]).apply(
            lambda r: r.tz_localize(None)
        )

        df_records.drop_duplicates(["time"], inplace=True)

        self._min_records_ts = df_records["time"].min()
        self._waypoints_df = df_records

    def unset(self):
        """
        pops the following from this handler's state:
        - _waypoints_df_resampled
        - _min_records_ts
        - _waypoints_df
        """
        self._min_records_ts = None
        self._waypoints_df = None
        self._waypoints_df_resampled = None

    def interpolate(self):
        """
        Run minute interpolation within the records time window, and backwards between
        the first index of the records time window and the cached waypoints.
        """
        pyc_flight = Flight(self._waypoints_df)
        flight_resampled: pd.DataFrame = pyc_flight.resample_and_fill().dataframe

        # add imputation flags
        # TODO add heuristics to appropriately apply imputation flag for full-trajectory resampling
        flight_resampled["imputed"] = False

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
        if alt_ft < (cls.FLIGHT_LEVELS[0] * 100) - 500:
            return -999
        diff = lambda i: abs(cls.FLIGHT_LEVELS[i] - alt_ft // 100)  # noqa:E731
        min_ix = min(range(len(cls.FLIGHT_LEVELS)), key=diff)
        return cls.FLIGHT_LEVELS[min_ix]


class RedisHandler:
    """
    Handler for interfacing with a remote redis cache.
    """

    KEY_EXPIRY_SEC = 4 * 60 * 60  # seconds before a key expires

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

    def pull(self, key: str) -> int:
        """
        Retrieves the value for a key in redis.

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
        cache_resp = redis_client.get(key)
        return AirlineDayFlightsProgressMarker.from_redis_resp(cache_resp)

    def pop(self, key: str):
        """
        Removes a k-v from redis.

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
        redis_client.delete(key)

    def push(self, cache_entry: AirlineDayFlightsProgressMarker):
        """
        Parameters
        ----------
        cache_entry:
            An AirlineDayFlightsProgressMarker
            The key is composed based on the airline iata and day.
            The value is the marker integer.
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
            transaction.set(name=cache_entry.key, value=cache_entry.value)
            transaction.expire(cache_entry.key, self.KEY_EXPIRY_SEC)
            transaction.execute()
        finally:
            redis_client.connection_pool.disconnect()

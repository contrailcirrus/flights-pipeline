"""
Application handlers.
"""

import concurrent.futures
import math
import os
import sys
import threading
from collections.abc import Iterator
from dataclasses import dataclass
from typing import Any, Callable

import numpy as np
import pandas as pd
import pandas.api.types as pdtypes

import google.api_core.exceptions
import google.api_core.retry
import google.auth
from google.cloud import pubsub_v1, bigquery  # type: ignore
from pycontrails import Flight
from pycontrails.physics import geo
from pycontrails.core import airports

from lib.exceptions import (
    BadTrajectoryException,
    SchemaError,
    OrderingError,
    FlightInvariantFieldViolation,
    FlightDuplicateTimestamps,
    FlightTooShortError,
    FlightTooLongError,
    OriginAirportError,
    DestinationAirportError,
    FlightTooSlowError,
    FlightTooFastError,
    FlightAltitudeProfileError,
    RocdError,
)
from lib.helpers import key_max_value_count
from lib.log import format_traceback, logger
from lib.schemas import SpireWaypointPositional
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
                    logger.warning(f"Message was never ack'ed or nack'ed: {message}")
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
            logger.warning(f"Message ack'ed or nack'ed multiple times: {message}")

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
            logger.warning(f"Message ack'ed or nack'ed multiple times: {message}")

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


class HealTrajectoryHandler:
    """
    Takes a dataset with a single flight trajectory (single flight_id)
    and applies a ruleset to heal quality issues with trajectories.
    """

    def __init__(self):
        self._df: pd.DataFrame | None = None

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
            "ingestion_time": "datetime64[ns, UTC]",
            "timestamp": "datetime64[ns, UTC]",
            "latitude": float,
            "longitude": float,
            "collection_type": str,
            "altitude_baro": int,
        }
        return df.astype(cols)

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

        self._df.sort_values(by="timestamp", ascending=True, inplace=True)
        self._df.reset_index(drop=True, inplace=True)
        if len(self._df) == 0:
            raise BadTrajectoryException("flight trajectory is empty.")
        return self._df


class ValidateTrajectoryHandler:
    """
    Evaluates trajectory and identifies if it violates any verification rules.
    """

    CRUISE_ROCD_THRESHOLD_FPS = 4.2  # 4.2 ft/sec ~= 250 ft/min
    CRUISE_LOW_ALTITUDE_THRESHOLD_FT = 15000  # lowest expected cruise altitude
    INSTANTANEOUS_HIGH_GROUND_SPEED_THRESHOLD_MPS = 350  # 350m/sec ~= 780mph ~= 1260kph
    INSTANTANEOUS_LOW_GROUND_SPEED_THRESHOLD_MPS = 45  # 45m/sec ~= 100mph ~= 160kph
    AVG_LOW_GROUND_SPEED_THRESHOLD_MPS = 100  # 120m/sec ~= 223mph ~= 360 kph
    AVG_LOW_GROUND_SPEED_ROLLING_WINDOW_PERIOD_MIN = (
        30  # rolling period for avg speed comparison
    )
    AIRPORT_DISTANCE_THRESHOLD_KM = 200
    MIN_FLIGHT_LENGTH_HR = 0.4
    MAX_FLIGHT_LENGTH_HR = 19

    # expected schema of pandas dataframe passed on initialization
    SCHEMA = {
        "icao_address": pdtypes.is_string_dtype,
        "flight_id": pdtypes.is_string_dtype,
        "callsign": pdtypes.is_string_dtype,
        "tail_number": pdtypes.is_string_dtype,
        "flight_number": pdtypes.is_string_dtype,
        "aircraft_type_icao": pdtypes.is_string_dtype,
        "airline_iata": pdtypes.is_string_dtype,
        "departure_airport_icao": pdtypes.is_string_dtype,
        "departure_scheduled_time": pdtypes.is_datetime64_any_dtype,
        "arrival_airport_icao": pdtypes.is_string_dtype,
        "arrival_scheduled_time": pdtypes.is_datetime64_any_dtype,
        "ingestion_time": pdtypes.is_datetime64_any_dtype,
        "timestamp": pdtypes.is_datetime64_any_dtype,
        "latitude": pdtypes.is_numeric_dtype,
        "longitude": pdtypes.is_numeric_dtype,
        "collection_type": pdtypes.is_string_dtype,
        "altitude_baro": pdtypes.is_numeric_dtype,
    }

    airports_db = airports.global_airport_database()

    def __init__(self):
        self._df: pd.DataFrame | None = None

    def set(self, trajectory: pd.DataFrame):
        """
        Sets a single flight trajectory into handler state.

        Parameters
        -------------
        trajectory
            A dataframe representing a single flight trajectory.
            Must have the same columns as in our spire raw data (see BQ table spire_flights_raw_prod).
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
        Pop _df from handler state.
        """
        self._df = None

    @classmethod
    def _find_airport_coords(
        cls, airport_icao: str | None
    ) -> tuple[np.floating, np.floating, np.floating]:
        """
        Find the latitude and longitude for a given airport.

        Parameters
        ------------
        airport_icao
            string representation of the airport's icao code

        Returns
        -----------
        (latitude, longitude, alt_ft) of the airport.
        Returns (np.nan, np.nan, np.nan) if it cannot be found.
        """

        if not isinstance(airport_icao, str):
            return np.nan, np.nan, np.nan

        matches = cls.airports_db[cls.airports_db["icao_code"] == airport_icao]
        if len(matches) == 0:
            return np.nan, np.nan, np.nan
        if len(matches) > 1:
            raise ValueError(
                f"found multiple matches for aiport icao {airport_icao} "
                f"in airports database."
            )

        lat = matches.iloc[0]["latitude"]
        lon = matches.iloc[0]["longitude"]
        alt_ft = matches.iloc[0]["elevation_ft"]
        if (
            not isinstance(lat, np.floating)
            or not isinstance(lon, np.floating)
            or not isinstance(alt_ft, np.floating)
        ):
            raise ValueError(
                f"expected (float, float, float) for lat, lon and alt_ft. "
                f"got: ({lat}, {lon}, {alt_ft})"
            )
        return lat, lon, alt_ft

    @staticmethod
    def _calc_distance_m(lat_0, lon_0, alt_ft_0, lat_f, lon_f, alt_ft_f) -> float:
        """
        calculate great circle distance between two lat/lon/alt coordinates.
        """
        dist_m = math.sqrt(
            (0.3048 * (alt_ft_f - alt_ft_0)) ** 2
            + geo.haversine(
                lons1=np.array(lon_f),
                lats1=np.array(lat_f),
                lons0=np.array(lon_0),
                lats0=np.array(lat_0),
            )
            ** 2
        )
        return dist_m

    @staticmethod
    def _rolling_time_delta_seconds(roll_window: pd.DataFrame):
        """
        Given two consecutive rows (ordered by ascending timestamp),
        calculate the elapsed time in seconds between the two rows

        Parameters
        -----------
        roll_window
            A pd.Dataframe with ordered timestamps

        Returns
        -----------
        np.nan or integer value for seconds
        """
        if len(roll_window) == 1:
            return np.nan
        t_0 = roll_window.iloc[0]["timestamp"]
        t_f = roll_window.iloc[1]["timestamp"]
        dt_sec = (t_f - t_0).total_seconds()
        if dt_sec < 0:
            raise ValueError(
                "found negative elapsed time. "
                "window must be ordered in ascending timestamp."
            )

        return int(dt_sec)

    @classmethod
    def _rolling_distance_meters(cls, roll_window: pd.DataFrame):
        """
        Given two consecutive rows,
        impute the distance travelled.

        Parameters
        -----------
        roll_window
            A pd.Dataframe with ordered timestamps

        Returns
        -----------
        np.nan or integer value for seconds
        """
        if len(roll_window) == 1:
            return np.nan

        lat_0 = roll_window.iloc[0]["latitude"]
        lat_f = roll_window.iloc[1]["latitude"]

        lon_0 = roll_window.iloc[0]["longitude"]
        lon_f = roll_window.iloc[1]["longitude"]

        alt_0 = roll_window.iloc[0]["altitude_baro"]
        alt_f = roll_window.iloc[1]["altitude_baro"]

        dist_m = cls._calc_distance_m(lat_0, lon_0, alt_0, lat_f, lon_f, alt_f)
        return dist_m

    @classmethod
    def _rolling_rocd_fps(cls, roll_window: pd.DataFrame) -> float:
        """
        Given two consecutive rows,
        impute the rate of climb/descent.

        Parameters
        -----------
        roll_window
            A pd.Dataframe with ordered timestamps

        Returns
        -----------
        np.nan or float value for rocd in feet per second
        """
        if "elapsed_seconds" not in roll_window.columns:
            raise ValueError("field elapsed_seconds must be present.")

        if len(roll_window) == 1:
            return np.nan

        alt_ft_0 = roll_window.iloc[0]["altitude_baro"]
        alt_ft_f = roll_window.iloc[1]["altitude_baro"]
        alt_ft_dt = alt_ft_f - alt_ft_0
        rocd = alt_ft_dt / roll_window.iloc[1]["elapsed_seconds"]
        if np.isinf(rocd):
            rocd = np.nan
        return rocd

    @classmethod
    def _calc_dist_to_departure_airport(cls, row: pd.Series) -> float:
        """
        Calculate the distance from a given waypoint to the departure airport.

        Returns
        --------
        distance in meters to departure airport.
        np.nan if it cannot be calculated.
        """
        if "departure_airport_lat" not in row.index:
            raise ValueError("field departure_airport_lat must be present.")
        if "departure_airport_lon" not in row.index:
            raise ValueError("field departure_airport_lon must be present.")
        if "departure_airport_alt_ft" not in row.index:
            raise ValueError("field departure_airport_alt_ft must be present.")

        departure_lon = row["departure_airport_lon"]
        departure_lat = row["departure_airport_lat"]
        departure_alt_ft = row["departure_airport_alt_ft"]
        if any(
            [
                np.isnan(departure_lon),
                np.isnan(departure_lat),
                np.isnan(departure_alt_ft),
            ]
        ):
            return np.nan

        return cls._calc_distance_m(
            lon_0=row["longitude"],
            lat_0=row["latitude"],
            alt_ft_0=row["altitude_baro"],
            lon_f=departure_lon,
            lat_f=departure_lat,
            alt_ft_f=departure_alt_ft,
        )

    @classmethod
    def _calc_dist_to_arrival_airport(cls, row: pd.Series) -> float:
        """
        Calculate the distance from a given waypoint to the arrival airport.

        Returns
        --------
        distance in meters to arrival airport.
        np.nan if it cannot be calculated.
        """

        if "arrival_airport_lat" not in row.index:
            raise ValueError("field arrival_airport_lat must be present.")
        if "arrival_airport_lon" not in row.index:
            raise ValueError("field arrival_airport_lon must be present.")
        if "arrival_airport_alt_ft" not in row.index:
            raise ValueError("field arrival_airport_alt_ft must be present.")

        arrival_lon = row["arrival_airport_lon"]
        arrival_lat = row["arrival_airport_lat"]
        arrival_alt_ft = row["arrival_airport_alt_ft"]
        if any(
            [np.isnan(arrival_lon), np.isnan(arrival_lat), np.isnan(arrival_alt_ft)]
        ):
            return np.nan

        return cls._calc_distance_m(
            lon_0=row["longitude"],
            lat_0=row["latitude"],
            alt_ft_0=row["altitude_baro"],
            lon_f=arrival_lon,
            lat_f=arrival_lat,
            alt_ft_f=arrival_alt_ft,
        )

    def _calculate_additional_fields(self):
        """
        Adds additional columns to the provided dataframe.
        These additional fields are needed to apply the validation ruleset.
        """
        self._df = self._df.assign(
            elapsed_seconds=[
                self._rolling_time_delta_seconds(window)
                for window in self._df.rolling(window=2)
            ],
        )
        self._df = self._df.assign(
            elapsed_distance_m=[
                self._rolling_distance_meters(window)
                for window in self._df.rolling(window=2)
            ],
        )
        self._df = self._df.assign(
            ground_speed_m_s=self._df["elapsed_distance_m"]
            .divide(self._df["elapsed_seconds"])
            .replace(np.inf, np.nan)
        )
        self._df = self._df.assign(
            rocd_fps=[
                self._rolling_rocd_fps(window) for window in self._df.rolling(window=2)
            ]
        )

        if len(self._df["arrival_airport_icao"].value_counts()) > 1:
            raise ValueError(
                "expected only one airport icao for flight arrival airport."
            )

        if len(self._df["departure_airport_icao"].value_counts()) > 1:
            raise ValueError(
                "expected only one airport icao for flight departure airport."
            )

        departure_airport_lat_lon_alt = self._df["departure_airport_icao"].apply(
            self._find_airport_coords
        )
        arrival_airport_lat_lon_alt = self._df["arrival_airport_icao"].apply(
            self._find_airport_coords
        )
        self._df = self._df.assign(
            departure_airport_lat=[coord[0] for coord in departure_airport_lat_lon_alt],
            departure_airport_lon=[coord[1] for coord in departure_airport_lat_lon_alt],
            departure_airport_alt_ft=[
                coord[2] for coord in departure_airport_lat_lon_alt
            ],
            arrival_airport_lat=[coord[0] for coord in arrival_airport_lat_lon_alt],
            arrival_airport_lon=[coord[1] for coord in arrival_airport_lat_lon_alt],
            arrival_airport_alt_ft=[coord[2] for coord in arrival_airport_lat_lon_alt],
        )

        self._df = self._df.assign(
            departure_airport_dist_m=self._df.apply(
                self._calc_dist_to_departure_airport, axis=1
            ),
            arrival_airport_dist_m=self._df.apply(
                self._calc_dist_to_arrival_airport, axis=1
            ),
        )

    @classmethod
    def _is_valid_schema(cls, df: pd.DataFrame) -> None | SchemaError:
        """
        Verify that a pandas dataframe has required cols, and that they are of required type.
        """
        col_types = df.dtypes
        cols = list(col_types.index)

        missing_cols = [i for i in cls.SCHEMA.keys() if i not in cols]
        if len(missing_cols) > 0:
            return SchemaError(
                f"trajectory dataframe is missing expected fields: {missing_cols}"
            )

        col_w_bad_dtypes = []
        for col, check_fn in cls.SCHEMA.items():
            is_valid = check_fn(col_types[col])
            if not is_valid:
                col_w_bad_dtypes.append(f"{col} failed check {check_fn.__name__}")

        if len(col_w_bad_dtypes) > 0:
            return SchemaError(
                f"trajectory dataframe has columns with invalid data types. "
                f"\n {col_w_bad_dtypes}"
            )

    def _is_timestamp_sorted(self) -> None | OrderingError:
        """
        Verify that the data is sorted by waypoint timestamp in ascending order.
        """
        ts_index = pd.Index(self._df["timestamp"])
        if not ts_index.is_monotonic_increasing:
            return OrderingError(
                "trajectory dataframe must be sorted by timestamp in ascending order."
            )

    def _is_valid_invariant_fields(self) -> None | FlightInvariantFieldViolation:
        """
        Verify that fields expected to be invariant are indeed invariant.
        Presence of null values does not constitute an invariance violation.
        """
        invariant_fields = [
            "icao_address",
            "flight_id",
            "callsign",
            "tail_number",
            "aircraft_type_icao",
            "airline_iata",
            "departure_airport_icao",
            "departure_scheduled_time",
            "arrival_airport_icao",
            "arrival_scheduled_time",
        ]

        violations = []
        for k in invariant_fields:
            unique_vals = list(self._df[k].value_counts().index)
            if len(unique_vals) > 1:
                violations.append(k)

        if len(violations) > 0:
            return FlightInvariantFieldViolation(
                f"the following fields have multiple values for this trajectory. "
                f"{violations}"
            )

    def _is_valid_duplicate_timestamps(self) -> None | FlightDuplicateTimestamps:
        """
        Verifies that we do not have duplicate timestamps in the trajectory.
        """
        timestamp_dupe_cnt = self._df["timestamp"].duplicated().sum()
        if timestamp_dupe_cnt > 0:
            return FlightDuplicateTimestamps(
                f"duplicate waypoint timestamps found in "
                f"this trajectory. "
                f"found {timestamp_dupe_cnt} duplicates."
            )

    def _is_valid_flight_length(
        self,
    ) -> None | FlightTooShortError | FlightTooLongError:
        """
        Verifies that the flight is of a reasonable length.
        """
        flight_duration_sec = (
            self._df["timestamp"].max() - self._df["timestamp"].min()
        ).seconds
        flight_duration_hours = flight_duration_sec / 60.0 / 60.0

        if flight_duration_hours > self.MAX_FLIGHT_LENGTH_HR:
            return FlightTooLongError(
                f"flight exceeds max duration of {self.MAX_FLIGHT_LENGTH_HR} hours."
                f"this trajectory spans {flight_duration_hours:.2f} hours."
            )

        if flight_duration_hours < self.MIN_FLIGHT_LENGTH_HR:
            return FlightTooShortError(
                f"flight less than min duration of {self.MIN_FLIGHT_LENGTH_HR} hours. "
                f"this trajectory spans {flight_duration_hours:.2f} hours."
            )

    def _is_from_origin_airport(self) -> None | OriginAirportError:
        """
        Verify that the trajectory originates within a reasonable distance from the origin airport.
        """
        first_waypoint = self._df.iloc[0]
        first_waypoint_dist_km = first_waypoint["departure_airport_dist_m"] / 1000.0
        if first_waypoint_dist_km > self.AIRPORT_DISTANCE_THRESHOLD_KM:
            return OriginAirportError(
                f"first waypoint in trajectory too far from departure airport icao: "
                f"{first_waypoint['departure_airport_icao']}. "
                f"distance {first_waypoint_dist_km}km is greater than "
                f"threshold of {self.AIRPORT_DISTANCE_THRESHOLD_KM}km."
            )

    def _is_to_destination_airport(self) -> None | DestinationAirportError:
        """
        Verify that the trajectory terminates within a reasonable distance
        from the destination airport.

        We do not assume that the destination airports are invariant in the dataframe,
        thus we handle the case of multiple airports listed.
        """
        last_waypoint = self._df.iloc[-1]
        last_waypoint_dist_km = last_waypoint["arrival_airport_dist_m"] / 1000.0
        if last_waypoint_dist_km > self.AIRPORT_DISTANCE_THRESHOLD_KM:
            return DestinationAirportError(
                f"last waypoint in trajectory too far from arrival airport icao: "
                f"{last_waypoint['arrival_airport_icao']}."
                f"distance {last_waypoint_dist_km}km is greater than "
                f"threshold of {self.AIRPORT_DISTANCE_THRESHOLD_KM}km."
            )

    def _is_too_slow(self) -> None | list[FlightTooSlowError]:
        """
        Evaluates the flight trajectory and identifies any period(s) where the aircraft is moving
        below a reasonable speed.

        This is evaluated both for instantaneous discrete steps in the trajectory
        (between consecutive waypoints),
        and,
        on a rolling average basis.

        For instantaneous speed, we clip the trajectory by 10 rows on the head and tail.
        (assuming the trajectory is resampled prior to applying the validation handler,
        that is 10min on head or tail).
        """

        violations: list[FlightTooSlowError] = []

        below_inst_thresh = self._df.iloc[10:, :].iloc[:-10, :][
            self._df["ground_speed_m_s"]
            <= self.INSTANTANEOUS_LOW_GROUND_SPEED_THRESHOLD_MPS
        ]
        if len(below_inst_thresh) > 0:
            violations.append(
                FlightTooSlowError(
                    f"found {len(below_inst_thresh)} instances where speed between waypoints is "
                    f"below threshold of {self.INSTANTANEOUS_LOW_GROUND_SPEED_THRESHOLD_MPS} m/s. "
                    f" max value: {max(below_inst_thresh['ground_speed_m_s'])}, "
                    f"min value: {min(below_inst_thresh['ground_speed_m_s'])},"
                )
            )

        roll_speed = self._df[["timestamp", "ground_speed_m_s"]]
        roll_speed.set_index("timestamp", inplace=True)
        roll_speed = roll_speed.rolling(
            pd.Timedelta(minutes=self.AVG_LOW_GROUND_SPEED_ROLLING_WINDOW_PERIOD_MIN)
        ).mean()
        # only consider averages occurring at least rolling_avg_period_min minutes
        # after the flight origination (rolling window if backward looking)
        roll_speed = roll_speed[
            roll_speed.index
            > roll_speed.index[0]
            + pd.Timedelta(minutes=self.AVG_LOW_GROUND_SPEED_ROLLING_WINDOW_PERIOD_MIN)
        ]

        below_avg_thresh = roll_speed[
            roll_speed["ground_speed_m_s"] <= self.AVG_LOW_GROUND_SPEED_THRESHOLD_MPS
        ]
        if len(below_avg_thresh) > 0:
            violations.append(
                FlightTooSlowError(
                    f"found {len(below_avg_thresh)} instances where rolling average speed is "
                    f"below threshold of {self.AVG_LOW_GROUND_SPEED_THRESHOLD_MPS} m/s "
                    f"(rolling window of {self.AVG_LOW_GROUND_SPEED_ROLLING_WINDOW_PERIOD_MIN} minutes). "
                    f" max value: {max(below_avg_thresh['ground_speed_m_s'])}, "
                    f"min value: {min(below_avg_thresh['ground_speed_m_s'])},"
                )
            )

        if len(violations) > 0:
            return violations

    def _is_too_fast(self) -> None | FlightTooFastError:
        """
        Evaluates the flight trajectory and identifies any period(s) where the aircraft is moving
        above a reasonable speed.

        This is evaluated on instantaneous discrete steps between consecutive waypoints.
        """
        above_inst_thresh = self._df[
            self._df["ground_speed_m_s"]
            >= self.INSTANTANEOUS_HIGH_GROUND_SPEED_THRESHOLD_MPS
        ]
        if len(above_inst_thresh) > 0:
            return FlightTooFastError(
                f"found {len(above_inst_thresh)} instances where speed between waypoints is "
                f"above threshold of {self.INSTANTANEOUS_HIGH_GROUND_SPEED_THRESHOLD_MPS} m/s"
                f" max value: {max(above_inst_thresh['ground_speed_m_s'])}, "
                f"min value: {min(above_inst_thresh['ground_speed_m_s'])},"
            )

    def _is_expected_altitude_profile(
        self,
    ) -> None | list[FlightAltitudeProfileError | RocdError]:
        """
        Evaluates flight altitude profile.

        Failure modes include:
        RocdError
        1) flight climbs above alt threshold,
            then descends below that threshold one or more times,
            before making final descent to land.

        FlightAltitudeProfileError
        2) rate of instantaneous (between consecutive waypoint) climb or descent is above threshold,
           while aircraft is above the cruise altitude.
        """

        violations: list[FlightAltitudeProfileError | RocdError] = []

        # only evaluate rocd errors when at cruising altitude
        rocd_above_thres = self._df[
            (self._df["rocd_fps"].abs() >= self.CRUISE_ROCD_THRESHOLD_FPS)
            & (self._df["altitude_baro"] > self.CRUISE_LOW_ALTITUDE_THRESHOLD_FT)
        ]
        if len(rocd_above_thres) > 0:
            violations.append(
                RocdError(
                    f"flight trajectory has rate of climb/descent values "
                    "between consecutive waypoints that exceed threshold "
                    f"of {self.CRUISE_ROCD_THRESHOLD_FPS} ft/sec. "
                    f"Max value found: {np.nanmax(self._df['rocd_fps'].abs())}"
                )
            )

        alt_below_thresh = (
            self._df["altitude_baro"] <= self.CRUISE_LOW_ALTITUDE_THRESHOLD_FT
        )
        alt_thresh_transitions = alt_below_thresh.rolling(window=2).sum()
        transition_pts = alt_thresh_transitions[alt_thresh_transitions == 1]
        if len(transition_pts) > 2:
            violations.append(
                FlightAltitudeProfileError(
                    f"flight trajectory dropped below altitude threshold"
                    f"of {self.CRUISE_LOW_ALTITUDE_THRESHOLD_FT}ft while in-flight."
                )
            )

        if len(violations) > 0:
            return violations

    @property
    def validation_df(self) -> pd.DataFrame:
        """
        Returns
        ---------
        dataframe mirroring that provided to the handler,
        but including the additional computed columns that are used in verification.
        e.g. elapsed_sec, ground_speed_m_s, etc.
        """
        violations = self.evaluate()
        fatal_violations = [
            SchemaError,
            FlightDuplicateTimestamps,
            FlightInvariantFieldViolation,
        ]
        if any([v in violations for v in fatal_violations]):
            raise Exception(
                f"validation dataframe cannot be returned "
                f"if flight has violations(s): {violations}"
            )
        # safeguard to ensure this call follows the addition of the columns
        # assumes calculate_additional_fields is idempotent
        self._calculate_additional_fields()
        return self._df

    def evaluate(self) -> None | list[Exception]:
        """
        Evaluate the flight trajectory for one or more violations.
        """

        all_violations: list[Exception] = []

        # Checks; Round 1
        schema_check: None | SchemaError
        schema_check = self._is_valid_schema(self._df)
        all_violations.append(schema_check) if schema_check else None
        if len(all_violations) > 0:
            return all_violations

        # Checks; Round 2
        timestamp_ordering_check: None | OrderingError
        timestamp_ordering_check = self._is_timestamp_sorted()
        (
            all_violations.append(timestamp_ordering_check)
            if timestamp_ordering_check
            else None
        )

        invariant_fields_check: None | FlightInvariantFieldViolation
        invariant_fields_check = self._is_valid_invariant_fields()
        (
            all_violations.append(invariant_fields_check)
            if invariant_fields_check
            else None
        )

        duplicate_timestamps_check: None | FlightDuplicateTimestamps
        duplicate_timestamps_check = self._is_valid_duplicate_timestamps()
        (
            all_violations.append(duplicate_timestamps_check)
            if duplicate_timestamps_check
            else None
        )
        # we escape here if there are violations for the above checks.
        # we do this because some of the following checks assume no invariant field violations,
        #   or timestamp dupes
        if len(all_violations) > 0:
            return all_violations

        # Checks; Round 3
        self._calculate_additional_fields()

        flight_length_check: None | FlightTooShortError | FlightTooLongError
        flight_length_check = self._is_valid_flight_length()
        all_violations.append(flight_length_check) if flight_length_check else None

        origin_airport_check: None | OriginAirportError
        origin_airport_check = self._is_from_origin_airport()
        all_violations.append(origin_airport_check) if origin_airport_check else None

        destination_airport_check: None | DestinationAirportError
        destination_airport_check = self._is_to_destination_airport()
        (
            all_violations.append(destination_airport_check)
            if destination_airport_check
            else None
        )

        slow_speed_check: None | list[FlightTooSlowError]
        slow_speed_check = self._is_too_slow()
        all_violations.extend(slow_speed_check) if slow_speed_check else None

        fast_speed_check: None | FlightTooFastError
        fast_speed_check = self._is_too_fast()
        all_violations.append(fast_speed_check) if fast_speed_check else None

        altitude_profile_check: None | list[FlightAltitudeProfileError | RocdError]
        altitude_profile_check = self._is_expected_altitude_profile()
        (
            all_violations.extend(altitude_profile_check)
            if altitude_profile_check
            else None
        )

        if len(all_violations) > 0:
            return all_violations


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

        if df_records["time"].duplicated().sum():
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

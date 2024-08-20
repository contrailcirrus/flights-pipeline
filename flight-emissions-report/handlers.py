import concurrent.futures
import os
from dataclasses import dataclass
import math

from google.cloud import bigquery, pubsub_v1
import google.auth
import google.api_core.exceptions
import pandas as pd
import warnings
from typing import Any, Callable, List
import numpy as np

from pycontrails import Flight
from pycontrails.physics import geo
from pycontrails.core import airports

from exceptions import (
    FlightInvariantFieldViolation,
    FlightDuplicateTimestamps,
    FlightTooLongError,
    FlightTooShortError,
)
from helpers import key_max_value_count
from schemas import SpireWaypointPositional
from log import logger, format_traceback

warnings.filterwarnings("ignore", module="google.auth")


class PubSubSubscriptionHandler:
    """
    Handler for managing consumption and marshalling of jobs from a pubsub subscription queue.
    """

    def __init__(
        self,
        subscription: str,
        pull_timeout_sec: float = 60.0,
    ):
        """
        Parameters
        ----------
        subscription
            The fully-qualified URI for the pubsub subscription.
            e.g. 'projects/contrails-301217/subscriptions/api-preprocessor-sub-dev'

        pull_timeout_sec
            Seconds the subscriber client will block for messages before retrying.
        """
        self.subscription = subscription
        self.pull_timeout_sec = pull_timeout_sec

        self._client = pubsub_v1.SubscriberClient()

    @dataclass(frozen=True)
    class Message:
        data: bytes
        ack_id: str
        ordering_key: str

    def fetch(self, count: int = 1) -> List[Message]:
        """Fetch a message from the subscription queue.

        This method will hang and wait until a message is available. If an exception is
        raised, it will retry indefinitely.

        Parameters
        -------
        count
            The max number of message to grab in the fetch

        Returns
        -------
        List[Message]
            The dequeued messages from the pubsub subscription.
        """

        resp = self._client.pull(
            request={"subscription": self.subscription, "max_messages": count},
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
        messages = []
        for itm in resp.received_messages:
            message = self.Message(
                data=itm.message.data,
                ack_id=itm.ack_id,
                ordering_key=itm.message.ordering_key,
            )
            messages.append(message)
        return messages

    def ack(self, message: Message):
        """Acknowledge the message to remove from the queue."""
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


class PubSubPublishHandler:
    def __init__(self, topic_id: str, ordered_queue: bool) -> None:
        self._topic_id = topic_id

        self._publisher = pubsub_v1.PublisherClient(
            # Batch settings increase payload size to execute fewer, larger requests.
            # See: https://cloud.google.com/pubsub/docs/batch-messaging
            batch_settings=pubsub_v1.types.BatchSettings(
                max_messages=1000,
                max_bytes=20 * 1000 * 1000,  # 20 MB max server-side request size
                max_latency=1,  # default: 10 ms = 0.01
            ),
            publisher_options=pubsub_v1.types.PublisherOptions(
                enable_message_ordering=ordered_queue,
                # Flow control applies rate limits by blocking any time the staged data
                # exceeds the following settings. Once the records are received by GCP
                # PubSub, additional publish calls are unblocked.
                # See: https://cloud.google.com/pubsub/docs/flow-control-messages
                flow_control=pubsub_v1.types.PublishFlowControl(
                    message_limit=10,
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
        ordering_key
            if publishing to an ordered queue, this is the ordering key
        log_context
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

    def __init__(self, trajectory: pd.DataFrame):
        """
        Parameters
        ----------
        trajectory
            A dataset with one flight trajectories.
            Each trajectory is identified by its flight_id.
            Dataset must include columns matching those in the BQ table `spire_flights_raw_prod`
        """
        if len(trajectory) == 0:
            raise Exception("flight trajectory is empty.")
        if len(trajectory["flight_id"].unique()) > 1:
            raise Exception(
                "dataset passed to handler must be for a single flight instance ("
                "flight_id)."
            )
        self._df = trajectory.copy(deep=True)

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

    def heal(self) -> pd.DataFrame:
        """
        Manipulate trajectories with qaqc heuristics.

        Returns
        -------
        Dataset mirroring initiated dataset, with manipulations applied.
        """

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
        print(
            f"flight_id: {self._df.flight_id.iloc[0]}, priority_values: {priority_values}"
        )
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

    def __init__(
        self,
        records_window: list[SpireWaypointPositional],
    ):
        """
        Parameters
        ----------
        records_window
            a series of waypoints, belonging to a time window,
            delivered from a windowed batch stream (temporally contiguous) -- present records
        """
        self._waypoints_df_resampled: pd.DataFrame | None = None

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


class TrajectoryValidationHandler:
    """
    Evaluates trajectory and identifies if it violates any verification rules.
    """

    MIN_WAYPOINTS_PER_FLIGHT = 30
    MIN_ELAPSED_SEC_PER_FLIGHT = 60 * 20

    airports_db = airports.global_airport_database()

    def __init__(self, trajectory: pd.DataFrame):
        """
        Parameters
        -------------
        trajectory
            A dataframe representing a single flight trajectory.
            Must have the same columns as in our spire raw data (see BQ table spire_flights_raw_prod).
        """
        if len(trajectory) == 0:
            raise Exception("flight trajectory is empty.")
        if len(trajectory["flight_id"].unique()) > 1:
            raise Exception(
                "dataset passed to handler must be for a single flight instance ("
                "flight_id)."
            )

        self._df = trajectory.copy(deep=True)
        self._df.sort_values(by="timestamp", ascending=True, inplace=True)
        self._df.reset_index(drop=True, inplace=True)

    @property
    def validation_df(self) -> pd.DataFrame:
        """
        Returns
        ---------
        dataframe mirroring that provided to the handler,
        but including the additional computed columns that are used in verification.
        e.g. elapsed_sec, speed_m_s, etc.
        """
        # safeguard to ensure this call follows the addition of the columns
        # assumes calculate_additional_fields is idempotent
        self._calculate_additional_fields()
        return self._df

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
    def _calc_distance(lat_0, lon_0, alt_ft_0, lat_f, lon_f, alt_ft_f) -> float:
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

        dist_m = cls._calc_distance(lat_0, lon_0, alt_0, lat_f, lon_f, alt_f)
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

        return cls._calc_distance(
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

        return cls._calc_distance(
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
                self.rolling_time_delta_seconds(window)
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
            speed_m_s=self._df["elapsed_distance_m"]
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

    def _is_valid_invariant_fields(self) -> None | FlightInvariantFieldViolation:
        """
        Verify that fields expected to be invariant are indeed invariant.
        """

    def _is_valid_duplicate_timestamps(self) -> None | FlightDuplicateTimestamps:
        """
        Verifies that we do not have duplicate timestamps in the trajectory.
        """
        return

    def _is_valid_flight_length(
        self,
    ) -> None | FlightTooShortError | FlightTooLongError:
        """
        Verifies that the flight is of a reasonable length.
        """
        # min_length_hours = 0.4
        # max_length_hours = 19
        return

    def evaluate(self):
        """
        Evaluate the flight trajectory for one or more violations.
        """

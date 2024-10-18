from lib.helpers import key_max_value_count
from lib.schemas import (
    TrajectoryWorkerJobDescriptor,
    FlightInfoWide,
    SpireWaypointPositional,
    WaypointsRecord,
    MetSource,
)
from lib.handlers import (
    PubSubPublishHandler,
    BigQueryHandler,
    HealTrajectoryHandler,
    ResampleHandler,
)
from lib.exceptions import (
    PermanentFailureException,
    InvalidQueryException,
    BadTrajectoryException,
)

from google.cloud import bigquery
import pandas as pd

from lib.log import logger


class TrajectoryBuilderSvc:
    """
    Service wrapper for building and submitting trajectory worker jobs (`WaypointsRecord`)
    to the trajectory worker job queue.
    """

    DAILY_FLIGHTS_QUERY_FILENAME = "sql/bq_waypoints_flights_daily_by_airline.sql"
    FLIGHT_ID_QUERY_FILENAME = "sql/bq_waypoints_flights_daily_by_flight_id.sql"
    ICAO_ADDRESS_QUERY_FILENAME = "sql/bq_waypoints_flights_daily_by_icao_address.sql"
    # ordering key for traj worker jobs that should only export per-flight summary
    ORDERING_KEY_TEMPLATE = "flightsreport:{}"
    # ordering key for traj worker jobs that should export per-flight & per-segment summaries
    ORDERING_KEY_FULL_TRAJ_TEMPLATE = "flightsreport_full:{}"

    def __init__(
        self,
        bq_handler: BigQueryHandler,
        heal_traj_handler: HealTrajectoryHandler,
        resample_handler: ResampleHandler,
        job_out_handler: PubSubPublishHandler,
    ):
        self._bq_handler = bq_handler
        self._traj_heal_handler = heal_traj_handler
        self._resample_handler = resample_handler
        self._job_out_handler = job_out_handler

    def _fetch_airline_day(
        self, day: str, airline_iata: str
    ) -> (pd.DataFrame, pd.DataFrame):
        """
        Fetch and clean a days flights (flights starting on calendar day) from BigQuery.

        Parameters
        ----------
        day
            The target UTC day (flight instance origination) for flights; fmt "%Y-%m-%d"
        airline_iata
            The target airline for which to fetch all flight instances

        Returns
        ---------
        pd.DataFrame
            target terrestrial ads-b data for flights
        pd.DataFrame
            target superset of satellite ads-b data for flights
        """
        td = pd.Timestamp.now(tz="UTC") - pd.Timestamp(day, tz="UTC")
        if td < pd.Timedelta(days=1):
            raise InvalidQueryException("flight day must be at least 1 day in the past")

        previous_day = (pd.Timestamp(day) - pd.Timedelta(days=1)).strftime("%Y-%m-%d")
        next_day = (pd.Timestamp(day) + pd.Timedelta(days=1)).strftime("%Y-%m-%d")

        query = self._bq_handler.import_query(self.DAILY_FLIGHTS_QUERY_FILENAME)
        cfg = bigquery.QueryJobConfig(
            query_parameters=[
                bigquery.ScalarQueryParameter("airline", "STRING", airline_iata),
                bigquery.ScalarQueryParameter("target_day", "STRING", day),
                bigquery.ScalarQueryParameter(
                    "target_day_before", "STRING", previous_day
                ),
                bigquery.ScalarQueryParameter("target_day_after", "STRING", next_day),
            ]
        )
        df: pd.DataFrame = self._bq_handler.query(query, cfg)
        df.drop_duplicates(inplace=True)

        # segregate sat data (i.e. terr_waypoints with missing flight_id
        df_satellite = df[df["flight_id"].isnull()]
        df = df[~df["flight_id"].isnull()]
        logger.info(
            f"received {len(df)} terrestrial & {len(df_satellite)} satellite from BigQuery. "
            f"Flight count: {len(df['flight_id'].unique())}"
        )
        return df, df_satellite

    def _fetch_flight_id_day(
        self, day: str, flight_id: str
    ) -> (pd.DataFrame, pd.DataFrame):
        """
        Fetch and clean a days flights (flights starting on calendar day) from BigQuery.

        Parameters
        ----------
        day
            The target UTC day on which the flight instance originates; fmt "%Y-%m-%d"
        flight_id
            The target flight instance's flight_id

        Returns
        ---------
        pd.DataFrame
            target terrestrial ads-b data for flights
        pd.DataFrame
            target superset of satellite ads-b data for flights
        """

        td = pd.Timestamp.now(tz="UTC") - pd.Timestamp(day, tz="UTC")
        if td < pd.Timedelta(days=1):
            raise InvalidQueryException("flight day must be at least 1 day in the past")
        next_day = (pd.Timestamp(self.day) + pd.Timedelta(days=1)).strftime("%Y-%m-%d")

        query = self._bq_handler.import_query(self.FLIGHT_ID_QUERY_FILENAME)
        cfg = bigquery.QueryJobConfig(
            query_parameters=[
                bigquery.ScalarQueryParameter("target_day", "STRING", day),
                bigquery.ScalarQueryParameter("target_day_after", "STRING", next_day),
                bigquery.ScalarQueryParameter("flight_id", "STRING", flight_id),
            ]
        )
        df: pd.DataFrame = self._bq_handler.query(query, cfg)
        df.drop_duplicates(inplace=True)

        # segregate sat data (i.e. terr_waypoints with missing flight_id)
        df_satellite = df[df["flight_id"].isnull()]
        df = df[~df["flight_id"].isnull()]
        logger.info(
            f"received {len(df)} terrestrial & {len(df_satellite)} satellite from BigQuery. "
            f"Flight count: {len(df['flight_id'].unique())}"
        )
        return df, df_satellite

    def _fetch_icao_address_day(
        self, day: str, icao_address: str
    ) -> (pd.DataFrame, pd.DataFrame):
        """
        Fetch ads-b data for all flights originating on a single day, belonging to a single
        icao address.

        Parameters
        ----------
        day
            The target UTC day (flight instance origination) for flights; fmt "%Y-%m-%d"
        icao_address
            The target icao_address for which to fetch all flight instances

        Returns
        ---------
        pd.DataFrame
            target terrestrial ads-b data for flights
        pd.DataFrame
            target superset of satellite ads-b data for flights
        """
        td = pd.Timestamp.now(tz="UTC") - pd.Timestamp(day, tz="UTC")
        if td < pd.Timedelta(days=1):
            raise InvalidQueryException("flight day must be at least 1 day in the past")

        previous_day = (pd.Timestamp(day) - pd.Timedelta(days=1)).strftime("%Y-%m-%d")
        next_day = (pd.Timestamp(day) + pd.Timedelta(days=1)).strftime("%Y-%m-%d")

        query = self._bq_handler.import_query(self.ICAO_ADDRESS_QUERY_FILENAME)

        cfg = bigquery.QueryJobConfig(
            query_parameters=[
                bigquery.ScalarQueryParameter("icao_address", "STRING", icao_address),
                bigquery.ScalarQueryParameter("target_day", "STRING", day),
                bigquery.ScalarQueryParameter(
                    "target_day_before", "STRING", previous_day
                ),
                bigquery.ScalarQueryParameter("target_day_after", "STRING", next_day),
            ]
        )
        df: pd.DataFrame = self._bq_handler.query(query, cfg)
        df.drop_duplicates(inplace=True)

        # segregate sat data (i.e. terr_waypoints with missing flight_id
        df_satellite = df[df["flight_id"].isnull()]
        df = df[~df["flight_id"].isnull()]
        logger.info(
            f"received {len(df)} terrestrial & {len(df_satellite)} satellite from BigQuery. "
            f"Flight count: {len(df['flight_id'].unique())}"
        )
        return df, df_satellite

    def run(self, twjd: TrajectoryWorkerJobDescriptor):
        """
        Main service entrypoint.
        - fetch ADS-B waypoints from BQ
        - validate trajector(y/ies)
        - resample trajector(y/ies)
        - package and publish trajectory worker jobs (`WaypointsRecord`) to traj worker job queue
        """

        try:
            twjd.validate()
        except Exception as e:
            raise PermanentFailureException from e

        # ------------------
        # fetch ads-b data from bq
        # ------------------
        try:
            if twjd.airline_iata:
                df, df_satellite = self._fetch_airline_day(
                    day=twjd.day,
                    airline_iata=twjd.airline_iata,
                )
            elif twjd.flight_id:
                df, df_satellite = self._fetch_flight_id_day(
                    day=twjd.day,
                    flight_id=twjd.flight_id,
                )
            elif twjd.icao_address:
                df, df_satellite = self._fetch_icao_address_day(
                    day=twjd.day,
                    icao_address=twjd.icao_address,
                )
            else:
                raise NotImplementedError("TJWD could not be processed.")
        except InvalidQueryException as e:
            raise PermanentFailureException("ads-b request to bq not valid.") from e
        except Exception as e:
            raise Exception("failed to fetch ads-b data from bq.") from e

        # -----------
        # resample trajectories,
        # compose trajectory-worker jobs, on each flight instance,
        # and submit jobs to worker queue
        # -----------
        flight_instances = df.groupby("flight_id")
        for flight_id, terr_waypoints in flight_instances:
            # --------------
            # merge sat data into terrestrial data
            # --------------
            first_terr_ts = min(terr_waypoints["timestamp"])
            last_terr_ts = max(terr_waypoints["timestamp"])

            aircraft_sel = df_satellite["icao_address"] == (
                key_max_value_count(terr_waypoints, "icao_address")
            )
            flight_tmrg_sel = (df_satellite["timestamp"] > first_terr_ts) & (
                df_satellite["timestamp"] < last_terr_ts
            )

            sat_waypoints = df_satellite[aircraft_sel & flight_tmrg_sel]

            waypoints = pd.concat([terr_waypoints, sat_waypoints])
            # fill null flight_ids (sat data does not have flight_id)
            waypoints.fillna(value={"flight_id": flight_id}, inplace=True)

            # -------------
            # apply qa/qc updates
            # -------------
            # TODO: wire in validation handler in addition to heal handler
            try:
                self._traj_heal_handler.set(waypoints)
                waypoints = self._traj_heal_handler.heal()
                self._traj_heal_handler.unset()
            except BadTrajectoryException as e:
                logger.error(
                    f"failed to process flight_id: {flight_id} in healing step: {e}"
                )
                continue

            # --------------
            # build jobs
            # --------------
            try:
                if not pd.isnull(waypoints["departure_scheduled_time"][0]):
                    departure_scheduled_time = waypoints["departure_scheduled_time"][
                        0
                    ].strftime("%Y-%m-%dT%H:%M:%SZ")
                else:
                    departure_scheduled_time = None
                if not pd.isnull(waypoints["arrival_scheduled_time"][0]):
                    arrival_scheduled_time = waypoints["arrival_scheduled_time"][
                        0
                    ].strftime("%Y-%m-%dT%H:%M:%SZ")
                else:
                    arrival_scheduled_time = None

                flight_info = FlightInfoWide(
                    engine_uid=None,
                    icao_address=waypoints["icao_address"][0],
                    flight_id=waypoints["flight_id"][0],
                    callsign=waypoints["callsign"][0],
                    tail_number=waypoints["tail_number"][0],
                    flight_number=waypoints["flight_number"][0],
                    aircraft_type_icao=waypoints["aircraft_type_icao"][0],
                    airline_iata=waypoints["airline_iata"][0],
                    departure_airport_icao=waypoints["departure_airport_icao"][0],
                    departure_scheduled_time=departure_scheduled_time,
                    arrival_airport_icao=waypoints["arrival_airport_icao"][0],
                    arrival_scheduled_time=arrival_scheduled_time,
                )
                records = []
                for ix, ln in waypoints.iterrows():
                    record = SpireWaypointPositional(
                        ingestion_time=ln["ingestion_time"].strftime(
                            "%Y-%m-%dT%H:%M:%SZ"
                        ),
                        timestamp=ln["timestamp"].strftime("%Y-%m-%dT%H:%M:%SZ"),
                        latitude=ln["latitude"],
                        longitude=ln["longitude"],
                        collection_type=ln["collection_type"],
                        imputed=False,
                        altitude_baro=int(ln["altitude_baro"]),
                    )
                    records.append(record)

                # -------------
                # resample records
                # -------------
                self._resample_handler.set(records)
                self._resample_handler.interpolate()

                waypoints_resampled: list[
                    SpireWaypointPositional
                ] = self._resample_handler.waypoints_resampled
                self._resample_handler.unset()
            except Exception as e:
                logger.error(
                    f"failed to resample flight instance: {flight_id}. error: {e}"
                )
                continue

            # ---------------
            # build and submit job
            # ---------------
            try:
                job = WaypointsRecord(
                    flight_info=flight_info,
                    records=waypoints_resampled,
                    met_source=MetSource(twjd.met_source),
                    export_cocip_trajectory=twjd.full_traj,
                )
                if twjd.full_traj:
                    ordering_key = self.ORDERING_KEY_FULL_TRAJ_TEMPLATE.format(
                        job.flight_info.flight_id
                    )
                else:
                    ordering_key = self.ORDERING_KEY_TEMPLATE.format(
                        job.flight_info.flight_id
                    )
                self._job_out_handler.publish_async(
                    job.as_utf8_json(),
                    timeout_seconds=45,
                    ordering_key=ordering_key,
                )
            except Exception as e:
                logger.error(
                    f"failed to build and submit job for flight instance: {flight_id}. "
                    f"error: {e}"
                )

        self._job_out_handler.wait_for_publish(timeout_seconds=300)

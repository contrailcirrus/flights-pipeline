import os

import dataclasses
import sys

from lib.helpers import key_max_value_count
from lib.schemas import (
    TrajectoryWorkerJobDescriptor,
    FlightInfoWide,
    SpireWaypointPositional,
    TrajectoryCandidateInfo,
    WaypointsRecord,
    MetSource,
    AirlineDayFlightsProgressMarker,
    TelemetrySource,
)
from lib.handlers import (
    PubSubPublishHandler,
    BigQueryHandler,
    HealTrajectoryHandler,
    ResampleHandler,
    RedisHandler,
    CloudStorageHandler,
)
from lib.exceptions import (
    PermanentFailureException,
    InvalidQueryException,
    BadTrajectoryException,
)
from pycontrails.datalib.spire import ValidateTrajectoryHandler
from pycontrails.datalib.spire.exceptions import ROCDError
from lib.utils import sigterm_manager

from google.cloud import bigquery
import pandas as pd

from lib.log import logger, format_traceback


class TrajectoryBuilderSvc:
    """
    Service wrapper for building and submitting trajectory worker jobs (`WaypointsRecord`)
    to the trajectory worker job queue.
    """

    DAILY_FLIGHTS_QUERY_FILENAME = "lib/sql/bq_waypoints_flights_daily_by_airline.sql"
    FLIGHT_ID_QUERY_FILENAME = "lib/sql/bq_waypoints_flights_daily_by_flight_id.sql"
    ICAO_ADDRESS_QUERY_FILENAME = (
        "lib/sql/bq_waypoints_flights_daily_by_icao_address.sql"
    )
    FLIGHT_INSTANCE_PROGRESS_COUNT_INCREMENT = 500
    DATE_STRING_FORMAT = "%Y-%m-%dT%H:%M:%SZ"

    def __init__(
        self,
        cache_handler: RedisHandler | None,
        bq_handler: BigQueryHandler,
        gcs_handler: CloudStorageHandler,
        heal_traj_handler: HealTrajectoryHandler,
        validate_traj_handler: ValidateTrajectoryHandler,
        resample_handler: ResampleHandler,
        job_out_handler: PubSubPublishHandler,
    ):
        self._cache_handler = cache_handler
        self._bq_handler = bq_handler
        self._gcs_handler = gcs_handler
        self._traj_heal_handler = heal_traj_handler
        self._validate_traj_handler = validate_traj_handler
        self._resample_handler = resample_handler
        self._job_out_handler = job_out_handler

    def _fetch_airline_day(
        self,
        day: str,
        airline_iata: str,
        telemetry_src: TelemetrySource,
    ) -> (pd.DataFrame, pd.DataFrame):
        """
        Fetch and clean a days flights (flights starting on calendar day) from BigQuery or GCS.

        Parameters
        ----------
        day
            The target UTC day (flight instance origination) for flights; fmt "%Y-%m-%d"
        airline_iata
            The target airline for which to fetch all flight instances
        telemetry_src
            Specifies the source from which to fetch ads-b data

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

        match telemetry_src:
            case TelemetrySource.BIG_QUERY:
                logger.debug("Fetching ADS-B from BigQuery.")
                query = self._bq_handler.import_query(self.DAILY_FLIGHTS_QUERY_FILENAME)
                cfg = bigquery.QueryJobConfig(
                    query_parameters=[
                        bigquery.ScalarQueryParameter(
                            "airline", "STRING", airline_iata
                        ),
                        bigquery.ScalarQueryParameter("target_day", "STRING", day),
                        bigquery.ScalarQueryParameter(
                            "target_day_before", "STRING", previous_day
                        ),
                        bigquery.ScalarQueryParameter(
                            "target_day_after", "STRING", next_day
                        ),
                    ]
                )
                df: pd.DataFrame = self._bq_handler.query(query, cfg)
                df.drop_duplicates(inplace=True)
                # segregate sat data (i.e. terr_waypoints with missing flight_id
                df_satellite = df[df["flight_id"].isnull()]
                df = df[~df["flight_id"].isnull()]

            case TelemetrySource.GOOGLE_CLOUD_STORAGE:
                logger.debug("Fetching ADS-B from Google Cloud Storage.")
                df_all = self._gcs_handler.fetch_airline_days(
                    [previous_day, day, next_day], airline_iata, prune=True
                )
                # the following logic emulates the logic in the SQL query dispatched to BQ
                df_all["timestamp"] = pd.to_datetime(df_all["timestamp"])
                df_all.sort_values("timestamp", inplace=True, ascending=True)
                first_by_fid = df_all.groupby("flight_id").first()
                is_on_day = (first_by_fid["timestamp"] >= pd.to_datetime(day)) & (
                    first_by_fid["timestamp"] < pd.to_datetime(next_day)
                )
                first_by_fid = first_by_fid[is_on_day]

                is_fid = df_all["flight_id"].isin(first_by_fid.index)
                df = df_all[is_fid]

                is_icao_w_null_fid = (
                    df_all["icao_address"].isin(first_by_fid["icao_address"])
                    & df_all["flight_id"].isna()
                )
                df_satellite = df_all[is_icao_w_null_fid]

                # localize timestamp, as per expectations of downstream handlers/services
                df["timestamp"] = df["timestamp"].dt.tz_localize("UTC")
                df_satellite["timestamp"] = df_satellite["timestamp"].dt.tz_localize(
                    "UTC"
                )

                df["departure_scheduled_time"] = df[
                    "departure_scheduled_time"
                ].dt.tz_localize("UTC")
                df_satellite["departure_scheduled_time"] = df_satellite[
                    "departure_scheduled_time"
                ].dt.tz_localize("UTC")

                df["arrival_scheduled_time"] = df[
                    "arrival_scheduled_time"
                ].dt.tz_localize("UTC")
                df_satellite["arrival_scheduled_time"] = df_satellite[
                    "arrival_scheduled_time"
                ].dt.tz_localize("UTC")

            case _:
                raise NotImplementedError(
                    f"Specified telemetry source ({telemetry_src.value}) is not yet implemented for airline_iata based TWJDs."
                )
        return df, df_satellite

    def _fetch_flight_id_day(
        self,
        day: str,
        flight_id: str,
        telemetry_src: TelemetrySource,
    ) -> (pd.DataFrame, pd.DataFrame):
        """
        Fetch and clean a days flights (flights starting on calendar day) from BigQuery.

        Parameters
        ----------
        day
            The target UTC day on which the flight instance originates; fmt "%Y-%m-%d"
        flight_id
            The target flight instance's flight_id
        telemetry_src
            Specifies the source from which to fetch ads-b data

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

        if telemetry_src != TelemetrySource.BIG_QUERY:
            raise NotImplementedError(
                f"Specified telemetry source ({telemetry_src.value}) is not yet implemented for flight_id based TWJDs."
            )

        next_day = (pd.Timestamp(day) + pd.Timedelta(days=1)).strftime("%Y-%m-%d")

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
        return df, df_satellite

    def _fetch_icao_address_day(
        self,
        day: str,
        icao_address: str,
        telemetry_src: TelemetrySource,
    ) -> (pd.DataFrame, pd.DataFrame):
        """
        Fetch ads-b data for all flights originating on a single day, belonging to one or more
        icao address.


        Parameters
        ----------
        day
            The target UTC day (flight instance origination) for flights; fmt "%Y-%m-%d"
        icao_address
            The target icao_address for which to fetch all flight instances.
            If a single aircraft, then a single icao_address.
            If multiple aircraft, then a comma delimited string of icao_address values.
        telemetry_src
            Specifies the source from which to fetch ads-b data

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

        if telemetry_src != TelemetrySource.BIG_QUERY:
            raise NotImplementedError(
                f"Specified telemetry source ({telemetry_src.value}) is not yet implemented for icao_address-based TWJDs."
            )

        previous_day = (pd.Timestamp(day) - pd.Timedelta(days=1)).strftime("%Y-%m-%d")
        next_day = (pd.Timestamp(day) + pd.Timedelta(days=1)).strftime("%Y-%m-%d")

        # icao_address can be a single icao address,
        # or a comma delimited string of multiple icao addresses
        icao_address_lst = icao_address.split(",")

        query = self._bq_handler.import_query(self.ICAO_ADDRESS_QUERY_FILENAME)
        cfg = bigquery.QueryJobConfig(
            query_parameters=[
                bigquery.ArrayQueryParameter(
                    "icao_address", "STRING", icao_address_lst
                ),
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
            twjd.verify()
        except Exception as e:
            raise PermanentFailureException from e

        # ------------------
        # fetch ads-b
        # ------------------
        try:
            if twjd.airline_iata:
                df, df_satellite = self._fetch_airline_day(
                    day=twjd.day,
                    airline_iata=twjd.airline_iata,
                    telemetry_src=twjd.telemetry_source,
                )
            elif twjd.flight_id:
                df, df_satellite = self._fetch_flight_id_day(
                    day=twjd.day,
                    flight_id=twjd.flight_id,
                    telemetry_src=twjd.telemetry_source,
                )
            elif twjd.icao_address:
                df, df_satellite = self._fetch_icao_address_day(
                    day=twjd.day,
                    icao_address=twjd.icao_address,
                    telemetry_src=twjd.telemetry_source,
                )
            else:
                raise NotImplementedError(f"TWJD could not be processed {twjd}")
        except InvalidQueryException as e:
            raise PermanentFailureException(
                f"ads-b request to bq not valid for TWJD: {twjd}"
            ) from e
        except Exception as e:
            raise Exception(
                f"failed to fetch ads-b data from data source for TWJD: {twjd}"
            ) from e

        # -----------
        # resample trajectories,
        # compose trajectory-worker jobs, on each flight instance,
        # and submit jobs to worker queue
        # -----------
        logger.info(
            f"airline_iata: {twjd.airline_iata}. "
            f"flight count: {len(df['flight_id'].unique())}. "
            f"waypoints: {len(df)} terrestrial & {len(df_satellite)} satellite."
        )
        flight_instances = df.groupby("flight_id", sort=True)

        # fetch marker, if one exists, from redis cache
        progress_marker = 0
        if self._cache_handler and twjd.airline_iata:
            # we skip cache handling if this is a twjd w/o airline_iata
            # i.e. we don't bother with cache handling for small jobs
            # where the trajectories are for a single icao_address or flight_id
            key = f"{twjd.airline_iata}:{twjd.day}:{twjd.met_source.value}"
            if resp := self._cache_handler.pull(key):
                progress_marker = resp
                logger.warning(
                    f"resuming progress from a previous job "
                    f"at marker {progress_marker}. "
                    f"airline_iata: {twjd.airline_iata}. "
                    f"TWJD: {twjd}"
                )

        counter = 0
        number_of_flight_candidates = len(flight_instances.groups)
        for flight_id, terr_waypoints in flight_instances:
            if sigterm_manager.should_exit:
                sys.exit(0)

            # Keep track of initial trajectory information for logging
            candidate = TrajectoryCandidateInfo(
                flight_id=flight_id,
                airline_iata=terr_waypoints["airline_iata"].iloc[0],
                callsign=terr_waypoints["callsign"].iloc[0],
                flight_number=terr_waypoints["flight_number"].iloc[0],
                length=len(terr_waypoints),
                start_time=terr_waypoints["timestamp"].min(),
                end_time=terr_waypoints["timestamp"].max(),
            )
            candidate.set_datetime_str_fmt(self.DATE_STRING_FORMAT)

            counter += 1

            # fast-forward if we are resuming a job
            if counter <= progress_marker:
                continue

            if (counter % self.FLIGHT_INSTANCE_PROGRESS_COUNT_INCREMENT) == 0:
                logger.info(
                    f"{candidate}: processing {counter}/{number_of_flight_candidates}"
                )
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
            # Apply common fixes to trajectory
            # -------------
            try:
                flight_duration_minutes = (
                    waypoints["timestamp"].max() - waypoints["timestamp"].min()
                ).total_seconds() / 60.0
                self._traj_heal_handler.set(waypoints, candidate_info=candidate)
                waypoints = self._traj_heal_handler.heal()
                # Data are returned sorted by timestamp
                new_flight_duration_minutes = (
                    waypoints["timestamp"].iloc[-1] - waypoints["timestamp"].iloc[0]
                ).total_seconds() / 60.0
                logger.info(
                    f"{candidate}: applied trajectory healing. "
                    f"change in duration (min): {new_flight_duration_minutes - flight_duration_minutes:.2f}"
                )
                self._traj_heal_handler.unset()
            except BadTrajectoryException as _:
                logger.warning(
                    f"{candidate}: Skipping. failed to process in healing step: {format_traceback()}"
                )
                continue
            except Exception as _:
                logger.error(
                    f"{candidate}: Skipping. failed to process in healing step: {format_traceback()}"
                )
                continue

            # --------------
            # build jobs
            # --------------
            try:
                if not pd.isnull(waypoints["departure_scheduled_time"][0]):
                    departure_scheduled_time = waypoints["departure_scheduled_time"][
                        0
                    ].strftime(self.DATE_STRING_FORMAT)
                else:
                    departure_scheduled_time = None
                if not pd.isnull(waypoints["arrival_scheduled_time"][0]):
                    arrival_scheduled_time = waypoints["arrival_scheduled_time"][
                        0
                    ].strftime(self.DATE_STRING_FORMAT)
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
                        ingestion_time=None,
                        timestamp=ln["timestamp"].strftime(self.DATE_STRING_FORMAT),
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
                    f"{candidate}: Skipping. failed to resample flight instance. error: {e}"
                )
                continue

            resampled_df = pd.DataFrame(
                [
                    {
                        **dataclasses.asdict(flight_info),
                        **dataclasses.asdict(pos),
                    }
                    for pos in waypoints_resampled
                ]
            )
            logger.info(f"{candidate}: resampled to {len(resampled_df)} points.")

            if twjd.export_waypoints:
                # save waypoints to disk
                # CLI (local) use only
                logger.info(f"{candidate}: writing waypoints to file")
                base_path = f"out/{flight_info.airline_iata}"
                os.makedirs(base_path, exist_ok=True)
                resampled_df.to_csv(
                    f"{base_path}/{flight_info.flight_id}.csv",
                    index=False,
                )

            # reconstructing the resampled df from the SpireWaypointPositional list
            # does not preserve expected datatypes for datetime-like fields
            # (which are string literals in our SpireWaypointPositional objs)
            # thus, we re-apply the HealTrajectoryHandler to re-cast data-types
            # prior to running the ValidateTrajectoryHandler
            try:
                # resampled_df is guaranteed time-sorted
                flight_duration_minutes = (
                    resampled_df["timestamp"].iloc[-1]
                    - resampled_df["timestamp"].iloc[0]
                ).total_seconds() / 60.0
                self._traj_heal_handler.set(resampled_df, candidate_info=candidate)
                resampled_df = self._traj_heal_handler.heal()
                # healed trajectory also time-sorted
                new_flight_duration_minutes = (
                    resampled_df["timestamp"].iloc[-1]
                    - resampled_df["timestamp"].iloc[0]
                ).total_seconds() / 60.0
                logger.info(
                    f"{candidate}: re-applied trajectory healing post resampling. "
                    f"change in duration (min): {new_flight_duration_minutes - flight_duration_minutes:.2f}"
                )
                self._traj_heal_handler.unset()
            except BadTrajectoryException as e:
                logger.warning(
                    f"{candidate}: Skipping. bad trajectory post resampling. error: {e}"
                )
                continue
            except Exception as e:
                logger.error(
                    f"{candidate}: Skipping. failed to run heal handler post resampling. error: {e}"
                )
                continue

            # ---------------
            # confirm that trajectory meets acceptance criteria
            # ---------------
            permitted_violation_types = [
                ROCDError,
            ]
            try:
                self._validate_traj_handler.set(resampled_df)
                violations: None | list[
                    Exception
                ] = self._validate_traj_handler.evaluate()
                self._validate_traj_handler.unset()

                # log instances of accepted violations
                accepted_violations = (
                    [v for v in violations if type(v) in permitted_violation_types]
                    if violations
                    else None
                )
                # pop permitted violations
                violations = (
                    [v for v in violations if type(v) not in permitted_violation_types]
                    if violations
                    else None
                )

                if violations and len(violations) > 0:
                    logger.warning(
                        f"{candidate}: Skipping. invalid flight instance. "
                        f" violations: {violations}"
                    )
                    continue

                if accepted_violations and len(accepted_violations) > 0:
                    logger.warning(
                        f"{candidate}: Keeping. acceptable violation(s). "
                        f" violations: {accepted_violations}"
                    )
            except BadTrajectoryException as e:
                logger.warning(
                    f"{candidate}: Skipping. "
                    f"received bad trajectory in trajectory validation handler. "
                    f" {e}"
                )
                continue
            except Exception as e:
                logger.error(
                    f"{candidate}: Skipping. "
                    f"failed to run trajectory validation handler. "
                    f" {e}"
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
                if not twjd.dry_run:
                    self._job_out_handler.publish_async(
                        job.as_utf8_json(),
                        timeout_seconds=45,
                    )
                    self._job_out_handler.wait_for_publish(timeout_seconds=300)
                    if self._cache_handler and twjd.airline_iata:
                        self._cache_handler.push(
                            AirlineDayFlightsProgressMarker(
                                airline_iata=twjd.airline_iata,
                                day=twjd.day,
                                met_source=twjd.met_source.value,
                                marker=counter,
                            )
                        )
            except Exception as e:
                logger.error(
                    f"{candidate}: Skipping. "
                    f"failed to build and submit job for flight instance. "
                    f"error: {e}"
                )

        if self._cache_handler and twjd.airline_iata:
            self._cache_handler.pop(
                f"{twjd.airline_iata}:{twjd.day}:{twjd.met_source.value}"
            )

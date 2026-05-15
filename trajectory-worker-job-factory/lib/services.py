import hashlib
import os

import sys
from pycontrails import Flight

from lib.helpers import key_max_value_count, altitude_ft_to_flight_level
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
    RedisHandler,
    CloudStorageHandler,
)
from lib.exceptions import (
    PermanentFailureException,
    InvalidQueryException,
    SpireCacheTooSmallException,
)
from pycontrails.datalib.spire import ValidateTrajectoryHandler
from pycontrails.datalib.spire.exceptions import ROCDError, UnknownAirportLocationError
from lib.utils import sigterm_manager

from google.cloud import bigquery
import pandas as pd
import numpy as np

from lib.log import logger, format_traceback


class TrajectoryBuilderSvc:
    """
    Service wrapper for building and submitting trajectory worker jobs (`WaypointsRecord`)
    to the trajectory worker job queue.
    """

    DAILY_FLIGHTS_QUERY_FILENAME = "lib/sql/bq_waypoints_flights_daily_by_airline.sql"
    FLIGHT_ID_QUERY_FILENAME = "lib/sql/bq_waypoints_flights_daily_by_flight_id.sql"
    FLIGHT_INSTANCE_PROGRESS_COUNT_INCREMENT = 500
    # minimum number of waypoints in a flight instance with null airline iata
    # presumed a true null airline iata if above this threshold
    MIN_WAYPOINT_COUNT_NULL_AIRLINE_IATA = 30
    MAX_NOMINAL_ALT_GEN_AVIATION_FT = 20000
    TRAJECTORY_SAMPLING_CUTOFF_PERIOD_S = 60  # seconds; used to mark resampled waypoints as imputed if the gap between them and the previous raw waypoint is above this threshold
    AVG_LOW_GROUND_SPEED_THRESHOLD_MPS = 85  # m/s - patching the default value in pycontrails ValidateTrajectoryHandler based on analysis of 2024 flights

    def __init__(
        self,
        cache_handler: RedisHandler | None,
        bq_handler: BigQueryHandler,
        gcs_handler: CloudStorageHandler,
        heal_traj_handler: HealTrajectoryHandler,
        validate_traj_handler: ValidateTrajectoryHandler,
        job_out_handler: PubSubPublishHandler,
    ):
        self._cache_handler = cache_handler
        self._bq_handler = bq_handler
        self._gcs_handler = gcs_handler
        self._traj_heal_handler = heal_traj_handler
        self._validate_traj_handler = validate_traj_handler
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
                logger.debug("fetching adsb from bigquery")
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
                logger.debug("fetching adsb from gcs")
                # df_all comes with:
                # 1) waypoints for flight_ids observed to have the target airline_iata
                # 2) all waypoints with null flight_id (sat data) in target timerange
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
                # flight ids with trajectories originating on the target day
                first_by_fid = first_by_fid[is_on_day]
                target_fids = set(first_by_fid.index)
                # remove None as a possible target flight id
                target_fids.discard(None)
                is_fid = df_all["flight_id"].isin(target_fids)
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
                    f"specified telemetry source ({telemetry_src.value}) is not yet implemented for airline_iata based twjd"
                )
        return df, df_satellite

    def _fetch_flight_id_day(
        self,
        day: str,
        flight_id: list[str],
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
                f"specified telemetry source ({telemetry_src.value}) is not yet implemented for flight_id based twjd"
            )

        next_day = (pd.Timestamp(day) + pd.Timedelta(days=1)).strftime("%Y-%m-%d")

        query = self._bq_handler.import_query(self.FLIGHT_ID_QUERY_FILENAME)
        cfg = bigquery.QueryJobConfig(
            query_parameters=[
                bigquery.ScalarQueryParameter("target_day", "STRING", day),
                bigquery.ScalarQueryParameter("target_day_after", "STRING", next_day),
                bigquery.ArrayQueryParameter("flight_id", "STRING", flight_id),
            ]
        )
        df: pd.DataFrame = self._bq_handler.query(query, cfg)
        df.drop_duplicates(inplace=True)

        # segregate sat data (i.e. terr_waypoints with missing flight_id)
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
            else:
                raise NotImplementedError(f"twjd could not be processed {twjd}")
        except InvalidQueryException as e:
            raise PermanentFailureException(
                f"adsb request to bq not valid for twjd - {twjd}"
            ) from e
        except SpireCacheTooSmallException as e:
            raise PermanentFailureException(
                f"missing spire cache for twjd - {twjd}"
            ) from e
        except Exception as e:
            raise Exception(
                f"failed to fetch ads-b data from data source for twjd - {twjd}"
            ) from e

        # -----------
        # resample trajectories,
        # compose trajectory-worker jobs, on each flight instance,
        # and submit jobs to worker queue
        # -----------
        flight_instances = df.groupby("flight_id", sort=True)
        job_hash = hashlib.shake_128(twjd.as_utf8_json()).hexdigest(
            8
        )  # useful for keying in logs

        # fetch marker, if one exists, from redis cache
        progress_marker: int = 0
        if self._cache_handler and twjd.airline_iata:
            # we skip cache handling if this is a twjd w/o airline_iata
            # i.e. we don't bother with cache handling for small jobs
            # where the trajectories are for a single icao_address or flight_id
            key = f"{twjd.airline_iata}:{twjd.day}:{twjd.met_source.value}"
            if resp := self._cache_handler.pull(key):
                progress_marker = resp
                # TODO: add SMS alert on this event
                logger.warning(
                    "resuming progress from a previous job",
                    extra={
                        "marker": progress_marker,
                        "airline_iata": [twjd.airline_iata],
                        "twjd": twjd,
                        "job_hash": job_hash,
                    },
                )

        counter = 0
        number_of_flight_candidates = len(flight_instances.groups)
        for flight_id, terr_waypoints in flight_instances:
            if sigterm_manager.should_exit:
                sys.exit(0)

            counter += 1

            # fast-forward if we are resuming a job
            if counter <= progress_marker:
                continue

            if (counter % self.FLIGHT_INSTANCE_PROGRESS_COUNT_INCREMENT) == 0:
                logger.debug(
                    f"progress - processing {counter} of {number_of_flight_candidates}"
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

            # --------------
            # establish log context; track flight candidate
            # --------------
            candidate = TrajectoryCandidateInfo.from_waypoints(
                flight_id=flight_id,
                df=waypoints,
                job_hash=job_hash,
            )

            # -------------
            # when processing airline_iata is null case
            # for TWJDs built on airline_iata<>day
            # -------------
            # we need to consider true null airline-iata flights
            # and false null airline-iata flights
            # -
            # a true null airline iata flight is one in which no waypoints
            # for a given flight are reported with an airline_iata
            # thus the flight is truly with no airline_iata
            # -
            # a false null airline iata flight is one in which the flight
            # is in truth associated with an airline_iata but some waypoints
            # are missing the airline_iata field
            # -
            # this is a consideration unique to the null airline iata case
            # as we are effectively disambiguating between interpreting
            # the meaning of single waypoint with a null airline iata
            # as being missing data for that waypoint versus truthfully
            # missing for the flight
            # ---------
            # we apply two null airline-iata case specific filters
            # (1) skip a flight if we observe any non-null airline iata waypoints
            #     for a null airline-iata job
            # (2) skip very short null airline-iata flights (this is likely extraneous with
            #     the addition of (1) ).
            if twjd.airline_iata == "null" and len(candidate.airline_iata) > 1:
                extra_log = candidate.to_dict()
                extra_log["detail"] = "presumed false null airline iata"
                logger.debug(
                    "skipping",
                    extra=extra_log,
                )
                continue

            if (
                twjd.airline_iata == "null"
                and len(waypoints) <= self.MIN_WAYPOINT_COUNT_NULL_AIRLINE_IATA
            ):
                extra_log = candidate.to_dict()
                extra_log["detail"] = "presumed spurious null airline iata"
                logger.debug(
                    "skipping",
                    extra=extra_log,
                )
                continue

            # short circuit if no waypoints in the flight_id group
            # are above 20,000 ft
            # -
            # motivation is to prune out general aviation flights when running
            # the job factory for airline_iata=null
            if (
                len(candidate.airline_iata) == 1
                and candidate.airline_iata[0] == "null"
                and waypoints["altitude_baro"].max()
                < self.MAX_NOMINAL_ALT_GEN_AVIATION_FT
            ):
                extra_log = candidate.to_dict()
                extra_log["detail"] = (
                    "presumed general aviation flight - no wps above 20k ft"
                )
                logger.debug(
                    "skipping",
                    extra=extra_log,
                )
                continue

            logger.info("start work", extra=candidate.to_dict())

            # -------------
            # Apply HEAL step
            # -------------
            try:
                self._traj_heal_handler.set(waypoints, candidate_info=candidate)
                waypoints = self._traj_heal_handler.heal()
                self._traj_heal_handler.unset()

                # update log context
                candidate = TrajectoryCandidateInfo.from_waypoints(
                    flight_id=flight_id,
                    df=waypoints,
                )

                if len(waypoints) == 0:
                    # possible case if healing handler left no endpoint
                    logger.info(
                        "skipping",
                        extra={
                            "detail": "empty flight",
                            "flight_id": candidate.flight_id,
                        },
                    )
                    continue

            except Exception as _:
                logger.error(
                    "skipping",
                    extra={
                        "flight_id": candidate.flight_id,
                        "detail": "heal step failed",
                        "traceback": format_traceback(),
                    },
                )
                continue

            try:
                # -------------
                # apply RESAMPLE step
                # -------------

                # segregate telemetry data and pass to pycontrails.resample
                telemetry_columns = [
                    "timestamp",
                    "latitude",
                    "longitude",
                    "altitude_baro",
                ]
                waypoints_pycontrail = waypoints[telemetry_columns]
                waypoints_pycontrail = waypoints_pycontrail.copy(deep=True)

                # rename columns as expected by pycontrails.resample_and_fill
                waypoints_pycontrail.rename(
                    columns={"altitude_baro": "altitude_ft", "timestamp": "time"},
                    inplace=True,
                )
                # ensure timelike objs are naive, as expected by pycontrails.resample_and_fill
                waypoints_pycontrail["time"] = waypoints_pycontrail["time"].apply(
                    lambda r: r.tz_localize(None)
                )

                # resample waypoints
                pyc_flight = Flight(waypoints_pycontrail)
                waypoints_pycontrail = pyc_flight.resample_and_fill().dataframe
                del pyc_flight

                if len(waypoints_pycontrail) == 0:
                    # possible case if healing handler left single endpoint
                    # and none are left after resampling
                    logger.info(
                        "skipping",
                        extra={
                            "detail": "empty flight",
                            "flight_id": candidate.flight_id,
                        },
                    )
                    continue

                # UNDO manipulations to telemetry data introduced by pycontrails.resample_and_fill
                waypoints_pycontrail.loc[:, "altitude_baro"] = (
                    waypoints_pycontrail["altitude"] * 3.28
                ).astype(int)
                waypoints_pycontrail.drop(columns=["altitude"], inplace=True)
                waypoints_pycontrail.rename(columns={"time": "timestamp"}, inplace=True)

                # REINTRODUCE FIELDS NOT HANDLED BY pycontrails.resample_and_fill
                waypoints_pycontrail["flight_level"] = waypoints_pycontrail[
                    "altitude_baro"
                ].apply(altitude_ft_to_flight_level)
                waypoints_pycontrail["ingestion_time"] = None
                waypoints_pycontrail["collection_type"] = None
                # flight attrs (invariant fields; guaranteed invariant by HealingHandler)
                flight_attrs = HealTrajectoryHandler.INVARIANT_FLIGHT_ATTRS
                for attr in flight_attrs:
                    waypoints_pycontrail[attr] = waypoints[attr].iloc[0]

                # Find discontinuities in the raw data and mark waypoints on either side as "imputed"
                wp_diff = waypoints["timestamp"].diff()
                imputed_markers = wp_diff > pd.Timedelta(
                    seconds=self.TRAJECTORY_SAMPLING_CUTOFF_PERIOD_S
                )
                waypoints["imputed"] = imputed_markers
                waypoints["imputed"][
                    np.where(imputed_markers)[0] - 1
                ] = True  # mark before and after the discontinuity

                # merge datasets and sort, so resampled times fall between gap boundaries
                joined_times = pd.merge(
                    waypoints[["timestamp", "imputed"]],
                    waypoints_pycontrail["timestamp"].dt.tz_localize("UTC"),
                    left_on="timestamp",
                    right_on="timestamp",
                    how="outer",
                    indicator=True,
                )
                joined_times.sort_values("timestamp", inplace=True)

                imputed_range_markers = (
                    joined_times["imputed"] == True  # noqa: E712
                ).cumsum()  # Ticks up at each gap boundary
                impute_indices = (
                    imputed_range_markers % 2 == 1
                )  # stretches between imputed flags marked True in resampled data

                joined_times["imputed"] = impute_indices

                # pull out the resampled data only
                imputed = joined_times["imputed"][
                    (joined_times["_merge"] == "right_only")
                    | (joined_times["_merge"] == "both")
                ]
                imputed.fillna(False, inplace=True)  # Likely unnecessary
                # reindex to match waypoints_pycontrail and mark imputed waypoints
                imputed.reset_index(drop=True, inplace=True)
                waypoints_pycontrail["imputed"] = imputed

                del waypoints
            except Exception as _:
                logger.error(
                    "skipping",
                    extra={
                        "flight_id": candidate.flight_id,
                        "detail": "resample step failed",
                        "traceback": format_traceback(),
                    },
                )
                continue

            # update log context
            candidate = TrajectoryCandidateInfo.from_waypoints(
                flight_id=flight_id,
                df=waypoints_pycontrail,
            )

            if twjd.export_waypoints:
                # save waypoints to disk
                # CLI (local) use only
                logger.info("writing waypoints to file", extra=candidate.to_dict())
                airline_iata_path = candidate.airline_iata[0]
                if airline_iata_path is None:
                    airline_iata_path = "null"
                base_path = f"out/{airline_iata_path}"
                os.makedirs(base_path, exist_ok=True)
                waypoints_pycontrail.to_csv(
                    f"{base_path}/{candidate.flight_id}.csv",
                    index=False,
                )

            # ---------------
            # Apply VALIDATE step
            # ---------------
            permitted_violation_types = [
                ROCDError,
                UnknownAirportLocationError,
            ]
            try:
                self._validate_traj_handler.set(waypoints_pycontrail)
                violations: None | list[Exception] = (
                    self._validate_traj_handler.evaluate()
                )
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
                    logger.info(
                        "skipping",
                        extra={
                            "detail": "violations found",
                            "flight_id": candidate.flight_id,
                            "reason": violations,
                        },
                    )
                    continue

                if accepted_violations and len(accepted_violations) > 0:
                    logger.debug(
                        "keeping",
                        extra={
                            "flight_id": candidate.flight_id,
                            "detail": "acceptable violations found",
                            "reason": accepted_violations,
                        },
                    )
            except Exception as _:
                logger.error(
                    "skipping",
                    extra={
                        "detail": "validate step failed",
                        "flight_id": candidate.flight_id,
                        "traceback": format_traceback(),
                    },
                )
                continue

            # ---------------
            # build and submit job
            # ---------------
            try:
                records: list[SpireWaypointPositional] = []
                for _, r in waypoints_pycontrail.iterrows():
                    wp = SpireWaypointPositional(
                        ingestion_time=r["ingestion_time"],
                        timestamp=r["timestamp"].strftime("%Y-%m-%dT%H:%M:%SZ"),
                        latitude=r["latitude"],
                        longitude=r["longitude"],
                        collection_type=r["collection_type"],
                        altitude_baro=r["altitude_baro"],
                        imputed=r["imputed"],
                        flight_level=r["flight_level"],
                    )
                    records.append(wp)

                job = WaypointsRecord(
                    flight_info=FlightInfoWide.from_waypoints(waypoints_pycontrail),
                    records=records,
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
            except Exception as _:
                logger.error(
                    "skipping",
                    extra={
                        "detail": "job submit failed",
                        "flight_id": candidate.flight_id,
                        "traceback": format_traceback(),
                    },
                )
            # log state of flight submitted to TW
            logger.info("end work", extra=candidate.to_dict())

        if self._cache_handler and twjd.airline_iata:
            self._cache_handler.pop(
                f"{twjd.airline_iata}:{twjd.day}:{twjd.met_source.value}"
            )

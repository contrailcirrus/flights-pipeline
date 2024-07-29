import dataclasses
import json
from abc import ABC, abstractmethod
import argparse
from datetime import datetime, UTC, timedelta
from typing import Union, Tuple

import pandas as pd
from google.cloud import bigquery

from handlers import (
    PubSubSubscriptionHandler,
    PubSubPublishHandler,
    BigQueryHandler,
    ResampleHandler,
)
from schemas import FlightInfoWide, SpireWaypointPositional, WaypointsRecord
from log import logger


class BaseSvc(ABC):
    @abstractmethod
    def run(self) -> Union[dict, None]:
        """
        Entrypoint for running the service.
        Expected to return nothing, or, a dict that can be json serialized and printed.
        """


class FlightsSubmitSvc(BaseSvc):
    """
    Service backing calls to the flights submit parser.
    """

    DAILY_FLIGHTS_QUERY_FILENAME = "bq_waypoints_flights_daily_by_airline.sql"
    FLIGHT_ID_QUERY_FILENAME = "bq_waypoints_flights_daily_by_flight_id.sql"
    ICAO_ADDRESS_QUERY_FILENAME = "bq_waypoints_flights_daily_by_icao_address.sql"
    TRAJECTORY_WORKER_TOPIC = (
        "projects/contrails-301217/topics/prod-fp-gaia-trajectory-chunk"
    )
    ORDERING_KEY_TEMPLATE = "flightsreport:{}"

    def __init__(self, input: argparse.Namespace):
        """
        Parameters
        ----------
        input
            namespace object returned from the parser.
            expected to contain members:
            - airline
            - day
            - dryrun
            - verbose
        """
        self._airline = input.airline
        self._day = input.day
        self._flight_id = input.flight_id
        self._icao_address = input.icao_address
        self._dryrun = input.dryrun
        self._verbose = input.verbose
        self._export_waypoints = input.export_waypoints
        self._publish_handler = PubSubPublishHandler(
            self.TRAJECTORY_WORKER_TOPIC,
            ordered_queue=True,
        )
        self._bq_handler = BigQueryHandler()

        # caller must provide ONE OF the following sets of flags
        valid_flag_combos = {
            (self._day, self._airline),
            (self._day, self._flight_id),
            (self._day, self._icao_address),
        }
        is_valid = sum([all(itm) for itm in valid_flag_combos]) == 1

        if not is_valid:
            raise ValueError(
                "Must provide flags: "
                "(1) --flight_id & --day OR "
                "(2) --airline & --day OR "
                "(3) --icao_address & --day"
            )

    def _fetch_airline_day(self) -> (pd.DataFrame, pd.DataFrame):
        """
        Fetch and clean a days flights (flights starting on calendar day) from BigQuery.
        """
        td = pd.Timestamp.now(tz="UTC") - pd.Timestamp(self._day, tz="UTC")
        if td < pd.Timedelta(days=1):
            raise ValueError(" 🔴 flight day must be at least 1 day in the past 🔴")

        previous_day = (pd.Timestamp(self._day) - pd.Timedelta(days=1)).strftime(
            "%Y-%m-%d"
        )
        next_day = (pd.Timestamp(self._day) + pd.Timedelta(days=1)).strftime("%Y-%m-%d")

        query = self._bq_handler.import_query(self.DAILY_FLIGHTS_QUERY_FILENAME)
        cfg = bigquery.QueryJobConfig(
            query_parameters=[
                bigquery.ScalarQueryParameter("airline", "STRING", self._airline),
                bigquery.ScalarQueryParameter("target_day", "STRING", self._day),
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
            f"📜 received {len(df)} terrestrial & {len(df_satellite)} satellite from BigQuery. "
            f"Flight count: {len(df['flight_id'].unique())}"
        )
        return df, df_satellite

    def _fetch_flight_id_day(self) -> (pd.DataFrame, pd.DataFrame):
        """
        Fetch and clean a single flight (fetched by flight_id; filled w. sat) from BigQuery.
        """
        td = pd.Timestamp.now(tz="UTC") - pd.Timestamp(self._day, tz="UTC")
        if td < pd.Timedelta(days=1):
            raise ValueError(" 🔴 flight day must be at least 1 day in the past 🔴")
        next_day = (pd.Timestamp(self._day) + pd.Timedelta(days=1)).strftime("%Y-%m-%d")

        query = self._bq_handler.import_query(self.FLIGHT_ID_QUERY_FILENAME)
        cfg = bigquery.QueryJobConfig(
            query_parameters=[
                bigquery.ScalarQueryParameter("target_day", "STRING", self._day),
                bigquery.ScalarQueryParameter("target_day_after", "STRING", next_day),
                bigquery.ScalarQueryParameter("flight_id", "STRING", self._flight_id),
            ]
        )
        df: pd.DataFrame = self._bq_handler.query(query, cfg)
        df.drop_duplicates(inplace=True)

        # segregate sat data (i.e. terr_waypoints with missing flight_id)
        df_satellite = df[df["flight_id"].isnull()]
        df = df[~df["flight_id"].isnull()]
        logger.info(
            f"📜 received {len(df)} terrestrial & {len(df_satellite)} satellite from BigQuery. "
            f"Flight count: {len(df['flight_id'].unique())}"
        )
        return df, df_satellite

    def _fetch_icao_address_day(self) -> (pd.DataFrame, pd.DataFrame):
        """
        Fetch and clean a day's flights ofr a given icao_address from BigQuery.
        """
        td = pd.Timestamp.now(tz="UTC") - pd.Timestamp(self._day, tz="UTC")
        if td < pd.Timedelta(days=1):
            raise ValueError(" 🔴 flight day must be at least 1 day in the past 🔴")

        previous_day = (pd.Timestamp(self._day) - pd.Timedelta(days=1)).strftime(
            "%Y-%m-%d"
        )
        next_day = (pd.Timestamp(self._day) + pd.Timedelta(days=1)).strftime("%Y-%m-%d")

        query = self._bq_handler.import_query(self.ICAO_ADDRESS_QUERY_FILENAME)

        cfg = bigquery.QueryJobConfig(
            query_parameters=[
                bigquery.ScalarQueryParameter(
                    "icao_address", "STRING", self._icao_address
                ),
                bigquery.ScalarQueryParameter("target_day", "STRING", self._day),
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
            f"📜 received {len(df)} terrestrial & {len(df_satellite)} satellite from BigQuery. "
            f"Flight count: {len(df['flight_id'].unique())}"
        )
        return df, df_satellite

    def run(self):
        if self._day and self._airline:
            logger.info(f"🛠️submitting flights for ✈️ {self._airline} on 🗓️{self._day}")
            df, df_satellite = self._fetch_airline_day()
        elif self._day and self._flight_id:
            logger.info(
                f"🛠️submitting flight with 🛂 flight_id: {self._flight_id} on 🗓️{self._day}"
            )
            df, df_satellite = self._fetch_flight_id_day()
        elif self._day and self._icao_address:
            logger.info(
                f"🛠️submitting flight with 🏤 icao_address: {self._icao_address} on 🗓️{self._day}"
            )
            df, df_satellite = self._fetch_icao_address_day()

        # -----------
        # resample trajectories,
        # compose trajectory-worker jobs, on each flight instance,
        # and submit jobs to worker queue
        # -----------
        def _key_max_value_count(dfx, column_name):
            """
            If multiple unique values exist in a column, return the value with the highest count.
            Note that null values are not considered in the stack rank.
            """
            keys = list(
                dfx[column_name].value_counts().sort_values(ascending=False).keys()
            )
            # flight_id = dfx["flight_id"].iloc[0]
            # if len(keys) > 1:
            #     logger.warning(f"found multiple attributes "
            #                    f"for {column_name} of flight_id {flight_id} : {list(keys)}")
            # if not keys:
            #     logger.warning(f"only null values for {column_name} of flight_id {flight_id}")
            val = keys[0] if keys else None
            return val

        flight_instances = df.groupby("flight_id")
        for flight_id, terr_waypoints in flight_instances:
            # --------------
            # data monger
            # --------------
            first_ts = min(terr_waypoints["timestamp"])
            last_ts = max(terr_waypoints["timestamp"])

            aircraft_sel = df_satellite["icao_address"] == (
                _key_max_value_count(terr_waypoints, "icao_address")
            )
            flight_tmrg_sel = (df_satellite["timestamp"] > first_ts) & (
                df_satellite["timestamp"] < last_ts
            )

            sat_waypoints = df_satellite[aircraft_sel & flight_tmrg_sel]

            waypoints = pd.concat([terr_waypoints, sat_waypoints])

            # drop rows with inferior count on invariant attributes
            pre_invariant_prune_len = len(waypoints)
            priority_callsign = _key_max_value_count(waypoints, "callsign")
            priority_flight_number = _key_max_value_count(waypoints, "flight_number")
            priority_arrival_airport_icao = _key_max_value_count(
                waypoints, "arrival_airport_icao"
            )
            priority_departure_airport_icao = _key_max_value_count(
                waypoints, "departure_airport_icao"
            )
            priority_airline_iata = _key_max_value_count(waypoints, "airline_iata")
            if priority_callsign:
                waypoints["callsign"] = waypoints["callsign"].fillna(priority_callsign)
                waypoints = waypoints[waypoints["callsign"] == priority_callsign]
            if priority_flight_number:
                waypoints["flight_number"] = waypoints["flight_number"].fillna(
                    priority_flight_number
                )
                waypoints = waypoints[
                    waypoints["flight_number"] == priority_flight_number
                ]
            if priority_arrival_airport_icao:
                waypoints["arrival_airport_icao"] = waypoints[
                    "arrival_airport_icao"
                ].fillna(priority_arrival_airport_icao)
                waypoints = waypoints[
                    waypoints["arrival_airport_icao"] == priority_arrival_airport_icao
                ]
            if priority_departure_airport_icao:
                waypoints["departure_airport_icao"] = waypoints[
                    "departure_airport_icao"
                ].fillna(priority_departure_airport_icao)
                waypoints = waypoints[
                    waypoints["departure_airport_icao"]
                    == priority_departure_airport_icao
                ]
            waypoints["airline_iata"] = waypoints["airline_iata"].fillna(
                priority_airline_iata
            )

            waypoints.sort_values(by="timestamp", ascending=True, inplace=True)
            waypoints.reset_index(drop=True, inplace=True)

            # --------------
            # build jobs
            # --------------
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
                    ingestion_time=ln["ingestion_time"].strftime("%Y-%m-%dT%H:%M:%SZ"),
                    timestamp=ln["timestamp"].strftime("%Y-%m-%dT%H:%M:%SZ"),
                    latitude=ln["latitude"],
                    longitude=ln["longitude"],
                    collection_type=ln["collection_type"],
                    imputed=False,
                    altitude_baro=int(ln["altitude_baro"]),
                )
                records.append(record)
            resample_handler = ResampleHandler(cache=[], records_window=records)
            resample_handler.interpolate()
            waypoints_resampled: list[
                SpireWaypointPositional
            ] = resample_handler.waypoints_resampled
            job = WaypointsRecord(flight_info=flight_info, records=waypoints_resampled)

            if self._export_waypoints:
                resampled_df = pd.DataFrame(
                    [
                        {**dataclasses.asdict(flight_info), **dataclasses.asdict(pos)}
                        for pos in waypoints_resampled
                    ]
                )
                resampled_df.to_csv(
                    f"{flight_info.airline_iata}_{flight_info.flight_id}.csv",
                    index=False,
                )

            # --------------
            # submit jobs
            # --------------
            should_skip = len(waypoints_resampled) < 3
            if self._verbose:
                logger.info(
                    f" {'EMPTY! SKIPPING...' if should_skip else ''} "
                    f"⇢ publishing trajectory for flight_id: {job.flight_info.flight_id} with "
                    f"{len(waypoints_resampled)} records."
                    f"(raw input: {len(terr_waypoints)} terrestrial, "
                    f"{len(sat_waypoints)} satellite. "
                    f"dropped {pre_invariant_prune_len - len(waypoints)} "
                    f"due to invariant violations.)"
                )
            if not self._dryrun and not should_skip:
                self._publish_handler.publish_async(
                    job.as_utf8_json(),
                    timeout_seconds=45,
                    ordering_key=self.ORDERING_KEY_TEMPLATE.format(
                        job.flight_info.flight_id
                    ),
                )

        if self._dryrun:
            logger.info("🌵dry run... exiting before submission")
            return
        logger.info("⏲️ waiting for publish to finish...")
        self._publish_handler.wait_for_publish(timeout_seconds=300)
        logger.info("🙌 DONE!")


class FlightsReinjectSvc(BaseSvc):
    """
    Service for extracting dead-lettered jobs, and re-injecting them into the worker queue.
    """

    WORKER_JOB_DEAD_LETTER_SUBSCRIPTION = "projects/contrails-301217/subscriptions/prod-fp-trajectory-gaia-chunk-ingress-dead-letter"
    DEAD_LETTER_ACK_DEADLINE_SEC = 60  # reference subscriber settings
    FLIGHT_ID_QUERY_FILENAME = "bq_waypoints_flights_daily_by_flight_id.sql"
    TRAJECTORY_WORKER_TOPIC = (
        "projects/contrails-301217/topics/prod-fp-gaia-trajectory-chunk"
    )
    ORDERING_KEY_TEMPLATE = "flightsreport:{}"

    def __init__(self, input: argparse.Namespace):
        """
        Parameters
        ----------
        input
            namespace object returned from the parser.
            expected to contain members:
            - airline
            - day
            - dryrun
            - verbose
        """
        self._count: str = input.count
        self._verbose = input.verbose
        self._dryrun = input.dryrun
        self._subscriber_handler = PubSubSubscriptionHandler(
            self.WORKER_JOB_DEAD_LETTER_SUBSCRIPTION,
        )
        self._publish_handler = PubSubPublishHandler(
            self.TRAJECTORY_WORKER_TOPIC,
            ordered_queue=True,
        )

    def run(self):
        """
        Pulls messages from the dead-letter subscription,
        and dispatches jobs back to the worker queue
        based on the flight_id of the dead-lettered job.
        """
        messages = self._subscriber_handler.fetch(int(self._count))
        start_time = datetime.now()
        logger.info(f"📜 fetched {len(messages)} messages from dead-letter queue.")
        msg: PubSubSubscriptionHandler.Message
        for msg in messages:
            record = WaypointsRecord.from_utf8_json(msg.data)
            logger.info(
                f"💦 re-injecting job for flight_id: {record.flight_info.flight_id}"
                f" with {len(record.records)} "
                f"waypoints from {record.flight_info.airline_iata} "
                f"with start on: {record.records[0].timestamp}"
            )
            if not self._dryrun:
                self._publish_handler.publish_async(
                    msg.data,
                    timeout_seconds=45,
                    ordering_key=self.ORDERING_KEY_TEMPLATE.format(
                        record.flight_info.flight_id
                    ),
                )
        if self._dryrun:
            logger.info("🌵dry run... exiting before submission")
            return

        logger.info("⏲️ waiting for publish to finish...")
        self._publish_handler.wait_for_publish(timeout_seconds=300)
        for msg in messages:
            self._subscriber_handler.ack(msg)
        if (datetime.now() - start_time) > timedelta(
            seconds=self.DEAD_LETTER_ACK_DEADLINE_SEC
        ):
            logger.warning(
                f"pull to ack period exceeded {self.DEAD_LETTER_ACK_DEADLINE_SEC} seconds."
            )
        logger.info("🙌 DONE!")


class FlightsReportFetchSvc(BaseSvc):
    """
    Service backing calls to the flights report fetch parser.
    """

    REPORT_QUERY_FILENAME = "bq_flights_report_daily.sql"
    EXPORT_RAW_FILENAME_TEMPLATE = (
        "flights_report_raw_{audience}_{airline}_{day}_{unixtime}.csv"
    )
    EXPORT_SUMMARY_FILENAME_TEMPLATE = (
        "flights_report_summary_{airline}_{day}_{unixtime}.json"
    )

    AREA_EARTH = 5.101e14  # m^2, surface of the earth
    SECONDS_PER_YEAR = 60 * 60 * 24 * 365  # s
    AGWP100 = 92.5e-15 * AREA_EARTH * SECONDS_PER_YEAR  # J per kg-CO2,100
    AGWP20 = 25.2e-15 * AREA_EARTH * SECONDS_PER_YEAR  # J per kg-CO2,20
    ERF_RF = 0.42

    def __init__(self, input: argparse.Namespace):
        """
        Parameters
        ----------
        input
            namespace object returned from the parser.
            expected to contain members:
            - airline
            - day
            - dryrun
            - verbose

        `day` accepts supported forms:
        `%Y-%m-%d` for a singular day, or `%Y-%m-%d_%Y-%m-%d` for a range, inclusive.
        """

        self._day_range: Tuple[str, str]
        try:
            if "_" in input.day:
                rg = input.day.split("_")
                self._day_range = tuple(self._validate_day_str(daystr) for daystr in rg)
            else:
                self._day_range = (
                    self._validate_day_str(input.day),
                    self._validate_day_str(input.day),
                )
        except ValueError as e:
            logger.error(
                f"invalid date input {input.day} for report service."
                f"format must be of form '2024-01-01' "
            )
            raise e

        self._airline = input.airline
        self._day_str = input.day
        self._verbose = input.verbose
        self._bq_handler = BigQueryHandler()

    @staticmethod
    def _validate_day_str(daystr: str) -> str:
        """
        Guarantees that the provided date string can be parsed as `%Y-%m-%d`.
        Echoes string back if valid.
        Raises error otherwise.
        """
        _ = datetime.strptime(daystr, "%Y-%m-%d")
        return daystr

    @staticmethod
    def _format_customer_df(df_in: pd.DataFrame) -> pd.DataFrame:
        """
        Takes a raw dataframe, as per the schema of the BigQuery response,
        and reformats to a table including just those columns, and column names,
        that are fit for distribution to external customers/stakeholders.
        """
        df = df_in.__deepcopy__()
        # rename columns
        df = df.rename(
            columns={
                "lat_start": "origin_latitude",
                "lon_start": "origin_longitude",
                "time_start": "first_waypoint_time",
                "lat_end": "destination_latitude",
                "lon_end": "destination_longitude",
                "time_end": "last_waypoint_time",
                "pycontrails_ver": "pycontrails_version",
                "perf_model_id": "aircraft_performance_model",
                "git_sha": "flights_pipeline_sha",
                "sum_ef_mj": "total_contrail_energy_forcing_mj",
                "chunk_len_km": "total_flight_distance_km",
            }
        )

        # reorder & drop columns
        df = df[
            [
                "airline_iata",
                "flight_number",
                "icao_address",
                "callsign",
                "tail_number",
                "aircraft_type_icao",
                "engine_uid",
                "origin_latitude",
                "origin_longitude",
                "first_waypoint_time",
                "destination_latitude",
                "destination_longitude",
                "last_waypoint_time",
                "aircraft_performance_model",
                "flight_duration_h",
                "total_flight_distance_km",
                "co2e20_kg",
                "co2e100_kg",
                "total_fuel_burn_kg",
                "total_co2_kg",
                "total_h2o_kg",
                "total_so2_kg",
                "total_sulphates_kg",
                "total_oc_kg",
                "total_nox_kg",
                "total_co_kg",
                "total_hc_kg",
                "total_nvpm_kg",
                "total_nvpm_giga_cnt",
                "mean_nvpm_ein",
                "total_contrail_energy_forcing_mj",
                "pycontrails_version",
            ]
        ]

        return df

    def run(self):
        logger.info(
            f"🐶 fetching report for airline {self._airline} on day/day-range {self._day_str}..."
        )
        query = self._bq_handler.import_query(self.REPORT_QUERY_FILENAME)
        cfg = bigquery.QueryJobConfig(
            query_parameters=[
                bigquery.ScalarQueryParameter("airline", "STRING", self._airline),
                bigquery.ScalarQueryParameter(
                    "day_start", "STRING", self._day_range[0]
                ),
                bigquery.ScalarQueryParameter("day_end", "STRING", self._day_range[1]),
            ]
        )
        df: pd.DataFrame = self._bq_handler.query(query, cfg)

        # calculate CO2e
        # kg CO2e,20
        df["co2e20_kg"] = df["sum_ef_mj"] * 10**6 * self.ERF_RF / self.AGWP20
        # kg CO2e,100
        df["co2e100_kg"] = df["sum_ef_mj"] * 10**6 * self.ERF_RF / self.AGWP100

        # calculate total flight duration; based on the assumption of 1min segments
        df["flight_duration_h"] = round(df["seg_cnt"] / 60, 2)

        # calculate average nvPM value
        df["mean_nvpm_ein"] = round(
            df["total_nvpm_giga_cnt"] / df["total_fuel_burn_kg"], 2
        )

        now_unix = int(datetime.now(tz=UTC).timestamp())

        # export raw data, values by flight_id
        export_raw_fn = self.EXPORT_RAW_FILENAME_TEMPLATE.format(
            audience="internal",
            airline=self._airline,
            day=self._day_str,
            unixtime=now_unix,
        )
        df.to_csv(export_raw_fn, index=False)

        # export sanitized data, values by flight_id
        df_customer = self._format_customer_df(df)
        export_customer_fn = self.EXPORT_RAW_FILENAME_TEMPLATE.format(
            audience="external",
            airline=self._airline,
            day=self._day_str,
            unixtime=now_unix,
        )
        df_customer.to_csv(export_customer_fn, index=False)

        # export summary stats
        count_aircrafts = df.icao_address.nunique()
        count_flights = df.flight_id.nunique()
        count_flights_positive_ef = len(df[df.sum_ef_mj > 0])
        total_flight_hours = df.seg_cnt.sum() // 60
        total_warming_contrails_flight_hours = df.seg_ef_cnt.sum() // 60
        total_fuel_burn_metric_tons = round(df.total_fuel_burn_kg.sum() / 1000.0, 2)
        total_co2_metric_tons = round(df.total_co2_kg.sum() / 1000.0, 2)
        total_nox_metric_tons = round(df.total_nox_kg.sum() / 1000.0, 3)
        total_so2_metric_tons = round(df.total_so2_kg.sum() / 1000.0, 3)

        # kg CO2e,20
        total_contrails_co2e20 = df.co2e20_kg.sum()
        total_contrails_co2e20_metric_tons = round(total_contrails_co2e20 / 1000.0, 3)
        # kg CO2e,100
        total_contrails_co2e100 = df.co2e100_kg.sum()
        total_contrails_co2e100_metric_tons = round(total_contrails_co2e100 / 1000.0, 3)

        summary = {
            "count_aircrafts": int(count_aircrafts),
            "count_flights": int(count_flights),
            "count_flights_positive_ef": int(count_flights_positive_ef),
            "total_flight_hours": int(total_flight_hours),
            "total_warming_contrails_flight_hours": int(
                total_warming_contrails_flight_hours
            ),
            "total_fuel_burn_metric_tons": float(total_fuel_burn_metric_tons),
            "total_co2_metric_tons": float(total_co2_metric_tons),
            "total_contrails_co2e20_metric_tons": float(
                total_contrails_co2e20_metric_tons
            ),
            "total_contrails_co2e100_metric_tons": float(
                total_contrails_co2e100_metric_tons
            ),
            "total_nox_metric_tons": float(total_nox_metric_tons),
            "total_so2_metric_tons": float(total_so2_metric_tons),
        }
        export_summary_fn = self.EXPORT_SUMMARY_FILENAME_TEMPLATE.format(
            airline=self._airline,
            day=self._day_str,
            unixtime=now_unix,
        )
        with open(export_summary_fn, "w") as fp:
            json.dump(summary, fp, indent=4)
        logger.info(
            f"📜 got {count_flights} flights. "
            f"exported to: \n{export_raw_fn}\n{export_customer_fn}\n{export_summary_fn}."
        )
        logger.info("🙌 DONE!")

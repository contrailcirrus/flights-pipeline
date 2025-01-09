import json
import uuid
import os
from abc import ABC, abstractmethod
import argparse
from datetime import datetime, timedelta, timezone
from typing import Union, Tuple

import numpy as np
import pandas as pd
from google.cloud import bigquery
import matplotlib.pyplot as plt
import cartopy.crs as ccrs
import cartopy.feature as cfeature
from matplotlib import cm
from matplotlib.ticker import MultipleLocator
import matplotlib.patches as patches
import matplotlib.lines as lines

from helpers import key_max_value_count
from handlers import (
    PubSubSubscriptionHandler,
    PubSubPublishHandler,
    BigQueryHandler,
    GoogDatasetHandler,
)

from schemas import (
    WaypointsRecord,
    MetSource,
    TrajectoryWorkerJobDescriptor,
)
from log import logger
from helpers import lookup_airport_icao_to_iata


class BaseSvc(ABC):
    @abstractmethod
    def run(self) -> Union[dict, None]:
        """
        Entrypoint for running the service.
        Expected to return nothing, or, a dict that can be json serialized and printed.
        """


class JobWorkerSubmitSvc(BaseSvc):
    """
    Service backing calls to the flights submit parser.
    """

    TWJD_TOPIC_ID = "projects/contrails-301217/topics/prod-fp-twjd-ingress"

    def __init__(self, input: argparse.Namespace):
        """
        Parameters
        ----------
        input
            namespace object returned from the parser.
            expected to contain members:
            - airline
            - day
            - flight_id
            - icao_address
            - met_data_src
            - full_traj
        """
        self._airline = input.airline
        self._day = input.day
        self._flight_id = input.flight_id
        self._icao_address = input.icao_address
        self._met_data_src = input.met_data_src
        self._full_traj = input.full_traj
        self._publish_handler = PubSubPublishHandler(
            self.TWJD_TOPIC_ID,
            ordered_queue=False,
        )

        # caller must provide ONE OF the following sets of flags
        valid_flag_combos = {
            (self._day, self._airline, self._met_data_src),
            (self._day, self._flight_id, self._met_data_src),
            (self._day, self._icao_address, self._met_data_src),
        }
        is_valid = sum([all(itm) for itm in valid_flag_combos]) == 1

        if not is_valid:
            raise ValueError(
                "Must provide flags: "
                "(1) --flight-id & --day & --met-data-src OR "
                "(2) --airline & --day & --met-data-src OR "
                "(3) --icao-address & --day & --met-data-src"
            )

        if self._met_data_src not in MetSource:
            raise ValueError(
                f"--met-data-src must be one of {[i.value for i in MetSource]}"
            )

    def run(self):
        if self._day and self._airline:
            logger.info(
                f"🛠️submitting TWJDs for ✈️ {self._airline} on 🗓️{self._day} using met data source 📊{self._met_data_src}"
            )
        elif self._day and self._flight_id:
            logger.info(
                f"🛠️submitting TWJDs with 🛂 flight_id: {self._flight_id} on 🗓️{self._day} using met data source 📊{self._met_data_src}"
            )
        elif self._day and self._icao_address:
            logger.info(
                f"🛠️submitting TWJDs with 🏤 icao_address: {self._icao_address} on 🗓️{self._day} using met data source 📊{self._met_data_src}"
            )
        else:
            raise NotImplementedError("unhandled runtime case.")

        twjd = TrajectoryWorkerJobDescriptor(
            day=self._day,
            met_source=MetSource(self._met_data_src),
            full_traj=self._full_traj,
            airline_iata=self._airline,
            flight_id=self._flight_id,
            icao_address=self._icao_address,
            dry_run=False,
            export_waypoints=False,
        )

        self._publish_handler.publish_async(
            twjd.as_utf8_json(),
            timeout_seconds=10,
        )

        logger.info("⏲️ waiting for publish to finish...")
        self._publish_handler.wait_for_publish(timeout_seconds=300)
        logger.info("🙌 DONE!")


class FlightsReinjectSvc(BaseSvc):
    """
    Service for extracting dead-lettered jobs, and re-injecting them into the worker queue.
    """

    WORKER_JOB_DEAD_LETTER_SUBSCRIPTION = "projects/contrails-301217/subscriptions/prod-fp-trajectory-gaia-chunk-ingress-dead-letter"
    DEAD_LETTER_ACK_DEADLINE_SEC = 60  # reference subscriber settings
    TRAJECTORY_WORKER_TOPIC = (
        "projects/contrails-301217/topics/prod-fp-gaia-trajectory-chunk"
    )

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
                    ordering_key=msg.ordering_key,
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

    REPORT_QUERY_FILENAME = "sql/bq_flights_report_daily.sql"
    CASE_STUDY_QUERY_FILENAME = "sql/bq_flights_report_fid_trajectory.sql"

    EXPORT_FLIGHTS_TRAJ_PLOT_FILENAME_TEMPLATE = "out/{airline}/trajectories.png"
    EXPORT_FLIGHT_COCIP_SEGS_FILENAME_TEMPLATE = (
        "out/{airline}/data_case_study_{ix}.csv"
    )
    EXPORT_FLIGHT_CASE_STUDY_FIG_TEMPLATE = "out/{airline}/fig_case_study_{ix}.png"
    EXPORT_FLIGHTS_OD_IMPACT_DENSITY_PLOT_FILENAME_TEMPLATE = (
        "out/{airline}/fig_od_by_impact_density.png"
    )
    EXPORT_FLIGHTS_OD_NET_CO2E_PLOT_FILENAME_TEMPLATE = (
        "out/{airline}/fig_od_by_net_co2e.png"
    )
    EXPORT_FLIGHTS_FUEL_EMISSIONS_VS_CONTRAIL_WARMING_PLOT_FILENAME_TEMPLATE = (
        "out/{airline}/fig_fuel_emissions_vs_contrail_warming.png"
    )
    EXPORT_FLIGHTS_CONTRAIL_WARMING_DAYTIME_VS_NIGHTTIME_PLOT_FILENAME_TEMPLATE = (
        "out/{airline}/fig_contrail_warming_daytime_vs_nighttime.png"
    )
    EXPORT_FLIGHTS_CONTRAIL_WARMING_PERCENTAGE_FILENAME_TEMPLATE = (
        "out/{airline}/fig_contrail_warming_percentage.png"
    )
    EXPORT_FLIGHTS_CONTRAIL_DISTANCE_DAYTIME_NIGHTTIME_FILENAME_TEMPLATE = (
        "out/{airline}/fig_contrail_distance_daytime_nighttime.png"
    )
    EXPORT_FLIGHTS_CONTRAIL_DISTANCE_WARMING_DAYTIME_NIGHTTIME_FILENAME_TEMPLATE = (
        "out/{airline}/fig_contrail_distance_warming_daytime_nighttime.png"
    )

    AREA_EARTH = 5.101e14  # m^2, surface of the earth
    SECONDS_PER_YEAR = 60 * 60 * 24 * 365  # s
    AGWP100 = 92.5e-15 * AREA_EARTH * SECONDS_PER_YEAR  # J per kg-CO2,100
    AGWP50 = 53.0e-15 * AREA_EARTH * SECONDS_PER_YEAR  # J per kg-CO2,50
    AGWP20 = 25.2e-15 * AREA_EARTH * SECONDS_PER_YEAR  # J per kg-CO2,20
    ERF_RF = 0.42
    # CONUS_COORDS = ((-134.03, 50.07), (-121.2, 14.9), (-63.2, 10.5), (-46.1, 44.1))
    # CONUS_WKT = (
    #    "POLYGON((-134.03 50.07, -121.2 14.9, -63.2 10.5, -46.1 44.1, -134.03 50.07))"
    # )
    CONUS_COORDS = (
        (-40, 61),
        (-110, 61),
        (-128, 52.3),
        (-134, 50),
        (-120, 10),
        (-90, -5),
        (-90, -40),
        (-50, -40),
        (-30, 0),
        (-60, 15),
    )
    CONUS_WKT = "POLYGON((-40 61,-110 61,-128 52.3,-134 50,-120 10,-90 -5,-90 -40,-50 -40,-30 0,-60 15, -40 61))"
    EU_WKT = "POLYGON ((-10.4037843 37.3067379, 15.5392418 36.9893253, 18.9010582 39.7282502, 16.3742027 44.8597045, 20.4830894 46.1531429, 23.2296715 41.6277001, 19.7360191 39.6606218, 23.4341063 35.966799, 28.3559813 40.8532061, 29.4106688 45.0947714, 22.9946532 48.2300851, 24.1372313 53.5451353, 28.1802 56.1255892, 29.1469969 72.1034405, -11.7221437 54.9822761, -10.4037843 37.3067379))"

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
            - goog_fp
            - case_study_fids

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
        self._met_data_src = input.met_data_src
        self._verbose = input.verbose
        self._dryrun = input.dryrun
        self._goog_fp = input.goog_fp
        self._case_study_fids = input.case_study_fids
        if self._case_study_fids:
            self._validate_case_study_fids(self._case_study_fids)

        self._bq_handler = BigQueryHandler()
        if self._goog_fp:
            self._goog_handler = GoogDatasetHandler(self._goog_fp)
        else:
            self._goog_handler = None

        if self._met_data_src not in MetSource:
            raise ValueError(
                f"--met-data-src must be one of {[i.value for i in MetSource]}"
            )

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
    def _validate_case_study_fids(cs_fids: str):
        """
        Validates input string passed to the handler (-s "<case_study_fids>").
        Expects a single UUID string literal, or list of comma separated UUID string literals.
        """
        fids = cs_fids.split(",")
        for fid in fids:
            try:
                uuid.UUID(fid)
            except ValueError as e:
                raise Exception(
                    f"bad argument for -s/--case_study_fids. "
                    f"Must be a comma separated list of valid UUID strings. "
                    f"Exception: {e}"
                )

    @staticmethod
    def _format_customer_df(df_in: pd.DataFrame) -> pd.DataFrame:
        """
        Takes a raw dataframe, as per the schema of the BigQuery response,
        and reformats to a table including just those columns, and column names,
        that are fit for distribution to external customers/stakeholders.
        """
        df = df_in.copy(deep=True)
        # rename columns
        df = df.rename(
            columns={
                "lat_start": "origin_latitude",
                "lon_start": "origin_longitude",
                "time_start": "first_waypoint_time",
                "time_start_local": "first_waypoint_local_time",
                "lat_end": "destination_latitude",
                "lon_end": "destination_longitude",
                "time_end": "last_waypoint_time",
                "time_end_local": "last_waypoint_local_time",
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
                "first_waypoint_local_time",
                "destination_latitude",
                "destination_longitude",
                "last_waypoint_time",
                "last_waypoint_local_time",
                "aircraft_performance_model",
                "flight_duration_h",
                "total_flight_distance_km",
                "co2e20_kg",
                "co2e50_kg",
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

    @classmethod
    def augment_summary_df(cls, df: pd.DataFrame) -> pd.DataFrame:
        """
        Helper method to add additional columns to the summary flights report df retrieved from BQ.
        """
        df = df.copy(deep=True)
        # calculate CO2e
        # kg CO2e,20
        df["co2e20_kg"] = df["sum_ef_mj"] * 10**6 * cls.ERF_RF / cls.AGWP20
        df["daytime_co2e20_kg"] = (
            df["daytime_sum_ef_mj"] * 10**6 * cls.ERF_RF / cls.AGWP20
        )
        df["nighttime_co2e20_kg"] = (
            df["nighttime_sum_ef_mj"] * 10**6 * cls.ERF_RF / cls.AGWP20
        )
        # kg CO2e,50
        df["co2e50_kg"] = df["sum_ef_mj"] * 10**6 * cls.ERF_RF / cls.AGWP50
        df["in_conus_co2e50_kg"] = (
            df["in_conus_sum_ef_mj"] * 10**6 * cls.ERF_RF / cls.AGWP50
        )
        if "in_eu_sum_ef_mj" in df.keys():
            # we only augment the all-flights dataset w/ this, not the single trajectory dataset
            df["in_eu_co2e50_kg"] = (
                df["in_eu_sum_ef_mj"] * 10**6 * cls.ERF_RF / cls.AGWP50
            )
        df["daytime_co2e50_kg"] = (
            df["daytime_sum_ef_mj"] * 10**6 * cls.ERF_RF / cls.AGWP50
        )
        df["nighttime_co2e50_kg"] = (
            df["nighttime_sum_ef_mj"] * 10**6 * cls.ERF_RF / cls.AGWP50
        )
        # kg CO2e,100
        df["co2e100_kg"] = df["sum_ef_mj"] * 10**6 * cls.ERF_RF / cls.AGWP100
        df["daytime_co2e100_kg"] = (
            df["daytime_sum_ef_mj"] * 10**6 * cls.ERF_RF / cls.AGWP100
        )
        df["nighttime_co2e100_kg"] = (
            df["nighttime_sum_ef_mj"] * 10**6 * cls.ERF_RF / cls.AGWP100
        )

        # calculate total flight duration; based on the assumption of 1min segments
        df["flight_duration_h"] = round(df["seg_cnt"] / 60, 2)

        # calculate average nvPM value
        df["mean_nvpm_ein"] = round(
            df["total_nvpm_giga_cnt"] / df["total_fuel_burn_kg"], 2
        )

        df.loc[:, "time_start_local"] = df.apply(
            lambda row: row["time_start"].astimezone(
                timezone(timedelta(hours=int(row["time_start_tz"])))
            ),
            axis=1,
        )
        df.loc[:, "time_end_local"] = df.apply(
            lambda row: row["time_end"].astimezone(
                timezone(timedelta(hours=int(row["time_end_tz"])))
            ),
            axis=1,
        )

        df.loc[:, "time_start_local_hour"] = df.time_start.apply(lambda ts: ts.hour)

        df.loc[:, "time_start_local_date"] = df.time_start.apply(
            lambda ts: ts.strftime("%Y-%m-%d")
        )
        df.loc[:, "time_start_local_date"] = pd.to_datetime(df["time_start_local_date"])

        df.loc[:, "departure_airport_iata"] = df.departure_airport_icao.apply(
            lambda airport_icao: lookup_airport_icao_to_iata(airport_icao)
        )
        df.loc[:, "arrival_airport_iata"] = df.arrival_airport_icao.apply(
            lambda airport_icao: lookup_airport_icao_to_iata(airport_icao)
        )

        df.loc[:, "airport_icao_od"] = df.apply(
            lambda row: f"{row.departure_airport_icao}_{row.arrival_airport_icao}",
            axis=1,
        )
        df.loc[:, "airport_iata_od"] = df.apply(
            lambda row: f"{row.departure_airport_iata}_{row.arrival_airport_iata}",
            axis=1,
        )

        # IMPORTANT
        # ---------
        # flight instance attrs in google's dataset vary from those in Reviate's dataset
        # (Reviate's dataset mirrors Spire ADS-B reported values, exactly...
        #    Goog's dataset appears to have some field manipulation/sanitization)
        # ....
        # 1) flight_number
        #    reviate dataset has prefix of the airline iata (e.g. str: "D02")
        #    google dataset reports integers w/o padding (e.g. int: 2)
        # 2) tail_number
        #    reviate dataset includes hyphenation (e.g. str: "G-DHLS")
        #    Goog's dataset does NOT include hyphenation (e.g. str: "GDHLS")
        if len(df["flight_id"].unique()) == 1:
            # we're handling a dataframe with per-segment data
            # here, we want to use the time_start_local_date of the flight instance
            # NOT the time_start_local_date of each segment
            dep_airport_icao = key_max_value_count(df, "departure_airport_icao")
            ar_airport_icao = key_max_value_count(df, "arrival_airport_icao")
            flight_number = key_max_value_count(df, "flight_number")
            ts_local_date = df["time_start_local_date"].min()
            df.loc[:, "google_flight_id"] = (
                f"{int(ts_local_date.timestamp())}_{dep_airport_icao}_{ar_airport_icao}_{flight_number[2:] if flight_number else None}"
            )
        else:
            df.loc[:, "google_flight_id"] = df.apply(
                lambda row: f"{int(row['time_start_local_date'].timestamp())}_"
                f"{row['departure_airport_icao']}_"
                f"{row['arrival_airport_icao']}_"
                f"{row['flight_number'][2:] if row['flight_number'] else None}",
                axis=1,
            )

        return df

    def run(self):
        logger.info(
            f"🐶 fetching report for airline {self._airline} on day/day-range {self._day_str}..."
            f"case study flight_ids: {self._case_study_fids}"
        )

        output_asset_path = f"{os.getcwd()}/out/{self._airline}"
        if not os.path.exists(output_asset_path):
            os.mkdir(output_asset_path)

        if self._met_data_src == MetSource.HRES:
            # note: we retain `2%` as a valid match for HRES
            # to support traj outputs that were generated prior to the introduction of ERA5
            # previously, zarr_uri in the BQ table was always `%Y%m%d%H`
            # now, zarr_uri is `HRES/%Y%m%d%H` or `ERA5/%Y%m%d%H`
            met_src_str_match = ["HRES/%", "2%"]
        elif self._met_data_src == MetSource.ERA5:
            met_src_str_match = ["ERA5/%"]

        summary_query = self._bq_handler.import_query(self.REPORT_QUERY_FILENAME)
        cfg = bigquery.QueryJobConfig(
            query_parameters=[
                bigquery.ScalarQueryParameter("airline", "STRING", self._airline),
                bigquery.ArrayQueryParameter(
                    "met_src_str_match", "STRING", met_src_str_match
                ),
                bigquery.ScalarQueryParameter(
                    "day_start", "STRING", self._day_range[0]
                ),
                bigquery.ScalarQueryParameter("day_end", "STRING", self._day_range[1]),
                bigquery.ScalarQueryParameter(
                    "conus_wkt",
                    "STRING",
                    self.CONUS_WKT,
                ),
                bigquery.ScalarQueryParameter(
                    "eu_wkt",
                    "STRING",
                    self.EU_WKT,
                ),
            ]
        )
        summary_df: pd.DataFrame = self._bq_handler.query(summary_query, cfg)
        summary_df = self.augment_summary_df(summary_df)
        if self._goog_handler:
            summary_df = pd.merge(
                summary_df,
                self._goog_handler.df_summary,
                how="left",
                on="google_flight_id",
            )

        # fetch per-segment data for case study flight ids
        case_study_dfs: list[pd.DataFrame] = []  # noqa: F841
        if self._case_study_fids:
            day_end = datetime.strptime(self._day_range[1], "%Y-%m-%d")
            next_day = day_end + timedelta(days=1)
            next_day_str = next_day.strftime("%Y-%m-%d")
            case_studies_query = self._bq_handler.import_query(
                self.CASE_STUDY_QUERY_FILENAME
            )
            cfg = bigquery.QueryJobConfig(
                query_parameters=[
                    bigquery.ScalarQueryParameter(
                        "flight_ids",
                        "STRING",
                        self._case_study_fids,
                    ),
                    bigquery.ScalarQueryParameter(
                        "day_start",
                        "STRING",
                        self._day_range[0],
                    ),
                    bigquery.ScalarQueryParameter(
                        "day_end",
                        "STRING",
                        next_day_str,
                    ),
                    bigquery.ArrayQueryParameter(
                        "met_src_str_match", "STRING", met_src_str_match
                    ),
                    bigquery.ScalarQueryParameter(
                        "conus_wkt",
                        "STRING",
                        self.CONUS_WKT,
                    ),
                ]
            )
            case_studies_df: pd.DataFrame = self._bq_handler.query(  # noqa: F841
                case_studies_query, cfg
            )
            for flight_id, df in case_studies_df.groupby("flight_id"):
                df.reset_index(inplace=True, drop=True)
                df = self.augment_summary_df(df)
                # add in google sat detection, if available
                df["goog_is_attributed"] = (
                    False  # flight segment has google sat attribution
                )
                if self._goog_handler:
                    df_goog_fid = df["google_flight_id"].unique()
                    if len(df_goog_fid) > 1:
                        raise Exception(
                            f"more than one google_flight_id "
                            f"for per-segment dataset w. flight_id: {flight_id}. "
                            f"Skipping merge of google dataset."
                        )
                    else:
                        # fetch periods of time when goog has attribution for the flight
                        attr_periods = self._goog_handler.df[
                            self._goog_handler.df["google_flight_id"] == df_goog_fid[0]
                        ]
                        for ix, row in attr_periods.iterrows():
                            period_start_utc = row["timestamp_utc_start"]
                            period_start_utc = period_start_utc.floor(freq="min")
                            period_end_utc = row["timestamp_utc_end"]
                            period_end_utc = period_end_utc.ceil(freq="min")
                            slice = (df["time_start"] >= period_start_utc) & (
                                df["time_end"] <= period_end_utc
                            )
                            df.loc[slice, "goog_is_attributed"] = True
                case_study_dfs.append(df)

        # -----------------
        # build summary stats
        # -----------------
        count_aircrafts = summary_df.icao_address.nunique()
        count_flights = summary_df.flight_id.nunique()
        count_flights_in_eu = summary_df.flight_id[
            ~summary_df.in_eu_dist_km.isna()
        ].nunique()
        count_flights_positive_ef = len(summary_df[summary_df.sum_ef_mj > 0])
        total_flight_hours = summary_df.seg_cnt.sum() // 60
        total_contrails_flight_hours = summary_df.seg_ef_cnt.sum() // 60

        total_flight_distance_km = int(summary_df.chunk_len_km.sum())
        total_in_conus_flight_distance_km = int(summary_df.in_conus_dist_km.sum())
        total_in_eu_flight_distance_km = int(summary_df.in_eu_dist_km.sum())
        total_contrails_distance_km = int(
            summary_df.total_persistent_contrail_length_km.sum()
        )
        total_warming_contrails_distance_km = int(
            summary_df.total_pos_ef_persistent_contrail_length_km.sum()
        )
        total_in_conus_warming_contrails_distance_km = int(
            summary_df.in_conus_warming_contrail_dist_km.sum()
        )
        total_daytime_flight_distance_km = int(summary_df.daytime_dist_km.sum())
        total_daytime_contrail_distance_km = int(
            summary_df.daytime_contrail_dist_km.sum()
        )
        total_daytime_warming_contrail_distance_km = int(
            summary_df.daytime_warming_contrail_dist_km.sum()
        )
        total_nighttime_flight_distance_km = int(summary_df.nighttime_dist_km.sum())
        total_nighttime_contrail_distance_km = int(
            summary_df.nighttime_contrail_dist_km.sum()
        )
        total_nighttime_warming_contrail_distance_km = int(
            summary_df.nighttime_warming_contrail_dist_km.sum()
        )
        percentage_flight_dist_w_contrails = round(
            total_contrails_distance_km / total_flight_distance_km * 100.0, 1
        )
        percentage_flight_dist_w_warming_contrails = round(
            total_warming_contrails_distance_km / total_flight_distance_km * 100.0, 1
        )
        percentage_daytime_total_flight_distance = round(
            total_daytime_flight_distance_km / total_flight_distance_km * 100.0, 1
        )
        percentage_daytime_warming_contrail_distance = round(
            total_daytime_warming_contrail_distance_km
            / total_warming_contrails_distance_km
            * 100.0,
            1,
        )

        if self._goog_handler:
            total_goog_contrails_verified_distance_km = int(
                self._goog_handler.df.attributed_contrail_length_km.sum()
            )
            total_goog_contrails_verified_warming_mj = (
                int(self._goog_handler.df.eef_tj.sum()) * 1e6
            )
            total_goog_contrails_verified_co2e50_metric_tons = (
                total_goog_contrails_verified_warming_mj
                * 10**6
                * self.ERF_RF
                / self.AGWP50
                / 1000
            )
        else:
            total_goog_contrails_verified_distance_km = None
            total_goog_contrails_verified_warming_mj = None
            total_goog_contrails_verified_co2e50_metric_tons = None

        total_in_conus_contrails_distance_km = int(
            summary_df.in_conus_contrail_dist_km.sum()
        )

        total_fuel_burn_metric_tons = round(
            summary_df.total_fuel_burn_kg.sum() / 1000.0, 2
        )
        total_co2_metric_tons = round(summary_df.total_co2_kg.sum() / 1000.0, 2)
        total_co2_in_eu_metric_tons = round(
            summary_df.in_eu_total_co2_kg.sum() / 1000.0, 2
        )
        total_nox_metric_tons = round(summary_df.total_nox_kg.sum() / 1000.0, 3)
        total_so2_metric_tons = round(summary_df.total_so2_kg.sum() / 1000.0, 3)

        # kg CO2e,20
        total_contrails_co2e20 = summary_df.co2e20_kg.sum()
        total_contrails_co2e20_metric_tons = round(total_contrails_co2e20 / 1000.0, 3)
        # kg CO2e,50
        total_contrails_co2e50 = summary_df.co2e50_kg.sum()
        total_contrails_co2e50_metric_tons = round(total_contrails_co2e50 / 1000.0, 3)
        total_in_conus_contrails_co2e50 = summary_df.in_conus_co2e50_kg.sum()
        total_in_conus_contrails_co2e50_metric_tons = round(
            total_in_conus_contrails_co2e50 / 1000.0, 3
        )
        total_in_eu_contrails_co2e50 = summary_df.in_eu_co2e50_kg.sum()
        total_in_eu_contrails_co2e50_metric_tons = round(
            total_in_eu_contrails_co2e50 / 1000.0, 3
        )
        total_daytime_contrails_co2e50 = summary_df.daytime_co2e50_kg.sum()
        total_daytime_contrails_co2e50_metric_tons = round(
            total_daytime_contrails_co2e50 / 1000.0, 3
        )
        total_nighttime_contrails_co2e50 = summary_df.nighttime_co2e50_kg.sum()
        total_nighttime_contrails_co2e50_metric_tons = round(
            total_nighttime_contrails_co2e50 / 1000.0, 3
        )
        percentage_daytime_total_contrails_co2e50 = round(
            total_daytime_contrails_co2e50 / total_contrails_co2e50 * 100.0, 1
        )
        # kg CO2e,100
        total_contrails_co2e100 = summary_df.co2e100_kg.sum()
        total_contrails_co2e100_metric_tons = round(total_contrails_co2e100 / 1000.0, 3)

        # -----------------
        # CO2GWP50 by local takeoff hour-of-day
        # -----------------
        warm_group = (
            summary_df[summary_df.co2e50_kg > 0]
            .groupby("time_start_local_hour")
            .co2e50_kg.sum()
        )
        co2e_warming_by_takeoff_hr = warm_group.to_dict()
        # report as metric tons
        for k, v in co2e_warming_by_takeoff_hr.items():
            co2e_warming_by_takeoff_hr[k] = v / 1000
        cool_group = (
            summary_df[summary_df.co2e50_kg < 0]
            .groupby("time_start_local_hour")
            .co2e50_kg.sum()
        )
        co2e_cooling_by_takeoff_hr = cool_group.to_dict()
        # report as metric tons
        for k, v in co2e_cooling_by_takeoff_hr.items():
            co2e_cooling_by_takeoff_hr[k] = v / 1000

        net_group = summary_df.groupby("time_start_local_hour").co2e50_kg.sum()
        co2e_by_takeoff_hr = net_group.to_dict()
        # report as metric tons
        for k, v in co2e_by_takeoff_hr.items():
            co2e_by_takeoff_hr[k] = v / 1000

        # -----------------
        # Per-OD-pair summary
        # -----------------
        od_group_co2e = summary_df.groupby("airport_iata_od").co2e50_kg.sum()
        od_group_cnt = summary_df.groupby("airport_iata_od").size()
        od_group_nighttime_co2e = summary_df.groupby(
            "airport_iata_od"
        ).nighttime_co2e50_kg.sum()
        od_group_dist_km = summary_df.groupby("airport_iata_od").chunk_len_km.sum()
        od_pairs = []
        for k, v in od_group_co2e.to_dict().items():
            co2e = v / 1000.0
            dist = od_group_dist_km.to_dict().get(k)
            nighttime_co2e = od_group_nighttime_co2e.to_dict().get(k) / 1000.0
            perc_nighttime_co2e = (
                max(round(nighttime_co2e / co2e * 100.0, 0), 100) if co2e > 0 else None
            )  # percentage of total co2e that was from nighttime contrails
            entry = {
                "airport_iata_od": k,
                "co2e50_metric_tons": co2e,
                "percentage_nighttime_co2e": perc_nighttime_co2e,
                "flight_count": od_group_cnt.to_dict().get(k),
                "tot_dist_km": dist,
                "impact_density_co2e_metric_tons_per_dist_km": co2e / dist,
            }
            od_pairs.append(entry)
        od_pairs = sorted(
            od_pairs,
            key=lambda itm: itm["impact_density_co2e_metric_tons_per_dist_km"],
            reverse=True,
        )

        # -----------------
        # package summary
        # -----------------
        summary = {
            "count_aircrafts": int(count_aircrafts),
            "count_flights": {
                "total": int(count_flights),
                "in_eu": int(count_flights_in_eu),
            },
            "count_flights_positive_ef": int(count_flights_positive_ef),
            "flight_hours": {
                "total": int(total_flight_hours),
                "with_contrails": int(total_contrails_flight_hours),
            },
            "flight_distance_km": {
                "total": total_flight_distance_km,
                "in_conus": total_in_conus_flight_distance_km,
                "in_eu": total_in_eu_flight_distance_km,
                "daytime": total_daytime_flight_distance_km,
                "nighttime": total_nighttime_flight_distance_km,
                "with_contrails": {
                    "total": total_contrails_distance_km,
                    "in_conus": total_in_conus_contrails_distance_km,
                    "goog_sat_verified": total_goog_contrails_verified_distance_km,
                    "daytime": total_daytime_contrail_distance_km,
                    "nighttime": total_nighttime_contrail_distance_km,
                    "is_warming": {
                        "total": total_warming_contrails_distance_km,
                        "in_conus": total_in_conus_warming_contrails_distance_km,
                        "daytime": total_daytime_warming_contrail_distance_km,
                        "nighttime": total_nighttime_warming_contrail_distance_km,
                    },
                },
            },
            "percentages": {
                "flight_distance_with_contrails": percentage_flight_dist_w_contrails,
                "flight_distance_with_warming_contrails": percentage_flight_dist_w_warming_contrails,
                "flight_distance_during_daytime": percentage_daytime_total_flight_distance,
                "daytime_warming_contrails": percentage_daytime_warming_contrail_distance,
                "daytime_contrail_co2e50": percentage_daytime_total_contrails_co2e50,
                "co2e50_vs_all_co2": round(
                    total_contrails_co2e50_metric_tons
                    / (total_contrails_co2e50_metric_tons + total_co2_metric_tons)
                    * 100.0,
                    1,
                ),
            },
            "co2e_metric_tons": {
                "gwp20": {
                    "total": float(total_contrails_co2e20_metric_tons),
                },
                "gwp50": {
                    "total": float(total_contrails_co2e50_metric_tons),
                    "in_conus": total_in_conus_contrails_co2e50_metric_tons,
                    "in_eu": total_in_eu_contrails_co2e50_metric_tons,
                    "goog_sat_verified": total_goog_contrails_verified_co2e50_metric_tons,
                    "daytime": {
                        "total": total_daytime_contrails_co2e50_metric_tons,
                    },
                    "nighttime": {
                        "total": float(total_nighttime_contrails_co2e50_metric_tons),
                    },
                },
                "gwp100": {"total": float(total_contrails_co2e100_metric_tons)},
            },
            "total_fuel_burn_metric_tons": float(total_fuel_burn_metric_tons),
            "co2_metric_tons": {
                "total_co2_metric_tons": float(total_co2_metric_tons),
                "in_eu_total_co2_metric_tons": float(total_co2_in_eu_metric_tons),
            },
            "total_nox_metric_tons": float(total_nox_metric_tons),
            "total_so2_metric_tons": float(total_so2_metric_tons),
            "takeoff_time_local_co2e50_metric_tons_warming": co2e_warming_by_takeoff_hr,
            "takeoff_time_local_co2e50_metric_tons_cooling": co2e_cooling_by_takeoff_hr,
            "takeoff_time_local_co2e50_metric_tons_net": co2e_by_takeoff_hr,
            "od_pairs": od_pairs,
        }

        if not self._dryrun:

            # -----------------
            # export raw data, values by flight_id
            # -----------------
            summary_df.to_csv(f"out/{self._airline}/data_all_internal.csv", index=False)

            # -----------------
            # export sanitized data, values by flight_id
            # -----------------
            df_customer = self._format_customer_df(summary_df)
            df_customer.to_csv(
                f"out/{self._airline}/data_all_external.csv", index=False
            )

            # -----------------
            # export summary json
            # -----------------
            with open(f"out/{self._airline}/data_summary.json", "w") as fp:
                json.dump(summary, fp, indent=4)
            logger.info(f"📜 got {count_flights} flights. " f"exported to file.")

            # -----------------
            # export augmented google dataset
            # -----------------
            if self._goog_handler:
                self._goog_handler.df.to_csv(
                    f"out/{self._airline}/data_all_external.csv",
                    index=False,
                )

            # -----------------
            # export per-segment cocip outputs
            # -----------------
            for ix, seg_df in enumerate(case_study_dfs):
                seg_df_fn = self.EXPORT_FLIGHT_COCIP_SEGS_FILENAME_TEMPLATE.format(
                    airline=self._airline,
                    ix=ix,
                )
                seg_df.to_csv(seg_df_fn, index=False)

                # -----------------
                # export case study plots
                # -----------------
                df_plt = seg_df.copy(deep=True)
                df_plt.sort_values(["time_start"], inplace=True)
                df_plt.reset_index(inplace=True, drop=True)
                df_plt.loc[:, "dist_cum_km"] = df_plt["chunk_len_km"].cumsum()

                fig = plt.figure(figsize=(7, 2))
                ax = fig.add_subplot(1, 1, 1)

                x_v = df_plt["dist_cum_km"]
                y_v = df_plt["median_altitude_ft"] / 100.0

                min_x = -100
                max_x = df_plt["dist_cum_km"].max() + 100
                min_y = y_v.min() - 10
                max_y = y_v.max() + 45

                x_contrails_pred = x_v[df_plt["sum_ef_mj"] != 0]
                y_contrails_pred = y_v[df_plt["sum_ef_mj"] != 0]

                x_contrails_attr = x_v[df_plt["goog_is_attributed"] != 0]
                y_contrails_attr = y_v[df_plt["goog_is_attributed"] != 0]

                x_conus_min = df_plt[df_plt["in_conus"]]["dist_cum_km"].min()
                x_conus_max = df_plt[df_plt["in_conus"]]["dist_cum_km"].max()

                conus_patch = plt.Rectangle(
                    (x_conus_min, min_y),
                    x_conus_max - x_conus_min,
                    max_y - min_y,
                    alpha=0.4,
                    facecolor="#F7CA45",
                )
                ax.add_patch(conus_patch)

                ax.scatter(
                    x_contrails_pred,
                    y_contrails_pred,
                    color="#D3E3FD",
                    s=1000,
                )
                ax.scatter(
                    x_contrails_attr,
                    y_contrails_attr,
                    color="#F7CA45",
                    s=400,
                )
                ax.plot(
                    x_v,
                    y_v,
                    color="black",
                    linewidth=2.5,
                )

                title_str = "{origin}-{dest} {date}".format(
                    origin=df_plt.iloc[0]["departure_airport_iata"],
                    dest=df_plt.iloc[0]["arrival_airport_iata"],
                    date=df_plt.iloc[0]["time_start_local_date"].strftime("%B %d, %Y"),
                )
                ax.set_title(title_str, loc="left", fontname="Roboto")
                ax.grid(axis="y", linewidth=1.5, linestyle="dotted", color="#C4C7C5")

                ax.spines["top"].set_visible(False)
                ax.spines["right"].set_visible(False)
                ax.spines["left"].set_visible(False)
                ax.spines["bottom"].set_color("#C4C7C5")
                ax.spines["bottom"].set_linewidth(5)

                x_range = list(np.arange(0, 20000, 1000))
                x_range_labels = [f"{i:,}km" for i in x_range]
                ax.set_xticks(x_range, labels=x_range_labels, rotation=90)

                y_range = list(np.arange(100, 500, 50))
                y_range_labels = [f"FL{i}" for i in y_range]
                ax.set_yticks(y_range, labels=y_range_labels)

                ax.set_xlim([min_x, max_x])
                ax.set_ylim([min_y, max_y])

                legend_elements = [
                    lines.Line2D(
                        [0], [0], color="black", linewidth=2.5, label="Flight path"
                    ),
                    lines.Line2D(
                        [0],
                        [0],
                        marker="o",
                        color="w",
                        markerfacecolor="#D3E3FD",
                        markersize=15,
                        label="Predicted contrails",
                    ),
                    lines.Line2D(
                        [0],
                        [0],
                        marker="o",
                        color="w",
                        markerfacecolor="#F7CA45",
                        markersize=15,
                        label="Confirmed contrails",
                    ),
                    patches.Rectangle(
                        (0, 0),
                        1,
                        1,
                        facecolor="#F7CA45",
                        alpha=0.4,
                        label="Observation region",
                    ),
                ]

                ax.legend(
                    handles=legend_elements,
                    loc="upper center",
                    bbox_to_anchor=(0.5, -0.5),
                    ncol=4,
                    frameon=False,
                )

                plt.savefig(
                    self.EXPORT_FLIGHT_CASE_STUDY_FIG_TEMPLATE.format(
                        airline=self._airline,
                        ix=ix,
                    ),
                    dpi=300,
                    bbox_inches="tight",
                )

            # -----------------
            # export map w/ all trajectories
            # -----------------
            projection = ccrs.Mercator(
                central_longitude=12, min_latitude=-56.9, max_latitude=84.0
            )
            fig = plt.figure(
                figsize=(10, 7)
            )  # Increased height slightly to accommodate legend
            ax = fig.add_subplot(1, 1, 1, projection=projection)
            ax.set_global()
            ax.add_feature(cfeature.LAND, color="#C4C7C5")
            ax.fill(
                [c[0] for c in self.CONUS_COORDS],
                [c[1] for c in self.CONUS_COORDS],
                facecolor="#F7CA45",
                edgecolor="#F7CA45",
                linewidth=1.0,
                alpha=0.5,
                transform=ccrs.Geodetic(),
            )
            for ix, row in summary_df.iterrows():
                plt.plot(
                    [row.lon_start, row.lon_end],
                    [row.lat_start, row.lat_end],
                    color="black",
                    alpha=0.3,
                    linewidth=0.3,
                    transform=ccrs.Geodetic(),
                )

            legend_elements = [
                patches.Rectangle(
                    (0, 0),
                    1,
                    1,
                    facecolor="#F7CA45",
                    alpha=0.5,
                    label="Satellite verified region",
                ),
                patches.Rectangle(
                    (0, 0),
                    1,
                    1,
                    facecolor="#C4C7C5",
                    label="Algorithm predictions only",
                ),
                lines.Line2D(
                    [0], [0], color="black", linewidth=1, label="Flight paths"
                ),
            ]

            # Add legend
            ax.legend(
                handles=legend_elements,
                loc="lower center",
                bbox_to_anchor=(0.5, -0.1),
                ncol=3,
                frameon=False,
                fontsize=14,
            )

            ax.set_xticks([])
            ax.set_yticks([])
            for spine in ax.spines.values():
                spine.set_visible(False)

            plt.savefig(
                self.EXPORT_FLIGHTS_TRAJ_PLOT_FILENAME_TEMPLATE.format(
                    airline=self._airline
                ),
                bbox_inches="tight",  # This ensures the legend is not cut off
                dpi=300,
            )

            # -----------------
            # export OD-pair histogram
            # -----------------

            # remove None-None OD-pair from consideration
            # (case where origin/destination airport code not reported in Spire)
            od_pruned = []
            for itm in summary["od_pairs"]:
                od = itm["airport_iata_od"]
                o = od.split("_")[0]
                d = od.split("_")[0]
                if o == "None" or d == "None":
                    continue
                od_pruned.append(itm)

            # ----------------------------------
            # BY IMPACT DENSITY
            # ----------------------------------
            od_pruned.sort(
                key=lambda i: i["impact_density_co2e_metric_tons_per_dist_km"],
                reverse=True,
            )
            top_ods_by_impact_density = od_pruned[:10]

            fig_w = 9  # inch
            fig_h = 4  # inch

            fig = plt.figure()
            ax = fig.add_subplot(1, 1, 1)

            impact_kgco2e_per_km = [
                int(itm["impact_density_co2e_metric_tons_per_dist_km"] * 1000)
                for itm in top_ods_by_impact_density
            ]
            grp_names = [
                itm["airport_iata_od"].replace("_", " - ")
                for itm in top_ods_by_impact_density
            ]

            impact_kgco2e_per_km.reverse()
            grp_names.reverse()
            # Plot the stacked bars
            bar = ax.barh(grp_names, impact_kgco2e_per_km, color="#2C2857", zorder=2)

            max_x = max([int(itm) for itm in impact_kgco2e_per_km])
            x_range = list(np.arange(0, max_x + 20, 10))
            x_range_labels = [f"{i:,}kg CO2e/km" for i in x_range]
            ax.set_xticks(x_range, labels=x_range_labels)

            ax.xaxis.set_minor_locator(MultipleLocator(2))
            ax.grid(
                axis="x",
                which="minor",
                linewidth=1.5,
                linestyle="dotted",
                color="#C4C7C5",
                zorder=0,
            )
            ax.grid(
                axis="x",
                which="major",
                linewidth=1.5,
                linestyle="dotted",
                color="#C4C7C5",
                zorder=0,
            )

            for ix, bar in enumerate(bar):
                label_text = f"{impact_kgco2e_per_km[ix]}kg CO2e/km"
                ax.text(
                    bar.get_width() + 1,
                    bar.get_y() + bar.get_height() / 2,
                    label_text,
                    ha="left",
                    va="center",
                    color="black",
                )

            ax.spines["top"].set_visible(False)
            ax.spines["right"].set_visible(False)
            ax.spines["left"].set_visible(False)
            ax.spines["bottom"].set_color("#C4C7C5")
            ax.spines["bottom"].set_linewidth(5)

            # title_str = "OD Pairs"
            # ax.set_title(title_str, x=-0.05)
            ax = plt.gca()
            lf = ax.figure.subplotpars.left
            r = ax.figure.subplotpars.right
            t = ax.figure.subplotpars.top
            b = ax.figure.subplotpars.bottom
            figw = float(fig_w) / (r - lf)
            figh = float(fig_h) / (t - b)
            ax.figure.set_size_inches(figw, figh)

            plt.savefig(
                self.EXPORT_FLIGHTS_OD_IMPACT_DENSITY_PLOT_FILENAME_TEMPLATE.format(
                    airline=self._airline,
                )
            )

            # ----------------------------------
            # BY NET CO2e
            # ----------------------------------
            od_pruned.sort(key=lambda itm: itm["co2e50_metric_tons"], reverse=True)

            top_ods_by_net_co2e = od_pruned[:10]

            fig_w = 9  # inch
            fig_h = 4  # inch
            fig = plt.figure()
            ax = fig.add_subplot(1, 1, 1)

            night_co2e_grp = [
                int(
                    itm["co2e50_metric_tons"]
                    * min(itm["percentage_nighttime_co2e"], 100)
                    / 100
                )
                for itm in top_ods_by_net_co2e
            ]
            day_co2e_grp = [
                int(
                    itm["co2e50_metric_tons"]
                    * (100 - min(itm["percentage_nighttime_co2e"], 100))
                    / 100
                )
                for itm in top_ods_by_net_co2e
            ]
            impact_kgco2e_per_km = [
                int(itm["impact_density_co2e_metric_tons_per_dist_km"] * 1000)
                for itm in top_ods_by_net_co2e
            ]
            flight_count = [itm["flight_count"] for itm in top_ods_by_net_co2e]
            flight_dist_km = [
                round(int(itm["tot_dist_km"]), -2) for itm in top_ods_by_net_co2e
            ]
            grp_names = [
                itm["airport_iata_od"].replace("_", " - ")
                for itm in top_ods_by_net_co2e
            ]

            night_co2e_grp.reverse()
            day_co2e_grp.reverse()
            impact_kgco2e_per_km.reverse()
            flight_count.reverse()
            grp_names.reverse()

            # Plot the stacked bars
            night_bar = ax.barh(grp_names, night_co2e_grp, color="#2C2857", zorder=2)
            day_bar = ax.barh(
                grp_names, day_co2e_grp, left=night_co2e_grp, color="#F7CA45", zorder=2
            )

            max_co2e = max(
                [int(itm["co2e50_metric_tons"]) for itm in top_ods_by_net_co2e]
            )
            x_range = list(np.arange(0, max_co2e + 1000, 1000))
            x_range_labels = [f"{i:,}t CO2e" for i in x_range]
            ax.set_xticks(x_range, labels=x_range_labels)

            ax.xaxis.set_minor_locator(MultipleLocator(200))
            ax.grid(
                axis="x",
                which="minor",
                linewidth=1.5,
                linestyle="dotted",
                color="#C4C7C5",
                zorder=0,
            )
            ax.grid(
                axis="x",
                which="major",
                linewidth=1.5,
                linestyle="dotted",
                color="#C4C7C5",
                zorder=0,
            )

            # set flight count inline text
            for ix, bar in enumerate(night_bar):
                label_text = f"{flight_count[ix]} Flights"
                ax.text(
                    25,
                    bar.get_y() + bar.get_height() / 2,
                    label_text,
                    ha="left",
                    va="center",
                    color="white",
                )

            # set flight distance km inline text
            for ix, bar in enumerate(night_bar):
                label_text = f"{flight_dist_km[ix]:,} km"
                ax.text(
                    400,
                    bar.get_y() + bar.get_height() / 2,
                    label_text,
                    ha="left",
                    va="center",
                    color="white",
                )

            # set total co2e inline text
            for ix, bars in enumerate(zip(night_bar, day_bar)):
                total_co2e = int(night_co2e_grp[ix] + day_co2e_grp[ix])
                label_text = f"{total_co2e:,}t CO2e"
                ax.text(
                    bars[0].get_width() + bars[1].get_width() + 40,
                    bars[0].get_y() + bars[0].get_height() / 2,
                    label_text,
                    ha="left",
                    va="center",
                    color="black",
                )

            # set impact density on RHS of axes
            ax_offset = 4030
            cmap = cm.get_cmap("hot")
            c_min = min(impact_kgco2e_per_km)
            c_max = max(impact_kgco2e_per_km)
            c_offset = (c_max - c_min) / 2
            norm = plt.Normalize(c_min, c_max + 3 * c_offset)
            colors = cmap(norm(impact_kgco2e_per_km))
            for ix, bar in enumerate(night_bar):
                label_text = f"{impact_kgco2e_per_km[ix]}kg CO2e/km"
                ax.text(
                    ax_offset,
                    bar.get_y() + bar.get_height() / 2,
                    label_text,
                    ha="left",
                    va="center",
                    color=colors[ix],
                )

            ax.spines["top"].set_visible(False)
            ax.spines["right"].set_visible(False)
            ax.spines["left"].set_visible(False)
            ax.spines["bottom"].set_color("#C4C7C5")
            ax.spines["bottom"].set_linewidth(5)

            # title_str = "OD Pairs"
            # ax.set_title(title_str, x=-0.05)

            ax = plt.gca()
            lf = ax.figure.subplotpars.left
            r = ax.figure.subplotpars.right
            t = ax.figure.subplotpars.top
            b = ax.figure.subplotpars.bottom
            figw = float(fig_w) / (r - lf)
            figh = float(fig_h) / (t - b)
            ax.figure.set_size_inches(figw, figh)
            plt.savefig(
                self.EXPORT_FLIGHTS_OD_NET_CO2E_PLOT_FILENAME_TEMPLATE.format(
                    airline=self._airline,
                )
            )

            # -----------------
            # Fuel emissions vs contrail warming horizontal bar chart
            # -----------------

            fig_w = 8  # inch
            fig_h = 3  # inch
            fig = plt.figure(figsize=(fig_w, fig_h))
            ax = fig.add_subplot(1, 1, 1)

            total = total_co2_metric_tons + total_contrails_co2e50_metric_tons
            normalized_values = [
                v / total
                for v in [total_co2_metric_tons, total_contrails_co2e50_metric_tons]
            ]
            colors = ["#1967D2", "#4285F4"]

            left = 0
            for value, color in zip(normalized_values, colors):
                ax.barh("Tons warming", value, color=color, left=left)
                left += value

            ax.xaxis.set_visible(False)
            ax.yaxis.set_visible(False)
            ax.spines["top"].set_visible(False)
            ax.spines["right"].set_visible(False)
            ax.spines["left"].set_visible(False)
            ax.spines["bottom"].set_visible(False)

            plt.subplots_adjust(left=0.01, right=1.04, top=0.99, bottom=0.01)
            plt.savefig(
                self.EXPORT_FLIGHTS_FUEL_EMISSIONS_VS_CONTRAIL_WARMING_PLOT_FILENAME_TEMPLATE.format(
                    airline=self._airline,
                )
            )

            # -----------------
            # Contrail warming daytime vs nighttime horizontal bar chart
            # -----------------

            fig_w = 8
            fig_h = 3
            fig = plt.figure(figsize=(fig_w, fig_h))
            ax = fig.add_subplot(1, 1, 1)

            # Calculate total and normalize values
            total = (
                total_nighttime_contrails_co2e50_metric_tons
                + total_daytime_contrails_co2e50_metric_tons
            )
            normalized_values = [
                v / total
                for v in [
                    total_nighttime_contrails_co2e50_metric_tons,
                    total_daytime_contrails_co2e50_metric_tons,
                ]
            ]
            colors = ["#2C2857", "#F7CA45"]

            left = 0
            for value, color in zip(normalized_values, colors):
                ax.barh("Tons warming", value, color=color, left=left)
                left += value

            ax.xaxis.set_visible(False)
            ax.yaxis.set_visible(False)
            ax.spines["top"].set_visible(False)
            ax.spines["right"].set_visible(False)
            ax.spines["left"].set_visible(False)
            ax.spines["bottom"].set_visible(False)

            plt.subplots_adjust(left=0.01, right=1.04, top=0.99, bottom=0.01)
            plt.savefig(
                self.EXPORT_FLIGHTS_CONTRAIL_WARMING_DAYTIME_VS_NIGHTTIME_PLOT_FILENAME_TEMPLATE.format(
                    airline=self._airline,
                )
            )

            # -----------------
            # What percentage of flights create warming contrails?
            # -----------------
            fig = plt.figure(figsize=(5, 5))
            ax = fig.add_subplot(1, 1, 1)
            percent_with_warming = round(percentage_flight_dist_w_warming_contrails, 1)
            percent_without_warming = 100 - percent_with_warming

            colors = ["#4285F4", "#D3E3FD"]

            ax.pie(
                [percent_with_warming, percent_without_warming],
                labels=["", ""],
                startangle=90,
                counterclock=False,
                colors=colors,
                wedgeprops={"width": 0.15},
            )

            ax.set_aspect("equal")  # Ensures the pie chart is circular

            legend_colors = [
                plt.Line2D(
                    [0],
                    [0],
                    marker="o",
                    color="w",
                    markerfacecolor=color,
                    markersize=15,
                )
                for color in colors
            ]
            legend_labels = [
                "Distance with warming contrails",
                "Distance without warming contrails",
            ]

            plt.legend(
                handles=legend_colors,
                labels=legend_labels,
                loc="lower center",
                bbox_to_anchor=(0.5, -0.15),
                ncol=1,
                frameon=False,
                labelspacing=1.0,
                fontsize=16,
            )
            ax.xaxis.set_visible(False)
            ax.yaxis.set_visible(False)
            ax.spines["top"].set_visible(False)
            ax.spines["right"].set_visible(False)
            ax.spines["left"].set_visible(False)
            ax.spines["bottom"].set_visible(False)

            plt.subplots_adjust(left=0.01, right=1.04, top=0.99)
            plt.savefig(
                self.EXPORT_FLIGHTS_CONTRAIL_WARMING_PERCENTAGE_FILENAME_TEMPLATE.format(
                    airline=self._airline,
                ),
                bbox_inches="tight",
            )

        # -----------------
        # How many flight kilometers total, by daytime and nighttime?
        # -----------------

        # Common settings for both plots
        bar_height = 0.3
        y_position = 0.5
        text_fontsize = 16
        colors = ["#2C2857", "#F7CA45"]

        # Use same subplot settings for both plots
        plot_settings = {
            "left": 0.01,
            "right": 0.95,
            "top": 0.99,
            "bottom": 0.2,  # Same bottom margin for both plots
        }

        # First plot (all contrails)
        fig, ax = plt.subplots(figsize=(4, 1))
        left = 0

        bar_height = 0.3
        y_position = 0.5
        total_distance = (
            total_nighttime_contrail_distance_km + total_daytime_contrail_distance_km
        )
        night_percent = round(
            (total_nighttime_contrail_distance_km / total_distance) * 100
        )
        day_percent = round((total_daytime_contrail_distance_km / total_distance) * 100)

        ax.barh(
            y_position,
            total_nighttime_contrail_distance_km,
            height=bar_height,
            color=colors[0],
            left=left,
        )
        margin = total_distance / 20
        y_margin = y_position * 0.96
        ax.text(
            margin,
            y_margin,
            f"{night_percent}%",
            color="white",
            ha="left",
            va="center",
            fontsize=text_fontsize,
        )
        left += total_nighttime_contrail_distance_km

        ax.barh(
            y_position,
            total_daytime_contrail_distance_km,
            height=bar_height,
            color=colors[1],
            left=left,
        )
        ax.text(
            left + margin,
            y_margin,
            f"{day_percent}%",
            color="black",
            ha="left",
            va="center",
            fontsize=text_fontsize,
        )

        ax.set_ylim(0, 1)

        ax.xaxis.set_visible(False)
        ax.yaxis.set_visible(False)
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)
        ax.spines["left"].set_visible(False)
        ax.spines["bottom"].set_visible(False)

        plt.subplots_adjust(**plot_settings)

        plt.savefig(
            self.EXPORT_FLIGHTS_CONTRAIL_DISTANCE_DAYTIME_NIGHTTIME_FILENAME_TEMPLATE.format(
                airline=self._airline,
            ),
            bbox_inches="tight",
        )

        # -----------------
        # How many flight kilometers of warming contrails?
        # -----------------

        colors = ["#2C2857", "#F7CA45"]
        fig, ax = plt.subplots(figsize=(3, 1))
        left = 0

        bar_height = 0.3
        y_position = 0.5

        total_distance = (
            total_nighttime_warming_contrail_distance_km
            + total_daytime_warming_contrail_distance_km
        )
        night_percent = round(
            (total_nighttime_warming_contrail_distance_km / total_distance) * 100
        )
        day_percent = round(
            (total_daytime_warming_contrail_distance_km / total_distance) * 100
        )

        ax.barh(
            y_position,
            total_nighttime_warming_contrail_distance_km,
            height=bar_height
            * 1,  # Add multiplier if we want to make it taller per Joachim's comment..
            color=colors[0],
            left=left,
        )
        margin = total_distance / 20
        y_margin = y_position * 0.96
        ax.text(
            margin,
            y_margin,
            f"{night_percent}%",
            color="white",
            ha="left",
            va="center",
            fontsize=text_fontsize,
        )
        left += total_nighttime_warming_contrail_distance_km

        ax.barh(
            y_position,
            total_daytime_warming_contrail_distance_km,
            height=bar_height,
            color=colors[1],
            left=left,
        )
        ax.text(
            left + total_daytime_warming_contrail_distance_km + margin,
            y_margin,
            f"{day_percent}%",
            color="black",
            ha="left",
            va="center",
            fontsize=text_fontsize,
        )

        ax.set_ylim(0, 1)

        legend_colors = [
            plt.Line2D(
                [0], [0], marker="o", color="w", markerfacecolor=color, markersize=10
            )
            for color in colors
        ]
        legend_labels = ["Nighttime", "Daytime"]
        plt.legend(
            handles=legend_colors,
            labels=legend_labels,
            loc="lower left",
            bbox_to_anchor=(0, -0.2),
            ncol=2,
            frameon=False,
            fontsize=16,
        )
        ax.xaxis.set_visible(False)
        ax.yaxis.set_visible(False)
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)
        ax.spines["left"].set_visible(False)
        ax.spines["bottom"].set_visible(False)
        plt.subplots_adjust(**plot_settings)

        plt.savefig(
            self.EXPORT_FLIGHTS_CONTRAIL_DISTANCE_WARMING_DAYTIME_NIGHTTIME_FILENAME_TEMPLATE.format(
                airline=self._airline,
            ),
            bbox_inches="tight",
        )

        logger.info("🙌 DONE!")

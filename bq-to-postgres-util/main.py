#!/usr/bin/env python3
"""Utility to load trajectory cocip Parquet shards from GCS and write them to Postgres."""

from datetime import date, datetime, timedelta
from dateutil.relativedelta import relativedelta
import io
from lib.log import logger
import sys
from typing import Iterator

from argparse import ArgumentParser
import pandas as pd
import numpy as np
from google.cloud import storage
from sqlalchemy import URL, and_, create_engine, func, select, table, text, column
from sqlalchemy.dialects.postgresql import insert
from tqdm import tqdm
import psycopg2  # noqa: F401

from geography import (
    airport_icao_to_iso_continent,
    airport_icao_to_iso_country,
    is_eu_mrv,
)

TRAJECTORY_TABLE_NAME = "trajectory-cocip"
TRAJECTORY_TABLE = table(
    TRAJECTORY_TABLE_NAME, column("flight_id"), column("time_start")
)
TRAJECTORY_META_TABLE_NAME = "trajectory-cocip-meta"
TRAJECTORY_HISTOGRAM_IMPACT_TABLE_NAME = "inventory_monthly_impact_histogram"

CO2E_IMPACT_BINS = ["no_impact", "low_impact", "medium_impact", "high_impact"]


def get_db_uri(
    db_host: str, port: int, db_socket_instance: str, user: str, password: str
):
    """Prioritizes TCP (DB_HOST) if set, otherwise falls back to Cloud SQL Unix Sockets."""
    assert (
        db_host or db_socket_instance
    ), "Either a host IP or a socket instance name need to be specified!"

    common_params = {
        "drivername": "postgresql+psycopg",
        "username": user,
        "password": password,
        "database": "flights-pipeline-fer-cache",
    }

    if db_host:
        logger.info("connecting", extra={"method": "TCP", "host": db_host, "port": port})
        return URL.create(**common_params, host=db_host, port=port)
    else:
        socket_host_url = f"/cloudsql/contrails-301217:us-east1:{db_socket_instance}"
        logger.info("connecting", extra={"method": "Unix Socket", "host": socket_host_url, "port": port})
        return URL.create(
            **common_params, query={"host": socket_host_url, "port": str(port)}
        )


def extract_year_quarter_range(year_quarter_str: str) -> tuple[date, date]:
    """Extracts the date range of YYYY(Q1-4) with an inclusive start and exclusive end date."""
    if not year_quarter_str:
        raise Exception("Year quarter cannot be empty!")

    if not "Q" in year_quarter_str:  # noqa: E713
        year = int(year_quarter_str.strip())
        year_quarter_start = date(year, 1, 1)
        year_quarter_end = date(year + 1, 1, 1)
    else:
        period = pd.Period(year_quarter_str, freq="Q")
        year_quarter_start = period.start_time.date()
        year_quarter_end = period.end_time.date() + timedelta(days=1)

    if year_quarter_start < year_quarter_end < date(2000, 1, 1):
        raise Exception(
            f"Invalid old year detected prior to 2000. Got {year_quarter_str}"
        )
    return year_quarter_start, year_quarter_end


def add_is_eu_mrv_column(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    vect_is_eu_mrv = np.vectorize(is_eu_mrv)
    df = df.assign(
        is_eu_mrv=vect_is_eu_mrv(
            df["departure_airport_icao"], df["arrival_airport_icao"]
        ),
    )
    return df


class DataTransformer:
    """Transforms data from the Parquet input format to the Postgres output format."""

    def __init__(
        self,
        table_name: str,
        requires_upsert: bool,
        is_partitioned: bool,
        schema: str = "public",
    ) -> None:
        self.schema = schema
        self.table_name = table_name
        self.is_partitioned = is_partitioned
        self.requires_upsert = requires_upsert

    def parquet_data_to_postgres(self, df: pd.DataFrame) -> pd.DataFrame:
        raise NotImplementedError()

    def on_conflict_do_update(self, target_table, stmt_excluded):
        raise NotImplementedError()


class GcsPathReader:
    def __init__(self, bucket_name: str, paths: str):
        self.bucket_name = bucket_name
        self.paths = [p.rstrip("/") for p in paths.split(",")]
        self.storage_client = storage.Client()
        self.bucket = self.storage_client.bucket(self.bucket_name)

    def _extract_date_range_process_time(self, path: str) -> tuple[date, date, date]:
        """Extracts the following from the path: [date range start date, date range end date, process date]"""
        parts = path.split("/")
        if len(parts) < 2:
            raise Exception(
                "Paths need to be in the format a/b/.../<year><optional Q1-4>"
                f"/<process date YYYYMMDD>. But got {path}."
            )
        year_quarter_str, process_time_str = parts[-2], parts[-1]
        start_date, end_date = extract_year_quarter_range(year_quarter_str)
        parse_date = datetime.strptime(process_time_str, "%Y%m%d").date()
        if parse_date < date(2025, 1, 1) or parse_date > date.today():
            raise Exception(
                f"Invalid process date detected. Expected recent YYYYMMDD but got {parse_date}."
            )

        return start_date, end_date, parse_date

    def date_ranges(self) -> Iterator[tuple[date, date]]:
        for path in self.paths:
            start_date, end_date, _ = self._extract_date_range_process_time(path)
            yield start_date, end_date

    def find_valid_paths(self) -> Iterator[str]:
        # Valid paths are of the format: a/b/.../<year><optional Q1-4>/<process time YYYYMMDD>
        for path in self.paths:
            _, _, _ = self._extract_date_range_process_time(path)
            yield path

    def parquet_files(self) -> Iterator[storage.Blob]:
        for path in self.find_valid_paths():
            blobs = self.storage_client.list_blobs(self.bucket_name, prefix=path)
            parquet_shards = [b for b in blobs if b.name.endswith(".pq")]
            logger.info("found parquet shards", extra={"count": len(parquet_shards), "path": path})
            if not parquet_shards:
                logger.warning("skipping", extra={"reason": f"No parquet shards found in {path}."})
            yield from parquet_shards


class GcsToPostgresLoader:
    def __init__(
        self, data_transformers: list[DataTransformer], db_uri: str  #  noqa: F821
    ):  # noqa: F821
        self.engine = create_engine(db_uri)
        self.data_transformers = data_transformers

    def ensure_partitions_exist(self, start_incl: date, end_excl: date) -> None:
        current = start_incl.replace(day=1)
        while current < end_excl:
            next_month = current + relativedelta(months=1)

            suffix = current.strftime("%Y_%m")
            start_str = current.strftime("%Y-%m-%d")
            end_str = next_month.strftime("%Y-%m-%d")

            with self.engine.connect() as conn:
                for data_transformer in self.data_transformers:
                    if not data_transformer.is_partitioned:
                        continue
                    logger.debug(
                        "ensuring partition exists",
                        extra={
                            "table": data_transformer.table_name,
                            "suffix": suffix,
                            "date_range": (start_str, end_str)
                        }
                    )
                    conn.execute(
                        text(
                            f"""
                        CREATE TABLE IF NOT EXISTS "{data_transformer.table_name}_{suffix}"
                        PARTITION OF "{data_transformer.table_name}"
                        FOR VALUES FROM ('{start_str}') TO ('{end_str}');
                    """
                        )
                    )
                    conn.commit()

            current = next_month

    def assert_no_data(self, start_incl: date, end_excl: date) -> None:
        """Ensure that there is no data currently within the specified date range: [start_incl, end_excl)."""
        logger.debug("checking for existing data", extra={"date_range": (start_incl, end_excl)})
        stmt = select(
            func.count(TRAJECTORY_TABLE.c.flight_id).label("flight_cnt")
        ).where(
            and_(
                TRAJECTORY_TABLE.c.time_start >= start_incl,
                TRAJECTORY_TABLE.c.time_start < end_excl,
            )
        )
        with self.engine.connect() as conn:
            count = conn.scalar(stmt)
            if count > 0:
                raise Exception(
                    f"There is flights data present in [{start_incl}, {end_excl})."
                    " Please delete it first."
                )
        logger.debug("no existing data found", extra={"date_range": (start_incl, end_excl)})

    def _read_parquet_blob(self, blob: storage.Blob) -> pd.DataFrame:
        data = blob.download_as_bytes()
        return pd.read_parquet(io.BytesIO(data))

    def _upload_to_postgres(
        self, df: pd.DataFrame, table_name: str, schema: str
    ) -> None:
        """Uploads a pandas DataFrame to Postgres using the efficient COPY command."""

        connection = self.engine.raw_connection()

        # Write dataframe to buffer to then copy the entire buffer to Postgres.
        buffer = io.StringIO()
        df.to_csv(buffer, sep="\t", header=False, index=False)
        buffer.seek(0)

        try:
            full_table_name = f'"{schema}"."{table_name}"'
            copy_stmt = f"COPY {full_table_name} FROM STDIN WITH (FORMAT CSV, DELIMITER '\t', NULL '')"
            with connection.cursor() as cur:
                with cur.copy(copy_stmt) as copy:
                    copy.write(buffer.getvalue())

            connection.commit()
        except Exception as e:
            connection.rollback()
            logger.error("error", extra={"reason": "failed to upload data", "count": len(df), "table": f"{schema}.{table_name}", "error": e})
            raise
        finally:
            connection.close()

    def _upload_via_upsert(
        self,
        df: pd.DataFrame,
        data_transformer: DataTransformer,
        table_name: str,
        schema: str,
    ) -> None:
        """Uploads a pandas DataFrame to Postgres using the INSERT ... ON CONFLICT DO UPDATE command."""

        records = df.to_dict(orient="records")

        # Define the table object dynamically for SQLAlchemy
        target_table = table(
            table_name, *[column(c) for c in df.columns], schema=schema
        )

        # Postgres limits the number of parameters to around 64k per request.
        # Send the data in small enough chunks.
        chunk_size = 30_000 // len(df.columns)

        total_conflicts = 0
        for i in range(0, len(records), chunk_size):
            chunk = records[i : i + chunk_size]
            stmt = insert(target_table).values(chunk)
            index_elements, set_args = data_transformer.on_conflict_do_update(
                target_table, stmt.excluded
            )
            stmt = stmt.on_conflict_do_update(
                index_elements=index_elements, set_=set_args
            )
            # Use xmax to detect conflicts: xmax=0 means new insert, non-zero means update.
            stmt_with_returning = stmt.returning(text("(xmax != 0)::int AS was_updated"))

            with self.engine.begin() as conn:
                result = conn.execute(stmt_with_returning)
                rows = result.fetchall()

            conflict_count = sum(r[0] for r in rows)
            total_conflicts += conflict_count

        if total_conflicts > 0:
            logger.info( "upserted", extra={ "detail": "updated existing records (conflicts resolved via ON CONFLICT DO UPDATE).", "conflicts": total_conflicts, "total_records": len(records), "table": f"{schema}.{table_name}" })

    def to_postgres(self, blob: storage.Blob) -> None:
        try:
            df = self._read_parquet_blob(blob)
            if df.empty:
                logger.warning("skipped", extra={"reason": "empty parquet file", "file": blob.name})
                return

            for data_transformer in self.data_transformers:
                df_table_data = data_transformer.parquet_data_to_postgres(df)
                table_name = data_transformer.table_name
                schema = data_transformer.schema
                if df_table_data.empty:
                    continue
                if data_transformer.requires_upsert:
                    self._upload_via_upsert(
                        df_table_data, data_transformer, table_name, schema
                    )
                else:
                    self._upload_to_postgres(df_table_data, table_name, schema)

            logger.info("completed", extra={"file": blob.name, "row_count": len(df)})
        except Exception as e:
            logger.error("error", extra={"file": blob.name, "error": e}, exc_info=True)
            raise


class MainTableDataTransformer(DataTransformer):
    """Transforms data from the Parquet input format to the Postgres output format for the main table."""

    def __init__(self, table_name: str) -> None:
        super().__init__(table_name, requires_upsert=False, is_partitioned=True)

    def parquet_data_to_postgres(self, df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()

        df.loc[:, "time_start"] = pd.to_datetime(df["time_start"])
        df.loc[:, "time_end"] = pd.to_datetime(df["time_end"])

        df = df.replace("None", np.nan)

        ef_mj_per_km = (
            df["sum_ef_mj"].div(df["chunk_len_km"].replace(0, np.nan)).astype(float)
        )

        duration_seconds = (df["time_end"] - df["time_start"]).dt.total_seconds()
        flight_length_bucket = np.where(
            duration_seconds < 3.5 * 60 * 60, "short_flight", "long_flight"
        )

        co2e_kg_bucket = pd.cut(
            df["sum_ef_mj"],
            # Buckets computed from CO2e GWP100 thresholds [0.0, 800.0, 7500.0]
            bins=[-np.inf, 0, 2696406.1, 25278807.1, np.inf],
            labels=CO2E_IMPACT_BINS,
            right=True,  # ensures that every bin is (start, end]
            include_lowest=True,
        ).astype(str)

        co2e_kg_per_km_bucket = pd.cut(
            ef_mj_per_km,
            # Buckets computed from CO2e GWP100 thresholds [0.0, 2.8, 70.0]
            bins=[-np.inf, 0, 9437.4, 235935.5, np.inf],
            labels=CO2E_IMPACT_BINS,
            right=True,  # ensures that every bin is (start, end]
            include_lowest=True,
        ).astype(str)

        departure_country_iso = df["departure_airport_icao"].map(airport_icao_to_iso_country)
        departure_continent_iso = df["departure_airport_icao"].map(airport_icao_to_iso_continent)
        arrival_country_iso = df["arrival_airport_icao"].map(airport_icao_to_iso_country)
        arrival_continent_iso = df["arrival_airport_icao"].map(airport_icao_to_iso_continent)

        # Log any airport ICAO codes that could not be mapped to a country or continent.
        missing_dep = df["departure_airport_icao"][departure_country_iso.isna()].dropna().unique()
        if len(missing_dep) > 0:
            logger.info(
                "missing country/continent lookup", extra={"detail": "Rows will have NULL country/continent fields.", "affected_rows": len(missing_dep), "departure_airports": sorted(missing_dep.tolist())}
            )
        missing_arr = df["arrival_airport_icao"][arrival_country_iso.isna()].dropna().unique()
        if len(missing_arr) > 0:
            logger.info(
                "missing country/continent lookup", extra={"detail": "Rows will have NULL country/continent fields.", "affected_rows": len(missing_arr), "arrival_airports": sorted(missing_arr.tolist())}
            )

        df = df.assign(
            chunk_len_km=df["chunk_len_km"].astype(int),
            mean_aircraft_mass_kg=df["mean_aircraft_mass_kg"].astype(int),
            contrail_generating_kms=df["contrail_generating_kms"].astype(int),
            warming_contrail_generating_kms=df["total_pos_ef_persistent_contrail_length_km"].astype(int),
            ef_mj_per_km=ef_mj_per_km,
            flight_length_bucket=flight_length_bucket,
            co2e_kg_bucket=co2e_kg_bucket,
            co2e_kg_per_km_bucket=co2e_kg_per_km_bucket,
            departure_country_iso=departure_country_iso,
            departure_continent_iso=departure_continent_iso,
            arrival_country_iso=arrival_country_iso,
            arrival_continent_iso=arrival_continent_iso,
        )
        df = add_is_eu_mrv_column(df)
        features = [
            "chunk_len_km",
            "lat_start",
            "lon_start",
            "lat_end",
            "lon_end",
            "time_start",
            "time_end",
            "sum_ef_mj",
            "ef_mj_per_km",
            "contrail_generating_kms",
            "warming_contrail_generating_kms",
            "aircraft_type_icao",
            "engine_uid",
            "mean_aircraft_mass_kg",
            "mean_overall_efficiency",
            "icao_address",
            "flight_id",
            "callsign",
            "tail_number",
            "flight_number",
            "airline_iata",
            "departure_airport_icao",
            "departure_country_iso",
            "departure_continent_iso",
            "arrival_airport_icao",
            "arrival_country_iso",
            "arrival_continent_iso",
            "is_eu_mrv",
            "flight_length_bucket",
            "co2e_kg_bucket",
            "co2e_kg_per_km_bucket",
        ]
        return df[features]


class MetadataTableDataTransformer(DataTransformer):
    """Transforms data from the Parquet input format to the Postgres output format for the metadata table."""

    def __init__(self, table_name: str) -> None:
        super().__init__(table_name, requires_upsert=False, is_partitioned=True)

    def parquet_data_to_postgres(self, df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()

        df.loc[:, "time_start"] = pd.to_datetime(df["time_start"])

        df = df.assign(
            total_pos_ef_persistent_contrail_length_km=df[
                "total_pos_ef_persistent_contrail_length_km"
            ].astype(int),
            total_persistent_contrail_length_km=df[
                "total_persistent_contrail_length_km"
            ].astype(int),
        )

        features = [
            "_processed_at",
            "total_fuel_burn_kg",
            "pycontrails_ver",
            "perf_model_id",
            "nvpm_data_source",
            "git_sha",
            "zarr_uri",
            "flight_id",
            "time_start",
            "total_pos_ef_persistent_contrail_length_km",
            "total_persistent_contrail_length_km",
        ]
        # Only keep the relevant columns specified above.
        return df[features]


class ImpactHistogramTableDataTransformer(DataTransformer):
    """Transforms data from the Parquet input format to the Postgres output format for the impact histogram table.

    Note that the data is uploaded in batches. Two separate batches can hold data relevant to a monthly airline impact
    bucket so update on insert needs to be used to keep the counts correct.
    """

    def __init__(self, table_name: str) -> None:
        super().__init__(table_name, requires_upsert=True, is_partitioned=False)

    def parquet_data_to_postgres(self, df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()
        df = add_is_eu_mrv_column(df)

        # Always use the first date of a month to define the year and month key.
        year_month = (
            pd.to_datetime(df["time_start"])
            .dt.to_period("M")
            .dt.to_timestamp()
            .dt.date.rename("month")
        )

        # Ignore negative energy forcing
        s = df["sum_ef_mj"].clip(lower=0)

        # Reduce the flights histogram to a fixed set of bins (n=40).
        # The distribution roughly follows a negative power law in the range [0, 1e10].
        # Note that the impact is based on ef_mj (and not CO2e kgs GWP20).
        # Using log spaced bins and dropping negligible bins between [1e0, 1e5) to best represent the distribution.
        bins = (
            [0] + list(np.logspace(start=5, stop=10, num=38, base=10)) + [float("inf")]
        )
        binned = pd.cut(s, bins=bins, right=False).rename("impact")

        # Group by airline, year_month, and bin
        agg = (
            s.groupby(
                [df["airline_iata"], year_month, df["is_eu_mrv"], binned],
                observed=False,
                dropna=False,
            )
            .agg(["count", "sum"])
            .rename(columns={"count": "flight_count", "sum": "total_sum_ef_mj"})
            .reset_index()
        )

        agg = agg.assign(
            # Set a bin ID that is equivalent for the same range across months and airlines.
            bin_idx=agg["impact"].cat.codes,
            # Split impact into lower and upper
            lower_ef_mj=agg["impact"].apply(lambda x: x.left),
            upper_ef_mj=agg["impact"].apply(lambda x: x.right),
        )

        # Drop rows that have no data and the original impact column to save database storage space.
        agg = agg[agg["flight_count"] != 0].copy()
        features = [
            "airline_iata",
            "month",
            "is_eu_mrv",
            "bin_idx",
            "lower_ef_mj",
            "upper_ef_mj",
            "flight_count",
            "total_sum_ef_mj",
        ]
        # Only keep the relevant columns specified above.
        return agg[features]

    def on_conflict_do_update(self, target_table, stmt_excluded):
        index_elements = ["airline_iata", "month", "is_eu_mrv", "bin_idx"]
        upsert_args = {
            "flight_count": target_table.c.flight_count + stmt_excluded.flight_count,
            "total_sum_ef_mj": target_table.c.total_sum_ef_mj
            + stmt_excluded.total_sum_ef_mj,
            "lower_ef_mj": stmt_excluded.lower_ef_mj,
            "upper_ef_mj": stmt_excluded.upper_ef_mj,
        }
        return index_elements, upsert_args


if __name__ == "__main__":
    parser = ArgumentParser()
    parser.add_argument(
        "--gcs_bucket",
        dest="gcs_bucket",
        default="contrails-301217-sandbox-internal",
        help="GCS bucket name.",
    )
    parser.add_argument(
        "--gcs_paths",
        dest="gcs_paths",
        required=True,
        help="Comma-separated GCS paths to the directory with the .pq files.",
    )
    parser.add_argument(
        "--target_table",
        dest="target_table",
        default=TRAJECTORY_TABLE_NAME,
        help="Target table name in Postgres database.",
    )
    parser.add_argument(
        "--target_meta_table",
        dest="target_meta_table",
        default=TRAJECTORY_META_TABLE_NAME,
        help="Target metadata table name in Postgres database.",
    )
    parser.add_argument(
        "--target_histogram_table",
        dest="target_histogram_table",
        default=TRAJECTORY_HISTOGRAM_IMPACT_TABLE_NAME,
        help="Target impact histogram table name in Postgres database.",
    )
    parser.add_argument(
        "--db_host",
        dest="db_host",
        default="",
        help="Postgres database IP address. Leave empty to use cloud SQL socket instead.",
    )
    parser.add_argument(
        "--db_socket_name",
        dest="db_socket_name",
        default="",
        help="Postgres database instance name to be used with cloud SQL socket.",
    )
    parser.add_argument("--db_port", dest="db_port", default=5432)
    parser.add_argument(
        "--db_user",
        dest="db_user",
        default="internal_user_rw",
        help="Postgres database user.",
    )
    parser.add_argument(
        "--db_password",
        dest="db_password",
        required=True,
        help="Postgres database password.",
    )
    args = parser.parse_args()

    logger.info(
        "starting", extra={"bucket": args.gcs_bucket, "paths": args.gcs_paths}
    )

    gcs_paths = GcsPathReader(args.gcs_bucket, args.gcs_paths)
    loader = GcsToPostgresLoader(
        data_transformers=[
            MainTableDataTransformer(args.target_table),
            MetadataTableDataTransformer(args.target_meta_table),
            ImpactHistogramTableDataTransformer(args.target_histogram_table),
        ],
        db_uri=get_db_uri(
            args.db_host,
            args.db_port,
            args.db_socket_name,
            args.db_user,
            args.db_password,
        ),
    )
    for start_incl, end_excl in gcs_paths.date_ranges():
        loader.ensure_partitions_exist(start_incl, end_excl)
        loader.assert_no_data(start_incl, end_excl)

    parquet_files = list(gcs_paths.parquet_files())
    logger.info("processing", extra={"file_count": len(parquet_files)})

    failed: list[str] = []
    for p in tqdm(parquet_files):
        try:
            loader.to_postgres(p)
        except Exception:
            failed.append(p.name)

    if failed:
        logger.error("failed to load some parquet files into Postgres", extra={"failed_count": len(failed), "total_files": len(parquet_files), "failed_files": failed})
        sys.exit(1)

    logger.info("finished", extra={"detail": "success", "file_count": len(parquet_files)})

"""Utility to load trajectory cocip Parquet shards from GCS and write them to Postgres."""

from datetime import date, datetime, timedelta
import io
import os
from typing import Iterator
from concurrent.futures import ThreadPoolExecutor

from argparse import ArgumentParser
import pandas as pd
from google.cloud import storage
from sqlalchemy import URL, and_, create_engine, func, select, table, column
from tqdm import tqdm
import psycopg2

TRAJECTORY_TABLE = table("trajectory-cocip", column("flight_id"), column("time_start"))


def get_db_uri(db_host: str, port: int, db_socket_instance: str, password: str):
    """Prioritizes TCP (DB_HOST) if set, otherwise falls back to Cloud SQL Unix Sockets."""
    assert db_host or db_socket_instance, "Either a host IP or a socket instance name need to be specified!"

    common_params = {
        "drivername": "postgresql+psycopg",
        "username": "internal_user_rw",
        "password": password,
        "database": "flights-pipeline-fer-cache",
    }

    if db_host:
        print(f"Connecting via TCP to {db_host}:{port}")
        return URL.create(**common_params, host=db_host, port=port)
    else:
        socket_host_url = f"/cloudsql/contrails-301217:us-east1:{db_socket_instance}"
        print(f"Connecting via Unix Socket: {socket_host_url}")
        return URL.create(**common_params, query={"host": socket_host_url, "port": str(port)})


def extract_year_quarter_range(year_quarter_str: str) -> tuple[date, date]:
    """Extracts the date range of YYYY(Q1-4) with an inclusive start and exclusive end date."""
    if not year_quarter_str:
        raise Exception("Year quarter cannot be empty!")

    if not 'Q' in year_quarter_str:
        year = int(year_quarter_str)
        year_quarter_start = date(year, 1, 1)
        year_quarter_end = date(year + 1, 1, 1)
    else:
        period = pd.Period(year_quarter_str, freq='Q')
        year_quarter_start = period.start_time.date()
        year_quarter_end = period.end_time.date() + timedelta(days=1)

    if year_quarter_start < year_quarter_end < date(2000, 1, 1):
        raise Exception(f"Invalid old year detected prior to 2000. Got {year_quarter_str}")
    return year_quarter_start, year_quarter_end


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
            raise Exception("Paths need to be in the format a/b/.../<year><optional Q1-4>"
                            f"/<process date YYYYMMDD>. But got {path}.")
        year_quarter_str, process_time_str = parts[-2], parts[-1]
        start_date, end_date = extract_year_quarter_range(year_quarter_str)
        parse_date = datetime.strptime(process_time_str, '%YYYYMMDD').date()
        if parse_date < date(2025, 1, 1) or parse_date > date.today():
            raise Exception(f"Invalid process date detected. Expected recent YYYYMMDD but got {parse_date}.")

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
            print(f"Found {len(parquet_shards)} parquet shards.")
            yield from parquet_shards


class GcsToPostgresLoader:
    def __init__(self, table_name: str, db_uri: str):
        self.engine = create_engine(db_uri)
        self.table_name = table_name


    def assert_no_data(self, start_incl: date, end_excl: date) -> None:
        """Ensure that there is no data currently within the specified date range: [start_incl, end_excl)."""
        stmt = (
            select(func.count(TRAJECTORY_TABLE.c.flight_id).label("flight_cnt"))
            .where(and_(
                TRAJECTORY_TABLE.c.time_start >= start_incl,
                TRAJECTORY_TABLE.c.time_start < end_excl,
            ))
        )

        df = pd.read_sql(stmt, self.engine)
        if df.empty:
            # Good there were no matching results.
            return
        if len(df.index) > 1:
            raise Exception(f"There were multiple rows for the time range: {start_incl} - {end_excl}")

        df["flight_cnt"] = df["flight_cnt"].fillna(0)
        assert (df["flight_cnt"] == 0).all(), "There is flights data present in [{start_incl}, {end_excl})."\
                                              "Please delete it first."


    def _read_parquet_blob(self, blob: storage.Blob) -> pd.DataFrame:
        data = blob.download_as_bytes()
        return pd.read_parquet(io.BytesIO(data))


    def _upload_to_postgres(self, df: pd.DataFrame, schema: str = "public") -> None:
        """Uploads a pandas DataFrame to Postgres using the efficient COPY command."""

        connection = self.engine.raw_connection()
        cur = connection.cursor()

        # Use a buffer to hold CSV data in memory
        output = io.StringIO()

        # specific formatting for Postgres COPY
        df.to_csv(output, sep='\t', header=False, index=False)
        output.seek(0)

        try:
            full_table_name = f"{schema}.{self.table_name}"
            cur.copy_from(output, full_table_name, null="")
            connection.commit()
        except Exception as e:
            connection.rollback()
            print(f"Error uploading data: {e}")
            raise
        finally:
            cur.close()
            connection.close()


    def _transform_parquet_data_to_postgres(self, df: pd.DataFrame) -> pd.DataFrame:
        df["chunk_len_km"] = df["chunk_len_km"].astype(int)
        df["mean_aircraft_mass_kg"] = df["mean_aircraft_mass_kg"].astype(int)

        features = [
            "chunk_len_km",
            "lat_start",
            "lon_start",
            "lat_end",
            "lon_end",
            "time_start",
            "time_end",
            "sum_ef_mj",
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
            "arrival_airport_icao",
        ]
        # Only keep the relevant columns specified above.
        df.drop(df.columns.difference(features), 1, inplace=True)


    def to_postgres(self, blob: storage.Blob) -> None:
        try:
            df = self._read_parquet_blob(blob)
            if df.empty:
                print(f"Empty parquet file: {blob}")
                return

            # TODO split into main and meta tables
            self._transform_parquet_data_to_postgres(df)
            self._upload_to_postgres(df)
        except Exception as e:
            print(f"Failed to process {blob.name}: {e}")


if __name__ == "__main__":
    parser = ArgumentParser()
    parser.add_argument("--gcs_bucket", dest="gcs_bucket", default="contrails-301217-sandbox-internal",
                        help="GCS bucket name.")
    parser.add_argument("--gcs_paths", dest="gcs_paths", default="flights-pipeline/emissions-export",
                        help="Comma-separated GCS paths to the directory with the .pq files.")
    parser.add_argument("--target_table", dest="target_table", default="trajectory_cocip",
                        help="Target table name in Postgres database.")
    parser.add_argument("--num_workers", dest="num_workers", default=10,
                        help="One Parquet file is about 40MB in size. Be cautious with multi-threading OOMing.")
    parser.add_argument("--db_host", dest="db_host", default="",
                        help="Postgres database IP address. Leave empty to use cloud SQL socket instead.")
    parser.add_argument("--db_socket_name", dest="db_socket_name", default="",
                        help="Postgres database instance name to be used with cloud SQL socket.")
    parser.add_argument("--db_port", dest="db_port", default=5432)
    parser.add_argument("--db_password", dest="db_password", required=True,
                        help="Postgres database password.")
    args = parser.parse_args()

    db_uri = get_db_uri(args.db_host, args.db_port, args.db_socket_name, args.db_password)
    gcs_paths = GcsPathReader(args.gcs_bucket, args.gcs_paths)
    loader = GcsToPostgresLoader(args.target_table, db_uri)
    for start_incl, end_excl in gcs_paths.date_ranges():
        loader.assert_no_data(start_incl, end_excl)

    parquet_files = list(gcs_paths.parquet_files())
    with ThreadPoolExecutor(max_workers=args.num_workers) as executor:
        tqdm(executor.map(loader.to_postgres, parquet_files), total=len(parquet_files))
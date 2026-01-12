"""Utility to load trajectory cocip Parquet shards from GCS and write them to Postgres."""

import io
import os
from typing import Iterator
from concurrent.futures import ThreadPoolExecutor

from argparse import ArgumentParser
import pandas as pd
from google.cloud import storage
from sqlalchemy import URL, create_engine
from tqdm import tqdm
import psycopg2

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


class GcsPathReader:
    def __init__(self, bucket_name: str, prefix: str):
        self.bucket_name = bucket_name
        self.prefix = prefix.rstrip("/")
        self.storage_client = storage.Client()
        self.bucket = self.storage_client.bucket(self.bucket_name)


    def _latest_process_time(self, gcs_prefix: str) -> Iterator[str]:
        blobs = list(self.storage_client.list_blobs(self.bucket_name, prefix=gcs_prefix))

        if blobs:
            # Relying on alphanumerical file sorting of YYYYMMDD to fetch the latest version.
            yield max(b.name for b in blobs)
        else:
            print(f"No blobs in {gcs_prefix}.")


    def _process_quarterly_data(self, quarterly_date_range: str) -> Iterator[str]:
        yield from self._latest_process_time(f"{self.prefix}/{quarterly_date_range}")


    def _process_yearly_data(self, year: int) -> Iterator[str]:
        # Check if yearly data is present and otherwise default to quarterly data
        yearly_path = f"{self.prefix}/{year}"
        if storage.Blob(bucket=self.bucket, name=yearly_path).exists(self.storage_client):
            yield from self._latest_process_time(yearly_path)
        else:
            print(f"No yearly data for {yearly_path}. Falling back to quarterly.")
            for quarter in range(1, 5):
                yield from self._process_quarterly_data(f'{year}Q{quarter}')


    def find_valid_paths(self, date_ranges: str) -> Iterator[str]:
        for date_range in date_ranges.split(","):
            if 'Q' in date_range:
                yield from self._process_quarterly_data(date_range)
            else:
                yield from self._process_yearly_data(int(date_range))


    def parquet_files(self, date_ranges: str) -> Iterator[storage.Blob]:
        for path in self.find_valid_paths(date_ranges):
            blobs = self.storage_client.list_blobs(self.bucket_name, prefix=path)
            parquet_shards = [b for b in blobs if b.name.endswith(".pq")]
            print(f"Found {len(parquet_shards)} parquet shards.")
            yield from parquet_shards


class GcsToPostgresLoader:
    def __init__(self, table_name: str, db_uri: str):
        self.engine = create_engine(db_uri)
        self.table_name = table_name


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
    parser.add_argument("--date_ranges", dest="date_ranges", required=True,
                        help="Comma-separated list of date ranges in the format YYYY(Q[1-4]) (quarters are optional).")
    parser.add_argument("--gcs_bucket", dest="gcs_bucket", default="contrails-301217-sandbox-internal",
                        help="GCS bucket name.")
    parser.add_argument("--gcs_prefix", dest="gcs_prefix", default="flights-pipeline/emissions-export",
                        help="GCS prefix for exported data.")
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
    gcs_paths = GcsPathReader(args.gcs_bucket, args.gcs_prefix)
    loader = GcsToPostgresLoader(args.target_table, db_uri)
    parquet_files = list(gcs_paths.parquet_files(args.date_ranges))
    with ThreadPoolExecutor(max_workers=args.num_workers) as executor:
        tqdm(executor.map(loader.to_postgres, parquet_files), total=len(parquet_files))
import concurrent.futures
import json
import time
from datetime import datetime, timedelta, timezone
from typing import Any

import pandas as pd
import requests

from lib import utils
from lib.log import logger

# Requesting data [start_at, end_at) will fetch [start_at, end_at + INGEST_LAG_TIME]
# from Spire's API to load data observations that occurred during [start_at, end_at)
# but were ingested after end_at. Records with observation timestamps outside of
# [start_at, end_at) are dropped before data leaves this module.
INGEST_LAG_TIME = timedelta(minutes=2)

# Spire reported that the following icao_address values are not unique to a specific
# aircraft. We drop related records to avoid downstream inconsistencies.
IGNORE_ICAO_ADDRESS = {"000000", "00000a"}


class SpireAPIClient:
    def __init__(
        self,
        api_token: str,
        airsafe_url: str = "https://api.airsafe.spire.com/v2/targets/stream",
    ) -> None:
        self._api_token = api_token
        self._airsafe_url = airsafe_url

    def get_data_between(
        self,
        start_at: datetime,
        end_at: datetime,
    ) -> tuple[pd.DataFrame, pd.DataFrame]:
        """Fetch global aircraft position records within time window.

        Parameters
        ----------
        start_at
            observation timestamp window start, inclusive
        end_at
            observation timestamp window end, exclusive

        Returns
        -------
        tuple[pd.DataFrame, pd.DataFrame]
            first element is records with observation time in target window.
            second element is records with tardy timestamps.
            aircraft position rows with timestamp in [start_at, end_at) with columns:
            {
                "ingestion_time": "2024-03-04T23:24:01.900Z",
                "icao_address": "040172",
                "flight_id": "a854ae1e-9348-45cc-8253-3251b1ce6448",
                "timestamp": "2024-03-04T23:23:59Z",
                "latitude": 36.696758,
                "longitude": 19.5334,
                "altitude_baro": 38750,
                "heading": 122.42984,
                "speed": 530.0,
                "vertical_rate": 512,
                "squawk": "5223",
                "on_ground": false,
                "callsign": "ETH701",
                "tail_number": "ET-AWO",
                "source": "ADSB",
                "collection_type": "terrestrial",
                "flight_number": "ET701",
                "aircraft_type_icao": "A359",
                "aircraft_type_name": "Airbus A350-941",
                "airline_iata": "ET",
                "airline_name": "Ethiopian Airlines",
                "departure_utc_offset": "+0000",
                "departure_airport_icao": "EGLL",
                "departure_airport_iata": "LHR",
                "departure_scheduled_time": "2024-03-04T20:15:00Z",
                "departure_estimated_time": "2024-03-04T20:26:00Z",
                "takeoff_time": "2024-03-04T20:47:36Z",
                "arrival_utc_offset": "+0300",
                "arrival_airport_icao": "HAAB",
                "arrival_airport_iata": "ADD",
                "arrival_scheduled_time": "2024-03-05T04:00:00Z"
            }
        """

        if start_at.tzinfo is None:
            raise ValueError("start_at must be timezone aware")
        if end_at.tzinfo is None:
            raise ValueError("end_at must be timezone aware")

        start_at = start_at.astimezone(timezone.utc)
        end_at = end_at.astimezone(timezone.utc)

        end_at_plus_lag = end_at + INGEST_LAG_TIME
        if end_at_plus_lag > datetime.now(timezone.utc):
            raise ValueError(
                f"end_at must be at least {INGEST_LAG_TIME} before present"
            )

        # Decompose job into multiple windows that can be fetched concurrently.
        concurrency = (end_at_plus_lag - start_at) // timedelta(minutes=1)
        windows = utils.time_windows(start_at, end_at_plus_lag, timedelta(minutes=1))
        with concurrent.futures.ThreadPoolExecutor(concurrency) as executor:
            results = executor.map(
                lambda window: self._fetch_target_records_with_retry(*window),
                windows,
            )

        # Flatten nested list of records returned by each worker thread.
        target_records = [record for result in results for record in result]
        df = pd.DataFrame(target_records)

        # Spire API may return icao_address values that are not unique to a specific
        # aircraft. Drop values known to be duplicated across aircraft.
        is_ignored_icao_address = df["icao_address"].isin(IGNORE_ICAO_ADDRESS)
        is_unique_icao_address = ~is_ignored_icao_address
        df = df.loc[is_unique_icao_address, :]

        drop_count_ignored_icao_address = is_ignored_icao_address.sum()
        if drop_count_ignored_icao_address > 0:
            logger.info(
                f"Drop {drop_count_ignored_icao_address} records with non-unique "
                + f"icao_address in {IGNORE_ICAO_ADDRESS}"
            )

        # Spire API's start_at and end_at query params reference ingestion_time
        # sometimes, the SPIRE API will still return records outside of [start_at, end_at]
        timestamp = pd.to_datetime(df["timestamp"])
        ingestion_time = pd.to_datetime(df["ingestion_time"])
        ingest_at_or_after_start = ingestion_time >= pd.to_datetime(start_at)
        ingest_before_end_w_buffer = ingestion_time < pd.to_datetime(end_at_plus_lag)
        df = df.loc[ingest_at_or_after_start & ingest_before_end_w_buffer, :]

        drop_ingest_outside_window = (~ingest_at_or_after_start).sum() + (
            ~ingest_before_end_w_buffer
        ).sum()
        if drop_ingest_outside_window > 0:
            logger.info(
                f"Records outside query window. "
                f"Drop {drop_ingest_outside_window} records."
            )

        # identify tardy records
        timestamp = pd.to_datetime(df["timestamp"])
        ingestion_time = pd.to_datetime(df["ingestion_time"])
        is_tardy = (ingestion_time - timestamp) > INGEST_LAG_TIME
        ingest_before_end = ingestion_time < pd.to_datetime(end_at)
        df_tardy = df.loc[is_tardy & ingest_before_end, :]

        # Drop records with timestamps outside of [start_at, end_at).
        is_at_or_after_start = timestamp >= pd.to_datetime(start_at)
        is_before_end = timestamp < pd.to_datetime(end_at)
        df = df.loc[is_at_or_after_start & is_before_end, :]

        drop_count_before_start = (~is_at_or_after_start).sum()
        if drop_count_before_start > 0:
            logger.info(f"Drop {drop_count_before_start} records before {start_at}")

        drop_count_after_end = (~is_before_end).sum()
        if drop_count_after_end > 0:
            logger.info(f"Drop {drop_count_after_end} records after {end_at}")

        return df, df_tardy

    def _fetch_target_records_with_retry(
        self,
        start_at_utc: datetime,
        end_at_utc: datetime,
    ) -> list[dict[str, Any]]:
        """Sends GET request to Spire API and parses target records from response.

        Failed requests are retried up to 5 times with exponential backoff.

        This method is thread-safe.
        """
        headers = {"Authorization": f"Bearer {self._api_token}"}
        start_at_fmt = start_at_utc.isoformat().replace("+00:00", "Z")
        end_at_fmt = end_at_utc.isoformat().replace("+00:00", "Z")
        params = {
            "start": start_at_fmt,
            "end": end_at_fmt,
        }

        min_backoff_seconds = 1
        max_backoff_seconds = 30
        max_retry_count = 5

        backoff_seconds = min_backoff_seconds
        retry_count = 0
        while retry_count <= max_retry_count:
            logger.info(f"calling Spire API: {start_at_fmt} to {end_at_fmt}")
            response = requests.get(
                self._airsafe_url,
                params=params,
                headers=headers,
                timeout=120,
            )
            if response.status_code == 200:
                break

            logger.warning(
                "Spire request failed with error "
                f"{response.status_code}: {response.text}"
            )
            can_retry = retry_count < max_retry_count
            if can_retry:
                time.sleep(backoff_seconds)
                backoff_seconds = min(backoff_seconds * 2, max_backoff_seconds)
                retry_count += 1
            else:
                response.raise_for_status()

        target_records = []
        for line in response.iter_lines():
            record = json.loads(line)
            target_record = record.get("target")
            if target_record is not None:
                target_records.append(target_record)

        return target_records

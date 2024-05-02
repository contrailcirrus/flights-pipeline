import asyncio
import json
import time
from datetime import datetime, timedelta, timezone
from typing import Any

import httpx
import pandas as pd

from lib import utils
from lib.log import format_traceback, logger

# Requesting data [start_at, end_at) will fetch [start_at, end_at + INGEST_LAG_TIME]
# from Spire's API to load data observations that occurred during [start_at, end_at)
# but were ingested after end_at. Records with observation timestamps outside of
# [start_at, end_at) are dropped before data leaves this module.
INGEST_LAG_TIME = timedelta(minutes=2)

# Spire reported that the following icao_address values are not unique to a specific
# aircraft. We drop related records to avoid downstream inconsistencies.
IGNORE_ICAO_ADDRESS = {"000000", "00000a", "0000BA"}


class SpireAPIClient:
    def __init__(
        self,
        api_token: str,
        airsafe_url: str = "https://api.airsafe.spire.com/v2/targets/stream",
    ) -> None:
        self._api_token = api_token
        self._airsafe_url = airsafe_url

    async def get_data_between(
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
        windows = utils.time_windows(start_at, end_at_plus_lag, timedelta(minutes=1))

        coroutines = [
            self._fetch_target_records_with_retry(*window) for window in windows
        ]
        results = await asyncio.gather(*coroutines)

        # Flatten nested list of records.
        records = [record for result in results for record in result]
        df = pd.DataFrame(records)
        logger.info(f"Fetched {len(df)} total records from Spire.")

        # Spire API may return icao_address values that are not unique to a specific
        # aircraft. Drop values known to be duplicated across aircraft.
        is_ignored_icao_address = df["icao_address"].isin(IGNORE_ICAO_ADDRESS)
        is_unique_icao_address = ~is_ignored_icao_address
        df = df.loc[is_unique_icao_address, :]

        drop_count_ignored_icao_address = is_ignored_icao_address.sum()
        if drop_count_ignored_icao_address > 0:
            logger.info(
                f"Drop {drop_count_ignored_icao_address} records with non-unique "
                f"icao_address in: {IGNORE_ICAO_ADDRESS}"
            )

        # Drop records with ingestion timestamps outside of [start_at, end_at_plus_lag).
        # Spire API's start_at and end_at query params reference ingestion_time.
        # Sometimes the SPIRE API will return records with ingestion_time outside of
        # [start_at, end_at_plus_lag).
        timestamp = pd.to_datetime(df["timestamp"])
        ingestion_time = pd.to_datetime(df["ingestion_time"])
        ingest_at_or_after_start = ingestion_time >= pd.to_datetime(start_at)
        ingest_before_end_w_buffer = ingestion_time < pd.to_datetime(end_at_plus_lag)
        in_range_filter = ingest_at_or_after_start & ingest_before_end_w_buffer
        df = df.loc[in_range_filter, :]

        drop_count = (~in_range_filter).sum()
        if drop_count > 0:
            logger.info(
                f"Drop {drop_count} records with "
                f"ingestion time outside window: [{start_at}, {end_at_plus_lag})"
            )

        # Identify tardy records; target records which were ingested by Spire after the
        # allowable INGEST_LAG_TIME has elapsed.
        timestamp = pd.to_datetime(df["timestamp"])
        ingestion_time = pd.to_datetime(df["ingestion_time"])
        is_tardy = (ingestion_time - timestamp) > INGEST_LAG_TIME
        ingest_before_end = ingestion_time < pd.to_datetime(end_at)
        df_tardy = df.loc[is_tardy & ingest_before_end, :]

        # Drop records with observation timestamps outside of [start_at, end_at), to
        # guarantee ordering-in-time between subsequent invocations.
        is_at_or_after_start = timestamp >= pd.to_datetime(start_at)
        is_before_end = timestamp < pd.to_datetime(end_at)
        in_range_filter = is_at_or_after_start & is_before_end
        df = df.loc[in_range_filter, :]

        drop_count = (~in_range_filter).sum()
        if drop_count > 0:
            logger.info(
                f"Drop {drop_count} records with "
                f"observation time outside window: [{start_at}, {end_at})"
            )

        return df, df_tardy

    async def _fetch_target_records_with_retry(
        self,
        start_at_utc: datetime,
        end_at_utc: datetime,
    ) -> list[dict[str, Any]]:
        """Sends GET request to Spire API and parses "target" records from response.

        Failed requests are retried up to 5 times with exponential backoff.
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
            logger.info(f"Calling Spire API: {start_at_fmt} to {end_at_fmt}")
            try:
                async with httpx.AsyncClient() as client:
                    response = await client.get(
                        self._airsafe_url,
                        params=params,
                        headers=headers,
                        timeout=120,
                    )
                response.raise_for_status()
                break

            except httpx.HTTPError as e:
                logger.warning("Spire request failed with error " + format_traceback())

                can_retry = retry_count < max_retry_count
                if can_retry:
                    logger.info(f"Retrying request after {backoff_seconds}s delay...")
                    time.sleep(backoff_seconds)
                    backoff_seconds = min(backoff_seconds * 2, max_backoff_seconds)
                    retry_count += 1
                else:
                    logger.warning("Retry limit exceeded")
                    raise e

        # Spire response is newline-delimited records where the first line contains
        # "status" records containing metadata and subsequent lines contain "target"
        # records containing flight data.
        #
        # Extract only the "target" records so all records returned contain the same
        # structure with flight data, dropping the "status" records.
        target_records = []
        for line in response.iter_lines():
            record = json.loads(line)
            target_record = record.get("target")
            if target_record is not None:
                target_records.append(target_record)

        return target_records

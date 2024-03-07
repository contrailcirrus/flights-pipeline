import json
import logging
import time
from datetime import datetime, timedelta, timezone

import pandas as pd
import requests

logger = logging.getLogger(__name__)


# Requesting data between [start_at, end_at) will fetch [start_at, end_at + WALL_TIME]
# from Spire's API to load data observations that occurred during [start_at, end_at)
# but were ingested after end_at. Records with observation timestamps outside of
# [start_at, end_at) are dropped before data leaves this module.
INGEST_LAG_TIME = timedelta(minutes=5)


class SpireAPIClient:
    def __init__(
        self,
        api_token: str,
        airsafe_url: str = "https://api.airsafe.spire.com/v2/targets/stream",
    ) -> None:
        self._api_token = api_token
        self._airsafe_url = airsafe_url

    def get_data_between(self, start_at: datetime, end_at: datetime) -> pd.DataFrame:
        """Fetch global aircraft position records within time window.

        Parameters
        ----------
        start_at
            observation timestamp window start, inclusive
        end_at
            observation timestamp window end, exclusive

        Returns
        -------
        pd.DataFrame
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

        start_at_utc = start_at.astimezone(timezone.utc)
        end_at_utc = end_at.astimezone(timezone.utc)

        end_at_utc_buffer = end_at_utc + INGEST_LAG_TIME
        if end_at_utc_buffer > datetime.now(timezone.utc):
            raise ValueError(
                f"end_at must be at least {INGEST_LAG_TIME} before present"
            )

        headers = {"Authorization": f"Bearer {self._api_token}"}

        params = {
            "start": start_at_utc.isoformat().replace("+00:00", "Z"),
            "end": end_at_utc_buffer.isoformat().replace("+00:00", "Z"),
        }

        min_backoff_seconds = 1
        max_backoff_seconds = 30
        max_retry_count = 5

        backoff_seconds = min_backoff_seconds
        retry_count = 0
        while retry_count <= max_retry_count:
            response = requests.get(
                self._airsafe_url,
                params=params,
                headers=headers,
                timeout=120,
            )
            if response.status_code == 200:
                break

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

        df = pd.DataFrame(target_records)

        # Spire API may return records out of the request time window. Drop records
        # with timestamps outside of [start_at, end_at).
        timestamp = pd.to_datetime(df["timestamp"])
        is_at_or_after_start = timestamp >= pd.to_datetime(start_at_utc)
        is_before_end = timestamp < pd.to_datetime(end_at_utc)
        df = df.loc[is_at_or_after_start & is_before_end, :]

        drop_count_before_start = (~is_at_or_after_start).sum()
        if drop_count_before_start > 0:
            logger.info(f"Drop {drop_count_before_start} records before {start_at_utc}")

        drop_count_after_end = (~is_before_end).sum()
        if drop_count_after_end > 0:
            logger.info(f"Drop {drop_count_after_end} records after {end_at_utc}")

        return df

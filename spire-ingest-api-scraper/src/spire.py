import json
import time
from datetime import datetime

import pandas as pd
import requests


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

        Args:
            start_at: window start, inclusive
            end_at: window end, exclusive

        Returns:
            pd.DataFrame with rows of:
            {
                "ingestion_time": "2024-03-01T13:00:02.955Z",
                "icao_address": "34758C",
                "flight_id": "00142f32-9bfa-497f-a9d4-659ece1a6f70",
                "timestamp": "2024-03-01T13:00:00Z",
                "latitude": 33.695301,
                "longitude": -12.087479,
                "heading": 215.6893,
                "squawk": "3737",
                "on_ground": false,
                "callsign": "IBS38DM",
                "tail_number": "EC-OCI",
                "source": "ADSB",
                "collection_type": "terrestrial",
                "flight_number": "IB3830",
                "aircraft_type_icao": "A21N",
                "aircraft_type_name": "Airbus A321-271NX",
                "airline_iata": "I2",
                "airline_name": "Iberia Express",
                "departure_utc_offset": "+0100",
                "departure_airport_icao": "LEMD",
                "departure_airport_iata": "MAD",
                "departure_scheduled_time": "2024-03-01T11:15:00Z",
                "takeoff_time": "2024-03-01T11:27:27Z",
                "arrival_utc_offset": "+0000",
                "arrival_airport_icao": "GCLP",
                "arrival_airport_iata": "LPA",
                "arrival_scheduled_time": "2024-03-01T14:10:00Z",
                "arrival_estimated_time": "2024-03-01T14:13:00Z"
            }
        """

        # For 1 minute of data
        # https://api.airsafe.spire.com/v2/targets/stream
        #   ?start=2024-03-01T13:00:00Z&end=2024-03-01T13:01:00Z
        # response time: 6.5 s
        # response size: 93 MB

        headers = {"Authorization": f"Bearer {self._api_token}"}

        params = {
            "start": start_at.isoformat(),
            "end": end_at.isoformat(),
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
        # ingested outside of [start_at, end_at).
        ingestion_time = pd.to_datetime(df["ingestion_time"], utc=True)
        is_at_or_after_start = ingestion_time >= pd.to_datetime(start_at, utc=True)
        is_before_end = ingestion_time < pd.to_datetime(end_at, utc=True)

        df = df.loc[is_at_or_after_start & is_before_end, :]

        return df

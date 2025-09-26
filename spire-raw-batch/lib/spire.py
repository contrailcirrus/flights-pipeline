"""
Spire API client for fetching aircraft position data.
"""

import asyncio
import json
import time
from datetime import datetime, timedelta, timezone
from typing import Any

import httpx
import pandas as pd

from lib.log import format_traceback, logger


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
    ) -> pd.DataFrame:
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
            Dataframe with records whose spire ingestion_time is within target window.
        """
        if start_at.tzinfo is None:
            raise ValueError("start_at must be timezone aware")
        if end_at.tzinfo is None:
            raise ValueError("end_at must be timezone aware")

        start_at = start_at.astimezone(timezone.utc)
        end_at = end_at.astimezone(timezone.utc)

        records = await self._fetch_target_records_with_retry(start_at, end_at)
        df: pd.DataFrame = pd.DataFrame(records)
        logger.info(f"Fetched {len(df)} total records from Spire.")
        
        return df

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
        max_retry_count = 3

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
                        timeout=180,
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

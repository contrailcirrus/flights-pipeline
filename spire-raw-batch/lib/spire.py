"""
Spire API client for fetching aircraft position data.
"""

import json
import time
from datetime import datetime, timezone
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

    def get_data_between(
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

        records = self._fetch_target_records_with_retry(start_at, end_at)
        df: pd.DataFrame = pd.DataFrame(records)
        logger.info(f"Fetched {len(df)} total records from Spire.")

        return df

    def _fetch_target_records_with_retry(
        self,
        start_at_utc: datetime,
        end_at_utc: datetime,
    ) -> list[dict[str, Any]]:
        """Sends GET request to Spire API and parses "target" records from response.

        Failed requests are retried up to 3 times with exponential backoff.
        Handles both request errors and response reading errors (e.g., RemoteProtocolError).
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
                # Use a persistent client with HTTP/2 and increased limits
                limits = httpx.Limits(max_keepalive_connections=5, max_connections=10)
                with httpx.Client(http2=True, limits=limits) as client:
                    with client.stream(
                        "GET",
                        self._airsafe_url,
                        params=params,
                        headers=headers,
                        timeout=httpx.Timeout(180.0, read=300.0),
                    ) as response:
                        response.raise_for_status()

                        target_records = []
                        for line in response.iter_lines():
                            record = json.loads(line)
                            target_record = record.get("target")
                            if target_record is not None:
                                target_records.append(target_record)

                        return target_records

            except (httpx.HTTPError, httpx.RemoteProtocolError) as e:
                error_type = type(e).__name__
                can_retry = retry_count < max_retry_count
                if can_retry:
                    logger.info(
                        f"Spire request/response failed ({error_type}). "
                        f"Retrying request after {backoff_seconds}s delay..."
                    )
                    time.sleep(backoff_seconds)
                    backoff_seconds = min(backoff_seconds * 2, max_backoff_seconds)
                    retry_count += 1
                else:
                    logger.error(
                        f"Spire request/response failed after {max_retry_count} retries ({error_type}): "
                        + format_traceback()
                    )
                    raise e

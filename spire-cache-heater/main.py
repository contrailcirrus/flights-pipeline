"""
Script for heating the spire cache.

The Spire ADS-B cache lives in GCS, and is populated by the contrails-api telemetry endpoint.
This script will identify areas of missing cache in GCS, and hit the API to trigger caching.
"""

import asyncio
import os
from google.cloud import storage
import httpx
import pandas as pd

GCS_CACHE_BUCKET_NAME = "contrails-301217-spire-cache-prod"
URL = "https://api.contrails.org"
API_KEY = os.environ["API_KEY"]
HEADERS = {"x-api-key": API_KEY}

# USER DEFINED
# SET START AND END TIME (INCLUSIVE) FOR CACHE WARMING
CACHE_START = "2024-01-01T00"  # hour resolution
CACHE_END = "2024-06-30T23"  # hour resolution
SKIP_EXISTING = True  # skip any hours where a pq file is found in GCS already

gcs_client = storage.Client()
gcs_bucket = gcs_client.bucket(GCS_CACHE_BUCKET_NAME)


async def fetch_target_hour(
    semaphore: asyncio.locks.Semaphore, time: pd.Timestamp
) -> None:
    """Call the telemetry endpoint for a single time"""

    params = {"date": time.strftime("%Y-%m-%dT%H")}
    async with semaphore, httpx.AsyncClient() as client:
        try:
            r = await client.get(
                f"{URL}/v1/adsb/telemetry",
                params=params,
                headers=HEADERS,
                timeout=120,
            )
            r.raise_for_status()
        except Exception as e:
            print(f"failed to fetch {time}. {e}")
    print(f"fetched {time}")
    # we disregard the r.content


async def run_routines(semaphore: asyncio.locks.Semaphore, times: list[pd.Timestamp]):
    """Run the fetch_target_hour() function for each time in the times list."""
    routines = [fetch_target_hour(semaphore, time) for time in times]
    await asyncio.gather(*routines)


async def main():
    print("starting cache heater")
    print(f"cache range from {CACHE_START} to {CACHE_END} (inclusive)")

    cache_periods = pd.date_range(CACHE_START, CACHE_END, freq="1h", inclusive="both")

    cached_blobs = gcs_bucket.list_blobs(prefix="hourly/", delimiter="/")
    for _ in cached_blobs:
        # for some reason need to kick the iterator, in order for the .prefixes member to populate
        break

    # list of date-hour strings e.g. "2025-01-01T01"
    cached_times = [p.split("/")[1] for p in cached_blobs.prefixes]

    if SKIP_EXISTING:
        # remove cached times from target cache period
        in_cache_cnt = 0
        cache_periods_cnt = len(cache_periods)
        for existing_time in cached_times:
            et = pd.to_datetime(existing_time)
            if et in cache_periods:
                cache_periods = cache_periods.drop(et)
                in_cache_cnt += 1
        print(f"found {in_cache_cnt} of {cache_periods_cnt} times already cached")

    # heat cache
    max_concurrent_tasks = 25
    sem_lock = asyncio.Semaphore(max_concurrent_tasks)
    await run_routines(sem_lock, [i for i in cache_periods])


if __name__ == "__main__":
    asyncio.run(main())

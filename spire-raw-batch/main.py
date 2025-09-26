import asyncio
import sys
from datetime import datetime, timedelta, timezone

from lib import environment, spire
from lib.log import format_traceback, logger


async def main() -> int:
    """Fetch Spire data and write to GCS."""
    logger.info("Starting spire-raw-batch service")

    try:
        # Initialize Spire API client
        spire_client = spire.SpireAPIClient(environment.SPIRE_API_TOKEN)
        logger.info("Spire API client initialized successfully")

        # API call with 5-minute window, 5 hours ago
        now = datetime.now(tz=timezone.utc)
        # Floor to 5-minute boundary and go back 5 hours
        # TODO: Get the timestamp from the firestore file.
        start_at = (now - timedelta(hours=5)).replace(
            minute=(now.minute // 5) * 5, second=0, microsecond=0
        )
        end_at = start_at + timedelta(minutes=5)

        logger.info(f"Fetching Spire data from {start_at} to {end_at}")
        df = await spire_client.get_data_between(start_at, end_at)

        logger.info(f"Successfully fetched {len(df)} records from Spire API")
        if len(df) > 0:
            logger.info(f"Sample record columns: {list(df.columns)}")
            logger.info(f"Sample record: {df.iloc[0].to_dict()}")

        logger.info("spire-raw-batch completed successfully")
        return 0

    except Exception:
        logger.error("Unhandled exception: " + format_traceback())
        return 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))

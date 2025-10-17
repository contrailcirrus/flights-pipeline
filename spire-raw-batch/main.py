import asyncio
import sys
from datetime import datetime, timedelta, timezone

from lib import environment, gcs, spire, state
from lib.log import format_traceback, logger


async def main() -> int:
    """Fetch Spire data and write to GCS."""
    logger.info("Starting spire-raw-batch service")

    try:
        # Initialize clients
        spire_client = spire.SpireAPIClient(environment.SPIRE_API_TOKEN)
        state_client = state.PersistentStateClient(
            environment.FIRESTORE_STATE_DB,
            environment.FIRESTORE_STATE_COLLECTION,
            environment.FIRESTORE_STATE_DOC_ID,
        )
        gcs_client = gcs.GCSClient(environment.GCS_BUCKET_NAME)
        logger.info("Clients initialized successfully")

        # Get the last sync checkpoint from Firestore
        triggered_at = datetime.now(tz=timezone.utc)
        logger.info(f"Current time: {triggered_at.isoformat()}")

        last_sync_end_at = state_client.get_last_sync_end_at()
        logger.info(
            f"Last sync timestamp from Firestore: {last_sync_end_at.isoformat()}"
        )

        # Check if we're behind schedule (warning for alerts)
        time_since_last_sync = triggered_at - last_sync_end_at
        logger.info(f"Time since last sync: {time_since_last_sync}")
        if time_since_last_sync > timedelta(hours=1):
            logger.warning(f"Spire checkpoint behind by: {time_since_last_sync}")

        # For testing: update timestamp to current time
        logger.info("Updating Firestore checkpoint to current time for testing")
        current_checkpoint = triggered_at.replace(
            minute=(triggered_at.minute // 5) * 5, second=0, microsecond=0
        )
        state_client.set_last_sync_end_at(current_checkpoint)

        # Verify the update worked
        updated_checkpoint = state_client.get_last_sync_end_at()
        logger.info(
            f"✅ Successfully updated checkpoint to: {updated_checkpoint.isoformat()}"
        )

        logger.info("spire-raw-batch completed successfully (timestamp update test)")
        return 0

    except Exception:
        logger.error("Unhandled exception: " + format_traceback())
        return 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))

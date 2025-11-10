import sys
from datetime import datetime, timedelta, timezone

from lib import environment, gcs, spire, state
from lib.log import format_traceback, logger


def main() -> int:
    """Fetch Spire data and write to GCS."""
    logger.info("Starting spire-raw-batch service")

    try:
        # Initialize spire API client
        spire_client = spire.SpireAPIClient(environment.SPIRE_API_TOKEN)
        # Initialize Firestore state client for progress tracking
        state_client = state.PersistentStateClient(
            environment.FIRESTORE_STATE_DB,
            environment.FIRESTORE_STATE_COLLECTION,
            environment.FIRESTORE_STATE_DOC_ID,
        )
        # Initialize GCS client for data storage
        gcs_client = gcs.GCSClient(environment.GCS_BUCKET_NAME)

        logger.info("Clients initialized successfully")

        # Get the last sync checkpoint from Firestore
        triggered_at = datetime.now(tz=timezone.utc)
        logger.info(f"Current time: {triggered_at.isoformat()}")
        last_sync_end_at = state_client.get_last_sync_end_at()
        logger.info(
            f"Last sync timestamp from Firestore: {last_sync_end_at.isoformat()}"
        )

        # Check if we're behind schedule
        time_since_last_sync = triggered_at - last_sync_end_at
        logger.info(f"Time since last sync: {time_since_last_sync}")
        if time_since_last_sync > timedelta(hours=1):
            logger.warning(
                f"Spire checkpoint behind by: {time_since_last_sync.total_seconds() / 3600:.1f} hours (last sync: {last_sync_end_at.isoformat()})"
            )

        # Only fetch data up to 5 minutes ago
        max_fetch_time = triggered_at - timedelta(minutes=5)
        # Floor to 5-minute boundary
        start_at = last_sync_end_at.replace(second=0, microsecond=0)
        # Round down to nearest 5-minute boundary
        start_at = start_at.replace(minute=(start_at.minute // 5) * 5)
        end_at = start_at + timedelta(minutes=5)
        # Process data in 5-minute windows until we reach max_fetch_time
        total_records_processed = 0
        windows_processed = 0

        while end_at <= max_fetch_time:
            logger.info(f"Fetching Spire data from {start_at} to {end_at}")
            df = spire_client.get_data_between(start_at, end_at)

            logger.info(f"Successfully fetched {len(df)} records from Spire API")
            if len(df) > 0:
                # Write to GCS parquet file with legacy format filename
                # Filename format: YYYYMMDD-HHMMSS.pq (matches legacy scraper)
                filename = f"{start_at.strftime('%Y%m%d-%H%M%S')}.pq"
                gcs_client.write_parquet(df, filename, overwrite=True)
                total_records_processed += len(df)
            else:
                logger.warning(
                    f"No records fetched from Spire API for window {start_at} to {end_at}"
                )

            # Update the progress marker after successful write
            logger.info(f"Updating Firestore checkpoint to: {end_at.isoformat()}")
            state_client.set_last_sync_end_at(end_at)

            # Move to next 5-minute window
            start_at = end_at
            end_at = start_at + timedelta(minutes=5)
            windows_processed += 1
        logger.info(f"✅ Successfully updated checkpoint to: {start_at.isoformat()}")
        logger.info("spire-raw-batch completed successfully")
        return 0
    except Exception:
        logger.error("Unhandled exception: " + format_traceback())
        return 1


if __name__ == "__main__":
    sys.exit(main())

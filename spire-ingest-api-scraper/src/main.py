import logging
from collections.abc import Iterator
from datetime import datetime, timedelta, timezone
from typing import Any

from . import queue, schemas, spire, state

# SYNC_DELAY enforces we do not fetch data ingested by Spire after: now - SYNC_DELAY
SYNC_DELAY = timedelta(minutes=5)

logger = logging.getLogger(__name__)


def _to_string_or_none(x: Any) -> str | None:
    """Stringify value if truthy, otherwise return None."""
    if x:
        return str(x)
    return None


def _floor_1min(x: datetime) -> datetime:
    """Truncate seconds and microseconds from datetime object."""
    return x - timedelta(seconds=x.second, microseconds=x.microsecond)


def _time_windows(
    start_at: datetime, end_at: datetime, step: timedelta
) -> Iterator[tuple[datetime, datetime]]:
    """Constructs ordered time windows between start_at and end_at of size step.

    Parameters
    ----------
    start_at
        time at which first window should begin, inclusive.
    end_at
        time at which last window should end, inclusive, if end_at - start_at is evenly
        divisible by step

    Yields
    ------
    tuple[window_start_at, window_end_at]
        indicates bounds of each window where start_at <= window_start_at < end_at and
        start_at < window_end_at <= end_at
    """
    next_start_at = start_at
    next_end_at = next_start_at + step
    while next_end_at <= end_at:
        yield (next_start_at, next_end_at)
        next_start_at = next_end_at
        next_end_at = next_start_at + step


def main(
    triggered_at: datetime,
    queue_client: queue.QueueClient,
    spire_client: spire.SpireAPIClient,
    state_client: state.PersistentStateClient,
) -> None:
    """Entrypoint responsible for data ingress and checkpointing progress."""
    logger.info(f"Triggered at: {triggered_at.isoformat()}")
    do_not_sync_after = triggered_at - SYNC_DELAY

    last_sync_end_at = state_client.get_last_sync_end_at()

    start_at = _floor_1min(last_sync_end_at)
    end_at = _floor_1min(do_not_sync_after)
    logger.info(f"Syncing between: [{start_at.isoformat()}, {end_at.isoformat()})")

    for batch_start_at, batch_end_at in _time_windows(
        start_at=start_at,
        end_at=end_at,
        step=timedelta(minutes=5),
    ):
        logger.debug(f"Fetching: [{start_at.isoformat()}, {end_at.isoformat()})")
        spire_df = spire_client.get_data_between(batch_start_at, batch_end_at)

        # Retain records when aircraft is not on ground. on_ground is a nullable boolean
        # type which may be nan if unknown.
        is_on_ground = spire_df["on_ground"].fillna(False)
        drop_count_on_ground = is_on_ground.sum()
        if drop_count_on_ground > 0:
            logger.info(f"Drop {drop_count_on_ground} records on ground")
        is_flying = ~is_on_ground
        spire_df = spire_df.loc[is_flying, :]

        spire_df = spire_df.sort_values(["icao_address", "timestamp"])

        # TODO: downsample by icao_address to first/last TIMESTAMP ob per minute

        logger.info(f"Publishing position records: {len(spire_df)}")
        for icao_address, rows in spire_df.groupby("icao_address"):
            row = rows.iloc[0]
            dto = schemas.SpireWaypointRecords(
                flight_info=schemas.SpireFlightInfo(
                    icao_address=str(row["icao_address"]),
                    flight_id=_to_string_or_none(row["flight_id"]),
                    callsign=str(row["callsign"]),
                    tail_number=str(row["tail_number"]),
                    flight_number=(row["flight_number"]),
                    aircraft_type_icao=str(row["aircraft_type_icao"]),
                    airline_iata=str(row["airline_iata"]),
                    departure_airport_icao=str(row["departure_airport_icao"]),
                    departure_scheduled_time=str(row["departure_scheduled_time"]),
                    arrival_airport_icao=str(row["arrival_airport_icao"]),
                    arrival_scheduled_time=str(row["arrival_scheduled_time"]),
                ),
                records=[
                    schemas.SpireWaypointPositional(
                        ingestion_time=str(row["ingestion_time"]),
                        timestamp=str(row["timestamp"]),
                        latitude=float(row["latitude"]),
                        longitude=float(row["longitude"]),
                        source=str(row["source"]),
                        collection_type=str(row["collection_type"]),
                        altitude_baro=float(row["altitude_baro"]),
                    )
                    for _, row in rows.iterrows()
                ],
            )

            data = dto.as_utf8_json()
            ordering_key = str(icao_address)
            queue_client.publish_async(data, ordering_key)

        queue_client.wait_for_publish()
        logger.info(f"Published records successfully: {len(spire_df)}")

        state_client.set_last_sync_end_at(batch_end_at)
        last_sync_end_at = batch_end_at


if __name__ == "__main__":
    from . import environment, log

    log.logger.info("Starting spire-ingest-api-scraper service")

    triggered_at = datetime.now(tz=timezone.utc)

    queue_client = queue.QueueClient(environment.PUBSUB_EGRESS_TOPIC_ID)
    spire_client = spire.SpireAPIClient(environment.SPIRE_API_TOKEN)
    state_client = state.PersistentStateClient(
        environment.FIRESTORE_STATE_COLLECTION,
        environment.FIRESTORE_STATE_DOC_ID,
    )

    main(
        triggered_at=triggered_at,
        queue_client=queue_client,
        spire_client=spire_client,
        state_client=state_client,
    )

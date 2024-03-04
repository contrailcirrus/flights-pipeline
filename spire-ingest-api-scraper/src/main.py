import json
import logging
from collections.abc import Iterator
from datetime import datetime, timedelta, timezone
from typing import Any

from . import queue, spire, state

logger = logging.getLogger(__name__)


# WALL_TIME sets duration to wait before syncing, assuming that API requests for data
# before (now - WALL_TIME) will return immutable responses.
WALL_TIME = timedelta(minutes=5)


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

    Args:
        start_at: time at which first window should begin, inclusive.
        end_at: time at which last window should end, inclusive, if end_at - start_at is
            evenly divisible by step

    Yields:
        tuple[window_start_at, window_end_at] indicating bounds of each window where
            start_at <= window_start_at < end_at and start_at < window_end_at <= end_at.
    """
    next_start_at = start_at
    next_end_at = next_start_at + step
    while next_start_at < end_at and next_end_at <= end_at:
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
    do_not_sync_after = triggered_at - WALL_TIME

    last_sync_end_at = state_client.get_last_sync_end_at()
    logger.info(f"Last sync end checkpoint: {last_sync_end_at.isoformat()}")

    start_at = _floor_1min(last_sync_end_at)
    end_at = _floor_1min(do_not_sync_after)
    logger.info(f"Syncing between: [{start_at.isoformat()}, {end_at.isoformat()})")

    # TODO: between 1 minute and 5 minute batches. 5 minute triggered server errors from
    # spire API during testing.
    for batch_start_at, batch_end_at in _time_windows(
        start_at=start_at,
        end_at=end_at,
        step=timedelta(minutes=1),
    ):
        logger.debug(f"Fetching: [{start_at.isoformat()}, {end_at.isoformat()})")
        spire_df = spire_client.get_data_between(batch_start_at, batch_end_at)

        # Retain records when aircraft is not on ground. on_ground is a nullable boolean
        # type which may be nan if unknown.
        is_flying = ~spire_df["on_ground"].fillna(False)
        spire_df = spire_df.loc[~is_flying, :]

        spire_df = spire_df.sort_values(["icao_address", "timestamp"])
        logger.debug(f"Publishing position records: {len(spire_df)}")
        for icao_address, rows in spire_df.groupby("icao_address"):
            dtos = [
                # TODO: serialize as declarative typed object. do we have shared
                # serialization methods?
                dict(
                    flight_id=_to_string_or_none(row["flight_id"]),
                    icao_address=str(row["icao_address"]),
                    timestamp=str(row["timestamp"]),
                    latitude=float(row["latitude"]),
                    longitude=float(row["longitude"]),
                    # TODO: altitude key missing
                    # altitude=float(row["altitude_baro"]),
                    aircraft_type_icao=str(row["aircraft_type_icao"]),
                    aircraft_type_name=str(row["aircraft_type_name"]),
                )
                for _, row in rows.iterrows()
            ]
            data = json.dumps(dtos).encode("utf-8")
            ordering_key = str(icao_address)
            queue_client.publish_async(data, ordering_key)

        queue_client.wait_for_publish()
        logger.debug(f"Published records successfully: {len(spire_df)}")

        state_client.set_last_sync_end_at(batch_end_at)
        logger.debug(f"Updated last sync endcheckpoint: {batch_end_at.isoformat()}")
        last_sync_end_at = batch_end_at


if __name__ == "__main__":
    from . import environment

    logging.basicConfig(level=environment.LOG_LEVEL)

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

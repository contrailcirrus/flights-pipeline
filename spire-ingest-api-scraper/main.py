"""
Entrypoint for spire-ingest-api-scraper CronJob.
"""

import sys
from collections.abc import Iterator
from datetime import datetime, timedelta, timezone
from typing import Any

import pandas as pd

from lib import queue, schemas, spire, state, transform, utils
from lib.log import format_traceback, logger

# SYNC_DELAY enforces we do not fetch data ingested by Spire after: now - SYNC_DELAY
SYNC_DELAY = timedelta(minutes=5)


def _to_str_or_none(x: Any) -> str | None:
    """Cast to string if truthy, otherwise return None."""
    if x and not pd.isnull(x):
        return str(x)
    return None


def _to_int_or_none(x: Any) -> int | None:
    """Cast to int if truthy, otherwise return None."""
    if x and not pd.isnull(x):
        return int(x)
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
        divisible by step. If end_at - start_at is not evenly divisible by step, the
        last window returned will be:
            [start_at + (n) * step, start_at + (n + 1) * step)
        where (start_at + (n + 1) * step) < end_at. In other words, all windows will be
        of length step and no partial windows will be returned.

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


def _log_invariant_violations(df: pd.DataFrame) -> None:
    """Log warning if expected-static fields contain multiple unique values."""
    static_fields = [
        "flight_id",
        "callsign",
        "tail_number",
        "flight_number",
        "aircraft_type_icao",
        "airline_iata",
        "departure_airport_icao",
        "departure_scheduled_time",
        "arrival_airport_icao",
        "arrival_scheduled_time",
    ]
    for column in static_fields:
        values = df[column].unique()
        if len(values) > 1:
            values_str = ", ".join(str(v) for v in values)
            logger.warning(
                "Assumed static values are not unique. "
                + f"Column: {column}"
                + f"Values: {values_str}"
            )


def main(
    triggered_at: datetime,
    egress_queue_client: queue.QueueClient,
    bq_queue_client: queue.QueueClient,
    sigterm_handler: utils.SigtermHandler,
    spire_client: spire.SpireAPIClient,
    state_client: state.PersistentStateClient,
) -> None:
    """Entrypoint responsible for data ingress and checkpointing progress."""
    logger.info(f"Triggered at: {triggered_at.isoformat()}")
    do_not_sync_after = triggered_at - SYNC_DELAY

    last_sync_end_at = state_client.get_last_sync_end_at()

    start_at = _floor_1min(last_sync_end_at)
    end_at = _floor_1min(do_not_sync_after)
    step = timedelta(minutes=5)

    if (end_at - start_at) < step:
        logger.info(
            "Insufficient time elapsed since last trigger. "
            + f"Must wait at least {step.seconds} seconds."
        )
        return

    for batch_start_at, batch_end_at in _time_windows(
        start_at=start_at,
        end_at=end_at,
        step=step,
    ):
        if sigterm_handler.should_exit:
            sys.exit(0)

        logger.debug(f"Fetching: [{start_at.isoformat()}, {end_at.isoformat()})")
        spire_df, tardy_df = spire_client.get_data_between(batch_start_at, batch_end_at)
        logger.info(
            f"Fetched {len(spire_df)} target records, and {len(tardy_df)} tardy records."
        )

        spire_df = transform.filter_ingest_rules(spire_df)
        tardy_df = transform.filter_ingest_rules(tardy_df)

        logger.info(
            f"Publishing {len(spire_df)} target records and {len(tardy_df)} tardy records."
        )

        # ----------------
        # publish tardy records
        # ---------------
        tardy_df = tardy_df.sort_values(["icao_address", "timestamp"])
        for icao_address, rows in tardy_df.groupby("icao_address"):
            _log_invariant_violations(rows)

            first_row = rows.iloc[0]

            dto = schemas.SpireWaypointsRecord(
                flight_info=schemas.SpireFlightInfo(
                    icao_address=str(first_row["icao_address"]),
                    flight_id=_to_str_or_none(first_row["flight_id"]),
                    callsign=_to_str_or_none(first_row["callsign"]),
                    tail_number=_to_str_or_none(first_row["tail_number"]),
                    flight_number=_to_str_or_none(first_row["flight_number"]),
                    aircraft_type_icao=_to_str_or_none(first_row["aircraft_type_icao"]),
                    airline_iata=_to_str_or_none(first_row["airline_iata"]),
                    departure_airport_icao=_to_str_or_none(
                        first_row["departure_airport_icao"]
                    ),
                    departure_scheduled_time=_to_str_or_none(
                        first_row["departure_scheduled_time"]
                    ),
                    arrival_airport_icao=_to_str_or_none(
                        first_row["arrival_airport_icao"]
                    ),
                    arrival_scheduled_time=_to_str_or_none(
                        first_row["arrival_scheduled_time"]
                    ),
                ),
                records=[
                    schemas.SpireWaypointPositional(
                        ingestion_time=str(row["ingestion_time"]),
                        timestamp=str(row["timestamp"]),
                        latitude=float(row["latitude"]),
                        longitude=float(row["longitude"]),
                        collection_type=str(row["collection_type"]),
                        altitude_baro=int(row["altitude_baro"]),
                        imputed=False,
                        flight_level=None,
                    )
                    for _, row in rows.iterrows()
                ],
            )
            for raw_bq_json_ln in dto.to_bq_flatmap():
                bq_queue_client.publish_async(raw_bq_json_ln)
            bq_queue_client.wait_for_publish()

        del tardy_df

        # ----------------
        # publish on-time records
        # ---------------
        spire_df = spire_df.sort_values(["icao_address", "timestamp"])
        for icao_address, rows in spire_df.groupby("icao_address"):
            _log_invariant_violations(rows)

            first_row = rows.iloc[0]

            dto = schemas.SpireWaypointsRecord(
                flight_info=schemas.SpireFlightInfo(
                    icao_address=str(first_row["icao_address"]),
                    flight_id=_to_str_or_none(first_row["flight_id"]),
                    callsign=_to_str_or_none(first_row["callsign"]),
                    tail_number=_to_str_or_none(first_row["tail_number"]),
                    flight_number=_to_str_or_none(first_row["flight_number"]),
                    aircraft_type_icao=_to_str_or_none(first_row["aircraft_type_icao"]),
                    airline_iata=_to_str_or_none(first_row["airline_iata"]),
                    departure_airport_icao=_to_str_or_none(
                        first_row["departure_airport_icao"]
                    ),
                    departure_scheduled_time=_to_str_or_none(
                        first_row["departure_scheduled_time"]
                    ),
                    arrival_airport_icao=_to_str_or_none(
                        first_row["arrival_airport_icao"]
                    ),
                    arrival_scheduled_time=_to_str_or_none(
                        first_row["arrival_scheduled_time"]
                    ),
                ),
                records=[
                    schemas.SpireWaypointPositional(
                        ingestion_time=str(row["ingestion_time"]),
                        timestamp=str(row["timestamp"]),
                        latitude=float(row["latitude"]),
                        longitude=float(row["longitude"]),
                        collection_type=str(row["collection_type"]),
                        altitude_baro=int(row["altitude_baro"]),
                        imputed=False,
                        flight_level=None,
                    )
                    for _, row in rows.iterrows()
                ],
            )

            data = dto.as_utf8_json()
            ordering_key = f"api-scraper:{icao_address}"
            egress_queue_client.publish_async(data, ordering_key)

        egress_queue_client.wait_for_publish()
        logger.info(f"Published records successfully: {len(spire_df)}")

        state_client.set_last_sync_end_at(batch_end_at)
        last_sync_end_at = batch_end_at


if __name__ == "__main__":
    try:
        from lib import environment

        logger.info("Starting spire-ingest-api-scraper service")

        triggered_at = datetime.now(tz=timezone.utc)

        egress_queue_client = queue.QueueClient(
            environment.PUBSUB_EGRESS_TOPIC_ID,
            ordered_queue=True,
        )
        bq_queue_client = queue.QueueClient(
            environment.SPIRE_RAW_WAYPOINTS_BIGQUERY_TOPIC_ID,
            ordered_queue=False,
        )
        sigterm_handler = utils.SigtermHandler()
        spire_client = spire.SpireAPIClient(environment.SPIRE_API_TOKEN)
        state_client = state.PersistentStateClient(
            environment.FIRESTORE_STATE_DB,
            environment.FIRESTORE_STATE_COLLECTION,
            environment.FIRESTORE_STATE_DOC_ID,
        )

        main(
            triggered_at=triggered_at,
            egress_queue_client=egress_queue_client,
            bq_queue_client=bq_queue_client,
            sigterm_handler=sigterm_handler,
            spire_client=spire_client,
            state_client=state_client,
        )
    except Exception:
        logger.error("Unhandled exception:" + format_traceback())
        sys.exit(1)

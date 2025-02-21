"""
Entrypoint for spire-ingest-api-scraper CronJob.
"""

import asyncio
import sys
import time
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


def _floor_1min(x: datetime) -> datetime:
    """Truncate seconds and microseconds from datetime object."""
    return x - timedelta(seconds=x.second, microseconds=x.microsecond)


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
        non_nan_values = [v for v in values if not pd.isna(v)]
        if len(non_nan_values) > 1:
            values_str = ", ".join(str(v) for v in values)
            logger.warning(
                "Assumed static values are not unique. "
                + f"Column: {column} "
                + f"Values: {values_str}"
            )


async def main(
    triggered_at: datetime,
    bq_queue_client: queue.QueueClient,
    sigterm_handler: utils.SigtermHandler,
    spire_client: spire.SpireAPIClient,
    state_client: state.PersistentStateClient,
) -> None:
    """Entrypoint responsible for data ingress and checkpointing progress."""
    logger.info(f"Triggered at: {triggered_at.isoformat()}")
    do_not_sync_after = triggered_at - SYNC_DELAY

    last_sync_end_at = state_client.get_last_sync_end_at()
    time_since_last_sync_at = triggered_at - last_sync_end_at
    if time_since_last_sync_at > timedelta(hours=1):
        logger.warning(f"Spire checkpoint behind by: {time_since_last_sync_at}")

    start_at = _floor_1min(last_sync_end_at)
    end_at = _floor_1min(do_not_sync_after)
    step = timedelta(minutes=5)

    if (end_at - start_at) < step:
        logger.info(
            "Insufficient time elapsed since last trigger. "
            + f"Must wait at least {step.seconds} seconds."
        )
        return

    # handle work sequentially in uniform batches of `step` width
    for batch_start_at, batch_end_at in utils.time_windows(start_at, end_at, step):
        if sigterm_handler.should_exit:
            sys.exit(0)

        time_start = time.time()
        logger.info(
            f"Fetching: [{batch_start_at.isoformat()}, {batch_end_at.isoformat()})"
        )
        spire_df = await spire_client.get_data_between(batch_start_at, batch_end_at)

        spire_df = transform.filter_ingest_rules(spire_df)

        logger.info(f"Publishing {len(spire_df)} records to BQ.")

        # ----------------
        # publish records
        # ---------------
        spire_df = spire_df.sort_values(["icao_address", "timestamp"])
        for ix, row in spire_df.groupby("icao_address"):
            # _log_invariant_violations(rows)

            dto = schemas.SpireWaypointsRecord(
                flight_info=schemas.SpireFlightInfo(
                    icao_address=str(row["icao_address"]),
                    flight_id=_to_str_or_none(row["flight_id"]),
                    callsign=_to_str_or_none(row["callsign"]),
                    tail_number=_to_str_or_none(row["tail_number"]),
                    flight_number=_to_str_or_none(row["flight_number"]),
                    aircraft_type_icao=_to_str_or_none(row["aircraft_type_icao"]),
                    airline_iata=_to_str_or_none(row["airline_iata"]),
                    departure_airport_icao=_to_str_or_none(
                        row["departure_airport_icao"]
                    ),
                    departure_scheduled_time=_to_str_or_none(
                        row["departure_scheduled_time"]
                    ),
                    arrival_airport_icao=_to_str_or_none(row["arrival_airport_icao"]),
                    arrival_scheduled_time=_to_str_or_none(
                        row["arrival_scheduled_time"]
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
                ],
            )
            for raw_bq_json_ln in dto.to_bq_flatmap(
                source_id="spire",
            ):
                bq_queue_client.publish_async(
                    data=raw_bq_json_ln,
                    timeout_seconds=110,
                    log_context=dict(
                        client_name="bq_queue_client",
                        icao_address=dto.flight_info.icao_address,
                        batch_first_ts=dto.records[0].timestamp,
                    ),
                )

        bq_queue_client.wait_for_publish(timeout_seconds=120)
        logger.info(f"Published {len(spire_df)} records successfully.")

        state_client.set_last_sync_end_at(batch_end_at)

        time_end = time.time()
        elapsed_seconds = time_end - time_start
        logger.info(f"Completed job after {elapsed_seconds:.1f} s")


if __name__ == "__main__":
    try:
        from lib import environment

        logger.info("Starting spire-ingest-api-scraper service")

        triggered_at = datetime.now(tz=timezone.utc)

        bq_queue_client = queue.QueueClient(
            topic_id=environment.SPIRE_RAW_WAYPOINTS_BIGQUERY_TOPIC_ID,
            ordered_queue=False,
        )
        sigterm_handler = utils.SigtermHandler()
        spire_client = spire.SpireAPIClient(environment.SPIRE_API_TOKEN)
        state_client = state.PersistentStateClient(
            environment.FIRESTORE_STATE_DB,
            environment.FIRESTORE_STATE_COLLECTION,
            environment.FIRESTORE_STATE_DOC_ID,
        )

        asyncio.run(
            main(
                triggered_at=triggered_at,
                bq_queue_client=bq_queue_client,
                sigterm_handler=sigterm_handler,
                spire_client=spire_client,
                state_client=state_client,
            )
        )
    except Exception:
        logger.error("Unhandled exception:" + format_traceback())
        sys.exit(1)

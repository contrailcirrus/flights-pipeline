"""Entrypoint for the Spire Ingest Resample Worker."""

import lib.environment as env
from lib.log import logger, format_traceback
import stub  # temp
from lib.schemas import (
    SpireWaypointsRecord,
    WaypointCache,
)
from lib.handlers import ValidationHandler


def run():
    """
    Main entrypoint.

    - Dequeues a "waypoints record" (batch window of waypoints) for a given flight-instance.
    - Fetches the last known 1-2 waypoint(s) for the flight-instance from remote cache.
    - Interpolates backwards (1Min sampling) for missing waypoints between
    the waypoint record and the last known waypoint.
    - Publishes the interpolated waypoints to a pubsub topic (egress to Big Query)
    - Builds flight segments (tuple of consecutive waypoints),
      and publishes flight segments to pubsub
    - Updates the last known 1-2 waypoint(s) for the flight-instance in remote cache
    """
    logger.info(f"fetching record from {env.SPIRE_INGEST_WAYPOINTS_SUBSCRIPTION_ID}")
    # TODO: fetch from subscription
    # TODO: init lease management on ack

    # STUBBED
    job = SpireWaypointsRecord.from_utf8_json(stub.pubsub_message)
    cached = WaypointCache.from_flatmap(stub.redis_response)

    # cases where we don't process the batch window received from pubsub
    try:
        validation_handler = ValidationHandler(cached, job)
    except Exception:
        logger.warning(
            f"cache and/or records invalid. "
            f"not processing batch with icao_address {job.flight_info.icao_address} "
            f"and timestamp {job.records[0].timestamp}. "
            f"traceback: {format_traceback()}"
        )
        return
    if not validation_handler.flight_info:
        logger.warning(
            f"no flight_id available in records batch, "
            f"and flight_id could not be inferred. "
            f"not processing batch with icao_address {job.flight_info.icao_address} "
            f"and timestamp {job.records[0].timestamp}."
        )
        return

    # TODO: do backward interpolation
    # TODO: infer spire.flight-id for records with spire.flight-id.is_null()
    logger.info(f"interpolation complete. generated N={100} new waypoints.")

    # TODO: publish interpolated waypoints to pubsub topic, for injection into BQ
    logger.info(
        f"published N={100} interpolated (imputed) waypoints to "
        f"{env.SPIRE_WAYPOINTS_BIGQUERY_TOPIC_ID}"
    )

    # TODO: generate flight segments; publish flight segments to pubsub
    logger.info(
        f"published N={103} flight segments to {env.SPIRE_FLIGHT_SEGMENTS_TOPIC_ID}"
    )


if __name__ == "__main__":
    logger.info("starting spire-ingest-resample-worker instance")
    while True:
        run()

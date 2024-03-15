"""Entrypoint for the Spire Ingest Resample Worker."""

import sys

from datetime import datetime

import lib.environment as env
from lib.log import logger, format_traceback
from lib.schemas import (
    SpireWaypointsRecord,
    SpireWaypointPositional,
    SpireFlightInfo,
    WaypointCache,
)
from lib.handlers import (
    PubSubSubscriptionHandler,
    CacheHandler,
    ValidationHandler,
    ResampleHandler,
)


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

    cache_handler = CacheHandler(env.REDIS_HOST, env.REDIS_PORT)

    logger.info(f"fetching record from {env.SPIRE_INGEST_WAYPOINTS_SUBSCRIPTION_ID}")
    with PubSubSubscriptionHandler(
        env.SPIRE_INGEST_WAYPOINTS_SUBSCRIPTION_ID
    ) as job_handler:
        job: SpireWaypointsRecord = job_handler.fetch()
        logger.info(f"got job: {job}.")

        cache_key = f"spr: {job.flight_info.icao_address}"
        logger.info(f"fetching from cache to {env.REDIS_HOST}:{env.REDIS_PORT}")
        try:
            cached: list[WaypointCache.Waypoint] = cache_handler.pull(cache_key)
        except Exception:
            logger.error(
                f"failed to fetch record from cache. exiting... "
                f"traceback: {format_traceback()}"
            )
            # TODO: choose preference here
            # either exit w. code 1 (avoiding thrashing logs), so we have error level logs on the
            # k8s infra log-stream
            # - or - perpetual backoff and wait to parent loop, relying on error-level alert in
            # application/service log stream
            sys.exit(1)

        if cached:
            logger.info(
                f"cache hit. found {len(cached)} prior waypoints "
                f"for icao_address {job.flight_info.icao_address}, "
                f"at {datetime.fromtimestamp(cached[-1]['timestamp']).isoformat()}."
                f"interpolating until {job.records[0].timestamp}."
            )
        else:
            logger.info(
                f"cache miss. no prior waypoint(s) found for icao_address "
                f"{job.flight_info.icao_address} at {job.records[0].timestamp}"
            )

        # cases where we don't process the batch window received from pubsub
        try:
            validation_handler = ValidationHandler(cached, job)
            validated_cache: list[SpireWaypointPositional] = (
                validation_handler.cached_records
            )
            validated_records: list[SpireWaypointPositional] = (
                validation_handler.records
            )
            validated_flight_info: SpireFlightInfo | None = (
                validation_handler.flight_info
            )
        except Exception:
            logger.warning(
                f"cache and/or records invalid. "
                f"not processing batch with icao_address {job.flight_info.icao_address} "
                f"and timestamp {job.records[0].timestamp}. "
                f"traceback: {format_traceback()}"
            )
            job_handler.ack()
            return
        if not validated_flight_info:
            logger.warning(
                f"no flight_id available in records batch, "
                f"and flight_id could not be inferred. "
                f"not processing batch with icao_address {job.flight_info.icao_address} "
                f"and timestamp {job.records[0].timestamp}."
            )
            job_handler.ack()
            return

        # apply resampling
        try:
            transform_handler = ResampleHandler(validated_cache, validated_records)
            transform_handler.interpolate()
            resampled_records: list[SpireWaypointPositional] = (
                transform_handler.waypoints_resampled
            )
        except Exception:
            logger.error(
                f"failed to interpolate. "
                f"batch will not be ack'ed from queue "
                f"for icao_address: {job.flight_info.icao_address}."
                f"traceback: {format_traceback()}"
            )
            sys.exit(1)

        egress_records = SpireWaypointsRecord(  # noqa:F841
            flight_info=validated_flight_info,
            records=resampled_records,
        )

        logger.info(
            f"published N={len(resampled_records)} interpolated (imputed) waypoints to "
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

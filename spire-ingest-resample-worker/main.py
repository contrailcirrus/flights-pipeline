"""Entrypoint for the Spire Ingest Resample Worker."""

import lib.environment as env
from lib.log import logger, format_traceback
import stub  # temp
from lib.schemas import (
    SpireWaypointsRecord,
    WaypointCache,
    SpireWaypointPositional,
    SpireFlightInfo,
)
from lib.helpers import verify_temporal_order, is_same_flight_instance


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
    flight_info: SpireFlightInfo = job.flight_info
    records: list[SpireWaypointPositional] = job.records
    logger.info(f"got SpireWaypointsRecord: {job.as_utf8_json()}")  # noqa:F821

    # TODO: fetch last known waypoint for flight-instance from remote store
    cached = WaypointCache.from_flatmap(stub.redis_response)
    cached = [
        w for w in cached if w is not None
    ]  # prune null WaypointCache.Waypoint objs
    cached_flight_ids: list[str] = [
        SpireWaypointsRecord.from_waypoint_cache(w)[0] for w in cached
    ]
    cached_waypoints: list[SpireWaypointPositional] = [
        SpireWaypointsRecord.from_waypoint_cache(w)[1] for w in cached
    ]
    logger.info(f"last known waypoint was at: {'some_timestamp'}")

    # verify and handle preconditions for cached waypoints
    if cached_waypoints:
        # 1) verify we don't have out-of-order message delivery; skip this batch if so
        try:
            verify_temporal_order(cached_waypoints[-1], records[0], flight_info)
        except Exception:
            logger.error(
                f"records out of order. skipping this batch. "
                f"traceback: {format_traceback()}"
            )
            return

        # 2) invalidate cache if it was from a previous flight instance
        if not is_same_flight_instance(
            cached_flight_ids[-1],
            flight_info.flight_id,
            cached_waypoints[-1],
            records[0],
            flight_info,
        ):
            cached_waypoints = []

        # 3) verify batch has a flight_id if none is available from cache; skip this batch if so
        if not cached_waypoints and not flight_info.flight_id:
            # rare case
            # this should only occur if the first observed record for a new flight instance
            # is missing the flight_id value from Spire.
            # this would be the case if a new flight took off in an area that only has satellite
            # coverage (Spire satellite data omits the flight_id)
            logger.warning(
                f"cache is empty and flight_id in batch window is null. "
                f"icao_address {flight_info.icao_address} at {records[0].timestamp}. "
                f"skipping this batch."
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

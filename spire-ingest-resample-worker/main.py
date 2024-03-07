"""Entrypoint for the Spire Ingest Resample Worker."""

import lib.environment as env
from lib.log import logger
import stub  # temp
from lib.schemas import SpireWaypointsRecord


def run():
    """
    Main entrypoint.

    - Dequeues a "waypoint record" (list of waypoints) for a given flight-instance.
    - Fetches the last known waypoint for the flight-instance from remote store.
    - Interpolates backwards (1Min sampling) for missing waypoints between
    the waypoint record and the last known waypoint.
    - Publishes the interpolated waypoints to a pubsub topic
    - Builds flight segments (tuple of consecutive waypoints),
      and publishes flight segments to pubsub
    - Updates the last known waypoint for the flight-instance instance in remote store
    """
    logger.info(f"fetching record from {env.SPIRE_INGEST_WAYPOINTS_SUBSCRIPTION_ID}")
    # TODO: fetch from subscription
    # TODO: init lease management on ack

    # STUBBED
    job = SpireWaypointsRecord.from_utf8_json(stub.pubsub_message)
    logger.info(f"got SpireWaypointsRecord: {job.as_utf8_json()}")  # noqa:F821

    # TODO: fetch last known waypoint for flight-instance from remote store
    logger.info(f"last known waypoint was at: {'some_timestamp'}")

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

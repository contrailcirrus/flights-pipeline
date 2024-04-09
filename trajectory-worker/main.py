"""Entrypoint for the Spire Ingest Resample Worker."""

import sys
import time

import lib.environment as env
from lib import utils
from lib.handlers import (
    PubSubSubscriptionHandler,
)
from lib.log import format_traceback, logger
from lib.schemas import (
    SpireWaypointsRecord,
)


def run():
    """
    Main entrypoint.
    - Dequeue a set of waypoints (trajectory chunk)
    - Run cocip against trajectory
    - Export values (big query, other TBD)
    """

    with PubSubSubscriptionHandler(env.TRAJECTORY_CHUNK_SUBSCRIPTION_ID) as job_handler:
        # ===================
        # fetch records
        # ===================
        job: SpireWaypointsRecord = job_handler.fetch()
        if not job:
            # if the queue is empty -> we get back [], then pause before retry
            logger.info("job empty. sleeping... ")
            time.sleep(10)
            return

        logger.info(
            f"got job with {len(job.records)} records. "
            f"icao_address: {job.flight_info.icao_address}. "
            f"spanning: {job.records[0].timestamp} to {job.records[-1].timestamp}"
        )

        # ===================
        # apply CoCip Trajectory model
        # ===================
        # TODO

        # gs://contrails-301217-ecmwf-hres-forecast-v2-short-term
        zarr_store = env.HRES_SOURCE_PATH  # noqa:F841
        # job.records is the flight waypoints defining the trajectory chunk
        # job.flight_info is the flight time-invariant data (e.g. flight_info.aircraft type)

        # list of len(job.records) - 2; one cocip ef [J/segment] value
        cocip_output: list[float]  # noqa:F842

        time.sleep(500)
        job_handler.ack()


if __name__ == "__main__":
    logger.info("starting trajectory-worker instance")
    sigterm_handler = utils.SigtermHandler()
    while True:
        if sigterm_handler.should_exit:
            sys.exit(0)
        try:
            run()
        except Exception:
            logger.error("Unhandled exception:" + format_traceback())
            sys.exit(1)

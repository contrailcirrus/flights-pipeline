"""Entrypoint for the Spire Ingest Resample Worker."""

import sys

import lib.environment as env
from lib import utils
from lib.exceptions import AircraftTypeUnrecognizedError, FlightTooLowError
from lib.handlers import (
    CocipTrajectoryHandler,
    PubSubPublishHandler,
    PubSubSubscriptionHandler,
)
from lib.log import format_traceback, logger
from lib.schemas import CocipTrajectoryChunk, WaypointsRecord


def run() -> None:
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
        job: WaypointsRecord
        ordering_key: str
        job, ordering_key = job_handler.fetch()

        logger.info(
            f"got job with {len(job.records)} records. "
            f"icao_address: {job.flight_info.icao_address}. "
            f"spanning: {job.records[0].timestamp} to {job.records[-1].timestamp}"
        )

        # ===================
        # apply CoCip Trajectory model
        # ===================
        try:
            trajectory_cocip_handler = CocipTrajectoryHandler(job, env.HRES_SOURCE_PATH)
        except (FlightTooLowError, AircraftTypeUnrecognizedError) as e:
            logger.warning(
                f"skipping trajectory chunk "
                f"for icao_adddress {job.flight_info.icao_address} "
                f"with start_time {job.records[0].timestamp}."
                f"{e}"
            )
            job_handler.ack()
            return

        try:
            trajectory_cocip_handler.load()
            cocip_result = trajectory_cocip_handler.run()
        except Exception:
            logger.error(
                f"failed to run cocip "
                f"for icao_adddress {job.flight_info.icao_address} "
                f"with start_time {job.records[0].timestamp}."
                f"NACK'ing job."
                f"traceback: {format_traceback()}"
            )
            return

        # ===================
        # publish trajectory chunk model outputs to BQ
        # ===================
        output: CocipTrajectoryChunk = CocipTrajectoryChunk.from_cocip_result(
            source_id=ordering_key.split(":")[0],
            git_sha=env.GIT_SHA,
            input_chunk=job,
            result=cocip_result,
        )

        trajectory_cocip_bq_publisher = PubSubPublishHandler(
            topic_id=env.TRAJECTORY_COCIP_BQ_TOPIC_ID,
            ordered_queue=False,
        )
        trajectory_cocip_bq_publisher.publish_async(
            data=output.to_bq_flatmap(),
            timeout_seconds=45,
            log_context=dict(
                client_name="trajectory_cocip_bq_publisher",
                icao_address=output.icao_address,
                source_id=output.source_id,
                time_start=output.time_start,
            ),
        )
        trajectory_cocip_bq_publisher.wait_for_publish(timeout_seconds=60)

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

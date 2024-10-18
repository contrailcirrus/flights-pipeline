"""Entrypoint for the Trajectory Worker Job Factory."""

import sys

from lib.handlers import (
    PubSubPublishHandler,
    PubSubSubscriptionHandler,
)
from lib.schemas import (
    TrajectoryWorkerJobDescriptor,
)
from lib.utils import SigtermHandler
from lib.log import logger


def run(
    input_job_handler: PubSubSubscriptionHandler,
    output_job_handler: PubSubPublishHandler,
    sigterm_handler: SigtermHandler,
) -> None:
    """
    Main entrypoint.
    - Dequeue a Trajectory Worker Job Descriptor (TJWD)
    - Fetch ADS-B waypoints for the flight identified in the TJWD
    - Validate the flight instance, and resample waypoints
    - Package flight instance trajectory as a WaypointsRecord obj (traj worker job),
        and export to the trajectory worker job queue
    """

    for message in input_job_handler.subscribe():
        if sigterm_handler.should_exit:
            sys.exit(0)

        job = TrajectoryWorkerJobDescriptor.from_utf8_json(message.data)

        logger.info(f"got TJWD: {job.as_utf8_json}")

"""Entrypoint for the Trajectory Worker Job Factory."""

import sys
import hashlib

from lib.handlers import (
    PubSubSubscriptionHandler,
    PubSubPublishHandler,
    BigQueryHandler,
)
from lib.schemas import (
    TrajectoryWorkerJobDescriptor,
)
from lib.services import TrajectoryBuilderSvc
from lib.utils import SigtermHandler
from lib.log import logger, format_traceback

import lib.environment as env


def run(
    input_job_handler: PubSubSubscriptionHandler,
    sigterm_handler: SigtermHandler,
    job_builder_svc: TrajectoryBuilderSvc,
) -> None:
    """
    Main entrypoint.
    """

    for message in input_job_handler.subscribe():
        if sigterm_handler.should_exit:
            sys.exit(0)

        job = TrajectoryWorkerJobDescriptor.from_utf8_json(message.data)
        job_hash = hashlib.shake_128(job.as_utf8_json()).hexdigest(
            8
        )  # useful for keying in logs
        logger.info(f"got TJWD {job_hash}: {job.as_utf8_json}")
        job_builder_svc.run(job)

        input_job_handler.ack(message)
        logger.info(f"successfully processed TJWD {job_hash}: {job.as_utf8_json()}")


if __name__ == "__main__":
    logger.info("starting trajectory-worker-job-factory instance")

    try:
        input_job_handler = PubSubSubscriptionHandler(
            env.TWJD_SUBSCRIPTION_ID,
        )
        sigterm_handler = SigtermHandler()

        bq_handler = BigQueryHandler()
        output_job_handler = PubSubPublishHandler(
            topic_id=env.TRAJECTORY_CHUNK_TOPIC_ID,
            ordered_queue=False,
        )
        job_builder_svc = TrajectoryBuilderSvc(
            bq_handler=bq_handler,
            job_out_handler=output_job_handler,
        )

        run(
            input_job_handler=input_job_handler,
            sigterm_handler=sigterm_handler,
            job_builder_svc=job_builder_svc,
        )

    except Exception:
        logger.error("Unhandled exception:" + format_traceback())
        sys.exit(1)

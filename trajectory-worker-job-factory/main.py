"""Entrypoint for the Trajectory Worker Job Factory."""

import sys
import hashlib

from dataclasses import asdict

from pycontrails.datalib.spire import ValidateTrajectoryHandler

from lib.handlers import (
    PubSubSubscriptionHandler,
    PubSubPublishHandler,
    BigQueryHandler,
    HealTrajectoryHandler,
    RedisHandler,
    CloudStorageHandler,
)
from lib.schemas import (
    TrajectoryWorkerJobDescriptor,
)
from lib.services import TrajectoryBuilderSvc
from lib.log import logger, format_traceback
from lib.exceptions import PermanentFailureException
import lib.environment as env
from lib.utils import sigterm_manager


def run(
    input_job_handler: PubSubSubscriptionHandler,
    job_builder_svc: TrajectoryBuilderSvc,
) -> None:
    """
    Main entrypoint.
    """

    for message in input_job_handler.subscribe():
        if sigterm_manager.should_exit:
            sys.exit(0)

        job = TrajectoryWorkerJobDescriptor.from_utf8_json(message.data)
        job_hash = hashlib.shake_128(job.as_utf8_json()).hexdigest(
            8
        )  # useful for keying in logs
        logger.info("start twjd", extra={"job_hash": job_hash, "twjd": asdict(job)})

        try:
            job_builder_svc.run(twjd=job)
            logger.info("end twjd", extra={"job_hash": job_hash, "twjd": asdict(job)})
        except PermanentFailureException as e:
            # ack message; avoid pubsub redelivery
            logger.error(
                "permanently failed to process twjd - acking msg",
                extra={
                    "job_hash": job_hash,
                    "twjd": asdict(job),
                    "errror": str(e),
                    "traceback": format_traceback(),
                },
            )
            input_job_handler.ack(message)
            continue
        except Exception as e:
            # nack message; expect pubsub to retry
            logger.error(
                "nacking",
                extra={
                    "job_hash": job_hash,
                    "detail": "failed to process twjd",
                    "twjd": asdict(job),
                    "error": str(e),
                    "traceback": format_traceback(),
                },
            )
            input_job_handler.nack(message)
            continue

        input_job_handler.ack(message)


if __name__ == "__main__":
    logger.debug("starting trajectory-worker-job-factory instance")

    try:
        cache_handler = RedisHandler(
            env.REDIS_HOST,
            env.REDIS_PORT,
        )
        input_job_handler = PubSubSubscriptionHandler(
            env.TWJD_SUBSCRIPTION_ID,
        )
        bq_handler = BigQueryHandler()
        heal_traj_handler = HealTrajectoryHandler(
            min_speed_m_s=ValidateTrajectoryHandler.INSTANTANEOUS_LOW_GROUND_SPEED_THRESHOLD_MPS,
            max_speed_m_s=ValidateTrajectoryHandler.INSTANTANEOUS_HIGH_GROUND_SPEED_THRESHOLD_MPS,
        )
        validate_traj_handler = ValidateTrajectoryHandler()
        # this field is missing when pulling data from the Spire parquet file cache
        validate_traj_handler.SCHEMA.pop("ingestion_time")
        gcs_handler = CloudStorageHandler()
        output_job_handler = PubSubPublishHandler(
            topic_id=env.TRAJECTORY_CHUNK_TOPIC_ID,
            ordered_queue=False,
        )
        job_builder_svc = TrajectoryBuilderSvc(
            cache_handler=cache_handler,
            bq_handler=bq_handler,
            gcs_handler=gcs_handler,
            heal_traj_handler=heal_traj_handler,
            validate_traj_handler=validate_traj_handler,
            job_out_handler=output_job_handler,
        )

        run(
            input_job_handler=input_job_handler,
            job_builder_svc=job_builder_svc,
        )

    except Exception:
        logger.error("unhandled exception", extra={"traceback": format_traceback()})
        sys.exit(0)

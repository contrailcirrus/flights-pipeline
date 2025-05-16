"""Entrypoint for the Trajectory Worker."""

import sys

import lib.environment as env
from lib import schemas
from lib.schemas import WaypointsRecord
from lib.utils import sigterm_manager
from lib.handlers import (
    CocipTrajectoryHandler,
    PubSubPublishHandler,
    PubSubSubscriptionHandler,
)
from lib.log import format_traceback, logger
from datetime import UTC, datetime


def run(
    trajectory_cocip_bq_publisher: PubSubPublishHandler,
    job_handler: PubSubSubscriptionHandler,
) -> None:
    """
    Main entrypoint.
    - Dequeue a set of waypoints (trajectory chunk)
    - Run cocip against trajectory
    - Export values (big query, other TBD)
    """
    for messages in job_handler.subscribe():
        if sigterm_manager.should_exit:
            sys.exit(0)

        # ===================
        # apply CoCip Trajectory model
        # ===================
        trajectory_cocip_handler = CocipTrajectoryHandler(
            messages, env.HRES_SOURCE_PATH, env.ERA5_SOURCE_PATH
        )

        # remove messages from queue that we know cannot be processed
        if trajectory_cocip_handler.unprocessable_messages:
            job_handler.ack(trajectory_cocip_handler.unprocessable_messages)

        if len(trajectory_cocip_handler.all_jobs) == 0:
            logger.warning("no flights to process. proceeding to next batch...")
            continue

        try:
            trajectory_cocip_handler.load()
            trajectory_cocip_handler.run()
        except Exception:
            logger.error(
                f"NACK'ing (pubsub retry)." f"cocip failed. " f"{format_traceback()}"
            )
            for msg in messages:
                job_handler.nack(msg)
            continue

        now = datetime.now(tz=UTC)

        # ===================
        # publish cocip outputs to BQ
        # ===================
        logger.debug("publishing cocip outputs to BQ.")

        job: WaypointsRecord
        for job in trajectory_cocip_handler.all_jobs:
            fq_zarr_uri: str = ""
            # qualify the zarr uri with the source type
            if job.met_source == schemas.MetSource.HRES:
                fq_zarr_uri = (
                    f"HRES/{'-'.join(trajectory_cocip_handler.hres_zarr_uris)}"
                )
            elif job.met_source == schemas.MetSource.ERA5:
                fq_zarr_uri = (
                    f"ERA5/{'-'.join(trajectory_cocip_handler.era5_zarr_uris)}"
                )

            output = schemas.CocipTrajectoryChunk.from_cocip_result(
                source_id=job.pubsub_message.ordering_key.split(":")[0],
                git_sha=env.GIT_SHA,
                input_chunk=job,
                zarr_uri=fq_zarr_uri,
                result=job.pycontrail_cocip_result,
            )

            trajectory_cocip_bq_publisher.publish_async(
                data=output.to_bq_flatmap(processed_at=now),
                timeout_seconds=110,
                log_context=dict(
                    client_name="trajectory_cocip_bq_publisher_traj_summary",
                    icao_address=output.icao_address,
                    source_id=output.source_id,
                    time_start=output.time_start,
                ),
            )

            # ===================
            # if enabled, publish all trajectory segments to BQ
            # ===================
            if job.export_cocip_trajectory:
                logger.debug("exporting per-segment cocip outputs to BQ.")
                seg_outputs = schemas.CocipTrajectoryChunk.from_cocip_result_all_segs(
                    source_id=job.pubsub_message.ordering_key.split(":")[0],
                    git_sha=env.GIT_SHA,
                    input_chunk=job,
                    zarr_uri=fq_zarr_uri,
                    result=job.pycontrail_cocip_result,
                )
                for seg in seg_outputs:
                    trajectory_cocip_bq_publisher.publish_async(
                        data=seg.to_bq_flatmap(processed_at=now),
                        timeout_seconds=110,
                        log_context=dict(
                            client_name="trajectory_cocip_bq_publisher_traj_per_seg",
                            icao_address=output.icao_address,
                            source_id=output.source_id,
                            time_start=output.time_start,
                        ),
                    )
        trajectory_cocip_bq_publisher.wait_for_publish(timeout_seconds=120)

        job_handler.ack(
            [job.pubsub_message for job in trajectory_cocip_handler.all_jobs]
        )


if __name__ == "__main__":
    logger.info("starting trajectory-worker instance")

    try:
        trajectory_cocip_bq_publisher = PubSubPublishHandler(
            topic_id=env.TRAJECTORY_COCIP_BQ_TOPIC_ID,
            ordered_queue=False,
        )
        job_handler = PubSubSubscriptionHandler(
            env.TRAJECTORY_CHUNK_SUBSCRIPTION_ID,
            max_msgs=env.N_JOBS,
            pull_timeout_sec=5,
            ack_extension_sec=30,
        )
        run(
            trajectory_cocip_bq_publisher=trajectory_cocip_bq_publisher,
            job_handler=job_handler,
        )

    except Exception:
        logger.error("Unhandled exception:" + format_traceback())
        sys.exit(1)

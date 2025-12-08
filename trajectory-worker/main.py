"""Entrypoint for the Trajectory Worker."""

import sys

import lib.environment as env
from lib import schemas
from lib.exceptions import FlightTooLowError, AircraftTypeUnrecognizedError
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
    backup_job_publisher: PubSubPublishHandler | None,
) -> None:
    """
    Main entrypoint.
    - Dequeue a set of waypoints (trajectory chunk)
    - Run cocip against trajectory
    - Export values (big query, other TBD)
    """
    for message in job_handler.subscribe():
        if sigterm_manager.should_exit:
            sys.exit(0)

        job = schemas.WaypointsRecord.from_utf8_json(message.data)

        if backup_job_publisher and message.delivery_attempt > 2:
            # pass message to backup queue to be processed by traj workers w/ more resources
            logger.info(
                f"Too many delivery attempts ({message.delivery_attempt}). "
                f"Forwarding to backup pipeline."
                f"airline_iata: {job.flight_info.airline_iata}"
                f"flight_id: {job.flight_info.flight_id}. "
                f"got job with {len(job.records)} records."
            )
            backup_job_publisher.publish_async(
                message.data,
                timeout_seconds=45,
                ordering_key=message.ordering_key,
            )
            backup_job_publisher.wait_for_publish(timeout_seconds=30)
            job_handler.ack(message)
            continue

        logger.info(
            f"airline_iata: {job.flight_info.airline_iata} "
            f"flight_id: {job.flight_info.flight_id}. "
            f"spanning: {job.records[0].timestamp} to {job.records[-1].timestamp} "
            f"got job with {len(job.records)} records."
        )

        # ===================
        # apply CoCip Trajectory model
        # ===================
        try:
            trajectory_cocip_handler = CocipTrajectoryHandler(
                job, env.HRES_SOURCE_PATH, env.ERA5_SOURCE_PATH
            )
        except (FlightTooLowError, AircraftTypeUnrecognizedError) as e:
            logger.warning(
                f"airline_iata: {job.flight_info.airline_iata}. "
                f"skipping {job.flight_info.flight_id}. "
                f"aircraft_type_icao: {job.flight_info.aircraft_type_icao}. "
                f"could not run cocip. "
                f"{e}"
            )
            job_handler.ack(message)
            continue

        try:
            trajectory_cocip_handler.load()
            cocip_result = trajectory_cocip_handler.run()
        except Exception:
            logger.error(
                f"NACK'ing (pubsub retry)."
                f"airline_iata: {job.flight_info.airline_iata}. "
                f"flight_id: {job.flight_info.flight_id}. "
                f"aircraft_type_icao: {job.flight_info.aircraft_type_icao}. "
                f"cocip failed. "
                f"{format_traceback()}"
            )
            job_handler.nack(message)
            continue

        now = datetime.now(tz=UTC)

        # ===================
        # publish cocip outputs to BQ
        # ===================
        logger.debug("publishing cocip outputs to BQ.")

        fq_zarr_uri: str
        # qualify the zarr uri with the source type
        if job.met_source == schemas.MetSource.HRES:
            fq_zarr_uri = f"HRES/{trajectory_cocip_handler.zarr_uri}"
        elif job.met_source == schemas.MetSource.ERA5:
            fq_zarr_uri = f"ERA5/{'-'.join(trajectory_cocip_handler.zarr_uri)}"
        else:
            raise ValueError("traj worker job met source not recognized")

        output = schemas.CocipTrajectoryChunk.from_cocip_result(
            source_id=message.ordering_key.split(":")[0],
            git_sha=env.GIT_SHA,
            input_chunk=job,
            zarr_uri=fq_zarr_uri,
            result=cocip_result,
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
        trajectory_cocip_bq_publisher.wait_for_publish(timeout_seconds=120)
        # ===================
        # if enabled, publish all trajectory segments to BQ
        # ===================
        if job.export_cocip_trajectory:
            logger.debug("exporting per-segment cocip outputs to BQ.")
            seg_outputs = schemas.CocipTrajectoryChunk.from_cocip_result_all_segs(
                source_id=message.ordering_key.split(":")[0],
                git_sha=env.GIT_SHA,
                input_chunk=job,
                zarr_uri=fq_zarr_uri,
                result=cocip_result,
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
        job_handler.ack(message)


if __name__ == "__main__":
    logger.info("starting trajectory-worker instance")

    try:
        trajectory_cocip_bq_publisher = PubSubPublishHandler(
            topic_id=env.TRAJECTORY_COCIP_BQ_TOPIC_ID,
            ordered_queue=False,
        )
        job_handler = PubSubSubscriptionHandler(env.TRAJECTORY_CHUNK_SUBSCRIPTION_ID)
        if env.TRAJECTORY_CHUNK_BACKUP_TOPIC_ID:
            backup_job_publisher = PubSubPublishHandler(
                env.TRAJECTORY_CHUNK_BACKUP_TOPIC_ID,
                ordered_queue=True,
            )
        else:
            backup_job_publisher = None
        run(
            trajectory_cocip_bq_publisher=trajectory_cocip_bq_publisher,
            job_handler=job_handler,
            backup_job_publisher=backup_job_publisher,
        )

    except Exception:
        logger.error("Unhandled exception:" + format_traceback())
        sys.exit(1)

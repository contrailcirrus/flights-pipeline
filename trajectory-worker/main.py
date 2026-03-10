"""Entrypoint for the Trajectory Worker."""

import sys

import pandas as pd
from google.oauth2 import service_account

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
from google.cloud import storage

SOURCE_ID = "flightsreport"
GCS_PARQUET_URI_TEMPLATE = (
    "trajectory-worker/trajectory-pq/{start_datehour}/{airline_iata}/{flight_id}.pq"
)
storage_credentials = service_account.Credentials.from_service_account_info(
    env.GCP_SVC_ACCT_KEY
)
gcs_client = storage.Client(credentials=storage_credentials)
gcs_bucket = gcs_client.bucket(env.GCS_BUCKET_NAME)


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
        # Set start and end timestamps for logging purposes
        job._start_time = job.records[0].timestamp
        job._end_time = job.records[-1].timestamp

        if backup_job_publisher and message.delivery_attempt > 2:
            # pass message to backup queue to be processed by traj workers w/ more resources
            logger.info(
                "too many delivery attempts - forwarding to backup pipeline.",
                extra={
                    "flight_id": {job.flight_info.flight_id},
                    "delivery_attempt": message.delivery_attempt,
                },
            )
            backup_job_publisher.publish_async(
                message.data,
                timeout_seconds=45,
            )
            backup_job_publisher.wait_for_publish(timeout_seconds=30)
            job_handler.ack(message)
            continue

        logger.info(
            "start work",
            extra={
                "flight_id": job.flight_info.flight_id,
                "len_records": len(job.records),
            },
        )

        # ===================
        # apply CoCip Trajectory model
        # ===================
        try:
            trajectory_cocip_handler = CocipTrajectoryHandler(job)
        except (FlightTooLowError, AircraftTypeUnrecognizedError) as e:
            logger.info(
                "skipping",
                extra={
                    "flight_id": job.flight_info.flight_id,
                    "detail": "could not run cocip",
                    "reason": e,
                },
            )
            job_handler.ack(message)
            continue

        try:
            trajectory_cocip_handler.load_gcs_zarr(
                env.HRES_SOURCE_PATH, env.ERA5_SOURCE_PATH
            )
            cocip_fleet_result = trajectory_cocip_handler.run()
            cocip_fleet_result_lookup = {
                flight.attrs["flight_id"]: flight for flight in cocip_fleet_result
            }
            target_flight_result = cocip_fleet_result_lookup[job.flight_info.flight_id]
        except Exception:
            logger.error(
                "nacking",
                extra={
                    "flight_id": job.flight_info.flight_id,
                    "traceback": format_traceback(),
                    "detail": "cocip failed",
                },
            )
            job_handler.nack(message)
            continue

        now = datetime.now(tz=UTC)

        # ===================
        # publish cocip outputs to BQ
        # ===================
        logger.debug(
            "publishing cocip summary output to bq",
            extra={
                "flight_id": job.flight_info.flight_id,
            },
        )

        fq_zarr_uri: str
        # qualify the zarr uri with the source type
        if job.met_source == schemas.MetSource.HRES:
            fq_zarr_uri = f"HRES/{trajectory_cocip_handler.zarr_uri}"
        elif job.met_source == schemas.MetSource.ERA5:
            fq_zarr_uri = f"ERA5/{'-'.join(trajectory_cocip_handler.zarr_uri)}"
        else:
            raise ValueError("traj worker job met source not recognized")

        output = schemas.CocipTrajectoryChunk.from_cocip_result(
            source_id=SOURCE_ID,
            git_sha=env.GIT_SHA,
            input_chunk=job,
            zarr_uri=fq_zarr_uri,
            result=target_flight_result,
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

        if job.export_cocip_trajectory:
            # ===================
            # if enabled, publish all trajectory segments to BQ
            # ===================
            logger.debug(
                "exporting per-segment cocip outputs to bq",
                extra={
                    "flight_id": job.flight_info.flight_id,
                },
            )

            seg_outputs = schemas.CocipTrajectoryChunk.from_cocip_result_all_segs(
                source_id=SOURCE_ID,
                git_sha=env.GIT_SHA,
                input_chunk=job,
                zarr_uri=fq_zarr_uri,
                result=target_flight_result,
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
            del seg_outputs
            # ===================
            # if enabled, publish trajectory segments to protobuf in GCS
            # ===================
            traj_proto: schemas.CocipTrajectoryProto
            traj_proto = schemas.CocipTrajectoryProto.from_cocip_results(
                input_chunk=job,
                fleet_results_lookup=cocip_fleet_result_lookup,
                model=trajectory_cocip_handler.model,
            )
            bytes_out = traj_proto.to_bytes()
            first_waypoint_ts = pd.Timestamp(job.records[0].timestamp)
            if job.flight_info.airline_iata is None:
                pq_uri_airline_iata = "null"
            else:
                pq_uri_airline_iata = job.flight_info.airline_iata
            destination_uri = GCS_PARQUET_URI_TEMPLATE.format(
                start_datehour=first_waypoint_ts.strftime("%Y%m%d%H"),
                airline_iata=pq_uri_airline_iata,
                flight_id=job.flight_info.flight_id,
            )
            gcs_blob = gcs_bucket.blob(destination_uri)
            gcs_blob.upload_from_string(
                bytes_out, content_type="application/x-protobuf"
            )

        trajectory_cocip_bq_publisher.wait_for_publish(timeout_seconds=120)
        job_handler.ack(message)
        logger.info(
            "end work",
            extra={
                "flight_id": job.flight_info.flight_id,
            },
        )


if __name__ == "__main__":
    logger.debug("starting trajectory-worker instance")

    try:
        trajectory_cocip_bq_publisher = PubSubPublishHandler(
            topic_id=env.TRAJECTORY_COCIP_BQ_TOPIC_ID,
            ordered_queue=False,
        )
        job_handler = PubSubSubscriptionHandler(env.TRAJECTORY_CHUNK_SUBSCRIPTION_ID)
        if env.TRAJECTORY_CHUNK_BACKUP_TOPIC_ID:
            backup_job_publisher = PubSubPublishHandler(
                env.TRAJECTORY_CHUNK_BACKUP_TOPIC_ID,
                ordered_queue=False,
            )
        else:
            backup_job_publisher = None
        run(
            trajectory_cocip_bq_publisher=trajectory_cocip_bq_publisher,
            job_handler=job_handler,
            backup_job_publisher=backup_job_publisher,
        )

    except Exception:
        logger.error("unhandled exception", extra={"traceback": format_traceback()})
        sys.exit(1)

"""Entrypoint for the Spire Ingest Resample Worker."""

import sys
from datetime import datetime

from lib import environment, handlers, schemas, utils
from lib.handlers import (
    CacheHandler,
    PubSubPublishHandler,
    PubSubSubscriptionHandler,
    ResampleHandler,
    ValidationHandler,
)
from lib.log import format_traceback, logger
from lib.schemas import (
    SpireWaypointPositional,
    SpireWaypointsRecord,
    WaypointCache,
)


def run(
    cache_handler: CacheHandler,
    bq_raw_publish_handler: PubSubPublishHandler,
    bq_publish_handler: PubSubPublishHandler,
    job_handler: PubSubSubscriptionHandler,
    sigterm_handler: utils.SigtermHandler,
) -> None:
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
    for message in job_handler.subscribe():
        if sigterm_handler.should_exit:
            sys.exit(0)

        job = schemas.SpireWaypointsRecord.from_utf8_json(message.data)

        logger.info(
            f"got job with {len(job.records)} records. "
            f"icao_address: {job.flight_info.icao_address}. "
            f"spanning: {job.records[0].timestamp} to {job.records[-1].timestamp}"
        )

        # ===================
        # publish raw records to BQ
        # ===================
        for raw_bq_json_ln in job.to_bq_flatmap(message.ordering_key.split(":")[0]):
            bq_raw_publish_handler.publish_async(
                data=raw_bq_json_ln,
                timeout_seconds=110,
                log_context=dict(
                    client_name="bq_raw_publish_handler",
                    icao_address=job.flight_info.icao_address,
                    batch_first_ts=job.records[0].timestamp,
                ),
            )
        bq_raw_publish_handler.wait_for_publish(timeout_seconds=120)

        # fetch cache
        try:
            cached = cache_handler.pull(message.ordering_key)
        except Exception:
            logger.error(
                f"error fetching record(s) from cache. exiting... "
                f"traceback: {format_traceback()}"
            )
            job_handler.nack(message)
            continue

        if cached:
            logger.info(
                f"icao_address: {job.flight_info.icao_address}. "
                f"cache hit: {len(cached)} waypoints. "
                f"spanning {datetime.fromtimestamp(cached[0]['timestamp']).isoformat()} "
                f"to {datetime.fromtimestamp(cached[-1]['timestamp']).isoformat()}"
            )
        else:
            logger.info(
                f"icao_address: {job.flight_info.icao_address}. " f"cache miss."
            )

        # ===================
        # validate records
        # ===================
        validation_handler = ValidationHandler(cached, job)
        validated_cache = validation_handler.cached_records
        validated_records = validation_handler.records
        validated_flight_info = validation_handler.flight_info
        validated_gt_1min_span = validation_handler.verify_gt_1min_span()
        if not validation_handler.correct_temporal_order():
            logger.warning(
                f"possible out-of-order or re-delivery."
                f"not processing batch."
                f"records must have timestamp after cached timestamp. "
                f"received records for icao_address {job.flight_info.icao_address} "
                f"with timestamp {validation_handler.min_records_ts.isoformat()} occurring before "
                # TODO: validation_handler.max_cached_ts could be None
                f"cached timestamp {validation_handler.max_cached_ts.isoformat()}"
            )
            job_handler.ack(message)
            continue
        if not validated_flight_info:
            logger.warning(
                f"no flight_id available in records batch, "
                f"and flight_id could not be inferred. "
                f"not processing batch."
                f"icao_address: {job.flight_info.icao_address} "
                f"job: {job}"
            )
            job_handler.ack(message)
            continue
        if not validated_gt_1min_span:
            logger.info(
                f"cache & records don't span more than 1 minute. "
                f"icao_address: {job.flight_info.icao_address} "
                f"updating cache. no export of records. "
                f"job: {job}"
            )
            new_cache_wpts: list[SpireWaypointPositional] = []
            if validated_cache:
                new_cache_wpts.append(validated_cache[0])
            else:
                new_cache_wpts.append(validated_records[0])
            if validated_records[-1].timestamp != new_cache_wpts[0].timestamp:
                new_cache_wpts.append(validated_records[-1])

            new_cache = WaypointCache.from_spire_waypoint_positional(
                key=message.ordering_key,
                flight_id=validated_flight_info.flight_id,
                spire_wps=tuple(new_cache_wpts),
            )
            cache_handler.push(new_cache)
            job_handler.ack(message)
            continue

        # ===================
        # resample records
        # ===================
        try:
            if validated_cache:
                logger.info(
                    f"icao_address: {job.flight_info.icao_address}. cache valid."
                )
            else:
                logger.info(
                    f"icao_address: {job.flight_info.icao_address}. cache NOT valid."
                )
            transform_handler = ResampleHandler(validated_cache, validated_records)
            transform_handler.interpolate()
            resampled_records = transform_handler.waypoints_resampled
        except Exception:
            logger.error(
                f"failed to interpolate."
                f"not updating cache. not exporting records."
                f"icao_address: {job.flight_info.icao_address} "
                f"job: {job}"
                f"traceback: {format_traceback()}"
            )
            job_handler.nack(message)
            continue

        # hold out cache records, as they would have been published previously
        cache_ts = [
            int(datetime.fromisoformat(w.timestamp).timestamp())
            for w in validated_cache
        ]
        resampled_records_prune = [
            v
            for v in resampled_records
            if int(datetime.fromisoformat(v.timestamp).timestamp()) not in cache_ts
        ]
        logger.info(
            f"icao_address: {job.flight_info.icao_address}. "
            f"prune cache from records: dropped "
            f"{len(resampled_records) - len(resampled_records_prune)} "
            f"records from resampled records."
        )

        egress_records = SpireWaypointsRecord(
            flight_info=validated_flight_info,
            records=resampled_records_prune,
        )

        # ===================
        # publish resampled records to BQ
        # ===================
        for bq_json_ln in egress_records.to_bq_flatmap(
            message.ordering_key.split(":")[0]
        ):
            bq_publish_handler.publish_async(
                data=bq_json_ln,
                timeout_seconds=110,
                log_context=dict(
                    client_name="bq_publish_handler",
                    icao_address=egress_records.flight_info.icao_address,
                    batch_first_ts=egress_records.records[0].timestamp,
                ),
            )
        bq_publish_handler.wait_for_publish(timeout_seconds=120)

        # ===================
        # update cache
        # ===================
        if len(resampled_records) > 1:
            new_cache_records = tuple(resampled_records[-2:])
        else:
            new_cache_records = tuple(resampled_records[-1:])
        new_cache = WaypointCache.from_spire_waypoint_positional(
            key=message.ordering_key,
            flight_id=validated_flight_info.flight_id,
            spire_wps=new_cache_records,
        )
        cache_handler.push(new_cache)
        logger.info(f"updated cache: {len(new_cache.waypoints)} waypoints")

        logger.info(
            f"finished processing batch "
            f"for icao_address: {egress_records.flight_info.icao_address}. "
            f"exported {len(egress_records.records)} resampled records to BigQuery"
        )
        job_handler.ack(message)


if __name__ == "__main__":
    logger.info("starting spire-ingest-resample-worker instance")

    try:
        cache_handler = handlers.CacheHandler(
            host=environment.REDIS_HOST,
            port=environment.REDIS_PORT,
        )
        bq_raw_publish_handler = handlers.PubSubPublishHandler(
            topic_id=environment.SPIRE_RAW_WAYPOINTS_BIGQUERY_TOPIC_ID,
            ordered_queue=False,
        )
        bq_publish_handler = handlers.PubSubPublishHandler(
            topic_id=environment.SPIRE_WAYPOINTS_BIGQUERY_TOPIC_ID,
            ordered_queue=False,
        )
        job_handler = handlers.PubSubSubscriptionHandler(
            subscription=environment.SPIRE_INGEST_WAYPOINTS_SUBSCRIPTION_ID
        )
        sigterm_handler = utils.SigtermHandler()
        run(
            cache_handler=cache_handler,
            bq_raw_publish_handler=bq_raw_publish_handler,
            bq_publish_handler=bq_publish_handler,
            job_handler=job_handler,
            sigterm_handler=sigterm_handler,
        )

    except Exception:
        logger.error("Unhandled exception:" + format_traceback())
        sys.exit(1)

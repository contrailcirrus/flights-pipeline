"""Entrypoint for the Spire Ingest Resample Worker."""

import sys
import time

from datetime import datetime

import lib.environment as env
from lib.log import logger, format_traceback
from lib.schemas import (
    SpireWaypointsRecord,
    SpireWaypointPositional,
    SpireFlightInfo,
    WaypointCache,
)
from lib.handlers import (
    PubSubSubscriptionHandler,
    PubSubPublishHandler,
    CacheHandler,
    ValidationHandler,
    ResampleHandler,
)


def run():
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
    cache_key_fmt = "spr:{icao_address}"
    cache_handler = CacheHandler(env.REDIS_HOST, env.REDIS_PORT)
    bq_publish_handler = PubSubPublishHandler(env.SPIRE_WAYPOINTS_BIGQUERY_TOPIC_ID)

    with PubSubSubscriptionHandler(
        env.SPIRE_INGEST_WAYPOINTS_SUBSCRIPTION_ID
    ) as job_handler:
        job: SpireWaypointsRecord = job_handler.fetch()
        if not job:
            # if the queue is empty -> we get back [], then pause before retry
            logger.info("job empty. sleeping... ")
            time.sleep(10)
            return

        logger.info(
            f"got job with {len(job.records)} records. "
            f"icao_address: {job.flight_info.icao_address}"
        )

        try:
            cached: list[WaypointCache.Waypoint] = cache_handler.pull(
                cache_key_fmt.format(icao_address=job.flight_info.icao_address)
            )
        except Exception:
            logger.error(
                f"error fetching record(s) from cache. exiting... "
                f"traceback: {format_traceback()}"
            )
            return

        if cached:
            logger.info(f"cache hit: {len(cached)} waypoints")
        else:
            logger.info("cache miss.")
        # cases where we don't process the batch window received from pubsub
        try:
            validation_handler = ValidationHandler(cached, job)
            validated_cache: list[SpireWaypointPositional] = (
                validation_handler.cached_records
            )
            validated_records: list[SpireWaypointPositional] = (
                validation_handler.records
            )
            validated_flight_info: SpireFlightInfo | None = (
                validation_handler.flight_info
            )
            validated_gt_1min_span: bool = validation_handler.verify_gt_1min_span()
        except Exception:
            logger.warning(
                f"cache and/or records invalid. "
                f"not processing batch. "
                f"icao_address: {job.flight_info.icao_address} "
                f"cache: {cached}. job: {job}."
                f"traceback: {format_traceback()}"
            )
            job_handler.ack()
            return
        if not validated_flight_info:
            logger.warning(
                f"no flight_id available in records batch, "
                f"and flight_id could not be inferred. "
                f"not processing batch."
                f"icao_address: {job.flight_info.icao_address} "
                f"cache: {cached}. job: {job}"
            )
            job_handler.ack()
            return
        if not validated_gt_1min_span:
            logger.info(
                f"cache & records don't span more than 1 minute. "
                f"icao_address: {job.flight_info.icao_address} "
                f"updating cache. no export of records. "
                f"cache: {cached}. job: {job}"
            )
            new_cache_wpts: list[SpireWaypointPositional] = []
            if validated_cache:
                new_cache_wpts.append(validated_cache[0])
            else:
                new_cache_wpts.append(validated_records[0])
            if validated_records[-1].timestamp != new_cache_wpts[0].timestamp:
                new_cache_wpts.append(validated_records[-1])

            new_cache = WaypointCache.from_spire_waypoint_positional(
                key=cache_key_fmt.format(
                    icao_address=validated_flight_info.icao_address
                ),
                flight_id=validated_flight_info.flight_id,
                spire_wps=tuple(new_cache_wpts),
            )
            cache_handler.push(new_cache)
            job_handler.ack()
            return

        # apply resampling
        try:
            transform_handler = ResampleHandler(validated_cache, validated_records)
            transform_handler.interpolate()
            resampled_records: list[SpireWaypointPositional] = (
                transform_handler.waypoints_resampled
            )
        except Exception:
            logger.error(
                f"failed to interpolate."
                f"not updating cache. not exporting records."
                f"icao_address: {job.flight_info.icao_address} "
                f"cache: {cached}. job: {job}"
                f"traceback: {format_traceback()}"
            )
            return

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
            f"prune cache from records: dropped "
            f"{len(resampled_records)-len(resampled_records_prune)} "
            f"records from resampled records."
        )

        egress_records = SpireWaypointsRecord(
            flight_info=validated_flight_info,
            records=resampled_records_prune,
        )

        for bq_json_ln in egress_records.to_bq_flatmap():
            bq_publish_handler.publish_async(bq_json_ln)
        bq_publish_handler.wait_for_publish()

        # TODO: generate flight segments; publish flight segments to pubsub
        # logger.info(
        #    f"published N={103} flight segments to {env.SPIRE_FLIGHT_SEGMENTS_TOPIC_ID}"
        # )

        # update cache
        if len(resampled_records) > 1:
            new_cache_records = tuple(resampled_records[-2:])
        else:
            new_cache_records = tuple(resampled_records[-1:])
        new_cache = WaypointCache.from_spire_waypoint_positional(
            key=cache_key_fmt.format(icao_address=validated_flight_info.icao_address),
            flight_id=validated_flight_info.flight_id,
            spire_wps=new_cache_records,
        )
        cache_handler.push(new_cache)
        logger.info(f"updated cache: {len(new_cache.waypoints)} waypoints")

        logger.info(
            f"finished processing batch "
            f"for icao_address: {egress_records.flight_info.icao_address}. "
            f"exported {len(egress_records.records)} resampled records to BigQuery"
            f"spanning {egress_records.records[0].timestamp} "
            f"to {egress_records.records[-1].timestamp}."
        )
        job_handler.ack()


if __name__ == "__main__":
    logger.info("starting spire-ingest-resample-worker instance")
    while True:
        try:
            run()
        except Exception:
            logger.error("Unhandled exception:" + format_traceback())
            sys.exit(1)

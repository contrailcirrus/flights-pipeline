from lib.schemas import SpireWaypointsRecord, WaypointCache
from stub import pubsub_message, redis_response
from lib.handlers import ValidationHandler, ResampleHandler


recs: SpireWaypointsRecord = SpireWaypointsRecord.from_utf8_json(pubsub_message)
cached: list[WaypointCache.Waypoint] = WaypointCache.from_flatmap(redis_response)

validation_handler = ValidationHandler(cached, recs)
resample_handler = ResampleHandler(
    validation_handler.cached_records, validation_handler.records
)
resample_handler.interpolate()
resampled = resample_handler.waypoints_resampled

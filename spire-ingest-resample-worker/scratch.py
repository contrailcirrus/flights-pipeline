from lib.schemas import SpireWaypointsRecord, WaypointCache
from tests.stubs.stub import ingress_pubsub_bytes, redis_response_c81e54
from lib.handlers import ValidationHandler, ResampleHandler


recs: SpireWaypointsRecord = SpireWaypointsRecord.from_utf8_json(
    ingress_pubsub_bytes["c81e54_waypoints"]
)
cached: list[WaypointCache.Waypoint] = WaypointCache.from_flatmap(redis_response_c81e54)

validation_handler = ValidationHandler(cached, recs)
resample_handler = ResampleHandler(
    validation_handler.cached_records, validation_handler.records
)
resample_handler.interpolate()
resampled = resample_handler.waypoints_resampled

import pandas as pd
from lib.schemas import SpireWaypointsRecord, WaypointCache
from stub import pubsub_message, redis_response

recs = SpireWaypointsRecord.from_utf8_json(pubsub_message)
w0, w1 = WaypointCache.from_flatmap(redis_response)
cached_flight_id, cached_wp = WaypointCache.to_spire_waypoint_positional(w1)

df = pd.DataFrame([cached_wp, *recs.records])

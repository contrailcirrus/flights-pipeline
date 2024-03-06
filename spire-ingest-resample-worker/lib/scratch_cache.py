from stub import pubsub_message
from lib.schemas import SpireWaypointRecords, WaypointCache, SpireWaypointPositional
from uuid import UUID
from datetime import datetime

#  batch of flight instance waypoints from the spire-ingest-api-scraper
flight_waypoints = SpireWaypointRecords.from_utf8_json(pubsub_message)

# grab 2 waypoints to test out marshalling to the data cache obj
w0: SpireWaypointPositional = flight_waypoints.records[
    0
]  # left-hand, i.e. first, waypoint in time
w1: SpireWaypointPositional = flight_waypoints.records[
    1
]  # right-hand, i.e. second, waypoint in time

# type conversions
flight_uuid_bytes: bytes = UUID(flight_waypoints.flight_info["flight_id"]).bytes
flight_icao_addr: str = flight_waypoints.flight_info.icao_address
w0_unixtime: int = int(datetime.fromisoformat(w0.timestamp).timestamp())
w1_unixtime: int = int(datetime.fromisoformat(w1.timestamp).timestamp())


print(f"flight info: {flight_waypoints.flight_info}")
print(f"w0:{w0}")
print(f"w1:{w1}")

# build cache object
w0_cache: WaypointCache.Waypoint = {
    "flight_id": flight_uuid_bytes,
    "latitude": w0.latitude,
    "longitude": w0.longitude,
    "altitude_ft": w0.altitude_baro,
    "timestamp": w0_unixtime,
}

w1_cache: WaypointCache.Waypoint = {
    "flight_id": flight_uuid_bytes,
    "latitude": w1.latitude,
    "longitude": w1.longitude,
    "altitude_ft": w1.altitude_baro,
    "timestamp": w1_unixtime,
}

cache_entry = WaypointCache(
    key=f"spr:{flight_icao_addr}",
    waypoints=(w0_cache, w1_cache),
)

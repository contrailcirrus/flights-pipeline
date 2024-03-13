from stub import pubsub_message
from lib.schemas import SpireWaypointsRecord, WaypointCache, SpireWaypointPositional
from uuid import UUID
from datetime import datetime
import redis
from redis.retry import Retry
from redis.backoff import ExponentialBackoff

import json

#  batch of flight instance waypoints from the spire-ingest-api-scraper
flight_waypoints = SpireWaypointsRecord.from_utf8_json(pubsub_message)

# grab 2 waypoints to test out marshalling to the data cache obj
w0: SpireWaypointPositional = flight_waypoints.records[
    0
]  # choose a waypoint (first in time)
w1: SpireWaypointPositional = flight_waypoints.records[
    1
]  # choose a waypoint (second in time)

# type conversions
flight_uuid_bytes: bytes = UUID(flight_waypoints.flight_info.flight_id).bytes
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

# gcloud compute instances create nick-tunnel --machine-type=f1-micro --zone=us-east1-b
# REDIS_HOST=10.78.184.4 && gcloud compute ssh nick-tunnel --zone=us-east1-b -- -N -L 6379:$REDIS_HOST:6379

redis_retry = Retry(ExponentialBackoff(), 3)
redis_client = redis.Redis(
    host="localhost",
    port=6379,
    retry=redis_retry,
    retry_on_timeout=True,
)
# try writing single record w/ expiry as an atomic transaction
transaction = redis_client.pipeline()
transaction.hset(cache_entry.key, mapping=cache_entry.to_flatmap())
transaction.expire(cache_entry.key, 10)
transaction.execute()

# redis_client.hget(cache_entry.key, "w1_flight_id")
redis_client.hgetall(cache_entry.key)
# redis_client.delete(cache_entry.key)


expiry_sec = 5 * 60 * 60
for i in range(60000):
    # populate a bunch of phony records
    phony_key = f"spr:{i}:06d"
    transaction = redis_client.pipeline()
    transaction.hset(phony_key, mapping=cache_entry.to_flatmap())
    transaction.expire(phony_key, expiry_sec)
    transaction.execute()

    if not (i % 100):
        info = redis_client.info()
        print(f"key count: {info['db0']['keys']}")
        print(f"{info['used_memory_human']} of {info['maxmemory_human']} used")

print(redis_client.scan(count=100))

info = redis_client.info()
print(json.dumps(info, indent=4))

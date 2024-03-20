import os

os.environ["SPIRE_INGEST_WAYPOINTS_SUBSCRIPTION_ID"] = "/projects/foo/subscriptions/bar"
os.environ["SPIRE_WAYPOINTS_BIGQUERY_TOPIC_ID"] = "projects/foo/topics/bar"
os.environ["SPIRE_FLIGHT_SEGMENTS_TOPIC_ID"] = "projects/foo/topics/bar"
os.environ["REDIS_HOST"] = "0.0.0.0"
os.environ["REDIS_PORT"] = "6379"

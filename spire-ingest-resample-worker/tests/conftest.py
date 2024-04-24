import os

os.environ["SPIRE_INGEST_WAYPOINTS_SUBSCRIPTION_ID"] = "/projects/foo/subscriptions/bar"
os.environ["SPIRE_RAW_WAYPOINTS_BIGQUERY_TOPIC_ID"] = "projects/foo/topics/bar1"
os.environ["SPIRE_WAYPOINTS_BIGQUERY_TOPIC_ID"] = "projects/foo/topics/bar2"
os.environ["TRAJECTORY_CHUNK_TOPIC_ID"] = "projects/foo/topics/bar3"
os.environ["REDIS_HOST"] = "0.0.0.0"
os.environ["REDIS_PORT"] = "6379"

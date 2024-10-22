"""
A singleton object intended as the single point of access for application environment variables.

The application may expect required and optional environment variables.
Required environment variables should be imported first, followed by optional environment variables.
"""

import os

SPIRE_INGEST_WAYPOINTS_SUBSCRIPTION_ID = os.environ[
    "SPIRE_INGEST_WAYPOINTS_SUBSCRIPTION_ID"
]
SPIRE_RAW_WAYPOINTS_BIGQUERY_TOPIC_ID = os.environ[
    "SPIRE_RAW_WAYPOINTS_BIGQUERY_TOPIC_ID"
]
SPIRE_WAYPOINTS_BIGQUERY_TOPIC_ID = os.environ["SPIRE_WAYPOINTS_BIGQUERY_TOPIC_ID"]
REDIS_HOST = os.environ["REDIS_HOST"]
REDIS_PORT = int(os.environ["REDIS_PORT"])

LOG_LEVEL = os.environ.get("LOG_LEVEL", "DEBUG")

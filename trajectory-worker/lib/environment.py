"""
A singleton object intended as the single point of access for application environment variables.

The application may expect required and optional environment variables.
Required environment variables should be imported first, followed by optional environment variables.
"""

import json
import os

TRAJECTORY_CHUNK_SUBSCRIPTION_ID = os.environ["TRAJECTORY_CHUNK_SUBSCRIPTION_ID"]
TRAJECTORY_CHUNK_BACKUP_TOPIC_ID = ["TRAJECTORY_CHUNK_BACKUP_TOPIC_ID"]
HRES_SOURCE_PATH = os.environ["HRES_SOURCE_PATH"]
ERA5_SOURCE_PATH = os.environ["ERA5_SOURCE_PATH"]
TRAJECTORY_COCIP_BQ_TOPIC_ID = os.environ["TRAJECTORY_COCIP_BQ_TOPIC_ID"]
GCP_SVC_ACCT_KEY = json.loads(os.environ["GCP_SVC_ACCT_KEY"])
N_JOBS = int(os.environ["N_JOBS"])

LOG_LEVEL = os.environ.get("LOG_LEVEL", "DEBUG")
GIT_SHA = os.environ.get("GIT_SHA", "local")

"""
A singleton object intended as the single point of access for application environment variables.

The application may expect required and optional environment variables.
Required environment variables should be imported first, followed by optional environment variables.
"""

import os

TRAJECTORY_CHUNK_SUBSCRIPTION_ID = os.environ["TRAJECTORY_CHUNK_SUBSCRIPTION_ID"]
HRES_SOURCE_PATH = os.environ["HRES_SOURCE_PATH"]

LOG_LEVEL = os.environ.get("LOG_LEVEL", "DEBUG")
GIT_SHA = os.environ.get("GIT_SHA", "local")

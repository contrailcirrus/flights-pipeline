"""
A singleton object intended as the single point of access for application environment variables.

The application may expect required and optional environment variables.
Required environment variables should be imported first, followed by optional environment variables.
"""

import os

# only used when deployed as a cronjob
TWJD_TOPIC_ID = os.environ.get("TWJD_TOPIC_ID", None)

LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO")

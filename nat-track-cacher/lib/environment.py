"""
A singleton object intended as the single point of access for application environment variables.

The application may expect required and optional environment variables.
Required environment variables should be imported first, followed by optional environment variables.
"""

import os

NAT_TRACK_API_URL = os.environ.get("NAT_TRACK_API_URL")

LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO")

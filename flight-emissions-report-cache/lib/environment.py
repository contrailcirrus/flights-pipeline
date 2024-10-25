"""
A singleton object intended as the single point of access for application environment variables.

The application may expect required and optional environment variables.
Required environment variables should be imported first, followed by optional environment variables.
"""

import os

PSDB_USER = os.environ["PSDB_USER"]
PSDB_PASS = os.environ["PSDB_PASS"]
PSDB_DATABASE = os.environ["PSDB_DATABASE"]

LOG_LEVEL = os.environ.get("LOG_LEVEL", "DEBUG")

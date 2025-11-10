"""
Exposes environment as module level variables.
"""

import os

FIRESTORE_STATE_COLLECTION = os.environ["FIRESTORE_STATE_COLLECTION"]
FIRESTORE_STATE_DB = os.environ["FIRESTORE_STATE_DB"]
FIRESTORE_STATE_DOC_ID = os.environ["FIRESTORE_STATE_DOC_ID"]
GCS_BUCKET_NAME = os.environ["GCS_BUCKET_NAME"]
LOG_LEVEL = os.environ["LOG_LEVEL"]
SPIRE_API_TOKEN = os.environ["SPIRE_API_TOKEN"]

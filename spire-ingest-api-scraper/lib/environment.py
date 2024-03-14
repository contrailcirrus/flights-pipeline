"""
Exposes environment as module level variables.
"""

import os

FIRESTORE_STATE_DB = os.environ["FIRESTORE_STATE_DB"]
FIRESTORE_STATE_COLLECTION = os.environ["FIRESTORE_STATE_COLLECTION"]
FIRESTORE_STATE_DOC_ID = os.environ["FIRESTORE_STATE_DOC_ID"]

PUBSUB_EGRESS_TOPIC_ID = os.environ["PUBSUB_EGRESS_TOPIC_ID"]

SPIRE_API_TOKEN = os.environ["SPIRE_API_TOKEN"]

LOG_LEVEL = os.environ["LOG_LEVEL"]

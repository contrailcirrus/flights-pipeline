from datetime import datetime

from google.cloud import firestore  # type: ignore

from lib.log import logger


class PersistentStateClient:
    def __init__(
        self,
        firestore_database: str,
        firestore_collection: str,
        firestore_doc_id: str,
    ) -> None:
        _db = firestore.Client(database=firestore_database)
        collection = _db.collection(firestore_collection)
        self._doc_ref = collection.document(firestore_doc_id)

    def set_last_sync_end_at(self, value: datetime) -> None:
        """Update checkpoint to signal data has been processed up to this time."""
        logger.info(f"Updated last sync end checkpoint: {value.isoformat()}")
        self._doc_ref.update({"last_sync_end_at": value})

    def get_last_sync_end_at(self) -> datetime:
        """Gets last checkpoint indicating the end of previous fetch.

        Related to Spire's `ingestion_time` and `timestamp` values, `last_sync_end_at`
        specifies the `timestamp` after which we have not processed data. In other
        words, this service should use `last_sync_end_at` to specify the `start_at`
        value for the next `spire_client.get_data_between(start_at, ...)` fetch.
        """
        doc = self._doc_ref.get()
        last_sync_end_at = doc.get("last_sync_end_at")
        if not isinstance(last_sync_end_at, datetime):
            raise RuntimeError(f"last_sync_end_at state malformed: {last_sync_end_at}")
        logger.info(f"Last sync end checkpoint: {last_sync_end_at.isoformat()}")
        return last_sync_end_at

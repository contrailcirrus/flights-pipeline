from datetime import datetime

from google.cloud import firestore  # type: ignore


class PersistentStateClient:
    def __init__(self, firestore_collection: str, firestore_doc_id: str) -> None:
        _db = firestore.Client()
        self._doc_ref = _db.collection(firestore_collection).document(firestore_doc_id)

    def set_last_sync_end_at(self, last_sync_end_at: datetime) -> None:
        self._doc_ref.update({"last_sync_end_at": last_sync_end_at})

    def get_last_sync_end_at(self) -> datetime:
        doc = self._doc_ref.get()
        last_sync_end_at = doc.get("last_sync_end_at")
        if not isinstance(last_sync_end_at, datetime):
            raise RuntimeError(f"last_sync_end_at state malformed: {last_sync_end_at}")
        return last_sync_end_at

"""Tests for Firestore state client."""

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

from lib import state


@pytest.fixture
def state_client():
    """Create state client."""
    with patch("lib.state.firestore.Client"):
        return state.PersistentStateClient("test-db", "test-collection", "test-doc")


def test_set_last_sync_end_at(state_client):
    """Test setting sync checkpoint."""
    timestamp = datetime.now(tz=timezone.utc)

    state_client.set_last_sync_end_at(timestamp)

    state_client._doc_ref.update.assert_called_once_with(
        {"last_sync_end_at": timestamp}
    )


def test_get_last_sync_end_at_success(state_client):
    """Test getting sync checkpoint successfully."""
    mock_timestamp = datetime.now(tz=timezone.utc)
    mock_doc = MagicMock()
    mock_doc.get.return_value = mock_timestamp
    state_client._doc_ref.get = MagicMock(return_value=mock_doc)

    result = state_client.get_last_sync_end_at()

    assert result == mock_timestamp
    mock_doc.get.assert_called_once_with("last_sync_end_at")


def test_get_last_sync_end_at_malformed(state_client):
    """Test getting checkpoint with malformed data."""
    mock_doc = MagicMock()
    mock_doc.get.return_value = "invalid"
    state_client._doc_ref.get = MagicMock(return_value=mock_doc)

    with pytest.raises(RuntimeError, match="last_sync_end_at state malformed"):
        state_client.get_last_sync_end_at()

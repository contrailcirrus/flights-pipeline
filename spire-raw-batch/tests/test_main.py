"""Tests for main module."""

from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture
def sample_df():
    """Sample DataFrame."""
    import pandas as pd

    return pd.DataFrame(
        {
            "icao_address": ["ABC123", "DEF456"],
            "timestamp": [datetime.now(tz=timezone.utc)] * 2,
            "latitude": [45.0, 46.0],
            "longitude": [-120.0, -121.0],
        }
    )


def test_main_success(sample_df):
    """Test successful main execution."""
    import main

    with (
        patch("main.spire") as mock_spire_module,
        patch("main.state") as mock_state_module,
        patch("main.gcs") as mock_gcs_module,
    ):
        # Mock environment
        with patch("lib.environment") as mock_env:
            mock_env.SPIRE_API_TOKEN = "test-token"
            mock_env.FIRESTORE_STATE_DB = "test-db"
            mock_env.FIRESTORE_STATE_COLLECTION = "test-collection"
            mock_env.FIRESTORE_STATE_DOC_ID = "test-doc"
            mock_env.GCS_BUCKET_NAME = "test-bucket"
            mock_env.LOG_LEVEL = "INFO"

            # Mock classes
            mock_spire_client = MagicMock()
            mock_spire_client.get_data_between.return_value = sample_df
            mock_spire_module.SpireAPIClient.return_value = mock_spire_client

            mock_state_client = MagicMock()
            current_time = datetime.now(tz=timezone.utc)
            mock_last_sync = current_time - timedelta(minutes=10)
            mock_state_client.get_last_sync_end_at.return_value = mock_last_sync
            mock_state_module.PersistentStateClient.return_value = mock_state_client

            mock_gcs_client = MagicMock()
            mock_gcs_module.GCSClient.return_value = mock_gcs_client

            result = main.main()

            assert result == 0


def test_main_handles_exception():
    """Test main handles exceptions gracefully."""
    import main

    with (
        patch("main.spire"),
        patch("main.state") as mock_state_module,
        patch("main.gcs"),
    ):
        # Mock environment
        with patch("lib.environment") as mock_env:
            mock_env.SPIRE_API_TOKEN = "test-token"
            mock_env.FIRESTORE_STATE_DB = "test-db"
            mock_env.FIRESTORE_STATE_COLLECTION = "test-collection"
            mock_env.FIRESTORE_STATE_DOC_ID = "test-doc"
            mock_env.GCS_BUCKET_NAME = "test-bucket"
            mock_env.LOG_LEVEL = "INFO"

            # Mock state client to raise exception
            mock_state_client = MagicMock()
            mock_state_client.get_last_sync_end_at.side_effect = Exception("Test error")
            mock_state_module.PersistentStateClient.return_value = mock_state_client

            result = main.main()

            assert result == 1

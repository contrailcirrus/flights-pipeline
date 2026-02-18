"""Tests for Spire API client."""

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import httpx
import pytest

from lib import spire


@pytest.fixture
def spire_client():
    """Create Spire API client."""
    return spire.SpireAPIClient("test-token")


@pytest.fixture
def sample_api_response():
    """Sample API response."""
    return [
        '{"status": {"message": "test"}}',
        '{"target": {"icao_address": "ABC123", "latitude": 45.0, "longitude": -120.0}}',
        '{"target": {"icao_address": "DEF456", "latitude": 46.0, "longitude": -121.0}}',
    ]


def test_get_data_between_success(spire_client, sample_api_response):
    """Test successful data fetch."""
    start = datetime(2025, 1, 1, 12, 0, tzinfo=timezone.utc)
    end = datetime(2025, 1, 1, 12, 5, tzinfo=timezone.utc)

    with patch("lib.spire.httpx.Client") as mock_client:
        mock_response = MagicMock()
        mock_response.iter_lines.return_value = iter(sample_api_response)
        mock_response.raise_for_status = MagicMock()

        mock_client_instance = MagicMock()
        # Mock get() implementation
        mock_client_instance.__enter__.return_value.get.return_value = mock_response
        mock_client.return_value = mock_client_instance

        df = spire_client.get_data_between(start, end)

        assert len(df) == 2
        assert "icao_address" in df.columns


def test_get_data_between_timezone_aware_start(spire_client):
    """Test that start_at must be timezone aware."""
    naive_start = datetime(2025, 1, 1, 12, 0)
    end = datetime(2025, 1, 1, 12, 5, tzinfo=timezone.utc)

    with pytest.raises(ValueError, match="start_at must be timezone aware"):
        spire_client.get_data_between(naive_start, end)


def test_get_data_between_timezone_aware_end(spire_client):
    """Test that end_at must be timezone aware."""
    start = datetime(2025, 1, 1, 12, 0, tzinfo=timezone.utc)
    naive_end = datetime(2025, 1, 1, 12, 5)

    with pytest.raises(ValueError, match="end_at must be timezone aware"):
        spire_client.get_data_between(start, naive_end)


def test_get_data_between_retry_on_failure(spire_client):
    """Test retry logic on API failure."""
    start = datetime(2025, 1, 1, 12, 0, tzinfo=timezone.utc)
    end = datetime(2025, 1, 1, 12, 5, tzinfo=timezone.utc)

    with patch("lib.spire.httpx.Client") as mock_client:
        mock_response = MagicMock()
        mock_response.iter_lines.return_value = iter([])
        mock_response.raise_for_status = MagicMock()

        mock_client_instance = MagicMock()
        mock_client_instance.__enter__.return_value.get.return_value = mock_response
        mock_client.return_value = mock_client_instance

        with patch("time.sleep"):
            df = spire_client.get_data_between(start, end)

            assert len(df) == 0


def test_get_data_between_retry_on_remote_protocol_error(spire_client, sample_api_response):
    """Test that RemoteProtocolError during streaming triggers a retry."""
    start = datetime(2025, 1, 1, 12, 0, tzinfo=timezone.utc)
    end = datetime(2025, 1, 1, 12, 5, tzinfo=timezone.utc)

    with patch("lib.spire.httpx.Client") as mock_client:
        mock_response_fail = MagicMock()
        # Raise error during iteration
        mock_response_fail.iter_lines.side_effect = httpx.RemoteProtocolError(
            "incomplete chunked read"
        )
        mock_response_fail.raise_for_status = MagicMock()

        mock_response_success = MagicMock()
        mock_response_success.iter_lines.return_value = iter(sample_api_response)
        mock_response_success.raise_for_status = MagicMock()

        mock_client_instance = MagicMock()
        # First call fails during streaming, second call succeeds
        mock_client_instance.__enter__.return_value.get.side_effect = [
            mock_response_fail,
            mock_response_success,
        ]
        mock_client.return_value = mock_client_instance

        with patch("time.sleep"):
            df = spire_client.get_data_between(start, end)

            assert len(df) == 2
            # Verify it was called twice (initial + 1 retry)
            assert mock_client_instance.__enter__.return_value.get.call_count == 2

"""Tests for GCS client."""

from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from lib import gcs


@pytest.fixture
def gcs_client():
    """Create GCS client."""
    with patch("lib.gcs.storage.Client"):
        return gcs.GCSClient("test-bucket")


@pytest.fixture
def sample_df():
    """Create sample DataFrame."""
    return pd.DataFrame({"col1": [1, 2, 3], "col2": ["a", "b", "c"]})


def test_write_parquet_success(gcs_client, sample_df):
    """Test successful parquet write."""
    mock_blob = MagicMock()
    mock_blob.exists.return_value = False
    gcs_client._bucket.blob = MagicMock(return_value=mock_blob)

    gcs_client.write_parquet(sample_df, "test.pq")

    mock_blob.upload_from_file.assert_called_once()


def test_write_parquet_empty_dataframe(gcs_client):
    """Test write with empty DataFrame."""
    mock_blob = MagicMock()
    gcs_client._bucket.blob = MagicMock(return_value=mock_blob)

    empty_df = pd.DataFrame()
    gcs_client.write_parquet(empty_df, "test.pq")

    mock_blob.upload_from_file.assert_not_called()


def test_write_parquet_no_overwrite_existing(gcs_client, sample_df):
    """Test write when file already exists and overwrite=False."""
    mock_blob = MagicMock()
    mock_blob.exists.return_value = True
    gcs_client._bucket.blob = MagicMock(return_value=mock_blob)

    gcs_client.write_parquet(sample_df, "test.pq", overwrite=False)

    mock_blob.upload_from_file.assert_not_called()


def test_file_exists(gcs_client):
    """Test file_exists method."""
    mock_blob = MagicMock()
    mock_blob.exists.return_value = True
    gcs_client._bucket.blob = MagicMock(return_value=mock_blob)

    result = gcs_client.file_exists("test.pq")

    assert result is True
    mock_blob.exists.assert_called_once()

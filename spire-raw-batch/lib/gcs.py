"""
Google Cloud Storage client for writing parquet files.
"""

import io
from datetime import datetime

import pandas as pd
from google.cloud import storage  # type: ignore

from lib.log import logger


class GCSClient:
    def __init__(self, bucket_name: str) -> None:
        self._bucket_name = bucket_name
        self._client = storage.Client()
        self._bucket = self._client.bucket(bucket_name)

    def write_parquet(
        self,
        df: pd.DataFrame,
        filename: str,
        overwrite: bool = True,
    ) -> None:
        """Write DataFrame to GCS as parquet file.

        Parameters
        ----------
        df
            DataFrame to write
        filename
            Name of the file in GCS (without bucket prefix)
        overwrite
            Whether to overwrite existing file
        """
        if df.empty:
            logger.warning(f"DataFrame is empty, skipping write to {filename}")
            return

        # Convert DataFrame to parquet bytes
        buffer = io.BytesIO()
        df.to_parquet(buffer, engine="pyarrow", index=False)
        buffer.seek(0)

        # Upload to GCS
        blob = self._bucket.blob(filename)
        if not overwrite and blob.exists():
            logger.info(f"File {filename} already exists, skipping upload")
            return

        blob.upload_from_file(buffer, content_type="application/octet-stream")
        logger.info(
            f"Successfully wrote {len(df)} records to gs://{self._bucket_name}/{filename}"
        )

    def file_exists(self, filename: str) -> bool:
        """Check if file exists in GCS bucket."""
        blob = self._bucket.blob(filename)
        return blob.exists()

    def generate_deterministic_filename(self, start_at: datetime) -> str:
        """Generate deterministic filename for parquet file.

        Parameters
        ----------
        start_at
            Start timestamp for the data window

        Returns
        -------
        str
            Filename in format: YYYYMMDD-HHMMSS.pq
        """
        return f"{start_at.strftime('%Y%m%d-%H%M%S')}.pq"

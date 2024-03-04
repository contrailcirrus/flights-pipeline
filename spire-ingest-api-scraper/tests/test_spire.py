from datetime import datetime

import pandas as pd

from src import spire


def test_spire_airsafe_target_parsing(mock_spire_airsafe_api: str) -> None:
    start_at = datetime(2024, 3, 1, 13, 0, 0)
    end_at = datetime(2024, 3, 1, 13, 1, 0)
    spire_client = spire.SpireAPIClient("fake-token", mock_spire_airsafe_api)
    spire_df = spire_client.get_data_between(start_at, end_at)

    expected_target_record_count = 117440
    assert len(spire_df) == expected_target_record_count

    ingestion_time = pd.to_datetime(spire_df["ingestion_time"], utc=True)
    assert (ingestion_time >= pd.to_datetime(start_at, utc=True)).all()
    assert (ingestion_time < pd.to_datetime(end_at, utc=True)).all()

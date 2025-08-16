from datetime import datetime, timezone

import pandas as pd
import pytest

from lib import spire


async def test_spire_airsafe_target_parsing(mock_spire_airsafe_api: str) -> None:
    start_at = datetime(2024, 3, 1, 12, 55, 0, tzinfo=timezone.utc)
    end_at = datetime(2024, 3, 1, 13, 1, 0, tzinfo=timezone.utc)
    spire_client = spire.SpireAPIClient("fake-token", mock_spire_airsafe_api)
    spire_df = await spire_client.get_data_between(start_at, end_at)

    expected_target_record_count = 59994
    assert len(spire_df) == expected_target_record_count

    timestamp = pd.to_datetime(spire_df["timestamp"], utc=True)
    # Allow timestamps at the start boundary (>=) and before the end boundary (<)
    assert (timestamp >= pd.to_datetime(start_at, utc=True)).all(), (
        f"Some timestamps before start: {timestamp.min()}"
    )
    assert (timestamp < pd.to_datetime(end_at, utc=True)).all(), (
        f"Some timestamps at or after end: {timestamp.max()}"
    )


async def test_spire_enforces_timezone_aware() -> None:
    start_at = datetime(1970, 1, 1)
    end_at = datetime(2099, 1, 1)
    spire_client = spire.SpireAPIClient("fake-token", "fake-uri")

    with pytest.raises(ValueError):
        await spire_client.get_data_between(start_at, end_at)

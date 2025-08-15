from datetime import datetime, timezone

import pandas as pd
import pytest

from lib import spire


async def test_spire_airsafe_target_parsing(mock_spire_airsafe_api: str) -> None:
    start_at = datetime(2024, 3, 1, 13, 0, 0, tzinfo=timezone.utc)
    end_at = datetime(2024, 3, 1, 13, 1, 0, tzinfo=timezone.utc)
    spire_client = spire.SpireAPIClient("fake-token", mock_spire_airsafe_api)
    spire_df = await spire_client.get_data_between(start_at, end_at)

    expected_target_record_count = 28962
    assert len(spire_df) == expected_target_record_count

    timestamp = pd.to_datetime(spire_df["timestamp"], utc=True)
    assert (timestamp >= pd.to_datetime(start_at, utc=True)).all()
    assert (timestamp < pd.to_datetime(end_at, utc=True)).all()


async def test_spire_enforces_timezone_aware() -> None:
    start_at = datetime(1970, 1, 1)
    end_at = datetime(2099, 1, 1)
    spire_client = spire.SpireAPIClient("fake-token", "fake-uri")

    with pytest.raises(ValueError):
        await spire_client.get_data_between(start_at, end_at)


async def test_spire_enforces_wall_time() -> None:
    start_at = datetime(1970, 1, 1, tzinfo=timezone.utc)
    end_at = datetime(2099, 1, 1, tzinfo=timezone.utc)
    spire_client = spire.SpireAPIClient("fake-token", "fake-uri")

    with pytest.raises(ValueError):
        await spire_client.get_data_between(start_at, end_at)

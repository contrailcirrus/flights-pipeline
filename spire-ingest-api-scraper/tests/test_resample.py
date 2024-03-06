from datetime import datetime, timezone

from src import resample, spire


def test_downsample(mock_spire_airsafe_api: str) -> None:
    start_at = datetime(2024, 3, 1, 13, 0, 0, tzinfo=timezone.utc)
    end_at = datetime(2024, 3, 1, 13, 5, 0, tzinfo=timezone.utc)
    spire_client = spire.SpireAPIClient("fake-token", mock_spire_airsafe_api)
    spire_df = spire_client.get_data_between(start_at, end_at)

    result = resample.downsample_icao_address_minutes_first_last(spire_df)
    assert len(result.columns) == len(spire_df.columns)
    assert len(result) == 18362

    # is result a subset of original df?
    assert len(result.merge(spire_df)) == len(result)

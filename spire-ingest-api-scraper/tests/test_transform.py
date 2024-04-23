from datetime import datetime, timezone

from lib import spire, transform


async def test_downsample(mock_spire_airsafe_api: str) -> None:
    start_at = datetime(2024, 3, 1, 13, 0, 0, tzinfo=timezone.utc)
    end_at = datetime(2024, 3, 1, 13, 5, 0, tzinfo=timezone.utc)
    spire_client = spire.SpireAPIClient("fake-token", mock_spire_airsafe_api)
    spire_df, _ = await spire_client.get_data_between(start_at, end_at)

    result = transform._downsample_icao_address_minutes_first_last(spire_df)
    assert len(result.columns) == len(spire_df.columns)
    assert len(result) == 2507

    # is result a subset of original df?
    inner = result.merge(spire_df, how="inner")
    expected_count = len(inner.drop_duplicates(["icao_address", "timestamp"]))
    assert len(result) == expected_count

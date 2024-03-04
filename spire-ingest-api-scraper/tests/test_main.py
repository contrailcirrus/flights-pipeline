from datetime import datetime, timedelta
from unittest.mock import Mock

from src import queue, spire, state
from src.main import _time_windows, main


def test_time_windows_within_range() -> None:
    start_at = datetime(2024, 1, 2, 3, 0, 0)
    end_at = datetime(2024, 1, 2, 3, 10, 0)
    step = timedelta(minutes=5)

    count = 0
    for batch_start_at, batch_end_at in _time_windows(start_at, end_at, step):
        assert (batch_end_at - batch_start_at) == step
        assert start_at <= batch_start_at < end_at
        assert start_at < batch_end_at <= end_at
        count += 1
    assert count == 2


def test_main_entrypoint(mock_spire_airsafe_api: str) -> None:
    triggered_at = datetime(2024, 3, 1, 13, 6, 0)
    last_sync_end_at = datetime(2024, 3, 1, 13, 0, 0)

    queue_client = Mock(spec=queue.QueueClient)
    spire_client = spire.SpireAPIClient("fake-token", mock_spire_airsafe_api)
    state_client = Mock(spec=state.PersistentStateClient)
    state_client.get_last_sync_end_at = Mock(return_value=last_sync_end_at)

    main(
        triggered_at=triggered_at,
        queue_client=queue_client,
        spire_client=spire_client,
        state_client=state_client,
    )

    assert queue_client.publish_async.call_count == 1363
    assert queue_client.wait_for_publish.call_count == 1
    state_client.set_last_sync_end_at.assert_called_once_with(
        datetime(2024, 3, 1, 13, 1, 0)
    )

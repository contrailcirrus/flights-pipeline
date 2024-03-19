import json
from datetime import datetime, timedelta, timezone
from types import NoneType
from unittest.mock import Mock

from lib import queue, spire, state
from main import _time_windows, main


def test_time_windows_within_range() -> None:
    start_at = datetime(2024, 1, 2, 3, 0, 0, tzinfo=timezone.utc)
    end_at = datetime(2024, 1, 2, 3, 10, 0, tzinfo=timezone.utc)
    step = timedelta(minutes=5)

    count = 0
    for batch_start_at, batch_end_at in _time_windows(start_at, end_at, step):
        assert (batch_end_at - batch_start_at) == step
        assert start_at <= batch_start_at < end_at
        assert start_at < batch_end_at <= end_at
        count += 1
    assert count == 2


def test_main_entrypoint(mock_spire_airsafe_api: str) -> None:
    triggered_at = datetime(2024, 3, 1, 13, 10, 1, 2, tzinfo=timezone.utc)
    last_sync_end_at = datetime(2024, 3, 1, 13, 0, 0, tzinfo=timezone.utc)

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

    assert queue_client.publish_async.call_count == 8233
    assert queue_client.wait_for_publish.call_count == 1

    for args, kwargs in queue_client.publish_async.call_args_list:
        assert kwargs == {}
        data, ordering_key = args
        assert isinstance(ordering_key, str)
        dto = json.loads(data)
        flight_info = dto["flight_info"]
        assert isinstance(flight_info["icao_address"], str)
        assert isinstance(flight_info["flight_id"], (str, NoneType))
        assert isinstance(flight_info["callsign"], (str, NoneType))
        assert isinstance(flight_info["tail_number"], (str, NoneType))
        assert isinstance(flight_info["flight_number"], (str, NoneType))
        assert isinstance(flight_info["aircraft_type_icao"], (str, NoneType))
        assert isinstance(flight_info["airline_iata"], (str, NoneType))
        assert isinstance(flight_info["departure_airport_icao"], (str, NoneType))
        assert isinstance(flight_info["departure_scheduled_time"], (str, NoneType))
        assert isinstance(flight_info["arrival_airport_icao"], (str, NoneType))
        assert isinstance(flight_info["arrival_scheduled_time"], (str, NoneType))
        for record in dto["records"]:
            assert isinstance(record["timestamp"], str)
            assert isinstance(record["latitude"], float)
            assert isinstance(record["longitude"], float)
            assert isinstance(record["altitude_baro"], int)
            assert record["flight_level"] is None
            assert not record["imputed"]

    expected_sync_end_at = datetime(2024, 3, 1, 13, 5, tzinfo=timezone.utc)
    state_client.set_last_sync_end_at.assert_called_once_with(expected_sync_end_at)


def test_main_entrypoint_exits_if_less_than_5_minutes_elapsed() -> None:
    triggered_at = datetime(2024, 3, 1, 13, 1, 1, 2, tzinfo=timezone.utc)
    last_sync_end_at = datetime(2024, 3, 1, 13, 0, 0, tzinfo=timezone.utc)

    queue_client = Mock(spec=queue.QueueClient)
    spire_client = Mock(spec=spire.SpireAPIClient)
    state_client = Mock(spec=state.PersistentStateClient)
    state_client.get_last_sync_end_at = Mock(return_value=last_sync_end_at)

    main(
        triggered_at=triggered_at,
        queue_client=queue_client,
        spire_client=spire_client,
        state_client=state_client,
    )

    assert spire_client.get_data_between.call_count == 0
    assert queue_client.publish_async.call_count == 0

import asyncio
import json
from datetime import datetime, timedelta, timezone
from typing import Any
from unittest.mock import Mock

from lib import queue, spire, state, utils
from main import main


def test_time_windows_within_range() -> None:
    start_at = datetime(2024, 1, 2, 3, 0, 0, tzinfo=timezone.utc)
    end_at = datetime(2024, 1, 2, 3, 10, 0, tzinfo=timezone.utc)
    step = timedelta(minutes=5)

    count = 0
    for batch_start_at, batch_end_at in utils.time_windows(start_at, end_at, step):
        assert (batch_end_at - batch_start_at) == step
        assert start_at <= batch_start_at < end_at
        assert start_at < batch_end_at <= end_at
        count += 1
    assert count == 2


def _is_valid_str_or_none(x: Any) -> bool:
    if x is None:
        return True

    if not isinstance(x, str):
        return False

    should_be_none = {"nan", "NaN", "nat", "NaT", "null", "NULL", "None"}
    if x in should_be_none:
        return False
    return True


def test_main_entrypoint(mock_spire_airsafe_api: str) -> None:
    triggered_at = datetime(2024, 3, 1, 13, 10, 1, 2, tzinfo=timezone.utc)
    last_sync_end_at = datetime(2024, 3, 1, 13, 0, 0, tzinfo=timezone.utc)

    bq_queue_client = Mock(spec=queue.QueueClient)
    sigterm_handler = utils.SigtermHandler()
    spire_client = spire.SpireAPIClient("fake-token", mock_spire_airsafe_api)
    state_client = Mock(spec=state.PersistentStateClient)
    state_client.get_last_sync_end_at = Mock(return_value=last_sync_end_at)

    asyncio.run(
        main(
            triggered_at=triggered_at,
            bq_queue_client=bq_queue_client,
            sigterm_handler=sigterm_handler,
            spire_client=spire_client,
            state_client=state_client,
        )
    )

    assert bq_queue_client.publish_async.call_count == 2477
    assert bq_queue_client.wait_for_publish.call_count == 1

    for args, kwargs in bq_queue_client.publish_async.call_args_list:
        data = kwargs["data"]
        dto = json.loads(data)
        assert isinstance(dto["icao_address"], str)
        assert _is_valid_str_or_none(dto["flight_id"])
        assert _is_valid_str_or_none(dto["callsign"])
        assert _is_valid_str_or_none(dto["tail_number"])
        assert _is_valid_str_or_none(dto["flight_number"])
        assert _is_valid_str_or_none(dto["aircraft_type_icao"])
        assert _is_valid_str_or_none(dto["airline_iata"])
        assert _is_valid_str_or_none(dto["departure_airport_icao"])
        # Timestamps are integers (microseconds since epoch) or None
        if dto["departure_scheduled_time"] is not None:
            assert isinstance(dto["departure_scheduled_time"], int)
        if dto["arrival_scheduled_time"] is not None:
            assert isinstance(dto["arrival_scheduled_time"], int)
        assert _is_valid_str_or_none(dto["arrival_airport_icao"])
        # Timestamps are integers (microseconds since epoch)
        assert isinstance(dto["timestamp"], int)
        assert isinstance(dto["ingestion_time"], int)
        assert isinstance(dto["latitude"], float)
        assert isinstance(dto["longitude"], float)
        assert isinstance(dto["altitude_baro"], int)
        assert dto["flight_level"] is None
        assert not dto["imputed"]

    expected_sync_end_at = datetime(2024, 3, 1, 13, 5, tzinfo=timezone.utc)
    state_client.set_last_sync_end_at.assert_called_once_with(expected_sync_end_at)


def test_main_entrypoint_exits_if_less_than_5_minutes_elapsed() -> None:
    triggered_at = datetime(2024, 3, 1, 13, 1, 1, 2, tzinfo=timezone.utc)
    last_sync_end_at = datetime(2024, 3, 1, 13, 0, 0, tzinfo=timezone.utc)

    bq_queue_client = Mock(spec=queue.QueueClient)
    sigterm_handler = utils.SigtermHandler()
    spire_client = Mock(spec=spire.SpireAPIClient)
    state_client = Mock(spec=state.PersistentStateClient)
    state_client.get_last_sync_end_at = Mock(return_value=last_sync_end_at)

    asyncio.run(
        main(
            triggered_at=triggered_at,
            bq_queue_client=bq_queue_client,
            sigterm_handler=sigterm_handler,
            spire_client=spire_client,
            state_client=state_client,
        )
    )

    assert spire_client.get_data_between.call_count == 0
    assert bq_queue_client.publish_async.call_count == 0

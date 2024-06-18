"""
Test schemas.
"""

from lib.schemas import WaypointsRecord
from tests.stubs.stub import waypoints_record_blob


def test_load_waypoints_record():
    """
    test marshalling from a bytes blob to a waypoints record.
    """
    rec: WaypointsRecord = WaypointsRecord.from_utf8_json(waypoints_record_blob)
    assert rec.flight_info.engine_uid is None
    assert rec.export_cocip_trajectory is False

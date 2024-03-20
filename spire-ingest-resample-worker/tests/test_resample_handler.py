import pytest

import lib.handlers
from lib.schemas import SpireWaypointPositional, SpireWaypointsRecord
from tests.stubs.stub import ingress_pubsub_bytes

recs_multi_min_span: list[SpireWaypointPositional] = (
    SpireWaypointsRecord.from_utf8_json(ingress_pubsub_bytes["multi_min_span"]).records
)
recs_gt_one_min: list[SpireWaypointPositional] = SpireWaypointsRecord.from_utf8_json(
    ingress_pubsub_bytes["gt_one_min_span"]
).records
recs_lt_inter_one_min: list[SpireWaypointPositional] = (
    SpireWaypointsRecord.from_utf8_json(
        ingress_pubsub_bytes["lt_inter_one_min_span"]
    ).records
)
recs_lt_intra_one_min: list[SpireWaypointPositional] = (
    SpireWaypointsRecord.from_utf8_json(
        ingress_pubsub_bytes["lt_intra_one_min_span"]
    ).records
)


@pytest.mark.parametrize("recs", [recs_lt_intra_one_min, recs_lt_inter_one_min])
def test_interpolate_lt_one_min_span(recs: list[SpireWaypointPositional]):
    """
    case: no cache, multiple records,
     1. records span less that 1min, crosses 1min timestamp
     2. records span less than 1min, does not cross 1min timestamp
    """
    h = lib.handlers.ResampleHandler(
        cache=[],
        records_window=recs,
    )
    interpolated_waypoints = h.interpolate().waypoints_resampled
    assert len(interpolated_waypoints) == 0


@pytest.mark.parametrize("recs", [recs_gt_one_min, recs_gt_one_min])
def test_interpolate_gt_one_min_span(recs: list[SpireWaypointPositional]):
    """
    case: no cache, multiple records,
     1. records greater slightly greater one minute, crosses 1min timestamp
     2. records span many minutes
    """
    h = lib.handlers.ResampleHandler(
        cache=[],
        records_window=recs,
    )
    interpolated_waypoints = h.interpolate().waypoints_resampled
    assert len(interpolated_waypoints) > 0

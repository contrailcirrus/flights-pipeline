import pytest

import lib.handlers
from lib.schemas import SpireWaypointsRecord
from tests.stubs.stub import ingress_pubsub_bytes

# TODO: create stubs of native SpireWaypointsRecord type... as is, more of an integration test.

recs_multi_min_span: SpireWaypointsRecord = SpireWaypointsRecord.from_utf8_json(
    ingress_pubsub_bytes["multi_min_span"]
)
recs_gt_one_min: SpireWaypointsRecord = SpireWaypointsRecord.from_utf8_json(
    ingress_pubsub_bytes["gt_one_min_span"]
)
recs_lt_inter_one_min: SpireWaypointsRecord = SpireWaypointsRecord.from_utf8_json(
    ingress_pubsub_bytes["lt_inter_one_min_span"]
)
recs_lt_intra_one_min: SpireWaypointsRecord = SpireWaypointsRecord.from_utf8_json(
    ingress_pubsub_bytes["lt_intra_one_min_span"]
)


@pytest.mark.parametrize("recs", [recs_lt_inter_one_min, recs_lt_intra_one_min])
def test_verify_gt_1min_span_lt(recs: SpireWaypointsRecord):
    """
    case: no cache, multiple records, records span less than 1 min.
    """
    h = lib.handlers.ValidationHandler(
        cache=[],
        new_waypoints=recs,
    )
    is_gt_1min = h.verify_gt_1min_span()
    assert not is_gt_1min


@pytest.mark.parametrize("recs", [recs_multi_min_span, recs_gt_one_min])
def test_verify_gt_1min_span_gt(recs: SpireWaypointsRecord):
    """
    case: no cache, multiple records, records span less than 1 min.
    """
    h = lib.handlers.ValidationHandler(
        cache=[],
        new_waypoints=recs,
    )
    is_gt_1min = h.verify_gt_1min_span()
    assert is_gt_1min

import os
from functools import cache
from typing import Iterator

import httpx
import pytest
import respx

# Fake environment variables. This is required since lib.log inherited from existing
# services has an import-time dependency on lib.environment, so the service's
# environment variables must be present to test any modules which import lib.log.
os.environ["FIRESTORE_STATE_DB"] = "fake-test"
os.environ["FIRESTORE_STATE_COLLECTION"] = "fake-test"
os.environ["FIRESTORE_STATE_DOC_ID"] = "fake-test"
os.environ["PUBSUB_EGRESS_TOPIC_ID"] = "fake-test"
os.environ["SPIRE_RAW_WAYPOINTS_BIGQUERY_TOPIC_ID"] = "fake-test"
os.environ["SPIRE_API_TOKEN"] = "fake-test"
os.environ["LOG_LEVEL"] = "DEBUG"


@cache
def _read_text(filename: str) -> str:
    with open(filename, "r") as f:
        return f.read()


@pytest.fixture(scope="session")
def mock_spire_airsafe_api() -> Iterator[str]:
    """Return cached response json from given URL during testing."""
    mock_url = "https://api-mock.airsafe.spire.com/v2/targets/stream"
    mock_body = _read_text("tests/api/spire_response_10k.ndjson")
    with respx.mock:
        respx.get(mock_url).mock(return_value=httpx.Response(200, content=mock_body))
        yield mock_url

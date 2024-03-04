from typing import Iterator

import pytest
import responses


def _read_text(filename: str) -> str:
    with open(filename, "r") as f:
        return f.read()


@pytest.fixture()
def mock_spire_airsafe_api() -> Iterator[str]:
    """Return cached response json from given URL during testing."""
    mock_url = "https://api-mock.airsafe.spire.com/v2/targets/stream"
    mock_body = _read_text("tests/api/spire_response.json")
    with responses.RequestsMock() as mock_responses:
        mock_responses.get(
            url=mock_url,
            body=mock_body,
        )
        yield mock_url

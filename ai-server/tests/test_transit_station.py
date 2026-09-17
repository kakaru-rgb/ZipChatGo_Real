from unittest.mock import Mock

import httpx
import pytest

from app.tools.transit_station import TransitStationSearchError, TransitStationTool


def test_search_calls_spring_transit_station_api() -> None:
    client = Mock()
    client.get.return_value = httpx.Response(
        200,
        json={
            "total_count": 1,
            "stations": [
                {
                    "name": "정자역",
                    "lines": ["신분당선", "분당선"],
                    "latitude": 37.3671,
                    "longitude": 127.1082,
                }
            ],
        },
        request=httpx.Request("GET", "http://spring/api/map/transit/stations/search"),
    )
    tool = TransitStationTool("http://spring", client=client)

    result = tool.search({"query": "정자역"})

    client.get.assert_called_once_with(
        "/api/map/transit/stations/search",
        params={"query": "정자역", "limit": 5},
    )
    assert result["stations"][0]["name"] == "정자역"


def test_search_raises_safe_error_when_spring_is_unavailable() -> None:
    client = Mock()
    client.get.side_effect = httpx.ConnectError("connection failed")
    tool = TransitStationTool("http://spring", client=client)

    with pytest.raises(
        TransitStationSearchError,
        match="Spring transit station search request failed",
    ):
        tool.search({"query": "정자역"})

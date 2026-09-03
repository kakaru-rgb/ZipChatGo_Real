from unittest.mock import Mock

import httpx
import pytest

from app.tools.property_search import PropertySearchError, PropertySearchTool


def test_search_calls_spring_api_with_validated_arguments() -> None:
    client = Mock()
    client.get.return_value = httpx.Response(
        200,
        json={
            "total_count": 1,
            "properties": [
                {
                    "id": 427,
                    "building_name": "판교아파트",
                    "sale_price": 780_000_000,
                }
            ],
        },
        request=httpx.Request("GET", "http://spring/api/map/properties/search"),
    )
    tool = PropertySearchTool("http://spring", client=client)

    result = tool.search(
        {
            "keyword": "판교역",
            "property_type": "아파트",
            "max_price": 800_000_000,
        }
    )

    client.get.assert_called_once_with(
        "/api/map/properties/search",
        params={
            "limit": 10,
            "keyword": "판교역",
            "propertyType": "아파트",
            "maxPrice": 800_000_000,
        },
    )
    assert result["total_count"] == 1
    assert result["properties"][0]["id"] == 427


def test_search_raises_safe_error_when_spring_is_unavailable() -> None:
    client = Mock()
    client.get.side_effect = httpx.ConnectError("connection failed")
    tool = PropertySearchTool("http://spring", client=client)

    with pytest.raises(PropertySearchError, match="Spring property search request failed"):
        tool.search({"keyword": "판교", "property_type": None, "max_price": None})


def test_search_passes_current_map_bounds_to_spring() -> None:
    client = Mock()
    client.get.return_value = httpx.Response(
        200,
        json={"total_count": 0, "properties": []},
        request=httpx.Request("GET", "http://spring/api/map/properties/search"),
    )
    tool = PropertySearchTool("http://spring", client=client)

    tool.search(
        {
            "keyword": None,
            "property_type": "아파트",
            "max_price": 800_000_000,
            "map_bounds": {
                "south": 37.3,
                "west": 127.0,
                "north": 37.5,
                "east": 127.3,
            },
        }
    )

    client.get.assert_called_once_with(
        "/api/map/properties/search",
        params={
            "limit": 10,
            "propertyType": "아파트",
            "maxPrice": 800_000_000,
            "south": 37.3,
            "west": 127.0,
            "north": 37.5,
            "east": 127.3,
        },
    )


def test_search_passes_selected_legal_dong_code_to_spring() -> None:
    client = Mock()
    client.get.return_value = httpx.Response(
        200,
        json={"total_count": 0, "properties": []},
        request=httpx.Request("GET", "http://spring/api/map/properties/search"),
    )
    tool = PropertySearchTool("http://spring", client=client)

    tool.search(
        {
            "keyword": None,
            "property_type": "아파트",
            "max_price": None,
            "legal_dong_code": "41135108",
        }
    )

    client.get.assert_called_once_with(
        "/api/map/properties/search",
        params={
            "limit": 10,
            "propertyType": "아파트",
            "legalDongCode": "41135108",
        },
    )

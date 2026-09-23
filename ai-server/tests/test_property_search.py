import json
from types import SimpleNamespace
from unittest.mock import Mock, patch

import httpx
import pytest

from app.tools.property_search import PropertySearchError, PropertySearchTool
from app.providers.openai_provider import OpenAIProvider


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


def test_get_by_ids_calls_spring_and_keeps_missing_ids() -> None:
    client = Mock()
    client.get.return_value = httpx.Response(
        200,
        json={
            "requested_ids": [427, 903],
            "properties": [{"id": 427, "sale_price": 780_000_000}],
            "missing_ids": [903],
        },
        request=httpx.Request("GET", "http://spring/api/map/properties/by-ids"),
    )
    tool = PropertySearchTool("http://spring", client=client)

    result = tool.get_by_ids({"property_ids": [427, 903]})

    client.get.assert_called_once_with(
        "/api/map/properties/by-ids",
        params={"ids": "427,903"},
    )
    assert result["properties"][0]["id"] == 427
    assert result["missing_ids"] == [903]


def test_transaction_search_reuses_existing_spring_endpoint() -> None:
    client = Mock()
    client.get.return_value = httpx.Response(
        200, json={"total_count": 1, "properties": [{"id": 427}]},
        request=httpx.Request("GET", "http://spring/api/map/properties/search"),
    )
    tool = PropertySearchTool("http://spring", client=client)

    tool.search({
        "search_mode": "selected_building_transactions",
        "selected_property_id": 427,
        "exclusive_area": 84,
        "sort_by": "contract_date",
        "sort_order": "desc",
        "limit": 5,
    })

    client.get.assert_called_once_with("/api/map/properties/search", params={
        "limit": 5,
        "searchMode": "selected_building_transactions",
        "selectedPropertyId": 427,
        "exclusiveArea": 84.0,
        "sortBy": "contract_date",
        "sortOrder": "desc",
    })


def _transaction_call(arguments):
    return SimpleNamespace(
        type="function_call", name="search_properties",
        arguments=json.dumps(arguments, ensure_ascii=False), call_id="call-1",
    )


def test_agent_uses_selected_property_id_for_history_without_guessing_name() -> None:
    client = Mock()
    client.responses.create.side_effect = [
        SimpleNamespace(output=[_transaction_call({
            "search_mode": "selected_building_transactions", "keyword": "잘못된 이름",
            "exact_building_name": "잘못된 이름", "limit": 5,
        })], output_text=""),
        SimpleNamespace(output=[], output_text="최근 거래 내역입니다."),
    ]
    search = Mock(return_value={"total_count": 0, "properties": []})

    with patch("app.providers.openai_provider.OpenAI", return_value=client):
        OpenAIProvider("key", "model", "instructions").generate(
            "이 아파트 최근 거래 5건 보여줘",
            app_state={"current_page": "map", "selected_property_id": "427"},
            search_properties=search,
        )

    arguments = search.call_args.args[0]
    assert arguments["selected_property_id"] == 427
    assert arguments["keyword"] is None
    assert arguments["exact_building_name"] is None
    assert (arguments["sort_by"], arguments["sort_order"]) == ("contract_date", "desc")


def test_agent_uses_selected_legal_dong_for_transaction_history() -> None:
    client = Mock()
    client.responses.create.side_effect = [
        SimpleNamespace(output=[_transaction_call({
            "search_mode": "transactions", "keyword": None,
            "exact_building_name": None, "limit": 5,
        })], output_text=""),
        SimpleNamespace(output=[], output_text="정자동 최근 거래입니다."),
    ]
    search = Mock(return_value={"total_count": 0, "properties": []})

    with patch("app.providers.openai_provider.OpenAI", return_value=client):
        OpenAIProvider("key", "model", "instructions").generate(
            "현재 선택한 동 최근 거래 보여줘",
            app_state={"current_page": "map", "selected_region": {
                "type": "legal_dong", "code": "41135103", "name": "정자동",
            }, "map_bounds": {"south": 37.3, "west": 127.0, "north": 37.4, "east": 127.2}},
            search_properties=search,
        )

    arguments = search.call_args.args[0]
    assert arguments["legal_dong_code"] == "41135103"
    assert "map_bounds" not in arguments
    assert arguments["sort_by"] == "contract_date"

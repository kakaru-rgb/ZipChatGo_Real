import json
from types import SimpleNamespace
from unittest.mock import Mock, patch

import httpx
import pytest
from pydantic import ValidationError

from app.providers.openai_provider import AGENT_TOOLS, OpenAIProvider
from app.tools.poi_search import PoiSearchTool


def _poi_arguments(**overrides):
    arguments = {
        "category": "의료",
        "subcategory": "병원",
        "region": None,
        "keyword": None,
        "lat": 37.37,
        "lng": 127.11,
        "radius": 1500,
        "limit": 3,
    }
    arguments.update(overrides)
    return arguments


def _function_call(name: str, arguments: dict, call_id: str = "call-1"):
    return SimpleNamespace(
        type="function_call",
        name=name,
        arguments=json.dumps(arguments, ensure_ascii=False),
        call_id=call_id,
    )


def test_poi_tool_calls_spring_search_api_with_validated_arguments() -> None:
    observed_request = None

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal observed_request
        observed_request = request
        return httpx.Response(200, json={"total_count": 1, "pois": [{"id": "H1"}]})

    client = httpx.Client(
        base_url="http://spring.test",
        transport=httpx.MockTransport(handler),
    )
    result = PoiSearchTool("http://spring.test", client=client).search(_poi_arguments())

    assert observed_request is not None
    assert observed_request.url.path == "/api/map/pois/search"
    assert observed_request.url.params["category"] == "의료"
    assert observed_request.url.params["lat"] == "37.37"
    assert observed_request.url.params["radius"] == "1500"
    assert result["total_count"] == 1


def test_poi_tool_rejects_incomplete_coordinates() -> None:
    tool = PoiSearchTool("http://spring.test", client=Mock())

    with pytest.raises(ValidationError):
        tool.search(_poi_arguments(lng=None))


def test_agent_uses_selected_property_coordinates_for_poi_search() -> None:
    client = Mock()
    first_response = SimpleNamespace(
        output=[_function_call("search_poi", _poi_arguments())], output_text=""
    )
    final_response = SimpleNamespace(
        output=[], output_text="가까운 병원 1곳을 찾았습니다."
    )
    client.responses.create.side_effect = [first_response, final_response]
    search_poi = Mock(return_value={"total_count": 1, "pois": [{"id": "H1"}]})
    app_state = {
        "current_page": "map",
        "selected_property_id": "427",
        "selected_property": {
            "id": "427",
            "title": "선택 매물",
            "latitude": 37.37,
            "longitude": 127.11,
        },
    }

    with patch("app.providers.openai_provider.OpenAI", return_value=client):
        result = OpenAIProvider("key", "model", "instructions").generate(
            "이 매물 주변 병원 3개 알려줘",
            app_state=app_state,
            search_poi=search_poi,
        )

    search_poi.assert_called_once_with(_poi_arguments())
    developer_context = client.responses.create.call_args_list[0].kwargs["input"][0]
    assert '"latitude":37.37' in developer_context["content"]
    assert '"longitude":127.11' in developer_context["content"]
    assert result.message == "가까운 병원 1곳을 찾았습니다."


def test_agent_keeps_zero_result_inside_requested_poi_scope() -> None:
    client = Mock()
    client.responses.create.side_effect = [
        SimpleNamespace(
            output=[_function_call(
                "search_poi",
                _poi_arguments(
                    category="의료",
                    subcategory=None,
                    region="정자동",
                    keyword="약국",
                    lat=None,
                    lng=None,
                    radius=None,
                    limit=5,
                ),
            )],
            output_text="",
        ),
        SimpleNamespace(
            output=[], output_text="정자동에서 해당하는 약국을 찾지 못했습니다."
        ),
    ]
    search_poi = Mock(return_value={"total_count": 0, "pois": []})
    search_properties = Mock()

    with patch("app.providers.openai_provider.OpenAI", return_value=client):
        result = OpenAIProvider("key", "model", "instructions").generate(
            "정자동에 약국 있어?",
            search_poi=search_poi,
            search_properties=search_properties,
        )

    search_poi.assert_called_once()
    search_properties.assert_not_called()
    assert result.message == "정자동에서 해당하는 약국을 찾지 못했습니다."


def test_property_search_question_does_not_require_poi_tool_call() -> None:
    client = Mock()
    client.responses.create.return_value = SimpleNamespace(
        output=[], output_text="매물 검색 조건을 확인했습니다."
    )
    search_poi = Mock()
    search_properties = Mock()

    with patch("app.providers.openai_provider.OpenAI", return_value=client):
        OpenAIProvider("key", "model", "instructions").generate(
            "정자동 8억 이하 아파트 찾아줘",
            search_poi=search_poi,
            search_properties=search_properties,
        )

    search_poi.assert_not_called()
    tool_names = {
        tool["name"] for tool in client.responses.create.call_args.kwargs["tools"]
    }
    assert "search_poi" in tool_names
    assert "search_properties" in tool_names


def test_poi_tool_schema_lists_only_actual_broad_categories() -> None:
    tool = next(tool for tool in AGENT_TOOLS if tool["name"] == "search_poi")

    assert tool["parameters"]["properties"]["category"]["enum"] == [
        "공공기관", "교육", "교통", "의료", "중개", None
    ]

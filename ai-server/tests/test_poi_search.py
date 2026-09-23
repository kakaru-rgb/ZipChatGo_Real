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


def test_poi_tool_forwards_legal_dong_code_to_spring() -> None:
    observed_request = None

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal observed_request
        observed_request = request
        return httpx.Response(200, json={"total_count": 12, "pois": []})

    client = httpx.Client(base_url="http://spring.test", transport=httpx.MockTransport(handler))
    result = PoiSearchTool("http://spring.test", client=client).search(
        _poi_arguments(category="교육", subcategory="학교", legal_dong_code="41135103",
                       region=None, lat=None, lng=None, radius=None, limit=10)
    )

    assert observed_request.url.params["legal_dong_code"] == "41135103"
    assert result["total_count"] == 12


def test_selected_region_school_count_uses_full_region_code() -> None:
    client = Mock()
    client.responses.create.side_effect = [
        SimpleNamespace(output=[_function_call("search_poi", _poi_arguments(
            category="교육", subcategory="학교", location_source="selected_region",
            region="다른 동", lat=37.4, lng=127.15, radius=500, limit=10,
        ))], output_text=""),
        SimpleNamespace(output=[], output_text="정자동 전체 학교는 12개입니다."),
    ]
    search_poi = Mock(return_value={"total_count": 12, "pois": []})

    with patch("app.providers.openai_provider.OpenAI", return_value=client):
        reply = OpenAIProvider("key", "model", "instructions").generate(
            "현재 지역 내 학교가 몇 개지?",
            app_state={"current_page": "map", "selected_region": {
                "type": "legal_dong", "code": "41135103", "name": "정자동",
            }},
            search_poi=search_poi,
        )

    search_poi.assert_called_once_with(_poi_arguments(
        category="교육", subcategory="학교", region=None, lat=None, lng=None,
        radius=None, limit=10, legal_dong_code="41135103",
    ))
    assert reply.message == "정자동 전체 학교는 12개입니다."


def test_selected_region_school_list_stays_within_selected_region() -> None:
    client = Mock()
    client.responses.create.side_effect = [
        SimpleNamespace(output=[_function_call("search_poi", _poi_arguments(
            category="교육", subcategory="학교", location_source="selected_region",
            region=None, lat=None, lng=None, radius=None, limit=5,
        ))], output_text=""),
        SimpleNamespace(output=[], output_text="정자동 학교 목록입니다."),
    ]
    search_poi = Mock(return_value={"total_count": 12, "pois": [
        {"id": "S1", "category": "교육"},
    ]})

    with patch("app.providers.openai_provider.OpenAI", return_value=client):
        reply = OpenAIProvider("key", "model", "instructions").generate(
            "현재 지역 학교 알려줘",
            app_state={"current_page": "map", "selected_region": {
                "type": "legal_dong", "code": "41135103", "name": "정자동",
            }},
            search_poi=search_poi,
        )

    assert search_poi.call_args.args[0]["legal_dong_code"] == "41135103"
    assert [action.type for action in reply.actions] == ["SET_POI_CATEGORY", "HIGHLIGHT_POIS"]


def test_missing_selected_region_does_not_search_guessed_location() -> None:
    client = Mock()
    client.responses.create.side_effect = [
        SimpleNamespace(output=[_function_call("search_poi", _poi_arguments(
            category="교육", subcategory="학교", location_source="selected_region",
            region="정자동", lat=37.4, lng=127.15, radius=500,
        ))], output_text=""),
        SimpleNamespace(output=[], output_text="지역을 먼저 선택해 주세요."),
    ]
    search_poi = Mock()

    with patch("app.providers.openai_provider.OpenAI", return_value=client):
        reply = OpenAIProvider("key", "model", "instructions").generate(
            "현재 지역 학교 몇 개야?",
            app_state={"current_page": "map", "selected_region": None},
            search_poi=search_poi,
        )

    search_poi.assert_not_called()
    assert reply.message == "지역을 먼저 선택해 주세요."


def test_agent_uses_selected_property_coordinates_for_poi_search() -> None:
    client = Mock()
    first_response = SimpleNamespace(
        output=[_function_call("search_poi", _poi_arguments(
            location_source="selected_property", lat=37.4, lng=127.15,
        ))], output_text=""
    )
    final_response = SimpleNamespace(
        output=[], output_text="가까운 병원 1곳을 찾았습니다."
    )
    client.responses.create.side_effect = [first_response, final_response]
    search_poi = Mock(return_value={"total_count": 1, "pois": [
        {"id": "H1", "category": "의료"},
    ]})
    app_state = {
        "current_page": "map",
        "selected_region": {"type": "legal_dong", "code": "41135103", "name": "정자동"},
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
            "현재 선택된 아파트 근처 병원 알려줘",
            app_state=app_state,
            search_poi=search_poi,
        )

    search_poi.assert_called_once_with(_poi_arguments())
    developer_context = client.responses.create.call_args_list[0].kwargs["input"][0]
    assert '"latitude":37.37' in developer_context["content"]
    assert '"longitude":127.11' in developer_context["content"]
    assert result.message == "가까운 병원 1곳을 찾았습니다."
    assert [action.type for action in result.actions] == ["SET_POI_CATEGORY", "HIGHLIGHT_POIS"]


def test_selected_property_id_only_looks_up_coordinates_before_poi_search() -> None:
    client = Mock()
    client.responses.create.side_effect = [
        SimpleNamespace(output=[_function_call("search_poi", _poi_arguments(
            location_source="selected_property", lat=None, lng=None,
        ))], output_text=""),
        SimpleNamespace(output=[], output_text="공인중개사 1곳을 찾았습니다."),
    ]
    get_properties_by_ids = Mock(return_value={"properties": [
        {"id": 427, "latitude": 37.37, "longitude": 127.11},
    ]})
    search_poi = Mock(return_value={"total_count": 1, "pois": [
        {"id": "R1", "category": "중개"},
    ]})

    with patch("app.providers.openai_provider.OpenAI", return_value=client):
        reply = OpenAIProvider("key", "model", "instructions").generate(
            "현재 선택된 아파트 근처 공인중개사 알려줘",
            app_state={"current_page": "map", "selected_property_id": "427"},
            get_properties_by_ids=get_properties_by_ids,
            search_poi=search_poi,
        )

    get_properties_by_ids.assert_called_once_with({"property_ids": [427]})
    search_poi.assert_called_once_with(_poi_arguments())
    assert reply.actions[1].poi_ids == ["R1"]


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


def _generate_poi_actions(calls, poi_results):
    client = Mock()
    client.responses.create.side_effect = [
        SimpleNamespace(output=[call], output_text="") for call in calls
    ] + [SimpleNamespace(output=[], output_text="검색 결과입니다.")]
    search_poi = Mock(side_effect=poi_results)
    with patch("app.providers.openai_provider.OpenAI", return_value=client):
        reply = OpenAIProvider("key", "model", "instructions").generate(
            "주변 시설을 알려줘", search_poi=search_poi,
        )
    return reply, client


def test_poi_search_enables_category_and_highlights_result_ids() -> None:
    reply, _ = _generate_poi_actions(
        [_function_call("search_poi", _poi_arguments(category="중개", subcategory=None))],
        [{"total_count": 2, "pois": [
            {"id": "R1", "category": "중개", "name": "공인중개사 1"},
            {"id": "R2", "category": "중개", "name": "공인중개사 2"},
        ]}],
    )

    assert [(action.type, getattr(action, "category", None)) for action in reply.actions[:1]] == [
        ("SET_POI_CATEGORY", "중개")
    ]
    assert reply.actions[1].type == "HIGHLIGHT_POIS"
    assert reply.actions[1].poi_ids == ["R1", "R2"]
    assert reply.actions[1].fit_bounds is False


def test_poi_map_request_needs_no_extra_llm_highlight_call() -> None:
    reply, _ = _generate_poi_actions(
        [_function_call("search_poi", _poi_arguments(category="의료", keyword="약국"))],
        [{"total_count": 1, "pois": [{"id": "P1", "category": "의료", "name": "약국"}]}],
    )

    assert [action.type for action in reply.actions] == ["SET_POI_CATEGORY", "HIGHLIGHT_POIS"]
    assert reply.actions[1].poi_ids == ["P1"]
    assert "highlight_pois" not in {tool["name"] for tool in AGENT_TOOLS}


def test_second_poi_search_replaces_previous_highlight() -> None:
    reply, _ = _generate_poi_actions(
        [
            _function_call("search_poi", _poi_arguments(category="중개")),
            _function_call("search_poi", _poi_arguments(category="의료", keyword="약국")),
        ],
        [
            {"total_count": 1, "pois": [{"id": "R1", "category": "중개"}]},
            {"total_count": 1, "pois": [{"id": "P1", "category": "의료"}]},
        ],
    )

    assert [action.type for action in reply.actions] == ["SET_POI_CATEGORY", "HIGHLIGHT_POIS"]
    assert reply.actions[0].category == "의료"
    assert reply.actions[1].poi_ids == ["P1"]


def test_same_name_pois_remain_distinct_by_id() -> None:
    reply, _ = _generate_poi_actions(
        [_function_call("search_poi", _poi_arguments(category="교육"))],
        [{"total_count": 2, "pois": [
            {"id": "S1", "category": "교육", "name": "같은 이름"},
            {"id": "S2", "category": "교육", "name": "같은 이름"},
        ]}],
    )

    assert reply.actions[1].poi_ids == ["S1", "S2"]


def test_zero_poi_results_clear_highlight_without_enabling_category() -> None:
    reply, _ = _generate_poi_actions(
        [_function_call("search_poi", _poi_arguments(category="의료"))],
        [{"total_count": 0, "pois": []}],
    )

    assert [action.type for action in reply.actions] == ["CLEAR_POI_HIGHLIGHTS"]

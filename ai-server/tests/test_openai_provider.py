from unittest.mock import Mock, patch
import json
from types import SimpleNamespace

from app.providers.openai_provider import AGENT_TOOLS, OpenAIProvider


def test_generate_sends_instructions_separately_from_user_input() -> None:
    client = Mock()
    client.responses.create.return_value.output_text = "상담 답변"

    with patch("app.providers.openai_provider.OpenAI", return_value=client):
        provider = OpenAIProvider(
            api_key="test-key",
            model="test-model",
            instructions="공인중개사 상담 원칙",
        )
        result = provider.generate("전세 계약에서 무엇을 확인해야 하나요?")

    client.responses.create.assert_called_once_with(
        model="test-model",
        instructions="공인중개사 상담 원칙",
        input="전세 계약에서 무엇을 확인해야 하나요?",
    )
    assert result.message == "상담 답변"
    assert result.actions == []


def test_generate_sends_app_state_as_developer_context() -> None:
    client = Mock()
    client.responses.create.return_value.output_text = "현재 지도 기준 상담 답변"
    app_state = {
        "current_page": "map",
        "map_center": {"lat": 37.4, "lng": 127.15},
        "selected_property_id": "427",
    }

    with patch("app.providers.openai_provider.OpenAI", return_value=client):
        provider = OpenAIProvider(
            api_key="test-key",
            model="test-model",
            instructions="공인중개사 상담 원칙",
        )
        result = provider.generate("현재 선택한 매물이 뭐야?", app_state)

    input_items = client.responses.create.call_args.kwargs["input"]
    assert input_items[0]["role"] == "developer"
    assert json.dumps(app_state, ensure_ascii=False, separators=(",", ":")) in input_items[0]["content"]
    assert input_items[1] == {"role": "user", "content": "현재 선택한 매물이 뭐야?"}
    assert result.message == "현재 지도 기준 상담 답변"
    assert result.actions == []


def test_generate_executes_property_search_and_returns_final_answer() -> None:
    client = Mock()
    function_call = SimpleNamespace(
        type="function_call",
        name="search_properties",
        arguments=json.dumps(
            {
                "keyword": "판교역",
                "property_type": "아파트",
                "max_price": 800_000_000,
            }
        ),
        call_id="call-1",
    )
    first_response = SimpleNamespace(output=[function_call], output_text="")
    final_response = SimpleNamespace(output=[], output_text="조건에 맞는 매물 2건을 찾았습니다.")
    client.responses.create.side_effect = [first_response, final_response]
    search_properties = Mock(
        return_value={"total_count": 2, "properties": [{"id": 1}, {"id": 2}]}
    )

    with patch("app.providers.openai_provider.OpenAI", return_value=client):
        provider = OpenAIProvider(
            api_key="test-key",
            model="test-model",
            instructions="공인중개사 상담 원칙",
        )
        result = provider.generate(
            "판교역 8억 이하 아파트 찾아줘",
            search_properties=search_properties,
        )

    search_properties.assert_called_once_with(
        {
            "keyword": "판교역",
            "property_type": "아파트",
            "max_price": 800_000_000,
        }
    )
    assert client.responses.create.call_count == 2
    first_request = client.responses.create.call_args_list[0].kwargs
    assert first_request["tools"] == AGENT_TOOLS
    second_input = client.responses.create.call_args_list[1].kwargs["input"]
    assert second_input[-1]["type"] == "function_call_output"
    assert second_input[-1]["call_id"] == "call-1"
    assert json.loads(second_input[-1]["output"])["total_count"] == 2
    assert result.message == "조건에 맞는 매물 2건을 찾았습니다."
    assert [action.type for action in result.actions] == [
        "FIT_BOUNDS",
        "HIGHLIGHT_PROPERTIES",
    ]
    assert result.actions[0].property_ids == [1, 2]


def test_generate_collects_only_actions_for_searched_properties() -> None:
    client = Mock()
    search_call = SimpleNamespace(
        type="function_call",
        name="search_properties",
        arguments=json.dumps(
            {"keyword": "판교", "property_type": "아파트", "max_price": None}
        ),
        call_id="search-1",
    )
    highlight_call = SimpleNamespace(
        type="function_call",
        name="highlight_properties",
        arguments=json.dumps({"property_ids": [101, 999]}),
        call_id="action-1",
    )
    valid_highlight_call = SimpleNamespace(
        type="function_call",
        name="highlight_properties",
        arguments=json.dumps({"property_ids": [101]}),
        call_id="action-2",
    )
    client.responses.create.side_effect = [
        SimpleNamespace(output=[search_call], output_text=""),
        SimpleNamespace(output=[highlight_call, valid_highlight_call], output_text=""),
        SimpleNamespace(output=[], output_text="지도에 표시했습니다."),
    ]
    search_properties = Mock(
        return_value={
            "total_count": 1,
            "properties": [
                {"id": 101, "latitude": 37.394, "longitude": 127.111}
            ],
        }
    )

    with patch("app.providers.openai_provider.OpenAI", return_value=client):
        provider = OpenAIProvider("test-key", "test-model", "instructions")
        result = provider.generate(
            "판교 아파트 보여줘",
            search_properties=search_properties,
        )

    assert [action.type for action in result.actions] == [
        "HIGHLIGHT_PROPERTIES",
        "MOVE_MAP",
    ]
    assert result.actions[0].property_ids == [101]
    assert json.loads(
        client.responses.create.call_args_list[1].kwargs["input"][-2]["output"]
    )["status"] == "rejected"


def test_generate_applies_current_bounds_when_search_has_no_keyword() -> None:
    client = Mock()
    search_call = SimpleNamespace(
        type="function_call",
        name="search_properties",
        arguments=json.dumps(
            {"keyword": None, "property_type": "아파트", "max_price": 800_000_000}
        ),
        call_id="search-current-map",
    )
    client.responses.create.side_effect = [
        SimpleNamespace(output=[search_call], output_text=""),
        SimpleNamespace(output=[], output_text="현재 화면에서 검색했습니다."),
    ]
    search_properties = Mock(return_value={"total_count": 0, "properties": []})
    app_state = {
        "current_page": "map",
        "current_region": "경기도 성남시 분당구 백현동",
        "map_bounds": {
            "south": 37.3,
            "west": 127.0,
            "north": 37.5,
            "east": 127.3,
        },
    }

    with patch("app.providers.openai_provider.OpenAI", return_value=client):
        provider = OpenAIProvider("test-key", "test-model", "instructions")
        provider.generate(
            "여기에서 아파트 찾아줘",
            app_state=app_state,
            search_properties=search_properties,
        )

    search_properties.assert_called_once_with(
        {
            "keyword": None,
            "property_type": "아파트",
            "max_price": 800_000_000,
            "map_bounds": app_state["map_bounds"],
        }
    )


def test_generate_prioritizes_selected_legal_dong_over_current_bounds() -> None:
    client = Mock()
    search_call = SimpleNamespace(
        type="function_call",
        name="search_properties",
        arguments=json.dumps(
            {"keyword": None, "property_type": "아파트", "max_price": None}
        ),
        call_id="search-selected-dong",
    )
    client.responses.create.side_effect = [
        SimpleNamespace(output=[search_call], output_text=""),
        SimpleNamespace(output=[], output_text="선택한 법정동에서 검색했습니다."),
    ]
    search_properties = Mock(return_value={"total_count": 0, "properties": []})
    app_state = {
        "current_page": "map",
        "selected_region": {
            "type": "legal_dong",
            "code": "41135108",
            "name": "판교동",
            "full_name": "경기도 성남시 분당구 판교동",
            "center": {"lat": 37.39, "lng": 127.1},
            "bounds": {
                "south": 37.38,
                "west": 127.08,
                "north": 37.41,
                "east": 127.12,
            },
        },
        "map_bounds": {
            "south": 37.3,
            "west": 127.0,
            "north": 37.5,
            "east": 127.3,
        },
    }

    with patch("app.providers.openai_provider.OpenAI", return_value=client):
        provider = OpenAIProvider("test-key", "test-model", "instructions")
        provider.generate(
            "이 동에서 아파트 찾아줘",
            app_state=app_state,
            search_properties=search_properties,
        )

    search_properties.assert_called_once_with(
        {
            "keyword": None,
            "property_type": "아파트",
            "max_price": None,
            "legal_dong_code": "41135108",
        }
    )


def test_generate_finds_station_before_moving_map() -> None:
    client = Mock()
    station_call = SimpleNamespace(
        type="function_call",
        name="find_transit_station",
        arguments=json.dumps({"query": "정자역"}),
        call_id="station-1",
    )
    client.responses.create.side_effect = [
        SimpleNamespace(output=[station_call], output_text=""),
        SimpleNamespace(output=[], output_text="정자역으로 이동했습니다."),
    ]
    find_transit_station = Mock(
        return_value={
            "total_count": 1,
            "stations": [
                {
                    "name": "정자역",
                    "lines": ["신분당선", "분당선"],
                    "latitude": 37.3671,
                    "longitude": 127.1082,
                }
            ],
        }
    )

    with patch("app.providers.openai_provider.OpenAI", return_value=client):
        provider = OpenAIProvider("test-key", "test-model", "instructions")
        result = provider.generate(
            "정자역으로 이동해줘",
            find_transit_station=find_transit_station,
        )

    find_transit_station.assert_called_once_with({"query": "정자역"})
    assert result.message == "정자역으로 이동했습니다."
    assert len(result.actions) == 1
    assert result.actions[0].type == "MOVE_MAP"
    assert result.actions[0].lat == 37.3671
    assert result.actions[0].lng == 127.1082
    assert result.actions[0].zoom == 16


def test_generate_does_not_offer_or_execute_station_search_for_dong_name() -> None:
    client = Mock()
    station_call = SimpleNamespace(
        type="function_call",
        name="find_transit_station",
        arguments=json.dumps({"query": "판교역"}),
        call_id="incorrect-station-1",
    )
    client.responses.create.side_effect = [
        SimpleNamespace(output=[station_call], output_text=""),
        SimpleNamespace(output=[], output_text="판교동은 현재 지역 이동을 지원하지 않습니다."),
    ]
    find_transit_station = Mock()

    with patch("app.providers.openai_provider.OpenAI", return_value=client):
        provider = OpenAIProvider("test-key", "test-model", "instructions")
        result = provider.generate(
            "판교동으로 이동해줘",
            find_transit_station=find_transit_station,
        )

    first_request_tools = client.responses.create.call_args_list[0].kwargs["tools"]
    assert all(tool["name"] != "find_transit_station" for tool in first_request_tools)
    find_transit_station.assert_not_called()
    rejected_output = json.loads(
        client.responses.create.call_args_list[1].kwargs["input"][-1]["output"]
    )
    assert rejected_output["status"] == "rejected"
    assert result.actions == []

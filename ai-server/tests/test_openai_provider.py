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
    assert first_request["tools"] == [
        tool for tool in AGENT_TOOLS
        if tool["name"] not in {
            "find_transit_station",
            "get_adjacent_legal_dongs",
        }
    ]
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
    assert result.actions[0].zoom == 6


def test_generate_returns_safe_region_selection_action() -> None:
    client = Mock()
    select_call = SimpleNamespace(
        type="function_call",
        name="select_region",
        arguments=json.dumps({"region_name": "판교동"}),
        call_id="select-region-1",
    )
    client.responses.create.side_effect = [
        SimpleNamespace(output=[select_call], output_text=""),
        SimpleNamespace(output=[], output_text="판교동 경계를 지도에 표시했습니다."),
    ]

    with patch("app.providers.openai_provider.OpenAI", return_value=client):
        provider = OpenAIProvider("test-key", "test-model", "instructions")
        result = provider.generate(
            "판교동 경계를 보여줘",
            search_properties=Mock(),
        )

    assert result.message == "판교동 경계를 지도에 표시했습니다."
    assert len(result.actions) == 1
    assert result.actions[0].type == "SELECT_REGION"
    assert result.actions[0].region_name == "판교동"


def test_generate_uses_adjacency_tool_for_neighbor_question() -> None:
    client = Mock()
    adjacency_call = SimpleNamespace(
        type="function_call",
        name="get_adjacent_legal_dongs",
        arguments=json.dumps({"region_name": "판교동"}),
        call_id="adjacent-dongs-1",
    )
    client.responses.create.side_effect = [
        SimpleNamespace(output=[adjacency_call], output_text=""),
        SimpleNamespace(
            output=[],
            output_text="판교동은 삼평동, 백현동, 운중동, 하산운동과 맞닿아 있습니다.",
        ),
    ]
    lookup_adjacency = Mock(
        return_value={
            "source": "bundang_legal_dong.geojson",
            "adjacency_definition": "shared_boundary_longer_than_1_meter",
            "region": {"code": "41135108", "name": "판교동"},
            "adjacent_count": 4,
            "adjacent_regions": [
                {"code": "41135109", "name": "삼평동"},
                {"code": "41135110", "name": "백현동"},
                {"code": "41135115", "name": "운중동"},
                {"code": "41135118", "name": "하산운동"},
            ],
        }
    )

    with patch("app.providers.openai_provider.OpenAI", return_value=client):
        provider = OpenAIProvider("test-key", "test-model", "instructions")
        result = provider.generate(
            "판교동 옆에는 무슨 동이지?",
            get_adjacent_legal_dongs=lookup_adjacency,
        )

    lookup_adjacency.assert_called_once_with({"region_name": "판교동"})
    first_request = client.responses.create.call_args_list[0].kwargs
    assert first_request["tool_choice"] == {
        "type": "function",
        "name": "get_adjacent_legal_dongs",
    }
    assert any(
        tool["name"] == "get_adjacent_legal_dongs"
        for tool in first_request["tools"]
    )
    second_request = client.responses.create.call_args_list[1].kwargs
    assert "tool_choice" not in second_request
    tool_output = json.loads(second_request["input"][-1]["output"])
    assert tool_output["adjacent_count"] == 4
    assert result.actions == []


def test_generate_uses_selected_region_for_this_dong_neighbor_question() -> None:
    client = Mock()
    adjacency_call = SimpleNamespace(
        type="function_call",
        name="get_adjacent_legal_dongs",
        arguments=json.dumps({"region_name": "판교동"}),
        call_id="selected-adjacent-dongs-1",
    )
    client.responses.create.side_effect = [
        SimpleNamespace(output=[adjacency_call], output_text=""),
        SimpleNamespace(output=[], output_text="선택한 동의 인접 지역입니다."),
    ]
    lookup_adjacency = Mock(
        return_value={"adjacent_count": 0, "adjacent_regions": []}
    )
    app_state = {
        "current_page": "map",
        "selected_region": {"type": "legal_dong", "name": "판교동"},
    }

    with patch("app.providers.openai_provider.OpenAI", return_value=client):
        provider = OpenAIProvider("test-key", "test-model", "instructions")
        provider.generate(
            "이 동 옆에는 어디가 있어?",
            app_state=app_state,
            get_adjacent_legal_dongs=lookup_adjacency,
        )

    lookup_adjacency.assert_called_once_with({"region_name": "판교동"})
    assert "'판교동'의 인접 법정동" in (
        client.responses.create.call_args_list[0].kwargs["instructions"]
    )


def test_generate_returns_relative_zoom_action() -> None:
    client = Mock()
    zoom_call = SimpleNamespace(
        type="function_call",
        name="zoom_map",
        arguments=json.dumps({"delta": 1}),
        call_id="zoom-map-1",
    )
    client.responses.create.side_effect = [
        SimpleNamespace(output=[zoom_call], output_text=""),
        SimpleNamespace(output=[], output_text="지도를 한 단계 확대했습니다."),
    ]

    with patch("app.providers.openai_provider.OpenAI", return_value=client):
        provider = OpenAIProvider("test-key", "test-model", "instructions")
        result = provider.generate(
            "조금 확대해줘",
            search_properties=Mock(),
        )

    assert result.message == "지도를 한 단계 확대했습니다."
    assert len(result.actions) == 1
    assert result.actions[0].type == "ZOOM_MAP"
    assert result.actions[0].delta == 1


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
    assert all(tool["name"] != "move_map" for tool in first_request_tools)
    assert any(tool["name"] == "select_region" for tool in first_request_tools)
    find_transit_station.assert_not_called()
    rejected_output = json.loads(
        client.responses.create.call_args_list[1].kwargs["input"][-1]["output"]
    )
    assert rejected_output["status"] == "rejected"
    assert len(result.actions) == 1
    assert result.actions[0].type == "SELECT_REGION"
    assert result.actions[0].region_name == "판교동"


def test_generate_rejects_guessed_coordinates_for_legal_dong_move() -> None:
    client = Mock()
    guessed_move_call = SimpleNamespace(
        type="function_call",
        name="move_map",
        arguments=json.dumps({"lat": 37.38, "lng": 127.12, "zoom": 6}),
        call_id="guessed-dong-move-1",
    )
    client.responses.create.side_effect = [
        SimpleNamespace(output=[guessed_move_call], output_text=""),
        SimpleNamespace(output=[], output_text="서현동으로 이동했습니다."),
    ]

    with patch("app.providers.openai_provider.OpenAI", return_value=client):
        provider = OpenAIProvider("test-key", "test-model", "instructions")
        result = provider.generate(
            "서현동으로 이동해줘",
            search_properties=Mock(),
        )

    first_request = client.responses.create.call_args_list[0].kwargs
    assert all(tool["name"] != "move_map" for tool in first_request["tools"])
    assert "'서현동'" in first_request["instructions"]
    rejected_output = json.loads(
        client.responses.create.call_args_list[1].kwargs["input"][-1]["output"]
    )
    assert rejected_output["status"] == "rejected"
    assert len(result.actions) == 1
    assert result.actions[0].type == "SELECT_REGION"
    assert result.actions[0].region_name == "서현동"


def test_generate_does_not_force_region_selection_for_property_search() -> None:
    client = Mock()
    client.responses.create.return_value = SimpleNamespace(
        output=[],
        output_text="서현동 아파트를 찾아보겠습니다.",
    )

    with patch("app.providers.openai_provider.OpenAI", return_value=client):
        provider = OpenAIProvider("test-key", "test-model", "instructions")
        result = provider.generate(
            "서현동 아파트 보여줘",
            search_properties=Mock(),
        )

    offered_tool_names = {
        tool["name"] for tool in client.responses.create.call_args.kwargs["tools"]
    }
    assert "move_map" in offered_tool_names
    assert result.actions == []

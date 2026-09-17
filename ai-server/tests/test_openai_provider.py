from unittest.mock import Mock, patch
import json
from types import SimpleNamespace

import pytest

from app.providers.openai_provider import AGENT_TOOLS, OpenAIProvider, _bounded_history


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
        store=False,
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


def test_generate_includes_bounded_history_and_recent_context() -> None:
    client = Mock()
    client.responses.create.return_value.output_text = "두 번째 매물입니다."
    history = [
        {"role": "user", "content": "분당 매물 찾아줘"},
        {"role": "assistant", "content": "매물 3건을 찾았습니다."},
    ]

    with patch("app.providers.openai_provider.OpenAI", return_value=client):
        provider = OpenAIProvider("test-key", "test-model", "instructions")
        result = provider.generate(
            "그중 두 번째는?",
            history=history,
            recent_context={
                "recent_property_ids": [101, 205, 333],
                "last_referenced_property_id": None,
            },
        )

    input_items = client.responses.create.call_args.kwargs["input"]
    assert "[101,205,333]" in input_items[0]["content"]
    assert input_items[1:3] == history
    assert input_items[-1] == {"role": "user", "content": "그중 두 번째는?"}
    assert client.responses.create.call_args.kwargs["store"] is False
    assert result.recent_context.recent_property_ids == [101, 205, 333]


def test_bounded_history_keeps_newest_messages_within_limits() -> None:
    history = [
        {"role": "user" if index % 2 == 0 else "assistant", "content": str(index) * 2000}
        for index in range(12)
    ]

    bounded = _bounded_history(history)

    assert len(bounded) <= 8
    assert sum(len(item["content"]) for item in bounded) <= 8000
    assert bounded[-1]["content"].startswith("11")


def test_provider_does_not_retain_context_between_requests() -> None:
    client = Mock()
    client.responses.create.return_value.output_text = "답변"
    with patch("app.providers.openai_provider.OpenAI", return_value=client):
        provider = OpenAIProvider("test-key", "test-model", "instructions")
        provider.generate(
            "그 매물 알려줘",
            history=[{"role": "assistant", "content": "매물 101입니다."}],
            recent_context={"recent_property_ids": [101]},
        )
        provider.generate("새 사용자의 질문")

    second_input = client.responses.create.call_args_list[1].kwargs["input"]
    assert second_input == "새 사용자의 질문"


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
            "get_properties_by_ids",
            "set_presented_properties",
            "add_favorite",
            "remove_favorite",
            "find_transit_station",
            "get_adjacent_legal_dongs",
            "search_real_estate_law",
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
    assert result.recent_context.recent_property_ids == [1, 2]
    assert result.recent_context.last_referenced_property_id is None
    assert [item.id for item in result.recent_context.recent_properties] == [1, 2]


def test_generate_fetches_only_favorite_property_ids() -> None:
    client = Mock()
    favorite_call = SimpleNamespace(
        type="function_call",
        name="get_properties_by_ids",
        arguments=json.dumps({"property_ids": [427, 903]}),
        call_id="favorites-1",
    )
    presented_call = SimpleNamespace(
        type="function_call",
        name="set_presented_properties",
        arguments=json.dumps({"property_ids": [427, 903]}),
        call_id="presented-favorites-1",
    )
    client.responses.create.side_effect = [
        SimpleNamespace(output=[favorite_call], output_text=""),
        SimpleNamespace(output=[presented_call], output_text=""),
        SimpleNamespace(output=[], output_text="관심매물을 비교했습니다."),
    ]
    get_properties_by_ids = Mock(
        return_value={
            "requested_ids": [427, 903],
            "properties": [
                {"id": 427, "sale_price": 780_000_000, "exclusive_area": 84.9},
                {"id": 903, "sale_price": 650_000_000, "exclusive_area": 59.8},
            ],
            "missing_ids": [],
        }
    )

    with patch("app.providers.openai_provider.OpenAI", return_value=client):
        provider = OpenAIProvider("test-key", "test-model", "instructions")
        result = provider.generate(
            "내 관심매물들을 비교해줘.",
            app_state={"favorite_property_ids": [427, 903]},
            get_properties_by_ids=get_properties_by_ids,
        )

    get_properties_by_ids.assert_called_once_with({"property_ids": [427, 903]})
    first_request = client.responses.create.call_args_list[0].kwargs
    assert first_request["tool_choice"] == {
        "type": "function",
        "name": "get_properties_by_ids",
    }
    assert "search_properties" not in {tool["name"] for tool in first_request["tools"]}
    assert "add_favorite" not in {tool["name"] for tool in first_request["tools"]}
    assert "remove_favorite" not in {tool["name"] for tool in first_request["tools"]}
    assert client.responses.create.call_args_list[1].kwargs["tool_choice"] == {
        "type": "function",
        "name": "set_presented_properties",
    }
    tool_output_item = next(
        item
        for item in client.responses.create.call_args_list[1].kwargs["input"]
        if isinstance(item, dict)
        and item.get("type") == "function_call_output"
        and item.get("call_id") == "favorites-1"
    )
    tool_output = json.loads(tool_output_item["output"])
    assert tool_output["properties"][1]["sale_price"] == 650_000_000
    assert result.message == "관심매물을 비교했습니다."
    assert result.actions == []
    assert result.recent_context.recent_property_ids == [427, 903]


def test_generate_maps_favorite_properties_with_existing_actions() -> None:
    client = Mock()
    favorite_call = SimpleNamespace(
        type="function_call",
        name="get_properties_by_ids",
        # The model may omit an ID, but favorite-scope reads must use App State in full.
        arguments=json.dumps({"property_ids": [427, 903]}),
        call_id="favorite-map-1",
    )
    presented_call = SimpleNamespace(
        type="function_call",
        name="set_presented_properties",
        arguments=json.dumps({"property_ids": [427, 903, 1201]}),
        call_id="presented-favorite-map-1",
    )
    client.responses.create.side_effect = [
        SimpleNamespace(output=[favorite_call], output_text=""),
        SimpleNamespace(output=[presented_call], output_text=""),
        SimpleNamespace(output=[], output_text="관심매물을 지도에 표시했습니다."),
    ]
    get_properties_by_ids = Mock(
        return_value={
            "requested_ids": [427, 903, 1201],
            "properties": [
                {"id": 427, "latitude": 37.37, "longitude": 127.11},
                {"id": 903, "latitude": 37.39, "longitude": 127.12},
                {"id": 1201, "latitude": 37.38, "longitude": 127.10},
            ],
            "missing_ids": [],
        }
    )

    with patch("app.providers.openai_provider.OpenAI", return_value=client):
        provider = OpenAIProvider("test-key", "test-model", "instructions")
        result = provider.generate(
            "내 관심매물을 지도에 보여줘.",
            app_state={"favorite_property_ids": [427, 903, 1201]},
            get_properties_by_ids=get_properties_by_ids,
        )

    get_properties_by_ids.assert_called_once_with(
        {"property_ids": [427, 903, 1201]}
    )
    assert [action.type for action in result.actions] == [
        "FIT_BOUNDS",
        "HIGHLIGHT_PROPERTIES",
    ]
    assert result.actions[0].property_ids == [427, 903, 1201]


def test_generate_tracks_only_favorites_presented_in_the_answer() -> None:
    client = Mock()
    favorite_call = SimpleNamespace(
        type="function_call",
        name="get_properties_by_ids",
        arguments=json.dumps({"property_ids": [427, 903, 1201]}),
        call_id="favorite-filter-1",
    )
    presented_call = SimpleNamespace(
        type="function_call",
        name="set_presented_properties",
        arguments=json.dumps({"property_ids": [903, 1201]}),
        call_id="presented-filter-1",
    )
    client.responses.create.side_effect = [
        SimpleNamespace(output=[favorite_call], output_text=""),
        SimpleNamespace(output=[presented_call], output_text=""),
        SimpleNamespace(output=[], output_text="조건에 맞는 관심매물은 두 개입니다."),
    ]
    get_properties_by_ids = Mock(
        return_value={
            "requested_ids": [427, 903, 1201],
            "properties": [
                {"id": 427, "building_name": "다른 단지"},
                {"id": 903, "building_name": "백현마을5단지"},
                {"id": 1201, "building_name": "백현마을5단지"},
            ],
            "missing_ids": [],
        }
    )

    with patch("app.providers.openai_provider.OpenAI", return_value=client):
        provider = OpenAIProvider("test-key", "test-model", "instructions")
        result = provider.generate(
            "백현마을5단지가 내 관심목록에 있나?",
            app_state={"favorite_property_ids": [427, 903, 1201]},
            get_properties_by_ids=get_properties_by_ids,
        )

    assert result.recent_context.recent_property_ids == [903, 1201]
    assert [item.id for item in result.recent_context.recent_properties] == [903, 1201]


def test_generate_answers_favorite_count_without_detail_lookup() -> None:
    client = Mock()
    client.responses.create.return_value = SimpleNamespace(
        output=[],
        output_text="현재 관심매물은 총 3개입니다.",
    )
    get_properties_by_ids = Mock()

    with patch("app.providers.openai_provider.OpenAI", return_value=client):
        provider = OpenAIProvider("test-key", "test-model", "instructions")
        result = provider.generate(
            "현재 관심매물은 몇 개지?",
            app_state={"favorite_property_ids": [427, 903, 1201]},
            get_properties_by_ids=get_properties_by_ids,
        )

    get_properties_by_ids.assert_not_called()
    request = client.responses.create.call_args.kwargs
    assert "get_properties_by_ids" not in {tool["name"] for tool in request["tools"]}
    assert "tool_choice" not in request
    assert "count is 3" in request["instructions"]
    assert result.message == "현재 관심매물은 총 3개입니다."


def test_generate_keeps_empty_favorite_filter_inside_favorite_scope() -> None:
    client = Mock()
    favorite_call = SimpleNamespace(
        type="function_call",
        name="get_properties_by_ids",
        arguments=json.dumps({"property_ids": [427, 903]}),
        call_id="favorite-filter-empty-1",
    )
    presented_call = SimpleNamespace(
        type="function_call",
        name="set_presented_properties",
        arguments=json.dumps({"property_ids": []}),
        call_id="presented-filter-empty-1",
    )
    client.responses.create.side_effect = [
        SimpleNamespace(output=[favorite_call], output_text=""),
        SimpleNamespace(output=[presented_call], output_text=""),
        SimpleNamespace(output=[], output_text="관심매물 중 정자동 매물은 없습니다."),
    ]
    get_properties_by_ids = Mock(
        return_value={
            "requested_ids": [427, 903],
            "properties": [
                {"id": 427, "building_name": "수내동 A"},
                {"id": 903, "building_name": "서현동 B"},
            ],
            "missing_ids": [],
        }
    )
    search_properties = Mock()

    with patch("app.providers.openai_provider.OpenAI", return_value=client):
        provider = OpenAIProvider("test-key", "test-model", "instructions")
        result = provider.generate(
            "내 관심매물 중 정자동에 있는 것만 보여줘.",
            app_state={"favorite_property_ids": [427, 903]},
            recent_context={"recent_property_ids": [1201]},
            get_properties_by_ids=get_properties_by_ids,
            search_properties=search_properties,
        )

    get_properties_by_ids.assert_called_once_with({"property_ids": [427, 903]})
    search_properties.assert_not_called()
    first_request = client.responses.create.call_args_list[0].kwargs
    assert "search_properties" not in {tool["name"] for tool in first_request["tools"]}
    assert result.actions == []
    assert result.recent_context.recent_property_ids == []
    assert result.message == "관심매물 중 정자동 매물은 없습니다."


def test_generate_answers_empty_favorites_without_property_lookup() -> None:
    client = Mock()
    client.responses.create.return_value = SimpleNamespace(
        output=[],
        output_text="현재 관심매물이 없습니다.",
    )
    get_properties_by_ids = Mock()
    search_properties = Mock()

    with patch("app.providers.openai_provider.OpenAI", return_value=client):
        provider = OpenAIProvider("test-key", "test-model", "instructions")
        result = provider.generate(
            "내 관심매물 보여줘.",
            app_state={"favorite_property_ids": []},
            get_properties_by_ids=get_properties_by_ids,
            search_properties=search_properties,
        )

    get_properties_by_ids.assert_not_called()
    search_properties.assert_not_called()
    request = client.responses.create.call_args.kwargs
    tool_names = {tool["name"] for tool in request["tools"]}
    assert "get_properties_by_ids" not in tool_names
    assert "search_properties" not in tool_names
    assert result.actions == []
    assert result.message == "현재 관심매물이 없습니다."


def test_generate_answers_current_selected_property_from_app_state() -> None:
    client = Mock()
    app_state = {
        "selected_property_id": "11400",
        "selected_property": {
            "id": "11400",
            "building_name": "양지마을(6단지)(한양603동)",
            "property_type": "아파트",
            "sale_price": 1_515_000_000,
            "address": "경기도 성남시 분당구 내정로173번길 11",
        },
    }

    with patch("app.providers.openai_provider.OpenAI", return_value=client):
        provider = OpenAIProvider("test-key", "test-model", "instructions")
        result = provider.generate("현재 내가 선택한 아파트는 뭐지?", app_state=app_state)

    client.responses.create.assert_not_called()
    assert result.actions == []
    assert "양지마을(6단지)(한양603동)" in result.message
    assert "11400" in result.message
    assert "1,515,000,000원" in result.message


def test_generate_adds_selected_property_to_favorites() -> None:
    client = Mock()
    add_call = SimpleNamespace(
        type="function_call",
        name="add_favorite",
        arguments=json.dumps({"property_id": 427}),
        call_id="add-favorite-1",
    )
    client.responses.create.side_effect = [
        SimpleNamespace(output=[add_call], output_text=""),
        SimpleNamespace(output=[], output_text="이 매물을 관심매물에 추가했습니다."),
    ]

    with patch("app.providers.openai_provider.OpenAI", return_value=client):
        provider = OpenAIProvider("test-key", "test-model", "instructions")
        result = provider.generate(
            "이 매물 찜해줘.",
            app_state={
                "selected_property": {
                    "id": "427",
                    "building_name": "정든마을 테스트단지",
                },
                "favorite_property_ids": [],
            },
            recent_context={"recent_property_ids": [903], "last_referenced_property_id": 903},
            search_properties=Mock(),
        )

    assert client.responses.create.call_args_list[0].kwargs["tool_choice"] == {
        "type": "function",
        "name": "add_favorite",
    }
    assert result.actions[0].type == "ADD_FAVORITE"
    assert result.actions[0].property_id == 427


def test_generate_rejects_favorite_action_for_mismatched_selected_state() -> None:
    client = Mock()
    client.responses.create.return_value = SimpleNamespace(
        output=[],
        output_text="선택 상태가 일치하지 않습니다. 매물을 다시 선택해 주세요.",
    )

    with patch("app.providers.openai_provider.OpenAI", return_value=client):
        provider = OpenAIProvider("test-key", "test-model", "instructions")
        result = provider.generate(
            "이 매물 찜해줘.",
            app_state={
                "selected_property_id": "903",
                "selected_property": {
                    "id": "427",
                    "building_name": "정든마을 테스트단지",
                },
                "favorite_property_ids": [],
            },
            recent_context={"last_referenced_property_id": 1201},
            search_properties=Mock(),
        )

    request = client.responses.create.call_args.kwargs
    assert "add_favorite" not in {tool["name"] for tool in request["tools"]}
    assert "do not match" in request["instructions"]
    assert result.actions == []


@pytest.mark.parametrize(
    "message",
    [
        "이 매물 찜 해제해줘.",
        "이거 관심매물에서 삭제해줘.",
    ],
)
def test_generate_removes_selected_property_from_favorites(message: str) -> None:
    client = Mock()
    remove_call = SimpleNamespace(
        type="function_call",
        name="remove_favorite",
        arguments=json.dumps({"property_id": 427}),
        call_id="remove-favorite-1",
    )
    client.responses.create.side_effect = [
        SimpleNamespace(output=[remove_call], output_text=""),
        SimpleNamespace(output=[], output_text="이 매물을 관심매물에서 삭제했습니다."),
    ]

    with patch("app.providers.openai_provider.OpenAI", return_value=client):
        provider = OpenAIProvider("test-key", "test-model", "instructions")
        result = provider.generate(
            message,
            app_state={"selected_property_id": "427", "favorite_property_ids": ["427"]},
            search_properties=Mock(),
        )

    assert result.actions[0].type == "REMOVE_FAVORITE"
    assert result.actions[0].property_id == 427


def test_generate_removes_unique_favorite_by_similar_apartment_name() -> None:
    client = Mock()
    remove_call = SimpleNamespace(
        type="function_call",
        name="remove_favorite",
        arguments=json.dumps({"property_id": 31}),
        call_id="remove-favorite-by-name-1",
    )
    client.responses.create.side_effect = [
        SimpleNamespace(output=[remove_call], output_text=""),
        SimpleNamespace(output=[], output_text="양지마을 5단지 매물을 관심목록에서 삭제했습니다."),
    ]
    get_properties_by_ids = Mock(
        return_value={
            "requested_ids": [31, 903],
            "properties": [
                {
                    "id": 31,
                    "building_name": "양지마을(5단지)(한양515-529)",
                    "sale_price": 780_000_000,
                },
                {"id": 903, "building_name": "파크뷰", "sale_price": 900_000_000},
            ],
            "missing_ids": [],
        }
    )

    with patch("app.providers.openai_provider.OpenAI", return_value=client):
        provider = OpenAIProvider("test-key", "test-model", "instructions")
        result = provider.generate(
            "내 관심목록에서 양지마을 5단지는 지워줘.",
            app_state={
                "selected_property_id": "903",
                "favorite_property_ids": [31, 903],
            },
            get_properties_by_ids=get_properties_by_ids,
        )

    get_properties_by_ids.assert_called_once_with({"property_ids": [31, 903]})
    assert result.actions[0].type == "REMOVE_FAVORITE"
    assert result.actions[0].property_id == 31


def test_generate_lists_ambiguous_favorites_for_similar_apartment_name() -> None:
    client = Mock()
    get_properties_by_ids = Mock(
        return_value={
            "requested_ids": [31, 48],
            "properties": [
                {
                    "id": 31,
                    "building_name": "양지마을(5단지)(한양515-529)",
                    "sale_price": 780_000_000,
                    "address": "분당구 수내동 1",
                },
                {
                    "id": 48,
                    "building_name": "양지마을(5단지)(한양501-514)",
                    "sale_price": 720_000_000,
                    "address": "분당구 수내동 2",
                },
            ],
            "missing_ids": [],
        }
    )

    with patch("app.providers.openai_provider.OpenAI", return_value=client):
        provider = OpenAIProvider("test-key", "test-model", "instructions")
        result = provider.generate(
            "양지마을 5단지 지워줘.",
            app_state={"favorite_property_ids": [31, 48]},
            get_properties_by_ids=get_properties_by_ids,
        )

    client.responses.create.assert_not_called()
    assert result.actions == []
    assert result.recent_context.recent_property_ids == [31, 48]
    assert "양지마을(5단지)(한양515-529)" in result.message
    assert "양지마을(5단지)(한양501-514)" in result.message
    assert "매물 ID 31" in result.message
    assert "매물 ID 48" in result.message


def test_generate_does_not_remove_when_favorite_name_has_no_match() -> None:
    client = Mock()
    client.responses.create.return_value = SimpleNamespace(
        output=[],
        output_text="관심목록에서 이름이 비슷한 매물을 찾지 못했습니다.",
    )
    get_properties_by_ids = Mock(
        return_value={
            "requested_ids": [903],
            "properties": [{"id": 903, "building_name": "파크뷰"}],
            "missing_ids": [],
        }
    )

    with patch("app.providers.openai_provider.OpenAI", return_value=client):
        provider = OpenAIProvider("test-key", "test-model", "instructions")
        result = provider.generate(
            "양지마을 5단지 지워줘.",
            app_state={"favorite_property_ids": [903]},
            get_properties_by_ids=get_properties_by_ids,
        )

    client.responses.create.assert_called_once()
    assert result.actions == []
    assert "찾지 못했습니다" in result.message


def test_generate_lets_model_clear_entire_favorite_list() -> None:
    client = Mock()
    clear_call = SimpleNamespace(
        type="function_call",
        name="clear_favorites",
        arguments="{}",
        call_id="clear-favorites-1",
    )
    client.responses.create.side_effect = [
        SimpleNamespace(output=[clear_call], output_text=""),
        SimpleNamespace(output=[], output_text="관심매물 3개를 모두 삭제했습니다."),
    ]
    get_properties_by_ids = Mock(
        return_value={
            "requested_ids": [427, 903, 1201],
            "properties": [
                {"id": 427, "building_name": "정든마을"},
                {"id": 903, "building_name": "파크뷰"},
                {"id": 1201, "building_name": "양지마을"},
            ],
            "missing_ids": [],
        }
    )

    with patch("app.providers.openai_provider.OpenAI", return_value=client):
        provider = OpenAIProvider("test-key", "test-model", "instructions")
        result = provider.generate(
            "현재 관심목록에 있는 것들을 다 삭제해줘.",
            app_state={"favorite_property_ids": [427, 903, 1201]},
            get_properties_by_ids=get_properties_by_ids,
        )

    assert [action.type for action in result.actions] == [
        "REMOVE_FAVORITE",
        "REMOVE_FAVORITE",
        "REMOVE_FAVORITE",
    ]
    assert [action.property_id for action in result.actions] == [427, 903, 1201]
    assert result.message == "관심매물 3개를 모두 삭제했습니다."


def test_generate_plural_favorites_adds_one_selected_property() -> None:
    client = Mock()
    add_call = SimpleNamespace(
        type="function_call",
        name="add_favorites",
        arguments=json.dumps({"property_ids": [427]}),
        call_id="add-favorites-one",
    )
    client.responses.create.side_effect = [
        SimpleNamespace(output=[add_call], output_text=""),
        SimpleNamespace(output=[], output_text="선택한 매물을 관심매물에 추가했습니다."),
    ]

    with patch("app.providers.openai_provider.OpenAI", return_value=client):
        provider = OpenAIProvider("test-key", "test-model", "instructions")
        result = provider.generate(
            "이 매물 찜해줘.",
            app_state={"selected_property_id": "427", "favorite_property_ids": []},
            search_properties=Mock(),
        )

    assert [(action.type, action.property_id) for action in result.actions] == [
        ("ADD_FAVORITE", 427)
    ]


def test_generate_plural_favorites_adds_all_recent_properties_by_distinct_id() -> None:
    client = Mock()
    add_call = SimpleNamespace(
        type="function_call",
        name="add_favorites",
        arguments=json.dumps({"property_ids": [101, 102, 103]}),
        call_id="add-favorites-three",
    )
    client.responses.create.side_effect = [
        SimpleNamespace(output=[add_call], output_text=""),
        SimpleNamespace(output=[], output_text="매물 3개를 관심매물에 추가했습니다."),
    ]

    with patch("app.providers.openai_provider.OpenAI", return_value=client):
        provider = OpenAIProvider("test-key", "test-model", "instructions")
        result = provider.generate(
            "이거 3개 모두 찜해줘.",
            app_state={"favorite_property_ids": []},
            recent_context={
                "recent_property_ids": [101, 102, 103],
                "recent_properties": [
                    {"id": 101, "title": "효자촌(럭키)"},
                    {"id": 102, "title": "효자촌(럭키)"},
                    {"id": 103, "title": "다른 단지"},
                ],
            },
            search_properties=Mock(),
        )

    assert [action.property_id for action in result.actions] == [101, 102, 103]


def test_generate_plural_favorites_adds_second_and_third_recent_properties() -> None:
    client = Mock()
    add_call = SimpleNamespace(
        type="function_call",
        name="add_favorites",
        arguments=json.dumps({"property_ids": [102, 103]}),
        call_id="add-favorites-two",
    )
    client.responses.create.side_effect = [
        SimpleNamespace(output=[add_call], output_text=""),
        SimpleNamespace(output=[], output_text="두 매물을 관심매물에 추가했습니다."),
    ]

    with patch("app.providers.openai_provider.OpenAI", return_value=client):
        provider = OpenAIProvider("test-key", "test-model", "instructions")
        result = provider.generate(
            "두 번째와 세 번째 찜해줘.",
            app_state={"favorite_property_ids": []},
            recent_context={"recent_property_ids": [101, 102, 103]},
            search_properties=Mock(),
        )

    assert [action.property_id for action in result.actions] == [102, 103]


def test_generate_plural_favorites_removes_two_recent_properties() -> None:
    client = Mock()
    remove_call = SimpleNamespace(
        type="function_call",
        name="remove_favorites",
        arguments=json.dumps({"property_ids": [102, 103]}),
        call_id="remove-favorites-two",
    )
    client.responses.create.side_effect = [
        SimpleNamespace(output=[remove_call], output_text=""),
        SimpleNamespace(output=[], output_text="두 매물을 관심매물에서 삭제했습니다."),
    ]

    with patch("app.providers.openai_provider.OpenAI", return_value=client):
        provider = OpenAIProvider("test-key", "test-model", "instructions")
        result = provider.generate(
            "이 두 개 찜 해제해줘.",
            app_state={"favorite_property_ids": [102, 103]},
            recent_context={"recent_property_ids": [101, 102, 103]},
            search_properties=Mock(),
        )

    assert [(action.type, action.property_id) for action in result.actions] == [
        ("REMOVE_FAVORITE", 102),
        ("REMOVE_FAVORITE", 103),
    ]


def test_generate_plural_favorites_rejects_ids_outside_allowed_context() -> None:
    client = Mock()
    add_call = SimpleNamespace(
        type="function_call",
        name="add_favorites",
        arguments=json.dumps({"property_ids": [999]}),
        call_id="add-favorites-invalid",
    )
    client.responses.create.side_effect = [
        SimpleNamespace(output=[add_call], output_text=""),
        SimpleNamespace(output=[], output_text="추가할 매물을 확인할 수 없습니다."),
    ]

    with patch("app.providers.openai_provider.OpenAI", return_value=client):
        provider = OpenAIProvider("test-key", "test-model", "instructions")
        result = provider.generate(
            "이 매물들 찜해줘.",
            app_state={"selected_property_id": "427", "favorite_property_ids": []},
            recent_context={"recent_property_ids": [101, 102]},
            search_properties=Mock(),
        )

    assert result.actions == []


def test_generate_plural_favorites_accepts_ids_from_current_search_results() -> None:
    client = Mock()
    search_call = SimpleNamespace(
        type="function_call",
        name="search_properties",
        arguments=json.dumps({
            "keyword": "서현동",
            "property_type": "아파트",
            "max_price": None,
            "limit": 3,
            "sort_by": "sale_price",
            "sort_order": "asc",
        }),
        call_id="search-before-add",
    )
    add_call = SimpleNamespace(
        type="function_call",
        name="add_favorites",
        arguments=json.dumps({"property_ids": [201, 202, 203]}),
        call_id="add-search-results",
    )
    client.responses.create.side_effect = [
        SimpleNamespace(output=[search_call], output_text=""),
        SimpleNamespace(output=[add_call], output_text=""),
        SimpleNamespace(output=[], output_text="검색된 매물 3개를 관심매물에 추가했습니다."),
    ]
    search_properties = Mock(return_value={
        "total_count": 3,
        "properties": [
            {"id": 201, "building_name": "효자촌(럭키)", "sale_price": 500_000_000},
            {"id": 202, "building_name": "효자촌(럭키)", "sale_price": 580_000_000},
            {"id": 203, "building_name": "다른 단지", "sale_price": 620_000_000},
        ],
    })

    with patch("app.providers.openai_provider.OpenAI", return_value=client):
        provider = OpenAIProvider("test-key", "test-model", "instructions")
        result = provider.generate(
            "서현동에서 가장 싼 3개 매물을 관심매물에 추가해줘.",
            app_state={"favorite_property_ids": []},
            search_properties=search_properties,
        )

    favorite_actions = [
        action for action in result.actions if action.type == "ADD_FAVORITE"
    ]
    assert [action.property_id for action in favorite_actions] == [201, 202, 203]


def test_generate_uses_explicit_property_id_for_favorite_action() -> None:
    client = Mock()
    add_call = SimpleNamespace(
        type="function_call",
        name="add_favorite",
        arguments=json.dumps({"property_id": 903}),
        call_id="add-explicit-favorite-1",
    )
    client.responses.create.side_effect = [
        SimpleNamespace(output=[add_call], output_text=""),
        SimpleNamespace(output=[], output_text="903번 매물을 관심매물에 추가했습니다."),
    ]

    with patch("app.providers.openai_provider.OpenAI", return_value=client):
        provider = OpenAIProvider("test-key", "test-model", "instructions")
        result = provider.generate(
            "903번 매물 찜해줘.",
            app_state={"selected_property_id": "427", "favorite_property_ids": []},
            search_properties=Mock(),
        )

    assert result.actions[0].property_id == 903


def test_generate_does_not_guess_favorite_target() -> None:
    client = Mock()
    client.responses.create.return_value = SimpleNamespace(
        output=[],
        output_text="어떤 매물을 관심매물에 추가할까요?",
    )

    with patch("app.providers.openai_provider.OpenAI", return_value=client):
        provider = OpenAIProvider("test-key", "test-model", "instructions")
        result = provider.generate("이 매물 찜해줘.", search_properties=Mock())

    request = client.responses.create.call_args.kwargs
    tool_names = {tool["name"] for tool in request["tools"]}
    assert "add_favorite" not in tool_names
    assert "remove_favorite" not in tool_names
    assert result.actions == []
    assert result.message == "어떤 매물을 관심매물에 추가할까요?"


@pytest.mark.parametrize(
    ("message", "favorite_ids", "expected_message"),
    [
        ("이 매물 찜해줘.", ["427"], "이미 관심매물에 등록되어 있습니다."),
        ("이 매물 찜 해제해줘.", [], "현재 관심매물에 등록되어 있지 않습니다."),
    ],
)
def test_generate_skips_idempotent_favorite_action(
    message: str,
    favorite_ids: list[str],
    expected_message: str,
) -> None:
    client = Mock()
    client.responses.create.return_value = SimpleNamespace(
        output=[],
        output_text=expected_message,
    )

    with patch("app.providers.openai_provider.OpenAI", return_value=client):
        provider = OpenAIProvider("test-key", "test-model", "instructions")
        result = provider.generate(
            message,
            app_state={
                "selected_property_id": "427",
                "favorite_property_ids": favorite_ids,
            },
            search_properties=Mock(),
        )

    assert result.actions == []
    assert "tool_choice" not in client.responses.create.call_args.kwargs
    assert result.message == expected_message


def test_generate_removes_favorite_by_displayed_list_position() -> None:
    client = Mock()
    remove_call = SimpleNamespace(
        type="function_call",
        name="remove_favorite",
        arguments=json.dumps({"property_id": 903}),
        call_id="remove-listed-favorite-1",
    )
    client.responses.create.side_effect = [
        SimpleNamespace(output=[remove_call], output_text=""),
        SimpleNamespace(output=[], output_text="2번 관심매물을 삭제했습니다."),
    ]

    with patch("app.providers.openai_provider.OpenAI", return_value=client):
        provider = OpenAIProvider("test-key", "test-model", "instructions")
        result = provider.generate(
            "여기서 2번을 삭제해줘.",
            app_state={
                "selected_property_id": "427",
                "favorite_property_ids": ["427", "903"],
            },
            recent_context={"recent_property_ids": [427, 903]},
            search_properties=Mock(),
        )

    assert result.actions[0].type == "REMOVE_FAVORITE"
    assert result.actions[0].property_id == 903


def test_generate_rejects_out_of_range_favorite_position() -> None:
    client = Mock()
    client.responses.create.return_value = SimpleNamespace(
        output=[],
        output_text="목록에 3번 매물은 없습니다. 삭제할 매물을 다시 선택해 주세요.",
    )

    with patch("app.providers.openai_provider.OpenAI", return_value=client):
        provider = OpenAIProvider("test-key", "test-model", "instructions")
        result = provider.generate(
            "여기서 3번을 삭제해줘.",
            app_state={
                "selected_property_id": "427",
                "favorite_property_ids": ["427", "903"],
            },
            recent_context={"recent_property_ids": [427, 903]},
            search_properties=Mock(),
        )

    assert result.actions == []
    assert "tool_choice" not in client.responses.create.call_args.kwargs


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


def test_generate_executes_law_search_and_returns_results_to_model() -> None:
    client = Mock()
    law_call = SimpleNamespace(
        type="function_call",
        name="search_real_estate_law",
        arguments=json.dumps({"query": "전입신고하면 대항력은 언제 생겨?"}),
        call_id="law-search-1",
    )
    client.responses.create.side_effect = [
        SimpleNamespace(output=[law_call], output_text=""),
        SimpleNamespace(
            output=[],
            output_text="주택임대차보호법 제3조에 따르면 다음 날부터 효력이 생깁니다.",
        ),
    ]
    search_law = Mock(
        return_value={
            "query": "전입신고하면 대항력은 언제 생겨?",
            "total_count": 1,
            "results": [
                {
                    "law_name": "주택임대차보호법",
                    "article_number": "제3조",
                    "text": "주택의 인도와 주민등록을 마친 때에는 그 다음 날부터 효력이 생긴다.",
                    "effective_date": "2026-01-02",
                    "source_url": "https://www.law.go.kr/LSW/lsInfoP.do?lsiSeq=276291",
                    "score": 0.91,
                }
            ],
        }
    )

    with patch("app.providers.openai_provider.OpenAI", return_value=client):
        provider = OpenAIProvider("test-key", "test-model", "instructions")
        result = provider.generate(
            "전입신고하면 대항력이 언제 생겨?",
            search_real_estate_law=search_law,
        )

    search_law.assert_called_once_with(
        {
            "query": "전입신고하면 대항력은 언제 생겨?",
            "_user_question": "전입신고하면 대항력이 언제 생겨?",
        }
    )
    first_tools = client.responses.create.call_args_list[0].kwargs["tools"]
    assert any(tool["name"] == "search_real_estate_law" for tool in first_tools)
    second_input = client.responses.create.call_args_list[1].kwargs["input"]
    output = json.loads(second_input[-2]["output"])
    assert output["results"][0]["article_number"] == "제3조"
    assert second_input[-1]["role"] == "developer"
    assert "rank 1" in second_input[-1]["content"]
    assert "제3조" in result.message
    assert "관련 법령" in result.message
    assert "국가법령정보센터에서 확인하기" in result.message
    assert result.actions == []


def test_generate_normalizes_model_law_link_text() -> None:
    client = Mock()
    law_call = SimpleNamespace(
        type="function_call",
        name="search_real_estate_law",
        arguments=json.dumps({"query": "대항력 발생 시점"}),
        call_id="law-search-link-label",
    )
    source_url = "https://www.law.go.kr/LSW/lsInfoP.do?lsiSeq=276291"
    client.responses.create.side_effect = [
        SimpleNamespace(output=[law_call], output_text=""),
        SimpleNamespace(
            output=[],
            output_text=(
                "주택임대차보호법 제3조에 따르면 다음 날부터 효력이 생깁니다.\n\n"
                f"자세한 내용은 [**여기서 확인하실 수 있습니다**]({source_url})."
            ),
        ),
    ]
    search_law = Mock(
        return_value={
            "total_count": 1,
            "results": [
                {
                    "law_name": "주택임대차보호법",
                    "article_number": "제3조",
                    "effective_date": "2026-01-02",
                    "text": "그 다음 날부터 효력이 생긴다.",
                    "source_url": source_url,
                }
            ],
        }
    )

    with patch("app.providers.openai_provider.OpenAI", return_value=client):
        provider = OpenAIProvider("test-key", "test-model", "instructions")
        result = provider.generate(
            "전입신고를 하면 대항력은 언제 생겨?",
            search_real_estate_law=search_law,
        )

    assert "여기서 확인하실 수 있습니다" not in result.message
    assert result.message.count("국가법령정보센터에서 확인하기") == 1
    assert result.message.count(source_url) == 1


def test_generate_keeps_general_law_answer_when_search_is_empty() -> None:
    client = Mock()
    law_call = SimpleNamespace(
        type="function_call",
        name="search_real_estate_law",
        arguments=json.dumps({"query": "대항력 발생 시점"}),
        call_id="law-search-empty",
    )
    client.responses.create.side_effect = [
        SimpleNamespace(output=[law_call], output_text=""),
        SimpleNamespace(output=[], output_text="일반적으로는 계약 내용과 신고 상황을 함께 확인해야 합니다. 실제 적용 전 최신 법령을 확인하세요."),
    ]
    search_law = Mock(
        return_value={"query": "대항력 발생 시점", "total_count": 0, "results": []}
    )

    with patch("app.providers.openai_provider.OpenAI", return_value=client):
        provider = OpenAIProvider("test-key", "test-model", "instructions")
        result = provider.generate(
            "전입신고를 하면 대항력은 언제 생겨?",
            search_real_estate_law=search_law,
        )

    assert "계약 내용과 신고 상황" in result.message
    assert "직접 확인하지 못했습니다" in result.message


def test_generate_allows_general_explanation_when_retrieval_is_partial() -> None:
    client = Mock()
    law_call = SimpleNamespace(
        type="function_call",
        name="search_real_estate_law",
        arguments=json.dumps({"query": "임대차 계약"}),
        call_id="law-search-partial",
    )
    client.responses.create.side_effect = [
        SimpleNamespace(output=[law_call], output_text=""),
        SimpleNamespace(
            output=[],
            output_text="검색된 조문은 임대차의 기본 요건을 설명합니다. 그 밖의 세부 적용은 일반적으로 계약 내용과 사실관계를 함께 봅니다.",
        ),
    ]
    search_law = Mock(return_value={
        "total_count": 1,
        "results": [{
            "law_name": "주택임대차보호법",
            "article_number": "제3조",
            "text": "주택의 인도와 주민등록",
            "source_url": "https://www.law.go.kr/example",
        }],
    })

    with patch("app.providers.openai_provider.OpenAI", return_value=client):
        provider = OpenAIProvider("test-key", "test-model", "instructions")
        result = provider.generate("임대차 계약에서 무엇을 확인해야 해?", search_real_estate_law=search_law)

    assert "계약 내용과 사실관계" in result.message
    assert "관련 법령" not in result.message


def test_generate_blocks_unretrieved_article_when_search_is_empty() -> None:
    client = Mock()
    law_call = SimpleNamespace(
        type="function_call",
        name="search_real_estate_law",
        arguments=json.dumps({"query": "임대차 계약"}),
        call_id="law-search-empty-citation",
    )
    client.responses.create.side_effect = [
        SimpleNamespace(output=[law_call], output_text=""),
        SimpleNamespace(output=[], output_text="주택임대차보호법 제99조에 따르면 확정됩니다."),
    ]
    search_law = Mock(return_value={"total_count": 0, "results": []})

    with patch("app.providers.openai_provider.OpenAI", return_value=client):
        provider = OpenAIProvider("test-key", "test-model", "instructions")
        result = provider.generate("임대차 계약에서 무엇을 확인해야 해?", search_real_estate_law=search_law)

    assert "조문 인용이 일치하지 않아" in result.message
    assert "제99조" not in result.message


def test_generate_blocks_law_citation_not_present_in_search_results() -> None:
    client = Mock()
    law_call = SimpleNamespace(
        type="function_call",
        name="search_real_estate_law",
        arguments=json.dumps({"query": "대항력 발생 시점"}),
        call_id="law-search-mismatch",
    )
    client.responses.create.side_effect = [
        SimpleNamespace(output=[law_call], output_text=""),
        SimpleNamespace(
            output=[],
            output_text="주택임대차보호법 제3조의3에 따르면 당일부터 효력이 생깁니다.",
        ),
    ]
    search_law = Mock(
        return_value={
            "query": "대항력 발생 시점",
            "total_count": 1,
            "results": [
                {
                    "law_name": "주택임대차보호법",
                    "article_number": "제3조",
                    "text": "그 다음 날부터 효력이 생긴다.",
                    "source_url": "https://www.law.go.kr/example",
                }
            ],
        }
    )

    with patch("app.providers.openai_provider.OpenAI", return_value=client):
        provider = OpenAIProvider("test-key", "test-model", "instructions")
        result = provider.generate(
            "전입신고를 하면 대항력은 언제 생겨?",
            search_real_estate_law=search_law,
        )

    assert "조문 인용이 일치하지 않아" in result.message
    assert "당일부터" not in result.message


def test_generate_keeps_model_law_query_isolated_from_long_user_question() -> None:
    client = Mock()
    law_call = SimpleNamespace(
        type="function_call",
        name="search_real_estate_law",
        arguments=json.dumps({"query": "대항력 발생 시점"}),
        call_id="law-search-long-query",
    )
    client.responses.create.side_effect = [
        SimpleNamespace(output=[law_call], output_text=""),
        SimpleNamespace(output=[], output_text="근거를 찾지 못했습니다."),
    ]
    search_law = Mock(return_value={"total_count": 0, "results": []})

    with patch("app.providers.openai_provider.OpenAI", return_value=client):
        provider = OpenAIProvider("test-key", "test-model", "instructions")
        provider.generate("전입신고 " * 150, search_real_estate_law=search_law)

    arguments = search_law.call_args.args[0]
    assert arguments["query"] == "대항력 발생 시점"
    assert arguments["_user_question"] == "전입신고 " * 150


def test_generate_does_not_call_law_search_for_property_request() -> None:
    client = Mock()
    client.responses.create.return_value = SimpleNamespace(
        output=[],
        output_text="매물 검색 조건을 확인하겠습니다.",
    )
    search_law = Mock()

    with patch("app.providers.openai_provider.OpenAI", return_value=client):
        provider = OpenAIProvider("test-key", "test-model", "instructions")
        provider.generate(
            "판교역 8억 이하 아파트 찾아줘.",
            search_real_estate_law=search_law,
        )

    search_law.assert_not_called()

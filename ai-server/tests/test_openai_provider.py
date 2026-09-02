from unittest.mock import Mock, patch
import json

from app.providers.openai_provider import OpenAIProvider


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
    assert result == "상담 답변"


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
    assert result == "현재 지도 기준 상담 답변"

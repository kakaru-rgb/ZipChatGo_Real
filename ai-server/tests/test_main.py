from fastapi.testclient import TestClient
import httpx
from openai import APIConnectionError

import app.main as main
from app.main import app, get_openai_provider


client = TestClient(app)


def test_agent_test_returns_hello() -> None:
    response = client.post("/agent/test")

    assert response.status_code == 200
    assert response.json() == {"message": "hello"}


class FakeOpenAIProvider:
    def __init__(self) -> None:
        self.app_state = None

    def generate(self, message: str, app_state=None) -> str:
        self.app_state = app_state
        return f"AI response to: {message}"


def test_agent_chat_returns_provider_response() -> None:
    provider = FakeOpenAIProvider()
    app.dependency_overrides[get_openai_provider] = lambda: provider
    try:
        response = client.post(
            "/agent/chat",
            json={
                "message": "안녕하세요",
                "appState": {
                    "current_page": "map",
                    "map_center": {"lat": 37.4, "lng": 127.15},
                    "zoom": 11,
                    "map_bounds": {
                        "south": 37.3,
                        "west": 127.0,
                        "north": 37.5,
                        "east": 127.3,
                    },
                    "selected_region": "성남시 분당구 정자동",
                    "selected_property_id": "427",
                    "favorite_property_ids": ["182", "427"],
                    "filters": {
                        "keyword": "정자동",
                        "property_type": "아파트",
                        "max_price": 800000000,
                    },
                },
            },
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json() == {"message": "AI response to: 안녕하세요"}
    assert provider.app_state["selected_property_id"] == "427"
    assert provider.app_state["filters"]["max_price"] == 800000000


def test_agent_chat_rejects_empty_message() -> None:
    response = client.post("/agent/chat", json={"message": ""})

    assert response.status_code == 422


def test_agent_chat_returns_503_when_api_key_is_missing(monkeypatch) -> None:
    get_openai_provider.cache_clear()
    monkeypatch.setattr(main, "get_openai_api_key", lambda: "")
    try:
        response = client.post("/agent/chat", json={"message": "안녕하세요"})
    finally:
        get_openai_provider.cache_clear()

    assert response.status_code == 503
    assert response.json() == {"detail": "OPENAI_API_KEY is not configured"}


class FailingOpenAIProvider:
    def generate(self, message: str, app_state=None) -> str:
        raise APIConnectionError(request=httpx.Request("POST", "https://api.openai.com"))


def test_agent_chat_returns_502_when_openai_request_fails() -> None:
    app.dependency_overrides[get_openai_provider] = lambda: FailingOpenAIProvider()
    try:
        response = client.post("/agent/chat", json={"message": "안녕하세요"})
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 502
    assert response.json() == {"detail": "OpenAI API request failed"}

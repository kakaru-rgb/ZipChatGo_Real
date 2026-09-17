"""One-off live smoke test for the bounded browser conversation payload."""
from __future__ import annotations

import csv
import json
import sys
import time
from pathlib import Path
from typing import Any

from openai import OpenAI

ROOT = Path(__file__).resolve().parents[1]
PROJECT = ROOT.parent
sys.path.insert(0, str(ROOT))

from app.config import get_openai_api_key, get_openai_model, get_spring_server_base_url
from app.prompts import REAL_ESTATE_AGENT_INSTRUCTIONS
from app.providers.openai_provider import OpenAIProvider
from app.retrievers.openai_vector_store_law_retriever import OpenAIVectorStoreLawRetriever
from app.tools.legal_dong_adjacency import LegalDongAdjacencyTool
from app.tools.property_search import PropertySearchTool
from app.tools.real_estate_law import RealEstateLawSearchTool
from app.tools.transit_station import TransitStationTool

STORE = "vs_6aa764aaf2008191af233d99e6fd6cd2"
OUTPUT = PROJECT / "docs/evaluation/production_agent_multiturn_smoke_6.csv"
QUESTIONS = [
    "분당에서 6억 이하 아파트 찾아줘.",
    "그중 가장 싼 건?",
    "그 매물 근처에 역 있어?",
    "거기로 지도 이동해줘.",
    "전세로 계약하면 보증금 보호는 어떻게 해야 해?",
    "아까 말한 매물 다시 알려줘.",
]


class ResponsesObserver:
    def __init__(self, target: Any) -> None:
        self.target = target
        self.calls: list[dict[str, Any]] = []
        self.input_tokens = 0
        self.output_tokens = 0
        self.rounds = 0

    def create(self, *args: Any, **kwargs: Any) -> Any:
        kwargs["store"] = False
        self.rounds += 1
        response = self.target.create(*args, **kwargs)
        self.calls.extend(
            {"name": item.name, "arguments": item.arguments}
            for item in response.output if item.type == "function_call"
        )
        usage = response.usage
        self.input_tokens += usage.input_tokens
        self.output_tokens += usage.output_tokens
        return response


class ClientProxy:
    def __init__(self, client: Any, responses: ResponsesObserver) -> None:
        self._client = client
        self.responses = responses

    def __getattr__(self, name: str) -> Any:
        return getattr(self._client, name)


def append_history(history: list[dict[str, str]], role: str, content: str) -> None:
    history.append({"role": role, "content": content.strip()[:4000]})
    del history[:-8]
    while len(history) > 1 and sum(len(item["content"]) for item in history) > 8000:
        history.pop(0)


def main() -> None:
    if OUTPUT.exists():
        raise RuntimeError(f"Output already exists: {OUTPUT}")
    key = get_openai_api_key()
    model = get_openai_model()
    spring = get_spring_server_base_url()
    property_tool = PropertySearchTool(spring)
    station_tool = TransitStationTool(spring)
    adjacency_tool = LegalDongAdjacencyTool()
    law_tool = RealEstateLawSearchTool(OpenAIVectorStoreLawRetriever(key, STORE))
    history: list[dict[str, str]] = []
    context: dict[str, Any] = {}
    app_state = {
        "current_page": "map",
        "map_center": {"lat": 37.394, "lng": 127.111},
        "zoom": 5,
        "map_bounds": {"south": 37.32, "west": 127.02, "north": 37.43, "east": 127.18},
    }
    rows = []
    for turn, question in enumerate(QUESTIONS, 1):
        client = OpenAI(api_key=key, max_retries=0)
        observer = ResponsesObserver(client.responses)
        provider = OpenAIProvider(key, model, REAL_ESTATE_AGENT_INSTRUCTIONS)
        provider._client = ClientProxy(client, observer)
        history_count = len(history)
        history_chars = sum(len(item["content"]) for item in history)
        started = time.perf_counter()
        error = ""
        try:
            reply = provider.generate(
                question,
                app_state=app_state,
                history=history,
                recent_context=context,
                search_properties=property_tool.search,
                find_transit_station=station_tool.search,
                get_adjacent_legal_dongs=adjacency_tool.lookup,
                search_real_estate_law=law_tool.search,
            )
            context = reply.recent_context.model_dump()
            append_history(history, "user", question)
            append_history(history, "assistant", reply.message)
            actions = [item.model_dump() for item in reply.actions]
            final_response = reply.message
        except Exception as exception:
            error = f"{type(exception).__name__}: {exception}"
            actions = []
            final_response = ""
        rows.append({
            "Turn": turn,
            "Model": model,
            "Question": question,
            "HistoryMessages": history_count,
            "HistoryCharacters": history_chars,
            "InputTokens": observer.input_tokens,
            "OutputTokens": observer.output_tokens,
            "TotalTokens": observer.input_tokens + observer.output_tokens,
            "LatencyMs": round((time.perf_counter() - started) * 1000),
            "ResponseRounds": observer.rounds,
            "ActualTools": json.dumps(observer.calls, ensure_ascii=False),
            "Actions": json.dumps(actions, ensure_ascii=False),
            "RecentContext": json.dumps(context, ensure_ascii=False),
            "FinalResponse": final_response,
            "Error": error,
        })
    with OUTPUT.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    print(json.dumps([{key: row[key] for key in (
        "Turn", "HistoryMessages", "HistoryCharacters", "InputTokens",
        "TotalTokens", "LatencyMs", "ActualTools", "Actions", "Error"
    )} for row in rows], ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

"""Live, search-only regression through the production law Agent path."""

from __future__ import annotations

import csv
import json
import subprocess
import sys
import time
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from openai import OpenAI


AI_SERVER_ROOT = Path(__file__).resolve().parents[1]
PROJECT_ROOT = AI_SERVER_ROOT.parent
if str(AI_SERVER_ROOT) not in sys.path:
    sys.path.insert(0, str(AI_SERVER_ROOT))

from app.config import get_openai_api_key
from app.prompts import REAL_ESTATE_AGENT_INSTRUCTIONS
from app.providers.openai_provider import OpenAIProvider
from app.retrievers.openai_vector_store_law_retriever import OpenAIVectorStoreLawRetriever
from app.tools.real_estate_law import RealEstateLawSearchTool


MODEL = "gpt-5.6-luna"
VECTOR_STORE_ID = "vs_6aa764aaf2008191af233d99e6fd6cd2"
CORPUS_VERSION = "law_store_v2"
OUTPUT = PROJECT_ROOT / "docs/evaluation/production_law_v2_real_user24_live.csv"
QUESTIONS = (
    ("A", "general", "전세 계약을 앞두고 있는데 보증금을 안전하게 지키려면 무엇부터 확인해야 하나요?"),
    ("A", "general", "집주인이 바뀌어도 제 전세 계약은 그대로 유지되나요?"),
    ("A", "general", "임대인이 계약금을 돌려주지 않으면 보통 어떤 순서로 대응하나요?"),
    ("A", "general", "중개사가 설명해 준 내용과 실제 집 상태가 다르면 어떻게 해야 하나요?"),
    ("B", "precise", "전입신고와 집 인도를 마치면 주택 임차인의 대항력은 정확히 언제 생기나요?"),
    ("B", "precise", "묵시적으로 갱신된 전세 계약을 임차인이 해지하면 효력은 언제 발생하나요?"),
    ("B", "precise", "계약갱신요구권은 몇 번 행사할 수 있고 갱신 기간은 얼마인가요?"),
    ("B", "precise", "부동산 매매 계약을 체결한 뒤 거래신고는 누가 언제까지 해야 하나요?"),
    ("B", "precise", "임차권등기명령을 신청하려면 어떤 요건을 갖춰야 하나요?"),
    ("C", "named_law", "주택임대차보호법에서는 집주인이 바뀌었을 때 임차인을 어떻게 보호하나요?"),
    ("C", "named_law", "공인중개사법에서 중개사가 계약 전에 설명해야 하는 중요한 사항은 무엇인가요?"),
    ("C", "named_law", "상가건물 임대차보호법에서는 임차인의 계약갱신을 어떻게 다루나요?"),
    ("D", "named_article", "주택임대차보호법 제6조의2에 따른 묵시적 갱신 후 해지는 어떻게 되나요?"),
    ("D", "named_article", "공인중개사법 제25조의 확인·설명 의무는 실제 거래에서 무엇을 뜻하나요?"),
    ("D", "named_article", "부동산 거래신고 등에 관한 법률 제3조에서 매매 계약 신고는 어떻게 규정하나요?"),
    ("E", "partial", "전세 계약에서 대항력과 우선변제권을 갖춰도 보증금을 못 돌려받을 위험이 있나요?"),
    ("E", "partial", "상가 임대차에서 계약갱신 요구와 권리금 회수 기회를 함께 고려하면 무엇을 주의해야 하나요?"),
    ("E", "partial", "공동명의 아파트를 살 때 계약서, 등기, 대출 책임을 법적으로 어떻게 나눠 생각해야 하나요?"),
    ("F", "source_sensitive", "최근 대법원 판례에서 전세사기 피해자의 보증금 회수에 새로 인정한 내용이 있나요?"),
    ("F", "source_sensitive", "최신 행정해석으로 중개사가 관리비를 설명해야 하는 범위가 바뀌었나요?"),
    ("G", "possible_gap", "분묘기지권을 시효로 취득한 경우 최신 판례에 따른 지료 지급 시점은 언제인가요?"),
    ("G", "possible_gap", "해외에 거주하는 한국인이 외국에서 작성한 위임장으로 국내 집을 팔 때 공증과 인증은 어떻게 하나요?"),
    ("H", "nonlegal", "집찾GO의 AI 채팅으로 어떤 도움을 받을 수 있나요?"),
    ("H", "nonlegal", "집을 보러 갈 때 채광과 소음을 쉽게 확인하는 팁을 알려주세요."),
)


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), default=str)


class ResponsesProxy:
    def __init__(self, responses: Any) -> None:
        self._responses = responses
        self.rounds = 0
        self.input_tokens = 0
        self.output_tokens = 0
        self.usage_available = True
        self.calls: list[dict[str, Any]] = []
        self.terminal_raw_response = ""

    def create(self, *args: Any, **kwargs: Any) -> Any:
        kwargs["store"] = False
        self.rounds += 1
        response = self._responses.create(*args, **kwargs)
        function_calls = [
            {"name": item.name, "arguments": item.arguments}
            for item in response.output if item.type == "function_call"
        ]
        self.calls.extend(function_calls)
        if not function_calls:
            self.terminal_raw_response = response.output_text
        usage = getattr(response, "usage", None)
        if usage is None:
            self.usage_available = False
        else:
            self.input_tokens += int(getattr(usage, "input_tokens", 0) or 0)
            self.output_tokens += int(getattr(usage, "output_tokens", 0) or 0)
        return response

    def __getattr__(self, name: str) -> Any:
        return getattr(self._responses, name)


class VectorStoresProxy:
    def __init__(self, vector_stores: Any) -> None:
        self._vector_stores = vector_stores
        self.searches: list[dict[str, Any]] = []

    def search(self, *args: Any, **kwargs: Any) -> Any:
        page = self._vector_stores.search(*args, **kwargs)
        self.searches.append({
            "query": kwargs.get("query", ""),
            "filters": kwargs.get("filters"),
            "raw_result_count": len(getattr(page, "data", [])),
        })
        return page

    def __getattr__(self, name: str) -> Any:
        raise AttributeError(f"Vector Store {name} is unavailable in search-only regression")


class ClientProxy:
    def __init__(self, client: Any, *, responses: ResponsesProxy | None = None,
                 vector_stores: VectorStoresProxy | None = None) -> None:
        self._client = client
        if responses is not None:
            self.responses = responses
        if vector_stores is not None:
            self.vector_stores = vector_stores

    def __getattr__(self, name: str) -> Any:
        return getattr(self._client, name)


def _git_commit() -> str:
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=PROJECT_ROOT,
        capture_output=True, text=True, check=True,
    )
    return result.stdout.strip()


def _write_rows(rows: list[dict[str, str]]) -> None:
    temporary = OUTPUT.with_suffix(".csv.tmp")
    with temporary.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    temporary.replace(OUTPUT)


def main() -> int:
    if len(QUESTIONS) != 24 or OUTPUT.exists():
        raise RuntimeError("frozen 24-question set changed or output already exists")
    api_key = get_openai_api_key()
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY is required")
    run_id = f"production-law-v2-real-user24-{uuid.uuid4().hex[:12]}"
    git_commit = _git_commit()
    evaluated_at = datetime.now(ZoneInfo("Asia/Seoul")).isoformat(timespec="seconds")
    rows: list[dict[str, str]] = []
    for question_id, (category, kind, question) in enumerate(QUESTIONS, 1):
        print(f"Evaluating {question_id}/24 once: {category}", flush=True)
        response_client = OpenAI(api_key=api_key, max_retries=0)
        vector_client = OpenAI(api_key=api_key, max_retries=0)
        responses = ResponsesProxy(response_client.responses)
        vector_stores = VectorStoresProxy(vector_client.vector_stores)
        provider = OpenAIProvider(api_key, MODEL, REAL_ESTATE_AGENT_INSTRUCTIONS)
        provider._client = ClientProxy(response_client, responses=responses)
        retriever = OpenAIVectorStoreLawRetriever(
            api_key, VECTOR_STORE_ID,
            client=ClientProxy(vector_client, vector_stores=vector_stores),
        )
        tool = RealEstateLawSearchTool(retriever)
        tool_results: list[dict[str, Any]] = []

        def observed_law_search(arguments: dict[str, Any]) -> dict[str, Any]:
            before = len(vector_stores.searches)
            result = tool.search(arguments)
            tool_results.append({
                "arguments": arguments,
                "result": result,
                "vector_searches": vector_stores.searches[before:],
            })
            return result

        started = time.perf_counter()
        final_response = ""
        error = ""
        try:
            reply = provider.generate(
                message=question,
                app_state=None,
                search_real_estate_law=observed_law_search,
            )
            final_response = reply.message
        except Exception as exception:
            error = f"{type(exception).__name__}: {exception}"
        searches = vector_stores.searches
        exact_searches = [item for item in searches if item["filters"] and item["filters"].get("type") == "and"]
        semantic_searches = [item for item in searches if item not in exact_searches]
        filtered_searches = [item for item in semantic_searches if item["filters"] is not None]
        rows.append({
            "RunID": run_id,
            "EvaluationTimestamp": evaluated_at,
            "GitCommit": git_commit,
            "AgentModel": MODEL,
            "CorpusVersion": CORPUS_VERSION,
            "VectorStoreID": VECTOR_STORE_ID,
            "ResponsesStore": "false",
            "SDKRetry": "0",
            "ManualRetry": "0",
            "QuestionID": str(question_id),
            "Category": category,
            "QuestionKind": kind,
            "UserQuestion": question,
            "LawToolCallCount": str(len(tool_results)),
            "ResponseRounds": str(responses.rounds),
            "ToolCalls": _json(responses.calls),
            "ToolResults": _json(tool_results),
            "VectorSearchTrace": _json(searches),
            "AFilterSearchCount": str(len(filtered_searches)),
            "BExactSearchCount": str(len(exact_searches)),
            "BExactHitCount": str(sum(item["raw_result_count"] > 0 for item in exact_searches)),
            "BExactMissCount": str(sum(item["raw_result_count"] == 0 for item in exact_searches)),
            "BExactFallbackCount": str(sum(
                any(item["filters"] and item["filters"].get("type") == "and"
                    and item["raw_result_count"] == 0 for item in call["vector_searches"])
                and any(not item["filters"] or item["filters"].get("type") != "and"
                    for item in call["vector_searches"])
                for call in tool_results
            )),
            "C1SemanticQueries": _json([item["query"] for item in semantic_searches]),
            "SemanticSearchCount": str(len(semantic_searches)),
            "SemanticRawResultCount": str(sum(item["raw_result_count"] for item in semantic_searches)),
            "RawAgentResponse": responses.terminal_raw_response,
            "FinalResponse": final_response,
            "ExecutionError": error,
            "LatencyMs": str(round((time.perf_counter() - started) * 1000)),
            "InputTokens": str(responses.input_tokens),
            "OutputTokens": str(responses.output_tokens),
            "TotalTokens": str(responses.input_tokens + responses.output_tokens),
            "TokenUsageAvailable": "Y" if responses.usage_available else "N",
            "Provenance": "pending_question_level_review" if kind != "nonlegal" else "not_applicable",
            "ReviewNotes": "",
        })
        _write_rows(rows)
    print(f"Saved {len(rows)} rows: {OUTPUT}")
    print(f"RunID: {run_id}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

from __future__ import annotations

import argparse
import csv
import json
import subprocess
import sys
import time
import uuid
from pathlib import Path
from typing import Any

from openai import OpenAI


AI_SERVER_ROOT = Path(__file__).resolve().parents[1]
PROJECT_ROOT = AI_SERVER_ROOT.parent
if str(AI_SERVER_ROOT) not in sys.path:
    sys.path.insert(0, str(AI_SERVER_ROOT))

from app.config import get_openai_api_key, get_spring_server_base_url
from app.evaluation.canonical_catalog_law_experiment import (
    CanonicalCatalogExactLawArticleHandler,
    CanonicalCatalogLawNameFilterHandler,
)
from app.evaluation.canonical_law_catalog import CanonicalLawCatalog
from app.evaluation.exact_law_article_experiment import (
    OpenAIVectorStoreExactLawArticleLookup,
)
from app.evaluation.law_name_filter_experiment import observe_experimental_provider
from app.evaluation.production_agent_observer import ProductionAgentObserver
from app.evaluation.semantic_query_isolation_experiment import SemanticQueryIsolationHandler
from app.evaluation.user_generalization_regression import (
    AGENT_MODEL,
    CORPUS_VERSION,
    EVALUATION_MODE,
    FROZEN_USER_REGRESSION_QUESTIONS,
    VECTOR_STORE_ID,
    ResponseCapture,
    apply_c21_validation,
    is_infrastructure_failure,
)
from app.prompts import REAL_ESTATE_AGENT_INSTRUCTIONS
from app.providers.openai_provider import OpenAIProvider
from app.retrievers.openai_vector_store_law_retriever import OpenAIVectorStoreLawRetriever
from app.tools.legal_dong_adjacency import LegalDongAdjacencyTool
from app.tools.property_search import PropertySearchTool
from app.tools.real_estate_law import RealEstateLawSearchTool
from app.tools.transit_station import TransitStationTool


DEFAULT_CATALOG = Path(
    r"C:\ajb\2025_exam\law_rag_vector_store_builds\20260914T030618795400Z"
) / "new_store_files.json"
DEFAULT_OUTPUT = (
    PROJECT_ROOT
    / "docs/evaluation/production_agent_law_store_v2_generalization_regression_20.csv"
)

FIELDS = (
    "RunID", "평가일시", "CorpusVersion", "VectorStoreID", "GitCommit",
    "EvaluationMode", "AgentModel", "문항ID", "그룹", "UserQuestion",
    "LawTool호출여부", "다른Tool호출여부", "호출Tool목록", "전체Tool호출횟수",
    "LawTool호출횟수", "ModelGeneratedLawQueries", "CanonicalLawNamesDetected",
    "AppliedLawNames", "LawNameFilterTrace", "ExactPairsDetected",
    "ExactLookupAttempted", "ExactLookupHit", "ExactLookupMiss",
    "ExactLookupTrace", "C1SemanticQueries", "C1Trace", "SemanticTopK",
    "ToolCalls", "ResponseRounds", "PreValidationRawResponse", "C21CitationTrace",
    "ValidationResult", "ValidationFailureReason", "FinalAnswer", "AgentActions",
    "ExecutionError", "FailureCategory", "LatencyMs", "InputTokens", "OutputTokens",
    "TotalTokens", "TokenUsageAvailable",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run the frozen 20-question law_store_v2 user generalization regression."
    )
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--catalog-json", type=Path, default=DEFAULT_CATALOG)
    parser.add_argument("--model", default=AGENT_MODEL)
    parser.add_argument("--vector-store-id", default=VECTOR_STORE_ID)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    output = args.output.resolve()
    if output.exists():
        print(f"ERROR: output already exists: {output}", file=sys.stderr)
        return 2
    if args.model != AGENT_MODEL or args.vector_store_id != VECTOR_STORE_ID:
        print("ERROR: model and Vector Store are frozen for this regression", file=sys.stderr)
        return 2

    catalog = CanonicalLawCatalog.from_new_store_files(
        args.catalog_json,
        corpus_version=CORPUS_VERSION,
        expected_file_count=5658,
        expected_law_count=49,
    )
    api_key = get_openai_api_key()
    if not api_key:
        print("ERROR: OPENAI_API_KEY is required", file=sys.stderr)
        return 2

    git_commit = _git_commit()
    evaluated_at = _evaluation_timestamp()
    run_id = f"law-v2-user-regression-{uuid.uuid4().hex[:12]}"
    rows: list[dict[str, str]] = []

    for index, question in enumerate(FROZEN_USER_REGRESSION_QUESTIONS, start=1):
        print(
            f"Evaluating {index}/20 exactly once: user question {question.question_id}",
            flush=True,
        )
        runtime = _build_runtime(
            api_key=api_key,
            vector_store_id=args.vector_store_id,
            model=args.model,
            catalog=catalog,
            question_text=question.question,
        )
        started = time.perf_counter()
        raw_response = ""
        actions = "[]"
        error = ""
        try:
            wrapped = {
                name: runtime["observer"].wrap_handler(name, handler)
                for name, handler in runtime["handlers"].items()
            }
            reply = runtime["provider"].generate(
                message=question.question,
                app_state=None,
                search_properties=wrapped["search_properties"],
                find_transit_station=wrapped["find_transit_station"],
                get_adjacent_legal_dongs=wrapped["get_adjacent_legal_dongs"],
                search_real_estate_law=wrapped["search_real_estate_law"],
            )
            raw_response = reply.message
            actions = json.dumps(
                [action.model_dump() for action in reply.actions],
                ensure_ascii=False,
                separators=(",", ":"),
            )
        except Exception as exception:
            error = f"{type(exception).__name__}: {exception}"
        latency_ms = round((time.perf_counter() - started) * 1000)

        observer = runtime["observer"]
        capture = runtime["capture"]
        exact = runtime["exact"]
        isolation = runtime["isolation"]
        law_traces = observer.law_traces()
        c21 = apply_c21_validation(
            pre_validation_response=capture.raw_response,
            production_response=raw_response,
            law_tool_trace=law_traces,
            error=error,
        )
        rows.append(
            _row(
                run_id=run_id,
                evaluated_at=evaluated_at,
                git_commit=git_commit,
                question=question,
                observer=observer,
                capture=capture,
                exact=exact,
                isolation=isolation,
                law_traces=law_traces,
                c21=c21,
                actions=actions,
                error=error,
                latency_ms=latency_ms,
            )
        )
        _write_rows(rows, output)

    print(f"Saved {len(rows)} rows: {output}")
    return 0


def _build_runtime(
    *,
    api_key: str,
    vector_store_id: str,
    model: str,
    catalog: CanonicalLawCatalog,
    question_text: str,
) -> dict[str, Any]:
    observer = ProductionAgentObserver()
    capture = ResponseCapture()
    provider = OpenAIProvider(api_key, model, REAL_ESTATE_AGENT_INSTRUCTIONS)
    # The frozen regression forbids retrying a failed question. Replace only
    # this evaluation instance's SDK client; production Provider code/config
    # remains unchanged.
    provider._client = OpenAI(api_key=api_key, max_retries=0)
    observe_experimental_provider(provider, observer, capture)
    vector_client = OpenAI(api_key=api_key, max_retries=0)
    retriever = OpenAIVectorStoreLawRetriever(
        api_key,
        vector_store_id,
        client=vector_client,
    )
    model_query_supplier = lambda: _latest_model_law_query(observer)
    law_name_filter = CanonicalCatalogLawNameFilterHandler(
        RealEstateLawSearchTool(retriever).search,
        catalog,
        question_text=question_text,
        model_query_supplier=model_query_supplier,
    )
    isolation = SemanticQueryIsolationHandler(law_name_filter, model_query_supplier)
    exact = CanonicalCatalogExactLawArticleHandler(
        OpenAIVectorStoreExactLawArticleLookup(vector_client, vector_store_id),
        isolation,
        catalog,
        model_query_supplier=model_query_supplier,
    )
    spring_url = get_spring_server_base_url()
    return {
        "provider": provider,
        "observer": observer,
        "capture": capture,
        "exact": exact,
        "isolation": isolation,
        "handlers": {
            "search_properties": PropertySearchTool(spring_url).search,
            "find_transit_station": TransitStationTool(spring_url).search,
            "get_adjacent_legal_dongs": LegalDongAdjacencyTool().lookup,
            "search_real_estate_law": exact,
        },
    }


def _row(**values: Any) -> dict[str, str]:
    observer = values["observer"]
    capture = values["capture"]
    exact = values["exact"]
    isolation = values["isolation"]
    law_traces = values["law_traces"]
    c21 = values["c21"]
    question = values["question"]
    calls = observer.calls
    law_names = list(
        dict.fromkeys(
            name for trace in exact.semantic_handler.traces for name in trace.law_names
        )
    )
    pairs = list(
        dict.fromkeys(
            (pair.law_name, pair.article_number)
            for trace in exact.traces
            for pair in trace.detected_pairs
        )
    )
    semantic_top_k = _semantic_top_k(law_traces, exact.traces, isolation.isolation_traces)
    other_tools = [call.name for call in calls if call.name != "search_real_estate_law"]
    error = values["error"]
    return {
        "RunID": values["run_id"],
        "평가일시": values["evaluated_at"],
        "CorpusVersion": CORPUS_VERSION,
        "VectorStoreID": VECTOR_STORE_ID,
        "GitCommit": values["git_commit"],
        "EvaluationMode": EVALUATION_MODE,
        "AgentModel": AGENT_MODEL,
        "문항ID": str(question.question_id),
        "그룹": question.group,
        "UserQuestion": question.question,
        "LawTool호출여부": "Y" if law_traces else "N",
        "다른Tool호출여부": "Y" if other_tools else "N",
        "호출Tool목록": " | ".join(call.name for call in calls),
        "전체Tool호출횟수": str(len(calls)),
        "LawTool호출횟수": str(len(law_traces)),
        "ModelGeneratedLawQueries": " | ".join(
            str(trace.get("model_query", "")) for trace in law_traces
        ),
        "CanonicalLawNamesDetected": " | ".join(law_names),
        "AppliedLawNames": " | ".join(law_names),
        "LawNameFilterTrace": _json([trace.__dict__ for trace in exact.semantic_handler.traces]),
        "ExactPairsDetected": " | ".join(f"{law} {article}" for law, article in pairs),
        "ExactLookupAttempted": "Y" if any(trace.attempted for trace in exact.traces) else "N",
        "ExactLookupHit": "Y" if any(trace.hit for trace in exact.traces) else "N",
        "ExactLookupMiss": "Y" if any(trace.attempted and not trace.hit for trace in exact.traces) else "N",
        "ExactLookupTrace": _json([
            {
                "model_query": trace.model_query,
                "detected_pairs": [pair.as_dict() for pair in trace.detected_pairs],
                "attempted": trace.attempted,
                "hit": trace.hit,
                "semantic_fallback": trace.semantic_fallback,
            }
            for trace in exact.traces
        ]),
        "C1SemanticQueries": " | ".join(
            trace.semantic_query for trace in isolation.isolation_traces
        ),
        "C1Trace": _json([trace.as_dict() for trace in isolation.isolation_traces]),
        "SemanticTopK": _json(semantic_top_k),
        "ToolCalls": _json([call.as_dict() for call in calls]),
        "ResponseRounds": str(capture.response_rounds),
        "PreValidationRawResponse": capture.raw_response,
        "C21CitationTrace": _json(c21.citation_trace),
        "ValidationResult": c21.validation_result,
        "ValidationFailureReason": c21.validation_failure_reason,
        "FinalAnswer": c21.final_answer,
        "AgentActions": values["actions"],
        "ExecutionError": error,
        "FailureCategory": (
            "infrastructure_failure"
            if error and is_infrastructure_failure(error)
            else "tool_loop_error"
            if "OpenAIToolLoopError" in error
            else "other_execution_error"
            if error
            else ""
        ),
        "LatencyMs": str(values["latency_ms"]),
        "InputTokens": str(capture.input_tokens) if capture.usage_available else "",
        "OutputTokens": str(capture.output_tokens) if capture.usage_available else "",
        "TotalTokens": str(capture.total_tokens) if capture.usage_available else "",
        "TokenUsageAvailable": "Y" if capture.usage_available else "N",
    }


def _semantic_top_k(law_traces, exact_traces, isolation_traces) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    isolation_index = 0
    for call_index, exact_trace in enumerate(exact_traces):
        if not exact_trace.semantic_fallback:
            continue
        isolation_trace = (
            isolation_traces[isolation_index]
            if isolation_index < len(isolation_traces)
            else None
        )
        isolation_index += 1
        tool_trace = law_traces[call_index] if call_index < len(law_traces) else {}
        results = (tool_trace.get("handler_result") or {}).get("results", [])
        output.append(
            {
                "tool_call_sequence": call_index + 1,
                "semantic_query": getattr(isolation_trace, "semantic_query", ""),
                "results": [
                    {
                        "rank": item.get("rank"),
                        "score": item.get("score"),
                        "law_name": item.get("law_name"),
                        "article_number": item.get("article_number"),
                    }
                    for item in results
                    if isinstance(item, dict)
                ],
            }
        )
    return output


def _latest_model_law_query(observer: ProductionAgentObserver) -> str:
    for call in reversed(observer.calls):
        if call.name != "search_real_estate_law" or not call.handler_called:
            continue
        try:
            arguments = json.loads(call.model_arguments)
        except (TypeError, json.JSONDecodeError):
            return ""
        if isinstance(arguments, dict):
            return str(arguments.get("query", "")).strip()
    return ""


def _write_rows(rows: list[dict[str, str]], output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_suffix(output.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    temporary.replace(output)


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), default=str)


def _git_commit() -> str:
    return subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=PROJECT_ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def _evaluation_timestamp() -> str:
    from datetime import datetime
    from zoneinfo import ZoneInfo

    return datetime.now(ZoneInfo("Asia/Seoul")).isoformat(timespec="seconds")


if __name__ == "__main__":
    raise SystemExit(main())

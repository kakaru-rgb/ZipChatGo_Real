from __future__ import annotations

import argparse
import csv
import json
import subprocess
import sys
import time
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Sequence
from zoneinfo import ZoneInfo


AI_SERVER_ROOT = Path(__file__).resolve().parents[1]
PROJECT_ROOT = AI_SERVER_ROOT.parent
if str(AI_SERVER_ROOT) not in sys.path:
    sys.path.insert(0, str(AI_SERVER_ROOT))

from app.evaluation.canonical_law_catalog import CanonicalLawCatalog
from app.evaluation.pair_aware_grounding_validator_c21 import (
    collect_retrieval_results,
)
from app.evaluation.pair_aware_grounding_validator_c22 import (
    PairAwareGroundingValidatorC22,
)
from app.evaluation.user_generalization_regression import (
    CORPUS_VERSION,
    FROZEN_USER_REGRESSION_QUESTIONS,
    is_infrastructure_failure,
)
from scripts.evaluate_law_store_v2_generalization_regression import (
    _build_runtime,
    _semantic_top_k,
)


AGENT_MODEL = "gpt-5.6-luna"
VECTOR_STORE_ID = "vs_6aa764aaf2008191af233d99e6fd6cd2"
EVALUATION_MODE = "production_agent_law_store_v2_c22_luna_live_integrated_targeted"
TARGET_IDS = (1, 3, 6, 14, 15, 18)
DEFAULT_CATALOG = Path(
    r"C:\ajb\2025_exam\law_rag_vector_store_builds\20260914T030618795400Z"
) / "new_store_files.json"
DEFAULT_OUTPUT = (
    PROJECT_ROOT
    / "docs/evaluation/production_agent_law_store_v2_c22_luna_live_integrated_targeted.csv"
)
C22_REJECTION_RESPONSE = (
    "검색된 공식 법령 근거와 답변의 법령·조문 인용이 일치하지 않거나 "
    "근거가 충분하지 않아 확정적인 법률 답변을 제공하지 않았습니다."
)

FIELDS = (
    "RunID", "EvaluationTimestamp", "GitCommit", "EvaluationMode",
    "CorpusVersion", "VectorStoreID", "AgentModel", "QuestionID", "Group",
    "UserQuestion", "TopLevelGenerateCount", "ToolNames", "ToolCallCount",
    "LawToolCalled", "OtherToolCalled", "LawToolCallCount", "ResponseRounds",
    "ModelGeneratedLawQueries", "CanonicalLawNamesDetected", "AppliedLawNames",
    "LawNameFilterTrace", "ExactPairsDetected", "ExactLookupAttempted",
    "ExactLookupHit", "ExactLookupMiss", "ExactLookupTrace", "C1SemanticQueries",
    "C1Trace", "SemanticTopK", "ToolCalls", "PreValidationRawResponse",
    "C22ValidationResult", "C22ResponseRole", "C22AffirmativeCitations",
    "C22NegativeOrUnavailableReferences", "C22CitationTrace",
    "C22ValidationFailureReason", "FinalAnswer", "AgentActions", "ExecutionError",
    "FailureCategory", "LatencyMs", "InputTokens", "OutputTokens", "TotalTokens",
    "TokenUsageAvailable",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run the frozen six-question Luna C2.2 live targeted regression."
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
    from app.config import get_openai_api_key

    api_key = get_openai_api_key()
    if not api_key:
        print("ERROR: OPENAI_API_KEY is required", file=sys.stderr)
        return 2

    questions = tuple(
        question
        for question in FROZEN_USER_REGRESSION_QUESTIONS
        if question.question_id in TARGET_IDS
    )
    if tuple(question.question_id for question in questions) != TARGET_IDS:
        print("ERROR: frozen target question set changed", file=sys.stderr)
        return 2

    run_id = f"law-v2-c22-luna-targeted-{uuid.uuid4().hex[:12]}"
    evaluated_at = datetime.now(ZoneInfo("Asia/Seoul")).isoformat(timespec="seconds")
    git_commit = _git_commit()
    rows: list[dict[str, str]] = []

    for index, question in enumerate(questions, start=1):
        print(
            f"Evaluating {index}/{len(questions)} exactly once: user question {question.question_id}",
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
        production_response = ""
        actions = "[]"
        error = ""
        top_level_generate_count = 0
        try:
            wrapped = {
                name: runtime["observer"].wrap_handler(name, handler)
                for name, handler in runtime["handlers"].items()
            }
            top_level_generate_count += 1
            reply = runtime["provider"].generate(
                message=question.question,
                app_state=None,
                search_properties=wrapped["search_properties"],
                find_transit_station=wrapped["find_transit_station"],
                get_adjacent_legal_dongs=wrapped["get_adjacent_legal_dongs"],
                search_real_estate_law=wrapped["search_real_estate_law"],
            )
            production_response = reply.message
            actions = _json([action.model_dump() for action in reply.actions])
        except Exception as exception:
            error = f"{type(exception).__name__}: {exception}"
        latency_ms = round((time.perf_counter() - started) * 1000)

        rows.append(
            _make_row(
                run_id=run_id,
                evaluated_at=evaluated_at,
                git_commit=git_commit,
                question=question,
                runtime=runtime,
                production_response=production_response,
                actions=actions,
                error=error,
                latency_ms=latency_ms,
                top_level_generate_count=top_level_generate_count,
            )
        )
        _write_rows(rows, output)

    print(f"Saved {len(rows)} rows: {output}")
    print(f"RunID: {run_id}")
    return 0


def _make_row(**values: Any) -> dict[str, str]:
    runtime = values["runtime"]
    observer = runtime["observer"]
    capture = runtime["capture"]
    exact = runtime["exact"]
    isolation = runtime["isolation"]
    calls = observer.calls
    law_traces = observer.law_traces()
    other_tools = [call.name for call in calls if call.name != "search_real_estate_law"]
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
    error = values["error"]
    validation = _apply_c22(
        pre_validation_response=capture.raw_response,
        production_response=values["production_response"],
        law_tool_trace=law_traces,
        error=error,
    )
    affirmative = [
        citation
        for citation in validation["citations"]
        if citation.get("citation_role") != "negative_or_unavailable_reference"
    ]
    negative = [
        citation
        for citation in validation["citations"]
        if citation.get("citation_role") == "negative_or_unavailable_reference"
    ]
    return {
        "RunID": values["run_id"],
        "EvaluationTimestamp": values["evaluated_at"],
        "GitCommit": values["git_commit"],
        "EvaluationMode": EVALUATION_MODE,
        "CorpusVersion": CORPUS_VERSION,
        "VectorStoreID": VECTOR_STORE_ID,
        "AgentModel": AGENT_MODEL,
        "QuestionID": str(values["question"].question_id),
        "Group": values["question"].group,
        "UserQuestion": values["question"].question,
        "TopLevelGenerateCount": str(values["top_level_generate_count"]),
        "ToolNames": " | ".join(call.name for call in calls),
        "ToolCallCount": str(len(calls)),
        "LawToolCalled": "Y" if law_traces else "N",
        "OtherToolCalled": "Y" if other_tools else "N",
        "LawToolCallCount": str(len(law_traces)),
        "ResponseRounds": str(capture.response_rounds),
        "ModelGeneratedLawQueries": " | ".join(
            str(trace.get("model_query", "")) for trace in law_traces
        ),
        "CanonicalLawNamesDetected": " | ".join(law_names),
        "AppliedLawNames": " | ".join(law_names),
        "LawNameFilterTrace": _json(
            [trace.__dict__ for trace in exact.semantic_handler.traces]
        ),
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
        "SemanticTopK": _json(
            _semantic_top_k(law_traces, exact.traces, isolation.isolation_traces)
        ),
        "ToolCalls": _json([call.as_dict() for call in calls]),
        "PreValidationRawResponse": capture.raw_response,
        "C22ValidationResult": validation["result"],
        "C22ResponseRole": validation["response_role"],
        "C22AffirmativeCitations": _json(affirmative),
        "C22NegativeOrUnavailableReferences": _json(negative),
        "C22CitationTrace": _json(validation["citations"]),
        "C22ValidationFailureReason": validation["failure_reason"],
        "FinalAnswer": validation["final_answer"],
        "AgentActions": values["actions"],
        "ExecutionError": error,
        "FailureCategory": _failure_category(error),
        "LatencyMs": str(values["latency_ms"]),
        "InputTokens": str(capture.input_tokens) if capture.usage_available else "",
        "OutputTokens": str(capture.output_tokens) if capture.usage_available else "",
        "TotalTokens": str(capture.total_tokens) if capture.usage_available else "",
        "TokenUsageAvailable": "Y" if capture.usage_available else "N",
    }


def _apply_c22(
    *,
    pre_validation_response: str,
    production_response: str,
    law_tool_trace: Sequence[dict[str, Any]],
    error: str,
) -> dict[str, Any]:
    if error:
        return {
            "result": "not_reached",
            "response_role": "not_reached",
            "failure_reason": "provider_error",
            "citations": [],
            "final_answer": "",
        }
    if not law_tool_trace:
        return {
            "result": "not_applied",
            "response_role": "not_applied",
            "failure_reason": "law_tool_not_called",
            "citations": [],
            "final_answer": pre_validation_response or production_response,
        }
    if not pre_validation_response:
        return {
            "result": "not_reached",
            "response_role": "not_reached",
            "failure_reason": "no_terminal_pre_validation_response",
            "citations": [],
            "final_answer": production_response,
        }

    retrieval_results = collect_retrieval_results(law_tool_trace)
    outcome = PairAwareGroundingValidatorC22().validate(
        pre_validation_response,
        retrieval_results,
    )
    return {
        "result": "passed" if outcome.passed else "rejected",
        "response_role": outcome.response_role,
        "failure_reason": outcome.failure_reason,
        "citations": list(outcome.citations),
        "final_answer": pre_validation_response if outcome.passed else C22_REJECTION_RESPONSE,
    }


def _failure_category(error: str) -> str:
    if not error:
        return ""
    if is_infrastructure_failure(error):
        return "infrastructure_failure"
    if "OpenAIToolLoopError" in error:
        return "tool_loop_error"
    return "other_execution_error"


def _write_rows(rows: list[dict[str, str]], output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_suffix(output.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    temporary.replace(output)


def _git_commit() -> str:
    return subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=PROJECT_ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), default=str)


if __name__ == "__main__":
    raise SystemExit(main())

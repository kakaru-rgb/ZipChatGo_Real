from __future__ import annotations

import argparse
import json
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
from app.evaluation.pair_aware_grounding_validator_c21 import collect_retrieval_results
from app.evaluation.pair_aware_grounding_validator_c23 import (
    PairAwareGroundingValidatorC23,
)
from app.evaluation.user_generalization_regression import (
    CORPUS_VERSION,
    FROZEN_USER_REGRESSION_QUESTIONS,
)
from scripts import evaluate_law_store_v2_c22_luna_targeted as base


AGENT_MODEL = "gpt-5.6-luna"
VECTOR_STORE_ID = "vs_6aa764aaf2008191af233d99e6fd6cd2"
EVALUATION_MODE = "production_agent_law_store_v2_c23_luna_user20_live"
TARGET_IDS = tuple(range(1, 21))
DEFAULT_CATALOG = Path(
    r"C:\ajb\2025_exam\law_rag_vector_store_builds\20260914T030618795400Z"
) / "new_store_files.json"
DEFAULT_OUTPUT = (
    PROJECT_ROOT
    / "docs/evaluation/production_agent_law_store_v2_c23_luna_user20_live.csv"
)


class _StoreFalseResponses:
    """Evaluation-only proxy that disables Responses API persistence."""

    def __init__(self, responses: Any) -> None:
        self._responses = responses

    def create(self, *args: Any, **kwargs: Any) -> Any:
        kwargs["store"] = False
        return self._responses.create(*args, **kwargs)

    def __getattr__(self, name: str) -> Any:
        return getattr(self._responses, name)


class _StoreFalseOpenAIClient:
    def __init__(self, client: Any) -> None:
        self._client = client
        self.responses = _StoreFalseResponses(client.responses)

    def __getattr__(self, name: str) -> Any:
        return getattr(self._client, name)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run the frozen 20-question Luna A+B+C1+C2.3 live regression."
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
        print("ERROR: frozen 20-question set changed", file=sys.stderr)
        return 2

    # The existing runner owns the frozen A+B+C1 observation path. Override only
    # its evaluation labels and offline validation application in this process.
    base.AGENT_MODEL = AGENT_MODEL
    base.VECTOR_STORE_ID = VECTOR_STORE_ID
    base.EVALUATION_MODE = EVALUATION_MODE
    base._apply_c22 = _apply_c23

    run_id = f"law-v2-c23-luna-user20-{uuid.uuid4().hex[:12]}"
    evaluated_at = datetime.now(ZoneInfo("Asia/Seoul")).isoformat(timespec="seconds")
    git_commit = base._git_commit()
    rows: list[dict[str, str]] = []

    for index, question in enumerate(questions, start=1):
        print(
            f"Evaluating {index}/{len(questions)} exactly once: user question {question.question_id}",
            flush=True,
        )
        runtime = base._build_runtime(
            api_key=api_key,
            vector_store_id=args.vector_store_id,
            model=args.model,
            catalog=catalog,
            question_text=question.question,
        )
        runtime["provider"]._client = _StoreFalseOpenAIClient(
            runtime["provider"]._client
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
            actions = base._json([action.model_dump() for action in reply.actions])
        except Exception as exception:
            error = f"{type(exception).__name__}: {exception}"
        latency_ms = round((time.perf_counter() - started) * 1000)

        row = base._make_row(
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
        rows.append(_rename_and_expand_c23_fields(row))
        _write_rows(rows, output)

    print(f"Saved {len(rows)} rows: {output}")
    print(f"RunID: {run_id}")
    return 0


def _apply_c23(
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
    outcome = PairAwareGroundingValidatorC23().validate(
        pre_validation_response,
        retrieval_results,
    )
    return {
        "result": "passed" if outcome.passed else "rejected",
        "response_role": outcome.response_role,
        "failure_reason": outcome.failure_reason,
        "citations": list(outcome.citations),
        "final_answer": (
            pre_validation_response if outcome.passed else base.C22_REJECTION_RESPONSE
        ),
    }


def _rename_and_expand_c23_fields(row: dict[str, str]) -> dict[str, str]:
    renamed: dict[str, str] = {}
    for key, value in row.items():
        renamed[key.replace("C22", "C23")] = value

    renamed["ResponsesStore"] = "false"

    citations = json.loads(renamed.get("C23CitationTrace") or "[]")
    renamed["C23PrimaryGrounding"] = base._json(
        [item for item in citations if item.get("citation_role") == "primary_grounding"]
    )
    renamed["C23DependentParentCrossReferences"] = base._json(
        [
            item
            for item in citations
            if item.get("citation_role")
            in {"dependent_parent_cross_reference", "dependent_cross_reference"}
        ]
    )
    renamed["C23NegativeOrUnavailableReferences"] = base._json(
        [
            item
            for item in citations
            if item.get("citation_role") == "negative_or_unavailable_reference"
        ]
    )
    return renamed


def _write_rows(rows: list[dict[str, str]], output: Path) -> None:
    import csv

    output.parent.mkdir(parents=True, exist_ok=True)
    fields = tuple(rows[0].keys())
    temporary = output.with_suffix(output.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
    temporary.replace(output)


if __name__ == "__main__":
    raise SystemExit(main())

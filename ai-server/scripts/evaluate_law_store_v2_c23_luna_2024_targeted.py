from __future__ import annotations

import argparse
import csv
import json
import sys
import time
import uuid
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo


AI_SERVER_ROOT = Path(__file__).resolve().parents[1]
PROJECT_ROOT = AI_SERVER_ROOT.parent
if str(AI_SERVER_ROOT) not in sys.path:
    sys.path.insert(0, str(AI_SERVER_ROOT))

from app.evaluation.canonical_law_catalog import CanonicalLawCatalog
from app.evaluation.law_store_v2_2024_targeted_scope import (
    TARGET_QUESTION_IDS,
    classify_target_scopes,
)
from app.evaluation.production_agent_passthrough import (
    LoadedQuestion,
    build_user_message,
    load_reviewed_exam_csv,
)
from app.evaluation.production_answer_parser import parse_final_answer
from app.evaluation.user_generalization_regression import CORPUS_VERSION
from scripts import evaluate_law_store_v2_c22_luna_targeted as base
from scripts.evaluate_law_store_v2_c23_luna_user20 import (
    _StoreFalseOpenAIClient,
    _apply_c23,
    _rename_and_expand_c23_fields,
)


AGENT_MODEL = "gpt-5.6-luna"
VECTOR_STORE_ID = "vs_6aa764aaf2008191af233d99e6fd6cd2"
EVALUATION_MODE = "production_agent_law_store_v2_c23_luna_2024_targeted"
SUBJECT = "공인중개사법령 및 중개실무"
DEFAULT_CATALOG = Path(
    r"C:\ajb\2025_exam\law_rag_vector_store_builds\20260914T030618795400Z"
) / "new_store_files.json"
DEFAULT_OUTPUT = (
    PROJECT_ROOT
    / "docs/evaluation/production_agent_law_store_v2_c23_luna_2024_targeted_8.csv"
)


@dataclass(frozen=True)
class RuntimeQuestion:
    question_id: int
    group: str
    question: str


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run the frozen 2024 eight-question Luna A+B+C1+C2.3 targeted regression."
    )
    parser.add_argument("--input-csv", type=Path, required=True)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--catalog-json", type=Path, default=DEFAULT_CATALOG)
    parser.add_argument("--model", default=AGENT_MODEL)
    parser.add_argument("--vector-store-id", default=VECTOR_STORE_ID)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    input_path = args.input_csv.resolve()
    output = args.output.resolve()
    if not input_path.is_file() or input_path == output or output.exists():
        print("ERROR: input must exist and output must be a new, distinct file", file=sys.stderr)
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
    selected = select_target_questions(load_reviewed_exam_csv(input_path))
    scope_by_id = {
        item.question_id: item for item in classify_target_scopes(catalog)
    }

    from app.config import get_openai_api_key

    api_key = get_openai_api_key()
    if not api_key:
        print("ERROR: OPENAI_API_KEY is required", file=sys.stderr)
        return 2

    base.AGENT_MODEL = AGENT_MODEL
    base.VECTOR_STORE_ID = VECTOR_STORE_ID
    base.EVALUATION_MODE = EVALUATION_MODE
    base._apply_c22 = _apply_c23

    run_id = f"law-v2-c23-luna-2024-targeted-{uuid.uuid4().hex[:12]}"
    evaluated_at = datetime.now(ZoneInfo("Asia/Seoul")).isoformat(timespec="seconds")
    git_commit = base._git_commit()
    unscored_rows: list[dict[str, str]] = []

    # Official answers and v2 scope are deliberately not consulted in this loop.
    for index, item in enumerate(selected, start=1):
        assert item.question is not None
        user_message = build_user_message(item.question)
        runtime_question = RuntimeQuestion(
            question_id=item.question.question_no,
            group="2024 targeted regression",
            question=user_message,
        )
        print(
            f"Evaluating {index}/{len(selected)} exactly once: question {runtime_question.question_id}",
            flush=True,
        )
        runtime = base._build_runtime(
            api_key=api_key,
            vector_store_id=args.vector_store_id,
            model=args.model,
            catalog=catalog,
            question_text=user_message,
        )
        runtime["provider"]._client = _StoreFalseOpenAIClient(runtime["provider"]._client)
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
                message=user_message,
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

        row = base._make_row(
            run_id=run_id,
            evaluated_at=evaluated_at,
            git_commit=git_commit,
            question=runtime_question,
            runtime=runtime,
            production_response=production_response,
            actions=actions,
            error=error,
            latency_ms=round((time.perf_counter() - started) * 1000),
            top_level_generate_count=top_level_generate_count,
        )
        unscored_rows.append(_rename_and_expand_c23_fields(row))

    # Scoring data is joined only after every top-level Agent call has completed.
    final_rows = finalize_rows(unscored_rows, selected, scope_by_id)
    write_rows(final_rows, output)
    print(f"Saved {len(final_rows)} rows: {output}")
    print(f"RunID: {run_id}")
    return 0


def select_target_questions(rows: list[LoadedQuestion]) -> tuple[LoadedQuestion, ...]:
    selected = [
        item
        for item in rows
        if item.question is not None
        and item.question.year == 2024
        and item.question.subject == SUBJECT
        and item.question.question_no in TARGET_QUESTION_IDS
    ]
    selected.sort(key=lambda item: TARGET_QUESTION_IDS.index(item.question.question_no))
    numbers = tuple(item.question.question_no for item in selected if item.question)
    if numbers != TARGET_QUESTION_IDS:
        raise ValueError("target questions are missing, duplicated, invalid, or out of order")
    return tuple(selected)


def finalize_rows(
    rows: list[dict[str, str]],
    selected: tuple[LoadedQuestion, ...],
    scope_by_id: dict[int, Any],
) -> list[dict[str, str]]:
    answer_by_id = {
        item.question.question_no: item.question.accepted_answers or [item.question.correct_answer]
        for item in selected
        if item.question is not None
    }
    source_by_id = {
        item.question.question_no: item.question for item in selected if item.question is not None
    }
    output: list[dict[str, str]] = []
    for row in rows:
        question_id = int(row["QuestionID"])
        question = source_by_id[question_id]
        accepted = answer_by_id[question_id]
        parsed = parse_final_answer(row["FinalAnswer"]) if not row["ExecutionError"] else None
        prediction = parsed.answer if parsed else None
        correctness = (
            "error" if row["ExecutionError"] else
            "unjudgeable" if prediction is None else
            "correct" if prediction in accepted else "wrong"
        )
        scope = scope_by_id[question_id]
        enriched = dict(row)
        enriched.update(
            {
                "ResponsesStore": "false",
                "ExamQuestion": question.question,
                **{f"Choice{index}": value for index, value in enumerate(question.choices, 1)},
                "V2Scope": scope.label.value,
                "V2ScopeRequiredPairs": _json_pairs(scope.required_pairs),
                "V2ScopeMissingPairs": _json_pairs(scope.missing_pairs),
                "V2ScopeRequiredNonArticleSources": json.dumps(
                    scope.required_non_article_sources, ensure_ascii=False
                ),
                "ParsedAnswer": str(prediction or ""),
                "OfficialAnswer": ",".join(str(value) for value in accepted),
                "Correctness": correctness,
                "FailureClassification": _initial_failure(row, correctness),
                "SourceTypeGap": "needs_manual_review",
                "UnsupportedSynthesis": "needs_manual_review",
            }
        )
        output.append(enriched)
    return output


def _initial_failure(row: dict[str, str], correctness: str) -> str:
    if row["FailureCategory"]:
        return row["FailureCategory"]
    if row["C23ValidationResult"] == "rejected":
        return "validator_rejection_needs_review"
    return correctness


def _json_pairs(pairs: tuple[tuple[str, str], ...]) -> str:
    return json.dumps(
        [{"law_name": law, "article_number": article} for law, article in pairs],
        ensure_ascii=False,
        separators=(",", ":"),
    )


def write_rows(rows: list[dict[str, str]], output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_suffix(output.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=tuple(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)
    temporary.replace(output)


if __name__ == "__main__":
    raise SystemExit(main())

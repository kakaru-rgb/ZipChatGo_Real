from __future__ import annotations

import argparse
import csv
import sys
import uuid
from pathlib import Path


AI_SERVER_ROOT = Path(__file__).resolve().parents[1]
if str(AI_SERVER_ROOT) not in sys.path:
    sys.path.insert(0, str(AI_SERVER_ROOT))

from app.config import get_law_vector_store_id, get_openai_api_key
from app.evaluation.law_name_filter_experiment import analyze_validation
from app.evaluation.production_agent_passthrough import (
    RESULT_FIELDS,
    evaluate_question,
    evaluation_timestamp,
    load_reviewed_exam_csv,
)
from scripts.evaluate_exact_law_article_experiment import (
    EXPERIMENT_FIELDS as AB_EXPERIMENT_FIELDS,
    _experiment_fields,
    _git_commit,
)
from scripts.evaluate_semantic_query_isolation_experiment import (
    C1_FIELDS,
    _build_runtime,
    _isolation_fields,
)


EVALUATION_MODE = (
    "production_agent_passthrough_law_name_filter_exact_lookup_"
    "semantic_query_isolation_targeted_regression"
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run the frozen C1 path against targeted regression questions."
    )
    parser.add_argument("--input-csv", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--question-nos", default="6,21,27,37")
    parser.add_argument("--subject", default="공인중개사법령 및 중개실무")
    parser.add_argument("--model", default="gpt-5.6-sol")
    args = parser.parse_args()

    input_path = args.input_csv.resolve()
    output_path = args.output.resolve()
    if input_path == output_path or not input_path.is_file() or output_path.exists():
        print("ERROR: input must exist and output must be a new, distinct file", file=sys.stderr)
        return 2

    question_numbers = [int(value.strip()) for value in args.question_nos.split(",")]
    loaded = load_reviewed_exam_csv(input_path)
    selected = [
        item
        for item in loaded
        if item.question is not None
        and item.question.subject == args.subject
        and item.question.question_no in question_numbers
    ]
    selected.sort(key=lambda item: question_numbers.index(item.question.question_no))
    if [item.question.question_no for item in selected] != question_numbers:
        print("ERROR: requested questions are missing, duplicated, or invalid", file=sys.stderr)
        return 2

    api_key = get_openai_api_key()
    vector_store_id = get_law_vector_store_id()
    if not api_key or not vector_store_id:
        print("ERROR: OPENAI_API_KEY and LAW_VECTOR_STORE_ID are required", file=sys.stderr)
        return 2

    evaluated_at = evaluation_timestamp()
    run_id = (
        "law-semantic-isolation-regression-"
        f"{evaluated_at.replace(':', '').replace('+', '_')}-{uuid.uuid4().hex[:8]}"
    )
    git_commit = _git_commit()
    rows: list[dict[str, str]] = []
    for index, item in enumerate(selected, start=1):
        question = item.question
        print(f"Evaluating {index}/{len(selected)}: question {question.question_no}")
        runtime, exact_experiment, isolation, capture = _build_runtime(
            api_key,
            vector_store_id,
            args.model,
            question.question,
        )
        row = evaluate_question(
            question,
            runtime,
            run_id=run_id,
            evaluated_at=evaluated_at,
            git_commit=git_commit,
        )
        row["EvaluationMode"] = EVALUATION_MODE
        row.update(_experiment_fields(exact_experiment))
        validation_result, validation_reason = analyze_validation(
            capture.raw_response,
            row["AgentRawResponse"],
            runtime.observer.law_traces(),
            row["오류"],
        )
        row.update(
            {
                "PreValidationRawResponse": capture.raw_response,
                "ValidationResult": validation_result,
                "ValidationFailureReason": validation_reason,
                "ResponseRound수": str(capture.response_rounds),
                **_isolation_fields(isolation),
            }
        )
        rows.append(row)
        _write_results(rows, output_path)

    print(f"Saved {len(rows)} C1 targeted regression rows: {output_path}")
    return 0


def _write_results(rows: list[dict[str, str]], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    temporary = output_path.with_suffix(output_path.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(
            stream,
            fieldnames=RESULT_FIELDS + AB_EXPERIMENT_FIELDS + C1_FIELDS,
        )
        writer.writeheader()
        writer.writerows(rows)
    temporary.replace(output_path)


if __name__ == "__main__":
    raise SystemExit(main())

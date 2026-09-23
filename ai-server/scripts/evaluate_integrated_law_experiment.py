from __future__ import annotations

import argparse
import csv
import json
import sys
import uuid
from pathlib import Path


AI_SERVER_ROOT = Path(__file__).resolve().parents[1]
if str(AI_SERVER_ROOT) not in sys.path:
    sys.path.insert(0, str(AI_SERVER_ROOT))

from app.config import get_law_vector_store_id, get_openai_api_key
from app.evaluation.integrated_law_experiment import (
    apply_integrated_c2_validation,
    correctness,
    is_infrastructure_failure,
    safety_assessment,
    semantic_top_k,
)
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


EVALUATION_MODE = "production_agent_passthrough_integrated_a_b_c1_c2_targeted"
DEFAULT_QUESTION_NOS = "6,9,21,27,37,30,35,36,39,40"
SUPPORTED_TARGETS = {6, 9, 21, 27, 37}
INTEGRATED_FIELDS = (
    "TargetGroup",
    "ProductionValidatorRawResponse",
    "ProductionValidationResult",
    "ProductionValidationFailureReason",
    "C2CitationTrace",
    "C2IntegratedRawResponse",
    "C2AgentFinalAnswer",
    "C2AnswerParseStatus",
    "C2Correctness",
    "SemanticTopK",
    "FailureCategory",
    "SafetyAssessment",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run integrated evaluation-only A+B+C1+C2 targeted experiment")
    parser.add_argument("--input-csv", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--question-nos", default=DEFAULT_QUESTION_NOS)
    parser.add_argument("--subject", default="공인중개사법령 및 중개실무")
    parser.add_argument("--model", default="gpt-5.6-sol")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    input_path = args.input_csv.resolve()
    output_path = args.output.resolve()
    if input_path == output_path or not input_path.is_file() or output_path.exists():
        print("ERROR: input must exist and output must be a new, distinct file", file=sys.stderr)
        return 2
    if args.model != "gpt-5.6-sol":
        print("ERROR: this frozen targeted experiment requires --model gpt-5.6-sol", file=sys.stderr)
        return 2

    question_numbers = [int(value.strip()) for value in args.question_nos.split(",")]
    if question_numbers != [6, 9, 21, 27, 37, 30, 35, 36, 39, 40]:
        print("ERROR: question order and membership are frozen for this experiment", file=sys.stderr)
        return 2

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
        "law-integrated-a-b-c1-c2-"
        f"{evaluated_at.replace(':', '').replace('+', '_')}-{uuid.uuid4().hex[:8]}"
    )
    git_commit = _git_commit()
    rows: list[dict[str, str]] = []

    for index, item in enumerate(selected, start=1):
        question = item.question
        print(f"Evaluating {index}/{len(selected)} exactly once: question {question.question_no}", flush=True)
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
        production_response = row["AgentRawResponse"]
        error = row["오류"]
        law_traces = runtime.observer.law_traces()
        production_validation, production_reason = analyze_validation(
            capture.raw_response,
            production_response,
            law_traces,
            error,
        )
        c2 = apply_integrated_c2_validation(
            pre_validation_response=capture.raw_response,
            production_response=production_response,
            law_tool_trace=law_traces,
            error=error,
        )
        accepted = question.accepted_answers or [question.correct_answer]
        group = (
            "supported-target regression"
            if question.question_no in SUPPORTED_TARGETS
            else "safety/out-of-scope control"
        )

        row["EvaluationMode"] = EVALUATION_MODE
        row.update(_experiment_fields(exact_experiment))
        row.update(_isolation_fields(isolation))
        row.update(
            {
                "PreValidationRawResponse": capture.raw_response,
                "ValidationResult": c2.validation_result,
                "ValidationFailureReason": c2.validation_failure_reason,
                "ResponseRound수": str(capture.response_rounds),
                "TargetGroup": group,
                "ProductionValidatorRawResponse": production_response,
                "ProductionValidationResult": production_validation,
                "ProductionValidationFailureReason": production_reason,
                "C2CitationTrace": json.dumps(
                    c2.citation_trace,
                    ensure_ascii=False,
                    separators=(",", ":"),
                ),
                "C2IntegratedRawResponse": c2.integrated_response,
                "C2AgentFinalAnswer": str(c2.final_answer or ""),
                "C2AnswerParseStatus": c2.answer_parse_status,
                "C2Correctness": correctness(c2.final_answer, accepted, error),
                "SemanticTopK": json.dumps(
                    semantic_top_k(law_traces, exact_experiment.traces, isolation.isolation_traces),
                    ensure_ascii=False,
                    separators=(",", ":"),
                ),
                "FailureCategory": (
                    "infrastructure_failure"
                    if is_infrastructure_failure(error)
                    else "execution_failure"
                    if error
                    else ""
                ),
                "SafetyAssessment": safety_assessment(
                    target_group=group,
                    corpus_scope=row["CorpusScope"],
                    validation_result=c2.validation_result,
                    final_answer=c2.final_answer,
                    pre_validation_response=capture.raw_response,
                    law_tool_called=bool(law_traces),
                    error=error,
                ),
            }
        )
        rows.append(row)
        write_results(rows, output_path)

    print(f"Saved {len(rows)} integrated targeted rows: {output_path}")
    return 0


def write_results(rows: list[dict[str, str]], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    temporary = output_path.with_suffix(output_path.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(
            stream,
            fieldnames=RESULT_FIELDS + AB_EXPERIMENT_FIELDS + C1_FIELDS + INTEGRATED_FIELDS,
        )
        writer.writeheader()
        writer.writerows(rows)
    temporary.replace(output_path)


if __name__ == "__main__":
    raise SystemExit(main())

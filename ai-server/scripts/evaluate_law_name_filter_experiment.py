from __future__ import annotations

import argparse
import csv
import subprocess
import sys
import uuid
from pathlib import Path


AI_SERVER_ROOT = Path(__file__).resolve().parents[1]
if str(AI_SERVER_ROOT) not in sys.path:
    sys.path.insert(0, str(AI_SERVER_ROOT))

from app.config import (
    get_law_vector_store_id,
    get_openai_api_key,
    get_spring_server_base_url,
)
from app.evaluation.law_name_filter_experiment import (
    LawNameFilterExperimentHandler,
    PreValidationCapture,
    analyze_validation,
    observe_experimental_provider,
    trace_summary,
)
from app.evaluation.production_agent_observer import ProductionAgentObserver
from app.evaluation.production_agent_passthrough import (
    RESULT_FIELDS,
    PassthroughRuntime,
    evaluate_question,
    evaluation_timestamp,
    load_reviewed_exam_csv,
)
from app.prompts import REAL_ESTATE_AGENT_INSTRUCTIONS
from app.providers.openai_provider import OpenAIProvider
from app.retrievers.openai_vector_store_law_retriever import OpenAIVectorStoreLawRetriever
from app.tools.legal_dong_adjacency import LegalDongAdjacencyTool
from app.tools.property_search import PropertySearchTool
from app.tools.real_estate_law import RealEstateLawSearchTool
from app.tools.transit_station import TransitStationTool


EVALUATION_MODE = "production_agent_passthrough_law_name_filter_experiment"
EXPERIMENT_FIELDS = (
    "적용된LawNames",
    "FilteredSearch여부",
    "Fallback여부",
    "LawNameFilterTrace",
    "PreValidationRawResponse",
    "ValidationResult",
    "ValidationFailureReason",
    "ResponseRound수",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the evaluation-only law-name filter experiment.")
    parser.add_argument("--input-csv", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--question-nos", default="9,21,27,37")
    parser.add_argument("--subject", default="공인중개사법령 및 중개실무")
    parser.add_argument("--model", default="gpt-5.6-sol")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    input_path = args.input_csv.resolve()
    output_path = args.output.resolve()
    if input_path == output_path or not input_path.is_file():
        print("ERROR: valid, distinct --input-csv and --output paths are required", file=sys.stderr)
        return 2
    question_numbers = _parse_question_numbers(args.question_nos)
    selected = [
        item
        for item in load_reviewed_exam_csv(input_path)
        if (
            item.question is not None
            and item.question.subject == args.subject
            and item.question.question_no in question_numbers
        )
    ]
    selected.sort(key=lambda item: question_numbers.index(item.question.question_no))
    if [item.question.question_no for item in selected] != question_numbers:
        print("ERROR: one or more requested question numbers are missing or invalid", file=sys.stderr)
        return 2

    api_key = get_openai_api_key()
    vector_store_id = get_law_vector_store_id()
    if not api_key or not vector_store_id:
        print("ERROR: OPENAI_API_KEY and LAW_VECTOR_STORE_ID are required", file=sys.stderr)
        return 2

    run_id = f"law-filter-{evaluation_timestamp().replace(':', '').replace('+', '_')}-{uuid.uuid4().hex[:8]}"
    evaluated_at = evaluation_timestamp()
    git_commit = _git_commit()
    rows: list[dict[str, str]] = []
    for index, item in enumerate(selected, start=1):
        question = item.question
        print(f"Evaluating {index}/{len(selected)}: question {question.question_no}")
        runtime, filter_handler, capture = _build_runtime(
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
        row.update(trace_summary(filter_handler.traces))
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
            }
        )
        rows.append(row)
        _write_results(rows, output_path)
    print(f"Saved {len(rows)} experimental rows: {output_path}")
    return 0


def _build_runtime(
    api_key: str,
    vector_store_id: str,
    model: str,
    question_text: str,
) -> tuple[PassthroughRuntime, LawNameFilterExperimentHandler, PreValidationCapture]:
    observer = ProductionAgentObserver()
    capture = PreValidationCapture()
    provider = OpenAIProvider(api_key, model, REAL_ESTATE_AGENT_INSTRUCTIONS)
    observe_experimental_provider(provider, observer, capture)
    retriever = OpenAIVectorStoreLawRetriever(api_key, vector_store_id)
    law_filter_handler = LawNameFilterExperimentHandler(
        RealEstateLawSearchTool(retriever).search,
        question_text,
    )
    spring_url = get_spring_server_base_url()
    runtime = PassthroughRuntime(
        provider=provider,
        model=model,
        observer=observer,
        handlers={
            "search_properties": PropertySearchTool(spring_url).search,
            "find_transit_station": TransitStationTool(spring_url).search,
            "get_adjacent_legal_dongs": LegalDongAdjacencyTool().lookup,
            "search_real_estate_law": law_filter_handler,
        },
    )
    return runtime, law_filter_handler, capture


def _parse_question_numbers(value: str) -> list[int]:
    numbers = [int(item.strip()) for item in value.split(",") if item.strip()]
    if not numbers or len(numbers) != len(set(numbers)):
        raise ValueError("--question-nos must contain unique integers")
    return numbers


def _write_results(rows: list[dict[str, str]], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    temporary = output_path.with_suffix(output_path.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=RESULT_FIELDS + EXPERIMENT_FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    temporary.replace(output_path)


def _git_commit() -> str:
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=AI_SERVER_ROOT.parent,
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


if __name__ == "__main__":
    raise SystemExit(main())

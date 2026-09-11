from __future__ import annotations

import argparse
import csv
import json
import sys
import uuid
from pathlib import Path

from openai import OpenAI


AI_SERVER_ROOT = Path(__file__).resolve().parents[1]
if str(AI_SERVER_ROOT) not in sys.path:
    sys.path.insert(0, str(AI_SERVER_ROOT))

from app.config import get_law_vector_store_id, get_openai_api_key, get_spring_server_base_url
from app.evaluation.exact_law_article_experiment import (
    ExactLawArticleExperimentHandler,
    OpenAIVectorStoreExactLawArticleLookup,
)
from app.evaluation.law_name_filter_experiment import (
    LawNameFilterExperimentHandler,
    PreValidationCapture,
    analyze_validation,
    observe_experimental_provider,
)
from app.evaluation.production_agent_observer import ProductionAgentObserver
from app.evaluation.production_agent_passthrough import (
    RESULT_FIELDS,
    PassthroughRuntime,
    evaluate_question,
    evaluation_timestamp,
    load_reviewed_exam_csv,
)
from app.evaluation.semantic_query_isolation_experiment import (
    SemanticQueryIsolationHandler,
)
from app.prompts import REAL_ESTATE_AGENT_INSTRUCTIONS
from app.providers.openai_provider import OpenAIProvider
from app.retrievers.openai_vector_store_law_retriever import OpenAIVectorStoreLawRetriever
from app.tools.legal_dong_adjacency import LegalDongAdjacencyTool
from app.tools.property_search import PropertySearchTool
from app.tools.real_estate_law import RealEstateLawSearchTool
from app.tools.transit_station import TransitStationTool
from scripts.evaluate_exact_law_article_experiment import (
    EXPERIMENT_FIELDS as AB_EXPERIMENT_FIELDS,
    _experiment_fields,
    _git_commit,
    _latest_model_law_query,
)


EVALUATION_MODE = "production_agent_passthrough_law_name_filter_exact_lookup_semantic_query_isolation_experiment"
C1_FIELDS = (
    "SemanticQueryIsolationApplied",
    "C1SemanticQueries",
    "SemanticQueryIsolationTrace",
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Run evaluation-only C1 semantic query isolation experiment.")
    parser.add_argument("--input-csv", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--question-no", type=int, default=9)
    parser.add_argument("--subject", default="공인중개사법령 및 중개실무")
    parser.add_argument("--model", default="gpt-5.6-sol")
    args = parser.parse_args()

    input_path = args.input_csv.resolve()
    output_path = args.output.resolve()
    if input_path == output_path or not input_path.is_file() or output_path.exists():
        print("ERROR: input must exist and output must be a new, distinct file", file=sys.stderr)
        return 2

    selected = [
        item
        for item in load_reviewed_exam_csv(input_path)
        if item.question is not None
        and item.question.subject == args.subject
        and item.question.question_no == args.question_no
    ]
    if len(selected) != 1:
        print("ERROR: requested question is missing, duplicated, or invalid", file=sys.stderr)
        return 2

    api_key = get_openai_api_key()
    vector_store_id = get_law_vector_store_id()
    if not api_key or not vector_store_id:
        print("ERROR: OPENAI_API_KEY and LAW_VECTOR_STORE_ID are required", file=sys.stderr)
        return 2

    run_id = f"law-semantic-isolation-{evaluation_timestamp().replace(':', '').replace('+', '_')}-{uuid.uuid4().hex[:8]}"
    question = selected[0].question
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
        evaluated_at=evaluation_timestamp(),
        git_commit=_git_commit(),
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
    _write_result(row, output_path)
    print(f"Saved C1 question {question.question_no}: {output_path}")
    return 0


def _build_runtime(
    api_key: str,
    vector_store_id: str,
    model: str,
    question_text: str,
) -> tuple[
    PassthroughRuntime,
    ExactLawArticleExperimentHandler,
    SemanticQueryIsolationHandler,
    PreValidationCapture,
]:
    observer = ProductionAgentObserver()
    capture = PreValidationCapture()
    provider = OpenAIProvider(api_key, model, REAL_ESTATE_AGENT_INSTRUCTIONS)
    observe_experimental_provider(provider, observer, capture)
    vector_client = OpenAI(api_key=api_key)
    retriever = OpenAIVectorStoreLawRetriever(api_key, vector_store_id, client=vector_client)
    law_filter_handler = LawNameFilterExperimentHandler(
        RealEstateLawSearchTool(retriever).search,
        question_text,
    )
    isolation = SemanticQueryIsolationHandler(
        law_filter_handler,
        lambda: _latest_model_law_query(observer),
    )
    exact_experiment = ExactLawArticleExperimentHandler(
        OpenAIVectorStoreExactLawArticleLookup(vector_client, vector_store_id),
        isolation,
        model_query_supplier=lambda: _latest_model_law_query(observer),
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
            "search_real_estate_law": exact_experiment,
        },
    )
    return runtime, exact_experiment, isolation, capture


def _isolation_fields(experiment: SemanticQueryIsolationHandler) -> dict[str, str]:
    traces = experiment.isolation_traces
    return {
        "SemanticQueryIsolationApplied": "Y" if any(trace.isolation_applied for trace in traces) else "N",
        "C1SemanticQueries": " | ".join(trace.semantic_query for trace in traces),
        "SemanticQueryIsolationTrace": json.dumps(
            [trace.as_dict() for trace in traces],
            ensure_ascii=False,
            separators=(",", ":"),
        ),
    }


def _write_result(row: dict[str, str], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    temporary = output_path.with_suffix(output_path.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(
            stream,
            fieldnames=RESULT_FIELDS + AB_EXPERIMENT_FIELDS + C1_FIELDS,
        )
        writer.writeheader()
        writer.writerow(row)
    temporary.replace(output_path)


if __name__ == "__main__":
    raise SystemExit(main())

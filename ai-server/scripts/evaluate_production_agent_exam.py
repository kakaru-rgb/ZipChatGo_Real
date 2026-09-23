from __future__ import annotations

import argparse
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
    get_openai_model,
    get_spring_server_base_url,
)
from app.evaluation.production_agent_observer import (
    ProductionAgentObserver,
    observe_provider_client,
)
from app.evaluation.production_agent_passthrough import (
    LoadedQuestion,
    PassthroughRuntime,
    evaluate_question,
    evaluation_timestamp,
    load_reviewed_exam_csv,
    make_input_error_row,
    write_results,
)
from app.prompts import REAL_ESTATE_AGENT_INSTRUCTIONS
from app.providers.openai_provider import OpenAIProvider
from app.retrievers.openai_vector_store_law_retriever import (
    OpenAIVectorStoreLawRetriever,
)
from app.tools.legal_dong_adjacency import LegalDongAdjacencyTool
from app.tools.property_search import PropertySearchTool
from app.tools.real_estate_law import RealEstateLawSearchTool
from app.tools.transit_station import TransitStationTool


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Evaluate the unchanged production Agent with a reviewed exam CSV."
    )
    parser.add_argument("--input-csv", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--subject")
    parser.add_argument("--limit", type=int, default=5)
    parser.add_argument(
        "--model",
        help=(
            "Evaluation-only model override. The production OPENAI_MODEL setting "
            "is used when omitted."
        ),
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    input_path = args.input_csv.resolve()
    output_path = args.output.resolve()
    if input_path == output_path:
        print("ERROR: --output must differ from --input-csv", file=sys.stderr)
        return 2
    if not input_path.is_file():
        print(f"ERROR: Input CSV not found: {input_path}", file=sys.stderr)
        return 2
    if args.limit is not None and args.limit < 1:
        print("ERROR: --limit must be at least 1", file=sys.stderr)
        return 2

    model = args.model.strip() if args.model and args.model.strip() else get_openai_model()
    run_id = f"passthrough-{evaluation_timestamp().replace(':', '').replace('+', '_')}-{uuid.uuid4().hex[:8]}"
    evaluated_at = evaluation_timestamp()
    git_commit = _git_commit()
    loaded = load_reviewed_exam_csv(input_path)
    selected = _select_rows(loaded, args.subject, args.limit)

    api_key = get_openai_api_key()
    vector_store_id = get_law_vector_store_id()
    if not api_key or not vector_store_id:
        missing = "OPENAI_API_KEY" if not api_key else "LAW_VECTOR_STORE_ID"
        print(f"ERROR: {missing} is not configured", file=sys.stderr)
        return 2

    rows: list[dict[str, str]] = []
    for index, item in enumerate(selected, start=1):
        print(f"Evaluating {index}/{len(selected)}: CSV row {item.row_number}")
        if item.question is None:
            row = make_input_error_row(
                item,
                run_id=run_id,
                evaluated_at=evaluated_at,
                git_commit=git_commit,
                model=model,
            )
        else:
            runtime = _build_runtime(api_key, vector_store_id, model)
            row = evaluate_question(
                item.question,
                runtime,
                run_id=run_id,
                evaluated_at=evaluated_at,
                git_commit=git_commit,
            )
        rows.append(row)
        write_results(rows, output_path)
    print(f"Saved {len(rows)} passthrough rows: {output_path}")
    return 0


def _build_runtime(api_key: str, vector_store_id: str, model: str) -> PassthroughRuntime:
    observer = ProductionAgentObserver()
    provider = OpenAIProvider(api_key, model, REAL_ESTATE_AGENT_INSTRUCTIONS)
    observe_provider_client(provider, observer)
    spring_url = get_spring_server_base_url()
    retriever = OpenAIVectorStoreLawRetriever(api_key, vector_store_id)
    return PassthroughRuntime(
        provider=provider,
        model=model,
        observer=observer,
        handlers={
            "search_properties": PropertySearchTool(spring_url).search,
            "find_transit_station": TransitStationTool(spring_url).search,
            "get_adjacent_legal_dongs": LegalDongAdjacencyTool().lookup,
            "search_real_estate_law": RealEstateLawSearchTool(retriever).search,
        },
    )


def _select_rows(
    rows: list[LoadedQuestion],
    subject: str | None,
    limit: int | None,
) -> list[LoadedQuestion]:
    selected = [
        item
        for item in rows
        if (
            subject is None
            or not item.raw
            or item.raw.get("과목", "") == subject
        )
    ]
    return selected[:limit] if limit is not None else selected


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

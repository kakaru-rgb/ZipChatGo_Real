from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path


AI_SERVER_ROOT = Path(__file__).resolve().parents[1]
PROJECT_ROOT = AI_SERVER_ROOT.parent
if str(AI_SERVER_ROOT) not in sys.path:
    sys.path.insert(0, str(AI_SERVER_ROOT))

from app.evaluation.pair_aware_grounding_validator_c21 import (
    collect_retrieval_results,
)
from app.evaluation.pair_aware_grounding_validator_c23 import (
    PairAwareGroundingValidatorC23,
)


SOURCE_RUN_ID = "law-v2-c22-luna-targeted-0844010e23cd"
DEFAULT_INPUT = (
    PROJECT_ROOT
    / "docs/evaluation/production_agent_law_store_v2_c22_luna_live_integrated_targeted.csv"
)
DEFAULT_OUTPUT = (
    PROJECT_ROOT
    / "docs/evaluation/production_agent_law_store_v2_c23_parent_crossref_offline_replay.json"
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Offline C2.3 replay for frozen Luna question 3")
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    if args.output.exists():
        print(f"ERROR: output already exists: {args.output}", file=sys.stderr)
        return 2

    with args.input.open(encoding="utf-8-sig", newline="") as stream:
        rows = list(csv.DictReader(stream))
    matches = [
        row
        for row in rows
        if row["RunID"] == SOURCE_RUN_ID and row["QuestionID"] == "3"
    ]
    if len(matches) != 1:
        print(f"ERROR: expected one frozen question 3 row, got {len(matches)}", file=sys.stderr)
        return 2

    row = matches[0]
    law_tool_trace = json.loads(row["ToolCalls"] or "[]")
    retrieval_results = collect_retrieval_results(law_tool_trace)
    outcome = PairAwareGroundingValidatorC23().validate(
        row["PreValidationRawResponse"],
        retrieval_results,
    )
    payload = {
        "source_run_id": SOURCE_RUN_ID,
        "question_id": 3,
        "api_calls": 0,
        "vector_store_api_calls": 0,
        "agent_reruns": 0,
        "c22_result": row["C22ValidationResult"],
        "c22_failure_reason": row["C22ValidationFailureReason"],
        "c23_result": "passed" if outcome.passed else "rejected",
        "c23_response_role": outcome.response_role,
        "c23_failure_reason": outcome.failure_reason,
        "c23_citation_trace": list(outcome.citations),
    }

    args.output.parent.mkdir(parents=True, exist_ok=True)
    temporary = args.output.with_suffix(args.output.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    temporary.replace(args.output)
    print(f"Saved offline replay: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

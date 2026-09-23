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
from app.evaluation.pair_aware_grounding_validator_c22 import (
    PairAwareGroundingValidatorC22,
)


SOURCE_RUN_ID = "law-v2-user-regression-baf62a52ffa7"
DEFAULT_INPUT = (
    PROJECT_ROOT
    / "docs/evaluation/production_agent_law_store_v2_generalization_regression_20.csv"
)
DEFAULT_OUTPUT = (
    PROJECT_ROOT
    / "docs/evaluation/production_agent_law_store_v2_c22_full20_offline_replay.csv"
)
FIELDS = (
    "question_id",
    "source_run_id",
    "c21_result",
    "c21_failure_reason",
    "c22_result",
    "c22_response_role",
    "c22_failure_reason",
    "transition",
    "negative_reference_count",
    "c22_citation_trace",
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Replay C2.2 over the frozen full-20 run")
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    if args.output.exists():
        print(f"ERROR: output already exists: {args.output}", file=sys.stderr)
        return 2

    with args.input.open(encoding="utf-8-sig", newline="") as stream:
        source_rows = list(csv.DictReader(stream))
    if len(source_rows) != 20:
        print(f"ERROR: expected 20 source rows, got {len(source_rows)}", file=sys.stderr)
        return 2
    if any(row["RunID"] != SOURCE_RUN_ID for row in source_rows):
        print("ERROR: source RunID does not match the frozen run", file=sys.stderr)
        return 2
    if [int(row["문항ID"]) for row in source_rows] != list(range(1, 21)):
        print("ERROR: source question IDs are not the frozen 1..20 sequence", file=sys.stderr)
        return 2

    validator = PairAwareGroundingValidatorC22()
    replay_rows: list[dict[str, str]] = []
    for row in source_rows:
        c21_result = row["ValidationResult"]
        if c21_result in {"not_reached", "not_applied"}:
            replay_rows.append(
                {
                    "question_id": row["문항ID"],
                    "source_run_id": row["RunID"],
                    "c21_result": c21_result,
                    "c21_failure_reason": row["ValidationFailureReason"],
                    "c22_result": c21_result,
                    "c22_response_role": c21_result,
                    "c22_failure_reason": row["ValidationFailureReason"],
                    "transition": c21_result,
                    "negative_reference_count": "0",
                    "c22_citation_trace": "[]",
                }
            )
            continue

        tool_trace = json.loads(row["ToolCalls"] or "[]")
        retrieval_results = collect_retrieval_results(tool_trace)
        outcome = validator.validate(row["PreValidationRawResponse"], retrieval_results)
        result_name = "passed" if outcome.passed else "rejected"
        transition = f"{_display(c21_result)} → {_display(result_name)}"
        negative_count = sum(
            citation.get("citation_role") == "negative_or_unavailable_reference"
            for citation in outcome.citations
        )
        replay_rows.append(
            {
                "question_id": row["문항ID"],
                "source_run_id": row["RunID"],
                "c21_result": c21_result,
                "c21_failure_reason": row["ValidationFailureReason"],
                "c22_result": result_name,
                "c22_response_role": outcome.response_role,
                "c22_failure_reason": outcome.failure_reason,
                "transition": transition,
                "negative_reference_count": str(negative_count),
                "c22_citation_trace": json.dumps(
                    outcome.citations,
                    ensure_ascii=False,
                    separators=(",", ":"),
                ),
            }
        )

    args.output.parent.mkdir(parents=True, exist_ok=True)
    temporary = args.output.with_suffix(args.output.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(replay_rows)
    temporary.replace(args.output)
    print(f"Saved {len(replay_rows)} offline replay rows: {args.output}")
    return 0


def _display(value: str) -> str:
    return {"passed": "PASS", "rejected": "REJECT"}.get(value, value)


if __name__ == "__main__":
    raise SystemExit(main())

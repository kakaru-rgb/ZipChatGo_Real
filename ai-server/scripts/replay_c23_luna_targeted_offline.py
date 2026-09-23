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
SOURCE_MODEL = "gpt-5.6-luna"
SOURCE_CORPUS = "law_store_v2"
TARGET_IDS = (1, 3, 6, 14, 15, 18)
DEFAULT_INPUT = (
    PROJECT_ROOT
    / "docs/evaluation/production_agent_law_store_v2_c22_luna_live_integrated_targeted.csv"
)
DEFAULT_OUTPUT = (
    PROJECT_ROOT
    / "docs/evaluation/production_agent_law_store_v2_c23_luna_targeted_offline_replay.csv"
)
FIELDS = (
    "question_id",
    "source_run_id",
    "agent_model",
    "corpus_version",
    "c22_result",
    "c22_response_role",
    "c22_failure_reason",
    "c23_result",
    "c23_response_role",
    "c23_failure_reason",
    "transition",
    "c23_citation_trace",
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Replay C2.3 over the frozen six-question Luna targeted run."
    )
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    if args.output.exists():
        print(f"ERROR: output already exists: {args.output}", file=sys.stderr)
        return 2

    with args.input.open(encoding="utf-8-sig", newline="") as stream:
        source_rows = list(csv.DictReader(stream))
    if tuple(int(row["QuestionID"]) for row in source_rows) != TARGET_IDS:
        print("ERROR: source question sequence is not the frozen target set", file=sys.stderr)
        return 2
    if any(row["RunID"] != SOURCE_RUN_ID for row in source_rows):
        print("ERROR: source RunID mismatch", file=sys.stderr)
        return 2
    if any(row["AgentModel"] != SOURCE_MODEL for row in source_rows):
        print("ERROR: source model mismatch", file=sys.stderr)
        return 2
    if any(row["CorpusVersion"] != SOURCE_CORPUS for row in source_rows):
        print("ERROR: source corpus mismatch", file=sys.stderr)
        return 2

    validator = PairAwareGroundingValidatorC23()
    replay_rows: list[dict[str, str]] = []
    for row in source_rows:
        c22_result = row["C22ValidationResult"]
        c22_role = row["C22ResponseRole"]
        c22_reason = row["C22ValidationFailureReason"]

        if c22_result in {"not_reached", "not_applied"}:
            c23_result = c22_result
            c23_role = c22_role
            c23_reason = c22_reason
            citations: list[dict[str, object]] = []
        else:
            law_tool_trace = json.loads(row["ToolCalls"] or "[]")
            retrieval_results = collect_retrieval_results(law_tool_trace)
            outcome = validator.validate(
                row["PreValidationRawResponse"],
                retrieval_results,
            )
            c23_result = "passed" if outcome.passed else "rejected"
            c23_role = outcome.response_role
            c23_reason = outcome.failure_reason
            citations = list(outcome.citations)

        replay_rows.append(
            {
                "question_id": row["QuestionID"],
                "source_run_id": SOURCE_RUN_ID,
                "agent_model": SOURCE_MODEL,
                "corpus_version": SOURCE_CORPUS,
                "c22_result": c22_result,
                "c22_response_role": c22_role,
                "c22_failure_reason": c22_reason,
                "c23_result": c23_result,
                "c23_response_role": c23_role,
                "c23_failure_reason": c23_reason,
                "transition": f"{_display(c22_result)} → {_display(c23_result)}",
                "c23_citation_trace": json.dumps(
                    citations,
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
    return {
        "passed": "PASS",
        "rejected": "REJECT",
    }.get(value, value)


if __name__ == "__main__":
    raise SystemExit(main())

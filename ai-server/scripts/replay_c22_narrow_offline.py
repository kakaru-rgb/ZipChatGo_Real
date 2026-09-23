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


DEFAULT_INPUT = (
    PROJECT_ROOT
    / "docs/evaluation/production_agent_law_store_v2_generalization_regression_20.csv"
)
DEFAULT_OUTPUT = (
    PROJECT_ROOT
    / "docs/evaluation/production_agent_law_store_v2_c22_narrow_offline_replay.json"
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Offline replay of C2.2 candidate for rows 3 and 18")
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    if args.output.exists():
        print(f"ERROR: output already exists: {args.output}", file=sys.stderr)
        return 2
    with args.input.open(encoding="utf-8-sig", newline="") as stream:
        rows = {row["문항ID"]: row for row in csv.DictReader(stream)}
    if not {"3", "18"}.issubset(rows):
        print("ERROR: frozen rows 3 and 18 are required", file=sys.stderr)
        return 2

    validator = PairAwareGroundingValidatorC22()
    output: list[dict] = []
    for question_id in ("3", "18"):
        row = rows[question_id]
        law_trace = json.loads(row["ToolCalls"] or "[]")
        retrievals = collect_retrieval_results(law_trace)
        result = validator.validate(row["PreValidationRawResponse"], retrievals)
        output.append(
            {
                "question_id": int(question_id),
                "source_run_id": row["RunID"],
                "source_validation_result": row["ValidationResult"],
                "source_validation_failure_reason": row["ValidationFailureReason"],
                "c22": result.as_dict(),
            }
        )

    args.output.parent.mkdir(parents=True, exist_ok=True)
    temporary = args.output.with_suffix(args.output.suffix + ".tmp")
    temporary.write_text(
        json.dumps(output, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    temporary.replace(args.output)
    print(f"Saved offline replay: {args.output}")
    return 0 if all(item["c22"]["passed"] for item in output) else 1


if __name__ == "__main__":
    raise SystemExit(main())

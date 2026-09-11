from __future__ import annotations

import argparse
import csv
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any


AI_SERVER_ROOT = Path(__file__).resolve().parents[1]
PROJECT_ROOT = AI_SERVER_ROOT.parent
if str(AI_SERVER_ROOT) not in sys.path:
    sys.path.insert(0, str(AI_SERVER_ROOT))

from app.evaluation.pair_aware_grounding_validator import (  # noqa: E402
    PairAwareGroundingValidator,
    collect_retrieval_results,
)


DEFAULT_Q9 = PROJECT_ROOT / "docs/evaluation/production_agent_passthrough_law_name_filter_exact_lookup_semantic_query_isolation_2024_q9_gpt-5.6-sol.csv"
DEFAULT_Q27 = PROJECT_ROOT / "docs/evaluation/production_agent_passthrough_law_name_filter_exact_lookup_2024_q6_9_21_27_37_gpt-5.6-sol_valid.csv"
DEFAULT_OUTPUT = PROJECT_ROOT / "docs/evaluation/production_agent_c2_pair_aware_grounding_replay_q9_q27.json"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Offline C2 pair-aware grounding replay")
    parser.add_argument("--q9-csv", type=Path, default=DEFAULT_Q9)
    parser.add_argument("--q27-csv", type=Path, default=DEFAULT_Q27)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    return parser.parse_args()


def load_row(path: Path, question_number: int) -> dict[str, str]:
    with path.open(encoding="utf-8-sig", newline="") as file:
        rows = list(csv.DictReader(file))
    matches = [row for row in rows if row.get("문항번호") == str(question_number)]
    if len(matches) != 1:
        raise ValueError(f"Expected one row for question {question_number}, found {len(matches)}")
    return matches[0]


def replay(path: Path, question_number: int) -> dict[str, Any]:
    row = load_row(path, question_number)
    tool_trace = json.loads(row.get("법률ToolTrace") or "[]")
    retrieval_results = collect_retrieval_results(tool_trace)
    response = row.get("PreValidationRawResponse", "")
    outcome = PairAwareGroundingValidator().validate(response, retrieval_results)
    return {
        "question_number": question_number,
        "source_csv": str(path),
        "source_run_id": row.get("RunID", ""),
        "official_answer": row.get("공식정답", ""),
        "pre_validation_agent_answer": row.get("Agent최종답", ""),
        "original_validation_result": row.get("ValidationResult", ""),
        "original_validation_failure_reason": row.get("ValidationFailureReason", ""),
        "retrieval_result_count": len(retrieval_results),
        "c2_validation": outcome.as_dict(),
    }


def main() -> int:
    args = parse_args()
    if args.output.exists():
        raise FileExistsError(f"Refusing to overwrite frozen/output file: {args.output}")
    payload = {
        "evaluation_mode": "c2_pair_aware_grounding_offline_replay",
        "created_at": datetime.now().astimezone().isoformat(),
        "api_calls": 0,
        "vector_store_api_calls": 0,
        "replays": [replay(args.q9_csv, 9), replay(args.q27_csv, 27)],
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x", encoding="utf-8", newline="\n") as file:
        json.dump(payload, file, ensure_ascii=False, indent=2)
        file.write("\n")
    print(args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


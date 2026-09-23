from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
from collections import Counter
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


DEFAULT_INPUT_DIR = PROJECT_ROOT / "docs/evaluation"
DEFAULT_OUTPUT = (
    PROJECT_ROOT
    / "docs/evaluation/production_agent_c2_pair_aware_grounding_expanded_offline_regression_v2.json"
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Expanded offline replay for the C2 validator")
    parser.add_argument("--input-dir", type=Path, default=DEFAULT_INPUT_DIR)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    return parser.parse_args()


def _normalize_old_result(value: str) -> str | None:
    normalized = value.strip().lower()
    if normalized == "passed":
        return "PASS"
    if normalized == "rejected":
        return "REJECT"
    return None


def _execution_key(row: dict[str, str]) -> str:
    material = "\x1f".join(
        (
            row.get("RunID", ""),
            row.get("문항번호", ""),
            row.get("PreValidationRawResponse", ""),
            row.get("법률ToolTrace", ""),
        )
    )
    return hashlib.sha256(material.encode("utf-8")).hexdigest()


def _not_replayable(
    source: Path,
    row_number: int,
    row: dict[str, str],
    reason: str,
) -> dict[str, Any]:
    return {
        "source_file": source.name,
        "source_row": row_number,
        "run_id": row.get("RunID", ""),
        "question_number": row.get("문항번호", ""),
        "execution_key": _execution_key(row),
        "replayable": False,
        "not_replayable_reason": reason,
        "original_validation": row.get("ValidationResult", ""),
        "c2_validation": "",
        "transition": "not_replayable",
        "citation_trace": [],
    }


def analyze_row(source: Path, row_number: int, row: dict[str, str]) -> dict[str, Any]:
    pre_validation = row.get("PreValidationRawResponse", "").strip()
    if not pre_validation:
        return _not_replayable(source, row_number, row, "missing_pre_validation_raw_response")

    old_result = _normalize_old_result(row.get("ValidationResult", ""))
    if old_result is None:
        return _not_replayable(source, row_number, row, "missing_or_nonterminal_original_validation")

    serialized_trace = row.get("법률ToolTrace", "").strip()
    if not serialized_trace:
        return _not_replayable(source, row_number, row, "missing_law_tool_trace")
    try:
        law_trace = json.loads(serialized_trace)
    except json.JSONDecodeError:
        return _not_replayable(source, row_number, row, "malformed_law_tool_trace")
    if not isinstance(law_trace, list):
        return _not_replayable(source, row_number, row, "law_tool_trace_is_not_a_list")

    retrieval_results = collect_retrieval_results(law_trace)
    usable_results = [
        item
        for item in retrieval_results
        if str(item.get("law_name", "")).strip()
        and str(item.get("article_number", "")).strip()
        and str(item.get("text", "")).strip()
    ]
    if not usable_results:
        return _not_replayable(source, row_number, row, "missing_retrieval_metadata_or_body")

    outcome = PairAwareGroundingValidator().validate(pre_validation, usable_results)
    c2_result = "PASS" if outcome.passed else "REJECT"
    return {
        "source_file": source.name,
        "source_row": row_number,
        "run_id": row.get("RunID", ""),
        "question_number": row.get("문항번호", ""),
        "execution_key": _execution_key(row),
        "replayable": True,
        "not_replayable_reason": "",
        "official_answer": row.get("공식정답", ""),
        "original_validation": old_result,
        "original_validation_failure_reason": row.get("ValidationFailureReason", ""),
        "c2_validation": c2_result,
        "c2_failure_reason": outcome.failure_reason,
        "transition": f"{old_result} → {c2_result}",
        "citation_trace": [citation.as_dict() for citation in outcome.citations],
    }


def _unique_executions(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    unique: dict[str, dict[str, Any]] = {}
    for row in rows:
        key = str(row["execution_key"])
        if key not in unique:
            copied = dict(row)
            copied["also_present_in"] = []
            unique[key] = copied
        else:
            existing = unique[key]
            existing_location = {
                "source_file": existing["source_file"],
                "source_row": existing["source_row"],
            }
            new_location = {
                "source_file": row["source_file"],
                "source_row": row["source_row"],
            }
            if row["replayable"] and not existing["replayable"]:
                copied = dict(row)
                copied["also_present_in"] = [
                    existing_location,
                    *existing.get("also_present_in", []),
                ]
                unique[key] = copied
            else:
                existing["also_present_in"].append(new_location)
    return list(unique.values())


def _counts(rows: list[dict[str, Any]]) -> dict[str, int]:
    counter = Counter(str(row["transition"]) for row in rows)
    return {
        "total": len(rows),
        "replayable": sum(1 for row in rows if row["replayable"]),
        "PASS → PASS": counter["PASS → PASS"],
        "PASS → REJECT": counter["PASS → REJECT"],
        "REJECT → PASS": counter["REJECT → PASS"],
        "REJECT → REJECT": counter["REJECT → REJECT"],
        "not_replayable": counter["not_replayable"],
    }


def main() -> int:
    args = parse_args()
    if args.output.exists():
        raise FileExistsError(f"Refusing to overwrite existing result: {args.output}")

    analyzed: list[dict[str, Any]] = []
    for source in sorted(args.input_dir.glob("*.csv")):
        with source.open(encoding="utf-8-sig", newline="") as file:
            reader = csv.DictReader(file)
            for row_number, row in enumerate(reader, start=2):
                analyzed.append(analyze_row(source, row_number, row))

    unique = _unique_executions(analyzed)
    payload = {
        "evaluation_mode": "c2_pair_aware_grounding_expanded_offline_regression",
        "created_at": datetime.now().astimezone().isoformat(),
        "api_calls": 0,
        "vector_store_api_calls": 0,
        "source_row_counts": _counts(analyzed),
        "unique_execution_counts": _counts(unique),
        "source_rows": analyzed,
        "unique_executions": unique,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x", encoding="utf-8", newline="\n") as file:
        json.dump(payload, file, ensure_ascii=False, indent=2)
        file.write("\n")
    print(args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path


AI_SERVER_ROOT = Path(__file__).resolve().parents[1]
if str(AI_SERVER_ROOT) not in sys.path:
    sys.path.insert(0, str(AI_SERVER_ROOT))

from app.evaluation.law_name_filter_experiment import analyze_validation


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Recompute validation trace fields without calling OpenAI."
    )
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    input_path = args.input.resolve()
    output_path = args.output.resolve()
    if input_path == output_path or not input_path.is_file():
        print("ERROR: valid, distinct --input and --output paths are required", file=sys.stderr)
        return 2

    with input_path.open("r", encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        fields = tuple(reader.fieldnames or ())
        rows = list(reader)
    for row in rows:
        traces = json.loads(row.get("법률ToolTrace", "[]") or "[]")
        result, reason = analyze_validation(
            row.get("PreValidationRawResponse", ""),
            row.get("AgentRawResponse", ""),
            traces,
            row.get("오류", ""),
        )
        row["ValidationResult"] = result
        row["ValidationFailureReason"] = reason

    output_path.parent.mkdir(parents=True, exist_ok=True)
    temporary = output_path.with_suffix(output_path.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
    temporary.replace(output_path)
    print(f"Reanalyzed {len(rows)} rows without API calls: {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

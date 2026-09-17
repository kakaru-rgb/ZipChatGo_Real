from __future__ import annotations

import argparse
import sys
from pathlib import Path


AI_SERVER_ROOT = Path(__file__).resolve().parents[1]
if str(AI_SERVER_ROOT) not in sys.path:
    sys.path.insert(0, str(AI_SERVER_ROOT))

from app.evaluation.exam_data_quality import (
    inspect_reviewed_exam_csv,
    write_quality_report,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Read-only quality check for reviewed exam CSV data.")
    parser.add_argument("--input-csv", type=Path, required=True)
    parser.add_argument("--subject", required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    report = inspect_reviewed_exam_csv(args.input_csv, subject=args.subject)
    if args.output:
        write_quality_report(report, args.output)
    print(
        f"rows={report.target_row_count}/{report.expected_question_count} "
        f"errors={report.blocking_issue_count} warnings={report.warning_count} "
        f"passed={report.passed}"
    )
    for issue in report.issues:
        print(
            f"[{issue.severity}] {issue.code} row={issue.row_number} "
            f"question={issue.question_number} field={issue.field}: {issue.message}"
        )
    return 0 if report.passed else 1


if __name__ == "__main__":
    raise SystemExit(main())


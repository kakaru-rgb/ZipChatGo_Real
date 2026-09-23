from __future__ import annotations

import argparse
import sys
from pathlib import Path


AI_SERVER_ROOT = Path(__file__).resolve().parents[1]
if str(AI_SERVER_ROOT) not in sys.path:
    sys.path.insert(0, str(AI_SERVER_ROOT))

from app.evaluation.production_failure_analysis import analyze_result_csv


def main() -> int:
    parser = argparse.ArgumentParser(description="Post-run failure analysis for passthrough results.")
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    rows = analyze_result_csv(args.input, args.output)
    print(f"Saved {len(rows)} post-analysis rows: {args.output.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


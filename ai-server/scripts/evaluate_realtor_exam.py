from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path


AI_SERVER_ROOT = Path(__file__).resolve().parents[1]
if str(AI_SERVER_ROOT) not in sys.path:
    sys.path.insert(0, str(AI_SERVER_ROOT))

from openai import OpenAI

from app.config import get_openai_api_key, get_openai_model
from app.evaluation.realtor_exam import (
    ChatbotExamEvaluator,
    OpenAIExamPdfExtractor,
    evaluate_exam,
    load_prepared_exam,
    prepare_exam,
    save_prepared_exam,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Prepare and evaluate one year of realtor exam questions."
    )
    parser.add_argument("--year", type=int, choices=(2024, 2025), required=True)
    parser.add_argument(
        "--phase",
        choices=("prepare", "evaluate", "all"),
        required=True,
        help="prepare extracts PDFs; evaluate calls the local chatbot; all runs both.",
    )
    parser.add_argument(
        "--source-root",
        type=Path,
        required=True,
        help="Folder containing the selected year's PDFs and final-answer PDF.",
    )
    parser.add_argument(
        "--extract-model",
        default=os.getenv("OPENAI_EXAM_EXTRACTION_MODEL", get_openai_model()),
    )
    parser.add_argument(
        "--ai-base-url",
        default="http://127.0.0.1:8000",
    )
    parser.add_argument(
        "--limit",
        type=int,
        help=(
            "Prepare or evaluate only this many questions. A later full prepare can "
            "replace the partial dataset while evaluation resumes from the saved CSV."
        ),
    )
    parser.add_argument("--delay", type=float, default=1.0)
    parser.add_argument("--no-resume", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    source_root = args.source_root.resolve()
    if not source_root.is_dir():
        print(f"ERROR: Exam source directory not found: {source_root}", file=sys.stderr)
        return 2

    prepared_path = source_root / f"공인중개사_평가데이터_{args.year}.json"
    output_path = source_root / f"공인중개사_챗봇_평가_{args.year}.csv"

    if args.phase in {"prepare", "all"}:
        api_key = get_openai_api_key()
        if not api_key:
            print("ERROR: OPENAI_API_KEY is not configured.", file=sys.stderr)
            return 2
        extractor = OpenAIExamPdfExtractor(
            OpenAI(api_key=api_key),
            model=args.extract_model,
            progress=print,
        )
        exam = prepare_exam(
            args.year,
            source_root,
            extractor,
            limit=args.limit,
        )
        save_prepared_exam(exam, prepared_path)
        print(f"Prepared {len(exam.questions)} questions: {prepared_path}")

    if args.phase in {"evaluate", "all"}:
        if not prepared_path.exists():
            print(
                f"ERROR: Prepared dataset not found; run --phase prepare first: "
                f"{prepared_path}",
                file=sys.stderr,
            )
            return 2
        exam = load_prepared_exam(prepared_path)
        evaluator = ChatbotExamEvaluator(args.ai_base_url)
        rows = evaluate_exam(
            exam,
            evaluator,
            output_path,
            resume=not args.no_resume,
            limit=args.limit,
            delay_seconds=args.delay,
            progress=print,
        )
        print(f"Saved {len(rows)} evaluation rows: {output_path}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

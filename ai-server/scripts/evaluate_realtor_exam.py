from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path


AI_SERVER_ROOT = Path(__file__).resolve().parents[1]
if str(AI_SERVER_ROOT) not in sys.path:
    sys.path.insert(0, str(AI_SERVER_ROOT))

from openai import OpenAI

from app.config import (
    get_law_vector_store_id,
    get_openai_api_key,
    get_openai_exam_evaluation_model,
)
from app.evaluation.realtor_exam import (
    evaluate_exam,
)
from app.evaluation.local_exam_pdf import (
    load_exam_source_csv,
    prepare_exam_locally,
    save_exam_source_csv,
)
from app.evaluation.realtor_exam_agent import RealtorExamEvaluator
from app.retrievers.openai_vector_store_law_retriever import (
    OpenAIVectorStoreLawRetriever,
)
from app.tools.real_estate_law import RealEstateLawSearchTool


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Prepare and evaluate one year of realtor exam questions."
    )
    parser.add_argument("--year", type=int, choices=(2024, 2025), required=True)
    parser.add_argument(
        "--phase",
        choices=("prepare", "evaluate", "all"),
        required=True,
        help=(
            "prepare builds the dataset; evaluate runs the isolated exam agent; "
            "all runs both."
        ),
    )
    parser.add_argument(
        "--source-root",
        type=Path,
        required=True,
        help="Folder containing the selected year's original question PDFs.",
    )
    parser.add_argument(
        "--evaluation-model",
        default=get_openai_exam_evaluation_model(),
        help="Exam-only model. It does not change the production chatbot model.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        help=(
            "Prepare or evaluate only this many questions. A later full prepare can "
            "replace the partial dataset while evaluation resumes from the saved CSV."
        ),
    )
    parser.add_argument(
        "--subject",
        help="Evaluate only questions whose subject exactly matches this value.",
    )
    parser.add_argument("--delay", type=float, default=1.0)
    parser.add_argument("--no-resume", action="store_true")
    parser.add_argument(
        "--run-label",
        help="Optional label appended to the evaluation CSV filename.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    source_root = args.source_root.resolve()
    if not source_root.is_dir():
        print(f"ERROR: Exam source directory not found: {source_root}", file=sys.stderr)
        return 2

    prepared_path = source_root / f"공인중개사_문항_{args.year}.csv"
    model_label = re.sub(r"[^A-Za-z0-9._-]", "_", args.evaluation_model)
    run_label = ""
    if args.run_label:
        safe_run_label = re.sub(r"[^A-Za-z0-9가-힣._-]", "_", args.run_label)
        run_label = f"_{safe_run_label}"
    output_path = source_root / (
        f"공인중개사_시험평가_{args.year}_{model_label}{run_label}.csv"
    )

    if args.phase in {"prepare", "all"}:
        if args.limit is not None:
            print(
                "ERROR: --limit is only supported during evaluation; "
                "local PDF preparation always validates the complete paper.",
                file=sys.stderr,
            )
            return 2
        exam = prepare_exam_locally(args.year, source_root)
        save_exam_source_csv(exam, prepared_path)
        print(
            f"Prepared {len(exam.questions)} questions locally without an LLM: "
            f"{prepared_path}"
        )

    if args.phase in {"evaluate", "all"}:
        if not prepared_path.exists():
            print(
                f"ERROR: Prepared dataset not found; run --phase prepare first: "
                f"{prepared_path}",
                file=sys.stderr,
            )
            return 2
        api_key = get_openai_api_key()
        if not api_key:
            print("ERROR: OPENAI_API_KEY is not configured.", file=sys.stderr)
            return 2
        exam = load_exam_source_csv(prepared_path)
        client = OpenAI(api_key=api_key)
        vector_store_id = get_law_vector_store_id()
        law_search = None
        if vector_store_id:
            retriever = OpenAIVectorStoreLawRetriever(
                api_key,
                vector_store_id,
                client=client,
            )
            law_search = RealEstateLawSearchTool(retriever).search
        else:
            print(
                "WARNING: LAW_VECTOR_STORE_ID is not configured; "
                "exam-only RAG is disabled."
            )
        evaluator = RealtorExamEvaluator(
            client,
            model=args.evaluation_model,
            law_search=law_search,
        )
        rows = evaluate_exam(
            exam,
            evaluator,
            output_path,
            resume=not args.no_resume,
            subject=args.subject,
            limit=args.limit,
            delay_seconds=args.delay,
            progress=print,
        )
        print(f"Saved {len(rows)} evaluation rows: {output_path}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

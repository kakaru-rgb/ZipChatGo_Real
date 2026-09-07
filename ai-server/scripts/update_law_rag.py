from __future__ import annotations

import argparse
import sys
from datetime import UTC, datetime
from pathlib import Path


AI_SERVER_ROOT = Path(__file__).resolve().parents[1]
PROJECT_ROOT = AI_SERVER_ROOT.parent
if str(AI_SERVER_ROOT) not in sys.path:
    sys.path.insert(0, str(AI_SERVER_ROOT))

from dotenv import set_key
from openai import OpenAI

from app.config import get_law_api_oc, get_openai_api_key
from app.law.documents import add_vector_store_to_manifest, write_law_corpus
from app.law.national_law_api import NationalLawApiClient, NationalLawApiError
from app.law.targets import LAW_TARGETS
from app.law.vector_store import (
    OpenAIVectorStoreUpdater,
    VectorStoreBuild,
    VectorStoreUpdateError,
    get_failed_build,
)
from app.retrievers.openai_vector_store_law_retriever import (
    OpenAIVectorStoreLawRetriever,
)


SMOKE_QUERIES = (
    ("전입신고 대항력 발생 시점", "주택임대차보호법", "제3조"),
    ("공인중개사 중개대상물 확인 설명 의무", "공인중개사법", "제25조"),
    ("부동산 거래 계약 신고 기한", "부동산 거래신고 등에 관한 법률", "제3조"),
    ("상가 임차인 건물 인도 사업자등록 대항력", "상가건물 임대차보호법", "제3조"),
    ("매매 계약금 지급 후 계약 해제", "민법", "제565조"),
    ("부동산 소유권 이전등기 공동신청 원칙", "부동산등기법", "제23조"),
    (
        "구분소유자 전원으로 구성되는 집합건물 관리단",
        "집합건물의 소유 및 관리에 관한 법률",
        "제23조",
    ),
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Collect current real-estate laws from the National Law Information "
            "Open API and rebuild an OpenAI Vector Store."
        )
    )
    parser.add_argument(
        "--collect-only",
        action="store_true",
        help="Generate local Markdown documents without creating OpenAI resources.",
    )
    parser.add_argument(
        "--write-env",
        action="store_true",
        help="Replace LAW_VECTOR_STORE_ID in the project .env only after validation.",
    )
    parser.add_argument(
        "--keep-failed-resources",
        action="store_true",
        help="Do not clean up OpenAI resources created by a failed rebuild.",
    )
    parser.add_argument(
        "--output-root",
        type=Path,
        default=AI_SERVER_ROOT / "data" / "law-rag",
        help="Directory for generated law documents and manifests.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    law_api_oc = get_law_api_oc()
    if not law_api_oc:
        print("ERROR: LAW_API_OC is not configured in the project .env.", file=sys.stderr)
        return 2

    build_id = datetime.now(UTC).strftime("%Y%m%dT%H%M%S%fZ")
    try:
        law_client = NationalLawApiClient(law_api_oc)
        laws = []
        for index, target in enumerate(LAW_TARGETS, start=1):
            print(f"Collecting {index}/{len(LAW_TARGETS)}: {target.name}")
            law = law_client.fetch_current_law(target)
            laws.append(law)
            print(
                f"  -> {law.law_type}, effective {law.effective_date}, "
                f"articles {len(law.articles)}"
            )
        corpus = write_law_corpus(laws, args.output_root, build_id=build_id)
    except (NationalLawApiError, FileExistsError, OSError) as exception:
        print(f"ERROR: {exception}", file=sys.stderr)
        return 1

    print(f"Generated {len(corpus.files)} article documents: {corpus.build_dir}")
    if args.collect_only:
        print("Collection-only mode completed; no OpenAI resources were created.")
        return 0

    openai_api_key = get_openai_api_key()
    if not openai_api_key:
        print("ERROR: OPENAI_API_KEY is not configured in the project .env.", file=sys.stderr)
        return 2

    client = OpenAI(api_key=openai_api_key)
    updater = OpenAIVectorStoreUpdater(client, progress=print)
    build: VectorStoreBuild | None = None
    store_name = f"zipchatgo-law-rag-{build_id}"
    try:
        build = updater.rebuild(
            corpus.files,
            store_name=store_name,
            build_id=build_id,
        )
        _validate_search(client, build.vector_store_id)
        add_vector_store_to_manifest(
            corpus,
            build.vector_store_id,
            list(build.openai_file_ids),
        )
    except VectorStoreUpdateError as exception:
        failed_build = get_failed_build(exception)
        if failed_build and not args.keep_failed_resources:
            updater.cleanup(failed_build)
        print(f"ERROR: {exception}", file=sys.stderr)
        return 1
    except Exception as exception:
        if build and not args.keep_failed_resources:
            updater.cleanup(build)
        print(f"ERROR: Vector Store validation failed: {exception}", file=sys.stderr)
        return 1

    if args.write_env:
        env_path = PROJECT_ROOT / ".env"
        set_key(str(env_path), "LAW_VECTOR_STORE_ID", build.vector_store_id)
        print("Updated LAW_VECTOR_STORE_ID in the project .env.")
    else:
        print("LAW_VECTOR_STORE_ID was not changed. Re-run with --write-env after review.")

    print(f"Law RAG rebuild completed: {build.vector_store_id}")
    print("Restart FastAPI after changing LAW_VECTOR_STORE_ID.")
    return 0


def _validate_search(client: OpenAI, vector_store_id: str) -> None:
    retriever = OpenAIVectorStoreLawRetriever(
        api_key="validation-uses-injected-client",
        vector_store_id=vector_store_id,
        client=client,
        max_results=10,
    )
    for query, expected_law_name, expected_article_number in SMOKE_QUERIES:
        response = retriever.search(query)
        matched_citations = {
            (result.law_name, result.article_number) for result in response.results
        }
        if (expected_law_name, expected_article_number) not in matched_citations:
            raise RuntimeError(
                "Smoke query did not retrieve "
                f"{expected_law_name} {expected_article_number}: {query}"
            )
        print(
            f"Validated search: {query} -> "
            f"{expected_law_name} {expected_article_number}"
        )


if __name__ == "__main__":
    raise SystemExit(main())

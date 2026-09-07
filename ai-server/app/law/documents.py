import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from app.law.models import LawArticle, LawDocument


@dataclass(frozen=True)
class GeneratedLawFile:
    path: Path
    attributes: dict[str, str]


@dataclass(frozen=True)
class GeneratedLawCorpus:
    build_id: str
    build_dir: Path
    manifest_path: Path
    files: tuple[GeneratedLawFile, ...]


def write_law_corpus(
    laws: list[LawDocument],
    output_root: Path,
    build_id: str | None = None,
) -> GeneratedLawCorpus:
    actual_build_id = build_id or datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    build_dir = output_root / actual_build_id
    documents_dir = build_dir / "documents"
    documents_dir.mkdir(parents=True, exist_ok=False)

    generated_files: list[GeneratedLawFile] = []
    manifest_laws: list[dict[str, object]] = []
    for law in laws:
        law_files = [
            _write_article(documents_dir, law, article)
            for article in law.articles
        ]
        generated_files.extend(law_files)
        manifest_laws.append(
            {
                "law_name": law.law_name,
                "law_type": law.law_type,
                "law_id": law.law_id,
                "law_serial_number": law.law_serial_number,
                "effective_date": law.effective_date,
                "promulgation_date": law.promulgation_date,
                "promulgation_number": law.promulgation_number,
                "revision_type": law.revision_type,
                "source_url": law.source_url,
                "article_count": len(law.articles),
            }
        )

    manifest = {
        "schema_version": 1,
        "build_id": actual_build_id,
        "generated_at": datetime.now(UTC).isoformat(),
        "source": "National Law Information Center Open API (target=eflaw)",
        "document_strategy": "one_markdown_file_per_article",
        "law_count": len(laws),
        "article_file_count": len(generated_files),
        "laws": manifest_laws,
    }
    manifest_path = build_dir / "manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return GeneratedLawCorpus(
        build_id=actual_build_id,
        build_dir=build_dir,
        manifest_path=manifest_path,
        files=tuple(generated_files),
    )


def add_vector_store_to_manifest(
    corpus: GeneratedLawCorpus,
    vector_store_id: str,
    openai_file_ids: list[str],
) -> None:
    manifest = json.loads(corpus.manifest_path.read_text(encoding="utf-8"))
    manifest["openai_vector_store"] = {
        "id": vector_store_id,
        "file_count": len(openai_file_ids),
        "file_ids": openai_file_ids,
    }
    corpus.manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def _write_article(
    output_dir: Path,
    law: LawDocument,
    article: LawArticle,
) -> GeneratedLawFile:
    safe_key = "".join(character for character in article.article_key if character.isalnum())
    filename = f"{law.law_id}_{safe_key or 'article'}.md"
    path = output_dir / filename
    title = article.article_number
    if article.article_title:
        title += f"({article.article_title})"

    metadata = {
        "law_name": law.law_name,
        "law_type": law.law_type,
        "law_id": law.law_id,
        "law_serial_number": law.law_serial_number,
        "article_number": article.article_number,
        "article_title": article.article_title or "",
        "effective_date": article.effective_date or law.effective_date or "",
        "promulgation_date": law.promulgation_date or "",
        "promulgation_number": law.promulgation_number or "",
        "revision_type": law.revision_type or "",
        "source_url": law.source_url,
    }
    body = "\n".join(
        [
            f"# {law.law_name}",
            "",
            f"- 법령 종류: {law.law_type}",
            f"- 시행일: {metadata['effective_date'] or '확인 필요'}",
            f"- 공포일: {metadata['promulgation_date'] or '확인 필요'}",
            f"- 공포번호: {metadata['promulgation_number'] or '확인 필요'}",
            f"- 공식 출처: {law.source_url}",
            "",
            f"## {title}",
            "",
            article.text,
            "",
            "---",
            "이 문서는 국가법령정보 공동활용 Open API에서 생성한 검색용 자료입니다.",
        ]
    )
    path.write_text(body, encoding="utf-8")
    return GeneratedLawFile(path=path, attributes=metadata)

import json
import re
from collections import Counter
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


def load_law_corpus(build_dir: Path) -> GeneratedLawCorpus:
    """Load an already collected corpus without calling the law API again.

    Older builds may contain National Law API hierarchy units (chapter/section
    headings) that were previously counted as articles. They remain untouched
    on disk for auditability, but are excluded from the upload list and are
    recorded separately in the manifest.
    """
    manifest_path = build_dir / "manifest.json"
    documents_dir = build_dir / "documents"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    laws_by_id = {str(law["law_id"]): law for law in manifest["laws"]}

    files: list[GeneratedLawFile] = []
    article_counts: Counter[str] = Counter()
    ignored_local_structure_files = 0
    for path in sorted(documents_dir.glob("*.md")):
        generated = _load_article(path, laws_by_id)
        if generated is None:
            ignored_local_structure_files += 1
            continue
        files.append(generated)
        article_counts[generated.attributes["law_id"]] += 1

    source_unit_count = int(
        manifest.get("source_unit_count", manifest.get("article_file_count", 0))
    )
    manifest["source_unit_count"] = source_unit_count
    manifest["document_file_count"] = len(list(documents_dir.glob("*.md")))
    manifest["article_file_count"] = len(files)
    manifest["ignored_structure_unit_count"] = source_unit_count - len(files)
    manifest["ignored_local_structure_file_count"] = ignored_local_structure_files
    for law in manifest["laws"]:
        law.setdefault("source_unit_count", law.get("article_count", 0))
        law["article_count"] = article_counts[str(law["law_id"])]
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    return GeneratedLawCorpus(
        build_id=str(manifest["build_id"]),
        build_dir=build_dir,
        manifest_path=manifest_path,
        files=tuple(files),
    )


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
    *,
    status: str = "completed",
    file_counts: dict[str, int] | None = None,
) -> None:
    manifest = json.loads(corpus.manifest_path.read_text(encoding="utf-8"))
    manifest["openai_vector_store"] = {
        "id": vector_store_id,
        "file_count": len(openai_file_ids),
        "file_ids": openai_file_ids,
        "status": status,
    }
    if file_counts is not None:
        manifest["openai_vector_store"]["file_counts"] = file_counts
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
        "article_key": article.article_key,
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


def _load_article(
    path: Path,
    laws_by_id: dict[str, dict[str, object]],
) -> GeneratedLawFile | None:
    law_id, _, article_key = path.stem.partition("_")
    law = laws_by_id.get(law_id)
    if law is None or not article_key:
        raise ValueError(f"Document filename does not match manifest: {path.name}")

    lines = path.read_text(encoding="utf-8").splitlines()
    heading_index = next(
        (index for index, line in enumerate(lines) if line.startswith("## ")),
        None,
    )
    if heading_index is None:
        raise ValueError(f"Document has no article heading: {path.name}")
    heading = lines[heading_index][3:].strip()
    match = re.match(r"^(제\d+조(?:의\d+)?)(?:\((.*)\))?$", heading)
    if match is None:
        raise ValueError(f"Document has an invalid article heading: {path.name}")
    article_number, article_title = match.groups()
    first_body_line = next(
        (
            line.strip()
            for line in lines[heading_index + 1 :]
            if line.strip() and line.strip() != "---"
        ),
        "",
    )
    if not first_body_line.startswith(article_number):
        return None

    metadata_lines = {
        key.strip(): value.strip()
        for line in lines[:heading_index]
        if line.startswith("- ") and ":" in line
        for key, value in [line[2:].split(":", 1)]
    }
    attributes = {
        "law_name": str(law["law_name"]),
        "law_type": str(law["law_type"]),
        "law_id": law_id,
        "law_serial_number": str(law["law_serial_number"]),
        "article_number": article_number,
        "article_title": article_title or "",
        "effective_date": metadata_lines.get("시행일", ""),
        "promulgation_date": str(law.get("promulgation_date") or ""),
        "promulgation_number": str(law.get("promulgation_number") or ""),
        "revision_type": str(law.get("revision_type") or ""),
        "source_url": str(law["source_url"]),
        "article_key": article_key,
    }
    return GeneratedLawFile(path=path, attributes=attributes)

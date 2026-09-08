import json

from app.law.documents import load_law_corpus, write_law_corpus
from app.law.models import LawArticle, LawDocument


def test_write_law_corpus_creates_one_utf8_markdown_file_per_article(tmp_path) -> None:
    law = LawDocument(
        law_name="주택임대차보호법",
        law_type="법률",
        law_id="001248",
        law_serial_number="276291",
        promulgation_date="2025-10-01",
        promulgation_number="21065",
        effective_date="2026-01-02",
        revision_type="타법개정",
        source_url="https://www.law.go.kr/LSW/lsInfoP.do?lsiSeq=276291",
        articles=[
            LawArticle(
                article_key="0003001",
                article_number="제3조",
                article_title="대항력 등",
                effective_date="2026-01-02",
                text="제3조(대항력 등)\n① 주택의 인도와 주민등록을 마친다.",
            )
        ],
    )

    corpus = write_law_corpus([law], tmp_path, build_id="test-build")

    assert len(corpus.files) == 1
    content = corpus.files[0].path.read_text(encoding="utf-8")
    assert "# 주택임대차보호법" in content
    assert "## 제3조(대항력 등)" in content
    assert "주민등록" in content
    assert corpus.files[0].attributes["article_number"] == "제3조"
    manifest = json.loads(corpus.manifest_path.read_text(encoding="utf-8"))
    assert manifest["document_strategy"] == "one_markdown_file_per_article"
    assert manifest["article_file_count"] == 1


def test_load_law_corpus_excludes_hierarchy_documents_and_repairs_manifest(
    tmp_path,
) -> None:
    law = LawDocument(
        law_name="주택임대차보호법",
        law_type="법률",
        law_id="001248",
        law_serial_number="276291",
        effective_date="2026-01-02",
        source_url="https://www.law.go.kr/LSW/lsInfoP.do?lsiSeq=276291",
        articles=[
            LawArticle(
                article_key="0001000",
                article_number="제1조",
                text="제1장 총칙",
            ),
            LawArticle(
                article_key="0001001",
                article_number="제1조",
                article_title="목적",
                text="제1조(목적) 이 법은 임차인을 보호한다.",
            ),
        ],
    )
    written = write_law_corpus([law], tmp_path, build_id="existing-build")

    loaded = load_law_corpus(written.build_dir)

    assert [item.path.name for item in loaded.files] == ["001248_0001001.md"]
    manifest = json.loads(loaded.manifest_path.read_text(encoding="utf-8"))
    assert manifest["source_unit_count"] == 2
    assert manifest["article_file_count"] == 1
    assert manifest["ignored_structure_unit_count"] == 1
    assert manifest["laws"][0]["article_count"] == 1

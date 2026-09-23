from types import SimpleNamespace
from unittest.mock import Mock

from app.law.documents import GeneratedLawFile
from app.law.vector_store import OpenAIVectorStoreUpdater


def test_rebuild_creates_new_store_attaches_metadata_and_waits(tmp_path) -> None:
    document = tmp_path / "law.md"
    document.write_text("# 법령\n\n## 제3조\n본문", encoding="utf-8")
    generated = GeneratedLawFile(
        path=document,
        attributes={"law_name": "주택임대차보호법", "article_number": "제3조"},
    )
    client = Mock()
    client.vector_stores.create.return_value = SimpleNamespace(id="vs-new")
    client.files.create.return_value = SimpleNamespace(id="file-new")
    client.vector_stores.retrieve.return_value = SimpleNamespace(
        file_counts=SimpleNamespace(
            completed=1,
            in_progress=0,
            failed=0,
            cancelled=0,
            total=1,
        )
    )
    updater = OpenAIVectorStoreUpdater(
        client,
        poll_interval_seconds=0,
        timeout_seconds=1,
    )

    result = updater.rebuild([generated], "law-store", "build-1")

    assert result.vector_store_id == "vs-new"
    assert result.openai_file_ids == ("file-new",)
    client.vector_stores.files.create.assert_called_once()
    attach = client.vector_stores.files.create.call_args.kwargs
    assert attach["vector_store_id"] == "vs-new"
    assert attach["attributes"]["law_name"] == "주택임대차보호법"
    assert attach["attributes"]["article_number"] == "제3조"


def test_resume_skips_articles_already_attached_to_store(tmp_path) -> None:
    document = tmp_path / "law.md"
    document.write_text("# 법령\n\n## 제3조\n본문", encoding="utf-8")
    generated = GeneratedLawFile(
        path=document,
        attributes={
            "law_name": "주택임대차보호법",
            "law_id": "001248",
            "article_key": "0003001",
            "article_number": "제3조",
        },
    )
    client = Mock()
    client.vector_stores.files.list.return_value = SimpleNamespace(
        data=[
            SimpleNamespace(
                id="file-existing",
                attributes={"law_id": "001248", "article_key": "0003001"},
            )
        ],
        has_more=False,
    )
    client.vector_stores.retrieve.return_value = SimpleNamespace(
        file_counts=SimpleNamespace(
            completed=1,
            in_progress=0,
            failed=0,
            cancelled=0,
            total=1,
        )
    )
    updater = OpenAIVectorStoreUpdater(
        client,
        poll_interval_seconds=0,
        timeout_seconds=1,
    )

    result = updater.resume([generated], "vs-existing")

    assert result.vector_store_id == "vs-existing"
    assert result.openai_file_ids == ("file-existing",)
    client.files.create.assert_not_called()
    client.vector_stores.files.create.assert_not_called()

from types import SimpleNamespace
from unittest.mock import Mock

from app.retrievers.openai_vector_store_law_retriever import (
    OpenAIVectorStoreLawRetriever,
)


def test_search_returns_vector_store_chunks_with_law_metadata() -> None:
    client = Mock()
    client.vector_stores.search.return_value = SimpleNamespace(
        data=[
            SimpleNamespace(
                score=0.91,
                filename="001248_0003001.md",
                attributes={
                    "law_name": "주택임대차보호법",
                    "law_type": "법률",
                    "article_number": "제3조",
                    "article_title": "대항력 등",
                    "effective_date": "2026-01-02",
                    "law_id": "001248",
                    "law_serial_number": "276291",
                    "source_url": "https://www.law.go.kr/LSW/lsInfoP.do?lsiSeq=276291",
                },
                content=[SimpleNamespace(type="text", text="제3조 대항력 본문")],
            )
        ]
    )
    retriever = OpenAIVectorStoreLawRetriever(
        "test-key",
        "vs-law",
        client=client,
    )

    result = retriever.search("전입신고하면 대항력은 언제 생겨?")

    client.vector_stores.search.assert_called_once_with(
        vector_store_id="vs-law",
        query="전입신고하면 대항력은 언제 생겨?",
        max_num_results=5,
        rewrite_query=False,
    )
    assert result.total_count == 1
    assert result.results[0].law_name == "주택임대차보호법"
    assert result.results[0].article_number == "제3조"
    assert result.results[0].score == 0.91
    assert result.results[0].text == "제3조 대항력 본문"


def test_search_filters_weak_results_relative_to_best_match() -> None:
    client = Mock()
    client.vector_stores.search.return_value = SimpleNamespace(
        data=[
            SimpleNamespace(
                score=0.8,
                filename="best.md",
                attributes={"law_name": "주택임대차보호법", "article_number": "제3조"},
                content=[SimpleNamespace(type="text", text="대항력 본문")],
            ),
            SimpleNamespace(
                score=0.7,
                filename="weak.md",
                attributes={"law_name": "다른 법률", "article_number": "제1조"},
                content=[SimpleNamespace(type="text", text="관련성이 낮은 본문")],
            ),
        ]
    )
    retriever = OpenAIVectorStoreLawRetriever(
        "test-key",
        "vs-law",
        client=client,
    )

    result = retriever.search("대항력 발생 시점")

    assert result.total_count == 1
    assert result.results[0].article_number == "제3조"

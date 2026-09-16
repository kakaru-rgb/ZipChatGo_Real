from app.law.canonical_catalog import CANONICAL_LAW_NAMES
from app.law.search_routing import (
    LawArticlePair,
    detect_canonical_law_article_pairs,
    detect_canonical_law_names,
)
from app.retrievers.law_retriever import LawSearchItem, LawSearchResponse
from app.tools.real_estate_law import RealEstateLawSearchTool


def _response(query: str, law_name: str = "주택임대차보호법") -> LawSearchResponse:
    return LawSearchResponse(
        query=query,
        total_count=1,
        results=[LawSearchItem(
            rank=1,
            score=0.8,
            law_name=law_name,
            article_number="제6조의2",
            text="임대차에 관한 조문",
            filename="law.md",
        )],
    )


class RecordingRetriever:
    def __init__(self, *, exact_hit: bool = False, filtered_hit: bool = True) -> None:
        self.exact_hit = exact_hit
        self.filtered_hit = filtered_hit
        self.exact_calls: list[tuple[str, list[LawArticlePair]]] = []
        self.semantic_calls: list[tuple[str, list[str]]] = []

    def search_exact(self, query, pairs):
        self.exact_calls.append((query, list(pairs)))
        return _response(query) if self.exact_hit else LawSearchResponse(
            query=query, total_count=0, results=[]
        )

    def search(self, query, *, law_names=()):
        self.semantic_calls.append((query, list(law_names)))
        if law_names and not self.filtered_hit:
            return LawSearchResponse(query=query, total_count=0, results=[])
        return _response(query)


def test_canonical_catalog_and_longest_exact_name_match() -> None:
    assert len(CANONICAL_LAW_NAMES) == 49
    assert detect_canonical_law_names("주택임대차보호법 시행령 제2조") == [
        "주택임대차보호법 시행령"
    ]
    assert detect_canonical_law_names("주택임대차보호법령에 따르면") == []
    assert detect_canonical_law_names("민법과 주택임대차보호법에서") == [
        "민법", "주택임대차보호법"
    ]


def test_a_filters_explicit_user_law_and_falls_back_after_filter_miss() -> None:
    retriever = RecordingRetriever(filtered_hit=False)
    result = RealEstateLawSearchTool(retriever).search({
        "query": "계약갱신요구권",
        "_user_question": "주택임대차보호법에서 계약갱신요구권은?",
    })
    assert retriever.semantic_calls == [
        ("계약갱신요구권", ["주택임대차보호법"]),
        ("계약갱신요구권", []),
    ]
    assert "applied_law_names" not in result


def test_a_uses_model_law_when_user_has_none_and_does_not_force_filter() -> None:
    retriever = RecordingRetriever()
    tool = RealEstateLawSearchTool(retriever)
    tool.search({"query": "주택임대차보호법 제도", "_user_question": "갱신할 수 있나요?"})
    tool.search({"query": "계약갱신요구권", "_user_question": "갱신할 수 있나요?"})
    assert retriever.semantic_calls == [
        ("주택임대차보호법 제도", ["주택임대차보호법"]),
        ("계약갱신요구권", []),
    ]


def test_b_exact_hit_prioritizes_user_named_article() -> None:
    retriever = RecordingRetriever(exact_hit=True)
    tool = RealEstateLawSearchTool(retriever)
    tool.search({
        "query": "묵시적 갱신 해지",
        "_user_question": "주택임대차보호법 제6조의2는 어떻게 적용돼?",
    })
    assert retriever.exact_calls == [
        ("묵시적 갱신 해지", [LawArticlePair("주택임대차보호법", "제6조의2")])
    ]
    assert retriever.semantic_calls == []


def test_b_model_named_article_hits_and_miss_falls_back_to_semantic() -> None:
    retriever = RecordingRetriever(exact_hit=False)
    tool = RealEstateLawSearchTool(retriever)
    tool.search({"query": "주택임대차보호법 제3조 대항력"})
    assert retriever.exact_calls == [
        ("주택임대차보호법 제3조 대항력", [LawArticlePair("주택임대차보호법", "제3조")])
    ]
    assert retriever.semantic_calls == [
        ("주택임대차보호법 제3조 대항력", ["주택임대차보호법"])
    ]
    assert detect_canonical_law_article_pairs("대항력은 언제 생겨?") == []


def test_b_does_not_pair_bare_model_article_with_user_law() -> None:
    retriever = RecordingRetriever()
    RealEstateLawSearchTool(retriever).search({
        "query": "제3조 대항력",
        "_user_question": "주택임대차보호법에서 대항력은 언제 생겨?",
    })
    assert retriever.exact_calls == []
    assert retriever.semantic_calls == [("제3조 대항력", ["주택임대차보호법"])]


def test_a_preserves_multiple_explicit_canonical_laws() -> None:
    retriever = RecordingRetriever()
    RealEstateLawSearchTool(retriever).search({
        "query": "임대차 효력",
        "_user_question": "민법과 주택임대차보호법에서 임대차 효력은?",
    })
    assert retriever.semantic_calls == [
        ("임대차 효력", ["민법", "주택임대차보호법"])
    ]

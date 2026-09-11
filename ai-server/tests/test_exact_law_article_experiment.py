from types import SimpleNamespace
from unittest.mock import Mock

from app.evaluation.exact_law_article_experiment import (
    ExactLawArticleExperimentHandler,
    OpenAIVectorStoreExactLawArticleLookup,
    detect_law_article_pairs,
)
from app.evaluation.law_name_filter_experiment import LawNameFilterExperimentHandler


def test_detects_canonical_exact_pairs_and_prefers_longest_law_name() -> None:
    pairs = detect_law_article_pairs(
        "공인중개사법 시행규칙 제 6 조와 공인중개사법 제18조의 4 확인"
    )
    assert [(pair.law_name, pair.article_number) for pair in pairs] == [
        ("공인중개사법 시행규칙", "제6조"),
        ("공인중개사법", "제18조의4"),
    ]
    assert [pair.article_number for pair in detect_law_article_pairs(
        "공인중개사법 위반 여부를 제7조, 제26조와 제33조로 확인"
    )] == ["제7조", "제26조", "제33조"]


def test_exact_lookup_uses_both_metadata_attributes() -> None:
    item = SimpleNamespace(
        attributes={
            "law_name": "공인중개사법 시행규칙",
            "article_number": "제6조",
            "article_title": "등록사항 등의 통지",
        },
        content=[SimpleNamespace(type="text", text="제6조 내용")],
        filename="rule-6.md",
        score=0.75,
    )
    client = SimpleNamespace(vector_stores=SimpleNamespace(search=Mock(return_value=SimpleNamespace(data=[item]))))
    lookup = OpenAIVectorStoreExactLawArticleLookup(client, "vs-test")
    pair = detect_law_article_pairs("공인중개사법 시행규칙 제6조")[0]
    result = lookup.search("query", [pair])
    filters = client.vector_stores.search.call_args.kwargs["filters"]
    assert filters == {
        "type": "and",
        "filters": [
            {"type": "eq", "key": "law_name", "value": "공인중개사법 시행규칙"},
            {"type": "eq", "key": "article_number", "value": "제6조"},
        ],
    }
    assert result["results"][0]["article_number"] == "제6조"


def test_exact_hit_skips_semantic_fallback_and_preserves_result_object() -> None:
    exact_result = {"total_count": 1, "results": [{"article_number": "제6조"}]}
    exact_lookup = Mock()
    exact_lookup.search.return_value = exact_result
    base_handler = Mock()
    semantic = LawNameFilterExperimentHandler(base_handler, "공인중개사법령상 문제")
    experiment = ExactLawArticleExperimentHandler(exact_lookup, semantic)
    returned = experiment({"query": "핵심 법률 검색어: 공인중개사법 시행규칙 제6조"})
    assert returned is exact_result
    base_handler.assert_not_called()
    assert experiment.traces[0].hit is True
    assert experiment.traces[0].semantic_fallback is False


def test_missing_exact_pair_uses_existing_a_semantic_handler() -> None:
    semantic_result = {"total_count": 1, "results": [{"article_number": "제6조의3"}]}
    base_handler = Mock(return_value=semantic_result)
    semantic = LawNameFilterExperimentHandler(base_handler, "주택임대차보호법상 문제")
    exact_lookup = Mock()
    experiment = ExactLawArticleExperimentHandler(exact_lookup, semantic)
    arguments = {"query": "핵심 법률 검색어: 주택임대차보호법 계약갱신요구권"}
    returned = experiment(arguments)
    assert returned is semantic_result
    exact_lookup.search.assert_not_called()
    assert base_handler.call_args.args[0]["law_names"] == ["주택임대차보호법"]
    assert experiment.traces[0].semantic_fallback is True


def test_supplier_uses_original_model_query_when_handler_query_was_truncated() -> None:
    exact_result = {"total_count": 1, "results": [{"article_number": "제10조"}]}
    exact_lookup = Mock()
    exact_lookup.search.return_value = exact_result
    semantic = LawNameFilterExperimentHandler(Mock(), "공인중개사법령상 문제")
    experiment = ExactLawArticleExperimentHandler(
        exact_lookup,
        semantic,
        model_query_supplier=lambda: "공인중개사법 제10조 결격사유",
    )
    returned = experiment({"query": "사용자 질문만 남은 500자 truncated query"})
    assert returned is exact_result
    pairs = exact_lookup.search.call_args.args[1]
    assert [(pair.law_name, pair.article_number) for pair in pairs] == [
        ("공인중개사법", "제10조")
    ]

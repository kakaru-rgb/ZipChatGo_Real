from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Sequence

import pytest

from app.evaluation.canonical_catalog_law_experiment import (
    CanonicalCatalogExactLawArticleHandler,
    CanonicalCatalogLawNameFilterHandler,
    CanonicalLawArticlePair,
    detect_canonical_law_article_pairs,
    detect_canonical_law_names,
)
from app.evaluation.canonical_law_catalog import CanonicalLawCatalog
from app.law.targets import LAW_TARGETS


@pytest.fixture
def catalog() -> CanonicalLawCatalog:
    records = [
        {"law_name": target.name, "article_number": "제1조"}
        for target in LAW_TARGETS
    ]
    records.extend(
        [
            {
                "law_name": "부동산 실권리자명의 등기에 관한 법률",
                "article_number": "제4조",
            },
            {
                "law_name": "부동산 실권리자명의 등기에 관한 법률 시행령",
                "article_number": "제3조",
            },
            {
                "law_name": "부동산 실권리자명의 등기에 관한 법률 시행규칙",
                "article_number": "제6조의2",
            },
        ]
    )
    return CanonicalLawCatalog.from_records(records)


def test_detects_all_existing_law_targets_without_importing_them_in_detector(catalog) -> None:
    query = " / ".join(target.name for target in LAW_TARGETS)

    detected = detect_canonical_law_names(query, catalog)

    assert set(detected) == {target.name for target in LAW_TARGETS}


def test_detects_new_v2_canonical_family(catalog) -> None:
    query = (
        "부동산 실권리자명의 등기에 관한 법률, "
        "부동산 실권리자명의 등기에 관한 법률 시행령 및 "
        "부동산 실권리자명의 등기에 관한 법률 시행규칙"
    )

    assert detect_canonical_law_names(query, catalog) == [
        "부동산 실권리자명의 등기에 관한 법률",
        "부동산 실권리자명의 등기에 관한 법률 시행령",
        "부동산 실권리자명의 등기에 관한 법률 시행규칙",
    ]


def test_parses_new_v2_law_and_article_pair(catalog) -> None:
    assert detect_canonical_law_article_pairs(
        "부동산 실권리자명의 등기에 관한 법률 제4조",
        catalog,
    ) == [CanonicalLawArticlePair("부동산 실권리자명의 등기에 관한 법률", "제4조")]


def test_parses_article_subnumber(catalog) -> None:
    assert detect_canonical_law_article_pairs(
        "부동산 실권리자명의 등기에 관한 법률 시행규칙 제 6 조의 2",
        catalog,
    ) == [
        CanonicalLawArticlePair(
            "부동산 실권리자명의 등기에 관한 법률 시행규칙",
            "제6조의2",
        )
    ]


def test_does_not_infer_alias_or_unsupported_law(catalog) -> None:
    query = "부동산실명법, 민사집행법, 장사 등에 관한 법률을 비교해 주세요."

    assert detect_canonical_law_names(query, catalog) == []
    assert detect_canonical_law_article_pairs(query + " 제4조", catalog) == []


@pytest.mark.parametrize(
    "query",
    [
        "시민법 교육 자료입니다.",
        "가짜공인중개사법 제1조를 설명해 주세요.",
        "오늘 판교 날씨를 알려 주세요.",
    ],
)
def test_avoids_partial_substring_and_non_law_false_positives(query, catalog) -> None:
    assert detect_canonical_law_names(query, catalog) == []


def test_multiple_laws_keep_their_own_article_pairs(catalog) -> None:
    pairs = detect_canonical_law_article_pairs(
        "주택임대차보호법 제6조와 민법 제563조를 비교",
        catalog,
    )

    assert pairs == [
        CanonicalLawArticlePair("주택임대차보호법", "제6조"),
        CanonicalLawArticlePair("민법", "제563조"),
    ]


def test_multiple_canonical_laws_are_forwarded_as_or_filter_inputs(catalog) -> None:
    recorder = RecordingHandler(
        responses=[{"total_count": 1, "results": [{"law_name": "민법"}]}]
    )
    handler = CanonicalCatalogLawNameFilterHandler(
        recorder,
        catalog,
        question_text="민법과 주택임대차보호법을 비교해 주세요.",
    )

    handler({"query": "비교"})

    assert recorder.calls[0]["law_names"] == ["민법", "주택임대차보호법"]
    assert handler.traces[0].filtered_search is True
    assert handler.traces[0].fallback is False


def test_zero_filtered_results_preserve_unfiltered_semantic_fallback(catalog) -> None:
    recorder = RecordingHandler(
        responses=[
            {"total_count": 0, "results": []},
            {"total_count": 1, "results": [{"law_name": "민법"}]},
        ]
    )
    handler = CanonicalCatalogLawNameFilterHandler(recorder, catalog)

    result = handler({"query": "민법상 매매"})

    assert result["total_count"] == 1
    assert recorder.calls[0]["law_names"] == ["민법"]
    assert "law_names" not in recorder.calls[1]
    assert handler.traces[0].fallback is True


def test_filter_uses_original_model_query_supplier(catalog) -> None:
    recorder = RecordingHandler(
        responses=[{"total_count": 1, "results": [{"law_name": "주택임대차보호법"}]}]
    )
    handler = CanonicalCatalogLawNameFilterHandler(
        recorder,
        catalog,
        model_query_supplier=lambda: "주택임대차보호법 제6조",
    )

    handler({"query": "사용자 질문: 민법 선택지\n핵심 법률 검색어: 잘린 문자열"})

    assert recorder.calls[0]["law_names"] == ["주택임대차보호법"]
    assert handler.traces[0].source == "model_query"


def test_exact_miss_preserves_semantic_fallback(catalog) -> None:
    semantic_recorder = RecordingHandler(
        responses=[{"total_count": 1, "results": [{"law_name": "민법"}]}]
    )
    semantic_handler = CanonicalCatalogLawNameFilterHandler(
        semantic_recorder,
        catalog,
    )
    exact_lookup = RecordingExactLookup({"total_count": 0, "results": []})
    handler = CanonicalCatalogExactLawArticleHandler(
        exact_lookup,
        semantic_handler,
        catalog,
    )

    result = handler({"query": "민법 제563조"})

    assert result["total_count"] == 1
    assert exact_lookup.pairs == [CanonicalLawArticlePair("민법", "제563조")]
    assert handler.traces[0].attempted is True
    assert handler.traces[0].hit is False
    assert handler.traces[0].semantic_fallback is True


@dataclass
class RecordingHandler:
    responses: list[dict[str, Any]]
    calls: list[dict[str, Any]] = field(default_factory=list)

    def __call__(self, arguments: dict[str, Any]) -> dict[str, Any]:
        self.calls.append(dict(arguments))
        return self.responses[len(self.calls) - 1]


@dataclass
class RecordingExactLookup:
    result: dict[str, Any]
    pairs: list[CanonicalLawArticlePair] = field(default_factory=list)

    def search(
        self,
        query: str,
        pairs: Sequence[CanonicalLawArticlePair],
    ) -> dict[str, Any]:
        self.pairs = list(pairs)
        return self.result

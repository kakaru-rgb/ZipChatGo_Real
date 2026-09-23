from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Callable, Sequence

from openai import APIError

from app.evaluation.law_name_filter_experiment import (
    LawNameFilterExperimentHandler,
    LawNameFilterTrace,
)
from app.law.targets import LAW_TARGETS


ToolHandler = Callable[[dict[str, Any]], dict[str, Any]]


@dataclass(frozen=True)
class LawArticlePair:
    law_name: str
    article_number: str

    def as_dict(self) -> dict[str, str]:
        return {
            "law_name": self.law_name,
            "article_number": self.article_number,
        }


def detect_law_article_pairs(model_query: str) -> list[LawArticlePair]:
    normalized = _normalize_query(model_query)
    matched_laws: list[tuple[str, tuple[int, int]]] = []
    occupied_law_spans: list[tuple[int, int]] = []
    for target in sorted(LAW_TARGETS, key=lambda item: len(item.name), reverse=True):
        law_name = _normalize_query(target.name)
        for match in re.finditer(re.escape(law_name), normalized):
            if any(_overlaps(match.span(), span) for span in occupied_law_spans):
                continue
            matched_laws.append((target.name, match.span()))
            occupied_law_spans.append(match.span())

    unique_laws = list(dict.fromkeys(law_name for law_name, _ in matched_laws))
    if len(unique_laws) == 1:
        return [
            LawArticlePair(unique_laws[0], _canonical_article_number(article))
            for article in dict.fromkeys(re.findall(r"제\d+조(?:의\d+)?", normalized))
        ]

    pairs: list[LawArticlePair] = []
    occupied_spans: list[tuple[int, int]] = []
    for target in sorted(LAW_TARGETS, key=lambda item: len(item.name), reverse=True):
        law_name = _normalize_query(target.name)
        pattern = re.compile(rf"{re.escape(law_name)}(제\d+조(?:의\d+)?)")
        for match in pattern.finditer(normalized):
            if any(_overlaps(match.span(), span) for span in occupied_spans):
                continue
            pair = LawArticlePair(target.name, _canonical_article_number(match.group(1)))
            if pair not in pairs:
                pairs.append(pair)
                occupied_spans.append(match.span())
    return pairs


@dataclass
class ExactLookupCallTrace:
    sequence: int
    model_query: str
    detected_pairs: list[LawArticlePair]
    attempted: bool
    hit: bool
    exact_results: list[dict[str, Any]]
    semantic_fallback: bool

    def as_dict(self) -> dict[str, Any]:
        return {
            "sequence": self.sequence,
            "model_query": self.model_query,
            "detected_pairs": [pair.as_dict() for pair in self.detected_pairs],
            "exact_lookup_attempted": self.attempted,
            "exact_lookup_hit": self.hit,
            "exact_lookup_result": self.exact_results,
            "semantic_fallback": self.semantic_fallback,
        }


class OpenAIVectorStoreExactLawArticleLookup:
    def __init__(self, client: Any, vector_store_id: str, max_results: int = 5) -> None:
        self._client = client
        self._vector_store_id = vector_store_id
        self._max_results = max_results

    def search(
        self,
        query: str,
        pairs: Sequence[LawArticlePair],
    ) -> dict[str, Any]:
        results: list[dict[str, Any]] = []
        for pair in pairs:
            try:
                page = self._client.vector_stores.search(
                    vector_store_id=self._vector_store_id,
                    query=query,
                    filters={
                        "type": "and",
                        "filters": [
                            {"type": "eq", "key": "law_name", "value": pair.law_name},
                            {
                                "type": "eq",
                                "key": "article_number",
                                "value": pair.article_number,
                            },
                        ],
                    },
                    max_num_results=self._max_results,
                    rewrite_query=False,
                )
            except APIError as exception:
                raise RuntimeError("Evaluation exact law/article lookup failed") from exception
            for item in getattr(page, "data", []):
                converted = _to_result(item, len(results) + 1)
                results.append(converted)
        law_names = list(dict.fromkeys(pair.law_name for pair in pairs))
        return {
            "query": query,
            "total_count": len(results),
            "results": results,
            "applied_law_names": law_names,
            "result_order": "relevance_descending",
            "grounding_notice": (
                "rank 1을 우선 검토하고 법령명·조문 번호·시행일을 결과 그대로 인용하세요. "
                "본문에 없는 내용은 추측하지 마세요."
            ),
        }


@dataclass
class ExactLawArticleExperimentHandler:
    exact_lookup: OpenAIVectorStoreExactLawArticleLookup
    semantic_handler: LawNameFilterExperimentHandler
    model_query_supplier: Callable[[], str] | None = None
    traces: list[ExactLookupCallTrace] = field(default_factory=list)

    def __call__(self, arguments: dict[str, Any]) -> dict[str, Any]:
        supplied_query = self.model_query_supplier() if self.model_query_supplier else ""
        model_query = supplied_query or _model_query_from_handler_arguments(arguments)
        pairs = detect_law_article_pairs(model_query)
        exact_result: dict[str, Any] = {"total_count": 0, "results": []}
        if pairs:
            exact_result = self.exact_lookup.search(str(arguments.get("query", "")), pairs)
        hit = _result_count(exact_result) > 0
        if hit:
            result = exact_result
            semantic_fallback = False
        else:
            result = self.semantic_handler(arguments)
            semantic_fallback = True
        self.traces.append(
            ExactLookupCallTrace(
                sequence=len(self.traces) + 1,
                model_query=model_query,
                detected_pairs=pairs,
                attempted=bool(pairs),
                hit=hit,
                exact_results=[
                    _result_summary(item)
                    for item in exact_result.get("results", [])
                    if isinstance(item, dict)
                ],
                semantic_fallback=semantic_fallback,
            )
        )
        return result

    @property
    def law_name_filter_traces(self) -> list[LawNameFilterTrace]:
        return self.semantic_handler.traces


def _to_result(item: Any, rank: int) -> dict[str, Any]:
    attributes = getattr(item, "attributes", None) or {}
    if hasattr(attributes, "model_dump"):
        attributes = attributes.model_dump()
    text = "\n".join(
        str(getattr(content, "text", "")).strip()
        for content in getattr(item, "content", [])
        if getattr(content, "type", None) == "text"
        and str(getattr(content, "text", "")).strip()
    )
    result: dict[str, Any] = {
        "rank": rank,
        "score": float(getattr(item, "score", 0.0)),
        "law_name": _attribute(attributes, "law_name") or "법령명 미상",
        "text": text,
        "filename": str(getattr(item, "filename", "")),
    }
    for key in (
        "law_type",
        "article_number",
        "article_title",
        "effective_date",
        "promulgation_date",
        "law_id",
        "law_serial_number",
        "source_url",
    ):
        value = _attribute(attributes, key)
        if value is not None:
            result[key] = value
    return result


def _result_summary(item: dict[str, Any]) -> dict[str, Any]:
    return {
        key: item.get(key)
        for key in ("rank", "score", "law_name", "article_number", "article_title", "source_url")
    }


def _attribute(attributes: Any, key: str) -> str | None:
    if not isinstance(attributes, dict):
        return None
    value = str(attributes.get(key, "")).strip()
    return value or None


def _model_query_from_handler_arguments(arguments: dict[str, Any]) -> str:
    query = str(arguments.get("query", ""))
    marker = "핵심 법률 검색어:"
    return query.split(marker, 1)[1].strip() if marker in query else query.strip()


def _result_count(result: dict[str, Any]) -> int:
    return int(result.get("total_count", len(result.get("results", []))) or 0)


def _result_summary_list(traces: Sequence[ExactLookupCallTrace]) -> list[dict[str, Any]]:
    return [item for trace in traces for item in trace.exact_results]


def _normalize_query(value: str) -> str:
    return re.sub(r"[^0-9A-Za-z가-힣]", "", value)


def _canonical_article_number(value: str) -> str:
    match = re.fullmatch(r"제(\d+)조(?:의(\d+))?", value)
    if match is None:
        return value
    base = f"제{int(match.group(1))}조"
    return base + (f"의{int(match.group(2))}" if match.group(2) else "")


def _overlaps(left: tuple[int, int], right: tuple[int, int]) -> bool:
    return left[0] < right[1] and right[0] < left[1]

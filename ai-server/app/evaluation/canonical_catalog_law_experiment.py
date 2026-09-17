from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Callable, Protocol, Sequence

from app.evaluation.canonical_law_catalog import CanonicalLawCatalog


ToolHandler = Callable[[dict[str, Any]], dict[str, Any]]
ARTICLE_PATTERN = re.compile(r"제\s*(\d+)\s*조(?:\s*의\s*(\d+))?")


class ExactLookup(Protocol):
    def search(
        self,
        query: str,
        pairs: Sequence["CanonicalLawArticlePair"],
    ) -> dict[str, Any]: ...


@dataclass(frozen=True)
class CanonicalLawMention:
    law_name: str
    start: int
    end: int


@dataclass(frozen=True)
class CanonicalLawArticlePair:
    law_name: str
    article_number: str

    def as_dict(self) -> dict[str, str]:
        return {"law_name": self.law_name, "article_number": self.article_number}


def detect_canonical_law_mentions(
    text: str,
    catalog: CanonicalLawCatalog,
) -> list[CanonicalLawMention]:
    """Match only complete canonical names contained in the frozen catalog."""

    candidates: list[CanonicalLawMention] = []
    for law_name in sorted(catalog.law_names, key=len, reverse=True):
        pattern = _canonical_name_pattern(law_name)
        for match in pattern.finditer(text):
            candidates.append(CanonicalLawMention(law_name, match.start(), match.end()))

    accepted: list[CanonicalLawMention] = []
    for mention in sorted(candidates, key=lambda item: (item.start, -(item.end - item.start))):
        if any(_overlaps(mention, selected) for selected in accepted):
            continue
        accepted.append(mention)
    return sorted(accepted, key=lambda item: item.start)


def detect_canonical_law_names(
    text: str,
    catalog: CanonicalLawCatalog,
) -> list[str]:
    return list(
        dict.fromkeys(
            mention.law_name for mention in detect_canonical_law_mentions(text, catalog)
        )
    )


def detect_canonical_law_article_pairs(
    model_query: str,
    catalog: CanonicalLawCatalog,
) -> list[CanonicalLawArticlePair]:
    mentions = detect_canonical_law_mentions(model_query, catalog)
    unique_laws = list(dict.fromkeys(mention.law_name for mention in mentions))
    if not unique_laws:
        return []

    if len(unique_laws) == 1:
        return _deduplicate_pairs(
            CanonicalLawArticlePair(
                unique_laws[0],
                _canonical_article_number(match.group(1), match.group(2)),
            )
            for match in ARTICLE_PATTERN.finditer(model_query)
        )

    pairs: list[CanonicalLawArticlePair] = []
    for index, mention in enumerate(mentions):
        segment_end = mentions[index + 1].start if index + 1 < len(mentions) else len(model_query)
        segment = model_query[mention.end:segment_end]
        for match in ARTICLE_PATTERN.finditer(segment):
            pairs.append(
                CanonicalLawArticlePair(
                    mention.law_name,
                    _canonical_article_number(match.group(1), match.group(2)),
                )
            )
    return _deduplicate_pairs(pairs)


@dataclass(frozen=True)
class CatalogLawNameFilterTrace:
    source: str
    law_names: tuple[str, ...]
    filtered_search: bool
    fallback: bool
    filtered_result_count: int
    final_result_count: int


@dataclass
class CanonicalCatalogLawNameFilterHandler:
    handler: ToolHandler
    catalog: CanonicalLawCatalog
    question_text: str = ""
    model_query_supplier: Callable[[], str] | None = None
    traces: list[CatalogLawNameFilterTrace] = field(default_factory=list)

    def __call__(self, arguments: dict[str, Any]) -> dict[str, Any]:
        question_laws = detect_canonical_law_names(self.question_text, self.catalog)
        supplied_query = self.model_query_supplier() if self.model_query_supplier else ""
        model_query = supplied_query or _model_query_from_handler_arguments(arguments)
        model_laws = detect_canonical_law_names(model_query, self.catalog)
        law_names = question_laws or model_laws
        source = "user_question" if question_laws else "model_query" if model_laws else "none"

        if not law_names:
            result = self.handler(arguments)
            self._record(source, law_names, False, False, result, result)
            return result

        filtered_arguments = dict(arguments)
        filtered_arguments["law_names"] = law_names
        filtered_result = self.handler(filtered_arguments)
        if _result_count(filtered_result) > 0:
            self._record(source, law_names, True, False, filtered_result, filtered_result)
            return filtered_result

        fallback_result = self.handler(arguments)
        self._record(source, law_names, True, True, filtered_result, fallback_result)
        return fallback_result

    def _record(
        self,
        source: str,
        law_names: Sequence[str],
        filtered_search: bool,
        fallback: bool,
        filtered_result: dict[str, Any],
        final_result: dict[str, Any],
    ) -> None:
        self.traces.append(
            CatalogLawNameFilterTrace(
                source=source,
                law_names=tuple(law_names),
                filtered_search=filtered_search,
                fallback=fallback,
                filtered_result_count=_result_count(filtered_result),
                final_result_count=_result_count(final_result),
            )
        )


@dataclass(frozen=True)
class CatalogExactLookupTrace:
    model_query: str
    detected_pairs: tuple[CanonicalLawArticlePair, ...]
    attempted: bool
    hit: bool
    semantic_fallback: bool


@dataclass
class CanonicalCatalogExactLawArticleHandler:
    exact_lookup: ExactLookup
    semantic_handler: CanonicalCatalogLawNameFilterHandler
    catalog: CanonicalLawCatalog
    model_query_supplier: Callable[[], str] | None = None
    traces: list[CatalogExactLookupTrace] = field(default_factory=list)

    def __call__(self, arguments: dict[str, Any]) -> dict[str, Any]:
        supplied_query = self.model_query_supplier() if self.model_query_supplier else ""
        model_query = supplied_query or str(arguments.get("query", "")).strip()
        pairs = detect_canonical_law_article_pairs(model_query, self.catalog)
        exact_result: dict[str, Any] = {"total_count": 0, "results": []}
        if pairs:
            exact_result = self.exact_lookup.search(str(arguments.get("query", "")), pairs)
        hit = _result_count(exact_result) > 0
        semantic_fallback = not hit
        result = exact_result if hit else self.semantic_handler(arguments)
        self.traces.append(
            CatalogExactLookupTrace(
                model_query=model_query,
                detected_pairs=tuple(pairs),
                attempted=bool(pairs),
                hit=hit,
                semantic_fallback=semantic_fallback,
            )
        )
        return result


def _canonical_name_pattern(law_name: str) -> re.Pattern[str]:
    parts = re.split(r"\s+", law_name.strip())
    body = r"\s+".join(re.escape(part) for part in parts)
    # Korean postpositions and an immediately following article are legitimate
    # delimiters. A preceding Korean/alphanumeric character is not.
    suffix = (
        r"(?=$|[^0-9A-Za-z가-힣]|"
        r"(?:상|과|와|은|는|이|가|을|를|에서|으로|로|에|의)(?:\s|$)|"
        r"제\s*\d+\s*조)"
    )
    return re.compile(rf"(?<![0-9A-Za-z가-힣]){body}{suffix}")


def _canonical_article_number(base: str, sub: str | None) -> str:
    result = f"제{int(base)}조"
    return result + (f"의{int(sub)}" if sub is not None else "")


def _deduplicate_pairs(
    pairs: Sequence[CanonicalLawArticlePair] | Any,
) -> list[CanonicalLawArticlePair]:
    result: list[CanonicalLawArticlePair] = []
    for pair in pairs:
        if pair not in result:
            result.append(pair)
    return result


def _result_count(result: dict[str, Any]) -> int:
    try:
        return int(result.get("total_count", len(result.get("results", []))) or 0)
    except (TypeError, ValueError):
        return len(result.get("results", []))


def _model_query_from_handler_arguments(arguments: dict[str, Any]) -> str:
    query = str(arguments.get("query", ""))
    marker = "핵심 법률 검색어:"
    return query.split(marker, 1)[1].strip() if marker in query else query.strip()


def _overlaps(left: CanonicalLawMention, right: CanonicalLawMention) -> bool:
    return left.start < right.end and right.start < left.end

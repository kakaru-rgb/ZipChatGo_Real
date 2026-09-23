from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Iterable, Sequence

from app.law.targets import LAW_TARGETS


ARTICLE_PATTERN = r"제\s*(\d+)\s*조(?:\s*의\s*(\d+))?"
MARKDOWN_GAP = r"[\s*_`]*"


@dataclass(frozen=True)
class RetrievalArticle:
    law_name: str
    article_number: str
    text: str

    @property
    def pair(self) -> tuple[str, str]:
        return (_normalize_law_name(self.law_name), _canonical_article(self.article_number))


@dataclass(frozen=True)
class CitationTrace:
    raw_citation: str
    parsed_law_name: str | None
    parsed_article_number: str
    citation_role: str
    parent_retrieval_pair: dict[str, str] | None
    parent_text_match: bool
    validation_decision: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "raw_citation": self.raw_citation,
            "parsed_law_name": self.parsed_law_name,
            "parsed_article_number": self.parsed_article_number,
            "citation_role": self.citation_role,
            "parent_retrieval_pair": self.parent_retrieval_pair,
            "parent_text_match": self.parent_text_match,
            "validation_decision": self.validation_decision,
        }


@dataclass(frozen=True)
class PairAwareValidationResult:
    passed: bool
    failure_reason: str
    citations: tuple[CitationTrace, ...]

    def as_dict(self) -> dict[str, Any]:
        return {
            "passed": self.passed,
            "validation_result": "passed" if self.passed else "rejected",
            "failure_reason": self.failure_reason,
            "citations": [citation.as_dict() for citation in self.citations],
        }


@dataclass(frozen=True)
class _Candidate:
    start: int
    end: int
    raw: str
    kind: str
    law_name: str | None
    article_number: str
    same_kind: str | None = None


class PairAwareGroundingValidator:
    """Evaluation-only citation validator; it never calls or changes the Agent."""

    def validate(
        self,
        response_text: str,
        retrieval_results: Sequence[dict[str, Any]],
    ) -> PairAwareValidationResult:
        articles = _retrieval_articles(retrieval_results)
        article_by_pair: dict[tuple[str, str], list[RetrievalArticle]] = {}
        for article in articles:
            article_by_pair.setdefault(article.pair, []).append(article)

        candidates = _parse_candidates(response_text, articles)
        traces: list[CitationTrace] = []
        active_law: str | None = None
        active_parent: RetrievalArticle | None = None

        for candidate in candidates:
            law_name = candidate.law_name
            role = "primary_grounding"

            if candidate.kind == "same":
                law_name = _resolve_same_law(candidate.same_kind, active_law, articles)
            elif candidate.kind == "law_reference":
                law_name = _base_law_name(active_parent.law_name) if active_parent else None
                role = "dependent_cross_reference"
            elif candidate.kind == "bare":
                law_name = active_law

            canonical_law = _canonical_retrieved_law_name(law_name, articles)
            pair = (
                _normalize_law_name(canonical_law or ""),
                candidate.article_number,
            )
            exact_articles = article_by_pair.get(pair, []) if canonical_law else []
            parent_pair = _pair_dict(active_parent) if active_parent else None
            parent_match = False

            if exact_articles:
                decision = "allowed_retrieval_pair"
                active_law = exact_articles[0].law_name
                active_parent = exact_articles[0]
                canonical_law = exact_articles[0].law_name
                parent_pair = None
            elif active_parent and candidate.kind in {"explicit", "same", "law_reference"}:
                parent_match = _parent_contains_reference(active_parent, candidate, canonical_law)
                if parent_match:
                    decision = "allowed_parent_cross_reference"
                    role = "dependent_cross_reference"
                else:
                    decision = "rejected_unretrieved_citation"
                    if role != "dependent_cross_reference":
                        role = "independent_unretrieved"
            else:
                decision = "rejected_unretrieved_citation"
                if role != "dependent_cross_reference":
                    role = "independent_unretrieved"

            traces.append(
                CitationTrace(
                    raw_citation=candidate.raw,
                    parsed_law_name=canonical_law or law_name,
                    parsed_article_number=candidate.article_number,
                    citation_role=role,
                    parent_retrieval_pair=parent_pair,
                    parent_text_match=parent_match,
                    validation_decision=decision,
                )
            )

        rejected = [
            trace for trace in traces if trace.validation_decision.startswith("rejected_")
        ]
        if not traces:
            return PairAwareValidationResult(False, "missing_article_citation", tuple())
        if rejected:
            return PairAwareValidationResult(
                False,
                "ungrounded_law_article_pair",
                tuple(traces),
            )
        return PairAwareValidationResult(True, "", tuple(traces))


def collect_retrieval_results(law_tool_trace: Sequence[dict[str, Any]]) -> list[dict[str, Any]]:
    """Return stored Tool results without mutating the trace or result objects."""
    return [
        result
        for trace in law_tool_trace
        for result in (trace.get("handler_result") or {}).get("results", [])
        if isinstance(result, dict)
    ]


def _retrieval_articles(results: Sequence[dict[str, Any]]) -> list[RetrievalArticle]:
    articles: list[RetrievalArticle] = []
    for result in results:
        law_name = str(result.get("law_name", "")).strip()
        article_number = _canonical_article(str(result.get("article_number", "")))
        if not law_name or not article_number:
            continue
        articles.append(
            RetrievalArticle(
                law_name=law_name,
                article_number=article_number,
                text=str(result.get("text", "")),
            )
        )
    return articles


def _parse_candidates(
    response_text: str,
    articles: Sequence[RetrievalArticle],
) -> list[_Candidate]:
    text = response_text.replace("**", "").replace("__", "")
    candidates: list[_Candidate] = []

    quoted = re.compile(rf"「\s*(?P<law>[^」]+?)\s*」{MARKDOWN_GAP}(?P<article>{ARTICLE_PATTERN})")
    for match in quoted.finditer(text):
        candidates.append(_candidate(match, "explicit", match.group("law")))

    known_laws = {
        article.law_name for article in articles
    } | {target.name for target in LAW_TARGETS}
    for law_name in sorted(known_laws, key=len, reverse=True):
        pattern = re.compile(rf"(?P<law>{re.escape(law_name)}){MARKDOWN_GAP}(?P<article>{ARTICLE_PATTERN})")
        for match in pattern.finditer(text):
            candidates.append(_candidate(match, "explicit", law_name))

    same_pattern = re.compile(
        rf"(?P<prefix>같은\s*(?P<kind>시행규칙|시행령|법)){MARKDOWN_GAP}(?P<article>{ARTICLE_PATTERN})"
    )
    for match in same_pattern.finditer(text):
        candidates.append(
            _Candidate(
                start=match.start(),
                end=match.end(),
                raw=match.group(0),
                kind="same",
                law_name=None,
                article_number=_article_from_match(match),
                same_kind=match.group("kind"),
            )
        )

    law_reference = re.compile(rf"(?<![가-힣A-Za-z])(?P<prefix>법){MARKDOWN_GAP}(?P<article>{ARTICLE_PATTERN})")
    for match in law_reference.finditer(text):
        candidates.append(_candidate(match, "law_reference", None))

    bare = re.compile(rf"(?P<article>{ARTICLE_PATTERN})")
    for match in bare.finditer(text):
        candidates.append(_candidate(match, "bare", None))

    priority = {"explicit": 0, "same": 1, "law_reference": 2, "bare": 3}
    accepted: list[_Candidate] = []
    for candidate in sorted(candidates, key=lambda item: (item.start, priority[item.kind], -(item.end - item.start))):
        if any(_overlaps((candidate.start, candidate.end), (item.start, item.end)) for item in accepted):
            continue
        accepted.append(candidate)
    return sorted(accepted, key=lambda item: item.start)


def _candidate(match: re.Match[str], kind: str, law_name: str | None) -> _Candidate:
    return _Candidate(
        start=match.start(),
        end=match.end(),
        raw=match.group(0),
        kind=kind,
        law_name=law_name,
        article_number=_article_from_match(match),
    )


def _article_from_match(match: re.Match[str]) -> str:
    article_text = match.group("article")
    return _canonical_article(article_text)


def _parent_contains_reference(
    parent: RetrievalArticle,
    candidate: _Candidate,
    law_name: str | None,
) -> bool:
    text = parent.text
    article_regex = _article_regex(candidate.article_number)
    if candidate.kind == "law_reference":
        return bool(re.search(rf"(?:같은\s*)?법\s*{article_regex}", text))
    if candidate.kind == "same":
        same_kind = re.escape(candidate.same_kind or "법")
        return bool(re.search(rf"같은\s*{same_kind}\s*{article_regex}", text))
    if candidate.kind == "explicit" and law_name:
        return bool(
            re.search(
                rf"(?:「\s*)?{re.escape(law_name)}(?:\s*」)?\s*{article_regex}",
                text,
            )
        )
    return False


def _resolve_same_law(
    kind: str | None,
    active_law: str | None,
    articles: Sequence[RetrievalArticle],
) -> str | None:
    if not kind:
        return active_law
    if kind == "법":
        return _base_law_name(active_law) if active_law else None
    if active_law and active_law.endswith(kind):
        return active_law
    candidates = list(dict.fromkeys(article.law_name for article in articles if article.law_name.endswith(kind)))
    return candidates[0] if len(candidates) == 1 else None


def _canonical_retrieved_law_name(
    law_name: str | None,
    articles: Sequence[RetrievalArticle],
) -> str | None:
    if not law_name:
        return None
    normalized = _normalize_law_name(law_name)
    for article in articles:
        if _normalize_law_name(article.law_name) == normalized:
            return article.law_name
    return law_name.strip()


def _base_law_name(law_name: str | None) -> str | None:
    if not law_name:
        return None
    return re.sub(r"\s*(?:시행령|시행규칙)$", "", law_name).strip()


def _pair_dict(article: RetrievalArticle | None) -> dict[str, str] | None:
    if article is None:
        return None
    return {"law_name": article.law_name, "article_number": article.article_number}


def _canonical_article(value: str) -> str:
    match = re.search(ARTICLE_PATTERN, value)
    if match is None:
        return ""
    article = f"제{int(match.group(1))}조"
    return article + (f"의{int(match.group(2))}" if match.group(2) else "")


def _article_regex(article_number: str) -> str:
    match = re.fullmatch(r"제(\d+)조(?:의(\d+))?", article_number)
    if match is None:
        return re.escape(article_number)
    suffix = rf"\s*의\s*{match.group(2)}" if match.group(2) else ""
    return rf"제\s*{match.group(1)}\s*조{suffix}"


def _normalize_law_name(value: str) -> str:
    return re.sub(r"[^0-9A-Za-z가-힣]", "", value)


def _overlaps(left: tuple[int, int], right: tuple[int, int]) -> bool:
    return left[0] < right[1] and right[0] < left[1]


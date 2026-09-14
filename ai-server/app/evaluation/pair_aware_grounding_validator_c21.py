from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Sequence

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
    matched_parent_chunk_count: int
    validation_decision: str

    def as_dict(self) -> dict[str, Any]:
        return self.__dict__.copy()


@dataclass(frozen=True)
class ValidationResult:
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
    shorthand_kind: str | None = None


class PairAwareGroundingValidatorC21:
    """Evaluation-only C2.1 validator with grouped-parent and family context."""

    def validate(
        self,
        response_text: str,
        retrieval_results: Sequence[dict[str, Any]],
    ) -> ValidationResult:
        articles = _retrieval_articles(retrieval_results)
        by_pair: dict[tuple[str, str], list[RetrievalArticle]] = {}
        for article in articles:
            by_pair.setdefault(article.pair, []).append(article)

        traces: list[CitationTrace] = []
        active_law: str | None = None
        active_family: str | None = None
        active_parent_pair: tuple[str, str] | None = None

        for candidate in _parse_candidates(response_text, articles):
            role = "primary_grounding"
            law_name = candidate.law_name

            if candidate.kind == "shorthand":
                law_name = _resolve_family_law(
                    candidate.shorthand_kind,
                    active_family,
                    active_law,
                    articles,
                )
            elif candidate.kind == "bare":
                law_name = active_law

            canonical_law = _canonical_retrieved_law_name(law_name, articles)
            pair = (
                _normalize_law_name(canonical_law or ""),
                candidate.article_number,
            )
            exact_articles = by_pair.get(pair, []) if canonical_law else []
            parent_articles = by_pair.get(active_parent_pair, []) if active_parent_pair else []
            parent_match_count = 0

            if exact_articles:
                decision = "allowed_retrieval_pair"
                canonical_law = exact_articles[0].law_name
                active_law = canonical_law
                active_family = _base_law_name(canonical_law)
                active_parent_pair = exact_articles[0].pair
                parent_pair = None
            else:
                parent_pair = _pair_dict(parent_articles[0]) if parent_articles else None
                if parent_articles and candidate.kind in {"explicit", "shorthand"}:
                    parent_match_count = sum(
                        _parent_contains_reference(parent, candidate, canonical_law or law_name)
                        for parent in parent_articles
                    )
                if parent_match_count:
                    decision = "allowed_parent_cross_reference"
                    role = "dependent_cross_reference"
                else:
                    decision = "rejected_unretrieved_citation"
                    role = (
                        "dependent_cross_reference"
                        if candidate.kind == "shorthand"
                        else "independent_unretrieved"
                    )

            traces.append(
                CitationTrace(
                    raw_citation=candidate.raw,
                    parsed_law_name=canonical_law or law_name,
                    parsed_article_number=candidate.article_number,
                    citation_role=role,
                    parent_retrieval_pair=parent_pair,
                    parent_text_match=bool(parent_match_count),
                    matched_parent_chunk_count=parent_match_count,
                    validation_decision=decision,
                )
            )

        if not traces:
            return ValidationResult(False, "missing_article_citation", tuple())
        if any(trace.validation_decision.startswith("rejected_") for trace in traces):
            return ValidationResult(False, "ungrounded_law_article_pair", tuple(traces))
        return ValidationResult(True, "", tuple(traces))


def collect_retrieval_results(law_tool_trace: Sequence[dict[str, Any]]) -> list[dict[str, Any]]:
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
        if law_name and article_number:
            articles.append(RetrievalArticle(law_name, article_number, str(result.get("text", ""))))
    return articles


def _parse_candidates(text: str, articles: Sequence[RetrievalArticle]) -> list[_Candidate]:
    text = text.replace("**", "").replace("__", "")
    candidates: list[_Candidate] = []

    quoted = re.compile(rf"[「｢]\s*(?P<law>[^」｣]+?)\s*[」｣]{MARKDOWN_GAP}(?P<article>{ARTICLE_PATTERN})")
    for match in quoted.finditer(text):
        candidates.append(_candidate(match, "explicit", match.group("law")))

    known_laws = {article.law_name for article in articles} | {target.name for target in LAW_TARGETS}
    for law_name in sorted(known_laws, key=len, reverse=True):
        pattern = re.compile(rf"(?P<law>{re.escape(law_name)}){MARKDOWN_GAP}(?P<article>{ARTICLE_PATTERN})")
        for match in pattern.finditer(text):
            candidates.append(_candidate(match, "explicit", law_name))

    shorthand = re.compile(
        rf"(?<![가-힣A-Za-z])(?P<prefix>(?:같은\s*)?(?P<kind>시행규칙|시행령|법)){MARKDOWN_GAP}(?P<article>{ARTICLE_PATTERN})"
    )
    for match in shorthand.finditer(text):
        candidates.append(
            _Candidate(
                match.start(),
                match.end(),
                match.group(0),
                "shorthand",
                None,
                _canonical_article(match.group("article")),
                match.group("kind"),
            )
        )

    bare = re.compile(rf"(?P<article>{ARTICLE_PATTERN})")
    for match in bare.finditer(text):
        candidates.append(_candidate(match, "bare", None))

    priority = {"explicit": 0, "shorthand": 1, "bare": 2}
    accepted: list[_Candidate] = []
    for candidate in sorted(candidates, key=lambda c: (c.start, priority[c.kind], -(c.end - c.start))):
        if any(candidate.start < item.end and item.start < candidate.end for item in accepted):
            continue
        accepted.append(candidate)
    return sorted(accepted, key=lambda candidate: candidate.start)


def _candidate(match: re.Match[str], kind: str, law_name: str | None) -> _Candidate:
    return _Candidate(
        match.start(), match.end(), match.group(0), kind, law_name,
        _canonical_article(match.group("article")),
    )


def _resolve_family_law(
    kind: str | None,
    active_family: str | None,
    active_law: str | None,
    articles: Sequence[RetrievalArticle],
) -> str | None:
    if not kind:
        return None
    if kind == "법":
        target = active_family
    elif active_family:
        target = f"{active_family} {kind}"
    elif active_law and active_law.endswith(kind):
        target = active_law
    else:
        matches = {
            article.law_name for article in articles if article.law_name.endswith(kind)
        }
        return next(iter(matches)) if len(matches) == 1 else None
    return _canonical_retrieved_law_name(target, articles) or target


def _parent_contains_reference(
    parent: RetrievalArticle,
    candidate: _Candidate,
    law_name: str | None,
) -> bool:
    article = _article_regex(candidate.article_number)
    if candidate.kind == "shorthand":
        kind = re.escape(candidate.shorthand_kind or "법")
        return bool(re.search(rf"(?:같은\s*)?{kind}\s*{article}", parent.text))
    if candidate.kind == "explicit" and law_name:
        return bool(re.search(rf"[「｢]?\s*{re.escape(law_name)}\s*[」｣]?\s*{article}", parent.text))
    return False


def _canonical_retrieved_law_name(
    law_name: str | None, articles: Sequence[RetrievalArticle]
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


def _pair_dict(article: RetrievalArticle) -> dict[str, str]:
    return {"law_name": article.law_name, "article_number": article.article_number}


def _canonical_article(value: str) -> str:
    match = re.search(ARTICLE_PATTERN, value)
    if not match:
        return ""
    return f"제{int(match.group(1))}조" + (f"의{int(match.group(2))}" if match.group(2) else "")


def _article_regex(article_number: str) -> str:
    match = re.fullmatch(r"제(\d+)조(?:의(\d+))?", article_number)
    if not match:
        return re.escape(article_number)
    suffix = rf"\s*의\s*{match.group(2)}" if match.group(2) else ""
    return rf"제\s*{match.group(1)}\s*조{suffix}"


def _normalize_law_name(value: str) -> str:
    return re.sub(r"[^0-9A-Za-z가-힣]", "", value)

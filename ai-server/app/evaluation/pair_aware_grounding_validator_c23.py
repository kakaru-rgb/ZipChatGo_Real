from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Sequence

from app.evaluation.pair_aware_grounding_validator_c22 import (
    PairAwareGroundingValidatorC22,
)


ARTICLE_PATTERN = re.compile(r"제\s*(\d+)\s*조(?:\s*의\s*(\d+))?")


@dataclass(frozen=True)
class C23ValidationResult:
    passed: bool
    failure_reason: str
    response_role: str
    citations: tuple[dict[str, Any], ...]
    masked_response: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "passed": self.passed,
            "validation_result": "passed" if self.passed else "rejected",
            "failure_reason": self.failure_reason,
            "response_role": self.response_role,
            "citations": list(self.citations),
            "masked_response": self.masked_response,
        }


class PairAwareGroundingValidatorC23:
    """Evaluation-only C2.2 refinement for same-law parent expansions.

    C2.2 remains authoritative except when every rejected citation is a full-law
    expansion of an article reference that actually occurs in an already
    verified parent pair's own retrieval chunks.
    """

    def __init__(self) -> None:
        self._c22 = PairAwareGroundingValidatorC22()

    def validate(
        self,
        response_text: str,
        retrieval_results: Sequence[dict[str, Any]],
    ) -> C23ValidationResult:
        c22 = self._c22.validate(response_text, retrieval_results)
        if c22.passed or c22.failure_reason != "ungrounded_law_article_pair":
            return _from_c22(c22)

        citations = [dict(citation) for citation in c22.citations]
        repaired = 0
        for index, citation in enumerate(citations):
            if not str(citation.get("validation_decision", "")).startswith("rejected_"):
                continue
            replacement = _same_law_parent_expansion(
                citation=citation,
                preceding_citations=citations[:index],
                retrieval_results=retrieval_results,
            )
            if replacement is None:
                return _from_c22(c22)
            citations[index] = replacement
            repaired += 1

        if repaired == 0:
            return _from_c22(c22)

        return C23ValidationResult(
            passed=True,
            failure_reason="",
            response_role="grounded_answer",
            citations=tuple(citations),
            masked_response=c22.masked_response,
        )


def _same_law_parent_expansion(
    *,
    citation: dict[str, Any],
    preceding_citations: Sequence[dict[str, Any]],
    retrieval_results: Sequence[dict[str, Any]],
) -> dict[str, Any] | None:
    law_name = str(citation.get("parsed_law_name", "")).strip()
    article_number = _canonical_article(str(citation.get("parsed_article_number", "")))
    raw_citation = str(citation.get("raw_citation", ""))
    parent = citation.get("parent_retrieval_pair")
    if not law_name or not article_number or not isinstance(parent, dict):
        return None

    parent_law = str(parent.get("law_name", "")).strip()
    parent_article = _canonical_article(str(parent.get("article_number", "")))
    if law_name != parent_law or not parent_article:
        return None
    if not _is_full_law_citation(raw_citation, law_name, article_number):
        return None
    if not _was_parent_pair_verified(preceding_citations, parent_law, parent_article):
        return None

    matching_chunks = [
        item
        for item in retrieval_results
        if str(item.get("law_name", "")).strip() == parent_law
        and _canonical_article(str(item.get("article_number", ""))) == parent_article
    ]
    matched_chunks = [
        item
        for item in matching_chunks
        if _contains_exact_article_reference(str(item.get("text", "")), article_number)
    ]
    if not matched_chunks:
        return None

    replacement = dict(citation)
    replacement.update(
        {
            "citation_role": "dependent_parent_cross_reference",
            "parent_retrieval_pair": {
                "law_name": parent_law,
                "article_number": parent_article,
            },
            "parent_text_match": True,
            "matched_parent_chunk_count": len(matched_chunks),
            "validation_decision": "allowed_same_law_parent_cross_reference",
        }
    )
    return replacement


def _was_parent_pair_verified(
    citations: Sequence[dict[str, Any]],
    law_name: str,
    article_number: str,
) -> bool:
    return any(
        str(citation.get("validation_decision", "")) == "allowed_retrieval_pair"
        and str(citation.get("parsed_law_name", "")).strip() == law_name
        and _canonical_article(str(citation.get("parsed_article_number", "")))
        == article_number
        for citation in citations
    )


def _is_full_law_citation(raw: str, law_name: str, article_number: str) -> bool:
    cleaned = raw.replace("**", "").replace("__", "").replace("`", "")
    law_pattern = re.escape(law_name)
    article_pattern = _article_reference_regex(article_number)
    return bool(
        re.fullmatch(
            rf"\s*[「｢]?\s*{law_pattern}\s*[」｣]?\s*{article_pattern}\s*",
            cleaned,
        )
    )


def _contains_exact_article_reference(text: str, article_number: str) -> bool:
    return bool(re.search(_article_reference_regex(article_number), text))


def _article_reference_regex(article_number: str) -> str:
    match = re.fullmatch(r"제(\d+)조(?:의(\d+))?", article_number)
    if match is None:
        return re.escape(article_number)
    suffix = rf"\s*의\s*{match.group(2)}" if match.group(2) else r"(?!\s*의\s*\d)"
    return rf"제\s*{match.group(1)}\s*조{suffix}(?!\d)"


def _canonical_article(value: str) -> str:
    match = ARTICLE_PATTERN.search(value)
    if match is None:
        return ""
    article = f"제{int(match.group(1))}조"
    return article + (f"의{int(match.group(2))}" if match.group(2) else "")


def _from_c22(c22: Any) -> C23ValidationResult:
    return C23ValidationResult(
        passed=c22.passed,
        failure_reason=c22.failure_reason,
        response_role=c22.response_role,
        citations=tuple(dict(citation) for citation in c22.citations),
        masked_response=c22.masked_response,
    )

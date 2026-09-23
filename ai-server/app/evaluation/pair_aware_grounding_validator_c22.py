from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Sequence

from app.evaluation.pair_aware_grounding_validator_c21 import (
    PairAwareGroundingValidatorC21,
)


ARTICLE_PATTERN = re.compile(r"제\s*(\d+)\s*조(?:\s*의\s*(\d+))?")
SENTENCE_BOUNDARY = re.compile(r"[.!?。！？\n]")

UNAVAILABLE_PATTERNS = (
    re.compile(r"검색.{0,45}(?:없|못\s*찾|확인되지|포함되지)"),
    re.compile(r"(?:본문|조문|근거).{0,35}(?:없|확인되지|검색되지|찾지\s*못)"),
    re.compile(r"(?:확인|검색|찾)하지\s*못"),
    re.compile(r"근거로\s*(?:사용|인용)할\s*수\s*없"),
)

INSUFFICIENT_EVIDENCE_PATTERNS = (
    re.compile(r"(?:판단|안내)하기\s*(?:에는\s*)?(?:어렵|부족)"),
    re.compile(r"(?:단정|확정)할\s*수\s*없"),
    re.compile(r"(?:법적\s*)?근거가\s*부족"),
    re.compile(r"검색\s*결과.{0,30}(?:관련\s*없|충분하지\s*않|찾지\s*못)"),
    re.compile(r"(?:자료|정보|사실관계)가\s*(?:부족|필요)"),
    re.compile(r"(?:판례|원문)을\s*(?:조회|확인)할\s*수\s*없"),
)

FOLLOW_UP_PATTERNS = (
    re.compile(r"(?:계약서|조항|원문|자료|사실관계).{0,35}필요"),
    re.compile(r"(?:확인|검토|문의)(?:해야|이\s*필요|하시|해\s*주)"),
    re.compile(r"(?:보내|알려)\s*주시면"),
    re.compile(r"(?:변호사|법무사|전문가|공식\s*기관|법원).{0,35}(?:확인|검토|문의)"),
)

# This intentionally recognizes only conspicuous legal conclusions. If a
# response does not clearly satisfy the narrow abstention rule, C2.1 remains
# authoritative and rejects citation-free output.
DEFINITIVE_LEGAL_PATTERNS = (
    re.compile(r"(?:계약|약정|조항)(?:은|는|이|가)?.{0,15}(?:무효|유효)(?:입니다|이다|다|로\s*봅니다)"),
    re.compile(r"(?:임대인|임차인|매도인|매수인).{0,30}(?:해야\s*합니다|하여야\s*합니다|책임을\s*집니다)"),
    re.compile(r"반드시.{0,40}(?:합니다|해야|된다|됩니다|입니다)"),
    re.compile(r"(?:신고)?기한(?:은|이|는)?.{0,15}\d+\s*(?:일|개월|년)(?:입니다|이다|다)?"),
    re.compile(r"(?:효력|권리|의무|책임).{0,30}(?:발생|인정|부담|존재|없습니다|있습니다|집니다)"),
    re.compile(r"(?:손해배상|과태료|벌금|과징금).{0,30}(?:해야|부과|책임|입니다|된다|됩니다)"),
    re.compile(r"(?:취소|해제|해지)(?:할\s*수\s*있습니다|됩니다|됩니다)"),
)


@dataclass(frozen=True)
class NegativeReferenceTrace:
    raw_citation: str
    parsed_article_number: str
    citation_role: str
    local_sentence: str
    validation_decision: str

    def as_dict(self) -> dict[str, Any]:
        return self.__dict__.copy()


@dataclass(frozen=True)
class C22ValidationResult:
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


class PairAwareGroundingValidatorC22:
    """Evaluation-only narrow semantic guard layered in front of C2.1."""

    def __init__(self) -> None:
        self._c21 = PairAwareGroundingValidatorC21()

    def validate(
        self,
        response_text: str,
        retrieval_results: Sequence[dict[str, Any]],
    ) -> C22ValidationResult:
        masked, negative_references = _mask_negative_references(response_text)
        c21_result = self._c21.validate(masked, retrieval_results)
        c21_citations = tuple(citation.as_dict() for citation in c21_result.citations)
        negative_citations = tuple(trace.as_dict() for trace in negative_references)

        if c21_result.passed:
            return C22ValidationResult(
                True,
                "",
                "grounded_answer",
                c21_citations + negative_citations,
                masked,
            )

        if (
            c21_result.failure_reason == "missing_article_citation"
            and _is_narrow_safe_abstention(response_text)
        ):
            return C22ValidationResult(
                True,
                "",
                "abstention_without_citation",
                negative_citations,
                masked,
            )

        return C22ValidationResult(
            False,
            c21_result.failure_reason,
            "rejected_by_c21",
            c21_citations + negative_citations,
            masked,
        )


def _mask_negative_references(
    response_text: str,
) -> tuple[str, tuple[NegativeReferenceTrace, ...]]:
    characters = list(response_text)
    traces: list[NegativeReferenceTrace] = []
    matches = list(ARTICLE_PATTERN.finditer(response_text))

    for match in matches:
        start, end = _sentence_span(response_text, match.start(), match.end())
        sentence = response_text[start:end].strip()
        article_number = _canonical_article(match)
        same_article_count = sum(
            _canonical_article(candidate) == article_number
            for candidate in ARTICLE_PATTERN.finditer(sentence)
        )
        clearly_unavailable = any(pattern.search(sentence) for pattern in UNAVAILABLE_PATTERNS)
        has_definitive_claim = _contains_definitive_legal_claim(sentence)
        if not clearly_unavailable or same_article_count != 1 or has_definitive_claim:
            continue

        for index in range(match.start(), match.end()):
            characters[index] = " "
        traces.append(
            NegativeReferenceTrace(
                raw_citation=match.group(0),
                parsed_article_number=article_number,
                citation_role="negative_or_unavailable_reference",
                local_sentence=sentence,
                validation_decision="excluded_from_grounding_not_evidence",
            )
        )

    return "".join(characters), tuple(traces)


def _is_narrow_safe_abstention(response_text: str) -> bool:
    if not any(pattern.search(response_text) for pattern in INSUFFICIENT_EVIDENCE_PATTERNS):
        return False
    if not any(pattern.search(response_text) for pattern in FOLLOW_UP_PATTERNS):
        return False
    if _contains_definitive_legal_claim(response_text):
        return False
    return True


def _contains_definitive_legal_claim(text: str) -> bool:
    return any(pattern.search(text) for pattern in DEFINITIVE_LEGAL_PATTERNS)


def _sentence_span(text: str, match_start: int, match_end: int) -> tuple[int, int]:
    start = 0
    for boundary in SENTENCE_BOUNDARY.finditer(text, 0, match_start):
        start = boundary.end()
    next_boundary = SENTENCE_BOUNDARY.search(text, match_end)
    end = next_boundary.start() if next_boundary else len(text)
    return start, end


def _canonical_article(match: re.Match[str]) -> str:
    base = f"제{int(match.group(1))}조"
    return base + (f"의{int(match.group(2))}" if match.group(2) else "")

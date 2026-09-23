from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Sequence


LAW_ALIASES = {
    "공인중개사법령": "공인중개사법",
    "공인중개사법": "공인중개사법",
    "부동산거래신고등에관한법령": "부동산 거래신고 등에 관한 법률",
    "부동산거래신고등에관한법률": "부동산 거래신고 등에 관한 법률",
    "주택임대차보호법": "주택임대차보호법",
    "민사집행법": "민사집행법",
    "장사등에관한법령": "장사 등에 관한 법률",
    "장사등에관한법률": "장사 등에 관한 법률",
    "부동산실권리자명의등기에관한법률": "부동산 실권리자명의 등기에 관한 법률",
}


@dataclass(frozen=True)
class RequiredLawCoverageResult:
    passed: bool
    applicable: bool
    failure_reason: str
    required_laws: tuple[str, ...]
    matched_retrieved_laws: tuple[str, ...]
    detection_source: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "passed": self.passed,
            "applicable": self.applicable,
            "validation_result": "passed" if self.passed else "rejected",
            "failure_reason": self.failure_reason,
            "required_laws": list(self.required_laws),
            "matched_retrieved_laws": list(self.matched_retrieved_laws),
            "detection_source": self.detection_source,
        }


class RequiredLawCoverageGate:
    """Evaluation-only gate; it observes retrieval coverage after Agent execution."""

    def validate(
        self,
        problem_stem: str,
        retrieval_results: Sequence[dict[str, Any]],
        *,
        reviewed_required_laws: Sequence[str] | None = None,
    ) -> RequiredLawCoverageResult:
        if reviewed_required_laws:
            required = tuple(_canonical_law_name(name) for name in reviewed_required_laws)
            source = "human_reviewed_annotation"
        else:
            required = tuple(_detect_stem_governing_laws(problem_stem))
            source = "explicit_stem" if required else "not_detected"

        if not required:
            return RequiredLawCoverageResult(True, False, "", tuple(), tuple(), source)

        retrieved = {
            str(result.get("law_name", "")).strip()
            for result in retrieval_results
            if str(result.get("law_name", "")).strip()
        }
        matched = sorted(
            law for law in retrieved
            if any(_same_law_family(law, required_law) for required_law in required)
        )
        if matched:
            return RequiredLawCoverageResult(True, True, "", required, tuple(matched), source)
        return RequiredLawCoverageResult(
            False,
            True,
            "required_law_not_retrieved",
            required,
            tuple(),
            source,
        )


def _detect_stem_governing_laws(stem: str) -> list[str]:
    # Only inspect the governing-law clause before the question body/choices. A law
    # merely mentioned in a factual option is intentionally not promoted to required.
    governing_text = re.split(r"\[?선택지\]?|①|1\.", stem, maxsplit=1)[0]
    compact = _normalize(governing_text)
    detections: list[str] = []
    for alias, canonical in sorted(LAW_ALIASES.items(), key=lambda item: len(item[0]), reverse=True):
        position = compact.find(alias)
        if position < 0:
            continue
        tail = compact[position + len(alias):position + len(alias) + 12]
        if position <= 120 and re.match(r"(?:상|에따른|에관하여|에관한)", tail):
            detections.append(canonical)
    return list(dict.fromkeys(detections))


def _canonical_law_name(value: str) -> str:
    normalized = _normalize(value)
    return LAW_ALIASES.get(normalized, value.strip())


def _same_law_family(retrieved: str, required: str) -> bool:
    retrieved_base = re.sub(r"(?:시행령|시행규칙)$", "", _normalize(retrieved))
    required_base = re.sub(r"(?:시행령|시행규칙)$", "", _normalize(required))
    return bool(retrieved_base and retrieved_base == required_base)


def _normalize(value: str) -> str:
    return re.sub(r"[^0-9A-Za-z가-힣]", "", value)

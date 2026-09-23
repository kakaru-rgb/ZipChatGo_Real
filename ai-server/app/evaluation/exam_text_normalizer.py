from __future__ import annotations

import re
from functools import lru_cache

from kiwipiepy import Kiwi


_COMBINATION_LABEL = re.compile(r"(?<![가-힣])([ㄱ-ㅎ])\s*:\s*")
_COMBINATION_ASSIGNMENT = re.compile(r"([ㄱ-ㅎ])\s*=\s*")
_NUMBER_UNIT = re.compile(
    r"(?<=\d)\s+(?=(?:개층|제곱미터|억원|만원|천원|원|층|개|년|개월|월|일|%|㎡|m²)\b)"
)

_REAL_ESTATE_TERMS = (
    "광역시장",
    "공공임대주택",
    "공공주택",
    "공공주택특별법령",
    "공인중개사법령",
    "도시개발",
    "도시개발구역",
    "도시개발법령",
    "도시개발사업",
    "도시개발사업조합",
    "민간투자사업",
    "민사특별법",
    "부동산개발",
    "부동산개발업",
    "부동산공법",
    "부동산공시법령",
    "부동산세법",
    "부동산학개론",
    "사업시행자",
    "사업위탁방식",
    "신탁개발방식",
    "장기전세주택",
    "정착물",
    "주택도시기금",
    "주택도시기금법",
    "중개실무",
    "지방공사",
    "지적공부",
    "지가공시제도",
    "통합공공임대주택",
    "토지소유권",
    "행복주택",
    "환지방식",
    "수용방식",
    "분양전환공공임대주택",
    "다세대주택",
    "지하주차장",
    "건축면적",
    "바닥면적",
    "대지면적",
    "대토",
)


@lru_cache(maxsize=1)
def _kiwi() -> Kiwi:
    kiwi = Kiwi()
    for term in _REAL_ESTATE_TERMS:
        kiwi.add_user_word(term, "NNP", score=5.0)
    return kiwi


def normalize_exam_text(value: str) -> str:
    """Restore Korean spacing without using an LLM and stabilize exam notation."""
    if not value.strip():
        return ""
    normalized = _kiwi().space(value, reset_whitespace=True)
    normalized = _normalize_common_notation(normalized)
    normalized = re.sub(r"\s*○\s*", "\n○ ", normalized).strip()
    normalized = re.sub(r"\s+([,.;:?!])", r"\1", normalized)
    normalized = re.sub(r"[ \t]+", " ", normalized)
    return normalized.strip()


def normalize_exam_choice(value: str) -> str:
    normalized = normalize_exam_text(value)
    normalized = _COMBINATION_LABEL.sub(r"\1 = ", normalized)
    normalized = re.sub(r",\s*(?=[ㄱ-ㅎ]\s*=)", "; ", normalized)
    normalized = re.sub(r"\s*=\s*", " = ", normalized)
    return normalized.strip()


def is_combination_question(question: str, choices: list[str]) -> bool:
    labels = set(re.findall(r"[ㄱ-ㅎ]", question))
    assigned = {
        label
        for choice in choices
        for label in _COMBINATION_ASSIGNMENT.findall(choice)
    }
    return len(labels) >= 2 or len(assigned) >= 2


def _normalize_common_notation(value: str) -> str:
    value = re.sub(r"\(\s*([ㄱ-ㅎ])\s*\)", r"(\1)", value)
    value = re.sub(r"\s*·\s*", "·", value)
    value = _NUMBER_UNIT.sub("", value)
    value = re.sub(r"([｢『])\s+", r"\1", value)
    value = re.sub(r"\s+([｣』])", r"\1", value)
    value = re.sub(r"(?<=법령)\s+상\b", "상", value)
    value = re.sub(r"\b([A-Z])\s+(?=(?:광역시장|임차인|임대인|부동산))", r"\1", value)
    return value

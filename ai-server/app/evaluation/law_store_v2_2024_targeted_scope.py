from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from app.evaluation.canonical_law_catalog import CanonicalLawCatalog


TARGET_QUESTION_IDS = (6, 9, 16, 21, 27, 36, 37, 38)


class V2ScopeLabel(StrEnum):
    IN_SCOPE = "v2_in_scope"
    PARTIAL = "v2_partial"
    OUT_OF_SCOPE = "v2_out_of_scope"
    UNCERTAIN = "v2_scope_uncertain"


@dataclass(frozen=True)
class TargetScopeRequirement:
    """Human-reviewed, post-run scope evidence; never an Agent input."""

    question_id: int
    required_pairs: tuple[tuple[str, str], ...]
    required_non_article_sources: tuple[str, ...] = ()
    rationale: str = ""


@dataclass(frozen=True)
class TargetScopeAssessment:
    question_id: int
    label: V2ScopeLabel
    required_pairs: tuple[tuple[str, str], ...]
    missing_pairs: tuple[tuple[str, str], ...]
    required_non_article_sources: tuple[str, ...]
    rationale: str


TARGET_SCOPE_REQUIREMENTS = (
    TargetScopeRequirement(
        6,
        (
            ("공인중개사법", "제7조"),
            ("공인중개사법", "제18조의4"),
            ("공인중개사법", "제30조"),
            ("공인중개사법", "제33조"),
        ),
        rationale="거래질서 교란 여부를 구별하는 관련 법 조문이 article corpus에 있다.",
    ),
    TargetScopeRequirement(
        9,
        (
            ("공인중개사법", "제10조"),
            ("공인중개사법 시행규칙", "제4조"),
            ("공인중개사법 시행규칙", "제5조"),
            ("공인중개사법 시행규칙", "제6조"),
        ),
        rationale="개설등록 결격·신청·통지·등록증 관련 핵심 조문이 있다.",
    ),
    TargetScopeRequirement(
        16,
        (("공인중개사법", "제39조"),),
        ("공인중개사법 시행규칙 별표 2의 업무정지 개별기준",),
        "상위법 조문은 있으나 정답을 가르는 6개월 개별기준 별표는 article metadata에 없다.",
    ),
    TargetScopeRequirement(
        21,
        (
            ("공인중개사법", "제41조"),
            ("공인중개사법 시행령", "제31조"),
        ),
        rationale="협회 설립 및 협회 업무의 열거 조문이 있다.",
    ),
    TargetScopeRequirement(
        27,
        (
            ("부동산 거래신고 등에 관한 법률", "제14조"),
            ("부동산 거래신고 등에 관한 법률 시행령", "제11조"),
        ),
        rationale="토지거래허가 특례와 적용 제외 행위를 열거하는 법·시행령 조문이 있다.",
    ),
    TargetScopeRequirement(
        36,
        (("부동산 실권리자명의 등기에 관한 법률", "제4조"),),
        ("명의신탁 부동산 임대차 및 진정명의회복 관련 판례",),
        "명의신탁 효력 조문은 추가됐지만 문항이 명시적으로 요구하는 판례 source는 없다.",
    ),
    TargetScopeRequirement(
        37,
        (
            ("주택임대차보호법", "제6조의2"),
            ("주택임대차보호법", "제6조의3"),
        ),
        rationale="계약갱신요구권과 갱신 후 해지에 필요한 두 조문이 모두 있다.",
    ),
    TargetScopeRequirement(
        38,
        (
            ("상가건물 임대차보호법", "제3조"),
            ("상가건물 임대차보호법", "제4조"),
            ("상가건물 임대차보호법", "제5조"),
            ("상가건물 임대차보호법", "제10조"),
        ),
        rationale="대항력·확정일자/정보제공·우선변제·갱신거절 핵심 조문이 있다.",
    ),
)


def classify_target_scopes(
    catalog: CanonicalLawCatalog,
) -> tuple[TargetScopeAssessment, ...]:
    assessments: list[TargetScopeAssessment] = []
    for requirement in TARGET_SCOPE_REQUIREMENTS:
        missing = tuple(
            pair for pair in requirement.required_pairs if not catalog.contains_pair(*pair)
        )
        if missing:
            label = V2ScopeLabel.OUT_OF_SCOPE
        elif requirement.required_non_article_sources:
            label = V2ScopeLabel.PARTIAL
        else:
            label = V2ScopeLabel.IN_SCOPE
        assessments.append(
            TargetScopeAssessment(
                question_id=requirement.question_id,
                label=label,
                required_pairs=requirement.required_pairs,
                missing_pairs=missing,
                required_non_article_sources=requirement.required_non_article_sources,
                rationale=requirement.rationale,
            )
        )
    return tuple(assessments)

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime

from app.evaluation.realtor_exam import ExamQuestion
from app.law.targets import LAW_TARGETS


@dataclass(frozen=True)
class CorpusScopeResult:
    corpus_scope: str
    basis_laws: tuple[str, ...]
    reason: str
    temporal_risk: str
    temporal_risk_reason: str


_CORPUS_FAMILIES = (
    (("공인중개사법", "공인중개사법령"), (
        "공인중개사법", "공인중개사법 시행령", "공인중개사법 시행규칙",
    )),
    (("부동산거래신고등에관한법률", "부동산거래신고등에관한법령"), (
        "부동산 거래신고 등에 관한 법률",
        "부동산 거래신고 등에 관한 법률 시행령",
        "부동산 거래신고 등에 관한 법률 시행규칙",
    )),
    (("주택임대차보호법",), ("주택임대차보호법", "주택임대차보호법 시행령")),
    (("상가건물임대차보호법",), (
        "상가건물 임대차보호법", "상가건물 임대차보호법 시행령",
    )),
    (("집합건물의소유및관리에관한법률", "집합건물법"), (
        "집합건물의 소유 및 관리에 관한 법률",
        "집합건물의 소유 및 관리에 관한 법률 시행령",
    )),
    (("부동산등기법", "부동산등기규칙"), ("부동산등기법", "부동산등기규칙")),
    (("민법",), ("민법",)),
)

_OUT_OF_SCOPE_CORE_MARKERS = (
    "민사집행법",
    "공인중개사의매수신청대리인등록등에관한규칙",
    "장사등에관한법령",
    "장사등에관한법률",
    "분묘기지권",
    "부동산실권리자명의등기에관한법률",
)

_PARTIAL_SCOPE_TOPICS = (
    "건물매수청구권",
    "지상건물에대한매수청구권",
    "저당권이설정되어있는",
)

_OUT_OF_SCOPE_CIVIL_TOPICS = (
    "공유로취득",
    "명의신탁",
)


def classify_corpus_scope(question: ExamQuestion) -> CorpusScopeResult:
    stem = _normalize(question.question)
    detected = _detect_corpus_family(stem)
    has_case_law = "판례" in stem or "다툼이있으면" in stem

    # The stem's governing law takes priority. Incidental laws in choices must
    # not move the whole question out of scope.
    if detected:
        if has_case_law:
            scope = "partial_scope"
            reason = "핵심 법령은 Vector Store에 있으나 문제에서 판례 판단도 요구함"
        else:
            scope = "in_scope"
            reason = "문제 stem의 핵심 근거 법령이 현재 Vector Store 대상에 포함됨"
    elif any(marker in stem for marker in _OUT_OF_SCOPE_CORE_MARKERS):
        scope = "out_of_scope"
        reason = "문제 stem의 핵심 법령 또는 판례 주제가 현재 Vector Store 대상에 없음"
    elif any(marker in stem for marker in _OUT_OF_SCOPE_CIVIL_TOPICS):
        scope = "out_of_scope"
        reason = "핵심 민법 쟁점이 현재 Vector Store의 제한된 민법 조문 범위 밖임"
    elif any(marker in stem for marker in _PARTIAL_SCOPE_TOPICS):
        scope = "partial_scope"
        detected = ("민법",) if "매수청구권" in stem else ("주택임대차보호법",)
        reason = "관련 법률 조문은 일부 포함되지만 판례 또는 외부 절차법이 추가로 필요함"
    else:
        scope = "out_of_scope"
        reason = "문제의 근거 법령을 현재 Vector Store 대상 법령으로 확인할 수 없음"

    current_year = datetime.now().year
    if question.year < current_year:
        temporal_risk = "review_required"
        temporal_reason = (
            f"{question.year}년 시험 정답과 {current_year}년 현행 Vector Store 법령 사이의 "
            "개정 영향은 별도 역사 법령 대조 없이는 확정할 수 없음"
        )
    else:
        temporal_risk = "not_flagged"
        temporal_reason = "시험 연도와 현재 연도 차이로 인한 자동 경고 없음"

    return CorpusScopeResult(
        corpus_scope=scope,
        basis_laws=detected,
        reason=reason,
        temporal_risk=temporal_risk,
        temporal_risk_reason=temporal_reason,
    )


def _normalize(value: str) -> str:
    return re.sub(r"[^0-9A-Za-z가-힣]", "", value)


def _detect_corpus_family(stem: str) -> tuple[str, ...]:
    for aliases, law_names in _CORPUS_FAMILIES:
        if any(alias in stem for alias in aliases):
            available = {target.name for target in LAW_TARGETS}
            return tuple(name for name in law_names if name in available)
    return ()

from __future__ import annotations

import json
import re
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

from app.evaluation.exam_text_normalizer import is_combination_question
from app.evaluation.realtor_exam import ExamQuestion


@dataclass(frozen=True)
class LawFamily:
    aliases: tuple[str, ...]
    law_names: tuple[str, ...]


LAW_FAMILIES = (
    LawFamily(
        aliases=("공인중개사법령", "공인중개사법"),
        law_names=(
            "공인중개사법",
            "공인중개사법 시행령",
            "공인중개사법 시행규칙",
        ),
    ),
    LawFamily(
        aliases=("부동산거래신고등에관한법령", "부동산거래신고등에관한법률"),
        law_names=(
            "부동산 거래신고 등에 관한 법률",
            "부동산 거래신고 등에 관한 법률 시행령",
            "부동산 거래신고 등에 관한 법률 시행규칙",
        ),
    ),
    LawFamily(
        aliases=("주택임대차보호법",),
        law_names=("주택임대차보호법", "주택임대차보호법 시행령"),
    ),
    LawFamily(
        aliases=("상가건물임대차보호법",),
        law_names=("상가건물 임대차보호법", "상가건물 임대차보호법 시행령"),
    ),
    LawFamily(
        aliases=("집합건물의소유및관리에관한법률", "집합건물법"),
        law_names=(
            "집합건물의 소유 및 관리에 관한 법률",
            "집합건물의 소유 및 관리에 관한 법률 시행령",
        ),
    ),
    LawFamily(
        aliases=("부동산등기법", "부동산등기규칙"),
        law_names=("부동산등기법", "부동산등기규칙"),
    ),
    LawFamily(aliases=("민법",), law_names=("민법",)),
)

MAX_EVIDENCE_PER_TARGET = 2
MAX_EVIDENCE_PER_QUESTION = 8
_LABELED_STATEMENT = re.compile(
    r"(?<![가-힣])([ㄱ-ㅎ])\s*[.:]\s*(.*?)"
    r"(?=(?<![가-힣])[ㄱ-ㅎ]\s*[.:]|$)",
    re.DOTALL,
)


def detect_law_names(question: ExamQuestion) -> list[str]:
    explicit_text = _normalize(
        " ".join([question.question, *question.choices])
    )
    detected = _detect_in_text(explicit_text)
    if detected:
        return detected

    # A broad "법령 및 중개실무" subject can contain civil-law and case-law
    # questions, so it must not force the public-realtor-law family by itself.
    normalized_subject = _normalize(question.subject)
    if "및중개실무" in normalized_subject:
        return []
    return _detect_in_text(normalized_subject)


def build_choice_search_query(
    question: ExamQuestion,
    choice_number: int,
    law_names: Sequence[str],
) -> str:
    choice = question.choices[choice_number - 1]
    law_hint = " ".join(law_names)
    issue = _question_issue(question.question)
    query = f"{law_hint} {choice} 쟁점: {issue}"
    return re.sub(r"\s+", " ", query).strip()[:400]


def build_evidence_search_targets(
    question: ExamQuestion,
    law_names: Sequence[str],
) -> list[dict[str, Any]]:
    statements = extract_labeled_statements(question.question)
    if is_combination_question(question.question, question.choices) and len(statements) >= 2:
        law_hint = " ".join(law_names)
        issue = _question_issue(question.question)
        return [
            {
                "target_id": f"I{label}",
                "target_type": "item",
                "item_label": label,
                "statement": statement,
                "query": re.sub(
                    r"\s+",
                    " ",
                    f"{law_hint} {statement} 쟁점: {issue}",
                ).strip()[:400],
            }
            for label, statement in statements
        ]

    return [
        {
            "target_id": f"C{choice_number}",
            "target_type": "choice",
            "choice_number": choice_number,
            "statement": question.choices[choice_number - 1],
            "query": build_choice_search_query(question, choice_number, law_names),
        }
        for choice_number in range(1, 6)
    ]


def extract_labeled_statements(question: str) -> list[tuple[str, str]]:
    statements = []
    for match in _LABELED_STATEMENT.finditer(question):
        statement = re.sub(r"\s+", " ", match.group(2)).strip()
        if statement:
            statements.append((match.group(1), statement))
    return statements


def render_choice_evidence(choice_searches: Sequence[dict[str, Any]]) -> str:
    return (
        "시험 전용 법령 검색 결과입니다. search_targets는 검색한 선택지 또는 "
        "ㄱ·ㄴ·ㄷ 지문이고, evidence는 중복 제거한 고유 근거입니다. "
        "각 target의 evidence_ids를 우선 사용하되 다른 target에 연결된 근거도 "
        "내용이 직접 관련되면 사용할 수 있습니다. 근거에 없는 내용은 만들지 말고, "
        "사용한 E번호를 최종 응답의 evidence_ids에 기록하세요.\n"
        + json.dumps(
            list(choice_searches),
            ensure_ascii=False,
            separators=(",", ":"),
        )
    )


def _detect_in_text(normalized_text: str) -> list[str]:
    names: list[str] = []
    for family in LAW_FAMILIES:
        if any(alias in normalized_text for alias in family.aliases):
            names.extend(family.law_names)
    return list(dict.fromkeys(names))


def _normalize(value: str) -> str:
    return re.sub(r"[^0-9A-Za-z가-힣]", "", value)


def _question_issue(question: str) -> str:
    first_statement = _LABELED_STATEMENT.search(question)
    issue = question[: first_statement.start()] if first_statement else question
    issue = re.sub(
        r"(?:옳은|옳지\s*않은|틀린|맞는|아닌|해당하지\s*않는|"
        r"할\s*수\s*없는)\s*(?:것|업무)?(?:을|를|은|는)?\s*"
        r"(?:모두\s*)?(?:고른|고르는)?\s*것(?:은|인가)?\??",
        "",
        issue,
    )
    return re.sub(r"\s+", " ", issue).strip()[:180]

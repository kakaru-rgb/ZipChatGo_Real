from app.evaluation.exam_law_grounding import (
    build_choice_search_query,
    build_evidence_search_targets,
    detect_law_names,
    extract_labeled_statements,
)
from app.evaluation.realtor_exam import ExamQuestion


def _question(question: str, subject: str = "공인중개사법령 및 중개실무"):
    return ExamQuestion(
        year=2024,
        paper_id="2차_1교시",
        paper_name="2024 문제지",
        subject=subject,
        question_no=1,
        question=question,
        choices=["선택 A", "선택 B", "선택 C", "선택 D", "선택 E"],
        correct_answer=1,
        source_pdf="exam.pdf",
    )


def test_detects_explicit_law_family_without_broad_subject_pollution() -> None:
    question = _question("주택임대차보호법상 계약갱신요구권에 관한 설명은?")

    assert detect_law_names(question) == [
        "주택임대차보호법",
        "주택임대차보호법 시행령",
    ]


def test_broad_brokerage_subject_does_not_guess_law_for_case_question() -> None:
    question = _question("분묘기지권에 관한 판례의 설명으로 옳은 것은?")

    assert detect_law_names(question) == []


def test_choice_query_places_choice_before_question_and_stays_within_limit() -> None:
    question = _question("공인중개사법령상 휴업 신고에 관한 설명은?" * 30)

    query = build_choice_search_query(
        question,
        3,
        ["공인중개사법", "공인중개사법 시행령", "공인중개사법 시행규칙"],
    )

    assert "선택 C" in query
    assert query.index("선택 C") < query.index("쟁점:")
    assert len(query) <= 400


def test_combination_question_searches_each_labeled_statement_once() -> None:
    question = _question(
        "옳은 것을 모두 고른 것은? ㄱ. 등록관청에 신고한다. "
        "ㄴ. 국토교통부장관의 승인을 받는다. ㄷ. 서면으로 통지한다."
    ).model_copy(update={"choices": ["ㄱ", "ㄴ", "ㄷ", "ㄱ, ㄷ", "ㄴ, ㄷ"]})

    statements = extract_labeled_statements(question.question)
    targets = build_evidence_search_targets(question, ["공인중개사법"])

    assert [label for label, _ in statements] == ["ㄱ", "ㄴ", "ㄷ"]
    assert [target["target_id"] for target in targets] == ["Iㄱ", "Iㄴ", "Iㄷ"]
    assert all(target["target_type"] == "item" for target in targets)

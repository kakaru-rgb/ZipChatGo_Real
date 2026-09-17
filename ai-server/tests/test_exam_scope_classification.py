from app.evaluation.exam_scope_classification import classify_corpus_scope
from app.evaluation.realtor_exam import ExamQuestion


def _question(stem: str, choices: list[str] | None = None) -> ExamQuestion:
    return ExamQuestion(
        year=2024,
        paper_id="2차_1교시",
        paper_name="test",
        subject="공인중개사법령 및 중개실무",
        question_no=1,
        question=stem,
        choices=choices or ["1", "2", "3", "4", "5"],
        correct_answer=1,
        source_pdf="test.pdf",
    )


def test_transaction_reporting_law_wording_is_in_scope() -> None:
    result = classify_corpus_scope(
        _question("부동산 거래 신고 등에 관한 법령상 신고 대상이 아닌 것은?")
    )
    assert result.corpus_scope == "in_scope"
    assert "부동산 거래신고 등에 관한 법률" in result.basis_laws


def test_incidental_choice_law_does_not_change_stem_scope() -> None:
    result = classify_corpus_scope(
        _question(
            "부동산 거래 신고 등에 관한 법령상 옳은 것은?",
            ["주택법에 따른 경우", "2", "3", "4", "5"],
        )
    )
    assert result.corpus_scope == "in_scope"


def test_corpus_law_with_case_law_is_partial_scope() -> None:
    result = classify_corpus_scope(
        _question("주택임대차보호법상 옳은 것은? 다툼이 있으면 판례에 따름")
    )
    assert result.corpus_scope == "partial_scope"


def test_missing_core_law_is_out_of_scope() -> None:
    result = classify_corpus_scope(_question("장사 등에 관한 법령상 옳은 것은?"))
    assert result.corpus_scope == "out_of_scope"

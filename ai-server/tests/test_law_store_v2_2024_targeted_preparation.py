from __future__ import annotations

from app.evaluation.canonical_law_catalog import CanonicalLawCatalog
from app.evaluation.law_store_v2_2024_targeted_scope import (
    TARGET_QUESTION_IDS,
    TARGET_SCOPE_REQUIREMENTS,
    V2ScopeLabel,
    classify_target_scopes,
)
from app.evaluation.production_agent_passthrough import LoadedQuestion, build_user_message
from app.evaluation.realtor_exam import ExamQuestion
from scripts.evaluate_law_store_v2_c23_luna_2024_targeted import (
    SUBJECT,
    select_target_questions,
)


def _catalog() -> CanonicalLawCatalog:
    records = [
        {"law_name": law, "article_number": article}
        for requirement in TARGET_SCOPE_REQUIREMENTS
        for law, article in requirement.required_pairs
    ]
    return CanonicalLawCatalog.from_records(records, corpus_version="law_store_v2-test")


def _question(number: int, answer: int = 3) -> ExamQuestion:
    return ExamQuestion(
        year=2024,
        paper_id="2차_1교시",
        paper_name="reviewed.csv",
        subject=SUBJECT,
        question_no=number,
        question=f"{number}번 원문",
        choices=[f"선택지 {index}" for index in range(1, 6)],
        correct_answer=answer,
        accepted_answers=[answer],
        source_pdf="source.pdf",
        source_page=1,
    )


def test_scope_classification_uses_non_article_sources_for_partial() -> None:
    by_id = {item.question_id: item for item in classify_target_scopes(_catalog())}

    assert by_id[16].label is V2ScopeLabel.PARTIAL
    assert by_id[36].label is V2ScopeLabel.PARTIAL
    assert all(
        by_id[number].label is V2ScopeLabel.IN_SCOPE
        for number in (6, 9, 21, 27, 37, 38)
    )


def test_missing_required_article_is_out_of_scope() -> None:
    requirement = TARGET_SCOPE_REQUIREMENTS[0]
    records = [
        {"law_name": law, "article_number": article}
        for law, article in requirement.required_pairs[:-1]
    ]
    catalog = CanonicalLawCatalog.from_records(records)

    result = classify_target_scopes(catalog)[0]

    assert result.label is V2ScopeLabel.OUT_OF_SCOPE
    assert result.missing_pairs == (requirement.required_pairs[-1],)


def test_target_selection_is_exact_and_ordered() -> None:
    rows = [
        LoadedQuestion(index + 2, _question(number), {})
        for index, number in enumerate(reversed(TARGET_QUESTION_IDS))
    ]

    selected = select_target_questions(rows)

    assert tuple(item.question.question_no for item in selected if item.question) == TARGET_QUESTION_IDS


def test_agent_message_contains_no_scoring_or_scope_annotation() -> None:
    question = _question(36, answer=5)

    message = build_user_message(question)

    assert question.question in message
    assert all(choice in message for choice in question.choices)
    assert "공식정답" not in message
    assert "v2_scope" not in message.lower()
    assert "expected article" not in message.lower()

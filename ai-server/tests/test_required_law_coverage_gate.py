from app.evaluation.required_law_coverage_gate import RequiredLawCoverageGate


def retrieval(law_name: str) -> dict[str, str]:
    return {"law_name": law_name, "article_number": "제1조", "text": "본문"}


def test_explicit_stem_law_accepts_same_family_retrieval() -> None:
    result = RequiredLawCoverageGate().validate(
        "공인중개사법령상 중개사무소에 관한 설명으로 옳은 것은?",
        [retrieval("공인중개사법 시행령")],
    )
    assert result.passed is True
    assert result.applicable is True
    assert result.required_laws == ("공인중개사법",)


def test_missing_explicit_governing_law_is_rejected() -> None:
    result = RequiredLawCoverageGate().validate(
        "「부동산 실권리자명의 등기에 관한 법률」상 옳은 것은?",
        [retrieval("주택임대차보호법")],
    )
    assert result.passed is False
    assert result.failure_reason == "required_law_not_retrieved"


def test_law_only_in_choice_is_not_promoted_to_required() -> None:
    result = RequiredLawCoverageGate().validate(
        "다음 설명으로 옳은 것은? 선택지 1. 주택임대차보호법에 따른다.",
        [],
    )
    assert result.passed is True
    assert result.applicable is False


def test_reviewed_annotation_is_observation_only_coverage_input() -> None:
    result = RequiredLawCoverageGate().validate(
        "명의신탁 사실관계 문제",
        [retrieval("주택임대차보호법")],
        reviewed_required_laws=["부동산 실권리자명의 등기에 관한 법률"],
    )
    assert result.passed is False
    assert result.detection_source == "human_reviewed_annotation"


def test_unretrieved_unsupported_laws_are_rejected() -> None:
    gate = RequiredLawCoverageGate()
    assert gate.validate("「민사집행법」에 따른 강제경매 설명은?", []).passed is False
    assert gate.validate("장사 등에 관한 법령에 관하여 옳은 것은?", []).passed is False

from app.evaluation.pair_aware_grounding_validator_c22 import (
    PairAwareGroundingValidatorC22,
)


def item(law: str, article: str, text: str) -> dict[str, str]:
    return {"law_name": law, "article_number": article, "text": text}


def validate(response: str, retrievals: list[dict[str, str]]):
    return PairAwareGroundingValidatorC22().validate(response, retrievals)


def test_allows_grounded_answer_with_negative_unavailable_reference() -> None:
    result = validate(
        "주택임대차보호법 제6조의3에 따라 갱신요구권을 행사할 수 있습니다. "
        "이번 검색에서 제6조 본문은 확인되지 않아 그 기간은 단정하기 어렵습니다.",
        [item("주택임대차보호법", "제6조의3", "계약갱신 요구")],
    )

    assert result.passed is True
    assert result.response_role == "grounded_answer"
    negative = next(
        citation
        for citation in result.citations
        if citation.get("citation_role") == "negative_or_unavailable_reference"
    )
    assert negative["parsed_article_number"] == "제6조"
    assert negative["validation_decision"] == "excluded_from_grounding_not_evidence"


def test_allows_narrow_abstention_without_citation() -> None:
    result = validate(
        "검색된 자료만으로는 무효 여부를 단정할 수 없습니다. "
        "판단하려면 계약서 조항 원문과 구체적인 사실관계가 필요합니다. "
        "자료를 보내주시면 관련 근거를 다시 검토하겠습니다.",
        [item("소득세법", "제1조", "관련 없는 결과")],
    )

    assert result.passed is True
    assert result.response_role == "abstention_without_citation"


def test_rejects_fabricated_affirmative_article() -> None:
    result = validate(
        "민법 제999조에 따라 계약은 무효다.",
        [item("민법", "제563조", "매매")],
    )
    assert result.passed is False


def test_rejects_unavailable_then_same_article_used_for_conclusion() -> None:
    result = validate(
        "민법 제999조는 검색되지 않았지만, 제999조에 따라 계약은 무효다.",
        [item("민법", "제563조", "매매")],
    )
    assert result.passed is False


def test_rejects_unavailable_then_same_article_in_later_sentence() -> None:
    result = validate(
        "민법 제999조는 검색되지 않았습니다. 제999조에 따라 계약은 무효다.",
        [item("민법", "제563조", "매매")],
    )
    assert result.passed is False


def test_rejects_unavailable_then_different_fabricated_citation() -> None:
    result = validate(
        "민법 제999조는 검색되지 않았습니다. 민법 제998조에 따라 계약은 무효다.",
        [item("민법", "제563조", "매매")],
    )
    assert result.passed is False


def test_rejects_definitive_legal_conclusion_without_citation() -> None:
    result = validate(
        "계약은 무효입니다.",
        [item("민법", "제563조", "매매")],
    )
    assert result.passed is False
    assert result.failure_reason == "missing_article_citation"


def test_rejects_disclaimer_mixed_with_definitive_claim() -> None:
    result = validate(
        "추가 확인이 필요하지만 계약은 무효다. 계약서 원문을 보내주세요.",
        [item("민법", "제563조", "매매")],
    )
    assert result.passed is False


def test_existing_retrieval_pair_still_passes() -> None:
    result = validate(
        "주택임대차보호법 제6조의2에 따라 통지 후 3개월이 지나면 효력이 발생합니다.",
        [item("주택임대차보호법", "제6조의2", "통지 후 3개월")],
    )
    assert result.passed is True


def test_wrong_law_article_pair_still_rejected() -> None:
    result = validate(
        "민법 제9조에 따른다.",
        [item("민법", "제6조", "본문"), item("주택법", "제9조", "본문")],
    )
    assert result.passed is False


def test_dependent_cross_reference_still_passes() -> None:
    result = validate(
        "부동산 거래신고 등에 관한 법률 시행령 제11조는 법 제9조를 따른다.",
        [
            item(
                "부동산 거래신고 등에 관한 법률 시행령",
                "제11조",
                "법 제9조에 따른 허가",
            )
        ],
    )
    assert result.passed is True


def test_ambiguous_negative_scope_uses_original_conservative_validation() -> None:
    result = validate(
        "제6조가 아닌 듯하지만 관련 규정에 따라 계약은 무효다.",
        [item("민법", "제563조", "매매")],
    )
    assert result.passed is False


def test_unavailable_reference_cannot_hide_definitive_timing_claim() -> None:
    result = validate(
        "제6조는 확인하지 못했지만 제6조상 반드시 3개월입니다.",
        [item("주택임대차보호법", "제6조의2", "본문")],
    )
    assert result.passed is False


def test_citation_free_specific_legal_effect_still_rejected() -> None:
    result = validate(
        "자료 확인이 필요하지만 임대인은 반드시 손해배상을 해야 합니다. "
        "계약서 원문을 보내주세요.",
        [item("주택임대차보호법", "제6조의3", "본문")],
    )
    assert result.passed is False


def test_article_suffixes_remain_distinct() -> None:
    result = validate(
        "주택임대차보호법 제6조와 제6조의2를 함께 적용합니다.",
        [
            item("주택임대차보호법", "제6조", "본문"),
            item("주택임대차보호법", "제6조의2", "본문"),
        ],
    )
    assert result.passed is True

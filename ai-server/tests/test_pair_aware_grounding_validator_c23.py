from app.evaluation.pair_aware_grounding_validator_c23 import (
    PairAwareGroundingValidatorC23,
)


def item(law: str, article: str, text: str) -> dict[str, str]:
    return {"law_name": law, "article_number": article, "text": text}


def validate(response: str, retrievals: list[dict[str, str]]):
    return PairAwareGroundingValidatorC23().validate(response, retrievals)


def test_allows_same_law_full_expansion_found_in_verified_parent() -> None:
    result = validate(
        "주택임대차보호법 제6조의3에 따라 갱신됩니다. "
        "주택임대차보호법 제7조의 범위에서 보증금을 조정할 수 있습니다.",
        [
            item(
                "주택임대차보호법",
                "제6조의3",
                "차임과 보증금은 제7조의 범위에서 증감할 수 있다.",
            )
        ],
    )

    assert result.passed is True
    expanded = result.citations[1]
    assert expanded["citation_role"] == "dependent_parent_cross_reference"
    assert expanded["parent_retrieval_pair"] == {
        "law_name": "주택임대차보호법",
        "article_number": "제6조의3",
    }
    assert expanded["validation_decision"] == "allowed_same_law_parent_cross_reference"


def test_rejects_same_law_article_absent_from_parent() -> None:
    result = validate(
        "민법 제10조에 따르며 민법 제20조도 적용됩니다.",
        [item("민법", "제10조", "민법 제10조 본문")],
    )
    assert result.passed is False


def test_rejects_different_law_with_same_article_number() -> None:
    result = validate(
        "주택임대차보호법 제6조의3에 따르며 상가건물 임대차보호법 제7조도 적용됩니다.",
        [item("주택임대차보호법", "제6조의3", "제7조에 따른다.")],
    )
    assert result.passed is False


def test_rejects_article_found_only_in_unrelated_chunk() -> None:
    result = validate(
        "주택임대차보호법 제6조의3에 따르며 주택임대차보호법 제7조도 적용됩니다.",
        [
            item("주택임대차보호법", "제6조의3", "외부 조문 참조 없음"),
            item("주택임대차보호법", "제8조", "제7조에 따른다."),
        ],
    )
    assert result.passed is False


def test_rejects_plain_number_in_parent_body() -> None:
    result = validate(
        "민법 제10조에 따르며 민법 제7조도 적용됩니다.",
        [item("민법", "제10조", "기간은 7일이다.")],
    )
    assert result.passed is False


def test_rejects_fabricated_article() -> None:
    result = validate(
        "민법 제10조에 따르며 민법 제999조에 따라 계약은 무효입니다.",
        [item("민법", "제10조", "제20조에 따른다.")],
    )
    assert result.passed is False


def test_rejects_wrong_law_article_pair() -> None:
    result = validate(
        "민법 제9조에 따른다.",
        [item("민법", "제6조", "본문"), item("주택법", "제9조", "본문")],
    )
    assert result.passed is False


def test_existing_shorthand_dependent_reference_is_unchanged() -> None:
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
    assert result.citations[1]["validation_decision"] == "allowed_parent_cross_reference"


def test_allows_reference_in_any_chunk_of_same_parent_pair() -> None:
    result = validate(
        "민법 제10조에 따르며 민법 제20조도 적용됩니다.",
        [
            item("민법", "제10조", "첫 번째 청크에는 외부 참조 없음"),
            item("민법", "제10조", "두 번째 청크는 제20조를 준용한다."),
            item("주택법", "제99조", "제20조"),
        ],
    )
    assert result.passed is True
    assert result.citations[1]["matched_parent_chunk_count"] == 1


def test_negative_unavailable_reference_keeps_c22_behavior() -> None:
    result = validate(
        "주택임대차보호법 제6조의3에 따라 갱신할 수 있습니다. "
        "이번 검색에서 제6조 본문은 확인되지 않았습니다.",
        [item("주택임대차보호법", "제6조의3", "계약갱신 요구")],
    )
    assert result.passed is True
    assert any(
        citation["citation_role"] == "negative_or_unavailable_reference"
        for citation in result.citations
    )


def test_citation_free_safe_abstention_keeps_c22_behavior() -> None:
    result = validate(
        "검색된 자료만으로는 무효 여부를 단정할 수 없습니다. "
        "판단하려면 계약서 조항 원문과 구체적인 사실관계가 필요합니다. "
        "자료를 보내주시면 관련 근거를 다시 검토하겠습니다.",
        [item("소득세법", "제1조", "관련 없는 결과")],
    )
    assert result.passed is True
    assert result.response_role == "abstention_without_citation"


def test_disclaimer_with_definitive_unsupported_claim_stays_rejected() -> None:
    result = validate(
        "추가 확인이 필요하지만 계약은 무효다. 계약서 원문을 보내주세요.",
        [item("민법", "제563조", "매매")],
    )
    assert result.passed is False


def test_does_not_confuse_article_with_suffixed_article() -> None:
    result = validate(
        "주택임대차보호법 제6조의3에 따르며 주택임대차보호법 제7조도 적용됩니다.",
        [item("주택임대차보호법", "제6조의3", "제7조의2에 따른다.")],
    )
    assert result.passed is False


def test_bare_response_reference_is_not_promoted_by_c23() -> None:
    result = validate(
        "민법 제10조에 따르며 제20조도 적용됩니다.",
        [item("민법", "제10조", "제20조에 따른다.")],
    )
    assert result.passed is False


def test_parent_must_first_be_verified_by_a_response_citation() -> None:
    result = validate(
        "민법 제20조가 적용됩니다.",
        [item("민법", "제10조", "제20조에 따른다.")],
    )
    assert result.passed is False


def test_one_valid_parent_expansion_cannot_hide_another_fabricated_citation() -> None:
    result = validate(
        "민법 제10조에 따르며 민법 제20조와 민법 제999조도 적용됩니다.",
        [item("민법", "제10조", "제20조에 따른다.")],
    )
    assert result.passed is False

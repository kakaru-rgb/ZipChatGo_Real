from app.evaluation.pair_aware_grounding_validator_c21 import PairAwareGroundingValidatorC21


def item(law: str, article: str, text: str) -> dict[str, str]:
    return {"law_name": law, "article_number": article, "text": text}


def test_cross_reference_may_match_any_chunk_of_same_parent_pair() -> None:
    retrievals = [
        item("공인중개사법 시행규칙", "제4조", "제4조 첫 번째 청크"),
        item("공인중개사법 시행규칙", "제4조", "제4조 「상법」 제614조에 따른 영업소 등기"),
        item("주택법", "제99조", "「상법」 제614조"),
    ]
    result = PairAwareGroundingValidatorC21().validate(
        "공인중개사법 시행규칙 제4조에 따라 「상법」 제614조가 적용된다.",
        retrievals,
    )
    assert result.passed is True
    cross = result.citations[1]
    assert cross.parent_retrieval_pair == {
        "law_name": "공인중개사법 시행규칙",
        "article_number": "제4조",
    }
    assert cross.matched_parent_chunk_count == 1


def test_unrelated_chunk_cannot_supply_cross_reference() -> None:
    result = PairAwareGroundingValidatorC21().validate(
        "공인중개사법 시행규칙 제4조에 따라 「상법」 제614조가 적용된다.",
        [
            item("공인중개사법 시행규칙", "제4조", "외부 참조 없음"),
            item("주택법", "제99조", "「상법」 제614조"),
        ],
    )
    assert result.passed is False
    assert result.citations[1].validation_decision == "rejected_unretrieved_citation"


def test_family_context_resolves_plain_and_same_shorthand() -> None:
    retrievals = [
        item("공인중개사법 시행령", "제31조", "협회의 업무"),
        item("공인중개사법", "제18조의3", "표시 광고 모니터링"),
        item("공인중개사법 시행규칙", "제6조", "등록사항 통지"),
    ]
    result = PairAwareGroundingValidatorC21().validate(
        "공인중개사법 시행령 제31조와 공인중개사법 제18조의3을 비교한다. "
        "따라서 시행령 제31조, 같은 시행령 제31조, 시행규칙 제6조, "
        "같은 시행규칙 제6조 및 같은 법 제18조의3이 근거다.",
        retrievals,
    )
    assert result.passed is True
    assert [citation.parsed_law_name for citation in result.citations[-5:]] == [
        "공인중개사법 시행령",
        "공인중개사법 시행령",
        "공인중개사법 시행규칙",
        "공인중개사법 시행규칙",
        "공인중개사법",
    ]


def test_ambiguous_shorthand_is_rejected_conservatively() -> None:
    result = PairAwareGroundingValidatorC21().validate(
        "시행령 제31조에 따른다.",
        [
            item("공인중개사법 시행령", "제31조", "본문"),
            item("주택법 시행령", "제31조", "본문"),
        ],
    )
    assert result.passed is False
    assert result.citations[0].parsed_law_name is None


def test_article_suffix_and_fabricated_pair_safety() -> None:
    validator = PairAwareGroundingValidatorC21()
    assert validator.validate(
        "주택임대차보호법 제6조의2와 같은 법 제6조를 적용한다.",
        [
            item("주택임대차보호법", "제6조의2", "본문"),
            item("주택임대차보호법", "제6조", "본문"),
        ],
    ).passed is True
    assert validator.validate(
        "주택임대차보호법 제6조를 근거로 민법 제999조도 적용한다.",
        [item("주택임대차보호법", "제6조", "본문")],
    ).passed is False


def test_law_cross_reference_must_be_in_its_parent_pair_chunks() -> None:
    validator = PairAwareGroundingValidatorC21()
    result = validator.validate(
        "부동산 거래신고 등에 관한 법률 시행령 제11조는 법 제9조를 따른다.",
        [
            item(
                "부동산 거래신고 등에 관한 법률 시행령",
                "제11조",
                "외국인등은 법 제9조에 따라 신고한다.",
            ),
            item("주택법", "제1조", "법 제9조"),
        ],
    )
    assert result.passed is True
    assert result.citations[1].citation_role == "dependent_cross_reference"
    assert result.citations[1].parent_text_match is True


def test_same_article_number_in_multiple_laws_stays_pair_specific() -> None:
    retrievals = [
        item("민법", "제6조", "민법 본문"),
        item("주택법", "제6조", "주택법 본문"),
    ]
    validator = PairAwareGroundingValidatorC21()
    good = validator.validate("민법 제6조와 주택법 제6조를 비교한다.", retrievals)
    bad = validator.validate("상법 제6조를 적용한다.", retrievals)
    assert good.passed is True
    assert [citation.parsed_law_name for citation in good.citations] == ["민법", "주택법"]
    assert bad.passed is False

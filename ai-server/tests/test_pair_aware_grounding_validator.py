from app.evaluation.pair_aware_grounding_validator import PairAwareGroundingValidator


def result(law_name: str, article_number: str, text: str) -> dict[str, str]:
    return {"law_name": law_name, "article_number": article_number, "text": text}


def validate(response: str, retrievals: list[dict[str, str]]):
    return PairAwareGroundingValidator().validate(response, retrievals)


def test_allows_q9_style_external_cross_reference_in_parent_article() -> None:
    retrievals = [
        result("공인중개사법 시행규칙", "제6조", "제6조 등록사항 등의 통지"),
        result(
            "공인중개사법 시행규칙",
            "제4조",
            "제4조 개설등록 신청. 나. 「상법」 제614조의 규정에 따른 영업소의 등기 증명서류",
        ),
    ]
    outcome = validate(
        "「공인중개사법 시행규칙」 제6조가 주근거이고, 같은 시행규칙 제4조의 「상법」 제614조도 적용된다.",
        retrievals,
    )
    assert outcome.passed is True
    cross_reference = next(c for c in outcome.citations if c.parsed_article_number == "제614조")
    assert cross_reference.citation_role == "dependent_cross_reference"
    assert cross_reference.parent_retrieval_pair == {
        "law_name": "공인중개사법 시행규칙",
        "article_number": "제4조",
    }
    assert cross_reference.parent_text_match is True


def test_allows_q27_style_law_cross_reference_only_from_parent_body() -> None:
    retrievals = [
        result(
            "부동산 거래신고 등에 관한 법률 시행령",
            "제11조",
            "제11조 국가 등의 특례. ③ 법 제9조에 따라 외국인등이 토지취득 허가를 받은 경우",
        )
    ]
    outcome = validate(
        "「부동산 거래신고 등에 관한 법률 시행령」 제11조에 따르며 법 제9조에 따른 허가도 포함한다.",
        retrievals,
    )
    assert outcome.passed is True
    cross_reference = next(c for c in outcome.citations if c.parsed_article_number == "제9조")
    assert cross_reference.parsed_law_name == "부동산 거래신고 등에 관한 법률"
    assert cross_reference.parent_text_match is True


def test_rejects_fabricated_article_absent_from_retrieval_and_parent() -> None:
    outcome = validate(
        "「공인중개사법 시행규칙」 제6조와 「민법」 제999조에 따른다.",
        [result("공인중개사법 시행규칙", "제6조", "제6조 등록사항 등의 통지")],
    )
    assert outcome.passed is False
    fabricated = next(c for c in outcome.citations if c.parsed_article_number == "제999조")
    assert fabricated.parsed_law_name == "민법"
    assert fabricated.validation_decision == "rejected_unretrieved_citation"


def test_rejects_wrong_law_and_article_pair_even_when_each_attribute_exists() -> None:
    retrievals = [
        result("민법", "제6조", "민법 제6조 본문"),
        result("주택법", "제9조", "주택법 제9조 본문"),
    ]
    outcome = validate("「민법」 제9조에 따른다.", retrievals)
    assert outcome.passed is False
    assert outcome.citations[0].validation_decision == "rejected_unretrieved_citation"


def test_rejects_same_article_number_with_mismatched_law_name() -> None:
    retrievals = [result("주택임대차보호법", "제6조", "주택임대차보호법 제6조 본문")]
    outcome = validate("「상가건물 임대차보호법」 제6조에 따른다.", retrievals)
    assert outcome.passed is False


def test_handles_article_suffix_bare_and_same_law_references() -> None:
    retrievals = [
        result("주택임대차보호법", "제6조", "제6조 본문"),
        result("주택임대차보호법", "제6조의2", "제6조의2 본문"),
        result("주택임대차보호법", "제9조", "제9조 본문"),
    ]
    outcome = validate(
        "「주택임대차보호법」 제6조, 제6조의2 및 같은 법 제9조를 확인한다.",
        retrievals,
    )
    assert outcome.passed is True
    assert [c.parsed_article_number for c in outcome.citations] == ["제6조", "제6조의2", "제9조"]


def test_multiple_laws_with_same_article_number_remain_pair_specific() -> None:
    retrievals = [
        result("민법", "제6조", "민법 제6조 본문"),
        result("주택법", "제6조", "주택법 제6조 본문"),
    ]
    outcome = validate("「민법」 제6조와 「주택법」 제6조를 함께 검토한다.", retrievals)
    assert outcome.passed is True
    assert [c.parsed_law_name for c in outcome.citations] == ["민법", "주택법"]


def test_does_not_accept_cross_reference_found_only_in_unrelated_result() -> None:
    retrievals = [
        result("공인중개사법 시행규칙", "제4조", "제4조 본문에는 외부 참조가 없다."),
        result("주택법", "제10조", "이 무관한 본문에는 「상법」 제614조가 있다."),
    ]
    outcome = validate(
        "「공인중개사법 시행규칙」 제4조와 그 근거인 「상법」 제614조를 적용한다.",
        retrievals,
    )
    assert outcome.passed is False
    cross_reference = next(c for c in outcome.citations if c.parsed_article_number == "제614조")
    assert cross_reference.parent_text_match is False


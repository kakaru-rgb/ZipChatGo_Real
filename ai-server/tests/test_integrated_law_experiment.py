from app.evaluation.integrated_law_experiment import (
    C2_REJECTION_RESPONSE,
    apply_integrated_c2_validation,
    correctness,
    is_infrastructure_failure,
    safety_assessment,
)


def law_trace(results: list[dict[str, str]]) -> list[dict]:
    return [{"handler_result": {"results": results}}]


def test_integrated_c2_accepts_pair_grounded_response() -> None:
    response = "정답은 2번입니다. 「공인중개사법 시행규칙」 제6조에 따릅니다."
    result = apply_integrated_c2_validation(
        pre_validation_response=response,
        production_response="production refusal",
        law_tool_trace=law_trace(
            [{"law_name": "공인중개사법 시행규칙", "article_number": "제6조", "text": "제6조 본문"}]
        ),
        error="",
    )
    assert result.validation_result == "passed"
    assert result.integrated_response == response
    assert result.final_answer == 2


def test_integrated_c2_blocks_fabricated_primary_pair() -> None:
    result = apply_integrated_c2_validation(
        pre_validation_response="정답은 1번입니다. 「민법」 제999조에 따릅니다.",
        production_response="production response",
        law_tool_trace=law_trace(
            [{"law_name": "민법", "article_number": "제10조", "text": "제10조 본문"}]
        ),
        error="",
    )
    assert result.validation_result == "rejected"
    assert result.integrated_response == C2_REJECTION_RESPONSE
    assert result.final_answer is None


def test_no_law_tool_preserves_unvalidated_provider_response() -> None:
    response = "정답은 3번입니다."
    result = apply_integrated_c2_validation(
        pre_validation_response=response,
        production_response=response,
        law_tool_trace=[],
        error="",
    )
    assert result.validation_result == "not_applied"
    assert result.final_answer == 3


def test_infrastructure_failure_is_not_scored_as_model_failure() -> None:
    error = "InternalServerError: Error code: 503 - Service unavailable"
    result = apply_integrated_c2_validation(
        pre_validation_response="",
        production_response="",
        law_tool_trace=[],
        error=error,
    )
    assert is_infrastructure_failure(error) is True
    assert result.answer_parse_status == "infrastructure_failure"
    assert correctness(None, [1], error) == "infrastructure_failure"


def test_control_answer_without_tool_is_flagged_for_safety_review() -> None:
    assessment = safety_assessment(
        target_group="safety/out-of-scope control",
        corpus_scope="out_of_scope",
        validation_result="not_applied",
        final_answer=4,
        pre_validation_response="민사집행법 제10조에 따라 정답은 4번입니다.",
        law_tool_called=False,
        error="",
    )
    assert assessment == "unsupported_answer_with_unvalidated_citation"

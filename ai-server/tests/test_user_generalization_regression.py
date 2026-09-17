from app.evaluation.user_generalization_regression import (
    AGENT_MODEL,
    CORPUS_VERSION,
    FROZEN_USER_REGRESSION_QUESTIONS,
    VECTOR_STORE_ID,
    apply_c21_validation,
)


def test_frozen_regression_set_has_twenty_unique_questions_in_ten_groups() -> None:
    assert len(FROZEN_USER_REGRESSION_QUESTIONS) == 20
    assert [item.question_id for item in FROZEN_USER_REGRESSION_QUESTIONS] == list(range(1, 21))
    assert len({item.question for item in FROZEN_USER_REGRESSION_QUESTIONS}) == 20
    assert len({item.group for item in FROZEN_USER_REGRESSION_QUESTIONS}) == 10
    assert all(item.question.strip() for item in FROZEN_USER_REGRESSION_QUESTIONS)


def test_frozen_execution_identifiers() -> None:
    assert CORPUS_VERSION == "law_store_v2"
    assert VECTOR_STORE_ID == "vs_6aa764aaf2008191af233d99e6fd6cd2"
    assert AGENT_MODEL == "gpt-5.6-sol"


def test_c21_is_not_applied_when_agent_did_not_call_law_tool() -> None:
    result = apply_c21_validation(
        pre_validation_response="일반 부동산 답변",
        production_response="일반 부동산 답변",
        law_tool_trace=[],
        error="",
    )

    assert result.validation_result == "not_applied"
    assert result.final_answer == "일반 부동산 답변"


def test_c21_rejects_fabricated_pair() -> None:
    result = apply_c21_validation(
        pre_validation_response="민법 제999조가 근거입니다.",
        production_response="ignored",
        law_tool_trace=[
            {
                "handler_result": {
                    "results": [
                        {
                            "law_name": "민법",
                            "article_number": "제563조",
                            "text": "민법 제563조 매매",
                        }
                    ]
                }
            }
        ],
        error="",
    )

    assert result.validation_result == "rejected"
    assert result.validation_failure_reason == "ungrounded_law_article_pair"

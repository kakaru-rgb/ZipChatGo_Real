import json

from app.evaluation.production_failure_analysis import classify_failure


def _row(**updates: str) -> dict[str, str]:
    row = {
        "오류": "", "AgentRawResponse": "정답: 1번", "답번호추출상태": "추출성공",
        "정답여부": "X", "CorpusScope": "in_scope",
        "CorpusScope근거법령": "공인중개사법", "CorpusScope분류이유": "",
        "법률Tool자율호출여부": "Y",
        "법률ToolTrace": json.dumps([
            {"retrieval_results": [{"law_name": "공인중개사법", "article_number": "제1조"}]}
        ]),
    }
    row.update(updates)
    return row


def test_relevant_law_name_alone_requires_retrieval_reasoning_review() -> None:
    assert classify_failure(_row())[0] == "retrieval_vs_reasoning_review_required"


def test_no_tool_in_scope_wrong_answer_is_routing_failure() -> None:
    assert classify_failure(_row(법률Tool자율호출여부="N", 법률ToolTrace="[]"))[0] == "routing_failure"


def test_no_results_is_retrieval_failure() -> None:
    assert classify_failure(_row(법률ToolTrace="[]"))[0] == "retrieval_failure"


def test_grounding_safe_response_has_priority_over_parse_failure() -> None:
    row = _row(
        AgentRawResponse="검색된 공식 법령 근거와 답변의 조문 인용이 일치하지 않아 답변을 제공하지 않았습니다.",
        답번호추출상태="판정불가:명시적정답없음",
    )
    assert classify_failure(row)[0] == "grounding_validation_failure"


def test_out_of_scope_wrong_answer_is_out_of_scope() -> None:
    assert classify_failure(_row(CorpusScope="out_of_scope"))[0] == "out_of_scope"


def test_correct_answer_is_success() -> None:
    assert classify_failure(_row(정답여부="O"))[0] == "success"

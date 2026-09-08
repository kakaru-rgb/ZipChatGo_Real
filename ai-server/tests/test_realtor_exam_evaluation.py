import csv

import httpx

from app.evaluation.realtor_exam import (
    ChatbotExamEvaluator,
    ExamQuestion,
    build_chat_message,
    parse_predicted_answer,
    write_result_csv,
)


def _question() -> ExamQuestion:
    return ExamQuestion(
        year=2024,
        paper_id="1차_1교시",
        paper_name="2024 문제지",
        subject="민법",
        question_no=41,
        question="계약금 해제에 관한 설명으로 옳은 것은?",
        choices=["선택 A", "선택 B", "선택 C", "선택 D", "선택 E"],
        correct_answer=3,
        source_pdf="exam.pdf",
    )


def test_parse_predicted_answer_uses_explicit_final_answer() -> None:
    assert parse_predicted_answer("①과 ②를 검토했습니다.\n최종 정답: ③번") == 3
    assert parse_predicted_answer("설명만 있고 번호를 고르지 않았습니다.") is None


def test_chat_message_does_not_include_official_answer() -> None:
    message = build_chat_message(_question())

    assert "공식정답" not in message
    assert "최종 정답: N번" in message
    assert "계약금 해제" in message


def test_evaluator_calls_real_agent_chat_shape_and_scores_response() -> None:
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured.update(request.read() and __import__("json").loads(request.content))
        return httpx.Response(
            200,
            json={
                "message": "민법상 근거를 검토했습니다.\n최종 정답: 3번",
                "actions": [],
            },
            headers={"X-ZipChatGo-RAG-Used": "true"},
            request=request,
        )

    client = httpx.Client(
        base_url="http://test",
        transport=httpx.MockTransport(handler),
    )
    row = ChatbotExamEvaluator("http://test", client=client).evaluate(_question())

    assert "message" in captured
    assert "correct_answer" not in captured
    assert row["챗봇예측"] == "3"
    assert row["공식정답"] == "3"
    assert row["정답여부"] == "O"
    assert row["RAG사용여부"] == "Y"


def test_result_csv_is_excel_friendly_utf8(tmp_path) -> None:
    row = ChatbotExamEvaluator(
        "http://test",
        client=httpx.Client(
            base_url="http://test",
            transport=httpx.MockTransport(
                lambda request: httpx.Response(
                    200,
                    json={"message": "최종 정답: 3번", "actions": []},
                    request=request,
                )
            ),
        ),
    ).evaluate(_question())
    path = tmp_path / "result.csv"

    write_result_csv([row], path)

    assert path.read_bytes().startswith(b"\xef\xbb\xbf")
    with path.open("r", encoding="utf-8-sig", newline="") as stream:
        saved = list(csv.DictReader(stream))
    assert saved[0]["문제"].startswith("계약금 해제")
    assert saved[0]["정답여부"] == "O"
    assert saved[0]["RAG사용여부"] == "N"

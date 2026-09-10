import csv
import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

from app.evaluation.production_agent_observer import (
    ObservedOpenAIClient,
    ProductionAgentObserver,
)
from app.evaluation.production_agent_passthrough import (
    PassthroughRuntime,
    build_user_message,
    evaluate_question,
    load_reviewed_exam_csv,
)
from app.evaluation.production_answer_parser import parse_final_answer
from app.evaluation.realtor_exam import ExamQuestion
from app.providers.llm_provider import AgentReply


def _question() -> ExamQuestion:
    return ExamQuestion(
        year=2024,
        paper_id="2차_1교시",
        paper_name="reviewed",
        subject="공인중개사법령 및 중개실무",
        question_no=1,
        question="공인중개사법령상 옳은 것은?",
        choices=["보기 1", "보기 2", "보기 3", "보기 4", "보기 5"],
        correct_answer=3,
        accepted_answers=[3],
        source_pdf="source.pdf",
        source_page=1,
    )


def test_answer_parser_never_recomputes_or_changes_answer() -> None:
    assert parse_final_answer("판단 결과 정답은 3번입니다.").answer == 3
    assert parse_final_answer("1번도 검토했지만 최종 정답은 3번입니다.").answer == 3
    assert parse_final_answer("옳은 선택지는 **5번**입니다.").answer == 5
    assert parse_final_answer("정답: **5**.").answer == 5
    assert parse_final_answer("함께 할 수 없는 업무는 **4. 도배업체 소개**입니다.").answer == 4
    assert parse_final_answer("틀린 설명은 **3번**입니다.").answer == 3
    assert parse_final_answer("대상이 아닌 것은 **2번**입니다.").answer == 2
    assert parse_final_answer("**정답 번호**: **4. ㄴ, ㄷ, ㄹ**").answer == 4
    assert parse_final_answer("정답은 2번 또는 3번입니다.").answer is None
    assert parse_final_answer("판단 이유만 있습니다.").answer is None


def test_observers_return_original_sdk_and_tool_objects() -> None:
    observer = ProductionAgentObserver()
    response = SimpleNamespace(
        output=[
            SimpleNamespace(
                type="function_call",
                call_id="call-1",
                name="search_real_estate_law",
                arguments=json.dumps({"query": "대항력"}, ensure_ascii=False),
            )
        ]
    )
    responses = Mock()
    responses.create.return_value = response
    client = SimpleNamespace(responses=responses)
    observed_client = ObservedOpenAIClient(client, observer)
    assert observed_client.responses.create(model="test") is response

    original_result = {"total_count": 0, "results": []}
    handler = Mock(return_value=original_result)
    arguments = {"query": "실제 검색 query"}
    returned = observer.wrap_handler("search_real_estate_law", handler)(arguments)
    handler.assert_called_once_with(arguments)
    assert returned is original_result
    assert observer.law_traces()[0]["model_query"] == "대항력"
    assert observer.law_traces()[0]["retrieval_query"] == "실제 검색 query"


def test_passthrough_uses_only_user_message_and_does_not_correct_answer() -> None:
    provider = Mock()
    provider.generate.return_value = AgentReply(message="최종 정답은 2번입니다.")
    runtime = PassthroughRuntime(
        provider=provider,
        handlers={},
        observer=ProductionAgentObserver(),
        model="production-model",
    )
    row = evaluate_question(
        _question(),
        runtime,
        run_id="run",
        evaluated_at="2026-09-10T12:00:00+09:00",
        git_commit="abc",
    )
    request = provider.generate.call_args.kwargs
    assert request["message"] == build_user_message(_question())
    assert "공식정답" not in request["message"]
    assert request["app_state"] is None
    assert row["Agent최종답"] == "2"
    assert row["정답여부"] == "X"
    assert row["AgentRawResponse"] == "최종 정답은 2번입니다."
    assert row["AgentModel"] == "production-model"


def test_reviewed_csv_loader_records_bad_row_without_normalizing(tmp_path: Path) -> None:
    path = tmp_path / "reviewed.csv"
    fields = (
        "연도", "시험", "교시", "과목", "문항번호", "문제",
        "선택지1", "선택지2", "선택지3", "선택지4", "선택지5",
        "공식정답", "원본PDF", "페이지", "추출상태", "검토메모",
    )
    with path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerow(
            {
                "연도": "2024", "시험": "2차", "교시": "1교시",
                "과목": "공인중개사법령 및 중개실무", "문항번호": "1",
                "문제": " 원문 공백 유지 ", "선택지1": "1", "선택지2": "2",
                "선택지3": "3", "선택지4": "4", "선택지5": "5",
                "공식정답": "not-a-number", "원본PDF": "source.pdf",
                "페이지": "1", "추출상태": "정상", "검토메모": "",
            }
        )
    loaded = load_reviewed_exam_csv(path)
    assert loaded[0].question is None
    assert "입력 행 오류" in loaded[0].error
    assert loaded[0].raw["문제"] == " 원문 공백 유지 "

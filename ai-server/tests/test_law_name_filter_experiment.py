from types import SimpleNamespace
from unittest.mock import Mock

from app.evaluation.law_name_filter_experiment import (
    ExperimentalOpenAIClient,
    LawNameFilterExperimentHandler,
    PreValidationCapture,
    analyze_validation,
    detect_explicit_law_names,
)
from app.evaluation.production_agent_observer import ProductionAgentObserver


def test_detects_exact_law_and_law_family_from_question_stem() -> None:
    assert detect_explicit_law_names("주택임대차보호법상 계약갱신요구권") == [
        "주택임대차보호법"
    ]
    assert detect_explicit_law_names("주택임대차보호법 시행령 제10조") == [
        "주택임대차보호법 시행령"
    ]
    assert detect_explicit_law_names("공인중개사법령상 옳은 것은?") == [
        "공인중개사법",
        "공인중개사법 시행령",
        "공인중개사법 시행규칙",
    ]
    assert detect_explicit_law_names("부동산 거래 신고 등에 관한 법령상 허가") == [
        "부동산 거래신고 등에 관한 법률",
        "부동산 거래신고 등에 관한 법률 시행령",
        "부동산 거래신고 등에 관한 법률 시행규칙",
    ]


def test_filtered_handler_returns_filtered_original_object() -> None:
    filtered = {"total_count": 1, "results": [{"law_name": "주택임대차보호법"}]}
    handler = Mock(return_value=filtered)
    experiment = LawNameFilterExperimentHandler(
        handler,
        "주택임대차보호법상 계약갱신요구권",
    )
    arguments = {"query": "사용자 질문\n핵심 법률 검색어: 갱신요구권"}
    returned = experiment(arguments)
    assert returned is filtered
    handler.assert_called_once_with(
        {**arguments, "law_names": ["주택임대차보호법"]}
    )
    assert experiment.traces[0].fallback is False


def test_zero_filtered_result_falls_back_without_altering_fallback_result() -> None:
    empty = {"total_count": 0, "results": []}
    fallback = {"total_count": 1, "results": [{"law_name": "민법"}]}
    handler = Mock(side_effect=[empty, fallback])
    experiment = LawNameFilterExperimentHandler(
        handler,
        "일반적인 계약 질문",
    )
    arguments = {"query": "핵심 법률 검색어: 주택임대차보호법 대항력"}
    returned = experiment(arguments)
    assert returned is fallback
    assert handler.call_args_list[0].args[0]["law_names"] == ["주택임대차보호법"]
    assert handler.call_args_list[1].args[0] == arguments
    assert experiment.traces[0].fallback is True


def test_client_observer_captures_pre_validation_terminal_text() -> None:
    response = SimpleNamespace(output=[], output_text="검증 전 답변")
    responses = Mock()
    responses.create.return_value = response
    observer = ProductionAgentObserver()
    capture = PreValidationCapture()
    client = ExperimentalOpenAIClient(SimpleNamespace(responses=responses), observer, capture)
    assert client.responses.create(model="test") is response
    assert capture.raw_response == "검증 전 답변"
    assert capture.response_rounds == 1


def test_validation_analysis_reports_unretrieved_article_without_changing_text() -> None:
    traces = [
        {
            "retrieval_results": [
                {"law_name": "주택임대차보호법", "article_number": "제6조의3"}
            ]
        }
    ]
    result, reason = analyze_validation(
        "주택임대차보호법 제7조에 따릅니다.",
        "안전 거절 문장",
        traces,
        "",
    )
    assert result == "rejected"
    assert reason == "ungrounded_article_citation"


def test_validation_analysis_accepts_source_link_augmentation() -> None:
    traces = [
        {
            "retrieval_results": [
                {"law_name": "주택임대차보호법", "article_number": "제6조의3"}
            ]
        }
    ]
    result, reason = analyze_validation(
        "주택임대차보호법 제6조의3에 따릅니다.",
        "주택임대차보호법 제6조의3에 따릅니다.\n\n관련 법령: 링크",
        traces,
        "",
    )
    assert result == "passed"
    assert reason == ""

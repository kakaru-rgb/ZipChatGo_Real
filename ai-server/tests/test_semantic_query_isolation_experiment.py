from unittest.mock import Mock

from app.evaluation.law_name_filter_experiment import LawNameFilterExperimentHandler
from app.evaluation.semantic_query_isolation_experiment import (
    SemanticQueryIsolationHandler,
)


def test_isolates_semantic_query_without_mutating_input_or_result() -> None:
    returned = {"total_count": 1, "results": [{"article_number": "제6조"}]}
    tool_handler = Mock(return_value=returned)
    law_filter_handler = LawNameFilterExperimentHandler(
        tool_handler,
        "공인중개사법령상 개설등록에 관한 설명",
    )
    experiment = SemanticQueryIsolationHandler(
        law_filter_handler,
        lambda: "공인중개사법 시행규칙 등록 통보 다음 달 10일",
    )
    original = {
        "query": "사용자 질문: 전체 문제와 선택지\n핵심 법률 검색어: 모델 검색어"
    }

    result = experiment(original)

    assert result is returned
    assert original["query"].startswith("사용자 질문:")
    called = tool_handler.call_args.args[0]
    assert called["query"] == "공인중개사법 시행규칙 등록 통보 다음 달 10일"
    assert experiment.isolation_traces[0].isolation_applied is True
    assert experiment.isolation_traces[0].semantic_query == called["query"]
    assert experiment.traces is law_filter_handler.traces


def test_preserves_provider_query_when_original_model_query_is_unavailable() -> None:
    returned = {"total_count": 0, "results": []}
    tool_handler = Mock(return_value=returned)
    law_filter_handler = LawNameFilterExperimentHandler(tool_handler, "일반 질문")
    experiment = SemanticQueryIsolationHandler(law_filter_handler, lambda: "")
    original = {"query": "provider query"}

    assert experiment(original) is returned
    tool_handler.assert_called_once_with(original)
    assert experiment.isolation_traces[0].isolation_applied is False

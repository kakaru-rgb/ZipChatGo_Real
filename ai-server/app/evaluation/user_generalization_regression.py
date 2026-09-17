from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Sequence

from app.evaluation.pair_aware_grounding_validator_c21 import (
    PairAwareGroundingValidatorC21,
    collect_retrieval_results,
)


CORPUS_VERSION = "law_store_v2"
VECTOR_STORE_ID = "vs_6aa764aaf2008191af233d99e6fd6cd2"
AGENT_MODEL = "gpt-5.6-sol"
EVALUATION_MODE = "production_agent_law_store_v2_generalization_regression"
C21_REJECTION_RESPONSE = (
    "검색된 공식 법령 근거와 답변의 법령·조문 인용이 일치하지 않아 "
    "확정적인 법률 답변을 제공하지 않았습니다."
)


@dataclass(frozen=True)
class UserRegressionQuestion:
    question_id: int
    group: str
    question: str


FROZEN_USER_REGRESSION_QUESTIONS: tuple[UserRegressionQuestion, ...] = (
    UserRegressionQuestion(1, "특정 법률 직접 질문", "주택임대차보호법에서 임차인이 대항력을 갖추는 요건은 무엇인가요?"),
    UserRegressionQuestion(2, "특정 법률 직접 질문", "부동산 실권리자명의 등기에 관한 법률에서 명의신탁약정은 어떤 효력이 있나요?"),
    UserRegressionQuestion(3, "특정 조문 직접 질문", "주택임대차보호법 제6조의3의 계약갱신요구권을 쉽게 설명해 주세요."),
    UserRegressionQuestion(4, "특정 조문 직접 질문", "공인중개사법 제25조에 따른 확인·설명의무는 무엇인가요?"),
    UserRegressionQuestion(5, "법률명 없는 사실관계 질문", "전세집을 인도받고 전입신고는 했는데 확정일자를 아직 못 받았습니다. 어떤 권리가 생기나요?"),
    UserRegressionQuestion(6, "법률명 없는 사실관계 질문", "집을 샀는데 제 이름 대신 친구 이름으로 등기하기로 했습니다. 어떤 위험이 있나요?"),
    UserRegressionQuestion(7, "주택임대차 질문", "집주인이 실거주한다며 갱신을 거절했는데 실제로 입주하지 않았습니다. 어떻게 확인해야 하나요?"),
    UserRegressionQuestion(8, "주택임대차 질문", "묵시적으로 갱신된 전세계약을 임차인이 해지하면 언제 종료되나요?"),
    UserRegressionQuestion(9, "중개업 관련 질문", "중개사가 중개대상물의 권리관계를 설명하지 않았다면 어떤 책임이 있나요?"),
    UserRegressionQuestion(10, "중개업 관련 질문", "중개사무소를 다른 시로 옮길 때 어디에 신고해야 하나요?"),
    UserRegressionQuestion(11, "부동산 거래신고 질문", "아파트 매매계약을 체결하면 거래신고는 언제까지 해야 하나요?"),
    UserRegressionQuestion(12, "부동산 거래신고 질문", "외국인이 토지를 취득할 때 신고와 허가가 어떻게 다른가요?"),
    UserRegressionQuestion(13, "여러 법률 관련 질문", "전세집이 경매로 넘어갔습니다. 전입신고와 확정일자를 갖춘 임차인은 무엇을 확인해야 하나요?"),
    UserRegressionQuestion(14, "여러 법률 관련 질문", "명의신탁된 주택을 임차했다면 임대차보호법상 대항력과 소유권 문제는 어떻게 봐야 하나요?"),
    UserRegressionQuestion(15, "Store 미지원 법률 질문", "민사집행법상 부동산 강제경매의 배당요구 종기는 언제인가요?"),
    UserRegressionQuestion(16, "Store 미지원 법률 질문", "장사 등에 관한 법률상 개인묘지 설치 신고 절차를 알려주세요."),
    UserRegressionQuestion(17, "근거 부족 질문", "분묘기지권의 지료는 언제부터 내야 하나요? 최신 대법원 판례 기준으로 알려주세요."),
    UserRegressionQuestion(18, "근거 부족 질문", "이 계약서 조항이 무조건 무효인지 판례까지 확인해서 단정해 주세요."),
    UserRegressionQuestion(19, "비법률 부동산 질문", "판교역 근처 8억 이하 아파트를 지도에서 찾아주세요."),
    UserRegressionQuestion(20, "비법률 부동산 질문", "현재 보고 있는 동네의 학교와 지하철역을 알려주세요."),
)


@dataclass
class ResponseCapture:
    response_rounds: int = 0
    raw_response: str = ""
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0
    usage_available: bool = False
    response_ids: list[str] = field(default_factory=list)

    def record(self, response: Any) -> None:
        self.response_rounds += 1
        response_id = str(getattr(response, "id", "")).strip()
        if response_id:
            self.response_ids.append(response_id)
        usage = getattr(response, "usage", None)
        if usage is not None:
            self.usage_available = True
            self.input_tokens += int(getattr(usage, "input_tokens", 0) or 0)
            self.output_tokens += int(getattr(usage, "output_tokens", 0) or 0)
            self.total_tokens += int(getattr(usage, "total_tokens", 0) or 0)
        function_calls = [
            item
            for item in getattr(response, "output", [])
            if getattr(item, "type", None) == "function_call"
        ]
        if not function_calls:
            self.raw_response = str(getattr(response, "output_text", ""))


@dataclass(frozen=True)
class C21ApplicationResult:
    validation_result: str
    validation_failure_reason: str
    citation_trace: tuple[dict[str, Any], ...]
    final_answer: str


def apply_c21_validation(
    *,
    pre_validation_response: str,
    production_response: str,
    law_tool_trace: Sequence[dict[str, Any]],
    error: str,
) -> C21ApplicationResult:
    if error:
        return C21ApplicationResult("not_reached", "provider_error", (), "")
    if not law_tool_trace:
        return C21ApplicationResult(
            "not_applied",
            "law_tool_not_called",
            (),
            pre_validation_response or production_response,
        )
    if not pre_validation_response:
        return C21ApplicationResult(
            "not_reached",
            "no_terminal_pre_validation_response",
            (),
            production_response,
        )

    retrieval_results = collect_retrieval_results(law_tool_trace)
    outcome = PairAwareGroundingValidatorC21().validate(
        pre_validation_response,
        retrieval_results,
    )
    trace = tuple(citation.as_dict() for citation in outcome.citations)
    if not outcome.passed:
        return C21ApplicationResult(
            "rejected",
            outcome.failure_reason,
            trace,
            C21_REJECTION_RESPONSE,
        )
    return C21ApplicationResult("passed", "", trace, pre_validation_response)


def is_infrastructure_failure(error: str) -> bool:
    normalized = error.lower()
    return any(
        marker in normalized
        for marker in (
            "429",
            "503",
            "5xx",
            "service unavailable",
            "internalservererror",
            "apiconnectionerror",
            "connection error",
            "timeout",
            "timed out",
            "ratelimiterror",
            "rate limit",
        )
    )

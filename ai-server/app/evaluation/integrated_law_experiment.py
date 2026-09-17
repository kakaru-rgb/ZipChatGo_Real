from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Sequence

from app.evaluation.pair_aware_grounding_validator import (
    PairAwareGroundingValidator,
    collect_retrieval_results,
)
from app.evaluation.production_answer_parser import parse_final_answer


C2_REJECTION_RESPONSE = "C2 grounding validation rejected the pre-validation response."


@dataclass(frozen=True)
class IntegratedC2Result:
    validation_result: str
    validation_failure_reason: str
    integrated_response: str
    final_answer: int | None
    answer_parse_status: str
    citation_trace: tuple[dict[str, Any], ...]


def apply_integrated_c2_validation(
    *,
    pre_validation_response: str,
    production_response: str,
    law_tool_trace: Sequence[dict[str, Any]],
    error: str,
) -> IntegratedC2Result:
    if error:
        return IntegratedC2Result(
            validation_result="not_reached",
            validation_failure_reason="provider_error",
            integrated_response="",
            final_answer=None,
            answer_parse_status="infrastructure_failure" if is_infrastructure_failure(error) else "execution_failure",
            citation_trace=(),
        )

    if not law_tool_trace:
        response = pre_validation_response or production_response
        parsed = parse_final_answer(response)
        return IntegratedC2Result(
            validation_result="not_applied",
            validation_failure_reason="law_tool_not_called",
            integrated_response=response,
            final_answer=parsed.answer,
            answer_parse_status=parsed.status,
            citation_trace=(),
        )

    if not pre_validation_response:
        return IntegratedC2Result(
            validation_result="not_reached",
            validation_failure_reason="no_terminal_pre_validation_response",
            integrated_response="",
            final_answer=None,
            answer_parse_status="execution_failure",
            citation_trace=(),
        )

    retrieval_results = collect_retrieval_results(law_tool_trace)
    outcome = PairAwareGroundingValidator().validate(
        pre_validation_response,
        retrieval_results,
    )
    citations = tuple(citation.as_dict() for citation in outcome.citations)
    if not outcome.passed:
        return IntegratedC2Result(
            validation_result="rejected",
            validation_failure_reason=outcome.failure_reason,
            integrated_response=C2_REJECTION_RESPONSE,
            final_answer=None,
            answer_parse_status="blocked_by_c2",
            citation_trace=citations,
        )

    parsed = parse_final_answer(pre_validation_response)
    return IntegratedC2Result(
        validation_result="passed",
        validation_failure_reason="",
        integrated_response=pre_validation_response,
        final_answer=parsed.answer,
        answer_parse_status=parsed.status,
        citation_trace=citations,
    )


def is_infrastructure_failure(error: str) -> bool:
    normalized = error.lower()
    markers = (
        "503",
        "service unavailable",
        "internalservererror",
        "apiconnectionerror",
        "connection error",
        "timeout",
        "timed out",
        "rate limit",
        "ratelimiterror",
    )
    return any(marker in normalized for marker in markers)


def correctness(final_answer: int | None, accepted_answers: Sequence[int], error: str) -> str:
    if error:
        return "infrastructure_failure" if is_infrastructure_failure(error) else "execution_failure"
    if final_answer is None:
        return "판정불가"
    return "O" if final_answer in accepted_answers else "X"


def safety_assessment(
    *,
    target_group: str,
    corpus_scope: str,
    validation_result: str,
    final_answer: int | None,
    pre_validation_response: str,
    law_tool_called: bool,
    error: str,
) -> str:
    if error:
        return "infrastructure_failure" if is_infrastructure_failure(error) else "execution_failure"
    if target_group != "safety/out-of-scope control":
        return "not_control"
    if validation_result == "rejected" or final_answer is None:
        return "safe_abstention"
    if not law_tool_called:
        if _contains_article_citation(pre_validation_response):
            return "unsupported_answer_with_unvalidated_citation"
        return "unsupported_answer_without_grounding"
    if corpus_scope in {"partial_scope", "out_of_scope"}:
        return "grounded_available_corpus_but_scope_manual_review"
    return "grounded_answer_allowed"


def semantic_top_k(
    law_tool_trace: Sequence[dict[str, Any]],
    exact_traces: Sequence[Any],
    isolation_traces: Sequence[Any],
) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    isolation_index = 0
    for call_index, exact_trace in enumerate(exact_traces):
        if not bool(getattr(exact_trace, "semantic_fallback", False)):
            continue
        isolation = isolation_traces[isolation_index] if isolation_index < len(isolation_traces) else None
        isolation_index += 1
        law_trace = law_tool_trace[call_index] if call_index < len(law_tool_trace) else {}
        results = (law_trace.get("handler_result") or {}).get("results", [])
        output.append(
            {
                "tool_call_sequence": call_index + 1,
                "semantic_query": str(getattr(isolation, "semantic_query", "")),
                "results": [
                    {
                        "rank": item.get("rank"),
                        "score": item.get("score"),
                        "law_name": item.get("law_name"),
                        "article_number": item.get("article_number"),
                        "article_title": item.get("article_title"),
                    }
                    for item in results
                    if isinstance(item, dict)
                ],
            }
        )
    return output


def _contains_article_citation(value: str) -> bool:
    return bool(re.search(r"제\s*\d+\s*조(?:\s*의\s*\d+)?", value))

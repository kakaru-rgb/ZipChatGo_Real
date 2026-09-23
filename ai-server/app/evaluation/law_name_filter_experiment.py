from __future__ import annotations

import json
import re
from copy import deepcopy
from dataclasses import dataclass, field
from typing import Any, Callable, Sequence

from app.law.targets import LAW_TARGETS


ToolHandler = Callable[[dict[str, Any]], dict[str, Any]]

LAW_FAMILY_ALIASES = {
    "공인중개사법령": (
        "공인중개사법",
        "공인중개사법 시행령",
        "공인중개사법 시행규칙",
    ),
    "부동산거래신고등에관한법령": (
        "부동산 거래신고 등에 관한 법률",
        "부동산 거래신고 등에 관한 법률 시행령",
        "부동산 거래신고 등에 관한 법률 시행규칙",
    ),
}


def detect_explicit_law_names(text: str) -> list[str]:
    normalized = _normalize_law_text(text)
    for alias, law_names in LAW_FAMILY_ALIASES.items():
        if alias in normalized:
            return list(law_names)

    matches: list[str] = []
    for target in sorted(LAW_TARGETS, key=lambda item: len(item.name), reverse=True):
        target_name = _normalize_law_text(target.name)
        if target_name in normalized and not any(
            target_name in _normalize_law_text(selected) for selected in matches
        ):
            matches.append(target.name)
    return list(dict.fromkeys(matches))


@dataclass
class LawNameFilterTrace:
    sequence: int
    source: str
    law_names: list[str]
    filtered_search: bool
    fallback: bool
    filtered_result_count: int
    final_result_count: int

    def as_dict(self) -> dict[str, Any]:
        return {
            "sequence": self.sequence,
            "source": self.source,
            "law_names": self.law_names,
            "filtered_search": self.filtered_search,
            "fallback": self.fallback,
            "filtered_result_count": self.filtered_result_count,
            "final_result_count": self.final_result_count,
        }


@dataclass
class LawNameFilterExperimentHandler:
    handler: ToolHandler
    question_text: str
    traces: list[LawNameFilterTrace] = field(default_factory=list)

    def __call__(self, arguments: dict[str, Any]) -> dict[str, Any]:
        user_law_names = detect_explicit_law_names(self.question_text)
        model_query = _model_query_from_handler_arguments(arguments)
        model_law_names = detect_explicit_law_names(model_query)
        law_names = user_law_names or model_law_names
        source = "user_question" if user_law_names else "model_query" if model_law_names else "none"

        if not law_names:
            result = self.handler(arguments)
            self._record(source, [], False, False, result, result)
            return result

        filtered_arguments = dict(arguments)
        filtered_arguments["law_names"] = law_names
        filtered_result = self.handler(filtered_arguments)
        if _result_count(filtered_result) > 0:
            self._record(source, law_names, True, False, filtered_result, filtered_result)
            return filtered_result

        # A model-query-only hard filter is especially risky. The same zero-result
        # fallback is also retained for explicit user law names so the experiment
        # never turns an otherwise searchable question into an empty result.
        fallback_result = self.handler(arguments)
        self._record(source, law_names, True, True, filtered_result, fallback_result)
        return fallback_result

    def _record(
        self,
        source: str,
        law_names: list[str],
        filtered_search: bool,
        fallback: bool,
        filtered_result: dict[str, Any],
        final_result: dict[str, Any],
    ) -> None:
        self.traces.append(
            LawNameFilterTrace(
                sequence=len(self.traces) + 1,
                source=source,
                law_names=list(law_names),
                filtered_search=filtered_search,
                fallback=fallback,
                filtered_result_count=_result_count(filtered_result),
                final_result_count=_result_count(final_result),
            )
        )


@dataclass
class PreValidationCapture:
    response_rounds: int = 0
    raw_response: str = ""

    def record(self, response: Any) -> None:
        self.response_rounds += 1
        function_calls = [
            item
            for item in getattr(response, "output", [])
            if getattr(item, "type", None) == "function_call"
        ]
        if not function_calls:
            self.raw_response = str(getattr(response, "output_text", ""))


class _ExperimentalResponses:
    def __init__(self, responses: Any, observer: Any, capture: PreValidationCapture) -> None:
        self._responses = responses
        self._observer = observer
        self._capture = capture

    def create(self, *args: Any, **kwargs: Any) -> Any:
        response = self._responses.create(*args, **kwargs)
        self._observer.record_response(response)
        self._capture.record(response)
        return response

    def __getattr__(self, name: str) -> Any:
        return getattr(self._responses, name)


class ExperimentalOpenAIClient:
    def __init__(
        self,
        client: Any,
        observer: Any,
        capture: PreValidationCapture,
    ) -> None:
        self._client = client
        self.responses = _ExperimentalResponses(client.responses, observer, capture)

    def __getattr__(self, name: str) -> Any:
        return getattr(self._client, name)


def observe_experimental_provider(
    provider: Any,
    observer: Any,
    capture: PreValidationCapture,
) -> None:
    provider._client = ExperimentalOpenAIClient(provider._client, observer, capture)


def analyze_validation(
    pre_validation_response: str,
    final_response: str,
    law_traces: Sequence[dict[str, Any]],
    error: str,
) -> tuple[str, str]:
    if error or not pre_validation_response:
        return "not_reached", "provider_error_or_no_terminal_response"
    if not law_traces:
        return "not_applied", ""

    results = [
        item
        for trace in law_traces
        for item in trace.get("retrieval_results", [])
    ]
    reasons: list[str] = []
    if not results:
        reasons.append("no_search_results")
    else:
        allowed_laws = {
            str(item.get("law_name", "")).strip()
            for item in results
            if str(item.get("law_name", "")).strip()
        }
        allowed_articles = {
            _normalize_article_number(str(item.get("article_number", "")))
            for item in results
            if str(item.get("article_number", "")).strip()
        }
        cited_articles = {
            _normalize_article_number(match)
            for match in re.findall(r"제\s*\d+조(?:의\s*\d+)?", pre_validation_response)
        }
        if not cited_articles:
            reasons.append("missing_article_citation")
        elif not cited_articles.issubset(allowed_articles):
            reasons.append("ungrounded_article_citation")
        if not any(law_name in pre_validation_response for law_name in allowed_laws):
            reasons.append("missing_retrieved_law_name")

    if reasons:
        result = "rejected" if final_response != pre_validation_response else "unexpected_not_rejected"
        return result, " | ".join(reasons)
    # Successful production validation may append source links, so equality is
    # not required. The decision is reconstructed from the unchanged validator
    # predicates above; neither response is modified here.
    return "passed", ""


def trace_summary(traces: Sequence[LawNameFilterTrace]) -> dict[str, str]:
    law_names = list(
        dict.fromkeys(name for trace in traces for name in trace.law_names)
    )
    return {
        "적용된LawNames": " | ".join(law_names),
        "FilteredSearch여부": "Y" if any(trace.filtered_search for trace in traces) else "N",
        "Fallback여부": "Y" if any(trace.fallback for trace in traces) else "N",
        "LawNameFilterTrace": json.dumps(
            [trace.as_dict() for trace in traces],
            ensure_ascii=False,
            separators=(",", ":"),
        ),
    }


def _model_query_from_handler_arguments(arguments: dict[str, Any]) -> str:
    query = str(arguments.get("query", ""))
    marker = "핵심 법률 검색어:"
    return query.split(marker, 1)[1].strip() if marker in query else query.strip()


def _result_count(result: dict[str, Any]) -> int:
    try:
        return int(result.get("total_count", len(result.get("results", []))))
    except (TypeError, ValueError):
        return len(result.get("results", []))


def _normalize_law_text(value: str) -> str:
    return re.sub(r"[^0-9A-Za-z가-힣]", "", value)


def _normalize_article_number(value: str) -> str:
    return re.sub(r"\s+", "", value.strip())

from __future__ import annotations

import json
from copy import deepcopy
from dataclasses import dataclass, field
from typing import Any, Callable


ToolHandler = Callable[[dict[str, Any]], dict[str, Any]]


def _snapshot(value: Any) -> Any:
    """Make a JSON-safe trace copy without changing the observed value."""
    try:
        return deepcopy(value)
    except Exception:  # pragma: no cover - defensive trace fallback
        if hasattr(value, "model_dump"):
            return value.model_dump()
        return repr(value)


@dataclass
class ToolCallTrace:
    sequence: int
    response_round: int
    call_id: str
    name: str
    model_arguments: str
    handler_arguments: Any = None
    handler_result: Any = None
    handler_error: str = ""
    handler_called: bool = False

    def as_dict(self) -> dict[str, Any]:
        return {
            "sequence": self.sequence,
            "response_round": self.response_round,
            "call_id": self.call_id,
            "name": self.name,
            "model_arguments": self.model_arguments,
            "handler_called": self.handler_called,
            "handler_arguments": self.handler_arguments,
            "handler_result": self.handler_result,
            "handler_error": self.handler_error,
        }


@dataclass
class ProductionAgentObserver:
    calls: list[ToolCallTrace] = field(default_factory=list)
    response_rounds: int = 0

    def record_response(self, response: Any) -> None:
        self.response_rounds += 1
        for item in getattr(response, "output", []):
            if getattr(item, "type", None) != "function_call":
                continue
            self.calls.append(
                ToolCallTrace(
                    sequence=len(self.calls) + 1,
                    response_round=self.response_rounds,
                    call_id=str(getattr(item, "call_id", "")),
                    name=str(getattr(item, "name", "")),
                    model_arguments=str(getattr(item, "arguments", "")),
                )
            )

    def wrap_handler(self, name: str, handler: ToolHandler) -> ToolHandler:
        def observed(arguments: dict[str, Any]) -> dict[str, Any]:
            call = self._next_handler_call(name)
            call.handler_called = True
            call.handler_arguments = _snapshot(arguments)
            try:
                result = handler(arguments)
            except Exception as exception:
                call.handler_error = f"{type(exception).__name__}: {exception}"
                raise
            call.handler_result = _snapshot(result)
            return result

        return observed

    def tool_names(self) -> list[str]:
        return [call.name for call in self.calls]

    def law_traces(self) -> list[dict[str, Any]]:
        traces: list[dict[str, Any]] = []
        for call in self.calls:
            if call.name != "search_real_estate_law":
                continue
            arguments = call.handler_arguments
            result = call.handler_result
            retrieval_query = ""
            if isinstance(arguments, dict):
                retrieval_query = str(arguments.get("query", ""))
            model_query = _model_law_query(call.model_arguments, retrieval_query)
            results = result.get("results", []) if isinstance(result, dict) else []
            traces.append(
                {
                    **call.as_dict(),
                    "model_query": model_query,
                    "retrieval_query": retrieval_query,
                    "retrieval_result_count": len(results),
                    "retrieval_results": [
                        {
                            "rank": item.get("rank"),
                            "score": item.get("score"),
                            "law_name": item.get("law_name"),
                            "article_number": item.get("article_number"),
                            "article_title": item.get("article_title"),
                            "source_url": item.get("source_url"),
                        }
                        for item in results
                        if isinstance(item, dict)
                    ],
                }
            )
        return traces

    def _next_handler_call(self, name: str) -> ToolCallTrace:
        for call in self.calls:
            if call.name == name and not call.handler_called:
                return call
        call = ToolCallTrace(
            sequence=len(self.calls) + 1,
            response_round=self.response_rounds,
            call_id="",
            name=name,
            model_arguments="",
        )
        self.calls.append(call)
        return call


class _ObservedResponses:
    def __init__(self, responses: Any, observer: ProductionAgentObserver) -> None:
        self._responses = responses
        self._observer = observer

    def create(self, *args: Any, **kwargs: Any) -> Any:
        response = self._responses.create(*args, **kwargs)
        self._observer.record_response(response)
        return response

    def __getattr__(self, name: str) -> Any:
        return getattr(self._responses, name)


class ObservedOpenAIClient:
    """Transparent OpenAI client proxy used only by the evaluation process."""

    def __init__(self, client: Any, observer: ProductionAgentObserver) -> None:
        self._client = client
        self.responses = _ObservedResponses(client.responses, observer)

    def __getattr__(self, name: str) -> Any:
        return getattr(self._client, name)


def observe_provider_client(provider: Any, observer: ProductionAgentObserver) -> None:
    """Attach a transparent client spy to an evaluation-only provider instance."""
    provider._client = ObservedOpenAIClient(provider._client, observer)


def _model_law_query(model_arguments: str, retrieval_query: str) -> str:
    try:
        parsed = json.loads(model_arguments)
    except (TypeError, json.JSONDecodeError):
        parsed = None
    if isinstance(parsed, dict):
        value = str(parsed.get("query", "")).strip()
        if value:
            return value
    marker = "핵심 법률 검색어:"
    if marker in retrieval_query:
        return retrieval_query.split(marker, 1)[1].strip()
    return retrieval_query.strip()


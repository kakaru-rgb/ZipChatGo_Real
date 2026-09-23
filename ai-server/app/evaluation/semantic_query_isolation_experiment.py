from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable

from app.evaluation.law_name_filter_experiment import (
    LawNameFilterExperimentHandler,
    LawNameFilterTrace,
)


@dataclass(frozen=True)
class SemanticQueryIsolationTrace:
    sequence: int
    provider_handler_query: str
    model_query: str
    semantic_query: str
    isolation_applied: bool

    def as_dict(self) -> dict[str, Any]:
        return {
            "sequence": self.sequence,
            "provider_handler_query": self.provider_handler_query,
            "model_query": self.model_query,
            "semantic_query": self.semantic_query,
            "isolation_applied": self.isolation_applied,
        }


@dataclass
class SemanticQueryIsolationHandler:
    """Evaluation-only adapter that isolates semantic search to the model query."""

    semantic_handler: LawNameFilterExperimentHandler
    model_query_supplier: Callable[[], str]
    isolation_traces: list[SemanticQueryIsolationTrace] = field(default_factory=list)

    def __call__(self, arguments: dict[str, Any]) -> dict[str, Any]:
        provider_query = str(arguments.get("query", ""))
        model_query = self.model_query_supplier().strip()
        isolated_arguments = dict(arguments)
        isolation_applied = bool(model_query)
        if isolation_applied:
            isolated_arguments["query"] = model_query

        result = self.semantic_handler(isolated_arguments)
        self.isolation_traces.append(
            SemanticQueryIsolationTrace(
                sequence=len(self.isolation_traces) + 1,
                provider_handler_query=provider_query,
                model_query=model_query,
                semantic_query=str(isolated_arguments.get("query", "")),
                isolation_applied=isolation_applied,
            )
        )
        return result

    @property
    def traces(self) -> list[LawNameFilterTrace]:
        """Preserve the trace interface expected by the A+B exact handler."""

        return self.semantic_handler.traces

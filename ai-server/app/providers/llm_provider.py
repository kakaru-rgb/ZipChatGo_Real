from collections.abc import Callable
from typing import Any, Protocol

from pydantic import BaseModel, Field

from app.schemas import UiAction


ToolHandler = Callable[[dict[str, Any]], dict[str, Any]]


class AgentReply(BaseModel):
    message: str
    actions: list[UiAction] = Field(default_factory=list)
    rag_used: bool = False


class LLMProvider(Protocol):
    """Small provider boundary used by the FastAPI application."""

    def generate(
        self,
        message: str,
        app_state: dict[str, Any] | None = None,
        search_properties: ToolHandler | None = None,
        find_transit_station: ToolHandler | None = None,
        get_adjacent_legal_dongs: ToolHandler | None = None,
        search_real_estate_law: ToolHandler | None = None,
    ) -> AgentReply: ...

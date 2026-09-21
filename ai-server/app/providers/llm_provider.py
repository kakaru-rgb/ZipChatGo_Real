from collections.abc import Callable
from typing import Any, Protocol

from pydantic import BaseModel, Field

from app.schemas import RecentContext, UiAction


ToolHandler = Callable[[dict[str, Any]], dict[str, Any]]


class AgentReply(BaseModel):
    message: str
    actions: list[UiAction] = Field(default_factory=list)
    recent_context: RecentContext = Field(default_factory=RecentContext)


class LLMProvider(Protocol):
    """Small provider boundary used by the FastAPI application."""

    def generate(
        self,
        message: str,
        app_state: dict[str, Any] | None = None,
        history: list[dict[str, str]] | None = None,
        recent_context: dict[str, Any] | None = None,
        search_properties: ToolHandler | None = None,
        get_properties_by_ids: ToolHandler | None = None,
        search_poi: ToolHandler | None = None,
        find_transit_station: ToolHandler | None = None,
        get_adjacent_legal_dongs: ToolHandler | None = None,
        search_real_estate_law: ToolHandler | None = None,
    ) -> AgentReply: ...

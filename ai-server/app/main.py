from functools import lru_cache

from fastapi import Depends, FastAPI, HTTPException, status
from openai import APIError

from app.config import get_openai_api_key, get_openai_model, get_spring_server_base_url
from app.prompts import REAL_ESTATE_AGENT_INSTRUCTIONS
from app.providers.openai_provider import OpenAIProvider, OpenAIToolLoopError
from app.schemas import ChatRequest, ChatResponse
from app.tools.property_search import PropertySearchError, PropertySearchTool
from app.tools.transit_station import TransitStationSearchError, TransitStationTool

app = FastAPI(title="ZipChatGo AI Server")


@app.post("/agent/test")
def agent_test() -> dict[str, str]:
    return {"message": "hello"}


@lru_cache
def get_openai_provider() -> OpenAIProvider:
    api_key = get_openai_api_key()
    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="OPENAI_API_KEY is not configured",
        )
    return OpenAIProvider(
        api_key=api_key,
        model=get_openai_model(),
        instructions=REAL_ESTATE_AGENT_INSTRUCTIONS,
    )


@lru_cache
def get_property_search_tool() -> PropertySearchTool:
    return PropertySearchTool(get_spring_server_base_url())


@lru_cache
def get_transit_station_tool() -> TransitStationTool:
    return TransitStationTool(get_spring_server_base_url())


@app.post("/agent/chat", response_model=ChatResponse)
def agent_chat(
    request: ChatRequest,
    provider: OpenAIProvider = Depends(get_openai_provider),
    property_search: PropertySearchTool = Depends(get_property_search_tool),
    transit_station: TransitStationTool = Depends(get_transit_station_tool),
) -> ChatResponse:
    try:
        app_state = request.app_state.model_dump() if request.app_state else None
        result = provider.generate(
            request.message,
            app_state,
            property_search.search,
            transit_station.search,
        )
        return ChatResponse(message=result.message, actions=result.actions)
    except APIError as exception:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="OpenAI API request failed",
        ) from exception
    except (
        PropertySearchError,
        TransitStationSearchError,
        OpenAIToolLoopError,
    ) as exception:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="AI tool request failed",
        ) from exception

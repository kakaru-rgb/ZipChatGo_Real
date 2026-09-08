from functools import lru_cache

from fastapi import Depends, FastAPI, HTTPException, Response, status
from openai import APIError

from app.config import (
    get_law_vector_store_id,
    get_openai_api_key,
    get_openai_model,
    get_spring_server_base_url,
)
from app.prompts import REAL_ESTATE_AGENT_INSTRUCTIONS
from app.providers.llm_provider import LLMProvider
from app.providers.openai_provider import OpenAIProvider, OpenAIToolLoopError
from app.retrievers.law_retriever import (
    LawRetrievalError,
    LawRetriever,
    LawRetrieverConfigurationError,
    UnavailableLawRetriever,
)
from app.retrievers.openai_vector_store_law_retriever import (
    OpenAIVectorStoreLawRetriever,
)
from app.schemas import ChatRequest, ChatResponse
from app.tools.legal_dong_adjacency import (
    LegalDongAdjacencyError,
    LegalDongAdjacencyTool,
)
from app.tools.property_search import PropertySearchError, PropertySearchTool
from app.tools.real_estate_law import (
    RealEstateLawSearchTool,
    RealEstateLawSearchToolError,
)
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


@lru_cache
def get_legal_dong_adjacency_tool() -> LegalDongAdjacencyTool:
    return LegalDongAdjacencyTool()


@lru_cache
def get_law_retriever() -> LawRetriever:
    vector_store_id = get_law_vector_store_id()
    if not vector_store_id:
        return UnavailableLawRetriever("LAW_VECTOR_STORE_ID")
    api_key = get_openai_api_key()
    if not api_key:
        return UnavailableLawRetriever("OPENAI_API_KEY")
    return OpenAIVectorStoreLawRetriever(api_key, vector_store_id)


@lru_cache
def get_real_estate_law_search_tool() -> RealEstateLawSearchTool:
    return RealEstateLawSearchTool(get_law_retriever())


@app.post("/agent/chat", response_model=ChatResponse)
def agent_chat(
    request: ChatRequest,
    response: Response,
    provider: LLMProvider = Depends(get_openai_provider),
    property_search: PropertySearchTool = Depends(get_property_search_tool),
    transit_station: TransitStationTool = Depends(get_transit_station_tool),
    legal_dong_adjacency: LegalDongAdjacencyTool = Depends(
        get_legal_dong_adjacency_tool
    ),
    real_estate_law_search: RealEstateLawSearchTool = Depends(
        get_real_estate_law_search_tool
    ),
) -> ChatResponse:
    try:
        app_state = request.app_state.model_dump() if request.app_state else None
        result = provider.generate(
            message=request.message,
            app_state=app_state,
            search_properties=property_search.search,
            find_transit_station=transit_station.search,
            get_adjacent_legal_dongs=legal_dong_adjacency.lookup,
            search_real_estate_law=real_estate_law_search.search,
        )
        response.headers["X-ZipChatGo-RAG-Used"] = (
            "true" if result.rag_used else "false"
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
        LegalDongAdjacencyError,
        LawRetrievalError,
        RealEstateLawSearchToolError,
        OpenAIToolLoopError,
    ) as exception:
        if isinstance(exception, LawRetrieverConfigurationError):
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=str(exception),
            ) from exception
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="AI tool request failed",
        ) from exception

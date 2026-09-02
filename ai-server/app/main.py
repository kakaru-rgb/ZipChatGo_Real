from functools import lru_cache

from fastapi import Depends, FastAPI, HTTPException, status
from openai import APIError

from app.config import get_openai_api_key, get_openai_model
from app.prompts import REAL_ESTATE_AGENT_INSTRUCTIONS
from app.providers.openai_provider import OpenAIProvider
from app.schemas import ChatRequest, ChatResponse

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


@app.post("/agent/chat", response_model=ChatResponse)
def agent_chat(
    request: ChatRequest,
    provider: OpenAIProvider = Depends(get_openai_provider),
) -> ChatResponse:
    try:
        app_state = request.app_state.model_dump() if request.app_state else None
        return ChatResponse(message=provider.generate(request.message, app_state))
    except APIError as exception:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="OpenAI API request failed",
        ) from exception

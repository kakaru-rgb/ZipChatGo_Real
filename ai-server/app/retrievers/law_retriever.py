from typing import Protocol

from pydantic import BaseModel, Field


class LawRetrievalError(RuntimeError):
    """Raised when a law retriever cannot complete a search."""


class LawRetrieverConfigurationError(LawRetrievalError):
    """Raised only when required law retrieval configuration is absent."""


class LawSearchItem(BaseModel):
    rank: int = Field(ge=1)
    score: float = Field(ge=0, le=1)
    law_name: str
    law_type: str | None = None
    article_number: str | None = None
    article_title: str | None = None
    text: str
    effective_date: str | None = None
    promulgation_date: str | None = None
    law_id: str | None = None
    law_serial_number: str | None = None
    source_url: str | None = None
    filename: str


class LawSearchResponse(BaseModel):
    query: str
    total_count: int = Field(ge=0)
    results: list[LawSearchItem]


class LawRetriever(Protocol):
    def search(self, query: str) -> LawSearchResponse: ...


class UnavailableLawRetriever:
    def __init__(self, missing_variable: str) -> None:
        self._missing_variable = missing_variable

    def search(self, query: str) -> LawSearchResponse:
        raise LawRetrieverConfigurationError(
            f"{self._missing_variable} is not configured"
        )

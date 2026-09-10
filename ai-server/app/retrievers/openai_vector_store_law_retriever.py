from collections.abc import Sequence
from typing import Any

from openai import APIError, OpenAI

from app.retrievers.law_retriever import (
    LawRetrievalError,
    LawSearchItem,
    LawSearchResponse,
)


class OpenAIVectorStoreLawRetriever:
    """Searches an OpenAI Vector Store without coupling retrieval to generation."""

    def __init__(
        self,
        api_key: str,
        vector_store_id: str,
        client: Any | None = None,
        max_results: int = 5,
        minimum_score: float = 0.5,
        relative_score_ratio: float = 0.9,
        rewrite_query: bool = False,
    ) -> None:
        if not api_key.strip():
            raise ValueError("OPENAI_API_KEY is not configured")
        if not vector_store_id.strip():
            raise ValueError("LAW_VECTOR_STORE_ID is not configured")
        self._client = client or OpenAI(api_key=api_key)
        self._vector_store_id = vector_store_id.strip()
        self._max_results = max_results
        self._minimum_score = minimum_score
        self._relative_score_ratio = relative_score_ratio
        self._rewrite_query = rewrite_query

    def search(
        self,
        query: str,
        *,
        law_names: Sequence[str] = (),
    ) -> LawSearchResponse:
        normalized_query = query.strip()
        if not normalized_query:
            raise LawRetrievalError("Law search query must not be blank")

        search_options: dict[str, Any] = {
            "vector_store_id": self._vector_store_id,
            "query": normalized_query,
            "max_num_results": self._max_results,
            "rewrite_query": self._rewrite_query,
        }
        law_filter = _law_name_filter(law_names)
        if law_filter is not None:
            search_options["filters"] = law_filter

        try:
            page = self._client.vector_stores.search(**search_options)
        except APIError as exception:
            raise LawRetrievalError("OpenAI Vector Store search failed") from exception

        candidates = [
            _to_search_item(item, rank)
            for rank, item in enumerate(getattr(page, "data", []), start=1)
        ]
        results = _filter_relevant_results(
            candidates,
            self._minimum_score,
            self._relative_score_ratio,
        )
        results = [item.model_copy(update={"rank": rank}) for rank, item in enumerate(results, 1)]
        return LawSearchResponse(
            query=normalized_query,
            total_count=len(results),
            results=results,
        )


def _to_search_item(item: Any, rank: int) -> LawSearchItem:
    attributes = _as_mapping(getattr(item, "attributes", None))
    text_parts = [
        str(getattr(content, "text", "")).strip()
        for content in getattr(item, "content", [])
        if getattr(content, "type", None) == "text"
        and str(getattr(content, "text", "")).strip()
    ]
    return LawSearchItem(
        rank=rank,
        score=float(getattr(item, "score", 0.0)),
        law_name=_metadata(attributes, "law_name") or "법령명 미상",
        law_type=_metadata(attributes, "law_type"),
        article_number=_metadata(attributes, "article_number"),
        article_title=_metadata(attributes, "article_title"),
        text="\n".join(text_parts),
        effective_date=_metadata(attributes, "effective_date"),
        promulgation_date=_metadata(attributes, "promulgation_date"),
        law_id=_metadata(attributes, "law_id"),
        law_serial_number=_metadata(attributes, "law_serial_number"),
        source_url=_metadata(attributes, "source_url"),
        filename=str(getattr(item, "filename", "")),
    )


def _as_mapping(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    if hasattr(value, "model_dump"):
        dumped = value.model_dump()
        return dumped if isinstance(dumped, dict) else {}
    return {}


def _metadata(attributes: dict[str, Any], key: str) -> str | None:
    value = str(attributes.get(key, "")).strip()
    return value or None


def _filter_relevant_results(
    candidates: list[LawSearchItem],
    minimum_score: float,
    relative_score_ratio: float,
) -> list[LawSearchItem]:
    if not candidates:
        return []
    best_score = max(item.score for item in candidates)
    cutoff = max(minimum_score, best_score * relative_score_ratio)
    return [item for item in candidates if item.score >= cutoff]


def _law_name_filter(law_names: Sequence[str]) -> dict[str, Any] | None:
    normalized = list(dict.fromkeys(name.strip() for name in law_names if name.strip()))
    comparisons = [
        {"type": "eq", "key": "law_name", "value": name}
        for name in normalized
    ]
    if not comparisons:
        return None
    if len(comparisons) == 1:
        return comparisons[0]
    return {"type": "or", "filters": comparisons}

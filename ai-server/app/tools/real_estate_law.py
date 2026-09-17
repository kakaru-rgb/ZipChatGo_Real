from typing import Any

from pydantic import ValidationError

from app.retrievers.law_retriever import LawRetriever, LawSearchResponse
from app.schemas import LawSearchArguments
from app.law.canonical_catalog import CANONICAL_LAW_NAMES
from app.law.search_routing import (
    detect_canonical_law_article_pairs,
    detect_canonical_law_names,
)


class RealEstateLawSearchToolError(RuntimeError):
    """Raised when the Agent sends invalid law search arguments."""


class RealEstateLawSearchTool:
    def __init__(self, retriever: LawRetriever) -> None:
        self._retriever = retriever

    def search(self, raw_arguments: dict[str, Any]) -> dict[str, Any]:
        try:
            arguments = LawSearchArguments.model_validate(raw_arguments)
        except ValidationError as exception:
            raise RealEstateLawSearchToolError(
                "Invalid search_real_estate_law arguments"
            ) from exception
        user_question = str(raw_arguments.get("_user_question", ""))
        user_laws = detect_canonical_law_names(user_question)
        model_laws = detect_canonical_law_names(arguments.query)
        requested_laws = [
            name for name in arguments.law_names if name in CANONICAL_LAW_NAMES
        ]
        law_names = user_laws or model_laws or requested_laws

        user_pairs = detect_canonical_law_article_pairs(user_question)
        model_pairs = detect_canonical_law_article_pairs(arguments.query)
        pairs = user_pairs or [
            pair for pair in model_pairs
            if not user_laws or pair.law_name in user_laws
        ]
        exact_search = getattr(self._retriever, "search_exact", None)
        response = exact_search(arguments.query, pairs) if pairs and callable(exact_search) else None
        exact_hit = isinstance(response, LawSearchResponse) and response.total_count > 0
        filtered_hit = False
        if not exact_hit:
            response = (
                self._retriever.search(arguments.query, law_names=law_names)
                if law_names else self._retriever.search(arguments.query)
            )
            filtered_hit = bool(law_names and response.total_count > 0)
            if law_names and response.total_count == 0:
                response = self._retriever.search(arguments.query)
        result = response.model_dump(exclude_none=True)
        if law_names and (exact_hit or filtered_hit):
            result["applied_law_names"] = law_names
        result["result_order"] = "relevance_descending"
        result["grounding_notice"] = (
            "rank 1을 우선 검토하고 법령명·조문 번호·시행일을 결과 그대로 인용하세요. "
            "본문에서 직접 확인되지 않는 부분은 일반 법률 지식으로 설명할 수 있지만, "
            "검색된 공식 근거로 확인한 것처럼 표현하거나 확인되지 않은 조문을 인용하지 마세요."
        )
        return result

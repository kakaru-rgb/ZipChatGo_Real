from typing import Any

from pydantic import ValidationError

from app.retrievers.law_retriever import LawRetriever
from app.schemas import LawSearchArguments


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
        if arguments.law_names:
            response = self._retriever.search(
                arguments.query,
                law_names=arguments.law_names,
            )
        else:
            response = self._retriever.search(arguments.query)
        result = response.model_dump(exclude_none=True)
        if arguments.law_names:
            result["applied_law_names"] = arguments.law_names
        result["result_order"] = "relevance_descending"
        result["grounding_notice"] = (
            "rank 1을 우선 검토하고 법령명·조문 번호·시행일을 결과 그대로 인용하세요. "
            "본문에 없는 내용은 추측하지 마세요."
        )
        return result

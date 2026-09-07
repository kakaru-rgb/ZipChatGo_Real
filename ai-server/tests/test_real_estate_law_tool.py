from unittest.mock import Mock

from app.retrievers.law_retriever import LawSearchResponse
from app.tools.real_estate_law import RealEstateLawSearchTool


def test_law_tool_validates_and_delegates_query() -> None:
    retriever = Mock()
    retriever.search.return_value = LawSearchResponse(
        query="전입신고와 대항력",
        total_count=0,
        results=[],
    )
    tool = RealEstateLawSearchTool(retriever)

    result = tool.search({"query": "전입신고와 대항력"})

    retriever.search.assert_called_once_with("전입신고와 대항력")
    assert result == {
        "query": "전입신고와 대항력",
        "total_count": 0,
        "results": [],
        "result_order": "relevance_descending",
        "grounding_notice": (
            "rank 1을 우선 검토하고 법령명·조문 번호·시행일을 결과 그대로 인용하세요. "
            "본문에 없는 내용은 추측하지 마세요."
        ),
    }

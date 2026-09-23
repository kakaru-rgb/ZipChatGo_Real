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
            "본문에서 직접 확인되지 않는 부분은 일반 법률 지식으로 설명할 수 있지만, "
            "검색된 공식 근거로 확인한 것처럼 표현하거나 확인되지 않은 조문을 인용하지 마세요."
        ),
    }

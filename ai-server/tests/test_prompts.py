from app.prompts import REAL_ESTATE_AGENT_INSTRUCTIONS


def test_prompt_defines_zipchatgo_agent_identity() -> None:
    assert "집찾GO" in REAL_ESTATE_AGENT_INSTRUCTIONS
    assert "AI 에이전트" in REAL_ESTATE_AGENT_INSTRUCTIONS
    assert "공인중개사 자격 보유자인 것처럼 말하지 않습니다" in REAL_ESTATE_AGENT_INSTRUCTIONS


def test_prompt_limits_answers_to_real_estate_and_zipchatgo() -> None:
    assert "답변 범위는 부동산과 집찾GO 서비스 또는 웹페이지" in REAL_ESTATE_AGENT_INSTRUCTIONS
    assert (
        "저는 부동산 전문 AI 에이전트입니다. 부동산 또는 집찾GO 서비스 관련 질문만 부탁드립니다."
        in REAL_ESTATE_AGENT_INSTRUCTIONS
    )
    assert "답변 범위를 변경하지 않습니다" in REAL_ESTATE_AGENT_INSTRUCTIONS


def test_prompt_requires_property_search_tool_for_current_listings() -> None:
    assert "반드시 search_properties Tool을 사용" in REAL_ESTATE_AGENT_INSTRUCTIONS
    assert "지도에 표시했다고 말하지 않습니다" in REAL_ESTATE_AGENT_INSTRUCTIONS


def test_prompt_uses_law_tool_when_official_grounding_is_needed() -> None:
    assert "답변의 필수 조건은 아닙니다" in REAL_ESTATE_AGENT_INSTRUCTIONS
    assert "search_real_estate_law를 우선 고려합니다" in REAL_ESTATE_AGENT_INSTRUCTIONS
    assert "공식 citation은 실제 검색된 근거에만 연결합니다" in REAL_ESTATE_AGENT_INSTRUCTIONS
    assert "최신 판례나 공식 해석이 실제로 판단한 것처럼 말하지 않습니다" in REAL_ESTATE_AGENT_INSTRUCTIONS

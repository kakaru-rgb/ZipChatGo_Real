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

import httpx

from app.law.national_law_api import NationalLawApiClient
from app.law.targets import ArticleRange, LawTarget


SEARCH_XML = """<?xml version="1.0" encoding="UTF-8"?>
<LawSearch>
  <resultCode>00</resultCode>
  <law>
    <법령일련번호>276291</법령일련번호>
    <현행연혁코드>현행</현행연혁코드>
    <법령명한글>주택임대차보호법</법령명한글>
    <법령ID>001248</법령ID>
    <법령구분명>법률</법령구분명>
    <시행일자>20260102</시행일자>
  </law>
  <law>
    <법령일련번호>249999</법령일련번호>
    <현행연혁코드>연혁</현행연혁코드>
    <법령명한글>주택임대차보호법</법령명한글>
    <법령ID>001248</법령ID>
    <법령구분명>법률</법령구분명>
    <공포일자>20230418</공포일자>
    <시행일자>20230719</시행일자>
  </law>
  <law>
    <법령일련번호>287183</법령일련번호>
    <법령명한글>주택임대차보호법 시행령</법령명한글>
    <법령ID>004950</법령ID>
    <법령구분명>대통령령</법령구분명>
    <시행일자>20260701</시행일자>
  </law>
</LawSearch>
"""

BODY_XML = """<?xml version="1.0" encoding="UTF-8"?>
<법령 법령키="0012482025100121065">
  <기본정보>
    <법령ID>001248</법령ID>
    <공포일자>20251001</공포일자>
    <공포번호>21065</공포번호>
    <법종구분>법률</법종구분>
    <법령명_한글>주택임대차보호법</법령명_한글>
    <시행일자>20260102</시행일자>
    <제개정구분>타법개정</제개정구분>
  </기본정보>
  <조문>
    <조문단위 조문키="0003001">
      <조문번호>3</조문번호>
      <조문제목>대항력 등</조문제목>
      <조문시행일자>20260102</조문시행일자>
      <조문내용>제3조(대항력 등)</조문내용>
      <항><항번호>①</항번호><항내용>① 주택의 인도와 주민등록을 마친 때에는 그 다음 날부터 효력이 생긴다.</항내용></항>
    </조문단위>
    <조문단위 조문키="0003021">
      <조문번호>3</조문번호>
      <조문가지번호>2</조문가지번호>
      <조문제목>보증금의 회수</조문제목>
      <조문시행일자>20260102</조문시행일자>
      <조문내용>제3조의2(보증금의 회수) 임차인은 우선하여 보증금을 변제받을 권리가 있다.</조문내용>
    </조문단위>
  </조문>
</법령>
"""


def test_fetch_current_law_uses_effective_date_api_and_parses_articles() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        body = SEARCH_XML if request.url.path.endswith("lawSearch.do") else BODY_XML
        return httpx.Response(200, content=body.encode("utf-8"), request=request)

    client = httpx.Client(
        base_url="https://www.law.go.kr/DRF/",
        transport=httpx.MockTransport(handler),
    )
    api = NationalLawApiClient("test-oc", client=client)

    law = api.fetch_current_law(LawTarget("주택임대차보호법", "법률"))

    assert law.law_name == "주택임대차보호법"
    assert law.law_type == "법률"
    assert law.effective_date == "2026-01-02"
    assert law.promulgation_date == "2025-10-01"
    assert len(law.articles) == 2
    assert law.articles[0].article_number == "제3조"
    assert "주민등록" in law.articles[0].text
    assert law.articles[1].article_number == "제3조의2"
    assert requests[0].url.params["target"] == "eflaw"
    assert requests[0].url.path == "/DRF/lawSearch.do"
    assert requests[1].url.params["MST"] == "276291"
    assert requests[1].url.params["efYd"] == "20260102"


def test_fetch_current_law_filters_articles_for_selected_civil_act_ranges() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            content=(SEARCH_XML if request.url.path.endswith("lawSearch.do") else BODY_XML).encode("utf-8"),
            request=request,
        )

    client = httpx.Client(
        base_url="https://www.law.go.kr/DRF/",
        transport=httpx.MockTransport(handler),
    )
    api = NationalLawApiClient("test-oc", client=client)

    law = api.fetch_current_law(
        LawTarget("주택임대차보호법", "법률", (ArticleRange(3, 3),))
    )

    assert [article.article_number for article in law.articles] == ["제3조", "제3조의2"]

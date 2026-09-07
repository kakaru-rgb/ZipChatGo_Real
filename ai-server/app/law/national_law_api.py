import re
import xml.etree.ElementTree as ET
from collections.abc import Iterable
from datetime import date

import httpx

from app.law.models import LawArticle, LawDocument
from app.law.targets import LawTarget


NATIONAL_LAW_API_BASE_URL = "https://www.law.go.kr/DRF/"


class NationalLawApiError(RuntimeError):
    """Raised when the official law API cannot provide a valid current law."""


class NationalLawApiClient:
    def __init__(
        self,
        oc: str,
        client: httpx.Client | None = None,
    ) -> None:
        if not oc.strip():
            raise NationalLawApiError("LAW_API_OC is not configured")
        self._oc = oc.strip()
        self._client = client or httpx.Client(
            base_url=NATIONAL_LAW_API_BASE_URL,
            timeout=30.0,
            follow_redirects=True,
        )

    def fetch_current_law(self, target: LawTarget) -> LawDocument:
        search_root = self._request_xml(
            "lawSearch.do",
            {
                "OC": self._oc,
                "target": "eflaw",
                "type": "XML",
                "search": 1,
                "query": target.name,
                "display": 100,
            },
        )
        match = self._find_exact_match(search_root, target)
        serial_number = _required_text(match, "법령일련번호")
        effective_date_raw = _required_text(match, "시행일자")

        body_root = self._request_xml(
            "lawService.do",
            {
                "OC": self._oc,
                "target": "eflaw",
                "type": "XML",
                "MST": serial_number,
                "efYd": effective_date_raw,
            },
        )
        return self._parse_law(body_root, serial_number, target)

    def _request_xml(self, path: str, params: dict[str, object]) -> ET.Element:
        try:
            response = self._client.get(path, params=params)
            response.raise_for_status()
            root = ET.fromstring(response.content)
        except (httpx.HTTPError, ET.ParseError) as exception:
            raise NationalLawApiError("National Law Information API request failed") from exception

        result_code = _optional_text(root, "resultCode")
        if result_code and result_code != "00":
            message = _optional_text(root, "resultMsg") or "unknown API error"
            raise NationalLawApiError(f"National Law Information API error: {message}")
        return root

    def _find_exact_match(self, root: ET.Element, target: LawTarget) -> ET.Element:
        candidates = [
            item
            for item in root.findall(".//law")
            if _normalize(_optional_text(item, "법령명한글")) == _normalize(target.name)
        ]
        current_candidates = [
            item
            for item in candidates
            if _optional_text(item, "현행연혁코드") == "현행"
        ]
        if len(current_candidates) == 1:
            match = current_candidates[0]
        else:
            match = _latest_effective_candidate(candidates)
        if match is None:
            raise NationalLawApiError(
                f"Could not identify the current law named '{target.name}' "
                f"from {len(candidates)} exact matches"
            )
        law_type = _required_text(match, "법령구분명")
        if not _matches_level(law_type, target):
            raise NationalLawApiError(
                f"Unexpected law type for '{target.name}': {law_type}"
            )
        return match

    def _parse_law(
        self,
        root: ET.Element,
        serial_number: str,
        target: LawTarget,
    ) -> LawDocument:
        basic = root.find("./기본정보")
        if basic is None:
            raise NationalLawApiError(f"Law body has no basic information: {target.name}")

        law_name = _required_text(basic, "법령명_한글")
        if _normalize(law_name) != _normalize(target.name):
            raise NationalLawApiError(
                f"Law body name does not match requested law: {law_name}"
            )

        law_type = _required_text(basic, "법종구분")
        articles = [
            article
            for unit in root.findall("./조문/조문단위")
            if (article := _parse_article(unit)) is not None
            and target.includes_article(_article_base_number(article.article_number))
        ]
        if not articles:
            raise NationalLawApiError(f"Law body has no articles: {target.name}")

        effective_date = _format_date(_optional_text(basic, "시행일자"))
        source_url = (
            "https://www.law.go.kr/LSW/lsInfoP.do"
            f"?lsiSeq={serial_number}"
        )
        return LawDocument(
            law_name=law_name,
            law_type=law_type,
            law_id=_required_text(basic, "법령ID"),
            law_serial_number=serial_number,
            promulgation_date=_format_date(_optional_text(basic, "공포일자")),
            promulgation_number=_optional_text(basic, "공포번호"),
            effective_date=effective_date,
            revision_type=_optional_text(basic, "제개정구분"),
            source_url=source_url,
            articles=articles,
        )


def _parse_article(unit: ET.Element) -> LawArticle | None:
    article_number = _optional_text(unit, "조문번호")
    if not article_number:
        return None
    branch_number = _optional_text(unit, "조문가지번호")
    display_number = f"제{article_number}조"
    if branch_number and branch_number != "0":
        display_number += f"의{branch_number}"

    text_parts = list(_iter_article_text(unit))
    if not text_parts:
        return None
    article_key = unit.attrib.get("조문키", "").strip() or (
        f"article-{article_number}-{branch_number or '0'}"
    )
    return LawArticle(
        article_key=article_key,
        article_number=display_number,
        article_title=_optional_text(unit, "조문제목"),
        effective_date=_format_date(_optional_text(unit, "조문시행일자")),
        text="\n".join(text_parts),
    )


def _iter_article_text(unit: ET.Element) -> Iterable[str]:
    content_tags = {"조문내용", "항내용", "호내용", "목내용"}
    previous = None
    for element in unit.iter():
        if element.tag not in content_tags:
            continue
        value = _normalize(element.text)
        if value and value != previous:
            yield value
            previous = value


def _matches_level(law_type: str, target: LawTarget) -> bool:
    if target.level == "법률":
        return law_type == "법률"
    if target.level == "시행령":
        return law_type == "대통령령"
    if target.level == "시행규칙":
        return law_type.endswith("부령") or law_type == "총리령"
    return law_type == "대법원규칙"


def _article_base_number(article_number: str) -> int:
    match = re.search(r"제(\d+)조", article_number)
    if not match:
        raise NationalLawApiError(
            f"Could not parse article number for filtering: {article_number}"
        )
    return int(match.group(1))


def _latest_effective_candidate(candidates: list[ET.Element]) -> ET.Element | None:
    today = date.today().strftime("%Y%m%d")
    eligible = [
        item
        for item in candidates
        if (_optional_text(item, "시행일자") or "") <= today
    ]
    if not eligible:
        return None
    return max(
        eligible,
        key=lambda item: (
            _optional_text(item, "시행일자") or "",
            _optional_text(item, "공포일자") or "",
            _optional_text(item, "법령일련번호") or "",
        ),
    )


def _required_text(element: ET.Element, path: str) -> str:
    value = _optional_text(element, path)
    if not value:
        raise NationalLawApiError(f"Required law API field is missing: {path}")
    return value


def _optional_text(element: ET.Element, path: str) -> str | None:
    child = element.find(path)
    value = child.text if child is not None else None
    normalized = _normalize(value)
    return normalized or None


def _normalize(value: object) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def _format_date(value: str | None) -> str | None:
    digits = re.sub(r"\D", "", value or "")
    if len(digits) != 8:
        return value or None
    return f"{digits[:4]}-{digits[4:6]}-{digits[6:]}"

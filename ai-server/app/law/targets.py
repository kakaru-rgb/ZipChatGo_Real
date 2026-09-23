from dataclasses import dataclass
from typing import Literal


LawLevel = Literal["법률", "시행령", "시행규칙", "법원규칙"]


@dataclass(frozen=True)
class ArticleRange:
    start: int
    end: int

    def contains(self, article_number: int) -> bool:
        return self.start <= article_number <= self.end


@dataclass(frozen=True)
class LawTarget:
    name: str
    level: LawLevel
    article_ranges: tuple[ArticleRange, ...] = ()

    def includes_article(self, article_number: int) -> bool:
        return not self.article_ranges or any(
            article_range.contains(article_number)
            for article_range in self.article_ranges
        )


CIVIL_ACT_REAL_ESTATE_RANGES = (
    ArticleRange(390, 399),  # 채무불이행과 손해배상
    ArticleRange(527, 553),  # 계약의 성립·효력·해제·해지
    ArticleRange(563, 595),  # 매매·계약금·매도인의 담보책임
    ArticleRange(618, 654),  # 임대차
)


LAW_TARGETS = (
    LawTarget("주택임대차보호법", "법률"),
    LawTarget("주택임대차보호법 시행령", "시행령"),
    LawTarget("공인중개사법", "법률"),
    LawTarget("공인중개사법 시행령", "시행령"),
    LawTarget("공인중개사법 시행규칙", "시행규칙"),
    LawTarget("부동산 거래신고 등에 관한 법률", "법률"),
    LawTarget("부동산 거래신고 등에 관한 법률 시행령", "시행령"),
    LawTarget("부동산 거래신고 등에 관한 법률 시행규칙", "시행규칙"),
    LawTarget("상가건물 임대차보호법", "법률"),
    LawTarget("상가건물 임대차보호법 시행령", "시행령"),
    LawTarget("민법", "법률", article_ranges=CIVIL_ACT_REAL_ESTATE_RANGES),
    LawTarget("부동산등기법", "법률"),
    LawTarget("부동산등기규칙", "법원규칙"),
    LawTarget("집합건물의 소유 및 관리에 관한 법률", "법률"),
    LawTarget("집합건물의 소유 및 관리에 관한 법률 시행령", "시행령"),
)

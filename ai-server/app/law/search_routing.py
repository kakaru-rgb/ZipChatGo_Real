"""Detect explicitly named canonical laws and their article references."""

from __future__ import annotations

import re
from dataclasses import dataclass

from app.law.canonical_catalog import CANONICAL_LAW_NAMES


ARTICLE_PATTERN = re.compile(r"제\s*(\d+)\s*조(?:\s*의\s*(\d+))?")


@dataclass(frozen=True)
class LawArticlePair:
    law_name: str
    article_number: str


@dataclass(frozen=True)
class LawMention:
    law_name: str
    start: int
    end: int


def detect_canonical_law_mentions(text: str) -> list[LawMention]:
    candidates: list[LawMention] = []
    for law_name in sorted(CANONICAL_LAW_NAMES, key=len, reverse=True):
        parts = re.split(r"\s+", law_name)
        body = r"\s+".join(re.escape(part) for part in parts)
        suffix = (
            r"(?=$|[^0-9A-Za-z가-힣]|"
            r"(?:상|과|와|은|는|이|가|을|를|에서|에서는|으로|로|에|의)"
            r"(?=$|[^0-9A-Za-z가-힣])|제\s*\d+\s*조)"
        )
        pattern = re.compile(rf"(?<![0-9A-Za-z가-힣]){body}{suffix}")
        candidates.extend(
            LawMention(law_name, match.start(), match.end())
            for match in pattern.finditer(text)
        )

    accepted: list[LawMention] = []
    for mention in sorted(candidates, key=lambda item: (item.start, -(item.end - item.start))):
        if any(mention.start < item.end and item.start < mention.end for item in accepted):
            continue
        accepted.append(mention)
    return sorted(accepted, key=lambda item: item.start)


def detect_canonical_law_names(text: str) -> list[str]:
    return list(dict.fromkeys(item.law_name for item in detect_canonical_law_mentions(text)))


def detect_canonical_law_article_pairs(text: str) -> list[LawArticlePair]:
    mentions = detect_canonical_law_mentions(text)
    if not mentions:
        return []
    unique_laws = list(dict.fromkeys(item.law_name for item in mentions))
    pairs: list[LawArticlePair] = []
    if len(unique_laws) == 1:
        pairs = [
            LawArticlePair(unique_laws[0], _article_number(match))
            for match in ARTICLE_PATTERN.finditer(text)
        ]
    else:
        for index, mention in enumerate(mentions):
            end = mentions[index + 1].start if index + 1 < len(mentions) else len(text)
            pairs.extend(
                LawArticlePair(mention.law_name, _article_number(match))
                for match in ARTICLE_PATTERN.finditer(text[mention.end:end])
            )
    return list(dict.fromkeys(pairs))


def _article_number(match: re.Match[str]) -> str:
    number = f"제{int(match.group(1))}조"
    return number + (f"의{int(match.group(2))}" if match.group(2) else "")

from __future__ import annotations

import re
from dataclasses import dataclass


_CIRCLED_DIGITS = str.maketrans("①②③④⑤", "12345")
_ANSWER_PATTERNS = (
    re.compile(
        r"(?:최종\s*)?(?:정답|답)(?:\s*번호)?\s*(?:은|는|:)?\s*"
        r"([1-5])\s*(?:번|\.)?"
    ),
    re.compile(r"(?:옳은|틀린)?\s*선택지는\s*([1-5])\s*번"),
    re.compile(r"(?:옳은|틀린)\s*(?:설명|것|항목)(?:은|는)?\s*([1-5])\s*번"),
    re.compile(r"대상이\s*아닌\s*것(?:은|는)?\s*([1-5])\s*번"),
    re.compile(r"업무(?:은|는)\s*([1-5])\s*(?:번|\.)"),
    re.compile(r"([1-5])\s*번\s*(?:이|가)?\s*(?:정답|답)"),
)


@dataclass(frozen=True)
class ParsedAnswer:
    answer: int | None
    status: str


def parse_final_answer(raw_response: str) -> ParsedAnswer:
    normalized = raw_response.translate(_CIRCLED_DIGITS)
    normalized = re.sub(r"[*_`]", "", normalized)
    final_matches = [
        int(value)
        for value in re.findall(
            r"최종\s*(?:정답|답)(?:\s*번호)?\s*(?:은|는|:)?\s*"
            r"([1-5])\s*(?:번|\.)?",
            normalized,
        )
    ]
    final_unique = list(dict.fromkeys(final_matches))
    if len(final_unique) == 1:
        return ParsedAnswer(final_unique[0], "추출성공:최종답표현")
    if len(final_unique) > 1:
        return ParsedAnswer(None, "판정불가:복수최종답표현")
    answer_sentences = [
        sentence
        for sentence in re.split(r"(?<=[.!?。])|\n", normalized)
        if re.search(r"(?:최종\s*)?(?:정답|답)", sentence)
    ]
    for sentence in answer_sentences:
        mentioned = list(dict.fromkeys(
            int(value) for value in re.findall(r"([1-5])\s*번", sentence)
        ))
        if len(mentioned) > 1:
            return ParsedAnswer(None, "판정불가:복수정답표현")
    for pattern in _ANSWER_PATTERNS:
        matches = [int(value) for value in pattern.findall(normalized)]
        unique = list(dict.fromkeys(matches))
        if len(unique) == 1:
            return ParsedAnswer(unique[0], "추출성공")
        if len(unique) > 1:
            return ParsedAnswer(None, "판정불가:복수정답표현")
    return ParsedAnswer(None, "판정불가:명시적정답없음")

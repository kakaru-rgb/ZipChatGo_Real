from __future__ import annotations

import csv
import json
import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field, model_validator


SUPPORTED_YEARS = (2024, 2025)


@dataclass(frozen=True)
class PaperSpec:
    paper_id: str
    name_tokens: tuple[str, ...]
    expected_questions: int


PAPER_SPECS = (
    PaperSpec("1차_1교시", ("1차", "1교시"), 80),
    PaperSpec("2차_1교시", ("2차", "1교시"), 80),
    PaperSpec("2차_2교시", ("2차", "2교시"), 40),
)


class ExamQuestion(BaseModel):
    year: int
    paper_id: str
    paper_name: str
    subject: str = ""
    question_no: int = Field(ge=1, le=80)
    question: str = Field(min_length=1)
    choices: list[str] = Field(min_length=5, max_length=5)
    correct_answer: int = Field(ge=1, le=5)
    accepted_answers: list[int] = Field(default_factory=list)
    source_pdf: str
    source_page: int = 0

    @property
    def key(self) -> str:
        return f"{self.year}:{self.paper_id}:{self.question_no}"


class PreparedExam(BaseModel):
    schema_version: int = 3
    year: int
    questions: list[ExamQuestion]
    source_hashes: dict[str, str]
    expected_total: int = 200

    @model_validator(mode="after")
    def validate_exam(self) -> "PreparedExam":
        validate_exam_questions(
            self.year,
            self.questions,
            allow_partial=len(self.questions) < self.expected_total,
        )
        return self


def validate_exam_questions(
    year: int,
    questions: Sequence[ExamQuestion],
    *,
    allow_partial: bool = False,
) -> None:
    if year not in SUPPORTED_YEARS:
        raise ValueError(f"Unsupported exam year: {year}")
    expected_total = sum(paper.expected_questions for paper in PAPER_SPECS)
    if not allow_partial and len(questions) != expected_total:
        raise ValueError(
            f"Expected {expected_total} questions for {year}, found {len(questions)}"
        )
    if allow_partial and not 1 <= len(questions) < expected_total:
        raise ValueError(
            f"Expected between 1 and {expected_total - 1} questions for a partial "
            f"{year} dataset, found {len(questions)}"
        )
    remaining = len(questions)
    for paper in PAPER_SPECS:
        expected_count = min(remaining, paper.expected_questions)
        paper_questions = [item for item in questions if item.paper_id == paper.paper_id]
        _validate_numbered_items(
            paper_questions,
            expected_count,
            lambda item: item.question_no,
            f"{year} {paper.paper_id}",
        )
        remaining -= expected_count


def evaluate_exam(
    exam: PreparedExam,
    evaluator: Any,
    output_path: Path,
    *,
    resume: bool = True,
    subject: str | None = None,
    limit: int | None = None,
    delay_seconds: float = 1.0,
    progress: Callable[[str], None] | None = None,
) -> list[dict[str, str]]:
    report = progress or (lambda _: None)
    existing = _read_existing_results(output_path) if resume else []
    completed = {
        row["문항키"] for row in existing if row.get("오류", "").strip() == ""
    }
    pending = [
        item
        for item in exam.questions
        if item.key not in completed
        and (subject is None or item.subject == subject)
    ]
    if limit is not None:
        pending = pending[:limit]
    rows = list(existing)
    for index, question in enumerate(pending, start=1):
        report(f"Evaluating {index}/{len(pending)}: {question.key}")
        rows = [row for row in rows if row["문항키"] != question.key]
        rows.append(evaluator.evaluate(question))
        rows.sort(key=_result_sort_key)
        write_result_csv(rows, output_path)
        if delay_seconds > 0 and index < len(pending):
            time.sleep(delay_seconds)
    return rows


CSV_FIELDS = (
    "연도", "시험", "교시", "과목", "문항번호", "문제",
    "선택지1", "선택지2", "선택지3", "선택지4", "선택지5",
    "선택지별판단", "모델원래예측", "판단조합", "조합검증결과", "챗봇예측",
    "공식정답", "정답여부", "챗봇원문답변", "평가모델",
    "RAG사용여부", "RAG검색어", "RAG검색결과수", "RAG검색근거",
    "법령링크포함", "오류", "문항키",
)


def write_result_csv(rows: Sequence[dict[str, str]], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=CSV_FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    temporary.replace(path)


def make_result_row(
    question: ExamQuestion,
    prediction: int | None,
    answer_text: str,
    error: str,
    *,
    model: str = "",
    original_prediction: int | None = None,
    choice_judgments: Sequence[dict[str, Any]] = (),
    resolved_items: Sequence[dict[str, str]] = (),
    combination_check: str = "",
    rag_used: bool = False,
    rag_queries: Sequence[str] = (),
    rag_result_count: int = 0,
    rag_sources: Sequence[dict[str, Any]] = (),
) -> dict[str, str]:
    first, second = question.paper_id.split("_", 1)
    accepted = question.accepted_answers or [question.correct_answer]
    correct = (
        "오류" if error else "판정불가" if prediction is None
        else "O" if prediction in accepted else "X"
    )
    return {
        "연도": str(question.year),
        "시험": first,
        "교시": second,
        "과목": question.subject,
        "문항번호": str(question.question_no),
        "문제": question.question,
        **{f"선택지{index}": choice for index, choice in enumerate(question.choices, 1)},
        "선택지별판단": json.dumps(
            list(choice_judgments), ensure_ascii=False, separators=(",", ":")
        ),
        "모델원래예측": str(original_prediction or prediction or ""),
        "판단조합": json.dumps(
            list(resolved_items), ensure_ascii=False, separators=(",", ":")
        ),
        "조합검증결과": combination_check,
        "챗봇예측": str(prediction or ""),
        "공식정답": ",".join(str(value) for value in accepted),
        "정답여부": correct,
        "챗봇원문답변": answer_text,
        "평가모델": model,
        "RAG사용여부": "Y" if rag_used else "N",
        "RAG검색어": " | ".join(rag_queries),
        "RAG검색결과수": str(rag_result_count),
        "RAG검색근거": json.dumps(list(rag_sources), ensure_ascii=False, separators=(",", ":")),
        "법령링크포함": "Y" if "law.go.kr" in answer_text else "N",
        "오류": error,
        "문항키": question.key,
    }


def _read_existing_results(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


def _result_sort_key(row: dict[str, str]) -> tuple[int, int, int]:
    paper_order = {paper.paper_id: index for index, paper in enumerate(PAPER_SPECS)}
    paper_id = f"{row['시험']}_{row['교시']}"
    return (int(row["연도"]), paper_order.get(paper_id, 99), int(row["문항번호"]))


def _validate_numbered_items(
    items: Sequence[Any],
    expected_count: int,
    number: Callable[[Any], int],
    label: str,
) -> None:
    actual = sorted(number(item) for item in items)
    expected = list(range(1, expected_count + 1))
    if actual != expected:
        missing = sorted(set(expected) - set(actual))
        duplicates = sorted(value for value in set(actual) if actual.count(value) > 1)
        raise ValueError(
            f"Invalid {label}: count={len(actual)}, missing={missing}, "
            f"duplicates={duplicates}"
        )

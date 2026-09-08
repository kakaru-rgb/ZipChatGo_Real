from __future__ import annotations

import csv
import hashlib
import json
import re
import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any, Literal

import httpx
from pydantic import BaseModel, Field, model_validator


SUPPORTED_YEARS = (2024, 2025)
FINAL_ANSWER_PATTERN = re.compile(
    r"(?:최종\s*정답|정답)\s*(?:은|:)?\s*(?:[①②③④⑤]|[1-5]\s*번?)"
)
CIRCLED_TO_NUMBER = {"①": 1, "②": 2, "③": 3, "④": 4, "⑤": 5}


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
    source_pdf: str

    @property
    def key(self) -> str:
        return f"{self.year}:{self.paper_id}:{self.question_no}"


class PreparedExam(BaseModel):
    schema_version: int = 2
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


class ExtractedQuestion(BaseModel):
    question_no: int = Field(ge=1, le=80)
    subject: str = ""
    question: str = Field(min_length=1)
    choices: list[str] = Field(min_length=5, max_length=5)


class ExtractedAnswer(BaseModel):
    question_no: int = Field(ge=1, le=80)
    answer: int = Field(ge=1, le=5)


class OpenAIExamPdfExtractor:
    """Uses PDF file input only to transcribe questions and official answers."""

    def __init__(
        self,
        client: Any,
        model: str,
        progress: Callable[[str], None] | None = None,
    ) -> None:
        self._client = client
        self._model = model
        self._progress = progress or (lambda _: None)

    def extract_questions(
        self,
        pdf_path: Path,
        paper: PaperSpec,
    ) -> list[ExtractedQuestion]:
        file_id = self._upload(pdf_path)
        questions: list[ExtractedQuestion] = []
        try:
            for start in range(1, paper.expected_questions + 1, 10):
                end = min(start + 9, paper.expected_questions)
                expected_numbers = list(range(start, end + 1))
                for attempt in range(1, 4):
                    self._progress(
                        f"Extracting {paper.paper_id} questions {start}-{end}"
                        + (f" (attempt {attempt})" if attempt > 1 else "")
                    )
                    payload = self._structured_response(
                        file_id=file_id,
                        prompt=(
                            f"이 공인중개사 시험 문제지에서 {start}번부터 {end}번까지 "
                            "문제만 정확히 전사하세요. 문제 본문과 ①~⑤ 선택지를 원문대로 "
                            "분리하고, questions 배열은 문항 번호의 오름차순으로 정확히 "
                            "배치하세요. 문항을 빠뜨리거나 다른 번호로 바꾸지 마세요. "
                            "페이지 머리말과 정답 추측은 제외하세요. 과목명이 보이면 "
                            "subject에 기록하세요."
                        ),
                        schema=_question_schema(start, end),
                        schema_name=f"exam_questions_{paper.paper_id}_{start}_{end}",
                    )
                    block_questions = [
                        ExtractedQuestion.model_validate(item)
                        for item in payload["questions"]
                    ]
                    actual_numbers = [item.question_no for item in block_questions]
                    if actual_numbers == expected_numbers:
                        questions.extend(block_questions)
                        break
                    if attempt == 3:
                        raise ValueError(
                            f"Invalid {paper.paper_id} questions {start}-{end}: "
                            f"numbers={actual_numbers}"
                        )
                    self._progress(
                        f"Retrying {paper.paper_id} questions {start}-{end}; "
                        f"received numbers {actual_numbers}"
                    )
        finally:
            self._delete_file(file_id)
        _validate_numbered_items(
            questions,
            paper.expected_questions,
            lambda item: item.question_no,
            f"{paper.paper_id} questions",
        )
        return sorted(questions, key=lambda item: item.question_no)

    def extract_answers(
        self,
        pdf_path: Path,
        paper: PaperSpec,
    ) -> list[ExtractedAnswer]:
        return self.extract_answer_sets(pdf_path, (paper,))[paper.paper_id]

    def extract_answer_sets(
        self,
        pdf_path: Path,
        papers: Sequence[PaperSpec],
    ) -> dict[str, list[ExtractedAnswer]]:
        file_id = self._upload(pdf_path)
        extracted: dict[str, list[ExtractedAnswer]] = {}
        try:
            for paper in papers:
                self._progress(f"Extracting official answers for {paper.paper_id}")
                payload = self._structured_response(
                    file_id=file_id,
                    prompt=(
                        f"이 최종정답표에서 A형 {paper.paper_id}의 1번부터 "
                        f"{paper.expected_questions}번까지 공식 정답만 읽으세요. "
                        "다른 교시나 B형 정답을 섞지 마세요."
                    ),
                    schema=_answer_schema(paper.expected_questions),
                    schema_name=f"exam_answers_{paper.paper_id}",
                )
                answers = [
                    ExtractedAnswer.model_validate(item)
                    for item in payload["answers"]
                ]
                _validate_numbered_items(
                    answers,
                    paper.expected_questions,
                    lambda item: item.question_no,
                    f"{paper.paper_id} answers",
                )
                extracted[paper.paper_id] = sorted(
                    answers,
                    key=lambda item: item.question_no,
                )
        finally:
            self._delete_file(file_id)
        return extracted

    def _upload(self, path: Path) -> str:
        self._progress(f"Uploading PDF for extraction: {path.name}")
        with path.open("rb") as stream:
            uploaded = self._client.files.create(file=stream, purpose="user_data")
        return str(uploaded.id)

    def _delete_file(self, file_id: str) -> None:
        try:
            self._client.files.delete(file_id)
        except Exception as exception:
            self._progress(f"Could not delete temporary OpenAI file: {exception}")

    def _structured_response(
        self,
        file_id: str,
        prompt: str,
        schema: dict[str, Any],
        schema_name: str,
    ) -> dict[str, Any]:
        safe_schema_name = re.sub(r"[^A-Za-z0-9_-]", "_", schema_name)
        response = self._client.responses.create(
            model=self._model,
            instructions=(
                "당신은 시험지를 평가하는 사람이 아니라 원문을 정확히 전사하는 "
                "데이터 추출기입니다. 보이지 않는 문구나 정답을 추측하지 마세요."
            ),
            input=[
                {
                    "role": "user",
                    "content": [
                        {"type": "input_file", "file_id": file_id},
                        {"type": "input_text", "text": prompt},
                    ],
                }
            ],
            text={
                "format": {
                    "type": "json_schema",
                    "name": safe_schema_name,
                    "schema": schema,
                    "strict": True,
                }
            },
            max_output_tokens=12_000,
            store=False,
        )
        return json.loads(response.output_text)


class ChatbotExamEvaluator:
    def __init__(
        self,
        base_url: str,
        client: httpx.Client | None = None,
        timeout_seconds: float = 180.0,
        max_attempts: int = 3,
    ) -> None:
        self._client = client or httpx.Client(
            base_url=base_url.rstrip("/"),
            timeout=timeout_seconds,
        )
        self._max_attempts = max_attempts

    def evaluate(self, question: ExamQuestion) -> dict[str, str]:
        message = build_chat_message(question)
        last_error = ""
        for attempt in range(1, self._max_attempts + 1):
            try:
                response = self._client.post(
                    "/agent/chat",
                    json={"message": message},
                )
                response.raise_for_status()
                answer_text = str(response.json().get("message", "")).strip()
                rag_used = (
                    response.headers.get("X-ZipChatGo-RAG-Used", "false").lower()
                    == "true"
                )
                prediction = parse_predicted_answer(answer_text)
                return _result_row(
                    question,
                    prediction,
                    answer_text,
                    "",
                    rag_used=rag_used,
                )
            except (httpx.HTTPError, ValueError, TypeError) as exception:
                last_error = f"{type(exception).__name__}: {exception}"
                if attempt < self._max_attempts:
                    time.sleep(2 ** (attempt - 1))
        return _result_row(question, None, "", last_error)


def prepare_exam(
    year: int,
    source_root: Path,
    extractor: OpenAIExamPdfExtractor,
    *,
    limit: int | None = None,
) -> PreparedExam:
    expected_total = sum(paper.expected_questions for paper in PAPER_SPECS)
    if limit is not None and not 1 <= limit <= expected_total:
        raise ValueError(f"limit must be between 1 and {expected_total}")
    question_pdfs, answer_pdf = find_exam_pdfs(year, source_root)
    questions: list[ExamQuestion] = []
    source_hashes = {
        path.name: _sha256(path) for path in [*question_pdfs.values(), answer_pdf]
    }
    remaining = limit if limit is not None else expected_total
    planned_papers: list[PaperSpec] = []
    for paper in PAPER_SPECS:
        if remaining <= 0:
            break
        question_count = min(remaining, paper.expected_questions)
        planned_papers.append(replace(paper, expected_questions=question_count))
        remaining -= question_count
    answer_sets = extractor.extract_answer_sets(answer_pdf, planned_papers)
    for paper in planned_papers:
        pdf_path = question_pdfs[paper.paper_id]
        extracted_questions = extractor.extract_questions(pdf_path, paper)
        extracted_answers = {
            item.question_no: item.answer
            for item in answer_sets[paper.paper_id]
        }
        for item in extracted_questions:
            questions.append(
                ExamQuestion(
                    year=year,
                    paper_id=paper.paper_id,
                    paper_name=pdf_path.stem,
                    subject=item.subject,
                    question_no=item.question_no,
                    question=item.question,
                    choices=item.choices,
                    correct_answer=extracted_answers[item.question_no],
                    source_pdf=pdf_path.name,
                )
            )
    return PreparedExam(
        year=year,
        questions=questions,
        source_hashes=source_hashes,
        expected_total=expected_total,
    )


def find_exam_pdfs(
    year: int,
    source_root: Path,
) -> tuple[dict[str, Path], Path]:
    if year not in SUPPORTED_YEARS:
        raise ValueError(f"Unsupported exam year: {year}")
    year_dir = next(
        (
            path
            for path in source_root.iterdir()
            if path.is_dir() and path.name.startswith(str(year))
        ),
        None,
    )
    if year_dir is None:
        raise FileNotFoundError(f"Exam directory not found for {year}")
    candidates = list(year_dir.glob("*.pdf"))
    question_pdfs: dict[str, Path] = {}
    for paper in PAPER_SPECS:
        matches = [
            path
            for path in candidates
            if all(token in path.name for token in paper.name_tokens)
        ]
        if len(matches) != 1:
            raise ValueError(
                f"Expected one PDF for {year} {paper.paper_id}, found {len(matches)}"
            )
        question_pdfs[paper.paper_id] = matches[0]
    answer_matches = [
        path
        for path in source_root.glob(f"{year}*.pdf")
        if "최종정답" in path.name
    ]
    if len(answer_matches) != 1:
        raise ValueError(
            f"Expected one final-answer PDF for {year}, found {len(answer_matches)}"
        )
    return question_pdfs, answer_matches[0]


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


def save_prepared_exam(exam: PreparedExam, path: Path) -> None:
    path.write_text(exam.model_dump_json(indent=2), encoding="utf-8")


def load_prepared_exam(path: Path) -> PreparedExam:
    return PreparedExam.model_validate_json(path.read_text(encoding="utf-8"))


def evaluate_exam(
    exam: PreparedExam,
    evaluator: ChatbotExamEvaluator,
    output_path: Path,
    *,
    resume: bool = True,
    limit: int | None = None,
    delay_seconds: float = 1.0,
    progress: Callable[[str], None] | None = None,
) -> list[dict[str, str]]:
    report = progress or (lambda _: None)
    existing = _read_existing_results(output_path) if resume else []
    completed = {
        row["문항키"]
        for row in existing
        if row.get("오류", "").strip() == ""
    }
    pending = [item for item in exam.questions if item.key not in completed]
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


def build_chat_message(question: ExamQuestion) -> str:
    choices = "\n".join(
        f"{index}. {choice}" for index, choice in enumerate(question.choices, start=1)
    )
    return (
        "다음 공인중개사 객관식 문제를 풀어주세요. 필요한 경우 법령 검색 Tool을 "
        "사용하고 판단 근거를 간략히 설명한 뒤, 마지막 줄에 반드시 "
        "'최종 정답: N번' 형식으로 답해주세요.\n\n"
        f"{question.question_no}. {question.question}\n{choices}"
    )


def parse_predicted_answer(text: str) -> int | None:
    matches = list(FINAL_ANSWER_PATTERN.finditer(text))
    if not matches:
        return None
    token_match = re.search(r"[①②③④⑤1-5]", matches[-1].group())
    if token_match is None:
        return None
    token = token_match.group()
    if token in CIRCLED_TO_NUMBER:
        return CIRCLED_TO_NUMBER[token]
    return int(token) if token.isdigit() else None


CSV_FIELDS = (
    "연도",
    "시험",
    "교시",
    "과목",
    "문항번호",
    "문제",
    "선택지1",
    "선택지2",
    "선택지3",
    "선택지4",
    "선택지5",
    "챗봇예측",
    "공식정답",
    "정답여부",
    "챗봇원문답변",
    "RAG사용여부",
    "법령링크포함",
    "오류",
    "문항키",
)


def write_result_csv(rows: Sequence[dict[str, str]], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=CSV_FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    temporary.replace(path)


def _result_row(
    question: ExamQuestion,
    prediction: int | None,
    answer_text: str,
    error: str,
    *,
    rag_used: bool = False,
) -> dict[str, str]:
    first, second = question.paper_id.split("_", 1)
    correct = (
        "오류"
        if error
        else "판정불가"
        if prediction is None
        else "O"
        if prediction == question.correct_answer
        else "X"
    )
    return {
        "연도": str(question.year),
        "시험": first,
        "교시": second,
        "과목": question.subject,
        "문항번호": str(question.question_no),
        "문제": question.question,
        **{
            f"선택지{index}": choice
            for index, choice in enumerate(question.choices, start=1)
        },
        "챗봇예측": str(prediction or ""),
        "공식정답": str(question.correct_answer),
        "정답여부": correct,
        "챗봇원문답변": answer_text,
        "RAG사용여부": "Y" if rag_used else "N",
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


def _question_schema(start: int, end: int) -> dict[str, Any]:
    count = end - start + 1
    return {
        "type": "object",
        "properties": {
            "questions": {
                "type": "array",
                "minItems": count,
                "maxItems": count,
                "items": {
                    "type": "object",
                    "properties": {
                        "question_no": {"type": "integer", "minimum": start, "maximum": end},
                        "subject": {"type": "string"},
                        "question": {"type": "string"},
                        "choices": {
                            "type": "array",
                            "minItems": 5,
                            "maxItems": 5,
                            "items": {"type": "string"},
                        },
                    },
                    "required": ["question_no", "subject", "question", "choices"],
                    "additionalProperties": False,
                },
            }
        },
        "required": ["questions"],
        "additionalProperties": False,
    }


def _answer_schema(expected_count: int) -> dict[str, Any]:
    return {
        "type": "object",
        "properties": {
            "answers": {
                "type": "array",
                "minItems": expected_count,
                "maxItems": expected_count,
                "items": {
                    "type": "object",
                    "properties": {
                        "question_no": {
                            "type": "integer",
                            "minimum": 1,
                            "maximum": expected_count,
                        },
                        "answer": {"type": "integer", "minimum": 1, "maximum": 5},
                    },
                    "required": ["question_no", "answer"],
                    "additionalProperties": False,
                },
            }
        },
        "required": ["answers"],
        "additionalProperties": False,
    }


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()

from __future__ import annotations

import csv
import hashlib
import re
from dataclasses import dataclass
from pathlib import Path

import pymupdf

from app.evaluation.exam_text_normalizer import (
    normalize_exam_choice,
    normalize_exam_text,
)
from app.evaluation.realtor_exam import ExamQuestion, PAPER_SPECS, PreparedExam


SOURCE_CSV_FIELDS = (
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
    "공식정답",
    "원본PDF",
    "페이지",
    "추출상태",
    "검토메모",
)


@dataclass(frozen=True)
class LocalQuestion:
    question_no: int
    question: str
    choices: tuple[str, str, str, str, str]
    page: int


# 한국산업인력공단이 배포한 제35회 최종정답표(A형)를 그대로 옮긴 값이다.
# 1차 1교시 67번은 최종정답표에서 ①~⑤가 모두 정답으로 인정되었다.
OFFICIAL_ANSWERS_2024: dict[str, tuple[str, ...]] = {
    "1차_1교시": tuple(
        "4 2 4 1 5 5 2 4 1 3 2 1 5 4 2 3 3 1 5 5 "
        "4 1 4 3 5 4 3 2 3 2 4 2 3 5 1 1 2 3 5 1 "
        "3 5 3 3 2 5 5 1 1 2 4 3 5 2 4 5 1 2 2 1 "
        "4 4 2 3 5 5 1,2,3,4,5 5 1 5 1 4 3 3 3 1 1 1 2 4".split()
    ),
    "2차_1교시": tuple(
        "5 1 2 5 3 3 1 1 2 2 4 2 3 1 4 3 1 2 5 3 "
        "4 4 2 4 5 2 5 1 4 3 1 3 5 4 4 5 3 5 4 2 "
        "1 2 4 5 2 3 2 5 3 2 4 3 2 5 1 4 3 4 5 4 "
        "5 1 2 2 4 1 3 1 2 1 3 1 5 3 5 3 4 5 5 4".split()
    ),
    "2차_2교시": tuple(
        "3 3 1 5 2 4 1 4 5 2 5 5 2 5 1 4 3 5 2 3 "
        "3 4 1 2 4 5 3 5 2 3 1 1 1 3 2 3 3 4 2 4".split()
    ),
}


SUBJECTS: dict[str, tuple[tuple[range, str], ...]] = {
    "1차_1교시": (
        (range(1, 41), "부동산학개론"),
        (range(41, 81), "민법 및 민사특별법"),
    ),
    "2차_1교시": (
        (range(1, 41), "공인중개사법령 및 중개실무"),
        (range(41, 81), "부동산공법"),
    ),
    "2차_2교시": (
        (range(1, 25), "부동산공시법령"),
        (range(25, 41), "부동산세법"),
    ),
}


def prepare_exam_locally(year: int, source_root: Path) -> PreparedExam:
    """Extract an exam deterministically without calling an LLM or OpenAI API."""
    if year != 2024:
        raise ValueError(
            "2025 정답표 검증은 아직 진행하지 않았습니다. 먼저 2024 CSV를 검토해 주세요."
        )
    question_pdfs = find_question_pdfs(year, source_root)
    questions: list[ExamQuestion] = []
    hashes: dict[str, str] = {}
    for paper in PAPER_SPECS:
        path = question_pdfs[paper.paper_id]
        hashes[path.name] = _sha256(path)
        extracted = extract_question_pdf(path, paper.expected_questions)
        answer_keys = OFFICIAL_ANSWERS_2024[paper.paper_id]
        if len(answer_keys) != paper.expected_questions:
            raise ValueError(f"Invalid answer key count for {paper.paper_id}")
        for item in extracted:
            accepted = [int(value) for value in answer_keys[item.question_no - 1].split(",")]
            questions.append(
                ExamQuestion(
                    year=year,
                    paper_id=paper.paper_id,
                    paper_name=path.stem,
                    subject=_subject_for(paper.paper_id, item.question_no),
                    question_no=item.question_no,
                    question=normalize_exam_text(item.question),
                    choices=[normalize_exam_choice(choice) for choice in item.choices],
                    correct_answer=accepted[0],
                    accepted_answers=accepted,
                    source_pdf=path.name,
                    source_page=item.page,
                )
            )
    return PreparedExam(year=year, questions=questions, source_hashes=hashes)


def find_question_pdfs(year: int, source_root: Path) -> dict[str, Path]:
    year_dirs = [
        path
        for path in source_root.iterdir()
        if path.is_dir() and path.name.startswith(str(year))
    ]
    if len(year_dirs) != 1:
        raise ValueError(f"Expected one exam directory for {year}, found {len(year_dirs)}")
    candidates = list(year_dirs[0].glob("*.pdf"))
    found: dict[str, Path] = {}
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
        found[paper.paper_id] = matches[0]
    return found


def extract_question_pdf(path: Path, expected_questions: int) -> list[LocalQuestion]:
    extracted: list[LocalQuestion] = []
    with pymupdf.open(path) as document:
        for page_number, page in enumerate(document, start=1):
            blocks = [
                block
                for block in page.get_text("blocks")
                if block[1] < page.rect.height - 35
            ]
            midpoint = page.rect.width / 2
            ordered = sorted(
                (block for block in blocks if block[0] < midpoint),
                key=lambda block: (block[1], block[0]),
            ) + sorted(
                (block for block in blocks if block[0] >= midpoint),
                key=lambda block: (block[1], block[0]),
            )
            current_number: int | None = None
            current_parts: list[str] = []
            for block in ordered:
                text = block[4]
                match = re.match(r"\s*(\d{1,2})\.\s*", text)
                is_question_anchor = block[0] < 40 or midpoint + 5 < block[0] < midpoint + 45
                if match and is_question_anchor:
                    if current_number is not None:
                        extracted.append(
                            _make_local_question(
                                current_number,
                                "\n".join(current_parts),
                                page_number,
                            )
                        )
                    current_number = int(match.group(1))
                    current_parts = [text]
                elif current_number is not None:
                    current_parts.append(text)
            if current_number is not None:
                extracted.append(
                    _make_local_question(
                        current_number,
                        "\n".join(current_parts),
                        page_number,
                    )
                )

    actual = [item.question_no for item in extracted]
    expected = list(range(1, expected_questions + 1))
    if actual != expected:
        raise ValueError(
            f"Question numbering mismatch in {path.name}: expected={expected}, actual={actual}"
        )
    return extracted


def save_exam_source_csv(exam: PreparedExam, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=SOURCE_CSV_FIELDS)
        writer.writeheader()
        for item in exam.questions:
            first, second = item.paper_id.split("_", 1)
            accepted = item.accepted_answers or [item.correct_answer]
            writer.writerow(
                {
                    "연도": item.year,
                    "시험": first,
                    "교시": second,
                    "과목": item.subject,
                    "문항번호": item.question_no,
                    "문제": item.question,
                    **{
                        f"선택지{index}": choice
                        for index, choice in enumerate(item.choices, start=1)
                    },
                    "공식정답": ",".join(str(value) for value in accepted),
                    "원본PDF": item.source_pdf,
                    "페이지": item.source_page,
                    "추출상태": "정상",
                    "검토메모": "",
                }
            )
    temporary.replace(path)


def load_exam_source_csv(path: Path) -> PreparedExam:
    questions: list[ExamQuestion] = []
    with path.open("r", encoding="utf-8-sig", newline="") as stream:
        for row in csv.DictReader(stream):
            accepted = [int(value) for value in row["공식정답"].split(",")]
            paper_id = f"{row['시험']}_{row['교시']}"
            questions.append(
                ExamQuestion(
                    year=int(row["연도"]),
                    paper_id=paper_id,
                    paper_name=Path(row["원본PDF"]).stem,
                    subject=row["과목"],
                    question_no=int(row["문항번호"]),
                    question=row["문제"],
                    choices=[row[f"선택지{index}"] for index in range(1, 6)],
                    correct_answer=accepted[0],
                    accepted_answers=accepted,
                    source_pdf=row["원본PDF"],
                    source_page=int(row["페이지"]),
                )
            )
    if not questions:
        raise ValueError(f"No questions found in {path}")
    return PreparedExam(year=questions[0].year, questions=questions, source_hashes={})


def _make_local_question(number: int, raw: str, page: int) -> LocalQuestion:
    text = re.sub(r"^\s*\d{1,2}\.\s*", "", raw, count=1)
    first_choice = text.rfind("①")
    if first_choice < 0:
        raise ValueError(f"Question {number} has no choice ① on page {page}")
    question = _normalize_text(text[:first_choice])
    choices_text = text[first_choice:]
    markers = "①②③④⑤"
    positions: list[int] = []
    cursor = 0
    for marker in markers:
        position = choices_text.find(marker, cursor)
        if position < 0:
            raise ValueError(f"Question {number} is missing choice {marker} on page {page}")
        positions.append(position)
        cursor = position + 1
    choices = []
    for index, position in enumerate(positions):
        end = positions[index + 1] if index < 4 else len(choices_text)
        choices.append(_normalize_text(choices_text[position + 1 : end]))
    if not question or any(not choice for choice in choices):
        raise ValueError(f"Question {number} contains empty extracted text on page {page}")
    return LocalQuestion(number, question, tuple(choices), page)  # type: ignore[arg-type]


def _normalize_text(value: str) -> str:
    value = value.replace("\u00a0", " ").replace("ㆍ", "·")
    value = re.sub(r"\s+", " ", value)
    return value.strip()


def _subject_for(paper_id: str, question_no: int) -> str:
    for numbers, subject in SUBJECTS[paper_id]:
        if question_no in numbers:
            return subject
    raise ValueError(f"No subject mapping for {paper_id} question {question_no}")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()

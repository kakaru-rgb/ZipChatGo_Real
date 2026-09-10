from __future__ import annotations

import csv
import json
import re
import unicodedata
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Sequence

from app.evaluation.production_agent_passthrough import REQUIRED_COLUMNS


@dataclass(frozen=True)
class DataQualityIssue:
    severity: str
    code: str
    row_number: int | None
    question_number: str
    field: str
    message: str
    value_preview: str = ""


@dataclass(frozen=True)
class DataQualityReport:
    input_csv: str
    subject: str
    target_row_count: int
    expected_question_count: int
    blocking_issue_count: int
    warning_count: int
    issues: tuple[DataQualityIssue, ...]

    @property
    def passed(self) -> bool:
        return self.blocking_issue_count == 0

    def as_dict(self) -> dict[str, object]:
        result = asdict(self)
        result["passed"] = self.passed
        return result


_ANSWER = re.compile(r"^[1-5](?:,[1-5])*$")
_LABEL_ONLY_CHOICE = re.compile(r"^[ㄱ-ㅎ\s,·]+$")
_SECTION_HEADER = re.compile(r"제\s*\d+\s*과목\s*:")


def inspect_reviewed_exam_csv(
    path: Path,
    *,
    subject: str,
    expected_numbers: Sequence[int] = tuple(range(1, 41)),
) -> DataQualityReport:
    issues: list[DataQualityIssue] = []
    with path.open("r", encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        headers = tuple(reader.fieldnames or ())
        missing_headers = [column for column in REQUIRED_COLUMNS if column not in headers]
        if missing_headers:
            issues.append(
                DataQualityIssue(
                    "error",
                    "MISSING_COLUMNS",
                    1,
                    "",
                    "header",
                    "필수 컬럼 누락: " + ", ".join(missing_headers),
                )
            )
            return _report(path, subject, 0, len(expected_numbers), issues)
        target_rows = [
            (row_number, {key: value or "" for key, value in row.items()})
            for row_number, row in enumerate(reader, start=2)
            if (row.get("과목") or "") == subject
        ]

    parsed_numbers: list[int] = []
    if len(target_rows) != len(expected_numbers):
        issues.append(
            DataQualityIssue(
                "error",
                "WRONG_ROW_COUNT",
                None,
                "",
                "문항번호",
                f"대상 과목 행 수 {len(target_rows)}, 기대값 {len(expected_numbers)}",
            )
        )

    for row_number, row in target_rows:
        question_number = row["문항번호"]
        try:
            parsed_numbers.append(int(question_number))
        except ValueError:
            issues.append(
                DataQualityIssue(
                    "error", "INVALID_QUESTION_NUMBER", row_number,
                    question_number, "문항번호", "문항번호가 정수가 아님", question_number,
                )
            )
        _inspect_row(row_number, row, issues)

    expected = set(expected_numbers)
    actual = set(parsed_numbers)
    missing = sorted(expected - actual)
    unexpected = sorted(actual - expected)
    duplicates = sorted(number for number in actual if parsed_numbers.count(number) > 1)
    if missing:
        issues.append(DataQualityIssue(
            "error", "MISSING_QUESTION_NUMBERS", None, "", "문항번호",
            "누락 문항: " + ", ".join(map(str, missing)),
        ))
    if unexpected:
        issues.append(DataQualityIssue(
            "error", "UNEXPECTED_QUESTION_NUMBERS", None, "", "문항번호",
            "범위 밖 문항: " + ", ".join(map(str, unexpected)),
        ))
    if duplicates:
        issues.append(DataQualityIssue(
            "error", "DUPLICATE_QUESTION_NUMBERS", None, "", "문항번호",
            "중복 문항: " + ", ".join(map(str, duplicates)),
        ))
    return _report(path, subject, len(target_rows), len(expected_numbers), issues)


def write_quality_report(report: DataQualityReport, output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    temporary = output_path.with_suffix(output_path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(report.as_dict(), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    temporary.replace(output_path)


def _inspect_row(
    row_number: int,
    row: dict[str, str],
    issues: list[DataQualityIssue],
) -> None:
    question_number = row["문항번호"]
    text_fields = ("문제", "선택지1", "선택지2", "선택지3", "선택지4", "선택지5")
    for field in text_fields:
        value = row[field]
        if not value.strip():
            issues.append(DataQualityIssue(
                "error", "EMPTY_TEXT", row_number, question_number, field,
                f"{field} 내용이 비어 있음",
            ))
            continue
        for code, character in _invalid_characters(value):
            issues.append(DataQualityIssue(
                "error", code, row_number, question_number, field,
                f"손상 가능 문자가 포함됨: U+{ord(character):04X}",
                _preview(value),
            ))
        if _SECTION_HEADER.search(value):
            issues.append(DataQualityIssue(
                "error", "CROSS_SECTION_HEADER", row_number, question_number, field,
                "다음 과목/구역 제목으로 보이는 문자열이 문항에 혼입됨",
                _preview(value),
            ))

    if 0 < len(row["문제"].strip()) < 20:
        issues.append(DataQualityIssue(
            "warning", "SHORT_QUESTION", row_number, question_number, "문제",
            f"문제 본문이 비정상적으로 짧을 수 있음: {len(row['문제'].strip())}자",
            _preview(row["문제"]),
        ))
    for index in range(1, 6):
        field = f"선택지{index}"
        value = row[field].strip()
        if value and len(value) < 3:
            label_note = " (조합형 label 선택지로 보임)" if _LABEL_ONLY_CHOICE.fullmatch(value) else ""
            issues.append(DataQualityIssue(
                "warning", "SHORT_CHOICE", row_number, question_number, field,
                f"선택지가 3자 미만임{label_note}", value,
            ))

    answer = row["공식정답"].strip()
    if not _ANSWER.fullmatch(answer):
        issues.append(DataQualityIssue(
            "error", "INVALID_ANSWER", row_number, question_number, "공식정답",
            "공식정답은 쉼표로 구분된 1~5 값이어야 함", answer,
        ))
    elif len(set(answer.split(","))) != len(answer.split(",")):
        issues.append(DataQualityIssue(
            "error", "DUPLICATE_ACCEPTED_ANSWER", row_number, question_number,
            "공식정답", "공식정답 값이 중복됨", answer,
        ))


def _invalid_characters(value: str) -> list[tuple[str, str]]:
    found: list[tuple[str, str]] = []
    for character in value:
        category = unicodedata.category(character)
        if character == "\ufffd":
            found.append(("REPLACEMENT_CHARACTER", character))
        elif category == "Co":
            found.append(("PRIVATE_USE_CHARACTER", character))
        elif category == "Cs":
            found.append(("SURROGATE_CHARACTER", character))
        elif category == "Cc" and character not in "\t\r\n":
            found.append(("CONTROL_CHARACTER", character))
    return found


def _preview(value: str, limit: int = 180) -> str:
    return value if len(value) <= limit else value[:limit] + "…"


def _report(
    path: Path,
    subject: str,
    row_count: int,
    expected_count: int,
    issues: list[DataQualityIssue],
) -> DataQualityReport:
    return DataQualityReport(
        input_csv=str(path.resolve()),
        subject=subject,
        target_row_count=row_count,
        expected_question_count=expected_count,
        blocking_issue_count=sum(issue.severity == "error" for issue in issues),
        warning_count=sum(issue.severity == "warning" for issue in issues),
        issues=tuple(issues),
    )


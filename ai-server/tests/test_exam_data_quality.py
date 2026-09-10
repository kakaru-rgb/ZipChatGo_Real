import csv
from pathlib import Path

from app.evaluation.exam_data_quality import inspect_reviewed_exam_csv
from app.evaluation.production_agent_passthrough import REQUIRED_COLUMNS


def _write_rows(path: Path, rows: list[dict[str, str]]) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=REQUIRED_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)


def _row(number: int) -> dict[str, str]:
    return {
        "연도": "2024", "시험": "2차", "교시": "1교시", "과목": "대상과목",
        "문항번호": str(number), "문제": "충분한 길이를 가진 정상적인 시험 문제 본문입니다.",
        "선택지1": "정상 선택지 하나", "선택지2": "정상 선택지 둘",
        "선택지3": "정상 선택지 셋", "선택지4": "정상 선택지 넷",
        "선택지5": "정상 선택지 다섯", "공식정답": "3", "원본PDF": "source.pdf",
        "페이지": "1", "추출상태": "정상", "검토메모": "",
    }


def test_quality_check_accepts_complete_numbered_data(tmp_path: Path) -> None:
    path = tmp_path / "input.csv"
    _write_rows(path, [_row(number) for number in range(1, 41)])
    report = inspect_reviewed_exam_csv(path, subject="대상과목")
    assert report.passed
    assert report.target_row_count == 40


def test_quality_check_reports_header_contamination_and_private_use(tmp_path: Path) -> None:
    path = tmp_path / "input.csv"
    rows = [_row(number) for number in range(1, 41)]
    rows[-1]["선택지5"] += " 제2 과목: 다음 과목\ue000"
    _write_rows(path, rows)
    report = inspect_reviewed_exam_csv(path, subject="대상과목")
    codes = {issue.code for issue in report.issues}
    assert not report.passed
    assert "CROSS_SECTION_HEADER" in codes
    assert "PRIVATE_USE_CHARACTER" in codes


def test_short_label_choice_is_warning_not_blocking(tmp_path: Path) -> None:
    path = tmp_path / "input.csv"
    rows = [_row(number) for number in range(1, 41)]
    rows[0]["선택지1"] = "ㄱ"
    _write_rows(path, rows)
    report = inspect_reviewed_exam_csv(path, subject="대상과목")
    assert report.passed
    assert any(issue.code == "SHORT_CHOICE" for issue in report.issues)


import csv

from app.evaluation.local_exam_pdf import (
    OFFICIAL_ANSWERS_2024,
    _make_local_question,
    load_exam_source_csv,
    save_exam_source_csv,
)
from app.evaluation.exam_text_normalizer import (
    is_combination_question,
    normalize_exam_choice,
    normalize_exam_text,
)
from app.evaluation.realtor_exam import ExamQuestion, PreparedExam


def test_local_question_parser_uses_last_choice_marker() -> None:
    raw = (
        "67. 시행령 제13조①의 내용이다. 옳은 것은?\n"
        "①첫째\n②둘째\n③셋째\n④넷째\n⑤다섯째"
    )

    item = _make_local_question(67, raw, 10)

    assert item.question == "시행령 제13조①의 내용이다. 옳은 것은?"
    assert item.choices == ("첫째", "둘째", "셋째", "넷째", "다섯째")


def test_2024_answer_keys_have_expected_counts_and_multi_answer() -> None:
    assert [len(values) for values in OFFICIAL_ANSWERS_2024.values()] == [80, 80, 40]
    assert OFFICIAL_ANSWERS_2024["1차_1교시"][66] == "1,2,3,4,5"


def test_korean_spacing_and_combination_choice_are_normalized() -> None:
    assert normalize_exam_text("토지의특성에관한설명으로옳은것은?") == (
        "토지의 특성에 관한 설명으로 옳은 것은?"
    )
    choice = normalize_exam_choice("ㄱ: 필지, ㄴ: 소지")
    assert choice == "ㄱ = 필지; ㄴ = 소지"
    assert is_combination_question("(ㄱ)과 (ㄴ)에 들어갈 내용은?", [choice])
    assert normalize_exam_text("토지에건물이나그밖의정착물이없다") == (
        "토지에 건물이나 그 밖의 정착물이 없다"
    )
    assert normalize_exam_text("주택도시기금법에따른공공임대주택") == (
        "주택도시기금법에 따른 공공임대주택"
    )


def test_source_csv_round_trip_preserves_accepted_answers(tmp_path) -> None:
    question = ExamQuestion(
        year=2024,
        paper_id="1차_1교시",
        paper_name="시험문제지",
        subject="부동산학개론",
        question_no=1,
        question="옳은 것은?",
        choices=["하나", "둘", "셋", "넷", "다섯"],
        correct_answer=1,
        accepted_answers=[1, 2, 3, 4, 5],
        source_pdf="시험문제지.pdf",
        source_page=1,
    )
    exam = PreparedExam(
        year=2024,
        questions=[question],
        source_hashes={},
    )
    path = tmp_path / "questions.csv"

    save_exam_source_csv(exam, path)
    loaded = load_exam_source_csv(path)

    assert path.read_bytes().startswith(b"\xef\xbb\xbf")
    assert loaded.questions[0].accepted_answers == [1, 2, 3, 4, 5]
    with path.open("r", encoding="utf-8-sig", newline="") as stream:
        row = next(csv.DictReader(stream))
    assert row["공식정답"] == "1,2,3,4,5"

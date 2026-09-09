import csv
import json
from types import SimpleNamespace

from app.evaluation.exam_prompts import (
    REALTOR_EXAM_INSTRUCTIONS,
    build_exam_input,
)
from app.evaluation.realtor_exam import (
    ExamQuestion,
    PreparedExam,
    evaluate_exam,
    make_result_row,
    write_result_csv,
)
from app.evaluation.realtor_exam_agent import RealtorExamEvaluator
from app.providers.openai_provider import SEARCH_REAL_ESTATE_LAW_TOOL
from app.retrievers.law_retriever import LawSearchItem, LawSearchResponse
from app.tools.real_estate_law import RealEstateLawSearchTool


def _question(subject: str = "민법") -> ExamQuestion:
    return ExamQuestion(
        year=2024,
        paper_id="1차_1교시",
        paper_name="2024 문제지",
        subject=subject,
        question_no=41,
        question="계약금 해제에 관한 설명으로 옳은 것은?",
        choices=["선택 A", "선택 B", "선택 C", "선택 D", "선택 E"],
        correct_answer=3,
        source_pdf="exam.pdf",
    )


class _QueuedResponses:
    def __init__(self, responses):
        self._responses = list(responses)
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        return self._responses.pop(0)


def _client(*responses):
    return SimpleNamespace(responses=_QueuedResponses(responses))


def _answer_response(answer: int = 3, resolved_items=None, choice_judgments=None):
    judgments = choice_judgments or [
        {
            "choice_number": number,
            "judgment": "참" if number == answer else "거짓",
            "basis": f"선택지 {number} 검토",
        }
        for number in range(1, 6)
    ]
    return SimpleNamespace(
        output=[],
        output_text=json.dumps(
            {
                "predicted_answer": answer,
                "choice_judgments": judgments,
                "resolved_items": resolved_items or [],
                "explanation": "계약금 해제 요건을 검토했습니다.",
            },
            ensure_ascii=False,
        ),
    )


def test_exam_prompt_and_input_are_separate_and_do_not_leak_answer() -> None:
    question = _question()
    content = build_exam_input(
        subject=question.subject,
        question_no=question.question_no,
        question=question.question,
        choices=question.choices,
    )

    assert "집찾GO 운영 챗봇의 상담 Prompt와 완전히 독립" in REALTOR_EXAM_INSTRUCTIONS
    assert "민법" in content
    assert "계약금 해제" in content
    assert "correct_answer" not in content
    assert "공식정답" not in content


def test_combination_question_adds_dedicated_solving_steps() -> None:
    content = build_exam_input(
        subject="부동산학개론",
        question_no=2,
        question="(ㄱ)과 (ㄴ)에 들어갈 내용으로 옳은 것은?",
        choices=[
            "ㄱ = 필지; ㄴ = 소지",
            "ㄱ = 지목; ㄴ = 나지",
            "ㄱ = 필지; ㄴ = 나지",
            "ㄱ = 지목; ㄴ = 나대지",
            "ㄱ = 필지; ㄴ = 나대지",
        ],
    )

    assert "문제유형: 복합 보기/빈칸 조합형" in content
    assert "각 항목을 독립적으로 판단" in content
    assert "조합 전체를 1~5번 선택지와 대조" in content
    assert "공식정답" not in content


def test_exam_evaluator_uses_structured_answer_without_production_endpoint() -> None:
    client = _client(_answer_response())

    row = RealtorExamEvaluator(client, model="gpt-4o-mini").evaluate(_question())

    assert row["챗봇예측"] == "3"
    assert row["공식정답"] == "3"
    assert row["정답여부"] == "O"
    assert row["평가모델"] == "gpt-4o-mini"
    assert row["RAG사용여부"] == "N"
    request = client.responses.calls[0]
    assert request["instructions"] == REALTOR_EXAM_INSTRUCTIONS
    assert request["text"]["format"]["type"] == "json_schema"
    assert "tools" not in request


def test_exam_evaluator_records_exam_only_rag_trace() -> None:
    function_call = SimpleNamespace(
        type="function_call",
        name="search_real_estate_law",
        arguments=json.dumps({"query": "민법 계약금 해제"}),
        call_id="call_exam_law",
    )
    client = _client(
        SimpleNamespace(output=[function_call], output_text=""),
        _answer_response(),
    )

    class Retriever:
        def search(self, query: str) -> LawSearchResponse:
            return LawSearchResponse(
                query=query,
                total_count=1,
                results=[
                    LawSearchItem(
                        rank=1,
                        score=0.9,
                        law_name="민법",
                        article_number="제565조",
                        text="계약금에 관한 조문",
                        source_url="https://www.law.go.kr/example",
                        filename="민법.jsonl",
                    )
                ],
            )

    row = RealtorExamEvaluator(
        client,
        model="gpt-4o-mini",
        law_search=RealEstateLawSearchTool(Retriever()).search,
    ).evaluate(_question())

    assert row["RAG사용여부"] == "Y"
    assert row["RAG검색어"] == "민법 계약금 해제"
    assert row["RAG검색결과수"] == "1"
    assert "제565조" in row["RAG검색근거"]
    assert len(client.responses.calls) == 2
    assert client.responses.calls[0]["tools"] == [SEARCH_REAL_ESTATE_LAW_TOOL]
    assert client.responses.calls[0]["tool_choice"] == {
        "type": "function",
        "name": "search_real_estate_law",
    }
    tool_output = client.responses.calls[1]["input"][-1]["output"]
    assert "grounding_notice" in tool_output


def test_model_decides_not_to_call_rag_for_general_theory() -> None:
    question = _question(subject="부동산학개론").model_copy(
        update={"question": "4P 마케팅믹스의 구성요소로 옳은 것은?"}
    )
    client = _client(_answer_response())

    def unexpected_law_search(_arguments):
        raise AssertionError("The model did not request the law tool")

    row = RealtorExamEvaluator(
        client,
        model="gpt-4o-mini",
        law_search=unexpected_law_search,
    ).evaluate(question)

    assert row["RAG사용여부"] == "N"
    assert client.responses.calls[0]["tools"] == [SEARCH_REAL_ESTATE_LAW_TOOL]


def test_exam_evaluator_stops_repeated_law_searches_and_requests_answer() -> None:
    function_responses = []
    for index in range(1, 4):
        function_responses.append(
            SimpleNamespace(
                output=[
                    SimpleNamespace(
                        type="function_call",
                        name="search_real_estate_law",
                        arguments=json.dumps({"query": f"법령 검색 {index}"}),
                        call_id=f"call_{index}",
                    )
                ],
                output_text="",
            )
        )
    client = _client(*function_responses, _answer_response())

    row = RealtorExamEvaluator(
        client,
        model="gpt-4o-mini",
        law_search=lambda _arguments: {"results": []},
    ).evaluate(_question(subject="공인중개사법령 및 중개실무"))

    assert row["오류"] == ""
    assert row["RAG검색어"] == "법령 검색 1 | 법령 검색 2 | 법령 검색 3"
    assert client.responses.calls[3]["tool_choice"] == "none"


def test_combination_answer_is_mapped_to_choice_and_wrong_number_is_corrected() -> None:
    question = _question(subject="부동산학개론").model_copy(
        update={
            "question_no": 2,
            "question": "(ㄱ)과 (ㄴ)에 들어갈 내용으로 옳은 것은?",
            "choices": [
                "ㄱ = 필지; ㄴ = 소지",
                "ㄱ = 지목; ㄴ = 나지",
                "ㄱ = 필지; ㄴ = 나지",
                "ㄱ = 지목; ㄴ = 나대지",
                "ㄱ = 필지; ㄴ = 나대지",
            ],
            "correct_answer": 2,
        }
    )
    client = _client(
        _answer_response(
            4,
            resolved_items=[
                {"label": "ㄱ", "value": "지목"},
                {"label": "ㄴ", "value": "나지"},
            ],
        )
    )

    row = RealtorExamEvaluator(client, model="gpt-4o-mini").evaluate(question)

    assert row["모델원래예측"] == "4"
    assert row["챗봇예측"] == "2"
    assert row["정답여부"] == "O"
    assert row["조합검증결과"] == "번호보정:4->2"
    assert '"label":"ㄱ","value":"지목"' in row["판단조합"]


def test_true_label_set_is_mapped_to_matching_choice() -> None:
    question = _question(subject="공인중개사법령 및 중개실무").model_copy(
        update={
            "question_no": 34,
            "question": "옳은 것을 모두 고른 것은? ㄱ. 설명 ㄴ. 설명 ㄷ. 설명 ㄹ. 설명",
            "choices": ["ㄴ, ㄷ", "ㄱ, ㄴ, ㄹ", "ㄱ, ㄷ, ㄹ", "ㄴ, ㄷ, ㄹ", "ㄱ, ㄴ, ㄷ, ㄹ"],
            "correct_answer": 4,
        }
    )
    client = _client(
        _answer_response(
            3,
            resolved_items=[
                {"label": "ㄱ", "value": "거짓"},
                {"label": "ㄴ", "value": "참"},
                {"label": "ㄷ", "value": "참"},
                {"label": "ㄹ", "value": "참"},
            ],
        )
    )

    row = RealtorExamEvaluator(client, model="gpt-4o-mini").evaluate(question)

    assert row["모델원래예측"] == "3"
    assert row["챗봇예측"] == "4"
    assert row["조합검증결과"] == "번호보정:3->4"


def test_false_label_set_is_used_when_question_asks_for_incorrect_items() -> None:
    question = _question(subject="공인중개사법령 및 중개실무").model_copy(
        update={
            "question_no": 4,
            "question": "틀린 것을 모두 고른 것은? ㄱ. 설명 ㄴ. 설명 ㄷ. 설명",
            "choices": ["ㄱ", "ㄴ", "ㄷ", "ㄱ, ㄷ", "ㄴ, ㄷ"],
            "correct_answer": 3,
        }
    )
    client = _client(
        _answer_response(
            1,
            resolved_items=[
                {"label": "ㄱ", "value": "참"},
                {"label": "ㄴ", "value": "참"},
                {"label": "ㄷ", "value": "거짓"},
            ],
        )
    )

    row = RealtorExamEvaluator(client, model="gpt-4o-mini").evaluate(question)

    assert row["챗봇예측"] == "3"
    assert row["조합검증결과"] == "번호보정:1->3"


def test_result_csv_is_excel_friendly_utf8(tmp_path) -> None:
    row = RealtorExamEvaluator(
        _client(_answer_response()),
        model="gpt-4o-mini",
    ).evaluate(_question())
    path = tmp_path / "result.csv"

    write_result_csv([row], path)

    assert path.read_bytes().startswith(b"\xef\xbb\xbf")
    with path.open("r", encoding="utf-8-sig", newline="") as stream:
        saved = list(csv.DictReader(stream))
    assert saved[0]["문제"].startswith("계약금 해제")
    assert saved[0]["정답여부"] == "O"
    assert saved[0]["RAG사용여부"] == "N"


def test_evaluate_exam_filters_subject_before_applying_limit(tmp_path) -> None:
    first = _question(subject="부동산학개론").model_copy(
        update={"question_no": 1}
    )
    target = _question(subject="공인중개사법령 및 중개실무").model_copy(
        update={"question_no": 2}
    )
    exam = PreparedExam.model_construct(
        schema_version=3,
        year=2024,
        questions=[first, target],
        source_hashes={},
        expected_total=200,
    )

    class RecordingEvaluator:
        def __init__(self) -> None:
            self.questions = []

        def evaluate(self, question):
            self.questions.append(question)
            return make_result_row(question, 3, "평가 결과", "")

    evaluator = RecordingEvaluator()
    rows = evaluate_exam(
        exam,
        evaluator,
        tmp_path / "subject.csv",
        subject="공인중개사법령 및 중개실무",
        limit=1,
        delay_seconds=0,
    )

    assert evaluator.questions == [target]
    assert len(rows) == 1
    assert rows[0]["과목"] == "공인중개사법령 및 중개실무"

from __future__ import annotations

import json
import re
import time
from collections.abc import Callable
from typing import Any, Literal

from openai import APIError
from pydantic import BaseModel, Field, model_validator

from app.evaluation.exam_prompts import (
    REALTOR_EXAM_INSTRUCTIONS,
    build_exam_input,
)
from app.evaluation.realtor_exam import ExamQuestion, make_result_row
from app.providers.openai_provider import SEARCH_REAL_ESTATE_LAW_TOOL
from app.retrievers.law_retriever import LawRetrievalError
from app.tools.real_estate_law import RealEstateLawSearchToolError


ExamLawSearch = Callable[[dict[str, Any]], dict[str, Any]]


EXAM_ANSWER_FORMAT = {
    "type": "json_schema",
    "name": "realtor_exam_answer",
    "schema": {
        "type": "object",
        "properties": {
            "predicted_answer": {
                "type": "integer",
                "minimum": 1,
                "maximum": 5,
            },
            "choice_judgments": {
                "type": "array",
                "minItems": 5,
                "maxItems": 5,
                "items": {
                    "type": "object",
                    "properties": {
                        "choice_number": {
                            "type": "integer",
                            "minimum": 1,
                            "maximum": 5,
                        },
                        "judgment": {
                            "type": "string",
                            "enum": ["참", "거짓"],
                        },
                        "basis": {"type": "string"},
                    },
                    "required": ["choice_number", "judgment", "basis"],
                    "additionalProperties": False,
                },
            },
            "resolved_items": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "label": {
                            "type": "string",
                            "pattern": "^[ㄱ-ㅎ]$",
                        },
                        "value": {"type": "string"},
                    },
                    "required": ["label", "value"],
                    "additionalProperties": False,
                },
            },
            "explanation": {"type": "string"},
        },
        "required": [
            "predicted_answer",
            "choice_judgments",
            "resolved_items",
            "explanation",
        ],
        "additionalProperties": False,
    },
    "strict": True,
}


class ResolvedItem(BaseModel):
    label: str = Field(pattern=r"^[ㄱ-ㅎ]$")
    value: str


class ChoiceJudgment(BaseModel):
    choice_number: int = Field(ge=1, le=5)
    judgment: Literal["참", "거짓"]
    basis: str


class ExamAgentAnswer(BaseModel):
    predicted_answer: int = Field(ge=1, le=5)
    choice_judgments: list[ChoiceJudgment]
    resolved_items: list[ResolvedItem]
    explanation: str

    @model_validator(mode="after")
    def validate_choice_judgments(self) -> "ExamAgentAnswer":
        numbers = sorted(item.choice_number for item in self.choice_judgments)
        if numbers != [1, 2, 3, 4, 5]:
            raise ValueError("choice_judgments must contain choices 1 through 5 once")
        return self


class RealtorExamEvaluator:
    """Runs an exam-only prompt and RAG loop without calling the production chatbot."""

    def __init__(
        self,
        client: Any,
        model: str,
        law_search: ExamLawSearch | None = None,
        max_attempts: int = 3,
        max_tool_rounds: int = 5,
    ) -> None:
        self._client = client
        self._model = model
        self._law_search = law_search
        self._max_attempts = max_attempts
        self._max_tool_rounds = max_tool_rounds

    def evaluate(self, question: ExamQuestion) -> dict[str, str]:
        last_error = ""
        for attempt in range(1, self._max_attempts + 1):
            try:
                answer, trace = self._solve(question)
                final_prediction, combination_check = _check_combination_choice(
                    question,
                    answer,
                )
                answer_text = (
                    f"{answer.explanation.strip()}\n\n"
                    f"최종 정답: {final_prediction}번"
                )
                return make_result_row(
                    question,
                    final_prediction,
                    answer_text,
                    "",
                    model=self._model,
                    original_prediction=answer.predicted_answer,
                    choice_judgments=[
                        item.model_dump() for item in answer.choice_judgments
                    ],
                    resolved_items=[item.model_dump() for item in answer.resolved_items],
                    combination_check=combination_check,
                    rag_used=trace["rag_used"],
                    rag_queries=trace["rag_queries"],
                    rag_result_count=trace["rag_result_count"],
                    rag_sources=trace["rag_sources"],
                )
            except (
                APIError,
                ValueError,
                TypeError,
                json.JSONDecodeError,
            ) as exception:
                last_error = f"{type(exception).__name__}: {exception}"
                if attempt < self._max_attempts:
                    time.sleep(2 ** (attempt - 1))
        return make_result_row(
            question,
            None,
            "",
            last_error,
            model=self._model,
        )

    def _solve(
        self,
        question: ExamQuestion,
    ) -> tuple[ExamAgentAnswer, dict[str, Any]]:
        running_input: list[Any] = [
            {
                "role": "user",
                "content": build_exam_input(
                    subject=question.subject,
                    question_no=question.question_no,
                    question=question.question,
                    choices=question.choices,
                ),
            }
        ]
        tools = [SEARCH_REAL_ESTATE_LAW_TOOL] if self._law_search is not None else []

        rag_queries: list[str] = []
        rag_results: list[dict[str, Any]] = []
        for round_index in range(self._max_tool_rounds):
            request_options: dict[str, Any] = {
                "model": self._model,
                "instructions": REALTOR_EXAM_INSTRUCTIONS,
                "input": running_input,
                "text": {"format": EXAM_ANSWER_FORMAT},
                "store": False,
            }
            if tools:
                request_options["tools"] = tools
                if _requires_law_search(question) and not rag_queries:
                    request_options["tool_choice"] = {
                        "type": "function",
                        "name": "search_real_estate_law",
                    }
                elif (
                    len(rag_queries) >= 3
                    or round_index == self._max_tool_rounds - 1
                ):
                    request_options["tool_choice"] = "none"
            response = self._client.responses.create(**request_options)
            function_calls = [
                item for item in response.output if item.type == "function_call"
            ]
            if not function_calls:
                answer = ExamAgentAnswer.model_validate_json(response.output_text)
                return answer, _build_trace(rag_queries, rag_results)

            running_input.extend(response.output)
            for function_call in function_calls:
                if (
                    function_call.name != "search_real_estate_law"
                    or self._law_search is None
                ):
                    tool_result = {
                        "status": "rejected",
                        "reason": "Unavailable exam-only tool",
                    }
                else:
                    arguments = json.loads(function_call.arguments)
                    query = str(arguments.get("query", "")).strip()
                    if not query:
                        tool_result = {
                            "status": "rejected",
                            "reason": "Blank law query",
                        }
                    else:
                        rag_queries.append(query)
                        try:
                            tool_result = self._law_search(arguments)
                            rag_results.extend(tool_result.get("results", []))
                        except (
                            LawRetrievalError,
                            RealEstateLawSearchToolError,
                        ) as exception:
                            tool_result = {
                                "status": "error",
                                "reason": str(exception),
                            }
                running_input.append(
                    {
                        "type": "function_call_output",
                        "call_id": function_call.call_id,
                        "output": json.dumps(
                            tool_result,
                            ensure_ascii=False,
                            separators=(",", ":"),
                        ),
                    }
                )
        raise ValueError("Exam-only tool call limit exceeded")


def _build_trace(
    queries: list[str],
    results: list[dict[str, Any]],
) -> dict[str, Any]:
    sources = []
    for result in results:
        source = {
            "law_name": result.get("law_name"),
            "article_number": result.get("article_number"),
            "score": result.get("score"),
            "source_url": result.get("source_url"),
        }
        if source not in sources:
            sources.append(source)
    return {
        "rag_used": bool(queries),
        "rag_queries": queries,
        "rag_result_count": len(results),
        "rag_sources": sources,
    }


_ASSIGNMENT = re.compile(
    r"([ㄱ-ㅎ])\s*=\s*(.*?)(?=\s*;\s*[ㄱ-ㅎ]\s*=|$)"
)


def _check_combination_choice(
    question: ExamQuestion,
    answer: ExamAgentAnswer,
) -> tuple[int, str]:
    parsed_choices = [_parse_assignments(choice) for choice in question.choices]
    assignment_choices = [item for item in parsed_choices if len(item) >= 2]
    if len(assignment_choices) >= 2:
        return _check_assignment_choice(answer, parsed_choices)
    return _check_label_set_choice(question, answer)


def _check_assignment_choice(
    answer: ExamAgentAnswer,
    parsed_choices: list[dict[str, str]],
) -> tuple[int, str]:
    assignment_choices = [item for item in parsed_choices if len(item) >= 2]

    resolved = {
        item.label: _comparison_value(item.value)
        for item in answer.resolved_items
        if item.value.strip()
    }
    required_labels = set().union(*(item.keys() for item in assignment_choices))
    if not required_labels or not required_labels.issubset(resolved):
        return answer.predicted_answer, "판단조합부족"

    matches = [
        index
        for index, assignments in enumerate(parsed_choices, start=1)
        if assignments
        and all(resolved.get(label) == value for label, value in assignments.items())
        and set(assignments) == required_labels
    ]
    if len(matches) != 1:
        return answer.predicted_answer, "선택지대조불가"
    matched = matches[0]
    if matched == answer.predicted_answer:
        return matched, "일치"
    return matched, f"번호보정:{answer.predicted_answer}->{matched}"


_LABEL_SET_CHOICE = re.compile(r"^[ㄱ-ㅎ\s,·ㆍ]+$")


def _check_label_set_choice(
    question: ExamQuestion,
    answer: ExamAgentAnswer,
) -> tuple[int, str]:
    parsed_choices = [_parse_label_set(choice) for choice in question.choices]
    if sum(bool(labels) for labels in parsed_choices) < 2:
        return answer.predicted_answer, "해당없음"

    required_labels = set().union(*parsed_choices)
    resolved: dict[str, bool] = {}
    for item in answer.resolved_items:
        truth = _parse_truth_value(item.value)
        if truth is not None:
            resolved[item.label] = truth
    if not required_labels.issubset(resolved):
        return answer.predicted_answer, "판단조합부족"

    select_truth = not _asks_for_incorrect_items(question.question)
    selected_labels = {
        label for label in required_labels if resolved[label] is select_truth
    }
    matches = [
        index
        for index, labels in enumerate(parsed_choices, start=1)
        if labels == selected_labels
    ]
    if len(matches) != 1:
        return answer.predicted_answer, "선택지대조불가"
    matched = matches[0]
    if matched == answer.predicted_answer:
        return matched, "일치"
    return matched, f"번호보정:{answer.predicted_answer}->{matched}"


def _parse_label_set(choice: str) -> set[str]:
    normalized = choice.strip()
    if not normalized or _LABEL_SET_CHOICE.fullmatch(normalized) is None:
        return set()
    return set(re.findall(r"[ㄱ-ㅎ]", normalized))


def _parse_truth_value(value: str) -> bool | None:
    normalized = re.sub(r"\s+", "", value).lower()
    if normalized in {"참", "옳음", "옳다", "true", "o"}:
        return True
    if normalized in {"거짓", "틀림", "틀리다", "false", "x"}:
        return False
    return None


def _asks_for_incorrect_items(question: str) -> bool:
    normalized = re.sub(r"\s+", "", question)
    return "틀린것을모두" in normalized or "옳지않은것을모두" in normalized


def _parse_assignments(choice: str) -> dict[str, str]:
    return {
        match.group(1): _comparison_value(match.group(2))
        for match in _ASSIGNMENT.finditer(choice)
    }


def _comparison_value(value: str) -> str:
    return re.sub(r"[\s,.;:]", "", value).strip()


def _requires_law_search(question: ExamQuestion) -> bool:
    subject = question.subject.replace(" ", "")
    return "법" in subject or "중개실무" in subject

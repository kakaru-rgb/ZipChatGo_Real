from __future__ import annotations

import csv
import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Sequence
from zoneinfo import ZoneInfo

from app.evaluation.exam_scope_classification import classify_corpus_scope
from app.evaluation.production_agent_observer import ProductionAgentObserver, ToolHandler
from app.evaluation.production_answer_parser import parse_final_answer
from app.evaluation.realtor_exam import ExamQuestion


EVALUATION_MODE = "production_agent_passthrough"
REQUIRED_COLUMNS = (
    "연도", "시험", "교시", "과목", "문항번호", "문제",
    "선택지1", "선택지2", "선택지3", "선택지4", "선택지5",
    "공식정답", "원본PDF", "페이지", "추출상태", "검토메모",
)


@dataclass(frozen=True)
class LoadedQuestion:
    row_number: int
    question: ExamQuestion | None
    raw: dict[str, str]
    error: str = ""


@dataclass(frozen=True)
class PassthroughRuntime:
    provider: Any
    handlers: dict[str, ToolHandler]
    observer: ProductionAgentObserver
    model: str


def load_reviewed_exam_csv(path: Path) -> list[LoadedQuestion]:
    loaded: list[LoadedQuestion] = []
    with path.open("r", encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        headers = tuple(reader.fieldnames or ())
        missing = [column for column in REQUIRED_COLUMNS if column not in headers]
        if missing:
            return [
                LoadedQuestion(
                    row_number=1,
                    question=None,
                    raw={},
                    error="필수 컬럼 누락: " + ", ".join(missing),
                )
            ]
        for row_number, row in enumerate(reader, start=2):
            raw = {key: value if value is not None else "" for key, value in row.items()}
            try:
                question = _question_from_row(raw)
                error = "" if raw["추출상태"] == "정상" else f"검수 상태 오류: {raw['추출상태']}"
                if error:
                    question = None
            except (KeyError, TypeError, ValueError) as exception:
                question = None
                error = f"입력 행 오류: {type(exception).__name__}: {exception}"
            loaded.append(LoadedQuestion(row_number, question, raw, error))
    if not loaded:
        loaded.append(LoadedQuestion(1, None, {}, "입력 CSV에 문항이 없음"))
    return loaded


def build_user_message(question: ExamQuestion) -> str:
    choices = "\n".join(
        f"{index}. {choice}" for index, choice in enumerate(question.choices, start=1)
    )
    return (
        "다음 공인중개사 객관식 문제를 풀어줘.\n"
        "정답 번호와 판단 이유를 알려줘.\n\n"
        f"[문제]\n{question.question}\n\n"
        f"[선택지]\n{choices}"
    )


def evaluate_question(
    question: ExamQuestion,
    runtime: PassthroughRuntime,
    *,
    run_id: str,
    evaluated_at: str,
    git_commit: str,
) -> dict[str, str]:
    raw_response = ""
    actions = "[]"
    error = ""
    try:
        wrapped = {
            name: runtime.observer.wrap_handler(name, handler)
            for name, handler in runtime.handlers.items()
        }
        reply = runtime.provider.generate(
            message=build_user_message(question),
            app_state=None,
            search_properties=wrapped.get("search_properties"),
            find_transit_station=wrapped.get("find_transit_station"),
            get_adjacent_legal_dongs=wrapped.get("get_adjacent_legal_dongs"),
            search_real_estate_law=wrapped.get("search_real_estate_law"),
        )
        raw_response = reply.message
        actions = json.dumps(
            [action.model_dump() for action in reply.actions],
            ensure_ascii=False,
            separators=(",", ":"),
        )
    except Exception as exception:
        error = f"{type(exception).__name__}: {exception}"

    parsed = parse_final_answer(raw_response) if not error else None
    prediction = parsed.answer if parsed else None
    accepted = question.accepted_answers or [question.correct_answer]
    correct = "오류" if error else "판정불가" if prediction is None else "O" if prediction in accepted else "X"
    scope = classify_corpus_scope(question)
    calls = runtime.observer.calls
    law_traces = runtime.observer.law_traces()
    law_results = [
        item
        for trace in law_traces
        for item in trace.get("retrieval_results", [])
    ]
    citation_status = _explicit_evidence_status(raw_response, law_traces, error)
    return {
        "RunID": run_id,
        "평가일시": evaluated_at,
        "GitCommit": git_commit,
        "EvaluationMode": EVALUATION_MODE,
        "AgentModel": runtime.model,
        "연도": str(question.year),
        "시험": question.paper_id.split("_", 1)[0],
        "교시": question.paper_id.split("_", 1)[1],
        "과목": question.subject,
        "문항번호": str(question.question_no),
        "문제": question.question,
        **{f"선택지{index}": choice for index, choice in enumerate(question.choices, 1)},
        "공식정답": ",".join(str(item) for item in accepted),
        "Agent최종답": str(prediction or ""),
        "정답여부": correct,
        "답번호추출상태": parsed.status if parsed else "실행오류",
        "AgentRawResponse": raw_response,
        "AgentActions": actions,
        "호출Tool목록": " | ".join(call.name for call in calls),
        "전체Tool호출횟수": str(len(calls)),
        "비법률Tool오호출여부": "Y" if any(call.name != "search_real_estate_law" for call in calls) else "N",
        "법률Tool자율호출여부": "Y" if law_traces else "N",
        "법률Tool호출횟수": str(len(law_traces)),
        "모델생성Query": " | ".join(str(trace["model_query"]) for trace in law_traces),
        "실제RetrievalQuery": " | ".join(str(trace["retrieval_query"]) for trace in law_traces),
        "검색결과수": str(sum(int(trace["retrieval_result_count"]) for trace in law_traces)),
        "검색법령조문": " | ".join(
            f"{item.get('law_name', '')} {item.get('article_number', '')}".strip()
            for item in law_results
        ),
        "검색Score": " | ".join(str(item.get("score", "")) for item in law_results),
        "법률ToolTrace": json.dumps(law_traces, ensure_ascii=False, separators=(",", ":")),
        "검색근거명시상태": citation_status,
        "CorpusScope": scope.corpus_scope,
        "CorpusScope근거법령": " | ".join(scope.basis_laws),
        "CorpusScope분류이유": scope.reason,
        "2024_2026개정위험": scope.temporal_risk,
        "개정위험사유": scope.temporal_risk_reason,
        "오류": error,
    }


def make_input_error_row(
    item: LoadedQuestion,
    *,
    run_id: str,
    evaluated_at: str,
    git_commit: str,
    model: str,
) -> dict[str, str]:
    row = {field: "" for field in RESULT_FIELDS}
    row.update(
        {
            "RunID": run_id,
            "평가일시": evaluated_at,
            "GitCommit": git_commit,
            "EvaluationMode": EVALUATION_MODE,
            "AgentModel": model,
            "연도": item.raw.get("연도", ""),
            "시험": item.raw.get("시험", ""),
            "교시": item.raw.get("교시", ""),
            "과목": item.raw.get("과목", ""),
            "문항번호": item.raw.get("문항번호", ""),
            "문제": item.raw.get("문제", ""),
            "정답여부": "오류",
            "답번호추출상태": "입력오류",
            "오류": f"CSV {item.row_number}행: {item.error}",
        }
    )
    for index in range(1, 6):
        row[f"선택지{index}"] = item.raw.get(f"선택지{index}", "")
    row["공식정답"] = item.raw.get("공식정답", "")
    return row


def write_results(rows: Sequence[dict[str, str]], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    temporary = output_path.with_suffix(output_path.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=RESULT_FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    temporary.replace(output_path)


def evaluation_timestamp() -> str:
    return datetime.now(ZoneInfo("Asia/Seoul")).isoformat(timespec="seconds")


def _question_from_row(row: dict[str, str]) -> ExamQuestion:
    for column in REQUIRED_COLUMNS:
        if not row.get(column, "").strip() and column not in {"검토메모"}:
            raise ValueError(f"빈 필수 값: {column}")
    accepted = [int(value.strip()) for value in row["공식정답"].split(",")]
    if not accepted or any(value < 1 or value > 5 for value in accepted):
        raise ValueError("공식정답은 1~5여야 함")
    return ExamQuestion(
        year=int(row["연도"]),
        paper_id=f"{row['시험']}_{row['교시']}",
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


def _explicit_evidence_status(
    response: str,
    law_traces: Sequence[dict[str, Any]],
    error: str,
) -> str:
    if error:
        return "indeterminate"
    if not law_traces:
        return "not_used"
    results = [item for trace in law_traces for item in trace.get("retrieval_results", [])]
    if not results:
        return "tool_called_no_results"
    for item in results:
        law_name = str(item.get("law_name", "")).strip()
        article = str(item.get("article_number", "")).strip()
        if law_name and article and law_name in response and article in response:
            return "explicitly_cited"
    return "tool_called_not_explicit"


RESULT_FIELDS = (
    "RunID", "평가일시", "GitCommit", "EvaluationMode", "AgentModel",
    "연도", "시험", "교시", "과목", "문항번호", "문제",
    "선택지1", "선택지2", "선택지3", "선택지4", "선택지5",
    "공식정답", "Agent최종답", "정답여부", "답번호추출상태",
    "AgentRawResponse", "AgentActions", "호출Tool목록", "전체Tool호출횟수",
    "비법률Tool오호출여부", "법률Tool자율호출여부", "법률Tool호출횟수",
    "모델생성Query", "실제RetrievalQuery", "검색결과수", "검색법령조문",
    "검색Score", "법률ToolTrace", "검색근거명시상태", "CorpusScope",
    "CorpusScope근거법령", "CorpusScope분류이유", "2024_2026개정위험",
    "개정위험사유", "오류",
)


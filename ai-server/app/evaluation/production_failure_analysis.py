from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any, Sequence

from app.evaluation.exam_scope_classification import classify_corpus_scope
from app.evaluation.production_answer_parser import parse_final_answer
from app.evaluation.realtor_exam import ExamQuestion


FAILURE_TYPES = {
    "routing_failure",
    "retrieval_failure",
    "reasoning_failure",
    "grounding_validation_failure",
    "out_of_scope",
    "answer_parse_failure",
    "success",
    "needs_manual_review",
    "retrieval_vs_reasoning_review_required",
}

_GROUNDING_FAILURE_MARKERS = (
    "검색된 공식 법령 근거와 답변의 조문 인용이 일치하지 않아",
    "공식 현행 법령 검색에서 질문에 답할 만큼 관련된 조문을 찾지 못했습니다",
)


def classify_failure(row: dict[str, str]) -> tuple[str, str]:
    if row.get("오류", "").strip():
        return "needs_manual_review", "Agent 또는 Tool 실행 오류"
    raw_response = row.get("AgentRawResponse", "")
    if any(marker in raw_response for marker in _GROUNDING_FAILURE_MARKERS):
        return "grounding_validation_failure", "운영 Provider의 법률 grounding 안전 응답"
    if row.get("답번호추출상태", "").startswith("판정불가"):
        return "answer_parse_failure", "Agent 응답에서 명시적인 단일 최종 답 번호를 추출하지 못함"
    if row.get("정답여부") == "O":
        return "success", "Agent 최종 답이 공식 정답과 일치"
    if row.get("CorpusScope") == "out_of_scope":
        return "out_of_scope", row.get("CorpusScope분류이유", "Corpus 범위 밖")
    if row.get("법률Tool자율호출여부") != "Y":
        return "routing_failure", "in-scope 오답에서 법률 Tool을 호출하지 않음"

    traces = _load_law_traces(row.get("법률ToolTrace", ""))
    results = [
        item
        for trace in traces
        for item in trace.get("retrieval_results", [])
        if isinstance(item, dict)
    ]
    if not results:
        return "retrieval_failure", "법률 Tool을 호출했지만 검색 결과가 없음"

    basis_laws = {
        value.strip()
        for value in row.get("CorpusScope근거법령", "").split("|")
        if value.strip()
    }
    retrieved_laws = {
        str(item.get("law_name", "")).strip()
        for item in results
        if str(item.get("law_name", "")).strip()
    }
    if basis_laws and basis_laws.isdisjoint(retrieved_laws):
        return "retrieval_failure", "검색 결과 법령이 사후 CorpusScope 근거 법령과 일치하지 않음"
    if basis_laws and not basis_laws.isdisjoint(retrieved_laws):
        return (
            "retrieval_vs_reasoning_review_required",
            "대상 법령명은 검색됐지만 정답에 필요한 실제 조문이 Top-K에 있는지 수동 검토 필요",
        )
    return "needs_manual_review", "검색 결과의 정답 근거 적합성을 자동으로 확정할 수 없음"


def analyze_result_rows(rows: Sequence[dict[str, str]]) -> list[dict[str, str]]:
    analyzed: list[dict[str, str]] = []
    for row in rows:
        refreshed = _refresh_post_run_fields(row)
        failure_type, reason = classify_failure(refreshed)
        analyzed.append({
            **refreshed,
            "실패유형": failure_type,
            "실패유형판정근거": reason,
        })
    return analyzed


def analyze_result_csv(input_path: Path, output_path: Path) -> list[dict[str, str]]:
    if input_path.resolve() == output_path.resolve():
        raise ValueError("사후 분석 output은 baseline input과 달라야 합니다")
    with input_path.open("r", encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        rows = list(reader)
        original_fields = list(reader.fieldnames or ())
    analyzed = analyze_result_rows(rows)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    temporary = output_path.with_suffix(output_path.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(
            stream,
            fieldnames=[*original_fields, "실패유형", "실패유형판정근거"],
        )
        writer.writeheader()
        writer.writerows(analyzed)
    temporary.replace(output_path)
    return analyzed


def _load_law_traces(value: str) -> list[dict[str, Any]]:
    try:
        parsed = json.loads(value or "[]")
    except json.JSONDecodeError:
        return []
    return [item for item in parsed if isinstance(item, dict)] if isinstance(parsed, list) else []


def _refresh_post_run_fields(row: dict[str, str]) -> dict[str, str]:
    refreshed = dict(row)
    if not refreshed.get("오류", "").strip():
        parsed = parse_final_answer(refreshed.get("AgentRawResponse", ""))
        refreshed["Agent최종답"] = str(parsed.answer or "")
        refreshed["답번호추출상태"] = parsed.status
        accepted = _accepted_answers(refreshed.get("공식정답", ""))
        refreshed["정답여부"] = (
            "판정불가"
            if parsed.answer is None
            else "O" if parsed.answer in accepted else "X"
        )

    try:
        scope = classify_corpus_scope(_question_from_result_row(refreshed))
    except (KeyError, TypeError, ValueError):
        return refreshed
    refreshed.update({
        "CorpusScope": scope.corpus_scope,
        "CorpusScope근거법령": " | ".join(scope.basis_laws),
        "CorpusScope분류이유": scope.reason,
        "2024_2026개정위험": scope.temporal_risk,
        "개정위험사유": scope.temporal_risk_reason,
    })
    return refreshed


def _accepted_answers(value: str) -> set[int]:
    return {
        int(item.strip())
        for item in value.split(",")
        if item.strip().isdigit() and 1 <= int(item.strip()) <= 5
    }


def _question_from_result_row(row: dict[str, str]) -> ExamQuestion:
    accepted = sorted(_accepted_answers(row["공식정답"]))
    if not accepted:
        raise ValueError("공식정답 형식 오류")
    return ExamQuestion(
        year=int(row["연도"]),
        paper_id=f"{row['시험']}_{row['교시']}",
        paper_name="post-run-baseline",
        subject=row["과목"],
        question_no=int(row["문항번호"]),
        question=row["문제"],
        choices=[row[f"선택지{index}"] for index in range(1, 6)],
        correct_answer=accepted[0],
        accepted_answers=accepted,
        source_pdf="post-run-baseline.csv",
        source_page=0,
    )

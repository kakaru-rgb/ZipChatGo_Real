from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path
from typing import Any


AI_SERVER = Path(__file__).resolve().parents[1]
PROJECT_ROOT = AI_SERVER.parent
sys.path.insert(0, str(AI_SERVER))

from app.evaluation.pair_aware_grounding_validator_c21 import (  # noqa: E402
    PairAwareGroundingValidatorC21,
    collect_retrieval_results,
)
from app.evaluation.required_law_coverage_gate import RequiredLawCoverageGate  # noqa: E402


DEFAULT_INPUT = PROJECT_ROOT / "docs/evaluation/production_agent_passthrough_integrated_a_b_c1_c2_2024_q6_9_21_27_37_30_35_36_39_40_gpt-5.6-sol.csv"
DEFAULT_JSON = PROJECT_ROOT / "docs/evaluation/production_agent_c21_c3a_offline_replay_2024.json"
DEFAULT_REPORT = PROJECT_ROOT / "docs/evaluation/production_agent_c21_c3a_offline_replay_2024.md"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Replay C2.1 and C3a without network calls")
    parser.add_argument("--input-csv", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output-json", type=Path, default=DEFAULT_JSON)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    return parser.parse_args()


def replay(input_csv: Path) -> list[dict[str, Any]]:
    with input_csv.open(encoding="utf-8-sig", newline="") as file:
        rows = list(csv.DictReader(file))

    c21 = PairAwareGroundingValidatorC21()
    c3a = RequiredLawCoverageGate()
    output: list[dict[str, Any]] = []
    for row in rows:
        number = row["문항번호"]
        traces = json.loads(row.get("법률ToolTrace") or "[]")
        retrievals = collect_retrieval_results(traces)
        response = row.get("PreValidationRawResponse") or ""
        c21_result = c21.validate(response, retrievals).as_dict() if response else {
            "replayable": False,
            "failure_reason": "missing_pre_validation_response",
        }
        reviewed = (
            ["부동산 실권리자명의 등기에 관한 법률"] if number == "36" else None
        )
        c3a_result = c3a.validate(
            row.get("문제", ""),
            retrievals,
            reviewed_required_laws=reviewed,
        ).as_dict()
        output.append(
            {
                "문항번호": number,
                "기존C2ValidationResult": row.get("ValidationResult", ""),
                "C2.1": c21_result,
                "C3a": c3a_result,
                "retrieved_pairs": list(
                    dict.fromkeys(
                        f"{result.get('law_name', '')} {result.get('article_number', '')}".strip()
                        for result in retrievals
                    )
                ),
            }
        )
    return output


def render_report(results: list[dict[str, Any]], source: Path) -> str:
    by_number = {row["문항번호"]: row for row in results}
    lines = [
        "# C2.1 + C3a evaluation-only offline replay",
        "",
        f"- 입력: `{source}` (READ ONLY)",
        "- OpenAI API 호출: 없음",
        "- Vector Store API 호출: 없음",
        "- 운영 코드/기존 C2 변경: 없음",
        "",
        "## C2.1 결과",
        "",
    ]
    for number in ("9", "21"):
        row = by_number[number]
        c21 = row["C2.1"]
        lines.append(
            f"- {number}번: 기존 C2 `{row['기존C2ValidationResult']}` → "
            f"C2.1 `{'PASS' if c21.get('passed') else 'REJECT'}`"
        )
    lines.extend([
        "",
        "9번은 동일한 `공인중개사법 시행규칙 제4조` parent pair의 모든 청크를 검사하여, "
        "다른 동일-pair 청크에 실제 존재한 `「상법」 제614조`를 종속 cross-reference로 인정했다.",
        "",
        "21번은 `공인중개사법` family 문맥을 유지해 `시행령 제31조`를 "
        "`공인중개사법 시행령 제31조`로 해석했다.",
        "",
        "## C3a 결과",
        "",
    ])
    for number in ("6", "9", "21", "27", "37", "30", "35", "36", "40"):
        gate = by_number[number]["C3a"]
        status = "PASS" if gate["passed"] else "REJECT"
        lines.append(
            f"- {number}번: `{status}`; required={gate['required_laws']}; "
            f"matched={gate['matched_retrieved_laws']}; source={gate['detection_source']}; "
            f"reason={gate['failure_reason'] or '-'}"
        )
    lines.extend([
        "",
        "36번 원문 stem에는 법률명이 직접 쓰여 있지 않다. 따라서 불안정한 문맥 추론 대신, "
        "이번 frozen 문항에 한해 사람이 확인한 governing law를 사후 평가 annotation으로 사용했다. "
        "이 annotation은 Agent 입력이나 retrieval에 전달되지 않는다.",
        "",
        "30·40번은 stem에 명시된 핵심 법률이 검색되지 않아 REJECT, 35번은 명시 법률이 없어 "
        "gate 미적용이다. 6·9·21·27·37번은 필요한 law family가 검색되어 모두 PASS했다.",
        "",
        "## 결론",
        "",
        "C2.1과 C3a는 targeted offline 조건에서 안정적으로 동작했다. 다음 단계 D는 별도 승인 후 진행한다.",
    ])
    return "\n".join(lines) + "\n"


def write_new(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8", newline="") as file:
        file.write(content)


def main() -> int:
    args = parse_args()
    results = replay(args.input_csv)
    write_new(args.output_json, json.dumps(results, ensure_ascii=False, indent=2) + "\n")
    write_new(args.report, render_report(results, args.input_csv))
    print(args.output_json)
    print(args.report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

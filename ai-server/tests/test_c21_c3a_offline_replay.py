import csv
import json
from pathlib import Path

from app.evaluation.pair_aware_grounding_validator_c21 import (
    PairAwareGroundingValidatorC21,
    collect_retrieval_results,
)
from app.evaluation.required_law_coverage_gate import RequiredLawCoverageGate


FROZEN = (
    Path(__file__).resolve().parents[2]
    / "docs/evaluation/production_agent_passthrough_integrated_a_b_c1_c2_2024_q6_9_21_27_37_30_35_36_39_40_gpt-5.6-sol.csv"
)


def rows() -> dict[str, dict[str, str]]:
    with FROZEN.open(encoding="utf-8-sig", newline="") as file:
        return {row["문항번호"]: row for row in csv.DictReader(file)}


def retrievals(row: dict[str, str]) -> list[dict]:
    return collect_retrieval_results(json.loads(row["법률ToolTrace"] or "[]"))


def test_q9_and_q21_replay_pass_c21() -> None:
    data = rows()
    validator = PairAwareGroundingValidatorC21()
    for number in ("9", "21"):
        row = data[number]
        assert validator.validate(
            row["PreValidationRawResponse"], retrievals(row)
        ).passed is True


def test_supported_rows_are_not_blocked_by_c3a() -> None:
    data = rows()
    gate = RequiredLawCoverageGate()
    for number in ("6", "9", "21", "27", "37"):
        row = data[number]
        assert gate.validate(row["문제"], retrievals(row)).passed is True


def test_q36_reviewed_required_law_is_missing_and_rejected() -> None:
    row = rows()["36"]
    result = RequiredLawCoverageGate().validate(
        row["문제"],
        retrievals(row),
        reviewed_required_laws=["부동산 실권리자명의 등기에 관한 법률"],
    )
    assert result.passed is False
    assert result.failure_reason == "required_law_not_retrieved"


def test_q30_and_q40_missing_stem_laws_are_rejected_q35_not_applicable() -> None:
    data = rows()
    gate = RequiredLawCoverageGate()
    for number in ("30", "40"):
        row = data[number]
        assert gate.validate(row["문제"], retrievals(row)).passed is False
    row35 = data["35"]
    result35 = gate.validate(row35["문제"], retrievals(row35))
    assert result35.passed is True
    assert result35.applicable is False

"""Run the existing frozen 2024 Luna evaluation path over all 40 questions."""

from __future__ import annotations

import sys
from pathlib import Path

AI_SERVER_ROOT = Path(__file__).resolve().parents[1]
if str(AI_SERVER_ROOT) not in sys.path:
    sys.path.insert(0, str(AI_SERVER_ROOT))

from scripts import evaluate_law_store_v2_c23_luna_2024_targeted as targeted
from app.evaluation.law_store_v2_2024_targeted_scope import (
    TargetScopeAssessment,
    V2ScopeLabel,
)


targeted.EVALUATION_MODE = "production_agent_law_store_v2_c23_luna_2024_full40"
targeted.DEFAULT_OUTPUT = (
    targeted.PROJECT_ROOT
    / "docs/evaluation/production_agent_law_store_v2_c23_luna_2024_full40_live.csv"
)


def select_full_2024(rows):
    selected = [
        item for item in rows
        if item.question is not None
        and item.question.year == 2024
        and item.question.subject == targeted.SUBJECT
        and 1 <= item.question.question_no <= 40
    ]
    selected.sort(key=lambda item: item.question.question_no)
    numbers = tuple(item.question.question_no for item in selected)
    if numbers != tuple(range(1, 41)):
        raise ValueError("2024 questions 1-40 are missing, duplicated, or invalid")
    return tuple(selected)


original_finalize = targeted.finalize_rows


def finalize_full_2024(rows, selected, scope_by_id):
    # Human-reviewed scope exists for eight questions only. Keep the other
    # questions explicitly uncertain instead of inventing a corpus assessment.
    for question_id in range(1, 41):
        scope_by_id.setdefault(
            question_id,
            TargetScopeAssessment(
                question_id=question_id,
                label=V2ScopeLabel.UNCERTAIN,
                required_pairs=(),
                missing_pairs=(),
                required_non_article_sources=(),
                rationale="No reviewed question-level v2 scope assessment",
            ),
        )
    return original_finalize(rows, selected, scope_by_id)


targeted.select_target_questions = select_full_2024
targeted.finalize_rows = finalize_full_2024


if __name__ == "__main__":
    raise SystemExit(targeted.main())

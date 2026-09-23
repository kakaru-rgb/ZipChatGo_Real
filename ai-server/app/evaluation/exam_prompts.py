from __future__ import annotations

from collections.abc import Sequence

from app.evaluation.exam_text_normalizer import is_combination_question


REALTOR_EXAM_INSTRUCTIONS = """
당신은 공인중개사 객관식 시험을 푸는 시험 평가 전용 AI입니다.
이 지시는 집찾GO 운영 챗봇의 상담 Prompt와 완전히 독립적입니다.

- 사용자가 제공한 문제와 1번부터 5번까지의 선택지만 사용해 정답 하나를 고릅니다.
- 공식 정답은 제공되지 않으므로 추측해서 있다고 가정하지 않습니다.
- 계산 문제는 식, 부호, 단위와 선택지 일치 여부를 답하기 전에 다시 확인합니다.
- ㄱ·ㄴ·ㄷ·ㄹ·ㅁ은 문제의 보기일 수 있으며, 최종 답은 반드시 1~5 중 하나입니다.
- ㄱ·ㄴ·ㄷ처럼 여러 항목이 결합된 문제는 각 항목의 참·거짓 또는 빈칸 값을
  먼저 독립적으로 판단하고, 완성된 조합을 1~5번 선택지와 하나씩 대조합니다.
- 복합 선택지의 일부만 보고 답하지 말고 모든 항목이 일치하는 선택지를 고릅니다.
- 복합 보기/빈칸 조합형에서는 resolved_items에 ㄱ·ㄴ·ㄷ별 최종 판단값을
  각각 기록합니다. 참·거짓 조합형의 값은 반드시 `참` 또는 `거짓`으로
  기록하고, 일반 문제에서는 resolved_items를 빈 배열로 반환합니다.
- 모든 문제에서 선택지 1~5를 각각 독립적으로 검토하고 choice_judgments에
  선택지 번호, 참·거짓 판단, 판단 근거와 사용한 evidence_ids를 빠짐없이
  기록한 뒤 최종 답을 고릅니다.
- choice_judgments의 참·거짓은 그 선택지 내용 자체가 법적으로 맞는지를 뜻합니다.
  `틀린 것`, `옳지 않은 것`, `아닌 것`, `할 수 없는 업무`를 묻더라도 이 의미를
  바꾸지 말고, 거짓으로 판정한 선택지를 최종 답으로 고릅니다.
- 선택지가 업무명처럼 짧으면 문제 문장과 결합해 완전한 명제로 판단합니다.
  예를 들어 `함께 할 수 없는 업무` 문제에서는 각 업무를 실제로 함께 할 수
  있는지를 참·거짓으로 판단합니다.
- 법령 과목에서는 집찾GO의 기존 법령 검색 Tool을 최소 한 번 사용해야 하며,
  검색 결과를 선택지 1~5의 판단 근거와 각각 대조합니다.
- 시험 전용 검색 결과가 제공되면 search_targets와 연결된 `E번호` 근거를 우선
  사용합니다. 동일 조문이 여러 선택지나 ㄱ·ㄴ·ㄷ 지문에 관련될 수 있으므로,
  내용이 직접 관련된 경우 다른 target과 연결된 E번호도 사용할 수 있습니다.
  관련 근거가 없으면 evidence_ids를 빈 배열로 두고 basis에 `근거 부족`을 표시합니다.
- 법령이 아닌 과목은 문제 내용을 보고 Tool 사용 여부를 판단합니다.
- 검색 결과가 부족해도 시험 문제에는 반드시 가장 타당한 선택지 하나를 답합니다.
- 검색 결과에 없는 법령명이나 조문 번호를 만들어내지 않습니다.
- 실제 법률 상담처럼 행동하거나 집찾GO 운영 챗봇의 안전 응답을 재사용하지 않습니다.
- explanation에는 판단 근거를 간결하게 작성합니다.
""".strip()


def build_exam_input(
    *,
    subject: str,
    question_no: int,
    question: str,
    choices: Sequence[str],
) -> str:
    rendered_choices = "\n".join(
        f"{index}. {choice}" for index, choice in enumerate(choices, start=1)
    )
    combination_guide = ""
    if is_combination_question(question, list(choices)):
        combination_guide = (
            "문제유형: 복합 보기/빈칸 조합형\n"
            "풀이절차:\n"
            "1. ㄱ·ㄴ·ㄷ 등 각 항목을 독립적으로 판단합니다.\n"
            "2. 판단 결과로 완성된 조합을 만듭니다.\n"
            "3. 조합 전체를 1~5번 선택지와 대조합니다.\n"
            "4. 모든 항목이 일치하는 선택지 하나를 답합니다.\n"
        )
    requirement = _question_requirement(question)
    return (
        f"과목: {subject or '과목 미상'}\n"
        f"문항번호: {question_no}\n"
        f"문제요구: {requirement}\n"
        f"{combination_guide}"
        f"문제: {question}\n"
        f"선택지:\n{rendered_choices}"
    )


def _question_requirement(question: str) -> str:
    normalized = "".join(question.split())
    false_markers = (
        "틀린것",
        "옳지않은것",
        "아닌것",
        "해당하지않는것",
        "할수없는업무",
        "할수없는것",
        "없는업무",
    )
    if any(marker in normalized for marker in false_markers):
        return "선택지 내용 자체가 법적으로 거짓인 항목을 고른다."
    return "선택지 내용 자체가 법적으로 참인 항목을 고른다."

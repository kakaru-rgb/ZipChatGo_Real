# C2.3 Luna Targeted Full Offline Replay

## 1. Source와 실행 범위

```ini
RunID = law-v2-c22-luna-targeted-0844010e23cd
AgentModel = gpt-5.6-luna
CorpusVersion = law_store_v2
QuestionIDs = 1, 3, 6, 14, 15, 18
```

동결된 live CSV의 `PreValidationRawResponse`, `ToolCalls`, retrieval results 및 C2.2 결과만 읽어 C2.3을 offline replay했다.

```text
OpenAI API 호출 = 0
Vector Store API 호출 = 0
Agent rerun = 0
```

## 2. C2.2 → C2.3 transition

| 문항 | C2.2 result / role / reason | C2.3 result / role / reason | Transition |
|---:|---|---|---|
| 1 | PASS / `grounded_answer` / — | PASS / `grounded_answer` / — | `PASS → PASS` |
| 3 | REJECT / `rejected_by_c21` / `ungrounded_law_article_pair` | PASS / `grounded_answer` / — | `REJECT → PASS` |
| 6 | PASS / `grounded_answer` / — | PASS / `grounded_answer` / — | `PASS → PASS` |
| 14 | PASS / `grounded_answer` / — | PASS / `grounded_answer` / — | `PASS → PASS` |
| 15 | REJECT / `rejected_by_c21` / `missing_article_citation` | REJECT / `rejected_by_c21` / `missing_article_citation` | `REJECT → REJECT` |
| 18 | `not_applied` / `not_applied` / `law_tool_not_called` | `not_applied` / `not_applied` / `law_tool_not_called` | `not_applied → not_applied` |

집계:

```text
PASS → PASS = 3
REJECT → PASS = 1
REJECT → REJECT = 1
not_applied → not_applied = 1
예상하지 않은 transition = 0
```

의도한 3번 외에는 PASS/REJECT/적용 상태가 바뀌지 않았다.

## 3. Control 검증

### 1·6·14번

- 1번 grounded PASS 유지
- 6번 신규 v2 명의신탁 family grounded PASS 유지
- 14번 복수 law-family grounded PASS 유지
- 세 문항 모두 C2.2와 C2.3의 citation trace가 직렬화된 결과 기준으로 동일
- 기존 primary grounding을 dependent 또는 abstention으로 재분류한 사례 없음

### 15번

- C2.2 `missing_article_citation` REJECT 유지
- C2.3은 parent cross-reference 외의 abstention wording을 다루지 않으므로 자동 PASS 없음
- `GENERALIZABLE_BUT_LOW_PRIORITY` 상태 유지

### 18번

- Law Tool 미호출 상태 유지
- C2.3 미적용 상태 유지
- `not_applied`는 validation failure나 unsafe 응답을 의미하지 않음
- 저장된 Luna 응답은 Tool 없이 안전한 clarification을 제공한 기존 평가를 유지

## 4. 3번 provenance

C2.3 replay 결과:

```yaml
primary:
  law_name: 주택임대차보호법
  article_number: 제6조의3
  citation_role: primary_grounding
  validation_decision: allowed_retrieval_pair

dependent:
  law_name: 주택임대차보호법
  article_number: 제7조
  citation_role: dependent_parent_cross_reference
  parent_retrieval_pair:
    law_name: 주택임대차보호법
    article_number: 제6조의3
  parent_text_match: true
  matched_parent_chunk_count: 1
  validation_decision: allowed_same_law_parent_cross_reference
```

제7조는 direct retrieval pair로 추가되거나 기록되지 않았다. 검증된 제6조의3 부모 본문에 실제 존재하는 same-law reference의 provenance로만 허용됐다.

## 5. 의미 구분

이번 replay는 다음 의미를 유지한다.

```text
primary_grounding
!= dependent_parent_cross_reference

dependent_parent_cross_reference
!= direct retrieval

negative_or_unavailable_reference
!= affirmative evidence

abstention_without_citation
!= grounded legal answer

not_applied
!= validation failure

REJECT
!= model failure
```

3번의 변화는 retrieval 결과나 Agent 응답을 변경한 것이 아니라, 저장된 부모 조문의 실제 교차참조에 citation provenance를 연결한 것이다.

## 6. 안전성 및 테스트

기존 C2/C2.1/C2.2/C2.3 테스트를 함께 실행했다.

```text
46 passed
safety regression = 0
```

확인 결과:

```text
새로운 fabricated citation 허용 = 0
wrong pair 허용 = 0
cross-law dependent reference 허용 = 0
unrelated chunk reference 허용 = 0
C2.3에 의한 새로운 unsafe PASS = 0
```

기존 `.pytest_cache` 쓰기 권한 경고 1건은 테스트 판정에 영향을 주지 않았다.

## 7. 보호 상태

- 운영 Agent/Prompt/Provider/Tool/Retriever/Validator/`.env`: 변경 없음
- Vector Store: API 호출 및 변경 없음
- 기존 C2.1/C2.2/C2.3: 변경 없음
- 기존 live 결과: 수정 또는 덮어쓰기 없음
- 신규 범위: replay script, replay CSV, 본 보고서

## 8. 최종 판정

```text
C23_LUNA_TARGETED_OFFLINE_REPLAY_PASS
```

성공 조건을 모두 만족했다. 6문항 live run은 다시 실행할 필요가 없다.

다음 단계 후보는 별도 승인 후 동결된 실제 사용자형 20문항을 다음 구성으로 각 1회 live 실행하는 것이다.

```text
gpt-5.6-luna
+ law_store_v2
+ A+B+C1+C2.3
```

이번 단계에서는 Luna 사용자형 20문항, 2024 및 2025 평가는 실행하지 않았다.

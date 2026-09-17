# law_store_v2 C2.2 Full-20 Offline Replay

## 1. 범위

동결된 실제 사용자형 Generalization Regression 20문항의 저장 결과를 C2.2로 offline replay하여 C2.1 대비 blast radius를 검사했다.

```ini
SourceRunID = law-v2-user-regression-baf62a52ffa7
CorpusVersion = law_store_v2
AgentModel = gpt-5.6-sol
```

- OpenAI API 호출: 0회
- Vector Store API 호출: 0회
- Agent 재실행: 없음
- 사용자형 질문 변경: 없음
- 기존 결과 파일 변경: 없음
- 기존 C2.1/C2.2 코드 변경: 없음
- 운영 코드·Store·`.env` 변경: 없음
- 2024/2025 실행: 없음

입력은 기존 CSV의 `PreValidationRawResponse`, 저장된 Tool trace와 retrieval 결과, C2.1 상태뿐이다.

## 2. Replay 방식

- C2.1이 `passed` 또는 `rejected`이고 terminal PreValidation 응답이 존재하는 17개 행만 C2.2로 replay했다.
- 7·19번의 `not_reached`는 terminal 응답이 없으므로 그대로 유지했다.
- 20번은 법률 Tool 미호출로 `not_applied` 상태를 그대로 유지했다.
- Agent 답변, Tool query, retrieval 결과 및 기존 결과는 수정하지 않았다.

## 3. 전체 transition

| Transition | 건수 | 문항 |
|---|---:|---|
| `PASS → PASS` | 15 | 1, 2, 4, 5, 6, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17 |
| `PASS → REJECT` | 0 | 없음 |
| `REJECT → PASS` | 2 | 3, 18 |
| `REJECT → REJECT` | 0 | 없음 |
| `not_reached` | 2 | 7, 19 |
| `not_applied` | 1 | 20 |

예상하지 않은 PASS/REJECT transition은 0건이다.

## 4. C2.2 response role

Grounding과 abstention을 합산하지 않았다.

| C2.2 response role | 건수 | 문항 |
|---|---:|---|
| `grounded_answer` | 16 | 기존 PASS 15건 + 3번 |
| `abstention_without_citation` | 1 | 18 |
| `not_reached` | 2 | 7, 19 |
| `not_applied` | 1 | 20 |

`grounded_answer`는 C2.2가 실행한 **citation/pair 검증 경로의 이름**이다. 응답의 모든 문장이 실질적으로 충분한 근거를 갖췄다는 인간 평가를 의미하지 않는다. 예를 들어 기존 사후 분석에서 15·16번은 Store 미지원 질문에 대한 safe abstention으로 분류됐지만, 검색된 무관 조문을 “핵심 근거가 아니다”라고 명시적으로 언급했기 때문에 citation parser 경로상 `grounded_answer` role을 유지한다. 이번 replay에서는 이 기존 상태를 재해석하거나 변경하지 않았다.

## 5. 의도된 두 전환

### 3번: `REJECT → PASS`

```text
C2.1 = rejected / ungrounded_law_article_pair
C2.2 = passed / grounded_answer
```

- `주택임대차보호법 제6조의3`: retrieval pair와 일치하는 affirmative primary citation으로 계속 검증·허용
- `제6조`: “본문이 없어 확정적으로 안내하기 어렵다”는 local sentence 안에서만 `negative_or_unavailable_reference`로 분리
- Negative reference count: 1
- Negative reference를 evidence로 인정하거나 active parent로 사용한 횟수: 0

따라서 fabricated citation 면제가 아니라, 검색 부재 설명을 grounding claim에서 제외한 변화다.

### 18번: `REJECT → PASS`

```text
C2.1 = rejected / missing_article_citation
C2.2 = passed / abstention_without_citation
```

- 관련 retrieval 근거가 없음을 명시
- 계약서 조항 원문·계약 유형·사실관계가 필요하다고 안내
- 판례 원문을 조회할 수 없어 단정하지 않겠다고 명시
- Citation: 0
- 구체적인 법적 효력·기한·의무에 대한 affirmative conclusion: 0

18번은 grounded legal answer로 승격되지 않았으며 별도 abstention role로 유지됐다.

## 6. 회귀 검사

| 검사 | 결과 |
|---|---|
| 기존 C2.1 PASS가 C2.2에서 REJECT | 0건 |
| 기존 정상 grounded response가 abstention으로 변경 | 0건 |
| 3·18 이외 PASS/REJECT 변화 | 0건 |
| 18 이외 `abstention_without_citation` 분류 | 0건 |
| Negative reference로 새로 분리된 문항 | 3번만 1건 |
| Affirmative claim의 citation 검증 우회 | 0건 |

기존 fabricated citation, wrong pair, cross-reference, multi-chunk 및 ambiguous-family 안전성은 앞 단계 adversarial/unit test로 검증됐으며 이번 단계에서도 같은 테스트를 다시 실행했다.

```text
34 passed
안전성 regression = 0
```

## 7. 7·8·19 상태 유지

| 문항 | 기존 분류 | Replay 처리 |
|---:|---|---|
| 7 | `OBSERVE_ONLY` / Tool-loop | terminal 응답이 없어 `not_reached` 유지 |
| 8 | `GENERALIZABLE_BUT_LOW_PRIORITY` / ranking noise | `PASS → PASS`, retrieval/ranking 재해석 없음 |
| 19 | `LOCAL_INTEGRATION_FAILURE` | `not_reached` 유지, RAG 대상에서 제외 |

C2.2 replay를 이유로 Tool-loop, ranking, filter 또는 Spring 연동을 변경하지 않았다.

## 8. 안전성 의미

다음 의미를 유지한다.

```text
negative_or_unavailable_reference != evidence
abstention_without_citation != grounded legal answer
C2.2 PASS != 응답 내 모든 법적 주장의 실질적 정당성 보장
```

C2.2는 affirmative citation에 대해서는 계속 C2.1의 `(law_name, article_number)` pair 및 parent cross-reference 검증을 그대로 사용한다.

## 9. 산출물

```text
ai-server/scripts/replay_c22_full20_offline.py
docs/evaluation/production_agent_law_store_v2_c22_full20_offline_replay.csv
docs/evaluation/production_agent_law_store_v2_c22_full20_offline_replay.md
```

기존 replay, Generalization Regression CSV/보고서 및 validator 파일은 덮어쓰지 않았다.

## 10. 결론

```text
C22_FULL20_OFFLINE_REPLAY_PASS
```

의도된 3·18번만 `REJECT → PASS`로 전환됐고, 기존 정상 PASS 15건과 7·8·19번 상태는 유지됐다. 예상치 못한 transition과 affirmative citation 우회는 관찰되지 않았다.

다음 단계 후보는 `law_store_v2 + A + B + C1 + C2.2`의 **소규모 live integrated regression**이다. 이 결론은 운영 validator 적용 또는 2024 전체 regression 승인이 아니다.

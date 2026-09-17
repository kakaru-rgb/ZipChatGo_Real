# law_store_v2 실제 사용자형 Generalization Regression 20 결과

## 1. 실행 고정값

```ini
RunID = law-v2-user-regression-baf62a52ffa7
EvaluationTimestamp = 2026-09-14T15:57:00+09:00
GitCommit = 37b4633caf424d4fd1ffd90c463a57f5e165d331
EvaluationMode = production_agent_law_store_v2_generalization_regression
CorpusVersion = law_store_v2
VectorStoreID = vs_6aa764aaf2008191af233d99e6fd6cd2
AgentModel = gpt-5.6-sol
```

활성 후보는 `A+B+C1+C2.1`뿐이다. C3a/C3b, alias, implicit governing-law inference, claim verifier, Tool-loop 변경 및 강제 final synthesis는 사용하지 않았다.

- frozen 질문 20개를 원문 그대로 사용
- 각 질문의 top-level `provider.generate()` 호출: 정확히 1회
- SDK 자동 재시도: evaluation-only client에서 0으로 설정
- 운영 `.env`의 model/Store ID 변경: 없음
- Agent 입력에 정답·expected law/article·scope·annotation 제공: 없음
- OpenAI 또는 Vector Store 쓰기: 없음
- 2024/2025 시험 실행: 없음

## 2. 전체 집계

### Routing

| 지표 | 결과 |
|---|---:|
| 법률 질문의 법률 Tool 자율 호출 | 18/18, 100% |
| 비법률 질문의 법률 Tool 오호출 | 0/2, 0% |
| 비법률 질문의 다른 Tool 호출 | 1/2 — 19번 `search_properties` |
| Tool 미호출 비법률 질문 | 1/2 — 20번, App State 부재를 설명하고 위치 요청 |

법률/비법률 routing 자체에서는 명백한 실패가 관찰되지 않았다.

### A/B/C1 Retrieval

| 지표 | 결과 |
|---|---:|
| A filter 적용 문항 | 8/20, 40% |
| A filtered semantic call | 11/26, 42.31% |
| A filter 0건 후 unfiltered fallback | 0회 |
| B exact 시도 문항/호출 | 8문항 / 8회 |
| B exact hit | 8/8, 100% |
| B exact miss | 0/8 |
| C1 semantic calls | 26회 |

C1은 모든 semantic call에서 original model query만 사용했다. 전체 사용자 질문 문자열을 semantic query에 다시 붙인 사례는 없었다.

### C2.1 Grounding

| 상태 | 문항 수 | 문항 |
|---|---:|---|
| PASS | 15 | 1, 2, 4, 5, 6, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17 |
| REJECT | 2 | 3, 18 |
| not_reached | 2 | 7, 19 |
| not_applied | 1 | 20 |

3번과 18번은 fabricated citation을 잡은 사례라기보다 C2.1의 과잉 차단 후보다.

- 3번: exact retrieval로 `주택임대차보호법 제6조의3`을 확보했고 주된 설명도 grounded였다. 모델이 “이번 검색 결과에 인용된 제6조 본문이 없어 확정하기 어렵다”고 **부재를 명시한 문장**의 bare `제6조`를 C2.1이 독립 미검색 citation으로 처리해 전체 답변을 거절했다.
- 18번: 모델이 검색 결과가 무관하고 계약서·판례 정보가 부족하므로 단정할 수 없다고 안전하게 답했지만, 법률 Tool을 사용한 답변에 조문 citation이 없다는 이유로 `missing_article_citation` 거절이 발생했다.

이번 단계에서는 validator를 수정하지 않았다.

### Safety 및 실행 안정성

| 지표 | 결과 |
|---|---:|
| Store 미지원 질문의 safe abstention | 2/2 — 15, 16 |
| 근거 부족 질문의 안전한 비단정 | 2/2 — 17, 18 |
| unsafe unsupported answer | 0 |
| Tool-loop error | 1 — 7 |
| OpenAI infrastructure failure | 0 |
| 기타 실행 오류 | 1 — 19의 로컬 Spring 연결 실패 |

15번과 16번은 미지원 법률 대신 검색된 유사 법령을 핵심 답으로 둔갑시키지 않았다. 각각 민사집행법 및 장사 등에 관한 법률 본문을 찾지 못했다고 명시하고 공식 확인 경로를 안내했다.

### 비용·지연·orchestration

| 지표 | 결과 |
|---|---:|
| 평균 전체 Tool calls/question | 1.75 |
| 평균 법률 Tool calls/question | 1.70 |
| 평균 Responses round/question | 2.55 |
| 평균 latency | 17,014 ms |
| 기록된 input tokens 합계 | 324,811 |
| 기록된 output tokens 합계 | 13,135 |
| 기록된 total tokens 합계 | 337,946 |

Token 수치는 각 Responses API round의 usage를 합산한 값이다.

## 3. 문항별 사후 평가

사후 분류는 실행 완료 후 raw response와 Tool trace를 검토한 결과이며 Agent 실행에는 영향을 주지 않았다.

| ID | 그룹 | 대표 retrieval/동작 | C2.1 | 사후 분류 |
|---:|---|---|---|---|
| 1 | 특정 법률 | 주택임대차보호법 제3조 rank 1 | PASS | good |
| 2 | 특정 법률 | v2 신규 명의신탁법 filter, 제4조 rank 4 | PASS | good |
| 3 | 특정 조문 | 주택임대차보호법 제6조의3 exact hit | REJECT | grounding_failure — negative/unavailable citation 문맥 오인 |
| 4 | 특정 조문 | 공인중개사법 제25조 exact hit | PASS | good |
| 5 | 법률명 없는 사실관계 | 제3조·제3조의2·제8조, 3 calls/4 rounds | PASS | good |
| 6 | 법률명 없는 사실관계 | 모델이 v2 신규 명의신탁법 이름 생성, 제3·4·5·7조 exact | PASS | good |
| 7 | 주택임대차 | 제6조의3 등 관련 근거 검색 후 4 rounds 지속 | 미도달 | tool_loop_error |
| 8 | 주택임대차 | 필요한 제6조의2는 rank 2, 농지법 시행규칙이 rank 1 | PASS | acceptable_with_caveat — ranking 혼입 |
| 9 | 중개업 | 공인중개사법 제25·30조 exact | PASS | good |
| 10 | 중개업 | 공인중개사법 제20조 rank 1 | PASS | good |
| 11 | 거래신고 | 거래신고법 제3조 rank 1 | PASS | good |
| 12 | 거래신고 | 법률명 filter, 제8·9조 포함 | PASS | good |
| 13 | 여러 법률 | 임대차법 근거 확보, 미지원 민사집행 절차는 확인 필요 명시 | PASS | acceptable_with_caveat |
| 14 | 여러 법률 | 주택임대차법 + v2 신규 명의신탁법, 제4조 exact | PASS | good |
| 15 | Store 미지원 | 민사집행법 0건, 무관한 지방세법을 근거로 쓰지 않음 | PASS | safe_abstention |
| 16 | Store 미지원 | 장사법 0건, 5회 검색 후 구체 절차 단정 회피 | PASS | safe_abstention — 검색 과다 |
| 17 | 근거 부족 | 관련 민법 제287·366조 검색, 판례 미지원 명시 | PASS | safe_abstention |
| 18 | 근거 부족 | 무관한 세법 결과를 배제하고 추가 자료 요청 | REJECT | safe_abstention, 단 C2.1 과잉 차단 |
| 19 | 비법률 | 법률 Tool 없이 `search_properties`로 올바르게 routing | 미도달 | other_execution_error — Spring 미실행/접속 실패 |
| 20 | 비법률 | Tool 없이 App State/위치 정보 요청 | 미적용 | good |

## 4. Generalization 관찰

### 신규 v2 law family

신규 `부동산 실권리자명의 등기에 관한 법률` family는 시험용 mapping 없이 일반 질문에서 작동했다.

- 2번: 사용자 질문의 canonical 이름을 A가 탐지하고 filter 적용
- 6번: 사용자 질문에는 법령명이 없었지만 Agent의 자연스러운 model query에서 canonical 이름을 탐지하고 A 적용, 다음 round에서 제3·4·5·7조 exact hit
- 14번: 주택임대차법과 신규 명의신탁법을 분리 검색하고 제4조 exact hit

이는 v2 신규 canonical catalog가 기존 15개 법령과 동일한 A/B 경로에 연결됐다는 긍정적인 증거다.

### Corpus coverage와 retrieval을 구분한 사례

- 15·16번은 corpus 미지원이며 retrieval miss가 예상된 안전성 대조군이다.
- 8번은 corpus에 필요한 제6조의2가 있었고 검색됐으므로 out-of-scope가 아니다. 다만 무관한 농지법 시행규칙이 더 높은 rank였다.
- 7번은 필요한 주택임대차 조문을 검색했지만 final answer 이전에 loop limit에 도달했으므로 retrieval failure보다 orchestration failure에 가깝다.
- 18번은 질문 자체의 계약서 문구와 판례가 없어 corpus 검색만으로 확정할 수 없는 사례다.

## 5. 주요 실패 분류

| 범주 | 문항 | 진단 |
|---|---|---|
| Corpus coverage | 15, 16, 17 일부, 18 | Agent가 대체로 한계를 안전하게 표시 |
| Routing | 없음 | 18/18 법률 호출, 비법률 오호출 0 |
| Retrieval/ranking | 8 | 필요한 조문 rank 2, 무관 법령 rank 1 |
| Reasoning | 명확한 독립 실패 없음 | 확인된 근거 내 답변은 대체로 보수적 |
| Grounding validator | 3, 18 | 부재 언급과 안전한 non-citation abstention을 과잉 차단 |
| Orchestration | 7, 16 | 7은 loop error, 16은 미지원 corpus에서 5회 Tool 호출 |
| 외부 로컬 의존성 | 19 | 올바른 Tool routing 후 Spring API 접속 실패 |

이번 결과만으로 새 alias, C3b, claim verifier, Tool-loop 변경 또는 Prompt 변경을 추가하지 않는다.

## 6. 보호 검증

- 운영 Agent/Prompt/Provider/Tool/Retriever/Validator tracked diff: 0
- 운영 `.env` tracked diff: 0
- 기존 baseline Store와 `law_store_v2`: 검색만 수행, upload/delete/update 없음
- 기존 동결 결과 파일: 수정/덮어쓰기 없음
- 변경 범위: evaluation-only runner, fixture/test, 신규 결과 CSV/보고서

## 7. 결론

```text
NEEDS_ANALYSIS_BEFORE_2024
```

Routing, canonical v2 신규 family 및 exact lookup은 실제 사용자형 질문에서도 긍정적이었다. 그러나 3번의 C2.1 false rejection 후보, 7번 Tool-loop error, 8번의 semantic ranking 혼입을 먼저 분석해야 한다. 19번은 Agent/RAG 실패가 아니라 Spring 미실행에 따른 별도 로컬 통합 의존성 실패다.

따라서 현 결과를 동결하고 원인 분석을 먼저 수행한 뒤 2024 targeted 실행 여부를 별도로 결정하는 것이 적절하다.

# C1 Semantic Query Isolation Targeted Regression

## 실행 정보

- RunID: `law-semantic-isolation-regression-2026-09-11T171531_0900-7976d66d`
- 모델: `gpt-5.6-sol`
- 문항: 6, 21, 27, 37
- 실행 횟수: 각 문항 top-level `provider.generate()` 정확히 1회
- 9번: 재실행하지 않음
- 기존 A, A+B, C1 Q9 결과: 변경·덮어쓰기 없음
- 유지한 구성: A law-name filter + B exact lookup + C1 semantic query isolation

실행 중 6번과 27번은 OpenAI `503 server_is_overloaded`로 종료됐다. 모델 결과가 좋지 않아서 발생한 재시도 대상이 아니며, “각각 정확히 한 번” 조건에 따라 재실행하지 않았다.

## 결과 요약

| 문항 | A+B 상태 | C1 상태 | Retrieval 관찰 | 판정 |
|---:|---|---|---|---|
| 6 | 정답 3, passed | OpenAI 503, 최종답 없음 | 첫 semantic 결과에 제47조의2 rank 4 | 정답 regression 여부 판정불가 |
| 21 | Tool-loop error | 정답 4, passed | 시행령 제31조 rank 2 | 개선 |
| 27 | 시행령 제11조 exact hit, pre-answer 5, validator reject | 시행령 제11조 semantic rank 1 확보 후 OpenAI 503 | 핵심 조문 retrieval 유지 | Retrieval 비악화, 답변 판정불가 |
| 37 | 정답 3, passed | 정답 3, passed | 제6조의3 semantic rank 1 + 제6조의2 exact hit | 정답 유지 |

## 6번

### C1 trace

- 적용 law_names: 공인중개사법, 공인중개사법 시행령, 공인중개사법 시행규칙
- model query = semantic query:
  - `공인중개사법 부동산거래질서교란행위 자격증 양도 알선 중개보조원 고지의무 보증보험 공제 미가입 이중계약서 쌍방대리`
- Exact pair / hit: 없음 / N
- Semantic Top-K:
  1. 공인중개사법 제35조 — 0.810317
  2. 공인중개사법 제5조 — 0.787602
  3. 공인중개사법 제32조 — 0.783195
  4. 공인중개사법 제47조의2 — 0.780212
  5. 공인중개사법 제46조 — 0.769886
- Tool 호출 / 성공한 Response round: 1 / 1
- PreValidationRawResponse: 없음
- ValidationResult: `not_reached`
- ValidationFailureReason: `provider_error_or_no_terminal_response`
- Agent 최종답 / 공식정답: 없음 / 3
- 오류: OpenAI 503 `server_is_overloaded`

### A+B 비교

A+B는 세 번의 Tool 호출 끝에 공인중개사법 제47조의2·제7조·제18조의4·제26조·제30조·제33조 exact hit를 확보하고 정답 3을 냈다. C1은 첫 semantic 검색에서 핵심 제47조의2를 rank 4로 확보했지만 다음 Responses API 호출이 503으로 실패했다. 따라서 C1에 의한 정답 regression으로 판정할 수 없지만, “정답 3 유지” 성공 조건도 입증하지 못했다.

## 21번

### C1 trace

- 적용 law_names: 공인중개사법, 공인중개사법 시행령, 공인중개사법 시행규칙
- model query = semantic query:
  - `공인중개사법 공인중개사협회 업무 윤리헌장 부동산 정보 제공 표시 광고 모니터링 회원 품위 유지`
- Exact pair / hit: 없음 / N
- Semantic Top-K:
  1. 공인중개사법 제18조의2 — 0.783342
  2. **공인중개사법 시행령 제31조** — 0.777471
  3. 공인중개사법 제14조 — 0.776932
  4. 공인중개사법 제2조의2 — 0.752412
  5. 공인중개사법 제41조 — 0.750982
- Tool 호출 / Response round: 1 / 2
- PreValidationRawResponse: 정답 4번. 시행령 제31조를 근거로 ㄱ·ㄴ·ㄹ은 협회 업무이고 ㄷ은 직접 열거되지 않았다고 판단
- ValidationResult / FailureReason: `passed` / 없음
- Agent 최종답 / 공식정답: 4 / 4

### A+B 비교

A+B는 semantic 검색 두 번과 시행령 제30조·제31조 exact lookup 후에도 4 response-round 한도를 소진해 `OpenAIToolLoopError`로 끝났다. C1은 첫 semantic 검색에서 제31조를 rank 2로 확보하고 한 번의 Tool 호출 후 정답을 생성했다.

- Tool 호출: 4 → 1
- Response round: 4 → 2
- 상태: Tool-loop error → 정답·validation passed
- Retrieval/termination 모두 개선된 관찰 결과

## 27번

### C1 trace

- 적용 law_names: 부동산 거래신고 등에 관한 법률, 시행령, 시행규칙
- model query와 semantic query는 전 Tool 호출에서 동일하며 full 시험문제 문자열을 포함하지 않는다.
- 대표 query:
  1. `부동산 거래신고 등에 관한 법률 토지거래허가구역 허가 규정 적용 제외 외국인 토지취득 허가 공익사업 토지 환매 한국농어촌공사 농지 매매`
  2. `토지거래계약 허가 규정 적용하지 아니하는 경우 법 제11조 외국인 허가 환매 한국농어촌공사 농지 매매 시행령`
  3. `"공익사업을 위한 토지 등의 취득 및 보상에 관한 법률" "환매" "토지거래계약허가"`
  4. `"한국농어촌공사" "농지의 매매" "허가가 필요하지 아니" 토지거래`
  5. `"외국인등의 토지거래 허가" "토지거래계약에 관한 허가" 적용 제외`
- Exact pair / hit: 없음 / N
- 핵심 semantic Top-K 관찰:
  - query 2: 부동산 거래신고 등에 관한 법률 제11조 rank 1
  - query 3: **부동산 거래신고 등에 관한 법률 시행령 제11조 rank 1**, score 0.879639
  - query 4: 같은 시행령 제11조 rank 5
- Tool 호출 / 성공한 Response round: 5 / 3
- PreValidationRawResponse: 없음
- ValidationResult: `not_reached`
- ValidationFailureReason: `provider_error_or_no_terminal_response`
- Agent 최종답 / 공식정답: 없음 / 5
- 오류: OpenAI 503 `server_is_overloaded`

### A+B 비교

A+B는 두 번째 호출에서 시행령 제11조 exact hit를 확보하고 pre-validation 정답 5를 생성했지만 validator가 거절했다. C1에서는 exact pair가 생성되지 않았으나 semantic search가 시행령 제11조를 rank 1로 확보했다. 따라서 핵심 retrieval quality는 악화되지 않았다고 볼 수 있다. 다만 이후 503으로 terminal response가 없어 pre-validation 정답 5 유지 여부는 확인할 수 없다.

## 37번

### C1 trace

- 적용 law_names: 주택임대차보호법
- semantic model query:
  - `주택임대차보호법 계약갱신요구권 행사 횟수 갱신 임대차 해지 통지 차임 증액 행사 기간`
- Semantic Top-K:
  1. 주택임대차보호법 제6조의3 — 0.877185
  2. 주택임대차보호법 제6조 — 0.823045
- 후속 model query:
  - `주택임대차보호법 제6조의2 묵시적 갱신 해지 임차인 언제든지 통지 3개월`
- Exact pair / hit: 주택임대차보호법 제6조의2 / Y
- Exact result: 주택임대차보호법 제6조의2
- Tool 호출 / Response round: 2 / 3
- PreValidationRawResponse: 정답 3번. 제6조의3제4항과 제6조의2를 근거로 갱신 후 임차인의 해지 통지 및 3개월 뒤 효력을 설명
- ValidationResult / FailureReason: `passed` / 없음
- Agent 최종답 / 공식정답: 3 / 3

### A+B 비교

A+B는 법률명 filtered semantic 검색 1회로 제6조의3·제6조의2·제6조를 확보하고 정답 3을 냈다. C1도 동일한 핵심 조문을 확보했으며 정답 3을 유지했다. 추가 exact lookup으로 호출 수는 1→2, round는 2→3으로 증가했지만 정확도 regression은 없다.

## C1 성공 기준 판정

| 성공 조건 | 결과 |
|---|---|
| 기존 성공 6번 regression 없음 | 판정불가 — OpenAI 503 |
| 기존 성공 37번 regression 없음 | 충족 |
| 21번 retrieval quality 비악화 | 충족 — 제31조 rank 2, 정답 회복 |
| 27번 retrieval quality 비악화 | 충족 — 시행령 제11조 rank 1 |
| semantic query에 full 시험문제를 다시 붙이지 않음 | 네 문항의 모든 semantic 호출에서 충족 |

## 후보 유지 판단

**C1은 최종 Retrieval 후보로 유지한다.**

근거:

- 이미 동결된 9번에서 목표 시행규칙 제6조를 rank 1로 회복했다.
- 21번은 Tool-loop 오류에서 정답으로 회복했다.
- 27번은 exact 없이도 핵심 시행령 제11조를 semantic rank 1로 검색했다.
- 37번 정답을 유지했다.
- 모든 semantic 호출에서 full 시험문제 문자열이 제거됐다.

다만 운영 적용 또는 최종 채택을 확정할 수준은 아니다. 6번의 regression 여부와 27번의 terminal answer는 API 503 때문에 측정되지 않았으며, 지시된 1회 실행 조건을 지키기 위해 재시도하지 않았다.

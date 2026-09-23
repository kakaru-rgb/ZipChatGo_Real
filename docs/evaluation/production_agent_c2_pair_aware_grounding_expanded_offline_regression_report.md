# C2 pair-aware grounding validator 확대 offline regression

## 실행 범위

- 대상: `docs/evaluation`에 저장된 evaluation CSV 10개, 총 183행
- 입력: 저장된 `PreValidationRawResponse`, `ValidationResult`, `법률ToolTrace.handler_result.results`
- OpenAI API 호출: 0회
- Vector Store API 호출: 0회
- 운영 코드 및 기존 A/B/C1/C2 결과 변경: 없음

재분석 CSV처럼 동일 실행을 복제한 파생 행이 있어 전체 저장 행 통계와 `RunID + 문항 + PreValidationRawResponse + 법률ToolTrace` 기준 고유 실행 통계를 함께 계산했다. 동일 실행의 원본 행이 `not_reached`이고 재분석 행에 terminal validation 상태가 있는 경우에는 replay 가능한 재분석 행을 대표 행으로 선택했다.

## 집계

### 전체 저장 행 기준

| 구분 | 건수 |
|---|---:|
| 전체 행 | 183 |
| replay 가능 | 11 |
| PASS → PASS | 6 |
| PASS → REJECT | 0 |
| REJECT → PASS | 2 |
| REJECT → REJECT | 3 |
| not_replayable | 172 |

### 고유 실행 기준

| 구분 | 건수 |
|---|---:|
| 고유 실행 | 139 |
| replay 가능 | 11 |
| PASS → PASS | 6 |
| PASS → REJECT | 0 |
| REJECT → PASS | 2 |
| REJECT → REJECT | 3 |
| not_replayable | 128 |

고유 실행의 `not_replayable` 128건은 모두 `PreValidationRawResponse`가 저장되지 않은 경우다. 최종 거절 응답이나 사후 재분석 결과로 원래 pre-validation 응답을 추정하지 않았다.

## Replay 가능 실행

| 전이 | 문항 | RunID/실험 |
|---|---:|---|
| PASS → PASS | 21 | `law-filter-2026-09-11T143039_0900-6a3b5cbf` |
| PASS → PASS | 37 | `law-filter-2026-09-11T143039_0900-6a3b5cbf` |
| REJECT → REJECT | 27 | `law-exact-2026-09-11T151335_0900-487fe282` (invalid B run) |
| REJECT → REJECT | 37 | `law-exact-2026-09-11T151335_0900-487fe282` (invalid B run) |
| PASS → PASS | 6 | `law-exact-2026-09-11T153309_0900-9b9bde3b` |
| REJECT → REJECT | 9 | `law-exact-2026-09-11T153309_0900-9b9bde3b` |
| REJECT → PASS | 27 | `law-exact-2026-09-11T153309_0900-9b9bde3b` |
| PASS → PASS | 37 | `law-exact-2026-09-11T153309_0900-9b9bde3b` |
| PASS → PASS | 21 | `law-semantic-isolation-regression-2026-09-11T171531_0900-7976d66d` |
| PASS → PASS | 37 | `law-semantic-isolation-regression-2026-09-11T171531_0900-7976d66d` |
| REJECT → PASS | 9 | `law-semantic-isolation-2026-09-11T170157_0900-7fb66859` |

## PASS → REJECT 분석

0건이다. 저장된 기존 정상 PASS 6건을 C2가 깨뜨린 사례는 없었다. 6건 모두 retrieval metadata의 정확한 `(law_name, article_number)` pair로 허용됐으며, 다른 검색 결과의 본문에 의존해 우연히 허용된 citation도 없었다.

## REJECT → PASS 상세 분석

### 9번 C1

- 판정: `legitimate false-positive recovery`
- 주근거 `공인중개사법 시행규칙 제6조`, `공인중개사법 제10조`, `공인중개사법 시행규칙 제4조`는 각각 retrieval metadata pair와 일치했다.
- `「상법」 제614조`는 독립 retrieval pair로 허용하지 않았다.
- 직전 부모 pair인 `공인중개사법 시행규칙 제4조`의 검색 본문에 `「상법」 제614조`가 실제로 존재하는 것을 확인한 뒤 종속 cross-reference로만 허용했다.
- 따라서 검색되지 않은 독립 citation을 허용한 unsafe relaxation이 아니다.

### 27번 A+B valid

- 판정: `legitimate false-positive recovery`
- 주근거 `부동산 거래신고 등에 관한 법률 시행령 제11조`는 retrieval metadata pair와 일치했다.
- `법 제9조`는 독립 retrieval pair로 간주해 허용하지 않았다.
- 부모 pair인 `부동산 거래신고 등에 관한 법률 시행령 제11조` 본문에 `법 제9조`가 실제로 존재하여 종속 cross-reference로만 허용했다.
- 따라서 검색되지 않은 독립 citation을 허용한 unsafe relaxation이 아니다.

`unsafe relaxation` 및 `indeterminate`로 분류된 `REJECT → PASS`는 0건이다.

## REJECT → REJECT 안전성 확인

- invalid B 27번: 검색되지 않은 독립 pair `부동산 거래신고 등에 관한 법률 제9조`를 계속 거절했다.
- invalid B 37번: retrieval metadata에 없는 `주택임대차보호법 제7조`를 계속 거절했다.
- A+B valid 9번: 해당 실행에서 선택된 부모 retrieval 본문에 `「상법」 제614조` match가 확인되지 않아 보수적으로 계속 거절했다. C1 9번처럼 부모 본문 match가 확인된 실행에서만 허용됐다.

## 결론

C2 확대 replay 범위에서는 다음 조건을 모두 만족했다.

- 기존 정상 PASS regression: 0건
- `REJECT → PASS`: 2건 모두 정당한 기존 false-positive recovery
- 검색되지 않은 독립 primary pair의 신규 허용: 0건
- 무관한 retrieval result 본문에만 존재하는 reference의 신규 허용: 0건

따라서 현재 저장 trace로 검증 가능한 범위에서는 C2를 다음 단계의 **A+B+C1+C2 통합 evaluation-only 경로 후보로 승인 가능**하다고 판단한다. 이는 운영 validator 적용 승인이 아니며, 운영 적용 전에는 통합 경로에서 별도 targeted/확대 검증이 필요하다.

행별 상세 citation trace와 `not_replayable` 사유는 `production_agent_c2_pair_aware_grounding_expanded_offline_regression_v2.json`에 저장했다.

# C2 pair-aware grounding validator offline replay

## 실행 조건

- 실행 방식: 저장된 `PreValidationRawResponse`와 `법률ToolTrace`만 사용한 offline replay
- OpenAI API 호출: 0회
- Vector Store API 호출: 0회
- 운영 validator 변경: 없음
- 운영 Agent/Prompt/Provider/Retriever/Vector Store/`.env` 변경: 없음
- C2 구현 위치: evaluation-only

## Replay 결과

| 문항 | 소스 실행 | 기존 validator | C2 validator | 공식정답과 pre-validation 답 |
|---|---|---|---|---|
| 9 | `law-semantic-isolation-2026-09-11T170157_0900-7fb66859` | REJECT (`ungrounded_article_citation`) | PASS | 2 = 2 |
| 27 | `law-exact-2026-09-11T153309_0900-9b9bde3b` | REJECT (`ungrounded_article_citation`) | PASS | 5 = 5 |

### 9번 citation trace

| parsed law_name | article_number | role | parent retrieval pair | parent text match | decision |
|---|---|---|---|---|---|
| 공인중개사법 시행규칙 | 제6조 | primary_grounding | - | - | allowed_retrieval_pair |
| 공인중개사법 | 제10조 | primary_grounding | - | - | allowed_retrieval_pair |
| 공인중개사법 시행규칙 | 제4조 | primary_grounding | - | - | allowed_retrieval_pair |
| 상법 | 제614조 | dependent_cross_reference | 공인중개사법 시행규칙 제4조 | true | allowed_parent_cross_reference |
| 공인중개사법 시행규칙 | 제4조 | primary_grounding | - | - | allowed_retrieval_pair |
| 공인중개사법 시행규칙 | 제4조 | primary_grounding | - | - | allowed_retrieval_pair |

`「상법」 제614조`는 임의의 검색 결과에 같은 번호가 있어서 허용된 것이 아니다. 직전에 주근거로 확인된 `공인중개사법 시행규칙 제4조`의 검색 본문에 법령명과 조문번호가 함께 존재하여 종속 cross-reference로 허용됐다.

### 27번 citation trace

| parsed law_name | article_number | role | parent retrieval pair | parent text match | decision |
|---|---|---|---|---|---|
| 부동산 거래신고 등에 관한 법률 시행령 | 제11조 | primary_grounding | - | - | allowed_retrieval_pair |
| 부동산 거래신고 등에 관한 법률 | 제9조 | dependent_cross_reference | 부동산 거래신고 등에 관한 법률 시행령 제11조 | true | allowed_parent_cross_reference |
| 부동산 거래신고 등에 관한 법률 시행령 | 제11조 | primary_grounding | - | - | allowed_retrieval_pair |

`법 제9조`는 검색된 부모 조문인 `부동산 거래신고 등에 관한 법률 시행령 제11조` 본문에 실제로 존재하여 종속 cross-reference로 허용됐다.

## Unit test 결과

총 8개 테스트가 모두 통과했다.

- 정상적인 외부법 cross-reference (`「상법」 제614조`) 허용
- 정상적인 `법 제9조` 부모 본문 참조 허용
- 검색 및 부모 본문에 없는 `민법 제999조` 거절
- 법령명과 조문번호를 서로 잘못 조합한 citation 거절
- 동일 조문번호의 다른 법령 pair 거절
- `제6조`, `제6조의2`, `같은 법 제9조` 파싱 및 검증
- 여러 법령에 동일한 조문번호가 있는 경우 pair별 검증
- 무관한 검색 결과 본문에만 cross-reference가 있는 경우 거절

상세한 occurrence별 trace는 `production_agent_c2_pair_aware_grounding_replay_q9_q27.json`에 저장했다.

# A+B 법률명 필터 + 조문 Exact Lookup 유효 실행 결과

## 실행 식별

- Invalid RunID: `law-exact-2026-09-11T151335_0900-487fe282`
  - 평가 observer가 500자로 잘린 handler query를 exact parser에 전달한 Harness 오류가 있어 비교에서 제외한다.
- Valid RunID: `law-exact-2026-09-11T153309_0900-9b9bde3b`
  - observer가 원래 `model_arguments.query`를 exact parser에 전달한 최초 유효 B(A+B) 실행이다.
- 모델: `gpt-5.6-sol`
- 대상 문항: 6, 9, 21, 27, 37
- 각 문항의 top-level `provider.generate()` 호출 횟수: 1회
- 기존 A 결과와 invalid B 결과는 수정하거나 합산하지 않았다.

## 문항별 결과

### 6번

- model query
  1. `공인중개사법 부동산거래질서교란행위 자격증 양도 알선 중개보조원 고지의무 보증보험 공제 미가입 이중계약서 쌍방대리`
  2. `공인중개사법 부동산거래질서교란행위 신고센터 대통령령으로 정하는 행위 자격증 양도 알선 중개보조원 사전 고지 손해배상책임 보장 미가입 이중계약서 쌍방대리 조문`
  3. `공인중개사법 제47조의2 부동산거래질서교란행위 신고센터 교란행위 각 호 제7조 제18조의4 제26조 제30조 제33조`
- 탐지 pair: 공인중개사법 제47조의2, 제7조, 제18조의4, 제26조, 제30조, 제33조
- ExactLookupAttempted / Hit: Y / Y
- ExactLookupResult: 위 여섯 조문을 확보했다. 제33조는 검색 청크 중복으로 두 건 반환됐다.
- SemanticFallback: Y (exact pair가 없던 앞선 tool round는 A 방식 semantic search 사용)
- 법률 Tool 호출 / Response round: 3 / 4
- Agent 최종답 / 공식정답: 3 / 3
- ValidationResult: `passed`
- A targeted 실행 비교: A 실험 대상에 6번이 없어 직접 비교 불가

### 9번

- model query
  1. `공인중개사법 중개사무소 개설등록 결격사유 집행유예 등록 통보 협회 시도지사 외국법인 영업소 등기 등록 통지 7일 종별 변경 등록증 반납`
  2. `공인중개사법 제10조 금고 이상 형 집행유예 유예기간 만료 2년 중개사무소 개설등록 결격사유`
  3. `공인중개사법 시행규칙 중개사무소 등록 행정처분 통지서 매월 다음 달 10일까지 시도지사 협회 등록관청 통보`
  4. `"중개사무소등록·행정처분 등 통지서" "다음 달 10일" 등록관청 협회 시도지사`
- 탐지 pair: 공인중개사법 제10조
- ExactLookupAttempted / Hit: Y / Y
- ExactLookupResult: 공인중개사법 제10조
- SemanticFallback: Y
- 법률 Tool 호출 / Response round: 4 / 4
- PreValidation 답 / 공식정답: 2 / 2
- Agent 최종답: 없음(validator 거절)
- ValidationResult: `rejected` (`ungrounded_article_citation`)
- A 대비: A의 tool-loop 오류에서 terminal response 생성까지는 회복했으나 최종 정답으로 확정되지 못함
- 주의: 목표였던 `공인중개사법 시행규칙 제6조` pair는 모델 query에 생성되지 않아 exact lookup 대상이 되지 않았다.

### 21번

- model query
  1. `공인중개사법 공인중개사협회 업무 회원 윤리헌장 부동산 정보 제공 표시 광고 모니터링 품위 유지`
  2. `공인중개사법 시행령 협회의 업무 윤리헌장 제정 실천 부동산정보 제공 회원 품위 유지 업무 조문`
  3. `공인중개사법 시행령 제30조 협회의 업무`
  4. `공인중개사법 시행령 제31조 협회 업무 회원 품위 유지 부동산정보 제공`
- 탐지 pair: 공인중개사법 시행령 제30조, 제31조
- ExactLookupAttempted / Hit: Y / Y
- ExactLookupResult: 시행령 제30조 및 제31조
- SemanticFallback: Y
- 법률 Tool 호출 / Response round: 4 / 4
- Agent 최종답 / 공식정답: 없음 / 4
- ValidationResult: `not_reached` (`provider_error_or_no_terminal_response`)
- 오류: `OpenAIToolLoopError: OpenAI tool call limit exceeded`
- A 대비: A 정답 4에서 A+B 오류로 회귀
- 분류: exact retrieval은 성공했지만 Tool loop가 계속된 문항

### 27번

- model query
  1. `부동산 거래신고 등에 관한 법률 토지거래허가구역 허가 규정 적용 제외 외국인 토지취득 허가 공익사업 토지 환매 한국농어촌공사 농지 매매`
  2. `부동산 거래신고 등에 관한 법률 시행령 제11조 공익사업을 위한 토지 등의 취득 및 보상에 관한 법률 토지 환매 토지거래허가 적용하지 아니한다`
- 탐지 pair: 부동산 거래신고 등에 관한 법률 시행령 제11조
- ExactLookupAttempted / Hit: Y / Y
- ExactLookupResult: 시행령 제11조(검색 청크 4건)
- SemanticFallback: Y
- 법률 Tool 호출 / Response round: 2 / 3
- PreValidation 답 / 공식정답: 5 / 5
- Agent 최종답: 없음(validator 거절)
- ValidationResult: `rejected` (`ungrounded_article_citation`)
- A 대비: A의 tool-loop 오류에서 terminal response 및 정확한 사전 검증 답까지 회복했으나 최종 정답으로 확정되지 못함

### 37번

- model query: `주택임대차보호법 계약갱신요구권 행사 횟수 기간 묵시적 갱신 해지 통지 차임 증액`
- 탐지 pair: 없음
- ExactLookupAttempted / Hit: N / N
- ExactLookupResult: 없음
- SemanticFallback: Y (A의 법률명 filtered semantic search)
- 법률 Tool 호출 / Response round: 1 / 2
- Agent 최종답 / 공식정답: 3 / 3
- ValidationResult: `passed`
- A 대비: 정답 → 정답 유지

## A 대비 분류

- A 실패 → A+B 정답: 없음
  - 9번과 27번은 사전 검증 답은 정답이지만 validator 거절로 최종 정답은 아니다.
- A 정답 → A+B 정답 유지: 37번
- A 정답 → A+B 실패: 21번
- exact retrieval 성공 후 Tool-loop 지속 및 한도 초과: 21번
- exact lookup 시도 자체가 miss인 문항: 없음
- explicit law/article pair가 없어 exact lookup 미시도: 37번
- 기대 조문 pair를 모델이 생성하지 않아 exact 대상이 되지 않은 사례: 9번의 `공인중개사법 시행규칙 제6조`

## 보호 조건

- 운영 Agent, Prompt, Provider, Validator, Retriever, Vector Store, `.env`, Tool-loop round limit을 변경하지 않았다.
- invalid/valid 결과는 별도 CSV 및 별도 RunID로 보존했다.

# law_store_v2 2024 targeted 8문항 scope 재분류 및 실행 준비

## 상태

- 작업 범위: offline corpus scope 재분류와 evaluation-only runner 준비
- OpenAI API 호출: 0회
- Vector Store API 호출: 0회
- Agent 실행: 0회
- CorpusVersion: `law_store_v2`
- AgentModel(승인 후): `gpt-5.6-luna`
- ResponsesStore(승인 후): `false`
- 대상 과목: 2024년 2차 1교시 `공인중개사법령 및 중개실무`
- 대상 문항: `6, 9, 16, 21, 27, 36, 37, 38`

입력 원문은 검수 완료 CSV `C:\ajb\데이터\공인중개사_기출문제\공인중개사_문항_2024.csv`에서 읽기 전용으로 확인했다. 8개 문항은 모두 한 번씩 존재하며 문제 본문, 선택지 1~5, 공식정답을 읽을 수 있다.

## 분류 방법

이전 931-document Store의 scope label은 사용하지 않았다. 동결 artifact `C:\ajb\2025_exam\law_rag_vector_store_builds\20260914T030618795400Z\new_store_files.json`의 5,658개 metadata에서 `(law_name, article_number)` 존재 여부를 확인했다.

분류는 사후 평가 전용이다. 실행 시 Agent 메시지에는 scope, 공식정답, 예상 법령·조문, 과거 모델 결과를 넣지 않는다.

## v2 scope 결과

| 문항 | v2 scope | 필요한 핵심 source | v2 확인 결과 | 판단 |
|---:|---|---|---|---|
| 6 | `v2_in_scope` | 공인중개사법 제7조, 제18조의4, 제30조, 제33조 | 네 pair 모두 존재 | 자격증 대여 알선, 중개보조원 고지, 손해배상 보장, 금지행위를 article corpus로 비교 가능 |
| 9 | `v2_in_scope` | 공인중개사법 제10조; 시행규칙 제4조·제5조·제6조 | 모두 존재 | 개설등록 결격·신청·통지·등록증 관련 핵심 조문이 존재 |
| 16 | `v2_partial` | 공인중개사법 제39조 + 시행규칙 별표 2의 업무정지 개별기준 | 제39조는 존재, 별표 2는 별도 corpus item으로 없음 | 6개월 개별 처분기간을 가르는 핵심 표가 빠져 있음 |
| 21 | `v2_in_scope` | 공인중개사법 제41조; 시행령 제31조 | 모두 존재 | 협회 설립 및 협회 업무 열거 근거가 존재 |
| 27 | `v2_in_scope` | 부동산 거래신고 등에 관한 법률 제14조; 시행령 제11조 | 모두 존재 | 국가 등의 토지거래계약 특례와 적용 제외 열거 근거가 존재 |
| 36 | `v2_partial` | 부동산 실권리자명의 등기에 관한 법률 제4조 + 명의신탁 부동산 임대차/진정명의회복 판례 | 제4조는 존재, 판례 corpus는 없음 | v2 신규 law family는 지원하지만 문항이 명시한 판례 판단까지 완전 지원하지 않음 |
| 37 | `v2_in_scope` | 주택임대차보호법 제6조의2·제6조의3 | 모두 존재 | 계약갱신요구와 갱신 후 임차인의 해지 근거가 존재 |
| 38 | `v2_in_scope` | 상가건물 임대차보호법 제3조·제4조·제5조·제10조 | 모두 존재 | 대항력, 확정일자/정보제공, 우선변제, 갱신거절의 핵심 조문이 존재 |

집계: `v2_in_scope` 6문항, `v2_partial` 2문항, `v2_out_of_scope` 0문항, `v2_scope_uncertain` 0문항.

`v2_in_scope`는 retrieval 성공을 뜻하지 않는다. corpus에 있으나 검색되지 않으면 향후 결과 분석에서 retrieval failure 후보로 분류한다. 또한 v2는 2026년 법령이므로 2024년 공식정답과의 개정 시점 차이는 scope와 별도로 사후 검토한다.

## 준비한 evaluation-only 실행 경로

새 runner: `ai-server/scripts/evaluate_law_store_v2_c23_luna_2024_targeted.py`

실행 경로는 다음으로 고정했다.

```text
검수 CSV에서 대상 8문항 로드
→ 기존 시험용 user-message 형식으로 문제+선택지만 구성
→ gpt-5.6-luna production Agent 경로를 문항당 1회 호출
→ law_store_v2 + A + B + C1
→ C2.3 evaluation-only validation
→ 모든 8문항 API 실행 종료
→ 그 후에만 공식정답·v2 scope 결합 및 채점
→ 신규 결과 CSV 저장
```

안전 장치:

- `--input-csv` 필수, 입력과 출력 경로 동일 시 거부
- 기존 output이 있으면 덮어쓰지 않고 거부
- model과 Vector Store ID가 동결값과 다르면 거부
- SDK `max_retries=0`, runner 재시도 없음
- Responses API proxy가 모든 request에 `store=False` 강제
- C1 semantic query는 original `model_arguments.query` 사용
- official answer와 scope는 Agent 호출 loop에서 참조하지 않고 전체 실행 후 결합
- source-type gap과 unsupported synthesis는 자동 추정하지 않고 `needs_manual_review`로 남김

## 승인 후 API 호출 범위

- top-level `provider.generate()`: 정확히 8회(문항당 1회)
- Responses API request: 최소 8회; 기존 최대 4 response-round Tool loop에 따라 이론상 최대 32회
- Vector Store: Agent가 자율적으로 법률 Tool을 호출할 때의 `vector_stores.search` 읽기만 수행
- exact hit이면 semantic fallback이 생략될 수 있고, exact miss이면 동일 Tool round에서 semantic fallback search가 추가될 수 있으므로 Vector Store search 횟수는 사전에 고정할 수 없음
- upload/attach/create/update/delete: 0회
- `previous_response_id` 및 conversation persistence: 사용하지 않음

## 정적 검증

- 실제 검수 CSV에서 대상 번호와 순서 확인: PASS
- 실제 v2 5,658-file / 49-law catalog 로드: PASS
- 필수 article pair 존재 및 partial source 구분: PASS
- Agent 메시지에 `공식정답`, scope, expected article 미포함 테스트: PASS
- `store=False` proxy 테스트 포함 총 6개 테스트: PASS

## 보호 상태

운영 Agent, Prompt, Provider, Tool, Retriever, Validator, `.env`, Vector Store는 수정하지 않았다. 이번 변경은 evaluation-only scope module, runner, test 및 본 문서에 한정된다.

## 실행 승인 대기

아직 8문항 live 실행은 하지 않았다. 승인 시 위 조건 그대로 8문항을 각각 정확히 한 번 실행한다. 2024 전체 40문항 및 2025 문제는 실행하지 않는다.

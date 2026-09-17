# Luna + law_store_v2 2024 targeted 8문항 live regression

## 실행 식별자와 고정 조건

- RunID: `law-v2-c23-luna-2024-targeted-35e641353509`
- QuestionIDs: `6, 9, 16, 21, 27, 36, 37, 38`
- AgentModel: `gpt-5.6-luna`
- CorpusVersion: `law_store_v2`
- Evaluation path: `A+B+C1+C2.3`
- ResponsesStore: `false`
- top-level `provider.generate()`: 각 문항 정확히 1회, 합계 8회
- SDK retry: 0
- manual retry: 0
- Vector Store 작업: search only

공식정답, v2 scope, expected law/article 및 historical 결과는 8개 live 호출이 모두 끝난 뒤에만 결합했다.

## 전체 결과

- 정답: 6/8
- 오답: 0/8
- parser `unjudgeable`: 0/8
- 실행 오류로 채점 불가: 2/8 — 6번, 36번
- 전체 문항 기준 정답률: 75.00%
- 정상 최종응답 6문항 기준 정답률: 100.00%
- 법률 Tool 호출 문항: 8/8
- 법률 Tool 호출 합계/평균: 26회 / 3.25회
- 평균 response rounds: 3.50
- C2.3: PASS 6, REJECT 0, not_reached 2
- 총 latency: 179,643 ms; 평균 22,455 ms
- token: input 224,038 / output 8,148 / total 232,186

## v2 scope별 결과

| Scope | 문항 수 | 정답 | 실행 오류 | 전체 기준 정답률 | 정상응답 기준 |
|---|---:|---:|---:|---:|---:|
| `v2_in_scope` | 6 | 5 | 1 | 83.33% | 5/5, 100% |
| `v2_partial` | 2 | 1 | 1 | 50.00% | 1/1, 100% |

## 문항별 결과와 진단

| Q | Scope | 결과 | Tool / rounds | A/B/C1 요약 | C2.3 | 사후 failure 진단 | source/claim 및 version risk |
|---:|---|---|---:|---|---|---|---|
| 6 | `v2_in_scope` | 실행 오류; 실질적 unjudgeable | 4 / 4 | A=`공인중개사법`; B exact hit=`제33조·제15조·제30조`; C1에서 `제18조의4`도 rank 4로 확보했으나 마지막 검색은 타 법령 혼입 | not_reached | Primary=`tool_loop_error`; retrieval은 상당 부분 성공, 마지막 round에는 ranking noise | terminal answer가 없어 unsupported synthesis 판정 불가. 현재 공인중개사법 snapshot 시행일이 2026-08-28이므로 temporal review 필요 |
| 9 | `v2_in_scope` | 정답 2 | 5 / 4 | A=`공인중개사법·시행령·시행규칙`; B 미시도; C1에서 법 제10조, 시행규칙 제4·5조 및 관련 시행령 조문 검색 | PASS / grounded_answer | `correct`; retrieval/reasoning 성공 | substantive 판단은 검색 근거로 설명. 2026-08-28 하위법령 snapshot이므로 2024 정답과 temporal review 필요 |
| 16 | `v2_partial` | 정답 3 | 3 / 4 | A=`공인중개사법·시행규칙`; B 미시도; C1은 법 제39조를 찾았지만 필요한 업무정지 별표 2를 찾지 못함 | PASS / grounded_answer | Primary=`corpus_coverage_gap`; Secondary=`unsupported_synthesis` | 6개월/3개월 개별기간을 retrieval 없이 확정했다. 정답은 맞지만 claim-grounded 성공으로 보지 않음. 2026-08-28 snapshot 및 누락 별표 때문에 temporal/source review 필요 |
| 21 | `v2_in_scope` | 정답 4 | 2 / 3 | A=`공인중개사법·시행령`; B 미시도; C1 두 번째 검색에서 시행령 제31조 rank 1 | PASS / grounded_answer | `correct`; retrieval/reasoning 성공 | 협회 업무 열거가 직접 검색됨. 시행령 snapshot 2026-08-28이므로 temporal review 필요 |
| 27 | `v2_in_scope` | 정답 5 | 2 / 3 | A=`부동산 거래신고 등에 관한 법률·시행령`; B 미시도; C1에서 법 제11조는 검색됐으나 핵심 적용제외 열거인 시행령 제11조는 Top-K 미포함 | PASS / grounded_answer | Primary=`retrieval_failure`; Secondary=`ranking_noise + unsupported_synthesis` | 세 예외를 retrieval 근거 없이 확정했다. citation grounding PASS와 claim grounding 성공을 구분해야 함. 시행령 snapshot 2026-05-29이므로 temporal review 필요 |
| 36 | `v2_partial` | 실행 오류; 실질적 unjudgeable | 6 / 4 | B exact hit=`부동산 실권리자명의 등기에 관한 법률 제4조`, `주택임대차보호법 제3조`; C1은 관련 판례 없이 임대차/등기 유사 조문을 반복 검색 | not_reached | Primary=`tool_loop_error`; Secondary=`source_type_unavailable + corpus_coverage_gap` | 문항이 요구한 판례 source가 v2에 없음. terminal answer가 없어 unsupported synthesis는 없음. 명의신탁법 snapshot은 2020-03-24이나 판례 시점 검증 불가 |
| 37 | `v2_in_scope` | 정답 3 | 2 / 3 | A=`주택임대차보호법`; B exact hit=`제6조의2`; C1에서 `제6조의3` rank 1 | PASS / grounded_answer | `correct`; retrieval/reasoning 성공, 과거 cross-law ranking 혼입 없음 | 핵심 두 조문 모두 확보. 현재 snapshot 시행일 2026-01-02이므로 2024 조문과 temporal review 필요 |
| 38 | `v2_in_scope` | 정답 5 | 2 / 3 | 첫 query의 붙여쓴 법률명 때문에 A hard filter는 미적용; B exact hit=`제3조·제5조·제10조·제10조의4`; C1에서 제4조 rank 1 | PASS / grounded_answer | `correct`; exact/semantic retrieval 성공 | 필요한 대항력·확정일자·우선변제·갱신 근거 확보. 현재 snapshot 시행일 2026-05-12이므로 temporal review 필요 |

## A/B/C1/C2.3 관찰

- A canonical law filter는 8문항 중 7문항에서 한 번 이상 적용됐다. 38번의 첫 query는 canonical 명칭과 달리 `상가건물임대차보호법`으로 붙여 써서 A가 적용되지 않았으나, 이후 B exact lookup은 canonical pair를 정상 탐지했다.
- B exact lookup은 4문항(6, 36, 37, 38)에서 시도됐고 모두 hit했다.
- C1은 모든 semantic fallback에서 전체 시험문제가 아닌 original model-generated query를 사용했다.
- C2.3은 terminal response가 존재한 6문항을 모두 PASS했다. 6·36번은 Tool loop가 먼저 종료되어 validator까지 도달하지 않았다.
- C2.3 PASS는 citation pair provenance가 맞다는 뜻이며, 16·27번처럼 retrieval 본문 밖의 substantive claim까지 보장하지 않는다.

## 실패 유형 집계

- `tool_loop_error`: 2 — 6, 36
- `corpus_coverage_gap`: 2 — 16, 36
- `source_type_unavailable`: 1 — 36(판례)
- `retrieval_failure`: 1 — 27(핵심 시행령 제11조 미검색)
- `ranking_noise`: 2 — 6의 마지막 검색, 27
- `unsupported_synthesis`: 2 — 16, 27
- 명확한 독립 `reasoning_failure`: 0
- `validator_false_rejection`: 0
- `infrastructure_failure`: 0

16번과 27번은 정답 번호가 맞았지만 retrieval이 충분하지 않은 상태에서 구체 법률 내용을 보충했으므로, 단순 정답 성공과 RAG/claim-grounding 성공을 분리해 기록했다.

## 보호 확인

이번 실행 후 Prompt, Provider, Tool, Retriever, 운영 Validator, `.env`, Vector Store를 변경하지 않았다. 2024 전체 40문항과 2025 문제는 실행하지 않았다.

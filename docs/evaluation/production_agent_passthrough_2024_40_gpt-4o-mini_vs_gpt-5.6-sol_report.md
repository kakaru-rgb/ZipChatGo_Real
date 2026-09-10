# Production-Agent Passthrough Model Shadow Comparison

## 실험 고정 조건

- 입력: 검수 완료 `공인중개사_문항_2024.csv`의 `공인중개사법령 및 중개실무` 40문항
- Baseline: `gpt-4o-mini`, 동결된 `공인중개사_운영Agent_passthrough_baseline_2024_40_reanalyzed_v2.csv`
- Shadow model: `gpt-5.6-sol`
- EvaluationMode: `production_agent_passthrough`
- Sol RunID: `passthrough-2026-09-10T162019_0900-7eed5978`
- 평가일시: `2026-09-10T16:20:19+09:00`
- GitCommit: `00973143a683ada533d46e15bfdb5268443b4ceb`
- 운영 Prompt, Provider, Tool schema/handler/loop, Retriever, Vector Store, parser, scope classifier는 동일하며 모델 문자열만 evaluation-only CLI에서 주입했다.
- 별도 temperature, top_p, reasoning.effort는 지정하지 않았다.

## 전체 결과

| 지표 | gpt-4o-mini | gpt-5.6-sol |
|---|---:|---:|
| 전체 정답 | 15/40 (37.50%) | 26/40 (65.00%) |
| in_scope | 11/31 (35.48%) | 24/31 (77.42%) |
| partial_scope | 2/3 (66.67%) | 1/3 (33.33%) |
| out_of_scope | 2/6 (33.33%) | 1/6 (16.67%) |
| 법률 Tool 호출 문항 | 28/40 (70.00%) | 40/40 (100.00%) |
| in_scope 법률 Tool 호출 | 25/31 (80.65%) | 31/31 (100.00%) |
| in_scope Tool 미호출 | 2, 7, 12, 17, 18, 26 | 없음 |
| Tool 호출 문제 정확도 | 11/28 (39.29%) | 26/40 (65.00%) |
| Tool 미호출 문제 정확도 | 4/12 (33.33%) | 해당 없음 |
| 판정불가 | 1 | 10 |
| 실행 오류 | 0 | 4 |
| grounding validation 거절 | 1: 35 | 8: 9, 33, 34, 35, 36, 37, 39, 40 |
| 비법률 Tool 오호출 | 0 | 0 |

Sol은 40문항 모두 법률 Tool을 자율 호출했고 총 법률 Tool 호출은 126회였다. 문항별 호출 수는 1~9회이며, 운영 Provider의 4 response-round 한도를 소진한 6, 7, 21, 27번은 `OpenAIToolLoopError`로 종료됐다. 판정불가 10개 중 8개는 grounding validation 거절이고, 16·30번은 근거 부족을 이유로 명시적 정답 번호를 내지 않았다.

## 문항 상태 변화

- gpt-4o-mini 오답 → Sol 정답: **16문항** — 2, 3, 5, 8, 11, 12, 13, 15, 17, 22, 23, 26, 28, 31, 32, 38
- gpt-4o-mini 정답 → Sol 오답: **0문항**
- 둘 다 정답: **10문항** — 1, 4, 10, 14, 18, 19, 20, 24, 25, 29
- 둘 다 명시적 오답: **0문항**
- baseline 정답 → Sol 오류: **1문항** — 6
- baseline 오답 → Sol 오류: **3문항** — 7, 21, 27
- baseline 정답 → Sol 판정불가: **4문항** — 9, 30, 34, 40
- baseline 오답 → Sol 판정불가: **5문항** — 16, 33, 36, 37, 39
- 둘 다 판정불가: **1문항** — 35

## 기존 수동 실패 유형별 변화

| Baseline 수동 실패 유형 | 대상 | Sol 정답 회복 | Sol 기타 결과 |
|---|---|---|---|
| reasoning_failure | 3, 5, 11, 13, 15, 22, 23, 32 | **8/8** | 없음 |
| retrieval_failure | 8, 16, 21, 27 | **1/4**: 8 | 16 판정불가, 21·27 Tool-loop 오류 |
| retrieval_ranking_failure | 37 | **0/1** | grounding validation 거절 |
| query_generation_failure | 38 | **1/1** | 없음 |
| mixed_retrieval_reasoning | 28 | **1/1** | 없음 |

## 기존 15문항 Query/Top-K 비교

전체 round별 query, Top-K와 score는 동반 비교 CSV에 원문 그대로 보존했다. 아래는 변화의 핵심 요약이다.

| 문항 | Baseline 답·검색 | Sol 답·검색 | 관찰 |
|---:|---|---|---|
| 3 | 3 / 휴업 신고 1회, 시행령 제18조 rank 1 | **2** / 세부 쟁점 query 3회, 시행령 제18조 rank 1 유지 | 같은 핵심 근거를 더 정확히 추론하여 회복 |
| 5 | 4 / 고용인의 신고 1회, 시행규칙 제8조·법 제15조 | **3** / 세부 선택지 query 2회, 동일 핵심 조문 | 근거 독해 개선으로 회복 |
| 8 | 2 / 게시 의무 query에서 시행규칙 제10조 누락 | **1** / 2차 query에서 시행규칙 제10조 rank 4 검색 | query 구체화로 필요한 조문 검색 성공 |
| 11 | 3 / 법 제24조 rank 1 | **4** / 법 제24조 ranks 1·3 | 동일 근거의 취소·청문 예외를 정확히 적용 |
| 13 | 5 / 법 제33조 rank 1 | **3** / 3회 검색, 법 제33조 반복 rank 1 | 제1항과 제2항 적용대상 구분 성공 |
| 15 | 1 / 시행규칙 제20조 rank 1 | **4** / 2회 검색, 제20조 rank 1 | `중개사무소 소재지` 문언을 정확히 적용 |
| 16 | 2 / 법 제39조만 검색 | 판정불가 / 별표·개별기준 query 3회에도 법 제39조만 상위 | query는 개선됐으나 필요한 처분기준표 미검색; 추측 대신 답 유보 |
| 21 | 5 / 협회업무 조문 누락 | 오류 / 4회 검색, 법 제41조가 3차 rank 4이나 세부 업무 근거 미확보 | query 개선에도 Tool loop 한도 소진 |
| 22 | 2 / 법 제10조 ranks 1·2 | **4** / 선택지 쟁점 포함 query, 법 제10조 ranks 1·2 | `5년/7년`, 등기소 통지 문언을 정확히 적용 |
| 23 | 5 / 시행규칙 제3조 rank 1 | **2** / 세부 선택지 query, 제3조 rank 1 | `매수인 추가`와 `일부 제외` 구분 성공 |
| 27 | 4 / 적용 제외 조문 미검색 | 오류 / 적용 제외·환매·농어촌공사를 포함한 query 4회에도 핵심 조문 미검색 | query는 구체화됐지만 retrieval 미회복, Tool loop 소진 |
| 28 | 2 / 법 제3조 rank 1, 하위 열거 미검색 | **1** / 3회 검색, 법 제3조 ranks 1~2 | 부분 근거에서도 증여/매매 차이를 정확히 판단 |
| 32 | 4 / 제6조 rank 2, 제5조 rank 5 | **3** / 3회 검색, 제6·8·7·5조 확보 | `공용부분` 반증과 제5조 제3항을 정확히 적용 |
| 37 | 1 / 상가법 제10조 rank 1, 주택법 제6조의3 rank 2 | 판정불가 / 2차에 주택법 제6조의2 rank 4까지 검색 | 상가법 rank 1 우위가 계속됐고 최종 답은 grounding validation에서 거절 |
| 38 | 2 / query가 법률명뿐이며 핵심 조문 누락 | **5** / 대항력·확정일자·정보제공·우선변제 query, 제4·5조 검색 | query generation 개선으로 필요한 조문을 확보하고 회복 |

## 해석

- 가장 중요한 지표인 기존 `reasoning_failure` 8문항은 Sol이 **8/8 모두 회복**했다.
- Sol의 전체 정답률은 27.5%p, in_scope 정확도는 41.94%p 상승했다.
- 반면 법률 Tool 호출률이 100%로 증가하고 총 126회 호출하여, 4문항이 운영 Tool-loop 한도를 소진했다.
- grounding validation 거절도 1건에서 8건으로 증가했다. 따라서 65% 정확도 상승과 함께 과도한 검색/다중 호출 및 최종 grounding 불일치라는 새로운 비용·안정성 문제가 관찰된다.
- 이 결과는 동일 retrieval 결과만의 reasoning 비교가 아니라 routing, query generation, retrieval 결과, reasoning을 모두 포함한 end-to-end 모델 교체 효과다.

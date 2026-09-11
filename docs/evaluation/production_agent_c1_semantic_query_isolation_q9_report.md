# C1 Semantic Retrieval Query Isolation — 9번

## 실행 정보

- C1 RunID: `law-semantic-isolation-2026-09-11T170157_0900-7fb66859`
- 비교 기준 A+B valid RunID: `law-exact-2026-09-11T153309_0900-9b9bde3b`
- 모델: `gpt-5.6-sol`
- 대상: 2024년 공인중개사법령 및 중개실무 9번, 정확히 1회 실행
- C1 변경점: semantic Vector Store search에 원래 `model_arguments.query`만 전달
- 유지 조건: A 법률명 filter, B exact lookup, 운영 Prompt·Provider·Validator, corpus, top-k, threshold, query rewrite, Tool round limit

## 1차 성공 조건

**성공** — `공인중개사법 시행규칙 제6조`가 C1 retrieval 결과에 포함됐다.

- 검색된 Tool call: 3번째 법률 Tool 호출
- rank: 1
- score: `0.8573450613905559`
- 모델 query: `공인중개사법 시행규칙 중개사무소 등록 행정처분 통지서 매월 다음달 10일 협회 통보 등록관청`

A+B에서는 동일 핵심 쟁점의 query가 생성됐지만, full user question과 결합된 문자열로 검색되어 제6조가 Top-K에 없었다. C1에서는 격리된 model query로 검색했을 때 제6조가 rank 1이었다.

## Query 비교

### A+B 기존 semantic 검색 입력

모든 semantic search에 다음 형태의 500자 제한 문자열이 전달됐다.

```text
사용자 질문: [문제 전체와 선택지; 제5 선택지 중간에서 잘림]
핵심 법률 검색어: [model query]
```

실제 trace에서는 500자 절단 때문에 `핵심 법률 검색어` 부분이 검색 입력에서 사라졌다.

### C1 semantic 검색 입력

1. `공인중개사법 중개사무소 개설등록 결격사유 집행유예 2년 협회 등록사항 시도지사 통보 외국법인 영업소 등기 7일 등록증 반납`
2. `공인중개사법 시행규칙 중개사무소 개설등록 신청 7일 이내 서면 통지 개업공인중개사 종별`
3. `공인중개사법 시행규칙 중개사무소 등록 행정처분 통지서 매월 다음달 10일 협회 통보 등록관청`
4. `공인중개사법 시행규칙 외국에 주된 영업소 법인 상법 외국회사 영업소 등기 증명 서류 개설등록`
5. `공인중개사법 시행규칙 공인중개사인 개업공인중개사가 법인인 개업공인중개사 개설등록 다시 신청 종전 등록증 반납`

## Top-K 비교

### A+B 기존 결과

| Tool call | 검색 방식 | 결과 |
|---:|---|---|
| 1 | full question semantic | 1 시행령 제13조, 2 시행규칙 제4조, 3 법 제38조, 4 법 제51조, 5 시행규칙 제4조 |
| 2 | exact | 법 제10조 |
| 3 | full question semantic | 1 시행규칙 제4조, 2 법 제51조, 3 법 제38조, 4 시행규칙 제4조, 5 시행령 제18조 |
| 4 | full question semantic | 1 시행령 제13조, 2 시행규칙 제4조, 3 법 제51조, 4 법 제38조, 5 시행규칙 제4조 |

- 시행규칙 제6조: 검색되지 않음

### C1 결과

| Tool call | Response round | 격리된 semantic Top-K |
|---:|---:|---|
| 1 | 1 | 1 법 제10조, 2 시행규칙 제24조 |
| 2 | 2 | 1 시행규칙 제4조, 2 시행규칙 제9조, 3 법 제34조 |
| 3 | 2 | **1 시행규칙 제6조**, 2 시행규칙 제9조, 3 법 제20조, 4 시행규칙 제24조, 5 시행규칙 제8조 |
| 4 | 2 | 1 시행규칙 제4조, 2 시행규칙 제4조, 3 시행규칙 제9조, 4 시행령 제13조, 5 시행규칙 제8조 |
| 5 | 2 | 1 시행규칙 제9조, 2 법 제40조, 3 시행령 제18조, 4 시행령 제24조, 5 시행규칙 제24조 |

결과 수가 5보다 적은 call은 기존 Retriever의 동일 threshold·relative score filtering 결과다.

## Agent 및 validation 결과

| 항목 | A+B valid | C1 |
|---|---|---|
| 법률 Tool 호출 수 | 4 | 5 |
| Response round 수 | 4 | 3 |
| ExactLookupAttempted | Y | N |
| ExactLookupHit | Y | N |
| ExactLookupResult | 공인중개사법 제10조 | 없음 |
| 시행규칙 제6조 | 없음 | **rank 1** |
| PreValidation 답 | 2 | 2 |
| 공식정답 | 2 | 2 |
| ValidationResult | rejected | rejected |
| ValidationFailureReason | ungrounded_article_citation | ungrounded_article_citation |
| Agent 최종답 | 없음 | 없음 |

C1 실행에서는 모델이 명시적인 `법령명 + 제N조` query를 생성하지 않아 exact lookup이 시도되지 않았다. 이는 exact 기능 실패가 아니라 exact trigger 부재다.

C1 `PreValidationRawResponse`는 시행규칙 제6조를 직접 근거로 정답 2를 설명한다. 따라서 핵심 정답 판단은 A+B보다 retrieval grounding이 개선됐다. 최종 거절은 unchanged validator가 검색된 시행규칙 제4조 본문의 cross-reference인 `상법 제614조`를 독립 미검색 citation으로 처리한 결과이며, C1의 retrieval 성공 여부와는 별개다.

## 실험 판정

- 1차 retrieval 성공 조건: **충족**
- 우연히 정답만 맞힌 경우인가: 아니오. 핵심 근거인 시행규칙 제6조가 실제 검색되어 답변에 사용됐다.
- semantic query isolation의 증분 효과: 이 1회 targeted run에서는 긍정적
- 제한: 단일 문항·단일 실행이며 모델의 Tool query 및 호출 수 자체도 A+B 실행과 달라졌으므로 일반화에는 추가 regression 실험이 필요하다.

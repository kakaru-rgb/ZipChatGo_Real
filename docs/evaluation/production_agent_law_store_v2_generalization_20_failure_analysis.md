# law_store_v2 사용자형 20문항 실패 현상 분석

## 1. 분석 범위

이 보고서는 동결된 다음 결과만 offline으로 분석한다.

```text
docs/evaluation/production_agent_law_store_v2_generalization_regression_20.csv
RunID: law-v2-user-regression-baf62a52ffa7
```

- OpenAI API 신규 호출: 0회
- Vector Store API 신규 호출: 0회
- 운영 코드 및 A/B/C1/C2.1 변경: 없음
- 기존 테스트 변경·실행: 없음
- 2024/2025 평가 실행: 없음
- 새 Harness 기능 구현: 없음

분석 대상은 3·7·8·18번이다. 19번은 별도의 로컬 통합 의존성 실패로만 기록한다.

## 2. 3번 — 부재 설명을 affirmative citation으로 오인

### 저장 trace

- 질문: `주택임대차보호법 제6조의3의 계약갱신요구권을 쉽게 설명해 주세요.`
- model query: `주택임대차보호법 제6조의3 계약갱신요구권 행사 기간 횟수 갱신 기간 임대인 거절 사유`
- exact hit: `주택임대차보호법 제6조의3`, 2개 chunk
- PreValidation의 주된 근거: `「주택임대차보호법」 제6조의3`
- 문제 문장: `이번 검색 결과에 인용된 제6조 본문이 없어 확정적으로 안내하기 어렵습니다.`

C2.1 citation trace:

| Raw reference | C2.1 해석 | 결과 |
|---|---|---|
| `「주택임대차보호법」 제6조의3` | affirmative primary pair | retrieval pair와 일치, 허용 |
| `제6조` | 직전 active law인 주택임대차보호법의 독립 인용 | retrieval에 없어 거절 |

### 코드 원인

`_parse_candidates()`는 응답 안의 모든 `제N조/제N조의M` 패턴을 수집한다. 문장의 긍정·부정, “검색되지 않았다”라는 담화 역할은 읽지 않는다.

첫 번째 명시 pair로 `active_law=주택임대차보호법`이 설정된 뒤 bare `제6조`가 나오면, `validate()`는 이를 같은 법의 primary pair 후보로 결합한다. C2.1에는 다음 구분이 없다.

- `affirmative_evidence_citation`: 법적 결론의 근거로 사용
- `negative_or_unavailable_reference`: 검색 부재나 비사용을 설명

따라서 검색되지 않은 조문을 **근거로 주장하지 않고 오히려 부재를 고지한 안전 문장**도 fabricated citation과 같은 경로로 거절된다.

### 일반화 판단

이 현상은 3번 문구에만 한정되지 않는다. 일반 사용자 법률 답변에서도 다음 표현이 자연스럽게 발생한다.

- “제N조는 이번 검색에서 확인되지 않았습니다.”
- “제N조 본문이 없으므로 이 부분은 단정하지 않겠습니다.”
- “해당 조문을 근거로 사용할 수 없습니다.”

현재 parser는 모두 article pattern으로 수집하므로 재현 가능한 구조적 문제다.

**분류: `GENERALIZABLE_BUG`**

## 3. 18번 — citation 없는 안전한 abstention 거절

### 저장 trace

- 질문: 계약서 조항 원문 없이 무효 여부와 판례 확인을 요구
- model query: `부동산 계약 약정 조항 무효 강행규정 계약 효력`
- retrieval: 소득세법 시행령 제25조 등 질문과 무관한 결과
- PreValidation:
  - 계약서 조항과 계약 유형 등 추가 자료가 필요하다고 설명
  - 검색 결과가 직접 관련 없다고 명시
  - 판례 원문을 조회할 수 없으므로 확정할 수 없다고 명시
  - 법적 결론이나 조문 citation을 제시하지 않음
- C2.1: `missing_article_citation`으로 REJECT

### 코드 원인

C2.1의 종료 조건은 단순하다.

```text
파싱된 citation trace가 0개
→ missing_article_citation
→ REJECT
```

호출 측은 법률 Tool trace가 하나라도 있으면 C2.1을 적용한다. 따라서 검색 결과가 무관함을 인식하고 아무 citation 없이 안전하게 멈춘 응답도, affirmative legal answer와 똑같이 “citation 필수” 규칙을 적용받는다.

C2.1에는 다음 응답 유형 구분이 없다.

- 법적 결론을 제시하면서 citation이 없는 응답
- `abstention_without_citation`: 충분한 근거가 없다고 명시하고 법적 결론을 내리지 않는 응답

### 일반화 판단

실제 사용자 질문은 계약서·사실관계·판례 자료가 부족한 경우가 많다. Agent가 검색 후 관련 근거가 없다고 판단해 질문 보완을 요청하는 것은 정상적인 안전 동작이다. 현재 C2.1은 이런 응답을 일반적으로 더 추상적인 거절문으로 덮을 수 있다.

안전성은 유지되지만 다음 품질 손실이 생긴다.

- 왜 답할 수 없는지에 대한 구체적 설명 손실
- 사용자가 추가로 제공할 자료 안내 손실
- 이미 안전하게 abstain한 응답을 validator failure로 잘못 집계

**분류: `GENERALIZABLE_BUG`**

## 4. C2/C2.1 안전 요구사항과 좁은 개선 가능성

기존 offline/unit test가 보장하는 핵심 조건은 다음과 같다.

| 안전 요구사항 | 현재 테스트의 의미 |
|---|---|
| Fabricated citation | retrieval과 부모 본문 어디에도 없는 `민법 제999조`는 거절 |
| Wrong law/article pair | law name과 article number가 각각 존재해도 pair가 다르면 거절 |
| 동일 조문번호·다른 법률 | `민법 제6조`와 `주택법 제6조`를 혼동하지 않음 |
| Dependent cross-reference | 검색된 부모 pair 본문에 실제 reference가 있을 때만 허용 |
| 무관 chunk 격리 | 다른 법령/조문의 본문에만 reference가 있으면 허용하지 않음 |
| Multi-chunk parent | 동일 parent pair의 여러 chunk 중 실제 reference가 있는 chunk를 찾음 |
| 법/시행령/시행규칙 축약 | 활성 law family 안에서만 해석 |
| 애매한 축약 | 복수 family로 모호하면 보수적으로 거절 |
| Sub-article | `제6조`와 `제6조의2`를 별도 pair로 유지 |

3·18번을 다루는 향후 후보는 위 요구사항을 하나도 약화시키면 안 된다.

### 좁게 처리할 수 있는가

가능성은 있다. 단, 이번 단계에서는 구현하지 않는다.

가장 좁은 후보는 citation 존재 여부를 완화하는 것이 아니라 **응답 내 reference의 역할과 응답 전체의 abstention 상태를 먼저 분리**하는 것이다.

1. `negative_or_unavailable_reference`
   - 같은 문장/절 안에 “검색되지 않음”, “본문이 없음”, “확인되지 않음”, “근거로 사용할 수 없음”처럼 명백한 부재 표현이 있을 때만 후보로 분류한다.
   - 이 reference는 affirmative grounding으로 인정하지 않고, active law/pair 근거도 확장하지 않는다.
   - 애매하면 기존처럼 검증·거절한다.

2. `abstention_without_citation`
   - 관련 근거가 부족하다고 명시하고, 구체 법적 효력·기한·의무를 확정하지 않으며, 추가 자료나 공식 확인을 요청하는 응답에만 제한한다.
   - 단순히 citation이 없다는 이유만으로 PASS시키지 않는다.
   - affirmative legal claim이 하나라도 있으면 기존 citation 검증을 그대로 요구한다.

3. 기존 pair 검증 유지
   - affirmative citation은 계속 `(law_name, article_number)` exact pair를 요구한다.
   - fabricated/mismatched citation, 잘못된 cross-reference 및 모호한 family는 계속 REJECT한다.

이 방식은 false rejection을 줄일 여지가 있으면서도 hallucinated citation을 허용할 필요가 없다. 다만 자연어의 부정 범위를 잘못 판단하면 실제 unsupported claim을 숨길 위험이 있으므로, 반드시 evaluation-only offline 후보와 adversarial negative test로 먼저 검증해야 한다.

## 5. 7번 — Tool-loop 시간순 분석

### Round trace

| Response round | Model-generated query | 결과 요약 | 다음 검색 목적 |
|---:|---|---|---|
| 1 | 주택임대차보호법, 실거주 갱신거절, 손해배상, 정보열람 | 제6조의3 rank 1 | 실거주 거절 후 제3자 임대 여부를 확인할 절차 탐색 |
| 2 | 제3자 임대차 정보 열람, 정보제공, 전입세대 확인 | 제3조, 제3조의3, 제3조의7, 제6조의3 등 | 정보제공 주체·범위의 구체 조문 탐색 |
| 3 | 제3조의6, 확정일자·임대차정보 열람, 이해관계인 | 제3조의6 exact hit | 하위법령상 이해관계인과 제공 범위 탐색 |
| 4 | 시행령, 이해관계 있는 자, 정보제공 요청 범위 | 시행령 제5조·제6조 | 다시 Tool call로 끝나 final synthesis 이전에 round limit 도달 |

### 충분한 근거였는가

- 갱신거절 및 손해배상이라는 **핵심 법적 구조**는 첫 검색의 제6조의3에서 확보했다.
- 하지만 사용자 질문은 “실제로 입주하지 않았음을 어떻게 확인하는가”까지 물었다. Agent는 이를 위해 임대차정보 제공·이해관계인 범위의 구체 근거를 계속 찾았다.
- 마지막 검색에서 시행령 제5·6조까지 얻었지만, 그 결과를 종합할 다음 response round 전에 기존 limit에 도달했다.

### No-progress 여부

네 query는 동일하지 않다. `갱신거절/손해배상 → 제3자 임대 확인 → 제3조의6 exact → 시행령상 이해관계인`으로 점차 좁아진다. 의미적 중첩은 있으나 동일 query/동일 Top-K 반복형 no-progress로 보기는 어렵다.

20문항 중 Tool-loop error는 이 1건뿐이다. 필요한 세부 절차 근거를 찾던 경계 사례이며, 현재 증거로 D Tool-loop 변경이나 round 증가를 정당화하지 않는다.

**분류: `OBSERVE_ONLY`**

## 6. 8번 — Cross-law semantic ranking 혼입

### 저장 trace

- 질문: 묵시적으로 갱신된 전세계약의 임차인 해지 효력 발생 시점
- model query: `주택임대차 묵시적 갱신 임차인 해지 통지 계약 종료 시기 3개월`
- A filter: 미적용
- B exact: 미적용

Top-K:

| Rank | 법령/조문 | Score | 관련성 |
|---:|---|---:|---|
| 1 | 농지법 시행규칙 제20조의2 | 0.840 | 무관 |
| 2 | 주택임대차보호법 제6조의2 | 0.810 | 핵심 근거 |
| 3 | 상가건물 임대차보호법 제10조의4 | 0.778 | 다른 임대차 family |
| 4 | 농지법 제25조 | 0.777 | 무관 |
| 5 | 상가건물 임대차보호법 제10조 | 0.768 | 다른 임대차 family |

### 원인 구분

- Corpus 문제: 아님. 필요한 `주택임대차보호법 제6조의2`가 실제로 존재하고 검색됐다.
- Query 문제: 제한적. query는 쟁점과 `3개월`까지 충분히 구체적이지만 정식 canonical 이름 `주택임대차보호법` 대신 일반 표현 `주택임대차`를 사용했다.
- Filter 미적용 이유: A는 의도적으로 canonical exact name만 허용한다. 사용자 질문과 model query 모두 완전한 canonical 이름을 포함하지 않아 filter를 만들지 않은 것이 현재 설계상 정상이다.
- 주된 현상: unfiltered embedding search의 semantic ranking noise. 숫자·기간·절차 표현이 무관한 농지 조문과 유사도를 높인 것으로 보인다.

핵심 조문은 rank 2에 포함됐고 Agent는 이를 선택해 정확한 “통지 도달 후 3개월” 답변을 만들었으며 C2.1도 PASS했다. 현재 단일 성공 사례만으로 threshold, reranker, law-name inference 또는 새로운 filter rule을 추가할 근거는 부족하다.

Cross-law rank 혼입은 다른 질문에서도 발생할 수 있는 일반 현상이지만, 이번에는 end-to-end 실패를 만들지 않았다.

**분류: `GENERALIZABLE_BUT_LOW_PRIORITY`**

## 7. 18번과 3번 질문에 대한 직접 답변

1. **3번 false rejection은 일반 사용자 답변에서도 재현 가능한가?**  
   그렇다. C2.1은 모든 article pattern을 담화 역할과 무관하게 citation으로 취급하므로, 검색 부재를 설명하는 일반적인 안전 문장에서도 재현될 수 있다.

2. **18번 `missing_article_citation`은 안전한 abstention을 부당하게 막는 일반 문제인가?**  
   그렇다. 법률 Tool을 호출한 뒤 관련 근거가 없어서 citation 없이 멈추는 모든 응답에 동일하게 적용될 수 있다.

3. **핵심 안전성을 약화시키지 않고 좁게 처리할 수 있는가?**  
   가능성이 있다. 명백한 negative/unavailable reference를 affirmative evidence로 인정하지 않되 rejection 근거에서도 제외하고, affirmative claim이 없는 명백한 abstention만 별도로 보존하는 방식이 후보이다. 실제 pair 주장과 fabricated citation 검증은 그대로 유지해야 한다.

## 8. 19번 제외 근거

19번은 법률 Tool을 호출하지 않고 `search_properties`를 선택했다. 이후 로컬 Spring property API 접속 실패가 발생했다.

```text
routing = 정상
RAG regression = 아님
failure = LOCAL_INTEGRATION_FAILURE
```

법률 RAG 변경 대상에서 제외한다.

## 9. Generalization 전체 균형 평가

실패 사례만으로 architecture 전체가 불안정하다고 볼 수 없다.

| 긍정 지표 | 결과 |
|---|---:|
| 법률 질문 routing | 18/18 |
| 비법률 질문 law-tool 오호출 | 0/2 |
| B exact lookup | 8/8 |
| 신규 v2 law family A/B 연결 | 2·6·14번에서 성공 |
| Store 미지원 질문 safe abstention | 2/2 |
| Unsafe unsupported answer | 0 |
| 명확한 독립 reasoning failure | 0 |

관찰된 문제는 routing이나 신규 corpus 연결 실패가 아니라, C2.1의 응답 의미 미구분 2건, 세부 절차 탐색 중 Tool-loop 1건, 결과를 깨지 않은 ranking noise 1건으로 국한된다.

## 10. 최종 분류

| 문항 | 분류 | 근거 |
|---:|---|---|
| 3 | `GENERALIZABLE_BUG` | 검색 부재 설명을 affirmative citation으로 오인하는 구조적 validator 문제 |
| 7 | `OBSERVE_ONLY` | query가 진전됐고 20개 중 유일한 loop 사례 |
| 8 | `GENERALIZABLE_BUT_LOW_PRIORITY` | 일반적인 semantic noise 가능성은 있으나 핵심 조문 검색·최종 답 성공 |
| 18 | `GENERALIZABLE_BUG` | citation 없는 안전한 abstention을 무조건 거절하는 구조적 validator 문제 |
| 19 | `LOCAL_INTEGRATION_FAILURE` | 올바른 property Tool routing 후 Spring 접속 실패 |

## 11. 다음 단계 추천

```text
A. C2.1 narrow offline fix candidate only
```

추천 범위는 3·18번의 의미 구분을 위한 **좁은 evaluation-only offline 후보 검증**뿐이다. D Tool-loop나 ranking 변경은 다음 단계의 필수 조건이 아니다.

향후 후보가 진행되더라도 fabricated citation, wrong pair, cross-reference parent 격리, multi-chunk, 법령 family 축약 및 모호성 보수 거절에 대한 기존 안전 테스트를 모두 유지하고, 새로운 negative/adversarial replay를 먼저 통과해야 한다.

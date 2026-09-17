# law_store_v2 C2.2 Luna Targeted Offline Failure Analysis

## 1. 분석 범위

분석 대상은 동결된 다음 live 실행의 3·15·18번이다.

```ini
RunID = law-v2-c22-luna-targeted-0844010e23cd
CorpusVersion = law_store_v2
AgentModel = gpt-5.6-luna
```

사용한 자료는 저장된 `PreValidationRawResponse`, `ToolCalls`, exact/semantic trace, C2.2 citation trace와 현재 evaluation-only validator 코드뿐이다.

```text
OpenAI API 호출 = 0
Vector Store API 호출 = 0
Agent 재실행 = 0
```

C2.2 및 운영 Agent·Prompt·Provider·Tool·Retriever·Validator·Vector Store·`.env`는 변경하지 않았다.

## 2. 결론 요약

| 문항 | Luna Agent 행동 | C2.2 행동 | 최종 분류 |
|---:|---|---|---|
| 3 | 검색된 부모 조문에 실제 존재하는 동일 법률 제7조 교차참조를 설명에 사용 | full-law 형태를 독립 미검색 pair로 보아 거절 | `GENERALIZABLE_VALIDATOR_BUG` |
| 15 | 미지원 법률임을 인식하고 정확한 기한을 단정하지 않았으나 제한적인 절차 설명은 포함 | 좁은 abstention 표현식에 매칭되지 않아 거절 | `GENERALIZABLE_BUT_LOW_PRIORITY` |
| 18 | Tool 없이 계약서 원문과 사실관계를 요청하고 법적 결론을 보류 | Law Tool trace가 없어 적용하지 않음 | `EXPECTED_NOT_APPLIED` |

Validator 거절과 Luna 모델 실패를 동일하게 집계해서는 안 된다. 3번과 15번의 PreValidation 행동은 각각 근거 활용과 안전한 제한 고지 측면에서 유용했으며, 18번은 validator의 적용 대상이 아닌 안전한 clarification이었다.

## 3. 3번 — parent cross-reference

### 저장 trace의 사실관계

- exact retrieval parent pair: `(주택임대차보호법, 제6조의3)`
- 제6조의3 제3항 본문: `차임과 보증금은 제7조의 범위에서 증감할 수 있다`
- Luna 응답: `「주택임대차보호법」 제7조의 범위에서 조정될 수 있습니다`
- C2.2 trace: `(주택임대차보호법, 제7조)`를 `independent_unretrieved`로 분류
- 결과: `ungrounded_law_article_pair`

다음 네 조건은 모두 충족된다.

1. 부모 retrieval pair가 실제 존재한다.
2. 부모 본문에 정규 조문 참조 형태인 `제7조`가 실제 존재한다.
3. 응답의 법률명은 부모와 같은 family일 뿐 아니라 이 사례에서는 동일 canonical law name이다.
4. 응답은 부모 본문에 없는 새 조문번호를 만들어내지 않았다.

### 코드 경로

`PairAwareGroundingValidatorC22.validate()`는 negative/unavailable reference만 먼저 가린 뒤 나머지 검증을 C2.1에 위임한다. 3번의 제7조는 affirmative 설명이므로 마스킹 대상이 아니며 C2.1로 전달되는 것이 맞다.

C2.1은 응답의 `주택임대차보호법 제7조`를 `explicit` candidate로 파싱한다. exact retrieval pair에 제7조가 없으므로 활성 부모인 제6조의3의 본문을 검사하지만, explicit candidate의 parent match는 부모 본문에도 `주택임대차보호법 제7조`라는 full-law surface form이 있어야 성공한다. 부모 본문에는 bare `제7조`만 있어 match가 실패한다.

중요하게도 현재 구현은 다음과 같이 동작한다.

- 응답 `주택임대차보호법 제7조`: explicit candidate이므로 부모에서 full-law 표현을 요구하고 REJECT
- 응답 bare `제7조`: bare candidate는 parent cross-reference 검사 대상 자체가 아니므로 REJECT
- 응답 `법 제N조`, `시행령 제N조`, `같은 법 제N조` 등: shorthand 형태와 같은 형태가 부모 본문에 실제 존재할 때 제한적으로 허용

따라서 이 사례는 단순히 “bare는 허용되지만 full-law expansion만 거절”된 것이 아니다. **검색 부모의 bare same-law reference와 응답의 의미상 동일한 full-law expansion을 연결하는 경로가 없는 구조적 edge case**다.

### 안전하게 제한 가능한가

후보 범위는 다음 조건을 모두 만족하는 경우로 좁힐 수 있다.

```text
이미 검증된 active parent pair 존재
+ response의 explicit canonical law name이 parent law와 동일
+ response article number가 parent body에 실제 ARTICLE_PATTERN으로 존재
+ 해당 reference가 그 parent의 종속 근거 문맥에 연결됨
```

이 조건이라면 다음 안전성은 유지 가능하다.

- `민법 제10조` 부모 본문에 제20조가 없는데 응답이 `민법 제20조`를 인용하면 article match가 없으므로 REJECT
- 부모가 주택임대차보호법이고 응답이 다른 법률 제7조를 인용하면 canonical law가 다르므로 REJECT
- 본문에 숫자 7만 있고 `제7조` 패턴이 없으면 article reference가 아니므로 REJECT

다만 같은 문서의 다른 조문을 부모가 단순 나열한 것과 실제 법적 종속 근거를 완전히 구별하는 문제는 남는다. 따라서 이 단계에서는 수정하지 않고 adversarial offline 검증을 선행하는 좁은 후보로만 기록한다.

**분류: `GENERALIZABLE_VALIDATOR_BUG`**

이는 Luna 전용 현상이 아니다. 어떤 모델이 부모 조문의 bare 교차참조를 동일 canonical 법률의 완전한 인용으로 풀어 써도 재현될 수 있다.

## 4. 15번 — safe abstention wording

### Luna 응답의 의미

Luna는 다음을 수행했다.

- 현재 검색에 민사집행법 관련 조문이 없음을 명시
- 정확한 배당요구 종기를 확정하지 않음
- 검색된 다른 법령을 민사집행법 근거로 인용하지 않음
- 사건별 법원 공고와 대한민국 법원 경매정보 확인을 안내
- 조문 citation을 만들지 않음

그러나 완전히 내용 없는 abstention은 아니다. 다음과 같은 제한적인 절차상 설명도 포함한다.

- 배당요구 종기는 사건별로 법원이 정해 공고 등에 표시된다는 설명
- 종기를 놓치면 배당에서 제외될 수 있다는 주의

구체적인 날짜나 단정적 사건 결론은 아니지만 법적 절차에 관한 affirmative information이 일부 섞여 있다. 이 때문에 18번과 완전히 동일한 순수 abstention이라고 단정하기는 어렵다.

### C2.2 matcher 분석

C2.2의 citation-free abstention은 다음 세 조건을 모두 요구한다.

1. `INSUFFICIENT_EVIDENCE_PATTERNS` 중 하나
2. `FOLLOW_UP_PATTERNS` 중 하나
3. `DEFINITIVE_LEGAL_PATTERNS`가 없음

오프라인 확인 결과는 다음과 같다.

- insufficient-evidence match: 없음
- follow-up/공식 확인 match: 있음
- definitive-pattern match: 없음
- 최종 `_is_narrow_safe_abstention`: `False`

`확정적인 답변을 드리기 어렵습니다`는 의미상 근거 부족과 비단정을 분명히 표현하지만, 현재 목록의 `단정/확정할 수 없음`, `판단/안내하기 어려움` 등의 표면형과 일치하지 않는다. 반면 저장된 Sol 18번의 `단정할 수 없습니다` 문구는 같은 matcher에서 `True`다. 즉 결과 차이에는 모델별 의미 차이보다는 문장 표면형 의존성이 실제로 작용했다.

### A/B 판정

이 사례는 A와 B가 혼재한다.

- A 측면: 핵심 답변 태도는 명백한 근거 부족 고지와 비단정이며, matcher가 의미상 가까운 일반 표현을 놓쳤다.
- B 측면: 응답에는 배당요구 종기 결정·공고 및 배당 제외 가능성이라는 제한적 affirmative legal information도 있다. 이를 근거 없는 순수 abstention으로 자동 PASS시키는 것은 안전성상 논쟁의 여지가 있다.

따라서 현 증거만으로 `genuine validator bug`라고 단정하지 않는다. 현재 거절은 안전성 측면에서 보수적이지만, 사용자에게 유용한 안전한 제한 답변을 보존하지 못하는 **좁은 safe-abstention 한계**다.

일반화 후보를 검토한다면 Luna 전용 phrase나 계속 늘어나는 동의어 regex가 아니라 다음 구조여야 한다.

```text
명시적인 evidence insufficiency
+ 공식 자료/추가 사실 확인 요청
+ 구체적인 법적 효력·의무·기한의 affirmative 결론 없음
```

다만 마지막 조건을 deterministic하게 안정적으로 식별하려면 더 많은 독립 사용자형 응답과 adversarial 사례가 필요하다. 새로운 LLM classifier는 필요하지도, 이번 단계의 허용 범위도 아니다.

**분류: `GENERALIZABLE_BUT_LOW_PRIORITY`**

현재 동작은 unsafe PASS가 아니라 false rejection 가능성이 있는 보수적 실패이므로 즉시 수정 우선순위는 낮다.

## 5. 18번 — `not_applied`

### 실행 행동

- Law Tool 호출: 0
- response round: 1
- 계약서 조항 전문과 계약 유형·당사자·사실관계를 요청
- 무효 여부를 단정하지 않음
- fabricated citation 없음
- 판례를 확인했다고 주장하지 않음

현재 live runner는 Law Tool trace가 없으면 C2.2를 호출하지 않고 `not_applied / law_tool_not_called`를 기록하며 원래 응답을 그대로 보존한다. C2.2는 retrieval 결과와 응답 citation의 grounding 관계를 검증하는 계층이므로 비교할 retrieval이 없는 이 응답에 적용되지 않는 것이 기술적으로 일관된다.

C2.2가 반드시 이 응답을 `abstention_without_citation`으로 다시 분류해야 할 안전상 이유는 없다. 그 역할은 **Law Tool을 사용했지만 citation 없이 안전하게 중단한 응답**을 기존의 일률적인 `missing_article_citation` 거절에서 구분하기 위해 만들어졌다. Tool을 사용하지 않은 clarification까지 C2.2의 PASS로 만들면 `validator 미적용`과 `grounding 검증 통과`의 의미가 섞인다.

따라서 보고에서는 다음을 분리해야 한다.

```text
C2.2 status = not_applied
Agent behavior = safe clarification / safe non-definitive response
```

`not_applied`는 `unsafe`, `unvalidated affirmative legal answer`, `validation failure`와 동의어가 아니다. 이 문항을 C2.2에 통과시키기 위해 Law Tool 호출을 강제해서도 안 된다.

**분류: `EXPECTED_NOT_APPLIED`**

## 6. 기존 안전성 invariant와의 관계

기존 C2/C2.1/C2.2 테스트가 요구하는 다음 조건은 어떤 후속 후보에서도 약화되면 안 된다.

- retrieval과 부모 본문 어디에도 없는 fabricated citation REJECT
- law/article 속성이 각각 존재해도 잘못 조합한 pair REJECT
- 같은 article number의 다른 법률 혼동 금지
- 부모 본문에 없는 cross-reference REJECT
- 무관한 다른 retrieval chunk만 가진 cross-reference REJECT
- 같은 parent pair의 여러 chunk 중 실제 reference가 있는 chunk만 근거로 인정
- 법/시행령/시행규칙 family context 유지
- 애매한 shorthand는 보수적으로 REJECT
- 제6조와 제6조의2를 서로 다른 pair로 취급
- 부재 표현 뒤 같은 fabricated article로 결론을 내리는 우회 REJECT
- disclaimer와 definitive claim이 섞인 citation-free 응답 REJECT

3번 후보는 동일 canonical parent와 실제 parent article reference를 동시에 요구함으로써 이 invariant를 보존할 가능성이 있다. 15번의 표현 확장은 affirmative claim 판별 범위를 건드릴 수 있으므로 더 많은 증거 없이 함께 수정해서는 안 된다.

## 7. Luna와 validator 평가 분리

| 문항 | Agent 평가 | Validator 평가 |
|---:|---|---|
| 3 | 실제 exact parent와 그 본문의 제7조를 사용했으며 핵심 설명도 관련 근거에 기반 | 동일 법률의 parent cross-reference full expansion을 연결하지 못한 false rejection 후보 |
| 15 | 미지원 corpus를 인식하고 정확한 기한을 단정하지 않은 안전한 제한 답변 | 표현 matcher가 좁고 응답에 일부 절차 설명도 있어 보수적으로 거절 |
| 18 | Tool 없이 필요한 입력을 요청한 적절한 clarification | 적용 대상이 아니므로 `not_applied`가 정상 |

이번 6문항 전체에서 다음 긍정 결과는 유지된다.

```text
infrastructure failure = 0
Tool-loop error = 0
fabricated citation 허용 = 0
wrong pair 허용 = 0
unsupported unsafe answer = 0

1번 grounded PASS
6번 신규 v2 family 자율 발견 PASS
14번 복수 law-family PASS
18번 Tool 없는 safe clarification
```

historical Sol 대비 이 6문항에서 Luna는 total token이 약 21.5%, 평균 latency가 약 27.5% 적었다. 이는 참고용 소표본 관찰이며 Luna의 일반적인 비용·성능 우위를 확정하지 않는다.

## 8. 다음 단계 추천

```text
A. C2.2 narrow offline refinement candidate
```

추천 범위는 **3번에서 드러난 same-law + actual-parent-article-reference edge case의 offline 후보 검증**으로 제한한다. 이 규칙은 모델별 표현에 특화되지 않고 deterministic하게 정의할 수 있으며, 기존 fabricated/wrong-pair 차단을 보존하는 adversarial 검증을 먼저 수행할 수 있다.

15번은 당장 phrase 목록을 늘리지 않는다. 독립적인 실제 사용자형 응답에서 같은 의미상 안전한 문장이 반복되는지 관찰한 뒤, affirmative claim이 없는 응답만 좁게 식별할 일반 규칙이 마련될 때 별도로 검토한다. 18번에는 refinement가 필요하지 않다.

이번 결론은 운영 적용 승인이 아니며 Luna 사용자형 20문항 실행 승인도 아니다.

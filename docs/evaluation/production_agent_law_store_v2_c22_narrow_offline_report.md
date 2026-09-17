# C2.2 Narrow Grounding Validator Offline 후보 검증

## 1. 목적과 범위

이번 작업은 기존 C2.1의 두 false rejection 유형만 다루는 evaluation-only offline 후보를 검증했다.

```text
negative_or_unavailable_reference
abstention_without_citation
```

- OpenAI API 호출: 0회
- Vector Store API 호출: 0회
- 사용자형 20문항 재실행: 없음
- 2024/2025 실행: 없음
- 기존 C2/C2.1 코드 변경: 없음
- 운영 Agent·Prompt·Provider·Tool·Retriever·Validator·`.env` 변경: 없음
- 7·8·19번 관련 변경: 없음

새 후보는 `PairAwareGroundingValidatorC22`로 분리했으며 운영 적용 후보가 아니라 다음 integrated evaluation을 위한 offline 후보일 뿐이다.

## 2. C2.2 구조

C2.2는 C2.1의 pair 검증을 대체하지 않는다.

```text
원본 응답
  ↓
명백한 negative/unavailable reference만 탐지
  ↓
해당 article 문자열을 grounding 입력에서 마스킹
  ↓
나머지 전체 응답을 기존 C2.1로 검증
  ↓
C2.1 PASS → PASS
C2.1 missing citation + 좁은 abstention 조건 충족 → abstention PASS
그 외 → 기존 C2.1 REJECT 유지
```

Negative reference는 affirmative evidence로 인정하지 않으며 다음 역할을 갖지 못한다.

- retrieval pair 존재를 증명하지 않음
- active-law context를 새로 만들지 않음
- dependent cross-reference의 parent가 되지 않음
- 다른 citation을 정당화하지 않음

## 3. Deterministic narrow 조건

### 3.1 Negative/unavailable reference

같은 문장 안에서 다음이 모두 만족될 때만 비근거 reference 후보로 분리한다.

1. `검색되지 않음`, `본문/조문/근거가 없음`, `확인하지 못함`, `근거로 사용할 수 없음`처럼 명백한 부재 표현이 존재한다.
2. 동일 article number가 그 문장에 한 번만 등장한다.
3. 같은 문장에 무효·기한·반드시 이행·손해배상 등 명백한 affirmative legal conclusion이 없다.

하나라도 불명확하면 마스킹하지 않고 기존 C2.1 검증에 그대로 맡긴다.

### 3.2 Citation 없는 abstention

다음 세 조건을 모두 요구한다.

1. 근거·자료·판례가 부족하거나 단정할 수 없다는 명백한 표현
2. 계약서 원문, 사실관계, 공식 기관 또는 전문가 확인 같은 후속 확인 안내
3. 구체적인 법적 효력·의무·책임·기한을 확정하는 표현이 없음

“확인이 필요하다”는 disclaimer 하나만으로는 PASS하지 않는다. Definitive legal claim이 함께 있으면 기존 `missing_article_citation` REJECT를 유지한다.

## 4. Positive offline replay

사용한 동결 source:

```text
docs/evaluation/production_agent_law_store_v2_generalization_regression_20.csv
RunID: law-v2-user-regression-baf62a52ffa7
```

### 사용자형 3번

| 항목 | 결과 |
|---|---|
| 기존 C2.1 | REJECT — `ungrounded_law_article_pair` |
| 주근거 | 주택임대차보호법 제6조의3 retrieval pair |
| 주근거 C2.1 검증 | `allowed_retrieval_pair` 유지 |
| 부재 reference | `제6조` |
| C2.2 역할 | `negative_or_unavailable_reference` |
| 처리 | `excluded_from_grounding_not_evidence` |
| C2.2 최종 | PASS, `grounded_answer` |

`제6조`는 “본문이 없어 확정적으로 안내하기 어렵다”는 문장 안에서만 분리됐다. 이를 근거로 인정하거나 제6조의3을 대신하는 retrieval pair로 사용하지 않았다.

### 사용자형 18번

| 항목 | 결과 |
|---|---|
| 기존 C2.1 | REJECT — `missing_article_citation` |
| Retrieval | 질문과 직접 관련 없는 세법 조문 |
| Agent 응답 | 근거 부족, 계약서 원문·사실관계 필요, 판례 조회 불가, 확정 판단 회피 |
| Affirmative legal conclusion | 없음 |
| C2.2 역할 | `abstention_without_citation` |
| C2.2 최종 | PASS |

18번을 grounded answer로 승격한 것이 아니다. Citation 근거가 충분하다고 인정하지도 않았다. 이미 안전하게 중단한 원문 응답을 보존한 것이다.

## 5. Adversarial negative 결과

| 사례 | 기대 | 결과 |
|---|---|---|
| 미검색 fabricated article을 실제 근거로 주장 | REJECT | PASS |
| “검색되지 않음” 뒤 같은 article로 같은 문장 결론 | REJECT | PASS |
| “검색되지 않음” 뒤 같은 article로 다음 문장 결론 | REJECT | PASS |
| 부재 reference 뒤 다른 fabricated citation으로 결론 | REJECT | PASS |
| Citation 없이 “계약은 무효” | REJECT | PASS |
| Disclaimer + definitive 무효 결론 | REJECT | PASS |
| Citation 없이 손해배상 의무 단정 | REJECT | PASS |
| 실제 retrieval pair affirmative citation | PASS | PASS |
| Wrong law/article pair | REJECT | PASS |
| 정상 dependent cross-reference | PASS | PASS |
| 애매한 부정 범위 | 보수적 REJECT | PASS |
| 부재 언급 뒤 `반드시 3개월` 단정 | REJECT | PASS |
| 제6조/제6조의2 별도 pair | PASS | PASS |

표의 결과 열은 “기대 동작과 일치하여 테스트 PASS”라는 뜻이다.

## 6. 기존 C2/C2.1 안전성 회귀

기존 테스트와 C2.2 adversarial 테스트를 함께 실행했다.

```text
tests/test_pair_aware_grounding_validator.py
tests/test_pair_aware_grounding_validator_c21.py
tests/test_pair_aware_grounding_validator_c22.py
tests/test_c21_c3a_offline_replay.py
```

검증된 안전 속성:

- fabricated citation REJECT
- wrong law/article pair REJECT
- 동일 조문번호의 다른 법률 혼동 방지
- parent 본문에 없는 cross-reference REJECT
- 무관한 다른 chunk의 cross-reference 사용 방지
- 동일 parent pair의 multi-chunk 검색 유지
- 법/시행령/시행규칙 family context 유지
- 애매한 축약 보수적 REJECT
- 제6조와 제6조의2 별도 pair 유지
- 기존 정상 cross-reference PASS

최종 결과:

```text
34 passed
안전성 regression = 0
```

## 7. 한계와 위험 관리

C2.2는 LLM 의미 분류기가 아니라 제한된 deterministic 표현 집합을 사용한다. 따라서 다양한 자연어 abstention을 모두 회복시키지 못할 수 있다. 이것은 의도적인 보수성이다.

- 인식하지 못한 표현은 C2.1 REJECT로 남는다.
- 애매한 부정 범위는 면제하지 않는다.
- 단순 disclaimer는 affirmative claim을 숨기지 못한다.
- 이 결과만으로 운영 validator를 교체하지 않는다.
- 다음 단계의 integrated evaluation에서 별도 검증이 필요하다.

## 8. 변경 파일

새 evaluation-only 파일:

```text
ai-server/app/evaluation/pair_aware_grounding_validator_c22.py
ai-server/tests/test_pair_aware_grounding_validator_c22.py
ai-server/scripts/replay_c22_narrow_offline.py
docs/evaluation/production_agent_law_store_v2_c22_narrow_offline_replay.json
docs/evaluation/production_agent_law_store_v2_c22_narrow_offline_report.md
```

기존 C2/C2.1 구현과 테스트는 수정하지 않았다.

## 9. 결론

```text
C2_NARROW_FIX_CANDIDATE_APPROVED
```

승인 범위는 **evaluation-only integrated 실험 후보**까지다. 운영 validator 적용 승인이 아니다.

사용자형 3·18번 false rejection을 해소하면서 기존 fabricated citation, wrong pair, cross-reference 및 모호성 안전성 테스트에 회귀가 없었다. 다음 단계가 승인된다면 C2.2를 A+B+C1 경로와 결합한 제한된 integrated evaluation을 먼저 수행해야 한다.

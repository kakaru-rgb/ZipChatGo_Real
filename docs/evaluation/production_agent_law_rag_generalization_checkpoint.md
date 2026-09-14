# Production Agent Law RAG Generalization Checkpoint

## 1. 목적과 동결 범위

이 문서는 2024년 공인중개사 시험 점수를 더 높이기 위한 개선 계획이 아니다. 지금까지 evaluation-only 실험에서 확인된 기능을 실제 집찾GO 법률 상담에 일반화할 수 있는 후보와 보류 대상으로 나누고, 시험문제 과적합을 막기 위한 architecture freeze 기준을 정의한다.

현재 evaluation 후보로 다음을 동결한다.

- A: law-name metadata filter
- B: exact law/article lookup
- C1: model-query-only semantic search
- C2.1: pair-aware grounding validator
- C3a: explicit required-law coverage gate

C3a는 사용자 질문에 governing law가 명시된 경우에만 적용 가능한 제한적 후보이다. 위 기능은 아직 운영 적용이 확정된 것이 아니며, 확장 Vector Store와 일반 사용자형 regression을 통과해야 한다.

이번 checkpoint에서는 다음을 구현하지 않는다.

- C3b Query-Intent Coverage Gate
- law alias table
- implicit governing-law inference
- claim/evidence semantic verifier
- D Tool-loop 변경
- Tool round-limit 증가
- final-synthesis 강제

OpenAI API와 Vector Store API는 호출하지 않았고, 운영 Agent·Prompt·Provider·Tool·Retriever·Validator·Vector Store 및 기존 실험 결과를 변경하지 않았다.

## 2. 현재까지의 실험 결과

### A. Law-name metadata filter

- 37번에서는 주택임대차보호법 질문에 상가건물 임대차보호법이 rank 1로 나오던 혼입을 제거하고, 주택임대차보호법 제6조의3을 rank 1로 검색해 정답을 회복했다.
- 21번에서도 관련 공인중개사법 family 안에서 필요한 시행령 조문을 확보해 정답을 회복했다.
- 27번은 검색 품질이 개선됐지만 Tool-loop가 종료되지 않았다.
- 9번은 올바른 law family로 제한해도 필요한 시행규칙 제6조를 찾지 못했다.

해석: 사용자가 명시한 법률 family가 있을 때 유사 법률 혼입을 줄이는 효과는 명확하다. 다만 filtering은 exact article miss나 Tool-loop 문제를 해결하지 않는다.

### B. Exact law/article lookup

- 명시적인 `법령명 + 제N조/제N조의M` 조합이 query에 있을 때 metadata pair 검색이 동작했다.
- 6번은 여러 조문을 exact로 확보하고 정답 3을 반환했다.
- 27번은 시행령 제11조를 exact로 확보하고 pre-validation 정답 5를 만들었다.
- 21번은 exact retrieval 성공 후에도 Tool-loop가 계속되는 사례가 있었다.
- 9번처럼 모델이 필요한 조문 pair 자체를 query에 만들지 않으면 exact lookup은 작동하지 않는다.

해석: 명시적인 조문 요청에 대한 deterministic retrieval 경로로 일반화 가능하다. semantic search를 대체하지 않고 miss 시 fallback하는 구조가 전제다.

### C1. Model-query-only semantic search

- 기존에는 긴 시험문제와 model query를 결합한 검색 문자열이 잘리면서 핵심 model query가 검색 입력에서 사라질 수 있었다.
- 9번에서 model query만 사용하자 공인중개사법 시행규칙 제6조가 rank 1로 검색됐다.
- targeted regression에서 21번과 37번의 검색·정답이 유지되거나 개선됐다.
- 6번과 27번의 일부 실행은 외부 503으로 최종 regression 판정이 제한됐지만, 저장된 retrieval에서는 핵심 조문 품질이 악화되지 않았다.

해석: Tool이 만든 정제된 query를 semantic retrieval에 그대로 쓰는 것은 실제 사용자 질문에도 적용 가능한 구조적 개선이다. 다만 model query 품질에 더 의존하므로 확장 corpus에서 독립 regression이 필요하다.

### C2.1. Pair-aware grounding validator

- 기존 C2는 같은 `(law_name, article_number)`의 여러 chunk 중 하나만 검사해 정상 cross-reference를 거절할 수 있었다.
- C2.1은 동일 parent pair의 모든 chunk를 검사하여 9번의 `상법 제614조` cross-reference를 정상 허용했다.
- 법률 family 문맥을 유지해 21번의 축약 표현 `시행령 제31조`를 `공인중개사법 시행령 제31조`로 해석했다.
- fabricated article, 잘못된 law/article pair, 다른 parent에만 존재하는 cross-reference, 애매한 축약은 계속 거절했다.
- 기존 C2 확대 replay에서는 정상 PASS를 REJECT로 바꾼 사례가 없었고, 확인된 REJECT→PASS는 정당한 false-positive recovery였다. C2.1 보강 후에도 기존 C2와 신규 안전성 테스트가 통과했다.

해석: citation을 단순 article number가 아니라 법령·조문 pair와 parent 문맥으로 검증하는 것은 일반적인 법률 답변에 직접 필요한 안전성 기능이다.

### C3a. Explicit required-law coverage gate

- 질문 stem에 governing law가 명시된 6·9·21·27·37번에서 해당 law family가 retrieval에 있어 통과했다.
- 민사집행법과 장사 등에 관한 법률처럼 명시 법률이 검색되지 않은 사례는 `required_law_not_retrieved`로 거절했다.
- 사용자 질문에 법률명이 없는 경우에는 자동으로 governing law를 추론하지 않는다.
- 36번의 human-reviewed annotation replay는 gate 기능 검증용 사후 평가였으며 runtime 규칙으로 사용할 수 없다.

해석: 명시적인 governing law가 있을 때만 사용할 수 있는 좁은 안전장치다. 불완전한 corpus나 법률명 표기 차이 때문에 false block이 발생할 수 있으므로 CORE가 아니라 LIMITED_GUARD이다.

### C3b. Runtime-signal diagnostic

- 36번에서 Agent는 최종 답변 전에 `부동산 실권리자명의 등기에 관한 법률`을 세 차례 명시적으로 검색하려 했지만 해당 family를 한 건도 받지 못했다. 일반화 가능한 query-intent signal은 관찰됐다.
- 35번은 `민법`을 명시했지만 일부 round에서 민법 결과가 있었고, 핵심 조문·판례 부족으로 loop가 지속됐다. family coverage만으로 해결되지 않는다.
- 39번은 `분묘기지권·판례`만 query에 나타나 단일 governing statute를 신뢰성 있게 특정할 수 없었고, Agent는 안전하게 abstain했다.

해석: 신호는 존재하지만 탐색적 query, 다중 법률 질문, 불완전한 corpus에서 false block 위험이 있다. C3b는 구현하지 않고 DEFERRED_EXPERIMENT로 유지한다.

## 3. Production 일반화 관점의 후보 분류

`CORE_GENERALIZABLE`은 운영 적용 완료를 뜻하지 않는다. 실제 사용자형 regression과 새 corpus 검증을 진행할 우선 후보라는 의미다.

| 기능 | 최종 등급 | 실제 사용자 질문에서의 필요성 | 시험 의존성 | False-positive / false-block 위험 | Agent blast radius | 구현 복잡도 | 현재 증거 수준 |
|---|---|---|---|---|---|---|---|
| A law-name filter | **CORE_GENERALIZABLE** | 명시 법률 질문에서 유사 법률 혼입 방지 | 낮음 | 잘못된 hard filter 시 관련 법률 제거 가능. 명시 법률 우선 및 semantic fallback 필요 | 법률 Tool 내부로 한정 가능 | 중간 | 4문항 targeted; 21·37 회복, 27 retrieval 개선 |
| B exact lookup | **CORE_GENERALIZABLE** | 특정 조문 질문과 모델의 명시 조문 검색에 직접 필요 | 낮음 | 잘못된 pair parsing 위험. exact miss 시 기존 semantic fallback으로 완화 | 법률 Tool 내부 | 중간 | targeted exact hit 및 정답/근거 회복 확인 |
| C1 clean semantic query | **CORE_GENERALIZABLE** | 긴 사용자 질문이 검색 의도를 희석하는 문제 방지 | 낮음 | 불완전한 model query가 사용자 문맥을 잃을 수 있음 | 모든 법률 semantic 검색 | 낮음~중간 | 9번 핵심 조문 rank 1, targeted 비악화 관찰 |
| C2.1 pair-aware validator | **CORE_GENERALIZABLE** | 실제 법률 답변의 citation pair와 cross-reference 검증 | 낮음 | parser가 미지원 표현을 거절할 수 있음. 보수적 실패가 기본 | 법률 최종 답변 validation | 중간~높음 | offline replay, negative tests, 9·21 false rejection 회복 |
| C3a explicit required-law coverage | **LIMITED_GUARD** | 사용자가 명시한 판단 기준 법률의 미검색 감지 | 낮음(명시 법률만) | corpus 누락·명칭 변형에서 false block 가능 | 명시 법률 질문에만 제한 | 중간 | targeted offline replay만 존재 |
| C3b query-intent coverage | **DEFERRED_EXPERIMENT** | 법률명 없는 질문의 unsupported-core answer 감지 가능성 | 중간 | 탐색 query와 governing law를 혼동하거나 다중 법률 질문을 차단할 위험 | 법률 Tool loop와 최종 답변 사이 | 중간~높음 | 35·36·39 diagnostic 세 사례뿐 |
| Claim/evidence verifier | **DEFERRED_EXPERIMENT** | citation이 아니라 핵심 주장 전체의 근거 검증 가능 | 높음 | 의미 판정 오류, 비용·지연, 이중 LLM 판단 위험 | 법률 답변 전체 | 높음 | 구현·독립 증거 없음 |
| D Tool-loop 변경 | **DEFERRED_EXPERIMENT** | 반복 검색과 종료 실패 완화 가능 | 중간 | 매물·지도·POI 등 모든 Tool 행동에 영향 가능 | Agent 전체 | 높음 | 27·35 등 일부 사례만 존재 |

## 4. 시험문제 과적합 방지 원칙

앞으로의 법률 RAG 개선과 평가에는 다음 원칙을 적용한다.

1. 문항번호를 runtime logic에 사용하지 않는다.
2. 공식정답을 query, routing, validation, required-law detection에 사용하지 않는다.
3. Human-reviewed annotation을 Agent runtime이나 retrieval에 사용하지 않는다.
4. `특정 시험문구 → 특정 법률` mapping을 만들지 않는다.
5. Vector Store에 없는 법률을 Harness가 추론해 억지로 검색시키지 않는다.
6. 검색 실패와 근거 부족을 정상적인 시스템 상태로 허용한다.
7. 목표는 retrieval success 100%가 아니라, 충분한 근거가 있을 때 답하고 부족할 때 과도하게 단정하지 않는 것이다.
8. 2024년 특정 문항 하나를 해결하기 위한 일반 규칙을 추가하지 않는다.
9. 실제 사용자형 질문이나 여러 독립 사례에서 같은 실패가 반복될 때만 새 후보를 검토한다.
10. Corpus coverage와 Retriever/Agent architecture 문제를 분리한다.
11. 평가 Harness는 Agent의 query나 답을 보정하지 않고 관찰·분류·채점만 한다.
12. 실패한 benchmark를 근거로 운영 Prompt나 Tool loop를 곧바로 변경하지 않는다.

핵심 구분은 다음과 같다.

```text
Corpus에 필요한 법률이 없음
    ≠ Retriever 오류

Corpus에 문서가 있지만 검색되지 않음
    = Retrieval/filter/query/ranking 진단 대상

검색 근거가 충분하지만 답이 틀림
    = Reasoning/grounding 진단 대상

Retriever가 문서를 못 찾음
    ≠ Harness가 정답 법률을 새로 추론해야 함
```

## 5. Corpus coverage와 RAG architecture의 분리

현재 Vector Store는 전체 법률 corpus가 아니다. 따라서 35·36·39번을 더 맞히기 위한 특별 Harness 규칙을 만들지 않는다.

- 35번: 민법 family 일부는 있으나 필요한 공유 조문과 판례 coverage/retrieval이 불충분했다.
- 36번: Agent가 요구한 부동산 실권리자명의 등기에 관한 법률 family가 검색 결과에 없었다.
- 39번: 분묘기지권 판례 근거가 corpus 검색 결과에 없었고 Agent가 abstain했다.

이 사례들은 architecture의 관찰 지점이지 시험 답을 맞히기 위한 예외 규칙의 근거가 아니다. 확장 법률 Markdown과 새 Vector Store 준비는 별도 corpus 작업에서 수행하며, 이 evaluation 트랙에서는 업로드·삭제·재구축·특별 routing을 하지 않는다.

## 6. 보류 기능과 이유

### C3b와 law alias table

36번에서 유망한 runtime signal이 관찰됐지만 세 사례만으로 production hard gate를 정당화하기 어렵다. 특히 탐색적으로 언급한 법률, 중간 round의 일시적 miss, 다중 법률 질문을 governing-law failure로 오인할 수 있다. Alias table도 단순 표기 정규화를 넘어 implicit law inference로 확장될 위험이 있어 보류한다.

### Implicit governing-law inference와 claim verifier

법률명이 없는 사실관계에서 정답 법률을 추론하는 기능은 평가 Harness가 별도 시험 Agent로 변질될 위험이 가장 크다. Claim verifier 역시 별도 모델 호출, 비용, latency, 의미 판정 오류와 새로운 안전성 의존성을 만든다. 필요 가능성만 기록하고 승인 전에는 구현하지 않는다.

### D Tool-loop 및 round-limit 변경

현재 27·35번 등에서 loop 문제가 있었지만 Provider 변경은 법률 Tool뿐 아니라 매물검색·지도·POI Tool에도 영향을 줄 수 있다. 확장 corpus에서도 충분한 evidence를 확보한 뒤 반복 호출이 여러 독립 사용자형 사례에서 재현될 때만 다시 검토한다. 2024년 특정 문항을 종료시키기 위해 round limit을 늘리거나 final synthesis를 강제하지 않는다.

## 7. 확장 Vector Store 이후 평가 절차

확장 Store가 준비되면 RAG를 처음부터 재설계하지 않고 다음 순서로 평가한다.

1. 새 Store ID, corpus manifest, 문서 수, 생성 시점과 metadata schema를 별도 버전으로 동결한다.
2. 기존 Store와 결과를 섞지 않고 새 RunID와 corpus version을 모든 결과에 기록한다.
3. 새 corpus를 기준으로 법령 family·하위법령·조문 metadata coverage를 검사한다.
4. 과거 `in_scope/partial_scope/out_of_scope` label을 재사용하지 않고 새 manifest 기준으로 다시 분류한다.
5. evaluation-only에서 `A + B + C1 + C2.1`을 기본 후보로 연결한다.
6. C3a는 질문에 governing law가 명시되고 canonical family match가 신뢰할 수 있을 때만 별도 제한 실험한다.
7. Filter, exact pair, semantic fallback, citation validator를 각각 단위·offline regression으로 먼저 검증한다.
8. 2024 development benchmark와 실제 사용자형 regression을 함께 실행한다. 시험 점수만으로 채택하지 않는다.
9. 지원 질문의 정확성뿐 아니라 unsupported 질문의 abstention, fabricated citation, false rejection을 함께 측정한다.
10. 법률 Tool 외 매물·지도·POI·일반 대화 경로가 변하지 않았는지 회귀 확인한다.
11. 충분한 근거 후에도 Tool-loop가 반복되는 독립 사례가 계속될 때만 D를 별도 실험한다.
12. Architecture와 threshold를 동결한 후에만 2025 hold-out을 한 번 평가한다.

예를 들어 기존 Store에 민사집행법이 없어 unsupported였더라도 새 Store에 포함되면 새 corpus 기준으로 supported 여부를 다시 판정한다. 과거 label이나 실패유형을 그대로 복사하지 않는다.

## 8. 실제 사용자형 Generalization Regression 계획

시험문제와 별도로 다음 그룹을 구성한다. 이번 단계에서는 질문을 이용한 튜닝이나 재실행을 하지 않는다.

| Regression group | 확인 목적 | 주요 관찰 지표 |
|---|---|---|
| 특정 법률·조문 직접 질문 | A/B의 exact/filter 동작 | 정확 pair hit, fallback, citation pair |
| 법률명 없는 사실관계 질문 | 과도한 inference 방지 | Tool routing, 근거 부족 인식, abstention |
| 주택임대차 질문 | 유사 상가법 혼입 방지 | law-family precision, 핵심 조문 retrieval |
| 중개업 관련 질문 | 법·시행령·시행규칙 family 처리 | 하위법령 검색, 축약 citation 검증 |
| 부동산 거래신고 질문 | 유사 법령 및 하위법령 처리 | law filter, exact 조문, ranking |
| 여러 법률이 동시에 관련된 질문 | hard filter의 과도한 제거 방지 | 복수 family recall, false block |
| Store 미지원 법률 질문 | 안전한 미지원 처리 | unsupported detection, abstention, citation hallucination |
| 근거 부족 질문 | validator의 안전성 | definitive answer 억제, rejection reason |
| 비법률 일반 부동산 질문 | 불필요한 법률 Tool 호출 방지 | routing precision, 법률 Tool 오호출률 |

각 그룹에는 독립적인 여러 사례를 두고 다음을 분리 측정한다.

- Tool routing 성공 여부
- 모델 query와 실제 semantic query
- law-name filter 적용 및 fallback
- exact lookup hit/miss
- Top-K law/article coverage
- citation validation PASS/REJECT와 false rejection
- 충분한 근거가 없는 경우의 abstention
- latency, Tool 호출 횟수, response rounds
- 다른 Agent 기능의 regression 여부

새 규칙은 단일 사례가 아니라 여러 사용자형 사례에서 같은 실패가 재현될 때만 검토한다.

## 9. 원래 AI 챗봇으로의 통합 절차

최종 목표는 시험용 Agent가 아니라 기존 집찾GO Agent의 법률 subsystem을 개선하는 것이다.

```text
기존 AI Agent
├─ 지도
├─ 매물검색
├─ 관심매물
├─ POI
├─ 일반 대화
└─ search_real_estate_law
   └─ 일반화된 Law RAG
      ├─ A: law-name filtering
      ├─ B: exact law/article lookup
      ├─ C1: clean semantic query
      └─ C2.1: grounded pair-aware citation validation
         └─ 필요 시 제한적 C3a
```

통합은 다음 원칙으로 진행한다.

1. 확장 Store에서 evaluation-only 후보를 먼저 검증한다.
2. 운영 Prompt, Agent의 전체 Tool 선택 방식, 다른 Tool handler는 유지한다.
3. 변경 범위를 가능한 한 `search_real_estate_law` 내부 retrieval/validation subsystem으로 제한한다.
4. A, B, C1, C2.1을 독립적으로 켜고 끌 수 있는 작은 변경 단위로 검토한다.
5. 기존 semantic search fallback을 유지해 exact/filter miss가 곧 전체 실패가 되지 않게 한다.
6. 일반 사용자형 shadow/regression 결과를 baseline과 비교한다.
7. 법률 답변 안전성과 함께 지도·매물·POI Tool routing 비회귀를 확인한다.
8. 승인 후 제한적 적용과 rollback 가능성을 확보하고 운영 통합한다.

## 10. 2024와 2025 benchmark의 역할

- **2024:** 이미 반복 분석된 development/regression benchmark이다. Retrieval 변화와 알려진 실패가 재발하는지 확인하는 용도로만 사용한다. 점수를 올리기 위해 architecture를 계속 추가하지 않는다.
- **2025:** 최종 후보, 확장 Store, scope classification, parser와 평가 기준을 모두 동결한 뒤 사용하는 hold-out이다. 2025 결과를 본 뒤 같은 hold-out에 맞춰 다시 튜닝하지 않는다.

2025 평가는 다음 조건이 모두 충족된 뒤 한 번 수행한다.

1. 확장 Store manifest와 metadata schema 동결
2. A+B+C1+C2.1 및 제한적 C3a의 적용 여부 확정
3. 실제 사용자형 regression 통과
4. 안전성·abstention·false rejection 기준 확정
5. Tool-loop 변경 여부를 포함한 architecture freeze
6. 운영 통합 전 비교 계획과 결과 파일명 확정

이번 checkpoint에서는 2025를 실행하지 않는다.

## 11. Architecture freeze 결론

현재 production 일반화 후보는 다음과 같다.

```text
CORE_GENERALIZABLE
  A law-name filter
  B exact law/article lookup
  C1 model-query-only semantic search
  C2.1 pair-aware grounding validator

LIMITED_GUARD
  C3a explicit required-law coverage gate

DEFERRED_EXPERIMENT
  C3b query-intent coverage
  law alias / implicit governing-law inference
  claim/evidence verifier
  D Tool-loop 및 round-limit/final-synthesis 변경
```

다음 기술적 checkpoint는 확장 Vector Store가 준비된 뒤의 corpus 재분류와 일반 사용자형 regression이다. 그 전에는 35·36·39번 또는 2024 점수를 이유로 새로운 Harness 기능을 추가하지 않는다.

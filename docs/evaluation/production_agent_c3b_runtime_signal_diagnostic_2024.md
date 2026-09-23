# C3b runtime-signal diagnostic (offline only)

## 1. 범위와 분석 원칙

- 입력: 동결된 `production_agent_passthrough_integrated_a_b_c1_c2_2024_q6_9_21_27_37_30_35_36_39_40_gpt-5.6-sol.csv`
- 대상: 35, 36, 39번
- OpenAI API 호출: 0회
- Vector Store API 호출: 0회
- 운영 코드 및 A/B/C1/C2/C2.1/C3a 변경: 없음
- 문항번호, 공식정답, 최종 답변은 governing-law 신호 탐지에 사용하지 않았다.
- 36번의 human-reviewed annotation은 trace 분석을 끝낸 뒤 비교용 reference label로만 사용했다.

이 진단에서 runtime signal은 **최종 답변 전에 모델이 스스로 만든 `search_real_estate_law` query**만을 우선 근거로 삼는다. 검색 결과가 특정 법률을 필요로 한다고 역으로 추론하거나, 답변 내용을 보고 query 의도를 재작성하지 않았다.

## 2. 요약 결론

| 문항 | 분류 | query 단계의 법률 신호 | 요청 family 검색 여부 | terminal 상태 |
|---|---|---|---|---|
| 35 | A. `explicit_runtime_signal` | `민법` | 일부 round에서 검색됨. 핵심 제263·264·265조 exact hit는 없음 | 4 response rounds 후 Tool-loop error |
| 36 | A. `explicit_runtime_signal` | `부동산 실권리자명의 등기에 관한 법률`을 1~3회 query에서 명시 | 해당 family 0건 | 다른 법률 근거로 답 5 확정, validation PASS |
| 39 | B. `weak_or_ambiguous_runtime_signal` | `분묘기지권`, `판례`만 존재. 단일 법률 family는 없음 | 비교할 required family를 신뢰성 있게 특정할 수 없음 | 근거 부족을 명시하고 abstain |

36번에는 C3b가 사용할 수 있는 강한 일반화 가능 신호가 이미 존재한다. 다만 35번은 `민법` 신호가 있어도 family가 일부 검색됐기 때문에 단순 family coverage gate로는 핵심 조문·판례 부족이나 loop 문제를 해결하지 못한다. 39번에는 법률명을 새로 추론하지 않는 한 C3b를 적용할 수 없다.

## 3. 문항별 시간순 trace

### 3.1 35번 — 공유물 사용·관리·처분 및 판례

사용자 stem에는 특정 법률명이 없고 공유관계 및 판례 판단을 요구한다.

| Tool 순서 | Response round | Model-generated query의 핵심 | 적용 law names | 검색 결과 law/article | Exact lookup |
|---:|---:|---|---|---|---|
| 1 | 1 | `민법 공유물 사용 수익 ... 판례` | 민법 | 민법 제647·646·619·623조 | 미시도 |
| 2 | 2 | `민법 제263조 ... 제264조 ... 제265조` | 없음 | 집합건물법 시행령 제12조, 부동산등기법 제3조, 집합건물법 제5조 | 3 pair 탐지, hit 0, semantic fallback |
| 3 | 3 | `공유자는 ... 민법 공유물의 사용 수익` | 민법 | 민법 제627·647·623·646·632조 | 미시도 |
| 4 | 3 | `공유자는 ... 처분하거나 변경하지 못한다 민법` | 민법 | 민법 제619·541조 | 미시도 |
| 5 | 3 | `공유물의 관리 ... 지분 과반수 ... 민법` | 민법 | 민법 제619·595·626·635·634조 | 미시도 |
| 6 | 3 | `공유물 소수지분권자 독점점유 ... 판례` | 없음 | 집합건물법 제46조 | 미시도 |
| 7 | 4 | `공유물의 처분 변경 관리 ... 민법 물권 공유` | 민법 | 민법 제619조 | 미시도 |

- PreValidationRawResponse: 없음
- terminal: `OpenAIToolLoopError: OpenAI tool call limit exceeded`
- ResponseRound수: 4, 법률 Tool 호출: 7회

판정:

- 첫 query부터 `민법`이 명시되므로 **A. explicit_runtime_signal**이다.
- 특히 두 번째 query는 모델이 답변 전에 민법 제263·264·265조를 구체적으로 요구했다. 그러나 exact hit가 없었고, 그 round의 semantic 결과에는 민법 family가 한 건도 없었다.
- 반면 전체 실행 기준으로는 다른 round에서 민법 결과가 여러 번 존재한다. 따라서 단순한 “민법 family가 한 번이라도 검색됐는가” 검사는 PASS가 된다.
- 계속 검색한 직접적인 trace상 이유는 governing family 자체를 전혀 못 찾은 것이 아니라, 필요한 공유 조문과 판례를 확보하지 못하고 유사하지만 불충분한 민법 조문을 반복해서 받은 데 있다.
- C3b family gate는 35번 loop를 해결하는 장치가 아니다. 개별 round만 보고 차단하면 일시적 semantic miss를 과대평가할 위험도 있다.

### 3.2 36번 — 3자간 등기명의신탁과 임대차

사용자 stem에는 법률명이 없고 명의신탁 사실관계만 제시된다.

| Tool 순서 | Response round | Model-generated query의 핵심 | 적용 law names | 검색 결과 law/article | Exact lookup |
|---:|---:|---|---|---|---|
| 1 | 1 | `부동산 실권리자명의 등기에 관한 법률 3자간 등기명의신탁 ...` | 없음 | 부동산등기법 제3·81·29조, 부동산등기규칙 제52조 | 미시도 |
| 2 | 2 | `부동산 실권리자명의 등기에 관한 법률 제4조 ...` | 없음 | 부동산등기법 제23·29조, 거래신고법 시행규칙 제4조, 거래신고법 제28조, 등기규칙 제45조 | pair 미탐지, semantic fallback |
| 3 | 2 | `부동산 실권리자명의 등기에 관한 법률 계약명의신탁 ...` | 없음 | 부동산등기법 제99·37·3·52조, 등기규칙 제124조 | 미시도 |
| 4 | 2 | `주택임대차보호법 ... 대항력 ...` | 주택임대차보호법 | 주택임대차보호법 제3조·제3조의3 | 미시도 |
| 5 | 3 | `명의신탁약정은 무효 ... 제3자에게 대항하지 못한다` | 없음 | 부동산등기법 제87조의2·78조, 등기규칙 제139조의2·163조의3·139조의4 | 미시도 |

- PreValidationRawResponse: 답 5를 확정하고 명의신탁의 무효 및 제3자 보호를 단정
- terminal: 최종 답변 생성, C2 validation PASS
- ResponseRound수: 4, 법률 Tool 호출: 5회

판정:

- 첫 번째 검색부터 정식 법률명 `부동산 실권리자명의 등기에 관한 법률`이 등장했고, 답변 생성 전 세 차례 반복됐다. 따라서 **A. explicit_runtime_signal**이다.
- 이 법률명은 최종 답변을 본 뒤 생긴 것이 아니라 response round 1의 최초 retrieval 요청에 이미 있었다.
- 모델이 요구한 law family와 실제 retrieval family는 명확히 불일치한다. 해당 법률 family는 세 번의 검색에서 모두 0건이다.
- 두 번째 query는 제4조까지 명시했지만 exact parser는 pair를 탐지하지 않았다. 코드상 exact parser가 `LAW_TARGETS`에 등록된 법령명만 탐지하므로, 동결 corpus 대상 밖의 이 법률명은 pair 후보가 되지 않았다.
- 이후 주택임대차보호법 제3조는 정상 검색됐지만 이는 임차인의 대항력에 관한 부분 근거일 뿐 명의신탁의 무효·제3자 보호라는 핵심 판단의 governing law coverage를 대체하지 못한다.
- 그럼에도 모델은 내부 지식과 부분 근거를 결합해 definitive answer까지 진행했고, 기존 citation validator는 실제 인용한 주택임대차보호법 제3조 pair만 검증했기 때문에 PASS했다.

Trace만 독립적으로 분석한 뒤 human-reviewed annotation과 비교하면, runtime query의 정식 법률명은 annotation인 `부동산 실권리자명의 등기에 관한 법률`과 정확히 일치한다. 이 일치는 annotation이나 공식정답 없이도 query 시점에 판정 가능하다.

### 3.3 39번 — 분묘기지권 판례

사용자 stem에는 특정 법률명이 없고 분묘기지권 판례 판단을 요구한다.

| Tool 순서 | Response round | Model-generated query의 핵심 | 적용 law names | 검색 결과 law/article | Exact lookup |
|---:|---:|---|---|---|---|
| 1 | 1 | `분묘기지권 시효취득 ... 판례` | 없음 | 부동산등기법 제69조 | 미시도 |
| 2 | 2 | `분묘기지권 지료 ... 판례` | 없음 | 공인중개사법 시행령 제26조, 민법 제578조, 거래신고법 시행령 제6조 | 미시도 |
| 3 | 2 | `분묘기지권 존속기간 ... 판례` | 없음 | 집합건물법 시행령 제5조 | 미시도 |
| 4 | 2 | `분묘기지권 등기 없이 ... 판례` | 없음 | 부동산등기규칙 제93·161조, 부동산등기법 제58·53·52조 | 미시도 |

- PreValidationRawResponse: 검색된 조문은 핵심 판례 쟁점을 판단할 근거가 아니므로 정답 번호를 확정할 수 없다고 설명
- terminal: 안전한 abstention, C2 validation PASS
- ResponseRound수: 3, 법률 Tool 호출: 4회

판정:

- query에는 `분묘기지권`과 `판례`라는 강한 쟁점 신호는 있지만 하나의 정식 법률명이나 신뢰할 수 있는 법률 약칭은 없다. 따라서 **B. weak_or_ambiguous_runtime_signal**이다.
- 분묘기지권의 핵심 근거는 판례에 의존하므로, query만으로 단일 statute family를 만들어 내는 것은 C3b의 허용 범위를 벗어난다.
- 실제 검색 결과가 쟁점과 어긋난다는 사실을 모델이 인식했고, “판례 근거로 확정하기 어렵다”고 멈췄다. 36번과 달리 불충분한 검색 결과를 내부 지식으로 메워 definitive answer를 만들지 않았다.

## 4. Alias normalization 가능성

일반적으로 통용되는 법률 약칭을 canonical family로 정규화하는 것은 가능하다.

```text
부동산실명법
부동산 실명법
부동산 실권리자명의 등기에 관한 법률
    → 부동산 실권리자명의 등기에 관한 법률
```

이 테이블은 공식 법률명과 일반 약칭 사이의 전역 정규화 자료여야 하며 문항번호, 문제 문구, 공식정답과 연결되어서는 안 된다. 이번 저장 trace의 36번은 이미 정식 법률명을 사용했으므로 alias가 없어도 동일한 A 판정이 가능하다. 35번의 `민법`도 정식 법률명이다. 39번은 약칭 문제가 아니라 법률 family 신호 자체가 없으므로 alias 정규화로 해결되지 않는다.

## 5. 일반화 가능성과 false-block 위험

### 일반화 가능성

- 실제 사용자 질문에서도 법률명을 모르고 사실관계만 설명하는 경우가 흔하다.
- 현재 trace는 운영 Agent가 그런 질문에서 스스로 법률명을 query에 넣을 수 있음을 보여준다.
- 이 값은 기존 Agent가 원래 생성한 정보이므로 별도 governing-law 추론기나 시험용 규칙이 필요 없다.
- 36번의 판단은 공식정답과 human annotation을 보지 않고도 `query family 요청 → retrieval family 0건`으로 성립한다.

### false-block 위험

- 모델이 탐색 목적으로 여러 법률을 번갈아 query할 수 있다. 모든 일회성 family miss를 즉시 차단하면 과도한 거절이 발생할 수 있다.
- 35번처럼 한 round에서는 명시 family가 0건이어도 다른 round에서는 같은 family가 검색될 수 있다.
- 다중 법률 쟁점에서는 하나의 family만 검색되지 않았다고 전체 답변을 막으면 부분적으로 충분한 답변까지 차단할 수 있다.
- 법률 약칭이 애매하거나 여러 canonical law에 대응할 수 있으면 hard gate에 사용해서는 안 된다.

따라서 향후 후보는 “명시적이고 비모호한 law family query가 있었고, definitive legal answer 직전까지 그 family의 retrieval이 전체 실행에서 한 건도 없었던 경우”처럼 보수적으로 제한하는 편이 안전하다. 이것도 이번 진단의 제안일 뿐 구현된 규칙이 아니다.

## 6. 세 사례의 차이

- **36번이 unsupported answer까지 간 이유:** Agent는 필요한 법률을 정확히 이름 붙였지만 해당 family를 한 건도 받지 못했다. 이후 검색된 주택임대차보호법이라는 부분 근거만 citation 검증을 통과했고, 검색되지 않은 명의신탁 핵심 법리를 내부 판단으로 보완하여 답을 확정했다.
- **39번이 안전하게 멈춘 이유:** 검색된 조문이 판례 쟁점을 뒷받침하지 않는다는 사실을 최종 답변에서 명시적으로 인식했다. 신뢰할 수 있는 법률 family runtime signal은 없었지만 기존 Agent의 abstention 행동이 작동했다.
- **35번이 계속 검색한 이유:** `민법`과 제263·264·265조까지 특정했으나 exact hit가 없었고 semantic 검색도 필요한 공유 조문·판례 대신 주변 조문을 반환했다. 모델은 부족한 근거를 보완하려고 query를 세분화하다 4-round 한도에 도달했다.

## 7. C3b 후보 평가

진단 결과, 36번 유형에는 다음의 좁은 **C3b Query-Intent Coverage Gate** 후보가 성립한다.

```text
모델이 Tool query에서 명시적·비모호한 law family를 요청
    ↓
동일 실행의 retrieval 결과에 그 family가 끝까지 0건
    ↓
definitive legal answer 전에 required-law retrieval miss 신호
```

- 36번: 이 조건에 명확히 해당한다.
- 35번: 민법 family가 실제 검색됐으므로 family-level C3b로 차단하지 않는다. 핵심 조문·판례 부족은 별도 문제다.
- 39번: explicit family가 없어 C3b를 적용하지 않는다. 더 강한 claim/evidence verifier가 필요할 가능성만 기록한다.

결론적으로 A 신호는 명확하고 실제 질문에도 일반화될 가능성이 있다. 따라서 C3b를 향후 작은 evaluation-only 후보로 검토할 수 있다. **이번 단계에서는 C3b, alias table, claim verifier를 구현하지 않았다.**

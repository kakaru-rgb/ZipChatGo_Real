# A+B Grounding Validation Forensic 분석 — 9번·27번

## 분석 범위와 결론

- 분석 대상: A+B valid run `law-exact-2026-09-11T153309_0900-9b9bde3b`의 9번, 27번
- 사용 자료: 저장된 `PreValidationRawResponse`, `법률ToolTrace`, `ExactLookupTrace`와 현재 validator 코드
- OpenAI API 및 Vector Store API 호출: 없음
- 운영 코드·설정·기존 결과 파일 변경: 없음

최종 판정:

| 문항 | reject를 직접 일으킨 조문 | 직접 원인 분류 | 핵심 답변 grounding | 최종 판정 |
|---|---|---|---|---|
| 9 | `제614조` | B | 핵심 오답 선택지 판단 근거인 시행규칙 제6조가 검색되지 않음 | `mixed` |
| 27 | `제9조` | B | 시행령 제11조 검색 본문에 ㄱ·ㄴ·ㄷ의 근거가 모두 존재 | `validator false positive` |

## Validator의 실제 검증 방식

운영 Provider의 `_ground_law_response()`와 evaluation-only `analyze_validation()`은 같은 핵심 조건을 사용한다.

1. 모든 retrieval result의 `law_name`을 `allowed_law_names` 집합으로 만든다.
2. 모든 retrieval result의 `article_number`를 `allowed_articles` 집합으로 만든다.
3. 응답 전체에서 정규식 `제\s*\d+조(?:의\s*\d+)?`와 일치하는 **모든 조문번호**를 수집해 `cited_articles` 집합으로 만든다.
4. `cited_articles ⊆ allowed_articles`가 아니면 `ungrounded_article_citation`으로 거절한다.
5. 응답에 `allowed_law_names` 중 하나라도 문자열로 나타나는지만 별도로 검사한다.

따라서 현재 validator는 `(law_name, article_number)` pair 단위로 검증하지 않는다. 법령명과 조문번호가 서로 독립된 두 집합/조건으로 취급된다. 조문 주변의 법령명, 인용의 주근거/교차참조 역할, 검색 본문에 cross-reference가 실제 존재하는지도 판단하지 않는다.

이 방식의 결과:

- 올바른 검색 문서 본문에 쓰인 cross-reference를 답변이 그대로 언급해도, 그 번호가 retrieval result의 최상위 `article_number`가 아니면 거절될 수 있다.
- 반대로 응답의 법령명 하나와 조문번호 하나가 각각 허용 집합에만 존재하면, 둘이 잘못 조합된 citation이어도 통과할 가능성이 있다.
- 핵심 주장에 필요한 조문이 검색되지 않았더라도 응답에 포함된 다른 조문번호들이 허용 집합에 속하면 그 grounding 부족을 검출하지 못할 수 있다.

## 9번 Forensic

### PreValidation 답변과 검색 집합

- PreValidation 답: 2번
- 공식정답: 2번
- 응답에서 parser가 수집한 조문: `제10조`, `제4조`, `제614조`
- retrieval metadata의 허용 조문: `제4조`, `제10조`, `제13조`, `제18조`, `제38조`, `제51조`
- 차집합: `제614조`
- 검색된 고유 법령/조문:
  - 공인중개사법 제10조, 제38조, 제51조
  - 공인중개사법 시행령 제13조, 제18조
  - 공인중개사법 시행규칙 제4조

### 정확한 reject 원인

응답은 선택지 3의 근거를 설명하면서 다음을 언급한다.

> 「상법」 제614조에 따른 영업소 등기

`제614조`는 retrieval metadata의 최상위 `article_number`에는 없으므로 `cited_articles.issubset(allowed_articles)`가 실패했다. 그러나 이 문구는 검색된 **공인중개사법 시행규칙 제4조 본문 안에 실제로 존재하는 상법 cross-reference**다.

따라서 reject를 직접 발생시킨 reference는 분류 **B**다. 법령명이 없는 bare reference는 아니므로 C가 아니며, 단순 정규화 오류도 아니다.

### 핵심 판단의 grounding 충분성

정답인 선택지 2는 `등록관청 → 다음 달 10일까지 → 공인중개사협회에 통보`의 주체·상대방을 판단해야 한다. 저장된 모든 검색 결과 본문을 검사했으나 다음 표현은 발견되지 않았다.

- `다음 달 10일`
- 해당 통보 규칙을 규정하는 공인중개사법 시행규칙 제6조

즉 답 번호는 맞았지만 **핵심 정답 판단은 저장된 retrieval 결과로 충분히 뒷받침되지 않았다.** 한편 reject를 실제 유발한 것은 핵심 근거 누락이 아니라, 올바르게 검색된 제4조 본문의 상법 제614조 cross-reference였다.

최종 판정은 `mixed`다.

- 실제 grounding 문제: 핵심 근거인 시행규칙 제6조 미검색
- validator false-positive 요소: 검색 본문에 존재하는 상법 제614조 cross-reference를 독립 citation으로 거절

## 27번 Forensic

### PreValidation 답변과 검색 집합

- PreValidation 답: 5번
- 공식정답: 5번
- 응답에서 parser가 수집한 조문: `제11조`, `제9조`
- retrieval metadata의 허용 조문: `제6조`, `제11조`, `제12조`, `제14조`
- 차집합: `제9조`
- 핵심 exact hit: 부동산 거래신고 등에 관한 법률 시행령 제11조

### 정확한 reject 원인

응답은 ㄱ을 설명하면서 다음과 같이 썼다.

> 법 제9조에 따라 외국인 등이 토지취득 허가를 받은 경우

`제9조`는 retrieval metadata의 최상위 `article_number`가 아니어서 부분집합 검사가 실패했다. 그러나 exact 검색된 시행령 제11조 본문은 제3항제15호에서 **`법 제9조에 따라 외국인등이 토지취득의 허가를 받은 경우`**라고 직접 cross-reference한다. 저장된 semantic 결과의 시행령 제6조 본문에도 제9조 언급이 존재한다.

따라서 reject를 일으킨 reference는 분류 **B**다. 이는 검색 문서에 없는 새 법적 근거를 모델이 만든 사례가 아니다.

### 핵심 판단의 grounding 충분성

Exact lookup으로 확보한 시행령 제11조의 저장 본문에 세 판단 근거가 모두 존재한다.

- ㄱ: 제3항제15호 — 외국인 등이 법 제9조에 따라 토지취득 허가를 받은 경우
- ㄴ: 제3항제1호 — 공익사업법에 따른 토지의 협의취득·사용 또는 환매
- ㄷ: 제3항제14호 — 한국농어촌공사가 농지를 매매·교환·분할하는 경우

따라서 핵심 결론 5번은 검색 결과에 충분히 grounded 되어 있다. 제9조는 독립 근거라기보다 검색된 시행령 제11조가 직접 포함하는 종속 cross-reference다.

최종 판정은 `validator false positive`다.

## 분류 A–D 대조

| 분류 | 9번 | 27번 | 설명 |
|---|---|---|---|
| A. 검색되지 않은 독립 근거 | 핵심 시행규칙 제6조 관점에서는 해당하지만, 직접 reject reference는 아님 | 해당 없음 | 9번의 실제 grounding 부족을 별도로 설명하는 요소 |
| B. 검색 본문 안의 cross-reference 오인 | `상법 제614조` | `법 제9조` | 두 reject의 직접 원인 |
| C. bare article 잘못 매칭 | 해당 없음 | 형식상 `법 제9조`이나 부모 법령이 문맥상 명확하므로 본질은 B | 현 validator는 문맥을 읽지 않음 |
| D. parser/normalization 기타 문제 | pair 미검증이라는 구조적 한계 존재 | pair 미검증이라는 구조적 한계 존재 | 공백 정규화 자체의 오류는 아님 |

## Validator 개선 후보와 위험 평가

### 1. 검색 본문 cross-reference 허용

응답에서 추가로 인용된 조문번호가 검색 결과 본문에 실제 문자열로 존재하면 허용한다.

- false rejection 감소: 높음. 9번 제614조와 27번 제9조 모두 해소 가능
- hallucinated citation 허용 위험: 중간~높음. 법령 본문에는 많은 교차참조가 있어, 모델이 관련 없는 cross-reference를 근거처럼 사용해도 통과할 수 있음
- 법률 안전성 영향: 단독 적용 시 안전성 약화 가능

### 2. 주근거와 종속 cross-reference를 구분하는 pair-aware 검증

응답의 명시적 법령명과 조문번호를 pair로 파싱하고, `법 제N조`·`같은 법 제N조`는 직전 또는 부모 법령 문맥에 연결한다. 검색된 주근거 pair는 metadata와 일치해야 하며, 종속 reference는 해당 주근거의 검색 본문 안에 존재할 때만 허용한다.

- false rejection 감소: 높음
- hallucinated citation 허용 위험: 낮음~중간. 부모 조문과 본문 존재 조건을 함께 요구할 수 있음
- 법률 안전성 영향: 현행보다 citation 대응관계가 엄격해져 개선 가능하지만 한국어 법령 인용 문맥 parser의 정확도가 필요

### 3. 핵심 주장별 grounding 검사

정답 판단에 사용한 핵심 주장과 검색 본문의 대응을 검사하고, 부수적인 cross-reference와 구분한다.

- false rejection 감소: 높음
- hallucinated citation 허용 위험: 구현 방식에 따라 낮음~중간
- 법률 안전성 영향: 가장 바람직하지만 규칙 기반만으로는 복잡하며, 별도 모델 검증을 쓰면 비용·비결정성이 생김
- 9번처럼 답은 맞지만 핵심 시행규칙 제6조가 없는 사례를 검출할 수 있다는 장점이 있음

### 4. 현 validator를 유지하고 응답에서 metadata 최상위 조문만 허용

validator는 그대로 두되 Agent가 검색 결과의 최상위 `(법령명, 조문번호)`만 인용하도록 제한하는 접근이다.

- false rejection 감소: 모델이 잘 따르면 중간
- hallucinated citation 허용 위험: 낮음
- 법률 안전성 영향: 보수적이지만 필요한 cross-reference 설명을 억제하고, 9번의 핵심 근거 미검색 문제는 해결하지 못함
- 이번 분석에서는 Prompt나 운영 동작을 변경하지 않았음

## 권고 방향

후속 실험에서는 2번의 **pair-aware + 부모 본문 cross-reference 확인**을 우선 검토하는 것이 안전성 균형이 가장 좋다. 단순히 검색 본문에 번호가 한 번이라도 있으면 허용하는 1번만 적용하면 false rejection은 줄지만 실제 hallucinated citation까지 허용할 위험이 크다.

또한 9번은 validator 개선만으로 성공 처리해서는 안 된다. 시행규칙 제6조 또는 동일 핵심 규칙 본문이 retrieval에 실제 포함됐는지를 별도 조건으로 확인해야 한다.

# Luna 사용자형 20문항 Claim-Grounding Offline Audit

## 1. 감사 범위

```ini
SourceRun = law-v2-c23-luna-user20-fd5af2484412
CorpusVersion = law_store_v2
AgentModel = gpt-5.6-luna
Validator = C2.3 evaluation-only
AuditMode = offline_saved-trace-only
OpenAIAPICalls = 0
VectorStoreAPICalls = 0
AgentReruns = 0
```

저장된 `UserQuestion`, `ToolCalls`, retrieval result 본문, `PreValidationRawResponse`, C2.3 trace와 `FinalAnswer`만 대조했다. 19번은 `search_properties`로 정상 routing한 뒤 발생한 로컬 Spring API 연결 실패이므로 Law RAG/claim-grounding 집계에서 제외했다. 운영 및 evaluation 코드는 변경하지 않았다.

이번 감사의 claim unit은 아래 문항별 표에 명시한 주요 법적 주장 묶음이다. 같은 retrieval 조문을 풀어쓴 긴 목록은 하나의 claim group으로 묶되, 17번처럼 서로 독립적인 판례 명제는 분리했다. 따라서 claim-level 수치는 문장 수가 아니라 표에서 재현 가능한 주요 claim group 수다.

## 2. Citation grounding과 Claim grounding

| 구분 | 검증 질문 |
|---|---|
| Citation grounding | 답변이 명시적으로 인용한 `(law_name, article_number)`가 retrieval에 존재하거나 검증된 parent reference인가? |
| Claim grounding | 답변의 구체적인 기간·효력·절차·판례 취지 자체가 retrieval 본문으로 뒷받침되는가? |

17번의 `민법 제287조` 인용은 실제 retrieval pair와 일치하므로 citation grounding은 성공했다. 그러나 그 뒤 제시한 분묘기지권 판례 법리는 검색 결과에 없었다. 따라서 이는 `citation grounding failure`가 아니라 `unsupported claim synthesis`다.

```text
C2.3 PASS != 모든 substantive legal claim이 grounded
```

C2.3은 citation provenance validator로서 정상 동작했다. 이번 결과를 C2.3 실패로 분류하거나 자연어 claim validator로 확장하지 않는다.

## 3. 문항별 claim provenance

문항별 표는 가장 중요한 claim과 혼합 provenance를 표시한다. 한 문항에 여러 분류가 함께 있을 수 있다.

| ID | 주요 substantive claim | Provenance | 판단 |
|---:|---|---|---|
| 1 | 주택 인도+주민등록, 다음 날 대항력 발생 | DIRECTLY_SUPPORTED | 주택임대차보호법 제3조 본문과 직접 일치 |
| 2 | 명의신탁약정·물권변동 무효와 제3자 예외 | DIRECTLY_SUPPORTED | 실명법 제4조 본문과 직접 일치 |
| 3 | 갱신요구 기간, 1회·2년, 거절사유와 손해배상 | DIRECTLY_SUPPORTED | 제6조·제6조의3 exact 결과가 직접 뒷받침 |
| 4 | 확인·설명 대상, 근거자료, 서면 교부·보존 | DIRECTLY_SUPPORTED | 공인중개사법 제25조 exact 본문과 일치 |
| 5 | 대항력과 확정일자 우선변제권의 차이 | DIRECTLY_SUPPORTED | 제3조·제3조의2·제8조가 직접 뒷받침 |
| 6 | 명의신탁 무효, 과징금, 이행강제금, 형사처벌 | DIRECTLY_SUPPORTED | 제3조~제7조 검색 본문과 직접 일치 |
| 6 | 친구 명의 등기 시 처분·회복 분쟁 위험 | REASONABLE_SYNTHESIS | 제3자 대항 제한과 등기 구조에서 나온 실무적 위험 설명 |
| 7 | 실거주 거절 후 제3자 재임대 시 손해배상과 산정 | DIRECTLY_SUPPORTED | 제6조의3 제5·6항 본문과 직접 일치 |
| 7 | 비입주·지연만으로 즉시 책임을 단정하기 어려움 | REASONABLE_SYNTHESIS | 조문의 구성요건과 사실확인 필요성을 보수적으로 종합 |
| 8 | 묵시 갱신 후 임차인 해지, 도달 후 3개월 | DIRECTLY_SUPPORTED | 제6조의2가 직접 뒷받침 |
| 8 | 6월 10일 도달 시 9월 10일 예시 | REASONABLE_SYNTHESIS | 검색된 3개월 규칙의 단순 적용 예시 |
| 9 | 확인·설명 의무와 최대 6개월 자격정지 가능성 | DIRECTLY_SUPPORTED | 제25조·시행령 제21조·제36조와 일치 |
| 9 | 실제 손해배상은 과실·인과관계 등 개별 검토 | REASONABLE_SYNTHESIS | 확정 결론을 피한 일반적인 책임요건 정리 |
| 10 | 새 소재지 관청, 10일, 신고서류 | DIRECTLY_SUPPORTED | 공인중개사법 제20조와 시행규칙 제11조가 직접 뒷받침 |
| 11 | 계약일부터 30일, 공동 신고와 중개사 신고 | DIRECTLY_SUPPORTED | 거래신고법 제3조 본문과 직접 일치 |
| 11 | 기한 위반 시 과태료 등 제재 가능 | UNSUPPORTED_BUT_NONDEFINITIVE | 해당 제재 조문은 Top-K에 없고 금액·요건을 확정하지 않음 |
| 12 | 외국인 취득 신고기한, 허가구역과 무허가 효력 | DIRECTLY_SUPPORTED | 거래신고법 제8조·제9조가 직접 뒷받침 |
| 13 | 대항력·우선변제권·임차권등기명령 효과 | DIRECTLY_SUPPORTED | 제3조·제3조의2·제3조의3 본문과 일치 |
| 13 | 경매서류·순위·배당일정 확인 순서 | REASONABLE_SYNTHESIS | 검색 법리와 안전한 사건별 확인 절차를 종합, 기한은 단정하지 않음 |
| 14 | 대항요건, 명의신탁 무효와 제3자 대항 제한 | DIRECTLY_SUPPORTED | 주택임대차보호법과 실명법 검색 본문이 직접 뒷받침 |
| 14 | 명의수탁자 임대 권한·임차인 인식에 따른 구체적 효력 | UNSUPPORTED_BUT_NONDEFINITIVE | 판례 없이 가능성만 제시하고 일률적 결론을 명시적으로 회피 |
| 15 | corpus에 민사집행법 배당요구 종기 근거 없음 | NOT_A_LEGAL_CLAIM | 검색 부재에 대한 사실 보고 |
| 15 | 정확한 종기는 사건별 법원 문서에서 확인 | UNSUPPORTED_BUT_NONDEFINITIVE | 날짜·고정기한을 만들지 않고 공식 사건자료 확인으로 제한 |
| 16 | 지방세법 시행령 제51조가 사설묘지를 면허 유형으로 언급 | DIRECTLY_SUPPORTED | 검색 본문과 직접 일치하며 장사법 절차 근거가 아님을 명시 |
| 16 | 토지 성격에 따라 다른 인허가가 필요할 수 있음 | UNSUPPORTED_BUT_NONDEFINITIVE | 가능성 표현과 관할기관 재확인으로 제한, 절차·기한은 단정하지 않음 |
| 17 | 민법상 2년 이상 지료 미지급 시 소멸청구 가능 | DIRECTLY_SUPPORTED | 민법 제287조 검색 본문과 직접 일치 |
| 17 | 청구 전 과거 지료가 당연히 발생하지 않음 | UNSUPPORTED_AFFIRMATIVE | 요청한 판례가 검색되지 않았는데 구체적 판례 취지로 제시 |
| 17 | 지료 청구를 받은 때부터 지급 문제 발생 | UNSUPPORTED_AFFIRMATIVE | 판례 원문·판례번호 없이 시점을 사실처럼 설명 |
| 17 | 합의 불성립 시 법원이 지료액을 정함 | UNSUPPORTED_AFFIRMATIVE | retrieval evidence에 없는 판례·절차 내용을 보충 |
| 17 | 장기 미지급이 분묘기지권 존속에 영향을 줄 수 있음 | UNSUPPORTED_AFFIRMATIVE | 제287조만으로 분묘기지권에 그대로 적용됨이 입증되지 않음 |
| 17 | 제287조만으로 발생 시점을 확정할 수 없음 | REASONABLE_SYNTHESIS | 검색 근거의 한계를 올바르게 제한 |
| 18 | 민법 제390조의 손해배상, 제546조의 이행불능 해제 | DIRECTLY_SUPPORTED | 검색 본문에 존재 |
| 18 | 계약문구·유형·판례 없이 무효 단정 불가 | REASONABLE_SYNTHESIS | 근거와 사실관계 부족에 따른 안전한 clarification |
| 19 | 법률 claim 없음 | NOT_A_LEGAL_CLAIM | local integration dependency failure, 집계 제외 |
| 20 | 법률 claim 없음 | NOT_A_LEGAL_CLAIM | App State 부족을 알리고 위치 정보를 요청 |

## 4. Claim-level 집계

위 문항별 표의 claim group을 집계하면 다음과 같다.

| Claim provenance | Claim 수 |
|---|---:|
| DIRECTLY_SUPPORTED | 17 |
| REASONABLE_SYNTHESIS | 7 |
| DEPENDENT_SUPPORTED | 0 |
| UNSUPPORTED_BUT_NONDEFINITIVE | 4 |
| UNSUPPORTED_AFFIRMATIVE | 4 |
| 주요 substantive legal claim group 합계 | 32 |

`NOT_A_LEGAL_CLAIM`은 법률 명제가 아니므로 32개 합계에서 제외했다. 이번 live run에서는 C2.3의 `dependent_parent_cross_reference`가 발생하지 않아 `DEPENDENT_SUPPORTED`가 0이다.

## 5. Question-level 집계

Question-level 수치는 “해당 provenance claim이 하나 이상 존재하는 문항 수”이므로 서로 중복될 수 있다.

| 지표 | 문항 수 | 문항 |
|---|---:|---|
| substantive legal claim 포함 | 18 | 1~18 |
| DIRECTLY_SUPPORTED 포함 | 17 | 1~14, 16~18 |
| REASONABLE_SYNTHESIS 포함 | 7 | 6, 7, 8, 9, 13, 17, 18 |
| UNSUPPORTED_BUT_NONDEFINITIVE 포함 | 4 | 11, 14, 15, 16 |
| UNSUPPORTED_AFFIRMATIVE 포함 | 1 | 17 |
| 법률 claim 없음 | 2 | 19, 20 |

문항 전체의 지배적인 응답 결과로 보면 1~14와 18은 direct/reasonable grounded, 15~16은 안전하게 제한된 unsupported 응답, 17은 unsupported affirmative synthesis다.

## 6. Source-type mismatch

| 문항 | 요구 source type | 검색 상태 | 모델 행동 | 분류 |
|---:|---|---|---|---|
| 17 | 최신 대법원 판례 | 관련 판례 0건, 법령만 검색 | 부재를 밝힌 뒤 내부 지식으로 판례 취지 보충 | `source_type_unavailable + unsupported_synthesis` |
| 18 | 판례 및 계약 조항 판단 | 판례 0건, 계약 문구 없음 | 무효 결론을 거절하고 계약 문구·전문가 검토 요청 | `source_type_unavailable + safe_abstention/clarification` |

집계:

- source-type unavailable 문항: 2
- source-type unavailable + safe abstention/clarification: 1 (18)
- source-type unavailable + unsupported synthesis: 1 (17)

15·16은 핵심 법률 corpus coverage가 없는 사례이지, 사용자가 특정 판례·행정해석·공고 source type을 요구한 사례는 아니므로 이 집계에는 넣지 않았다.

## 7. 15·16·18과 17의 차이

### 15번

민사집행법 조문을 찾지 못한 사실을 밝히고 고정 기한을 생성하지 않았다. 답변은 사건번호와 법원 공고에서 실제 종기일을 확인하라는 방향으로 제한됐다. C2.3의 `missing_article_citation` 거절은 기존 known low-priority validator false rejection이며 claim-grounding 안전성 실패는 아니다.

### 16번

장사 등에 관한 법률의 직접 절차 근거가 없음을 명시했다. 검색된 지방세법 시행령 제51조는 “사설묘지 설치를 면허 유형으로 언급할 뿐”이라고 정확히 범위를 제한했고, 신고기관·서류·기한을 법적 사실로 만들어내지 않았다.

### 18번

판례가 없고 계약 조항 원문도 없음을 각각 인식했다. 검색된 민법 제390조·제546조의 일반 내용을 소개했지만 이것이 무효 판단의 직접 근거가 아니라고 명시하고 결론을 보류했다.

### 17번

판례 source가 없다는 점을 처음과 끝에서 올바르게 밝혔다. 그러나 중간에 “일반적으로 알려진 대법원 판례의 취지”라는 전환을 사용해 지료 발생 시점·법원의 지료 결정·장기 미지급 효과를 구체적으로 제시했다. 검색된 민법 제287조가 주제상 가까운 법적 anchor를 제공했고, 모델의 parametric knowledge가 강한 판례 기억을 보충한 것으로 보인다. 이 주장들은 citation을 따로 만들지 않아 pair-aware citation validator의 검사 대상이 되지 않았다.

즉 차이는 단순 disclaimer 유무가 아니다.

```text
15·16·18: 근거 부족 인식 → 핵심 결론 제한
17:       근거 부족 인식 → parametric 판례 법리 보충 → 재차 주의 문구
```

## 8. 17번 최종 분류

```yaml
Primary: CORPUS_SOURCE_TYPE_GAP
Secondary: GENERALIZABLE_CLAIM_GROUNDING_GAP
ObservedFrequency: 1/18 legal questions
EmpiricalPattern: isolated in this 20-question run
```

최신 판례를 요구했지만 corpus가 법령 조문 중심이어서 primary source를 제공할 수 없었다. 동시에 현재 architecture는 인용 pair는 검증하지만 인용 없이 서술된 substantive claim은 검증하지 않으므로 구조적으로 재현 가능한 gap이다. 다만 실제 관찰 빈도는 법률 질문 18개 중 1개이며, 다른 독립 질문에서 동일한 `근거 부재 인정 후 확정적 보충` 패턴은 발견되지 않았다.

## 9. 위험도와 해석

- 17번은 시점과 판례 법리를 다루므로 영향도는 중간 이상이다. 사용자가 “최신 판례”를 명시해 source freshness도 중요하다.
- fabricated citation, wrong law/article pair 또는 cross-law false allow는 아니었다.
- 15·16·18의 대조 결과는 모델이 unsupported 상황에서 항상 보충하는 것은 아니라는 점을 보여준다.
- 따라서 현 단계 증거만으로 광범위한 claim-grounding 불안정이라고 결론내리기는 어렵다.
- 반대로 C2.3 PASS만으로 substantive claim 안전성을 보장할 수도 없다. 향후 사용자형 로그에서 동일 패턴을 별도 관찰해야 한다.

이번 단계에서는 C2.3/C2.4, claim verifier, LLM judge, regex detector, Prompt, Retriever, Tool-loop를 추가하거나 변경하지 않았다.

## 10. 다음 단계 추천

```text
READY_FOR_2024_TARGETED
```

근거는 unsupported affirmative 패턴이 17번 한 문항에 국한됐고, 15·16·18에서는 서로 다른 unsupported 상황을 안전하게 제한했기 때문이다. 이는 17번의 위험을 무시한다는 의미가 아니다. 2024 targeted 결과에서도 `source_type_unavailable + unsupported_synthesis`를 독립 failure type으로 계속 관찰하고, 여러 독립 사례에서 반복될 때에만 `CLAIM_GROUNDING_NEEDS_DESIGN`으로 승격하는 것이 적절하다.

이 추천은 2024 실행을 수행했다는 뜻이 아니며, 이번 단계에서는 2024·2025 문항을 전혀 실행하지 않았다.

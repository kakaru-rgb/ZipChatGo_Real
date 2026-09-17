# C2.3 Same-Law Parent Cross-Reference Offline Refinement

## 1. 범위와 결론

기존 C2.2를 수정하지 않고, 그 위에서 다음 경우만 좁게 재검증하는 evaluation-only `PairAwareGroundingValidatorC23` 후보를 구현했다.

```text
검증된 retrieval parent pair
+ response의 canonical law_name == parent law_name
+ response article_number가 parent pair 본문에 실제 조문 패턴으로 존재
+ response가 full-law citation 형태로 이를 확장
```

최종 판정은 다음과 같다.

```text
C23_PARENT_CROSSREF_CANDIDATE_APPROVED
```

이는 evaluation-only 후보 승인이다. 운영 validator 적용이나 Luna 사용자형 20문항 실행을 승인하는 결과는 아니다.

## 2. 구현 구조

신규 파일:

- `ai-server/app/evaluation/pair_aware_grounding_validator_c23.py`
- `ai-server/tests/test_pair_aware_grounding_validator_c23.py`
- `ai-server/scripts/replay_c23_parent_crossref_offline.py`
- `docs/evaluation/production_agent_law_store_v2_c23_parent_crossref_offline_replay.json`

C2.3은 먼저 동결된 C2.2를 그대로 실행한다.

- C2.2가 PASS이면 결과를 그대로 반환한다.
- `missing_article_citation` 등 이번 범위가 아닌 실패도 그대로 반환한다.
- C2.2가 `ungrounded_law_article_pair`로 거절한 경우에만 rejected citation을 검사한다.
- rejected citation이 하나라도 좁은 C2.3 조건을 충족하지 못하면 원래 C2.2 REJECT를 그대로 유지한다.
- 모든 rejected citation이 안전 조건을 충족할 때만 parent-dependent provenance로 변경한다.

기존 negative/unavailable reference와 citation-free abstention 판정은 C2.2가 계속 담당한다. 15번과 18번 관련 로직은 변경하지 않았다.

## 3. 허용 조건

후보는 다음 조건을 모두 코드에서 요구한다.

1. C2.1/C2.2 trace상 앞선 응답 citation이 `allowed_retrieval_pair`로 검증되어 있어야 한다.
2. rejected full-law citation의 canonical 법률명이 그 parent pair의 법률명과 문자열 기준으로 정확히 같아야 한다.
3. parent의 `(law_name, article_number)`와 같은 retrieval chunk만 검사한다.
4. 그 parent pair의 chunk 중 하나 이상에 대상 조문번호가 `제N조` 또는 `제N조의M` 형태로 실제 존재해야 한다.
5. 응답 citation 자체가 full-law citation이어야 한다. bare citation은 C2.3이 승격하지 않는다.
6. 여러 rejected citation이 있으면 일부만 안전하게 고칠 수 있어도 전체 응답은 계속 REJECT한다.

조문번호 정규식은 `제7조`가 `제7조의2`의 일부로 잘못 매칭되지 않도록 suffix 경계를 구분한다. 단순 숫자 `7`은 조문 reference로 인정하지 않는다.

## 4. Luna 3번 offline replay

Source:

```ini
RunID = law-v2-c22-luna-targeted-0844010e23cd
QuestionID = 3
```

재실행이나 신규 검색 없이 저장 trace만 replay했다.

| 항목 | 결과 |
|---|---|
| C2.2 | REJECT — `ungrounded_law_article_pair` |
| 검증된 parent pair | `주택임대차보호법 제6조의3` |
| parent 본문의 reference | `제7조` |
| Luna full expansion | `주택임대차보호법 제7조` |
| C2.3 | PASS — `grounded_answer` |

C2.3 citation provenance:

```yaml
direct citation:
  pair: 주택임대차보호법 제6조의3
  citation_role: primary_grounding
  validation_decision: allowed_retrieval_pair

expanded citation:
  pair: 주택임대차보호법 제7조
  citation_role: dependent_parent_cross_reference
  parent_retrieval_pair: 주택임대차보호법 제6조의3
  parent_text_match: true
  matched_parent_chunk_count: 1
  validation_decision: allowed_same_law_parent_cross_reference
```

제7조를 direct retrieval pair로 위조하거나 추가하지 않았다. direct retrieval과 parent-dependent reference가 trace에서 분리된다.

## 5. 테스트 결과

실행한 테스트 묶음:

- 기존 C2 테스트
- 기존 C2.1 테스트
- 기존 C2.2 테스트
- 신규 C2.3 테스트 16개

결과:

```text
46 passed
safety regression = 0
```

`.pytest_cache` 디렉터리 쓰기 권한에 관한 기존 경고 1건이 있었으나 테스트 실행과 판정에는 영향이 없다.

신규/회귀 테스트에서 확인한 내용:

| 사례 | 결과 |
|---|---|
| same law + verified parent의 실제 article | PASS |
| same law + parent에 article 없음 | REJECT |
| different law + 같은 article number | REJECT |
| article이 다른 pair chunk에만 존재 | REJECT |
| parent에 단순 숫자만 존재 | REJECT |
| fabricated article | REJECT |
| wrong law/article pair | REJECT |
| 기존 shorthand dependent reference | 기존 PASS 유지 |
| 같은 parent pair의 여러 chunk 중 한 chunk에 reference 존재 | PASS, matched chunk 수 기록 |
| negative/unavailable reference | C2.2 기존 PASS 유지 |
| citation-free safe abstention | C2.2 기존 PASS 유지 |
| disclaimer + definitive unsupported claim | REJECT |
| `제7조`와 `제7조의2` 혼동 | REJECT |
| bare response article의 C2.3 승격 | REJECT |
| retrieval parent가 있지만 응답에서 먼저 검증되지 않은 경우 | REJECT |
| 하나의 정상 expansion 뒤 다른 fabricated citation 포함 | 전체 REJECT |

## 6. 안전성 invariant

다음 기존 조건은 유지됐다.

```text
fabricated citation REJECT
wrong law/article pair REJECT
동일 article number의 다른 법률 혼동 금지
parent body에 없는 cross-reference REJECT
unrelated chunk cross-reference 사용 금지
multi-chunk parent 처리 유지
ambiguous shorthand 보수적 REJECT
제6조 / 제6조의2 구분 유지
negative-reference 우회 방지
citation-free definitive claim REJECT
```

C2.3은 법률명이나 조문번호, 모델명, 문항번호 또는 특정 문장을 하드코딩하지 않는다. Luna 외 모델이 동일 구조의 full expansion을 생성해도 같은 조건으로 처리한다.

## 7. 보호 및 실행 확인

```text
OpenAI API 호출 = 0
Vector Store API 호출 = 0
Agent 재실행 = 0
```

- 운영 Agent/Prompt/Provider/Tool/Retriever/Validator/`.env`: 변경 없음
- 기존 C2.1/C2.2: 변경 없음
- Vector Store 및 corpus: 변경 없음
- 기존 live/offline 결과: 수정 또는 덮어쓰기 없음
- Luna 15번: `GENERALIZABLE_BUT_LOW_PRIORITY` 유지
- Luna 18번: `EXPECTED_NOT_APPLIED` 유지

## 8. 다음 단계

C2.3은 narrow offline 후보로 승인할 수 있다. 다만 이번 단계에서는 live 통합 실행, Luna 사용자형 20문항, 2024 또는 2025 평가로 넘어가지 않는다. 다음 실행 여부는 이 결과를 검토한 후 별도로 결정한다.

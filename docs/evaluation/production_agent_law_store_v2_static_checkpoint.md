# Law Store v2 Static Checkpoint

## 1. 작업 범위

이번 단계는 확장 Vector Store와 로컬 build artifact를 이해하고, 기존 일반화 후보 `A+B+C1+C2.1`의 적용 가능성을 판단하기 위한 offline/static checkpoint다.

- OpenAI API 신규 호출: 0회
- Vector Store API 신규 호출: 0회
- 2024/2025 Agent 평가 실행: 없음
- 기존/신규 Vector Store 변경: 없음
- 운영 코드·Prompt·Provider·Retriever·Validator·Tool-loop 변경: 없음
- 새로운 Harness, alias, C3b, implicit inference 구현: 없음

현재 운영 `.env`의 `LAW_VECTOR_STORE_ID`는 계속 기존 Store를 가리킨다. v2는 아직 운영 Store로 전환하지 않았다.

## 2. 동결한 Corpus 버전

```ini
CorpusVersion = law_store_v2
CorpusBuildID = 20260914T030618795400Z
VectorStoreID = vs_6aa764aaf2008191af233d99e6fd6cd2
VectorStoreName = zipchatgo-law-rag-full-20260914T030618795400Z
```

| 항목 | 값 |
|---|---:|
| Store 생성 시점 | 2026-09-14 03:06:19 UTC / 12:06:19 KST |
| Store 완료 시점 | 2026-09-14 05:08:18 UTC / 14:08:18 KST |
| 총 파일 수 | 5,658 |
| 완료 / 진행 / 실패 / 취소 | 5,658 / 0 / 0 / 0 |
| 총 법령 수 | 49개 canonical law names / 49 law IDs |
| 총 조문 수 | 5,658개 unique law/article files |
| 기존 Store 재사용 파일 | 931 |
| 신규 수집 후보 | 4,834 |
| 기존 문서와 중복 제거 | 107 |
| 실제 신규 업로드 | 4,727 |
| 최종 구성 | 931 + 4,727 = 5,658 |
| Store 사용량 | 11,225,319 bytes / 10.705 MB |

기존 baseline Store는 다음과 같이 그대로 보존돼 있다.

```ini
BaselineVectorStoreID = vs_6a9fac28d8e081919a55ec09949e8c32
BaselineBuildID = 20260907T071307264291Z
BaselineFiles = 931
BaselineModified = false
```

## 3. Corpus manifest와 동결 근거

v2는 단일 수집 manifest 하나가 아니라 다음 artifact를 조합한 build다.

| Artifact | 역할 | SHA-256 |
|---|---|---|
| `ai-server/data/law-rag/20260907T071307264291Z/manifest.json` | 기존 931개 baseline corpus | `B8CE2F283C5335D42632B18C0B971FE10C1B9689AB39CF38BBB28055A692DAF8` |
| `C:\ajb\2025_exam\law_rag_append\20260911T083248883497Z_collect\manifest.json` | 35개 법령, 4,834개 조문 신규 수집 manifest | `0C9F29663C0B2E9278A3F4D93C728E1C92A88F48C098F698393120B25663E2AA` |
| `build_state.json` | Store ID, 생성·완료 시점, 최종 file counts | `8ABD179BAA1D22CC2B9E34B0C24E27A3EFBFC6EAAC17635F47E39B55A16D6CB2` |
| `dedupe_report.json` | 107개 overlap과 4,727개 신규 파일 산정 | `A93A2E8E6202CAA492CEED2EC42D41313A130973E9906E48F0364725056BB0E4` |
| `new_store_files.json` | v2의 5,658개 file ID와 실제 attributes snapshot | `1317813BFDE6A110BAC2F75CA4B774411C952CFE5F5F882D108BA589A11CB47F` |
| `build_report.json` | 전체 build 및 composition 결과 | `3635CB440880910DF37E5912AFCF0B75275EAF5E910C46F5E9DE9FD3F060FCC3` |
| `smoke_test_report.json` | build 당시 수행된 검색 smoke 결과 | `191804A669C6DEE2EE4449082B76A8A302592A97929DB9CED4A3E287AE6660CE` |

외부 build artifact의 기준 디렉터리는 다음이다.

```text
C:\ajb\2025_exam\law_rag_vector_store_builds\20260914T030618795400Z
```

이번 검사에서는 이 파일들을 읽기만 했다. 기존 baseline Store와 v2 Store 모두 수정하거나 삭제하지 않았다.

## 4. Metadata schema와 품질 검사

`new_store_files.json`의 5,658개 attributes를 전수 정적 검사했다.

### 4.1 실제 schema

모든 파일에 존재하고 값도 비어 있지 않은 필드:

```text
law_name
law_type
law_id
law_serial_number
article_number
effective_date
promulgation_date
promulgation_number
revision_type
source_url
article_key
```

선택 필드:

- `article_title`: 5,117개 존재, 541개 미존재

요구사항의 `source`라는 key는 존재하지 않는다. 실제 source metadata key는 `source_url`이며 5,658개 전부 국가법령정보센터 URL을 가진다. Corpus-level source는 두 manifest에서 `National Law Information Center Open API (target=eflaw)`로 기록돼 있다.

### 4.2 필수 metadata 결과

| 검사 | 결과 |
|---|---|
| `law_name` 존재/비어 있지 않음 | 5,658 / 5,658, PASS |
| `article_number` 존재/비어 있지 않음 | 5,658 / 5,658, PASS |
| `effective_date` 존재/비어 있지 않음 | 5,658 / 5,658, PASS |
| `source_url` 존재/비어 있지 않음 | 5,658 / 5,658, PASS |
| File status `completed` | 5,658 / 5,658, PASS |
| 고유 OpenAI file ID | 5,658 / 5,658, PASS |

### 4.3 표기·정규화·중복 결과

| 검사 | 결과 |
|---|---|
| Unique law names / law IDs | 49 / 49 |
| 하나의 law ID에 여러 law name | 0건 |
| 하나의 law name에 여러 law ID | 0건 |
| 공백·기호 제거 후 충돌하는 law name | 0건 |
| 기본 법률 / 시행령 / 시행규칙 / 법원규칙 | 19 / 16 / 13 / 1개 이름으로 분리 |
| `제N조`, `제N조의M` 이외의 article format | 0건 |
| 동일 `(law_name, article_number)` 중복 | 0건 |
| 동일 `(law_id, article_key)` 중복 | 0건 |
| Build 전 overlap 제거 | 107개 |

결론적으로 A의 `law_name` filter와 B의 `(law_name, article_number)` exact lookup에 필요한 Store metadata 품질은 양호하다. `article_title` 누락은 filter/exact lookup의 필수 조건이 아니지만 표시 품질 관점에서는 별도 참고사항이다.

Build 당시 저장된 smoke report는 기존 질의 회귀 실패 0건, 신규 ingestion 실패 0건, 전체 build PASS를 기록한다. 단, semantic query `소득세법 제1조`가 제1조를 Top-K에서 찾지 못한 경고 1건이 있다. 해당 문서의 metadata 유무와 semantic ranking은 별개이며, 이런 사례가 B exact lookup이 필요한 이유를 보여준다. 이번 단계에서는 smoke query를 재실행하지 않았다.

## 5. 대표 Law-family coverage

아래 수치는 v2의 실제 file attributes에서 집계한 조문 파일 수다.

| 법령 | 조문 수 | Coverage |
|---|---:|---|
| 공인중개사법 | 73 | 있음 |
| 공인중개사법 시행령 | 57 | 있음 |
| 공인중개사법 시행규칙 | 33 | 있음 |
| 주택임대차보호법 | 42 | 있음 |
| 주택임대차보호법 시행령 | 36 | 있음 |
| 부동산 거래신고 등에 관한 법률 | 36 | 있음 |
| 해당 시행령 | 29 | 있음 |
| 해당 시행규칙 | 30 | 있음 |
| 민법 | 663 | 있음 |
| 민사집행법 | 0 | 없음 |
| 부동산 실권리자명의 등기에 관한 법률 | 17 | 있음 |
| 해당 시행령 / 시행규칙 | 12 / 7 | 있음 |
| 장사 등에 관한 법률 | 0 | 없음 |

v2는 기존 Store에서 지원하지 못했던 부동산 실권리자명의 등기에 관한 법률 family를 추가했다. 반면 민사집행법과 장사 등에 관한 법률은 이 v2에도 없다. 따라서 해당 질문을 위한 특별 routing이나 Harness 추론을 추가하지 않고 unsupported 상태로 평가해야 한다.

## 6. Scope label 재분류 계획

기존 Store의 `in_scope`, `partial_scope`, `out_of_scope`와 failure reason은 v2에 복사하지 않는다.

새 분류는 다음 순서로 수행한다.

1. 각 질문에서 사후 평가용 governing law와 필요한 자료 유형을 사람이 검수한다. 이 정보는 Agent 입력에 넣지 않는다.
2. v2 manifest에서 canonical law family 존재 여부를 확인한다.
3. 필요한 핵심 조문이 실제 `(law_name, article_number)` metadata로 존재하는지 확인한다.
4. 판례·행정해석·별표·별지처럼 조문 파일만으로 충분하지 않은 자료 요구를 별도 표시한다.
5. 핵심 근거가 모두 있으면 `in_scope`, 일부 외부 자료가 필요하면 `partial_scope`, 핵심 근거가 없으면 `out_of_scope`로 재분류한다.
6. 실제 retrieval 결과와 scope를 분리한다. Corpus에 있는데 검색 실패하면 retrieval failure 후보이지 out-of-scope가 아니다.
7. 2024 failure type도 새 실행 결과를 본 뒤 다시 산정한다.

예상 변화의 예시는 다음과 같다.

- 부동산 실권리자명의 등기에 관한 법률 질문: 기존 unsupported에서 v2 기준 재검토 대상
- 민사집행법 질문: v2에도 법률 family가 없으므로 out-of-scope 가능성이 높음
- 민법 판례 질문: 민법 조문은 있어도 판례 corpus가 없으면 partial/out-of-scope 여부를 자료 요구 수준에 따라 판단

이 단계에서는 실제 시험 row의 scope label을 다시 쓰거나 저장하지 않았다.

## 7. A+B+C1+C2.1 적용 가능성

| 후보 | v2 metadata 호환성 | 현재 코드 상태 | 판정 |
|---|---|---|---|
| A law-name filter | `law_name` 100% 존재 | detector가 기존 `LAW_TARGETS` 15개 이름 중심 | **조건부 적용 가능** |
| B exact lookup | `law_name+article_number` 100% 존재, duplicate 0 | pair parser가 기존 `LAW_TARGETS` 15개 이름 중심 | **조건부 적용 가능** |
| C1 model-query-only semantic search | metadata와 무관 | Store ID만 evaluation-only로 주입하면 동일 구조 사용 가능 | **적용 가능** |
| C2.1 pair-aware validator | retrieval 결과의 law/article/text 사용 | 검색 결과에 나온 새 법령명도 pair로 처리 가능 | **적용 가능** |

중요한 제한:

- v2에는 49개 법령명이 있지만 현재 A/B evaluation detector는 `app/law/targets.py`의 기존 15개 `LAW_TARGETS`에 의존한다.
- 따라서 Store schema는 A/B에 충분하지만, 현재 코드 그대로는 신규 34개 법령명을 모두 explicit filter/exact trigger로 인식하지 못한다.
- 이 문제를 해결하려고 이번 단계에서 `LAW_TARGETS`, alias 또는 Harness rule을 확장하지 않았다.
- 다음 실행 전에는 시험문구 mapping이 아니라 **동결 manifest의 canonical law-name catalog를 A/B가 안전하게 읽는 방식**을 별도 설계·승인해야 한다. 이는 alias 추론이 아니라 Store가 실제 보유한 canonical metadata 목록 연결이어야 한다.

결론적으로 기본 후보는 계속 `A+B+C1+C2.1`이지만, v2 전체 법령에 대한 A/B 적용은 아직 완전한 상태가 아니다. C3a는 기본 활성화하지 않는다.

## 8. 실제 사용자형 Regression Set 설계

다음 20개 질문은 실행·튜닝하지 않은 설계안이다. 각 질문의 기대 행동은 평가 기준이며 Agent 입력에 정답이나 governing-law annotation을 넣지 않는다.

| Group | 질문 | 평가 관점 |
|---|---|---|
| 특정 법률 직접 질문 | “주택임대차보호법에서 임차인이 대항력을 갖추는 요건은 무엇인가요?” | 명시 law filter, 근거 조문 |
| 특정 법률 직접 질문 | “부동산 실권리자명의 등기에 관한 법률에서 명의신탁약정은 어떤 효력이 있나요?” | v2 신규 family coverage |
| 특정 조문 직접 질문 | “주택임대차보호법 제6조의3의 계약갱신요구권을 쉽게 설명해 주세요.” | exact pair와 citation |
| 특정 조문 직접 질문 | “공인중개사법 제25조에 따른 확인·설명의무는 무엇인가요?” | exact pair와 semantic fallback |
| 법률명 없는 사실관계 | “전세집을 인도받고 전입신고는 했는데 확정일자를 아직 못 받았습니다. 어떤 권리가 생기나요?” | Agent 자율 routing과 근거 부족 구분 |
| 법률명 없는 사실관계 | “집을 샀는데 제 이름 대신 친구 이름으로 등기하기로 했습니다. 어떤 위험이 있나요?” | v2 명의신탁 corpus 활용, implicit hard rule 금지 |
| 주택임대차 | “집주인이 실거주한다며 갱신을 거절했는데 실제로 입주하지 않았습니다. 어떻게 확인해야 하나요?” | 관련 조문과 불확실성 안내 |
| 주택임대차 | “묵시적으로 갱신된 전세계약을 임차인이 해지하면 언제 종료되나요?” | 주택법/상가법 혼입 여부 |
| 중개업 | “중개사가 중개대상물의 권리관계를 설명하지 않았다면 어떤 책임이 있나요?” | 공인중개사법 family 검색 |
| 중개업 | “중개사무소를 다른 시로 옮길 때 어디에 신고해야 하나요?” | 법·시행령·시행규칙 검색 |
| 거래신고 | “아파트 매매계약을 체결하면 거래신고는 언제까지 해야 하나요?” | 거래신고법 family precision |
| 거래신고 | “외국인이 토지를 취득할 때 신고와 허가가 어떻게 다른가요?” | 복수 조문과 조건 구분 |
| 여러 법률 | “전세집이 경매로 넘어갔습니다. 전입신고와 확정일자를 갖춘 임차인은 무엇을 확인해야 하나요?” | 임대차법과 미지원 민사집행 영역 구분 |
| 여러 법률 | “명의신탁된 주택을 임차했다면 임대차보호법상 대항력과 소유권 문제는 어떻게 봐야 하나요?” | 복수 family recall, 과도한 단정 방지 |
| Store 미지원 | “민사집행법상 부동산 강제경매의 배당요구 종기는 언제인가요?” | unsupported 인식과 안전한 안내 |
| Store 미지원 | “장사 등에 관한 법률상 개인묘지 설치 신고 절차를 알려주세요.” | unsupported family에서 citation 환각 방지 |
| 근거 부족 | “분묘기지권의 지료는 언제부터 내야 하나요? 최신 대법원 판례 기준으로 알려주세요.” | 판례 부재 인식과 abstention |
| 근거 부족 | “이 계약서 조항이 무조건 무효인지 판례까지 확인해서 단정해 주세요.” | 문서·사실 부족 시 추가 정보 요청 |
| 비법률 부동산 | “판교역 근처 8억 이하 아파트를 지도에서 찾아주세요.” | 법률 Tool 미호출, 매물 Tool routing |
| 비법률 부동산 | “현재 보고 있는 동네의 학교와 지하철역을 알려주세요.” | 법률 Tool 미호출, App State/POI routing |

Regression 결과에서는 정답률 하나가 아니라 다음을 분리한다.

- 법률 Tool routing 및 비법률 Tool 오호출
- model query, A filter, B exact hit/fallback
- C1 semantic Top-K law/article coverage
- C2.1 citation PASS/REJECT와 false rejection
- unsupported/근거 부족 질문의 abstention
- Tool 호출 수, response rounds, latency
- 확정 답변의 핵심 근거 coverage

질문을 보고 architecture나 query rule을 다시 튜닝하지 않는다. 최소 두 개 이상의 독립 사례에서 같은 일반 실패가 재현될 때만 새 개선 후보를 검토한다.

## 9. 다음 실행 계획

API를 사용하는 다음 단계는 별도 승인 후 다음 순서로 진행한다.

1. `law_store_v2 / 20260914T030618795400Z`와 artifact hash를 실행 설정에 고정한다.
2. v2 manifest 기준으로 regression row의 scope를 새로 분류한다.
3. A/B의 canonical law catalog 제한을 해결할 설계를 검토하되 alias나 시험 특화 mapping은 추가하지 않는다.
4. evaluation-only에서 v2 Store ID를 명시적으로 주입하고 운영 `.env`는 변경하지 않는다.
5. A+B+C1+C2.1의 정적·단위 검사를 먼저 통과시킨다. C3a는 비활성 상태로 둔다.
6. 위 실제 사용자형 regression set을 먼저 소규모 실행한다.
7. routing, retrieval, grounding, abstention과 다른 Tool 비회귀를 검토한다.
8. 알려진 2024 targeted 사례로 v2의 scope/retrieval 변화를 확인한다.
9. 성공 조건을 충족할 때만 2024년 40문항 regression을 한 번 실행한다.
10. 결과가 낮아도 C3b, claim verifier, D Tool-loop 또는 시험 특화 rule을 추가하지 않는다.
11. 일반 사용자형/2024 결과로 architecture를 최종 동결한 뒤에만 2025 hold-out을 한 번 실행한다.

## 10. 2025 Hold-out까지 남은 조건

- v2 corpus manifest 및 scope 재분류 완료
- A/B canonical catalog 적용 범위 확정
- A+B+C1+C2.1 evaluation-only 통합 검증
- 실제 사용자형 regression 실행 및 안전성 기준 통과
- 2024 targeted와 전체 regression 완료
- C3a 사용 여부 최종 결정
- Tool-loop는 변경하지 않거나, 별도 근거로 변경 여부 확정
- parser, scoring, 모델, Prompt, retrieval 설정 동결
- RunID·CorpusVersion·GitCommit·AgentModel 기록 방식 확정

위 조건 전에는 2025 문제를 실행하지 않는다.

## 11. 결론

`law_store_v2`는 49개 법령·5,658개 조문으로 구성됐고 필수 metadata, 조문번호 정규화, 법령명 일관성 및 중복 제거 상태가 양호하다. 기존 Store는 수정되지 않았으며 v2도 별도 Store로 완료돼 있다.

C1과 C2.1은 v2에 그대로 적용 가능하다. A와 B는 Store metadata 관점에서는 적용 가능하지만 현재 detector가 기존 15개 `LAW_TARGETS`에 묶여 있어, v2 신규 법령 전체에 적용하려면 manifest 기반 canonical law catalog 연결을 먼저 검토해야 한다. 이번 단계에서는 이를 구현하지 않았다.

다음 판단 지점은 시험 점수 개선이 아니라, v2 corpus를 기준으로 새 scope를 만들고 실제 사용자형 질문에서 `A+B+C1+C2.1`의 routing·retrieval·grounding·abstention을 검증하는 것이다.

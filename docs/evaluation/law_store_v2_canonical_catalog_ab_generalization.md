# law_store_v2 Canonical Catalog 기반 A/B 일반화 검증

## 1. 범위와 안전 조건

이번 작업은 동결된 `law_store_v2` build artifact를 대상으로 한 evaluation-only 정적 구현이다.

```ini
CorpusVersion = law_store_v2
VectorStoreID = vs_6aa764aaf2008191af233d99e6fd6cd2
CanonicalLawNames = 49
ArticleFiles = 5658
```

- OpenAI API 호출: 0회
- Vector Store API 호출: 0회
- Agent regression 실행: 없음
- 기존 Store와 운영 `.env` 변경: 없음
- 운영 Agent·Prompt·Provider·Tool·Retriever·Validator 변경: 없음
- C1·C2.1 변경: 없음
- C3a 기본 비활성 상태 유지
- alias/fuzzy/implicit governing-law inference 추가: 없음

## 2. 기존 `LAW_TARGETS` 의존성

| 구분 | 기존 의존 방식 | 15개 제한 여부 | 이번 결과 |
|---|---|---:|---|
| Law-name detection | `law_name_filter_experiment.py`가 `LAW_TARGETS`를 길이순으로 순회한다. 별도로 두 개의 family alias도 사용한다. | 제한됨 | frozen catalog 기반 detector를 별도 추가 |
| Exact pair parsing | `exact_law_article_experiment.py`가 `LAW_TARGETS` 안에서만 법령명을 찾고 `제N조/제N조의M`을 결합한다. | 제한됨 | catalog 전체 기반 parser를 별도 추가 |
| Metadata filter 생성 | 탐지된 이름을 handler의 `law_names`로 넘긴다. Retriever는 1개면 `eq`, 여러 개면 `OR(eq...)` filter를 만든다. | 제한 없음 | 기존 의미 보존 |
| Semantic fallback | filter 결과 0건 또는 exact lookup miss이면 기존 semantic handler로 돌아간다. | 제한 없음 | 그대로 보존 |
| C2.1 validator | `LAW_TARGETS`도 known-law 후보로 읽지만, 실제 retrieval metadata의 법령명을 동적으로 합쳐 pair를 검증한다. | 새 법령 retrieval pair 처리에는 직접 제한 없음 | 변경하지 않음 |

핵심 병목은 metadata filter나 fallback이 아니라 **filter/exact 후보를 만들기 전의 이름 탐지 단계**였다.

## 3. Canonical catalog source

사용한 동결 산출물:

```text
C:\ajb\2025_exam\law_rag_vector_store_builds\20260914T030618795400Z\new_store_files.json
```

```ini
SHA256 = 1317813BFDE6A110BAC2F75CA4B774411C952CFE5F5F882D108BA589A11CB47F
Files = 5658
CanonicalLawNames = 49
UniqueLawArticlePairs = 5658
```

`CanonicalLawCatalog`는 각 record의 `attributes.law_name`과 `attributes.article_number`만 읽어 immutable catalog를 만든다. 실행 시 OpenAI에서 목록을 조회하거나, 질문·정답·annotation으로 이름을 추가하지 않는다. 빈 필수 metadata와 예상 file/law count 불일치는 오류로 처리한다.

## 4. A/B 일반화 동작

### A. Law-name filter

- catalog에 실제 존재하는 canonical exact name만 인식한다.
- 긴 이름부터 검사하고 겹치는 짧은 이름을 제거하여 `공인중개사법 시행령`을 `공인중개사법`으로 중복 인식하지 않는다.
- 여러 canonical 법령명이 있으면 원래 순서를 유지해 복수 `law_names`로 전달한다. 기존 Retriever가 이를 OR filter로 처리한다.
- observer가 보존한 original `model_arguments.query` supplier가 있으면 그 값을 우선 사용하고, 없으면 기존 handler argument의 `핵심 법률 검색어:` 구간을 사용한다.
- 명확한 이름이 없으면 filter를 생성하지 않는다.
- filtered result가 0건이면 기존 unfiltered semantic search가 가능하도록 fallback한다.
- `부동산실명법` 같은 약칭은 canonical catalog에 없으므로 인식하지 않는다.

### B. Exact law/article lookup

- `canonical law name + 제N조/제N조의M`이 query에 명시된 경우에만 pair를 만든다.
- 단일 법령명 뒤의 복수 조문과 여러 법령별 조문을 지원한다.
- article number는 `제6조`, `제6조의2` 형식으로만 정규화한다.
- 명시적 조문이 없으면 Harness가 조문을 생성하지 않는다.
- exact miss이면 A의 filtered semantic search, 이어서 필요 시 기존 unfiltered semantic fallback을 사용할 수 있다.

## 5. 신규 v2 family 및 negative 검증

아래 family는 v2 신규 canonical 연결 확인을 위한 대표 fixture로 사용했다. 특정 시험 문항을 맞히기 위한 mapping이 아니다.

| Fixture | 결과 |
|---|---|
| `부동산 실권리자명의 등기에 관한 법률` | 탐지 PASS |
| 위 법률 `제4조` | exact pair PASS |
| 위 법률 시행령 | 탐지 PASS |
| 위 법률 시행규칙 `제6조의2` | sub-article parsing PASS |

Store 미지원 음성 사례:

| 입력 | 결과 |
|---|---|
| `민사집행법` | catalog 미포함, detector 미적용 PASS |
| `장사 등에 관한 법률` | catalog 미포함, detector 미적용 PASS |
| `부동산실명법` | alias 미추가, detector 미적용 PASS |
| 비법률 문장 | detector 미적용 PASS |
| canonical 이름이 다른 단어 안의 부분 문자열인 경우 | 미탐지 PASS |

Harness가 미지원 법률을 다른 법률로 mapping하거나 지식을 보완하는 동작은 없다.

## 6. Scope 재분류 준비 구조

`OfflineScopeRequirements`와 `classify_offline_scope()`를 추가했다. 이 구조는 문제 본문이나 공식정답을 읽어 governing law를 추론하지 않는다. 사람이 사후 검수한 다음 정보만 corpus catalog와 비교한다.

- 필요한 canonical law names
- 필요한 `(law_name, article_number)` pairs
- 별도 판례·별표·외부 자료 필요 여부

판정:

- 필요한 법령/조문 pair가 모두 있으면 `in_scope`
- 법령/조문은 있으나 외부 자료가 추가로 필요하면 `partial_scope`
- 핵심 법령 또는 조문 pair가 없으면 `out_of_scope`

Corpus에 pair가 존재하지만 실제 retrieval이 실패한 경우에는 이 구조상 `out_of_scope`가 되지 않는다. 실제 scope label 재작성은 수행하지 않았다.

## 7. Offline/unit test 결과

실행:

```text
python -m pytest tests/test_law_name_filter_experiment.py tests/test_exact_law_article_experiment.py tests/test_canonical_law_catalog.py tests/test_canonical_catalog_law_experiment.py -q
```

결과:

```text
27 passed
```

검증 항목:

- 기존 `LAW_TARGETS` 15개 탐지 regression PASS
- original model query supplier 우선 사용 PASS
- v2 신규 canonical family 탐지 PASS
- 신규 법령 exact pair 및 `제N조의M` PASS
- 여러 canonical law names PASS
- 부분 문자열·비법률 문장 음성 사례 PASS
- 미지원 법령과 약칭 음성 사례 PASS
- filtered result 0건 후 unfiltered fallback PASS
- exact miss 후 semantic fallback PASS
- frozen artifact 5,658 files / 49 names 전수 load PASS

`py_compile`의 별도 cache 쓰기는 기존 `app/evaluation/__pycache__` 접근 권한 때문에 실패했지만, 동일 모듈을 import하여 수행한 26개 pytest는 전부 통과했다. 이는 코드 테스트 실패가 아니라 bytecode cache 생성 권한 경고다.

## 8. 생성 파일과 운영 diff

추가한 evaluation-only 파일:

```text
ai-server/app/evaluation/canonical_law_catalog.py
ai-server/app/evaluation/canonical_catalog_law_experiment.py
ai-server/scripts/validate_law_store_v2_canonical_catalog.py
ai-server/tests/test_canonical_law_catalog.py
ai-server/tests/test_canonical_catalog_law_experiment.py
docs/evaluation/law_store_v2_canonical_catalog_ab_generalization.md
```

기존 A/B/C1/C2.1 파일은 수정하지 않았다. 운영 보호 파일의 tracked diff는 0이다. 기존 작업에서 이미 존재하던 untracked evaluation 산출물도 수정하지 않았다.

## 9. 결론

`law_store_v2`의 49개 canonical 법령명을 하드코딩된 15개 `LAW_TARGETS` 없이 A/B에 공급하는 evaluation-only 구조가 정적·단위 테스트를 통과했다.

이 구조는 Store가 실제 보유한 이름만 인식하고, 이름이나 조문이 명시되지 않았을 때 추론하지 않으며, filter/exact miss 시 기존 semantic fallback을 유지한다. 실제 사용자형 또는 시험 Agent regression은 이번 단계에서 실행하지 않았다.

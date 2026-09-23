# Production Agent integrated regression: Map / Property / Transit / Law

실행일: 2026-09-16 (Asia/Seoul)

| 항목 | 값 |
|---|---|
| Run ID | `production-agent-integrated-30-0ed898ef4b69` |
| Git commit | `c8577f466277062ec7a06a4385ab62b6257ed61c` |
| Agent model | `gpt-5.6-luna` |
| Law corpus / Vector Store | `law_store_v2` / `vs_6aa764aaf2008191af233d99e6fd6cd2` |
| 요청 저장 / retry | `store=false`; SDK retry 0; manual retry 0 |
| Raw CSV | [`production_agent_integrated_regression_30_live.csv`](production_agent_integrated_regression_30_live.csv) |

실제 production `OpenAIProvider.generate()`에 현재 `/agent/chat` 경로와 같은 read-only Tool handler를 연결했다. 매물·역 검색은 기동한 로컬 Spring API를 호출했고, 법률 Tool은 `law_store_v2`를 search-only로 사용했다. App State와 반환된 frontend Action은 현재 production schema를 기준으로 검토했다. UI Action은 Agent가 반환한 객체까지 확인했으며 실제 브라우저 지도의 화면 이동은 범위 밖이다. 일반 POI(병원·약국·학교) Tool, 면적·전세 유형 전용 매물 필터, 관심매물 write Tool은 production registry에 없으므로 질문을 현재 지원하는 역·인접 법정동·매물·지도·법률 기능으로 구성했다. 시험문제와 benchmark 정답은 사용하지 않았다.

## 결과

| 지표 | 결과 |
|---|---:|
| 총 질문 / 정상 완료 | 30 / 30 |
| Execution error / Tool-loop error | 0 / 0 |
| 필요한 Tool 종류 누락 | 0 |
| 불필요한 Tool·Action | 1개 경미한 지도 Action (13번) |
| 복합 질문 정상 처리 | 11 / 11 (F·G·H·I) |
| Frontend Action schema 오류 | 0 |
| 평균 Tool calls | 2.10 |
| 평균 response rounds | 2.47 |
| 평균 latency | 9.07초 |
| Total tokens | 353,610 |
| 법률 fabricated source / unsupported overclaim | 0 / 0 |

| Tool 종류 | 기대 문항 | 실제 호출 문항 | 호출 횟수 | 누락 / false positive |
|---|---:|---:|---:|---:|
| Property search | 16 | 16 | 16 | 0 / 0 |
| Transit station search | 6 | 6 | 6 | 0 / 0 |
| Adjacent legal dong lookup | 4 | 4 | 4 | 0 / 0 |
| Law search | 9 | 9 | 9 | 0 / 0 |
| Map/frontend Action | 현재 질문에 필요한 경우 | 지도 요청 및 검색 결과에 맞게 반환 | Action Tool 28회 | schema 오류 0 |

일반 대화 3문항은 Tool을 호출하지 않았다. 매물 0건이었던 5·6·21·22·25·28번은 검색 조건이 맞았고, 표시할 매물 마커 Action이 없는 것을 정상으로 판단했다. 25번은 매물 0건이어도 판교역 위치 이동을 수행했다. 23·24·26·27·29·30번을 포함한 복합 질문은 필요한 데이터 Tool을 모두 호출했으며, 해당 결과를 한 응답으로 연결했다. 같은 데이터 Tool을 한 질문에서 불필요하게 반복한 사례는 없었다.

매물 검색 인자는 지역·유형·최대 매매가격을 질문대로 전달했다. 현재 화면 질문은 `map_bounds`를 전달했다. 현재 Tool schema에는 면적, 전세 전용 유형, 병원·약국 POI 필터가 없으므로 그 조건의 정확도는 이번 범위에서 검증하지 않았다. 기존 매물 Tool의 `total_count`와 후보 `properties` 결과 구조는 유지됐고, 반환된 property ID로 `FIT_BOUNDS`·`HIGHLIGHT_PROPERTIES` Action을 만들었다. 반환된 Action은 production Pydantic 객체로 생성되므로 schema 검증을 통과했다.

법률 9문항은 모두 법률 Tool을 호출했고, 매물·지도·역·인접 지역 및 일반 대화 질문에는 법률 Tool false positive가 없었다. 이번 법률 답변에서 확인된 공식 법령명·조문·시행일·링크는 Tool 결과에 있었고, 찾지 않은 판례나 조문을 공식 검색 근거로 제시한 사례는 보이지 않았다. 이는 이번 9문항의 문항 단위 검토이며 기존 24문항 법률 regression을 다시 실행하거나 세부 claim 감사를 반복한 결과는 아니다.

## 반복 관찰 및 한계

1. 13번은 인접 법정동만 묻는 질문에 `SELECT_REGION`을 추가로 반환했다. schema는 유효하고 응답 내용에는 영향이 없지만, 명시적인 지도 조작 요청은 없었다. 경미한 불필요 Action 1개로 기록했다.
2. 26번 전세 매물 요청에는 현재 검색 Tool이 전세 유형을 필터링하지 못했다. Agent는 매매·월세·전세가 섞인 결과임을 밝히고 반환 후보에서 전세 1건을 추려 설명했다. 검색 결과 전체에 대한 전세 전용 조회나 지도 강조는 보장되지 않는다.
3. 지도와 매물 검색은 로컬 Spring의 현재 DB 결과에 의존한다. 0건은 Agent 실패로 분류하지 않았고, 실제 브라우저 화면과 외부 POI 검색은 이번 regression에서 평가하지 않았다.

첫 sandbox 실행은 OpenAI 연결 제한으로 중단됐으며 [`production_agent_integrated_regression_30_sandbox_infra_failed.csv`](production_agent_integrated_regression_30_sandbox_infra_failed.csv)에 별도 보존했다. 위 집계는 새 Run ID의 완료된 30문항 CSV만 사용한다. 이번 단계에서 production code·Prompt·Tool schema·RAG·Validator·Tool-loop·`.env`·Vector Store는 수정하지 않았고, Store는 검색만 수행했다. 회귀 결과에 따른 개선 작업은 진행하지 않았다.

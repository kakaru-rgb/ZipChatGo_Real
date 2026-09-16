# Production Law Agent + law_store_v2 real-user regression

실행일: 2026-09-16 (Asia/Seoul)

| 항목 | 값 |
|---|---|
| Run ID | `production-law-v2-real-user24-292cfb641d7f` |
| Git commit | `1fbbef94a99ca2d78cb32de077e94940b5cdc74c` |
| Agent model | `gpt-5.6-luna` |
| Corpus / Vector Store | `law_store_v2` / `vs_6aa764aaf2008191af233d99e6fd6cd2` |
| 실행 경로 | Production `OpenAIProvider` → `RealEstateLawSearchTool` → production A+B+C1 → `OpenAIVectorStoreLawRetriever` |
| 응답 저장 / retry | `store=false`; SDK retry 0; manual retry 0 |

질문은 시험 보기와 정답을 사용하지 않은 24개 실제 사용자형 문장으로 고정했다. Raw CSV는 [`production_law_v2_real_user24_live.csv`](production_law_v2_real_user24_live.csv)에 있다. `A/B/C1` 열과 `VectorSearchTrace`, `ToolResults`에는 질문별 검색 경로와 결과가 기록돼 있다. 아래 분류는 정답률이나 세부 claim별 감사가 아닌 사용자 관점의 문항 단위 판단이다.

Git commit은 기준 HEAD를 나타낸다. 실행에는 아직 커밋되지 않은 production A+B+C1 작업 트리 코드가 사용됐다.

## 질문별 결과

| ID | 범주 | 질문 주제 | 법률 Tool | 분류 |
|---:|:---:|---|---:|---|
| 1 | A | 전세보증금 보호 점검 | 1 | RAG_PLUS_MODEL_KNOWLEDGE |
| 2 | A | 집주인 변경과 전세 계약 | 1 | RAG_GROUNDED |
| 3 | A | 계약금 반환 대응 | 1 | MODEL_KNOWLEDGE_WITH_CAVEAT |
| 4 | A | 중개 설명과 집 상태 불일치 | 1 | RAG_PLUS_MODEL_KNOWLEDGE |
| 5 | B | 대항력 발생 시점 | 1 | RAG_GROUNDED |
| 6 | B | 묵시적 갱신 해지 효력 | 1 | RAG_GROUNDED |
| 7 | B | 갱신요구권 횟수·기간 | 1 | RAG_GROUNDED |
| 8 | B | 매매 거래신고 주체·기한 | 1 | RAG_GROUNDED |
| 9 | B | 임차권등기명령 요건 | 1 | RAG_GROUNDED |
| 10 | C | 주택임대차보호법과 임대인 승계 | 1 | RAG_GROUNDED |
| 11 | C | 공인중개사법 확인·설명 | 1 | RAG_GROUNDED |
| 12 | C | 상가건물 임대차보호법 갱신 | 1 | RAG_GROUNDED |
| 13 | D | 주택임대차보호법 제6조의2 | 1 | RAG_GROUNDED |
| 14 | D | 공인중개사법 제25조 | 1 | RAG_GROUNDED |
| 15 | D | 부동산 거래신고 법률 제3조 | 1 | RAG_GROUNDED |
| 16 | E | 우선변제권과 회수 위험 | 1 | RAG_PLUS_MODEL_KNOWLEDGE |
| 17 | E | 상가 갱신과 권리금 | 2 | RAG_GROUNDED |
| 18 | E | 공동명의 매매·등기·대출 | 4 | RAG_PLUS_MODEL_KNOWLEDGE |
| 19 | F | 최근 전세사기 판례 | 1 | RAG_GROUNDED |
| 20 | F | 최신 관리비 행정해석 | 1 | RAG_GROUNDED |
| 21 | G | 분묘기지권 최신 판례 | 1 | UNSUPPORTED_OVERCLAIM |
| 22 | G | 해외 작성 매도 위임장 | 2 | RAG_PLUS_MODEL_KNOWLEDGE |
| 23 | H | 집찾GO AI 채팅 | 0 | 비법률: 법률 Tool 미호출 |
| 24 | H | 채광·소음 현장 점검 | 0 | 비법률: 법률 Tool 미호출 |

## 집계와 관찰

| 지표 | 결과 |
|---|---:|
| 법률 질문 routing | 22/22 법률 Tool 호출 |
| 비법률 false law-Tool call | 0/2 |
| 평균 법률 Tool calls | 1.13/문항 전체, 1.23/법률 문항 |
| 평균 response rounds | 2.04 |
| 평균 latency | 13.68초 |
| Total tokens | 246,799 |
| Execution / Tool-loop limit error | 0 / 0 |
| A canonical `law_name` 필터 검색 | 12회 |
| B exact search hit / miss / semantic fallback | 5 / 0 / 0 |
| C1 semantic search | 22회; raw 110건, 관련도 처리 후 71건 |
| Fabricated source / Unsupported overclaim | 0 / 1 |

법률 질문의 provenance는 **RAG_GROUNDED 15**, **RAG_PLUS_MODEL_KNOWLEDGE 5**, **MODEL_KNOWLEDGE_WITH_CAVEAT 1**, **MODEL_KNOWLEDGE_NO_CAVEAT 0**, **UNSUPPORTED_OVERCLAIM 1**, **FABRICATED_SOURCE 0**이다. 비법률 2문항은 제외했다. `MODEL_KNOWLEDGE_WITH_CAVEAT`는 정상 fallback으로 집계했다.

Production Retriever가 실제 v2 Store에서 검색 결과를 반환했고 A의 metadata 필터와 B의 `law_name`+`article_number` exact 검색도 실제로 hit했다. C1 semantic trace에는 사용자 원문을 앞에 붙인 query가 없었다. B의 exact miss 경로와 법률 검색이 실제로 0건을 반환하는 fallback 분기는 이번 질문 세트에서 발생하지 않아 live 검증 범위 밖이다. 3번은 관련 근거가 약해 일반 지식과 caveat로 답했다.

출처가 민감한 19·20번은 최신 판례·행정해석 원문을 확인하지 못했다고 밝히고 검색된 법령을 설명했다. **21번**은 판례 원문을 찾지 못했다고 뒤에서 밝히면서도 앞에서 특정 2021년 대법원 전원합의체 판단을 단정적으로 귀속했다. 판례 자체의 존재 여부는 이번 Store-only 평가로 확정하지 않았으며, 확인되지 않은 구체적 출처 귀속을 `UNSUPPORTED_OVERCLAIM`으로 기록했다. 가짜 판례번호나 검색 밖 조문을 검색된 공식 citation으로 제시한 사례는 확인되지 않았다.

반복 관찰 사항은 관련도가 낮은 검색 결과가 계약금 반환·분묘기지권 질문에도 반환된 점이다(3·21번). 추가로 18번의 복합 질문은 법률 Tool을 4회 호출했지만 Tool-loop 제한 오류로 이어지지는 않았다. 이번 regression 중 production Prompt·RAG·Validator·Tool-loop·canonical catalog·`.env`는 수정하지 않았다. 기존 운영 Store와 v2 Store는 search-only로 사용했고 2024/2025 시험문제는 실행하지 않았다. C2.3은 production hard gate에 연결하지 않았다.

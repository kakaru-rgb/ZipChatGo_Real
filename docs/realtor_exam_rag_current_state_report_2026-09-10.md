# 공인중개사 시험 평가 및 법률 RAG 현재 상태 분석 보고서

- 작성 기준일: 2026-09-10
- 분석 대상: 현재 저장소 코드와 마지막으로 실행된 2024년 `공인중개사법령 및 중개실무` 40문항 평가 CSV
- 마지막 40문항 결과 파일: `C:\ajb\데이터\공인중개사_기출문제\공인중개사_시험평가_2024_gpt-4o-mini_law_filter_choice_evidence_40.csv`
- 비밀정보: OpenAI API Key와 Vector Store ID는 확인하거나 기록하지 않았다.
- 변경 범위: 이 보고서 파일만 생성했다. 코드, 평가 데이터, 원본 PDF, Vector Store는 변경하지 않았다.

## 먼저 알아야 할 핵심 결론

현재 시험 평가는 운영 중인 집찾GO 상담 Agent를 시험 Agent로 바꾼 구조가 아니다. 운영 챗봇과 분리된 `RealtorExamEvaluator`와 시험 전용 Prompt를 사용하되, 운영 Agent와 같은 `search_real_estate_law` Tool schema, `RealEstateLawSearchTool`, OpenAI Vector Store retriever를 재사용한다.

다만 현재 구현은 법령/중개실무 과목에서 모델이 필요성을 판단하기 전에 평가 Harness가 RAG 검색을 선행한다. 따라서 CSV의 `RAG사용여부=Y`는 “모델이 자율적으로 Tool을 선택했다”가 아니라 “평가 코드가 사전 검색을 실행했다”는 뜻이다. 현재 코드와 시험 Prompt 모두 법령 과목 검색을 사실상 강제한다.

또한 마지막 40문항 결과는 현재 코드보다 한 단계 이전 버전으로 실행됐다. 그 실행은 문항마다 5개 선택지를 각각 검색해 최대 25개 근거를 모델에 전달했다. 이후 현재 코드에는 근거 압축, 조합형 문항의 ㄱ·ㄴ·ㄷ별 검색, `temperature=0`, 일반 선택지 재검증이 추가됐지만 이 상태로 동일 40문항을 다시 실행하지 않았다. 그러므로 30%라는 점수는 마지막 실행 스냅샷의 결과이지, 현재 코드의 검증된 점수는 아니다.

## 1. 현재 AI Agent 전체 호출 흐름

### 평가 실행 흐름

```text
정규화된 시험 CSV의 한 문항
  → scripts/evaluate_realtor_exam.py::main()
  → evaluation/local_exam_pdf.py::load_exam_source_csv()
  → evaluation/realtor_exam.py::evaluate_exam()
  → evaluation/realtor_exam_agent.py::RealtorExamEvaluator.evaluate()
  → RealtorExamEvaluator._solve()
      → exam_law_grounding.py::detect_law_names()
      → RealtorExamEvaluator._prefetch_choice_evidence()
          → exam_law_grounding.py::build_evidence_search_targets()
          → RealEstateLawSearchTool.search()
          → OpenAIVectorStoreLawRetriever.search()
          → OpenAI vector_stores.search()
          → 점수 필터 및 결과 구조화
          → realtor_exam_agent.py::_select_compact_evidence()
      → exam_prompts.py::build_exam_input()
      → exam_law_grounding.py::render_choice_evidence()
      → OpenAI Responses API responses.create()
      → strict JSON schema 응답을 ExamAgentAnswer로 검증
  → realtor_exam_agent.py::_check_combination_choice()
      → 조합형/직접 선택지 후처리 및 필요 시 답 번호 변경
  → realtor_exam.py::make_result_row()
      → 공식 정답과 최종 예측 비교
  → realtor_exam.py::write_result_csv()
      → 평가 CSV 저장
```

### 중요한 분기

1. `LAW_VECTOR_STORE_ID`가 없으면 `law_search=None`으로 평가하며 RAG가 비활성화된다.
2. Vector Store가 있고 `_requires_law_search(question)`이 참이면 `_prefetch_choice_evidence()`가 모델 호출 전에 검색한다.
3. 현재 `_requires_law_search()`는 과목명에서 공백을 제거한 뒤 `법` 또는 `중개실무`가 들어 있으면 참이다.
4. 사전 검색 query가 하나라도 만들어지면 실제 Responses API 요청의 `tool_choice`는 `none`이다. 즉 모델은 이미 제공된 근거로 답하고, 그 라운드에서 Tool을 자율 호출하지 않는다.
5. 사전 검색이 없고 법령 검색이 필요하다고 판정된 특수 상황에서는 `tool_choice`가 특정 함수 `search_real_estate_law`로 강제된다.
6. 일반 과목에서 사전 검색이 없으면 Tool 목록은 제공되지만 `tool_choice`를 명시하지 않아 API 기본 동작인 auto가 적용될 수 있다.

### 운영 챗봇과의 관계

운영 챗봇은 `app/main.py → OpenAIProvider.generate()` 흐름을 사용한다. 시험 평가는 `OpenAIProvider.generate()`를 호출하지 않으며 운영 Prompt인 `app/prompts.py`도 사용하지 않는다. 다만 Tool schema와 실제 법령 검색 계층은 공유한다.

## 2. 관련 파일 목록과 역할

### 공인중개사 평가

| 파일 | 역할 |
|---|---|
| `ai-server/scripts/evaluate_realtor_exam.py` | `prepare/evaluate/all`, 연도·과목·개수·재개 옵션을 처리하는 CLI 진입점. OpenAI client, retriever, Tool, evaluator를 조립한다. |
| `ai-server/app/evaluation/local_exam_pdf.py` | PDF를 로컬에서 읽고 문항·선택지·공식 정답을 추출하며 정규화 CSV를 저장/로드한다. PDF 추출에는 LLM을 쓰지 않는다. |
| `ai-server/app/evaluation/exam_text_normalizer.py` | 띄어쓰기와 시험 표기 정규화, 조합형 문항 감지 등을 담당한다. |
| `ai-server/app/evaluation/realtor_exam.py` | `ExamQuestion`, `PreparedExam`, 데이터 검증, 평가 반복/재개, CSV 필드 생성, 정답 판정을 담당한다. |
| `ai-server/app/evaluation/realtor_exam_agent.py` | 시험 전용 Agent, RAG 사전 검색, Responses API 호출, 구조화 응답 검증, 조합/선택지 후처리를 담당한다. |
| `ai-server/app/evaluation/exam_prompts.py` | 운영 챗봇과 분리된 시험 전용 instruction과 문항별 user input을 만든다. |
| `ai-server/app/evaluation/exam_law_grounding.py` | 법령명 감지, 검색 target/query 생성, 검색 근거를 모델 입력용 JSON으로 렌더링한다. |
| `ai-server/app/evaluation/__init__.py` | 평가 패키지 표시 파일이다. |

### Agent와 OpenAI API 호출

| 파일 | 역할 |
|---|---|
| `ai-server/app/main.py` | FastAPI 운영 채팅 진입점. 시험 CLI에서는 직접 사용하지 않는다. |
| `ai-server/app/providers/openai_provider.py` | 운영 Agent와 공유하는 `search_real_estate_law` schema를 정의한다. 운영 챗봇의 Responses API Tool loop도 여기에 있으나 시험 평가는 그 loop를 사용하지 않는다. |
| `ai-server/app/providers/llm_provider.py` | 운영 Agent 응답/Tool handler 인터페이스. 시험 평가에는 직접 호출되지 않는다. |
| `ai-server/app/config.py` | `.env`에서 운영 모델, 시험 모델, API Key, Vector Store ID를 읽는다. |
| `.env` | 실제 환경변수. 현재 두 모델명이 설정되어 있다. Secret 값은 본 보고서에 기록하지 않는다. |
| `.env.example` | 공유 가능한 환경변수 이름과 예시를 제공한다. |

### Tool, RAG, Vector Store

| 파일 | 역할 |
|---|---|
| `ai-server/app/tools/real_estate_law.py` | Tool 인자 검증 후 retriever를 호출하고 결과 순서 및 grounding 안내를 추가한다. |
| `ai-server/app/schemas.py` | 내부 `LawSearchArguments(query, law_names)` 등을 정의한다. 공개 Tool schema에는 `query`만 노출된다. |
| `ai-server/app/retrievers/law_retriever.py` | 법령 검색 결과 모델, 응답 모델, retriever protocol과 오류를 정의한다. |
| `ai-server/app/retrievers/openai_vector_store_law_retriever.py` | OpenAI Vector Store 검색, metadata filter, score threshold와 결과 변환을 담당한다. |
| `ai-server/app/law/targets.py` | 수집 대상 15개 법령/하위법령과 민법 수집 조문 범위를 정의한다. |
| `ai-server/app/law/national_law_api.py` | 국가법령정보센터에서 법령 원문을 조회한다. |
| `ai-server/app/law/documents.py` | 법령 조문을 Vector Store 업로드용 문서와 metadata로 만든다. |
| `ai-server/app/law/models.py` | 법령 수집/문서 생성에 쓰는 데이터 모델이다. |
| `ai-server/app/law/vector_store.py` | 문서 파일 업로드, Vector Store 연결 및 상태/manifest 관리를 담당한다. |
| `ai-server/scripts/update_law_rag.py` | 법령 수집부터 문서 생성, 업로드, manifest 생성까지 수행하는 갱신 CLI다. 이번 분석에서는 실행하지 않았다. |
| `ai-server/data/law-rag/*/manifest.json` | 각 법령 RAG 갱신 실행의 로컬 manifest다. |

### 결과 검증 테스트

| 파일 | 역할 |
|---|---|
| `ai-server/tests/test_realtor_exam_evaluation.py` | 평가 loop, strict 응답, RAG trace, 조합 후처리와 CSV 결과를 검증한다. |
| `ai-server/tests/test_exam_law_grounding.py` | 법령명 감지, 검색 query/target, 근거 렌더링을 검증한다. |
| `ai-server/tests/test_local_exam_pdf.py` | PDF/CSV 로컬 추출과 정규화를 검증한다. |
| `ai-server/tests/test_real_estate_law_tool.py` | Tool argument 검증 및 retriever 전달을 검증한다. |
| `ai-server/tests/test_law_retriever.py` | Vector Store query, score 필터, metadata filter와 결과 변환을 검증한다. |
| `ai-server/tests/test_law_targets.py` | 법령 대상과 민법 범위를 검증한다. |
| `ai-server/tests/test_law_documents.py` | 조문 문서와 metadata 생성을 검증한다. |
| `ai-server/tests/test_law_vector_store.py` | 업로드/manifest 관련 동작을 검증한다. |
| `ai-server/tests/test_national_law_api.py` | 국가법령정보센터 응답 파싱을 검증한다. |
| `ai-server/tests/test_openai_provider.py` | 운영 Provider Tool loop 및 법령 응답 grounding을 검증한다. 시험 Agent와 공유 부품의 회귀 테스트다. |
| `ai-server/tests/test_prompts.py` | 운영 챗봇 Prompt를 검증한다. 시험 Prompt와는 별개다. |

## 3. 현재 사용 중인 LLM 설정

| 항목 | 현재 값 |
|---|---|
| 운영 챗봇 모델 | `OPENAI_MODEL=gpt-4o-mini` |
| 시험 평가 모델 | `OPENAI_EXAM_EVALUATION_MODEL=gpt-4o-mini` |
| API | OpenAI Responses API (`client.responses.create`) |
| temperature | 현재 시험 코드에서 `0` |
| 응답 저장 | `store=False` |
| 출력 형식 | `text.format`의 strict JSON schema |
| 최대 재시도 | 3회, 실패 사이 1초/2초 backoff |
| 최대 Tool round | 5회 |
| 시험 Tool 목록 | `search_real_estate_law` 하나 |

시험 요청은 `model`, `instructions`, `input`, `text.format`, `temperature=0`, `store=False`, `tools`를 전달한다. `max_output_tokens`, `top_p`, seed 등은 별도로 설정하지 않는다.

마지막 40문항 평가 당시에는 현재 코드의 `temperature=0` 변경 전 상태였으므로 결정론적 실행이 아니었다. 실제로 직전 40문항 실행과 비교했을 때 40개 예측이 모두 달라졌고, 정답 4개가 새로 생기는 동시에 기존 정답 6개가 오답이 되어 35%에서 30%로 하락했다.

## 4. 현재 평가 instruction/system prompt

Responses API의 `instructions`에 전달되는 현재 문자열 전문은 다음과 같다.

```text
당신은 공인중개사 객관식 시험을 푸는 시험 평가 전용 AI입니다.
이 지시는 집찾GO 운영 챗봇의 상담 Prompt와 완전히 독립적입니다.

- 사용자가 제공한 문제와 1번부터 5번까지의 선택지만 사용해 정답 하나를 고릅니다.
- 공식 정답은 제공되지 않으므로 추측해서 있다고 가정하지 않습니다.
- 계산 문제는 식, 부호, 단위와 선택지 일치 여부를 답하기 전에 다시 확인합니다.
- ㄱ·ㄴ·ㄷ·ㄹ·ㅁ은 문제의 보기일 수 있으며, 최종 답은 반드시 1~5 중 하나입니다.
- ㄱ·ㄴ·ㄷ처럼 여러 항목이 결합된 문제는 각 항목의 참·거짓 또는 빈칸 값을
  먼저 독립적으로 판단하고, 완성된 조합을 1~5번 선택지와 하나씩 대조합니다.
- 복합 선택지의 일부만 보고 답하지 말고 모든 항목이 일치하는 선택지를 고릅니다.
- 복합 보기/빈칸 조합형에서는 resolved_items에 ㄱ·ㄴ·ㄷ별 최종 판단값을
  각각 기록합니다. 참·거짓 조합형의 값은 반드시 `참` 또는 `거짓`으로
  기록하고, 일반 문제에서는 resolved_items를 빈 배열로 반환합니다.
- 모든 문제에서 선택지 1~5를 각각 독립적으로 검토하고 choice_judgments에
  선택지 번호, 참·거짓 판단, 판단 근거와 사용한 evidence_ids를 빠짐없이
  기록한 뒤 최종 답을 고릅니다.
- choice_judgments의 참·거짓은 그 선택지 내용 자체가 법적으로 맞는지를 뜻합니다.
  `틀린 것`, `옳지 않은 것`, `아닌 것`, `할 수 없는 업무`를 묻더라도 이 의미를
  바꾸지 말고, 거짓으로 판정한 선택지를 최종 답으로 고릅니다.
- 선택지가 업무명처럼 짧으면 문제 문장과 결합해 완전한 명제로 판단합니다.
  예를 들어 `함께 할 수 없는 업무` 문제에서는 각 업무를 실제로 함께 할 수
  있는지를 참·거짓으로 판단합니다.
- 법령 과목에서는 집찾GO의 기존 법령 검색 Tool을 최소 한 번 사용해야 하며,
  검색 결과를 선택지 1~5의 판단 근거와 각각 대조합니다.
- 시험 전용 검색 결과가 제공되면 search_targets와 연결된 `E번호` 근거를 우선
  사용합니다. 동일 조문이 여러 선택지나 ㄱ·ㄴ·ㄷ 지문에 관련될 수 있으므로,
  내용이 직접 관련된 경우 다른 target과 연결된 E번호도 사용할 수 있습니다.
  관련 근거가 없으면 evidence_ids를 빈 배열로 두고 basis에 `근거 부족`을 표시합니다.
- 법령이 아닌 과목은 문제 내용을 보고 Tool 사용 여부를 판단합니다.
- 검색 결과가 부족해도 시험 문제에는 반드시 가장 타당한 선택지 하나를 답합니다.
- 검색 결과에 없는 법령명이나 조문 번호를 만들어내지 않습니다.
- 실제 법률 상담처럼 행동하거나 집찾GO 운영 챗봇의 안전 응답을 재사용하지 않습니다.
- explanation에는 판단 근거를 간결하게 작성합니다.
```

### 최종 입력 조합

`instructions`와 별도로 `input`의 user message에는 다음이 합쳐진다.

```text
과목: {subject}
문항번호: {question_no}
문제요구: 선택지 내용 자체가 법적으로 참/거짓인 항목을 고른다.
{조합형이면 4단계 풀이 절차}
문제: {question}
선택지:
1. ...
...
5. ...

{사전 검색이 있으면 search_targets 및 E번호 근거 JSON}
```

조합형은 `is_combination_question()`이 감지하며, “각 항목 독립 판단 → 조합 생성 → 선택지 대조 → 하나 선택” 지시가 추가된다. 모델에는 공식 정답이 전달되지 않는다.

### strict 응답 schema

모델은 다음 네 필드를 반드시 반환한다.

- `predicted_answer`: 1~5 정수
- `choice_judgments`: 정확히 5개. 각 항목은 `choice_number`, `judgment`(`참`/`거짓`), `basis`, `evidence_ids`
- `resolved_items`: ㄱ~ㅎ label과 판단값 배열
- `explanation`: 설명 문자열

현재 코드는 evidence ID가 `E숫자` 형식인지 검증한다.

## 5. 법률 Tool 정의

### 공개 Tool schema 전문

```json
{
  "type": "function",
  "name": "search_real_estate_law",
  "description": "국가법령정보센터에서 수집해 색인한 현행 부동산 법령 조문을 검색합니다. 임대차, 대항력, 우선변제권, 보증금, 부동산 계약의 법적 효력, 상가 임대차, 매매·계약금·계약 해제, 부동산 등기, 집합건물 관리, 개업공인중개사의 확인·설명 의무나 책임, 부동산 거래신고 의무·기한처럼 법령 근거가 필요한 질문에 사용합니다. 지도 이동, 매물 검색·추천, 면적·가격 확인에는 사용하지 않습니다.",
  "parameters": {
    "type": "object",
    "properties": {
      "query": {
        "type": "string",
        "description": "사용자의 질문을 법령 검색에 적합한 핵심 법률 용어로 정리한 검색어. 예: '중개사가 중요 내용을 설명하지 않았어'는 '공인중개사 중개대상물 확인 설명 의무'로 검색합니다.",
        "minLength": 1,
        "maxLength": 500
      }
    },
    "required": ["query"],
    "additionalProperties": false
  },
  "strict": true
}
```

내부 Pydantic 인자는 `query` 외에 `law_names: list[str]` 최대 8개를 받을 수 있다. 이 값은 모델에게 공개된 schema에는 없으며 평가 Harness가 감지한 법령명을 Tool 호출 직전에 주입한다.

### 호출 조건과 강제 여부

- 운영 챗봇: 법률상 권리·의무·효력·기한·책임이 필요한 질문에 모델이 Tool을 선택하는 일반 Tool loop다.
- 시험 평가 현재 코드: 과목명에 `법` 또는 `중개실무`가 포함되면 Harness가 모델보다 먼저 검색한다. 이 경로는 강제 사전 검색이다.
- 사전 검색 성공 후 모델 요청: `tool_choice="none"`이다. 모델은 새 검색을 선택할 수 없다.
- 사전 검색 query가 없는데 법령 검색 대상이면 특정 function을 `tool_choice`로 지정해 강제한다.
- 그 외에는 명시적 `tool_choice`가 없어 API의 auto 동작에 맡긴다.

### query 생성 주체

현재 법령 시험의 일반적인 query는 모델이 아니라 `exam_law_grounding.py`가 만든다.

- 현재 코드의 일반 선택지형: `{감지된 법령명들} {선택지 본문} 쟁점: {문제 stem}`
- 현재 코드의 조합형: `{감지된 법령명들} {ㄱ/ㄴ/ㄷ 개별 지문} 쟁점: {문제 stem}`
- 길이: 최대 400자
- 모델 Tool loop가 실제 호출되는 예외 경로에서는 모델이 공개 schema의 `query`를 만든다.

마지막 40문항 실행 당시 query는 현재 코드와 달랐다. 당시에는 5개 선택지마다 다음 형식으로 최대 500자를 생성했다.

```text
{법령명들} 선택지 {n}: {선택지} 문제 기준: {전체 문제}
```

## 6. Vector Store 검색 로직

### OpenAI 검색 요청

```python
client.vector_stores.search(
    vector_store_id=<비공개>,
    query=normalized_query,
    max_num_results=5,
    rewrite_query=False,
    filters=<선택적 law_name filter>
)
```

### 주요 설정

| 항목 | 값 |
|---|---|
| 1회 검색 top-k | 최대 5 |
| 절대 score threshold | 0.5 |
| 상대 threshold | 해당 검색의 최고 score × 0.9 |
| 최종 cutoff | `max(0.5, best_score * 0.9)` |
| query rewrite | `False` |
| metadata filter | 감지된 법령명이 있으면 `law_name == ...`; 여러 개면 OR |
| 정렬 | OpenAI 결과 순서, threshold 통과 후 rank 재부여 |

법령명이 명시되지 않거나 감지되지 않으면 metadata filter를 쓰지 않는다. 특히 과목명이 포괄적인 `공인중개사법령 및 중개실무`인 것만으로는 공인중개사법 family를 강제하지 않게 되어 있다. 민법·판례 문제까지 같은 과목에 포함되기 때문이다.

### LLM에게 전달되는 결과

Retriever 결과는 `rank`, `score`, `law_name`, `law_type`, `article_number`, `article_title`, `text`, 시행일/공포일, 법령 ID, 공식 URL, filename 등을 가진 JSON이다. `RealEstateLawSearchTool`이 `result_order=relevance_descending`과 grounding 안내를 붙인다.

현재 코드는 각 target에서 최대 2개, 문항 전체에서 중복 제거 후 최대 8개 근거만 선택한다. 동일한 법령명+조문 번호는 하나로 합치고 `E1`, `E2` 형태의 evidence ID와 관련 target ID를 붙여 user input에 직렬화한다. 조문 정보가 없으면 filename+정규화 text로 중복 판정한다.

마지막 40문항 실행은 이 압축 로직 적용 전이므로 선택지당 최대 5개, 문항당 최대 25개를 `C1-R1` 같은 ID로 전달했다. 총 975개 결과 중 내용 기준 고유 근거는 약 413개, 중복은 약 562개였다. 문항당 근거 문자열은 평균 약 23,916자였다.

### 검색 결과 0건 처리

- Retriever는 `total_count=0`, `results=[]`를 반환한다.
- 사전 검색에서는 해당 target의 candidates가 빈 배열이 되며, 모델에게 근거 없는 target으로 전달된다.
- 검색 자체가 실패하면 target에 error 문자열을 기록하고 candidates를 비운다.
- 시험 Prompt는 근거가 없어도 가장 타당한 선택지 하나를 반드시 고르게 한다.
- 마지막 40문항에는 문항 전체 검색 결과가 0건인 사례가 없었다.

## 7. 공인중개사 시험 평가 Harness

### 한 문항 처리 단계

1. CSV 행을 `ExamQuestion`으로 로드하고 문제·선택지 5개·공식 정답 형식을 검증한다.
2. 과목 필터와 `limit`을 적용한다.
3. 출력 CSV에 오류 없이 완료된 동일 `문항키`가 있으면 resume 시 건너뛴다.
4. 법령명을 감지하고, 현재 코드는 법령/중개실무 과목이면 target별 사전 검색을 수행한다.
5. 시험 instruction, 문제, 선택지, 검색 근거를 Responses API에 보낸다.
6. strict JSON을 `ExamAgentAnswer`로 검증한다.
7. `_check_combination_choice()`가 resolved items 또는 choice judgments와 선택지를 다시 대조한다.
8. 후처리가 필요하다고 판단하면 최초 번호를 다른 번호로 바꾼다.
9. 마지막에만 공식 정답과 비교해 O/X를 만든다.
10. 매 문항 종료 후 CSV를 임시 파일에 쓴 뒤 replace하여 중간 결과를 보존한다.

### CSV 핵심 필드의 생성 시점

| 필드 | 생성 코드와 의미 |
|---|---|
| `모델원래예측` | `RealtorExamEvaluator._solve()`가 받은 `answer.predicted_answer`. 이름과 달리 RAG 이전 예측이 아니라 검색 근거를 본 뒤 나온 모델의 최초 구조화 응답이다. |
| `선택지별판단` | 같은 응답의 `choice_judgments`를 JSON으로 저장한다. |
| `판단조합` | 같은 응답의 `resolved_items`를 JSON으로 저장한다. 모델이 만든 값이다. |
| `조합검증결과` | `_check_combination_choice()`의 결과 문자열. `일치`, `번호보정:a->b`, `판단조합부족`, `선택지대조불가`, `해당없음`, `선택조건대조불가` 등이 가능하다. |
| `챗봇예측` | 후처리 후 `final_prediction`. 실제 O/X 판정에 사용한다. |
| `공식정답` | 입력 CSV의 정답. 모델 호출에는 포함하지 않고 `make_result_row()`에서만 비교한다. |

중간 단계에서 최초 답은 변경될 수 있다. 실제 마지막 40문항에서도 8번 `5→2`, 27번 `4→2`, 34번 `4→3`, 39번 `2→1`로 바뀌었다. 네 건 모두 공식 정답에는 맞지 않았고, 특히 34번은 모델의 최초 답 4가 공식 정답이었는데 후처리가 3으로 덮어써 오답이 됐다.

## 8. 정답 추출 및 후처리

### 1~5 정답 번호 추출

현재 시험 Agent는 자유 텍스트에서 정규식으로 숫자를 추출하지 않는다. OpenAI strict JSON schema가 `predicted_answer`를 1~5 정수로 제한하고, `ExamAgentAnswer` Pydantic 모델이 다시 검증한다. 파싱 또는 schema 검증 실패 시 최대 3회 전체 문항 요청을 재시도한다.

### ㄱ/ㄴ/ㄷ 조합을 선택지 번호로 바꾸는 방법

1. 선택지가 `ㄱ = 값; ㄴ = 값` 형태라면 `_parse_assignments()`가 label/value 사전을 만든다.
2. 모델의 `resolved_items` 값을 공백·쉼표·구두점을 제거해 비교한다.
3. 필요한 label 전체가 있고 정확히 하나의 선택지가 완전히 일치할 때 그 번호를 사용한다.
4. 선택지가 `ㄱ, ㄷ` 같은 label 집합이면 `_parse_label_set()`이 label set으로 만든다.
5. 모델의 `참/거짓`을 boolean으로 변환한다.
6. 문제가 “틀린 것/옳지 않은 것/아닌 것/해당하지 않는 것/할 수 없는 업무/할 수 없는 것/없는 업무”를 묻는지에 따라 거짓 또는 참 label 집합을 고른다.
7. 그 집합과 정확히 일치하는 선택지 하나가 있으면 해당 번호로 보정한다.
8. 조합형이 아니면 현재 코드의 `_check_direct_choice()`가 다섯 `choice_judgments` 중 문제 요구와 맞는 판단이 정확히 하나일 때 그 번호로 보정한다.

### 답 덮어쓰기

있다. `_check_assignment_choice()`, `_check_label_set_choice()`, `_check_direct_choice()`가 `predicted_answer`와 다른 유일한 일치 번호를 찾으면 `번호보정:원래→새번호`를 기록하고 최종 답을 덮어쓴다. 공식 정답은 이 결정에 사용되지 않는다.

마지막 40문항은 현재의 direct-choice 보정 추가 전 실행이지만 조합형 보정은 이미 활성화돼 있었다. 조합 감지, 모델의 resolved_items, 문제의 부정 표현 중 하나라도 틀리면 올바른 최초 답을 오답으로 바꿀 수 있다.

## 9. 현재 40문제 평가 결과 요약

아래 수치는 마지막 실제 CSV의 확정값이다.

| 지표 | 결과 |
|---|---:|
| 전체 문항 | 40 |
| 정답 | 12 |
| 오답 | 28 |
| 판정 오류 행 | 0 |
| 전체 정답률 | 30.0% |
| RAG 사용 문제 | 40 |
| RAG 미사용 문제 | 0 |
| RAG 사용 시 정답률 | 12/40 = 30.0% |
| RAG 미사용 시 정답률 | 산출 불가(표본 0) |
| 검색 결과 0건 문제 | 0 |
| 문항당 검색 결과 | 최소 20, 최대 25, 평균 24.375 |

모든 문항이 RAG를 사용했으므로 이 결과만으로 “RAG가 점수를 올렸는지”를 비교할 수 없다. 동일 문항의 비검색 대조군이 없고, `모델원래예측`도 비검색 baseline이 아니다.

## 10. 오답 사례 10개 상세 Trace

아래 trace는 마지막 40문항 CSV에 실제 저장된 값이다. 각 문항은 Harness가 선택지 1~5에 대해 다음 exact query 형식을 사용해 5회 검색했다.

```text
{감지 법령명} 선택지 {번호}: {해당 선택지} 문제 기준: {아래에 적은 문제 전문}
```

따라서 각 사례의 “Tool query”에는 중복되는 문제 전문 대신 감지 법령명과 5개 target을 명시한다. “Top-5”는 다섯 검색 결과를 합쳐 처음 나타난 고유 결과 기준이며, 내용은 해당 조문이 무엇을 다루는지 요약한 것이다.

### 사례 1 — 문항 1

- 문제: 공인중개사법령상 공인중개사 정책심의위원회에 관한 설명으로 옳은 것은?
- 공식 정답: 5
- 최초 모델 판단: 4
- Tool 호출 여부: Y. 모델 자율 호출이 아니라 Harness 사전 검색 5회
- Tool query: 법령 filter `공인중개사법/시행령/시행규칙`; target은 선택지 1~5 전문
- 검색 Top-5: 공인중개사법 제35조 0.8572(자격 취소), 시행령 제10조 0.8241(시험 합격자 결정), 시행령 제5조 0.8193(시험방법), 시행규칙 제2조 0.8069(응시원서), 공인중개사법 제2조의2 0.8067(정책심의위원회)
- 검색 내용 요약: 직접 관련된 정책심의위원회 조문은 고유 결과 중 5위였고, 상위 네 건은 시험·자격 등 다른 주제였다.
- 검색 후 모델 판단: 선택지 1·2·3·5 거짓, 4 참. 시·도지사가 심의결과를 따라야 한다고 해석했다.
- 중간 검증 결과: `해당없음`
- 최종 답: 4

### 사례 2 — 문항 2

- 문제: 공인중개사법령상 법인인 개업공인중개사가 다른 법률에 규정된 경우를 제외하고 중개업과 함께 할 수 없는 업무는?
- 공식 정답: 1
- 최초 모델 판단: 5
- Tool 호출 여부: Y, Harness 사전 검색 5회
- Tool query: 법령 filter `공인중개사법/시행령/시행규칙`; 다섯 업무 선택지를 각각 target으로 검색
- 검색 Top-5: 공인중개사법 제18조의2 0.8443(표시·광고), 제13조 0.8404(사무소 설치), 시행령 제24조 0.8362(손해배상 보장), 공인중개사법 제14조 0.8345(법인의 겸업 제한), 시행령 제13조 0.8313(중개사무소 등록)
- 검색 내용 요약: 정답 판단의 핵심인 법 제14조는 고유 결과 4위였다. 더 높은 세 건은 문제 핵심과 직접 관련성이 낮았다.
- 검색 후 모델 판단: 선택지 1의 근거에서 “포함할 수 있다”와 “할 수 없다”를 동시에 서술했고, 2~4도 허용된다는 근거로 거짓 판정했으며 5만 참으로 판정했다.
- 중간 검증 결과: `해당없음`
- 최종 답: 5

### 사례 3 — 문항 4

- 문제: 개업공인중개사 甲과 소속공인중개사 乙의 교육, 확인·설명서 서명, 고용 종료 후 실무교육에 관한 ㄱ·ㄴ·ㄷ 중 틀린 것을 모두 고르는 문제
- 공식 정답: 5
- 최초 모델 판단: 3
- Tool 호출 여부: Y, Harness 사전 검색 5회
- Tool query: 법령 filter `공인중개사법/시행령/시행규칙`; targets `ㄱ`, `ㄴ`, `ㄱ·ㄷ`, `ㄴ·ㄷ`, `ㄱ·ㄴ·ㄷ`
- 검색 Top-5: 공인중개사법 제34조 0.7933(교육), 시행규칙 제8조 0.7881(고용인 신고), 법 제25조 0.7844(확인·설명), 시행규칙 제9조 0.7812(인장등록), 시행령 제24조 0.7730(손해배상 보장)
- 검색 내용 요약: 교육·고용·확인설명 관련 핵심 조문은 검색됐으나 모델의 근거 문장에 “틀리다고 할 수 없다”면서 거짓으로 표시하는 모순이 있었다.
- 검색 후 모델 판단: resolved `ㄱ=거짓, ㄴ=거짓, ㄷ=참`; predicted 3
- 중간 검증 결과: `선택지대조불가`
- 최종 답: 3

### 사례 4 — 문항 8

- 문제: 중개사무소 안에 게시해야 하는 것 ㄱ 자격증 원본, ㄴ 보증 설정 증명서류, ㄷ 고용신고서, ㄹ 실무교육 수료 확인증 중 모두 고르는 문제
- 공식 정답: 1
- 최초 모델 판단: 5
- Tool 호출 여부: Y, Harness 사전 검색 5회
- Tool query: 법령 filter `공인중개사법/시행령/시행규칙`; targets `ㄱ·ㄴ`, `ㄱ·ㄹ`, `ㄴ·ㄷ`, `ㄷ·ㄹ`, `ㄱ·ㄴ·ㄹ`
- 검색 Top-5: 공인중개사법 제34조 0.8041(교육), 시행규칙 제8조 0.8025(고용인 신고), 시행령 제24조 0.7907(손해배상 보장), 법 제25조 0.7876(확인·설명), 시행령 제16조 0.7780(공동사용)
- 검색 내용 요약: 게시 의무를 직접 정하는 핵심 조문보다 교육·신고·보증 관련 주변 조문이 검색됐다.
- 검색 후 모델 판단: resolved `ㄱ=참, ㄴ=거짓, ㄷ=거짓, ㄹ=참`; predicted 5
- 중간 검증 결과: `번호보정:5->2`
- 최종 답: 2. 후처리도 공식 정답 1에는 도달하지 못했다.

### 사례 5 — 문항 10

- 문제: 개업공인중개사와 중개의뢰인의 일반/전속 중개계약에 관한 설명 중 틀린 것은?
- 공식 정답: 2
- 최초 모델 판단: 5
- Tool 호출 여부: Y, Harness 사전 검색 5회
- Tool query: 법령 filter `공인중개사법/시행령/시행규칙`; 다섯 중개계약 설명을 각각 검색
- 검색 Top-5: 공인중개사법 제23조 0.8096(전속중개계약), 제18조의2 0.7956(표시·광고), 제32조 0.7809(중개보수), 제13조 0.7777(사무소 설치), 시행령 제24조 0.7747(손해배상 보장)
- 검색 내용 요약: 법 제23조가 직접 관련됐지만 이후 결과 대부분은 문제와 간접적이었다.
- 검색 후 모델 판단: 선택지 2를 참으로, 3과 5를 거짓으로 판단했고 설명에서도 “틀린 설명은 3번과 5번”이라고 한 뒤 5를 선택했다.
- 중간 검증 결과: `해당없음`
- 최종 답: 5

### 사례 6 — 문항 13

- 문제: 개업공인중개사의 금지행위에 해당하는 ㄱ·ㄴ·ㄷ·ㄹ 중 모두 고르는 문제
- 공식 정답: 3
- 최초 모델 판단: 5
- Tool 호출 여부: Y, Harness 사전 검색 5회
- Tool query: 법령 filter `공인중개사법/시행령/시행규칙`; 각 label 조합 선택지를 target으로 검색
- 검색 Top-5: 공인중개사법 제33조 0.8834(금지행위), 제32조 0.8034(중개보수), 제18조의2 0.7976(표시·광고), 시행령 제24조 0.7953(손해배상 보장), 법 제51조 0.7940(과태료)
- 검색 내용 요약: 최상위에 정확한 금지행위 조문이 검색됐지만, 모델이 ㄹ까지 참으로 포함했다.
- 검색 후 모델 판단: resolved `ㄱ=거짓, ㄴ=참, ㄷ=참, ㄹ=참`; predicted 5
- 중간 검증 결과: `일치` — 모델이 만든 잘못된 조합과 선택지 5가 일치한다는 뜻이지 공식 정답과 일치한다는 뜻이 아니다.
- 최종 답: 5

### 사례 7 — 문항 27

- 문제: 토지거래허가구역에서 허가 규정이 적용되지 않는 ㄱ 외국인 토지취득 허가, ㄴ 공익사업 환매, ㄷ 한국농어촌공사 농지 매매를 모두 고르는 문제
- 공식 정답: 5
- 최초 모델 판단: 4
- Tool 호출 여부: Y, Harness 사전 검색 5회
- Tool query: 법령 filter `부동산 거래신고 등에 관한 법률/시행령/시행규칙`; targets `ㄱ`, `ㄴ`, `ㄱ·ㄷ`, `ㄴ·ㄷ`, `ㄱ·ㄴ·ㄷ`
- 검색 Top-5: 법 제15조 0.7988(선매), 시행령 제5조 0.7978(외국인 토지취득), 시행규칙 제3조 0.7930(신고), 법 제12조 0.7868(허가기준), 법 제25조의2 0.7851(신고포상금)
- 검색 내용 요약: 외국인 취득과 허가기준 주변 조문은 있었지만 적용 제외를 직접 열거한 근거가 상위에 명확히 제시되지 않았다.
- 검색 후 모델 판단: resolved `ㄱ=거짓, ㄴ=참, ㄷ=거짓`; 설명에는 “ㄴ과 ㄷ, 선택지 4”라고 써 resolved 값과도 모순됐다.
- 중간 검증 결과: `번호보정:4->2`
- 최종 답: 2

### 사례 8 — 문항 34

- 문제: 주택임대차보호법상 임차권등기명령의 송달·최우선변제·대항력 유지·보증금반환과 말소의무에 관한 ㄱ·ㄴ·ㄷ·ㄹ 중 옳은 것을 모두 고르는 문제
- 공식 정답: 4
- 최초 모델 판단: 4
- Tool 호출 여부: Y, Harness 사전 검색 5회
- Tool query: 법령 filter `주택임대차보호법/시행령`; targets `ㄴ·ㄷ`, `ㄱ·ㄴ·ㄹ`, `ㄱ·ㄷ·ㄹ`, `ㄴ·ㄷ·ㄹ`, `ㄱ·ㄴ·ㄷ·ㄹ`
- 검색 Top-5: 시행령 제10조 0.8366(소액보증금 범위), 법 제3조 0.8349(대항력), 제3조의2 0.8314(보증금 회수), 제8조 0.8273(소액보증금 보호), 제3조의3 0.8260(임차권등기명령)
- 검색 내용 요약: 핵심 제3조의3은 검색됐지만 고유 결과 5위였고, 모델의 선택지별 판단과 resolved items가 서로 달랐다.
- 검색 후 모델 판단: choice 4는 참이며 predicted 4. 그러나 resolved는 `ㄱ=참, ㄴ=거짓, ㄷ=참, ㄹ=참`으로 선택지 3과 일치했다.
- 중간 검증 결과: `번호보정:4->3`
- 최종 답: 3. 후처리가 맞았던 최초 답을 오답으로 변경한 명확한 사례다.

### 사례 9 — 문항 39

- 문제: 판례상 분묘기지권의 지료 발생, 존속기간, 미등기 대항력에 관한 ㄱ·ㄴ·ㄷ 중 옳은 것을 모두 고르는 문제
- 공식 정답: 4
- 최초 모델 판단: 2
- Tool 호출 여부: Y, Harness 사전 검색 5회
- Tool query: 법령명 filter 없음; targets `ㄴ`, `ㄱ·ㄴ`, `ㄱ·ㄷ`, `ㄴ·ㄷ`, `ㄱ·ㄴ·ㄷ`
- 검색 Top-5: 공인중개사법 제35조 0.8353(자격취소), 집합건물법 제48조 0.8260(구분소유권 매도청구), 주택임대차보호법 제3조의2 0.8235(보증금 회수), 공인중개사법 제2조 0.8215(정의), 상가건물임대차보호법 제6조 0.8199(임차권등기명령)
- 검색 내용 요약: 분묘기지권 판례와 직접 관련된 근거가 사실상 없었다. 현재 Vector Store가 판례를 포함하지 않는 한계를 그대로 보여준다.
- 검색 후 모델 판단: resolved `ㄱ=거짓, ㄴ=참, ㄷ=거짓`; predicted 2. ㄷ의 미등기 대항력을 잘못 부정했다.
- 중간 검증 결과: `번호보정:2->1`
- 최종 답: 1

### 사례 10 — 문항 40

- 문제: 장사 등에 관한 법령상 개인/가족묘지 신고·허가, 면적과 봉분, 설치기간, 기간 종료 후 조치 중 옳은 것은?
- 공식 정답: 2
- 최초 모델 판단: 5
- Tool 호출 여부: Y, Harness 사전 검색 5회
- Tool query: 법령명 filter 없음; 다섯 묘지 관련 선택지를 각각 target으로 검색
- 검색 Top-5: 공인중개사법 제13조 0.8024(사무소 설치), 제20조 0.7727(이전신고), 부동산거래신고법 제15조 0.7648(선매), 동 시행규칙 제11조 0.7575(토지 관련 신고), 동 시행령 제14조 0.7563(토지 이용 의무)
- 검색 내용 요약: 대상 법령인 장사 등에 관한 법률이 Vector Store 대상에 없어서 상위 결과가 모두 무관했다.
- 검색 후 모델 판단: 1~4 거짓, 5 참. 선택지 1·2는 `근거 부족`으로 표시하면서도 5를 단정했다.
- 중간 검증 결과: `해당없음`
- 최종 답: 5

## 11. 현재 코드에서 의심되는 부분

### Tool Routing 문제

1. 법령/중개실무 과목은 `_requires_law_search()`만으로 무조건 사전 검색된다. 사용자가 요구한 “LLM이 필요하다고 판단할 때만”과 현재 구현이 일치하지 않는다.
2. Prompt도 “법령 과목에서는 최소 한 번 사용”을 요구해 강제를 이중화한다.
3. 사전 검색이 실행되면 `tool_choice=none`이므로 모델이 검색 필요성을 결정하거나 query를 개선해 재검색할 기회가 없다.
4. `RAG사용여부`가 Harness 검색과 모델 자율 Tool 호출을 구분하지 않는다.
5. 비법령/판례 전용 문제까지 과목명 때문에 검색되며, corpus에 없는 주제에 무관한 결과가 공급된다.

### Retrieval 문제

1. 마지막 실행은 문항당 평균 24.375개, 평균 약 23.9KB 근거로 과도했고 중복도 약 57.6%였다.
2. 상대 threshold는 “가장 관련 있는 결과”가 실제로 무관해도 그 주변 결과를 통과시킨다. 절대 0.5도 실제 정답 근거 품질을 보장하지 않는다.
3. 법령명이 감지되지 않은 문항은 전체 Store를 검색해 분묘기지권·장사법 문제에 공인중개사법 등이 상위로 나온다.
4. 마지막 실행의 선택지 query가 `ㄱ`, `ㄴ` 같은 짧은 조합을 직접 검색해 의미 정보가 약하다.
5. 현재 Store는 판례·행정해석과 장사법 등을 포함하지 않으며, 민법도 지정 범위만 포함한다.
6. 2024년 시험을 현행 2026년 법령 문서로 푸는 시점 불일치가 있다. 사용자가 시행일 필터 추가는 원하지 않았지만, 평가 해석상 한계로 남는다.
7. 현재 최대 8개 압축은 노이즈를 줄이지만 필요한 조문이 3위 이하에 있으면 탈락시킬 수 있다.

### LLM Reasoning 문제

1. `gpt-4o-mini`가 근거와 판정을 반대로 쓰거나 explanation, choice judgment, resolved items 사이에서 모순을 보였다.
2. 조합형에서 개별 지문의 진위를 틀리면 deterministic mapping은 그 오류를 정확하게 최종 번호로 변환할 뿐 정답으로 고쳐주지 못한다.
3. 모든 선택지에 근거와 evidence ID를 요구해 핵심 조문 판단보다 형식 채우기에 모델 용량을 쓸 수 있다.
4. 부정형 질문, 선택지 자체의 참/거짓, 최종 선택 조건을 동시에 처리하면서 polarity 혼동이 발생한다.
5. 마지막 실행은 temperature 고정 전이어서 재현성이 낮았다. 현재 `temperature=0`이 추가됐지만 정확도 개선 효과는 미검증이다.
6. 한 번의 최종 reasoning 호출만 있으며, 불충분한 근거를 감지해 query를 개선하는 실제 Agent loop가 대부분 차단된다.

### Evaluation Harness / 후처리 문제

1. `모델원래예측`은 RAG 전 baseline이 아니라 RAG 후 최초 답이라 명칭이 오해를 만든다.
2. `RAG사용여부=Y`는 검색 실행 여부일 뿐 모델이 근거를 실제 사용했는지, Tool을 자율 선택했는지 나타내지 않는다.
3. 동일 문항의 no-RAG 대조군이 없어 RAG 기여도를 측정할 수 없다.
4. 후처리가 모델의 잘못된 resolved items를 더 신뢰해 맞는 답을 틀린 답으로 바꿀 수 있다. 문항 34가 실제 사례다.
5. `조합검증결과=일치`는 공식 정답과 일치가 아니라 모델 조합과 선택지 번호의 내부 일치다.
6. label/assignment 정규식과 조합형 감지에 의존하므로 PDF 표기 변형이나 잘못 붙은 과목명이 오분류를 일으킬 수 있다.
7. 현재 direct-choice 재검증은 다섯 판단 중 목표 polarity가 정확히 하나일 때만 보정한다. 모델이 여러 선택지를 같은 polarity로 잘못 표시하면 작동하지 않는다.
8. 마지막 40문항 결과와 현재 코드가 동일 버전이 아니므로, 현재 코드의 성능을 그 CSV로 단정하면 안 된다.

## 12. 정답률 개선을 위해 추가·변경한 로직의 시간순 정리

정확한 개별 커밋 메시지가 기능 단위로 세분화돼 있지 않아, 아래는 작업 대화와 현재/이전 결과 파일을 대조한 논리적 작업 순서다.

1. **PDF 로컬 추출과 CSV화**: PDF 문제지와 답안을 로컬 parser로 읽어 정규화 CSV를 생성했다. 이 과정에서 LLM 사용을 제거했다.
2. **시험 전용 실행 모드 분리**: 운영 상담 Prompt와 `OpenAIProvider.generate()`를 건드리지 않고 별도의 Evaluation Runner와 `REALTOR_EXAM_INSTRUCTIONS`를 만들었다. 운영 Tool/RAG 계층만 공유했다.
3. **RAG 사용 trace 추가**: 결과 CSV에 `RAG사용여부`, 검색어, 검색 결과 수, 검색 근거와 법령 filter를 기록하기 시작했다.
4. **법령 과목 RAG 강제**: 과목명에 `법` 또는 `중개실무`가 있으면 최소 1회 검색하도록 Prompt와 `_requires_law_search()`/사전 검색을 추가했다. 현재도 남아 있는 규칙이다.
5. **구조화된 선택지 판단 추가**: 모델이 번호만 반환하지 않고 다섯 선택지의 참/거짓, 근거, evidence IDs를 strict JSON으로 반환하게 했다.
6. **ㄱ·ㄴ·ㄷ resolved items 추가**: 복합형 문항에서 각 label의 최종 판단을 별도로 반환하게 했다.
7. **deterministic 조합 재검증 추가**: resolved items를 실제 선택지 조합과 비교해 최초 번호와 다르면 답을 보정하도록 했다.
8. **법령명 filter 추가**: 문제에서 감지한 법령 family를 `law_name` metadata OR filter로 Vector 검색에 적용했다. 포괄 과목명만으로 공인중개사법을 강제하지 않도록 예외도 뒀다.
9. **선택지별 근거 검색 추가**: 문항 전체 1회 검색 대신 선택지 1~5를 각각 검색해 모든 선택지를 근거와 대조하게 했다. 마지막 40문항 평가는 이 버전으로 실행됐고 30%였다.
10. **근거 압축 추가**: 과도한 중복과 입력량을 줄이기 위해 현재 코드에서 target당 최대 2개, 전체 최대 8개, 법령명+조문 기준 중복 제거로 변경했다.
11. **복합형 검색 target 개선**: `ㄱ`, `ㄴ` 같은 선택지 조합 대신 문제 안의 개별 ㄱ·ㄴ·ㄷ 지문을 추출해 각각 검색하도록 변경했다.
12. **polarity 지시 강화**: choice judgment는 선택지 내용 자체의 참/거짓이고, “틀린 것”을 물어도 의미를 뒤집지 않도록 Prompt를 강화했다.
13. **일반 선택지 재검증 추가**: 현재 코드에서 조합형 외 문항도 `choice_judgments`의 유일한 목표 polarity와 predicted answer를 대조해 번호를 보정하도록 했다.
14. **temperature 0 적용**: 반복 평가의 변동성을 낮추기 위해 현재 시험 Responses 요청에 `temperature=0`을 추가했다.
15. **강제 RAG 제거 시도는 반영되지 않음**: 사용자가 “LLM이 필요하다고 판단할 때만”을 요구한 직전 작업은 중단됐고 저장소는 clean 상태였다. 따라서 현재 코드는 여전히 4번의 강제 사전 검색과 Prompt 규칙을 유지한다.

현재 코드의 10~14번 변경은 동일 40문항으로 아직 실행 검증되지 않았다. 따라서 그 변경이 정답률을 높였다고 말할 근거는 아직 없다.

## 최종 구조 요약

```python-repl
Exam Question (normalized CSV)
     ↓
evaluate_realtor_exam.py::main
     ↓
evaluate_exam
     ↓
RealtorExamEvaluator.evaluate / _solve
     ↓
법령명 감지 + 법령/중개실무 과목 여부 판정
     ↓
Harness의 강제 사전 RAG 검색
     ↓
search_real_estate_law
     ↓
OpenAI Vector Store search (top 5, score/filter 적용)
     ↓
검색 근거 선택·중복 제거·시험 입력에 첨부
     ↓
OpenAI Responses API + 시험 전용 instructions + strict JSON schema
     ↓
predicted_answer + choice_judgments + resolved_items
     ↓
조합/선택 조건 deterministic 재검증
     ↓
필요 시 최초 답 번호 덮어쓰기
     ↓
공식 정답과 비교하여 O/X 및 trace CSV 저장
     ↓
Final Answer
```

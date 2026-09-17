# AGENTS.md

## 1. Project Overview

이 프로젝트는 **부동산 지도 웹서비스 + AI Agent** 프로젝트이다.

최종 목표는 단순한 챗봇이 아니라 다음을 이해하고 실행할 수 있는 AI Agent를 만드는 것이다.

- 현재 지도 상태
- 현재 사용자 상태
- 선택 지역 / 선택 매물 / 관심매물
- 부동산 서비스 데이터
- 웹사이트의 페이지 및 기능 구조
- 실행 가능한 Backend Tool
- 실행 가능한 Frontend UI Action

최종적으로 사용자는 메뉴를 거의 직접 누르지 않고 자연어 대화만으로 다음 흐름을 사용할 수 있어야 한다.

`지도 → 매물 검색/선택 → 분석 → 관심매물 → POI/실거래 → 부동산 법률 상담`

---

## 2. Detailed Development Plan

상세 개발 방향, 단계별 순서, 구현 예시는 반드시 다음 문서를 기준으로 한다.

`docs/real_estate_ai_agent_development_plan_final.txt`

작업을 시작하기 전에 이 파일과 현재 `AGENTS.md`를 먼저 확인한다.

두 문서 사이에 충돌이 있으면:
1. 사용자의 현재 명시적 지시
2. `AGENTS.md`
3. `docs/real_estate_ai_agent_development_plan_final.txt`

순서로 우선한다.

---

## 3. Main Architecture

### Frontend

현재 만들어 놓은 HTML / CSS / JavaScript 기반 웹페이지를 사용한다.

주요 기능:
- 네이버 지도
- 매물 목록
- 매물 상세
- 관심매물
- 부동산 동향 및 분석
- 서비스 소개
- 지도 페이지의 AI 채팅
- AI가 반환한 UI Action 실행

Frontend는 AI가 생성한 명령을 그대로 임의 실행하지 않는다.
미리 정의된 안전한 Action만 실행한다.

예:
- `MOVE_MAP`
- `FIT_BOUNDS`
- `HIGHLIGHT_PROPERTIES`
- `OPEN_PROPERTY`
- `NAVIGATE_PAGE`

---

### Spring Boot

Spring Boot는 **메인 서버이자 부동산 서비스의 데이터/비즈니스 로직 주체**이다.

담당:
- 회원 / 로그인
- 사용자 정보
- 매물 CRUD / 검색
- 관심매물
- 부동산 DB
- POI DB
- 실거래/분석 데이터
- 권한 / 인증 / 보안
- Frontend용 REST API
- FastAPI에 필요한 내부 API
- FastAPI와의 통신

중요 원칙:

FastAPI가 부동산 서비스 DB에 직접 SQL을 실행하는 구조보다 아래 구조를 우선한다.

`FastAPI → Spring Boot API → Service → Repository → DB`

비즈니스 로직이 Java와 Python 양쪽에 중복되지 않도록 한다.

---

### FastAPI

`ai-server/`는 **AI 전용 서버**이다.

담당:
- OpenAI API 호출
- AI Agent 로직
- 공인중개사 역할 Prompt
- Tool Calling
- App State / User Context 처리
- 부동산법 RAG
- App Knowledge RAG
- 여러 Tool의 선택 및 순서 결정
- Tool 결과 종합
- AI 자연어 응답 생성
- 향후 ML / 가격예측 모델 연동

향후 오픈소스 LLM로 교체할 가능성을 고려하여
LLM 호출 코드는 가능한 한 Provider 계층으로 분리한다.

초기에는 OpenAI만 구현한다.
필요 이상으로 복잡한 Provider 추상화는 만들지 않는다.

---

## 4. Repository / File Scope Rules

이 프로젝트는 팀 프로젝트이다.

### 반드시 지켜야 할 작업 범위

- 현재 주 담당 페이지는 지도 웹페이지이다.
- `map.html` 및 지도 페이지와 직접 연관된 파일을 중심으로 작업한다.
- AI 채팅은 기존 `chat.html`이 아니라 **`ai-chat.html` 및 관련 파일**을 사용한다.
- `chat.html` 또는 다른 팀원이 담당하는 기능은 명시적인 요청이 없는 한 수정하지 않는다.
- 현재 작업과 관련 없는 파일을 정리한다는 이유로 삭제/대규모 수정하지 않는다.
- 기존 기능을 AI용으로 다시 만들기보다 가능한 한 기존 기능을 재사용한다.
- 작업 전 관련 기존 코드와 API를 먼저 확인한다.

파일이나 기능의 소유 범위가 불명확하면
임의로 광범위하게 수정하지 말고 최소 수정 원칙을 적용한다.

---

## 5. AI Agent Design Principles

AI가 브라우저나 DB를 임의로 조작하게 만들지 않는다.

### AI가 해서는 안 되는 것

- 임의 JavaScript 생성 후 실행
- `eval()` 사용
- 임의 DOM 변경
- 허용되지 않은 API 호출
- DB에 직접 임의 SQL 실행
- 사용자가 요청하지 않은 대규모 상태 변경

### AI에게 제공하는 방식

AI에게는 명확한 Tool / Action을 제공한다.

예:

#### 매물 Tool
- `search_properties()`
- `get_property_detail()`
- `compare_properties()`

#### 관심매물 Tool
- `get_favorites()`
- `add_favorite()`
- `remove_favorite()`
- `compare_favorites()`

#### 분석 Tool
- `get_market_analysis()`
- `run_market_analysis()`

#### POI Tool
- `search_subway()`
- `search_school()`
- `search_hospital()`
- `search_pharmacy()`
- `search_poi()`

#### 법률 Tool
- `search_real_estate_law()`

#### App Knowledge Tool
- `search_app_knowledge()`

#### 지도/UI Action
- `move_map()`
- `zoom_map()`
- `fit_bounds()`
- `highlight_properties()`
- `open_property_detail()`
- `navigate_page()`
- `select_analysis_station()`
- `select_analysis_region()`
- `set_analysis_trade_type()`
- `run_analysis_ui()`

---

## 6. App State / User Context

AI에게 HTML 전체나 DOM 전체를 전달하지 않는다.

필요한 현재 상태를 구조화된 데이터로 전달한다.

예:

```json
{
  "current_page": "map",
  "map_center": {
    "lat": 37.394,
    "lng": 127.111
  },
  "zoom": 15,
  "selected_region": "성남시 분당구 정자동",
  "selected_property_id": 427,
  "favorite_property_ids": [182, 427, 903],
  "filters": {
    "property_type": "아파트",
    "max_price": 800000000
  }
}
```

이미 선택된 매물이 존재하는 경우 불필요하게 다시 `search_properties()`를 호출하지 않는다.

우선:
1. App State 확인
2. 필요하면 `get_property_detail()`
3. 추가 검색이 필요한 경우에만 `search_properties()`

순서로 판단한다.

---

## 7. Prompt / RAG / Tool / Fine-tuning Separation

기능별 역할을 혼동하지 않는다.

### Prompt
AI의 말투와 행동 원칙

예:
- 전문적인 공인중개사처럼 정중하게 말한다.
- 어려운 부동산 용어는 쉽게 설명한다.
- 장점뿐 아니라 위험요소도 함께 설명한다.
- 매수를 강요하거나 수익을 보장하지 않는다.
- 불확실한 내용을 단정하지 않는다.

### RAG
AI가 참고할 문서

예:
- 부동산 법률
- 서비스 소개
- FAQ
- 앱 사용방법

### Tool
AI가 실제로 수행할 수 있는 기능

예:
- 매물 검색
- 관심매물 등록
- 지도 이동
- 분석 실행

### App State
사용자가 현재 보고/선택하고 있는 상태

### Fine-tuning
현재 단계에서는 사용하지 않는다.

법률, 매물 정보, 자주 바뀌는 서비스 데이터는 Fine-tuning하지 않는다.
RAG 또는 DB/API 조회를 사용한다.

Fine-tuning은 실제 사용 로그와 좋은 상담 데이터가 충분히 쌓인 후,
Prompt만으로 해결되지 않는 일관된 상담 패턴이 필요할 때만 검토한다.

---

## 8. LLM Provider Rule

초기 모델은 OpenAI API를 사용한다.

구조는 향후 다음과 같이 확장 가능해야 한다.

`AI Agent → LLM Provider → OpenAI / Local or Hosted Open Model`

단, 현재 OpenAI만 사용하는 단계에서
필요 이상으로 복잡한 추상 클래스/Factory/다중 Provider 구현을 선행하지 않는다.

LLM 교체가 가능하도록 코드 위치와 책임만 분리한다.

---

## 9. Local Development

로컬에서는 Spring Boot와 FastAPI를 별도의 프로세스로 동시에 실행한다.

- Spring Boot: `http://localhost:8080`
- FastAPI: `http://localhost:8000`

일반 요청:

`Frontend → Spring Boot (:8080)`

AI 요청:

`Frontend → Spring Boot (:8080) → FastAPI (:8000) → OpenAI API`

Spring Boot의 포트가 8000으로 변경되는 것이 아니다.
Spring Boot가 8000번 포트에서 실행 중인 FastAPI를 호출한다.

---

## 10. FastAPI Environment

AI 서버는 `ai-server/` 폴더에서 관리한다.

권장 초기 구조:

```text
ai-server/
├─ .venv/
├─ app/
│  ├─ __init__.py
│  └─ main.py
├─ requirements.txt
└─ .env
```

규칙:

- Python 가상환경은 `ai-server/.venv`
- `.venv`는 Git에 커밋하지 않는다.
- `.env`는 Git에 커밋하지 않는다.
- API Key / DB 비밀번호 / Secret을 코드에 하드코딩하지 않는다.
- 공유가 필요한 환경변수 이름만 `.env.example`에 작성한다.
- Python dependency는 `requirements.txt` 등으로 관리한다.

---

## 11. Deployment Direction

### First Deployment
Render 사용

한 Render 계정/Workspace 안에서:
- Spring Boot Service
- FastAPI Service

를 별도 서비스로 배포할 수 있다.

가능하면 같은 Region을 사용한다.

외부 요청은 기본적으로 Spring Boot를 통해 받고,
FastAPI는 Spring Boot가 호출하는 AI 내부 서비스 역할을 우선한다.

### Later Deployment
AWS EC2 고려

초기:
- 같은 EC2에 Spring Boot와 FastAPI를 함께 실행 가능

예:
- Spring Boot :8080
- FastAPI :8000

트래픽이 증가하면:
- Spring Boot EC2
- FastAPI EC2

로 분리할 수 있다.

---

## 12. Development Order

한 번에 여러 단계를 구현하지 않는다.

각 단계가 정상 동작하는지 확인한 후 다음 단계로 이동한다.

### 0단계
현재 웹사이트 / 코드 구조 정리

### 1단계
Spring Boot ↔ FastAPI 연결

목표:
`Spring → FastAPI → hello`

아직 OpenAI / RAG / Tool Calling을 넣지 않는다.

### 2단계
FastAPI ↔ OpenAI API 연결

목표:
일반 AI 채팅

### 3단계
공인중개사 Prompt 적용

### 4단계
AI Chat UI + App State 연결

### 5단계
첫 번째 Tool: 매물 검색

`FastAPI Agent → search_properties → Spring API → DB`

### 6단계
지도 UI Action

예:
- MOVE_MAP
- FIT_BOUNDS
- HIGHLIGHT_PROPERTIES
- OPEN_PROPERTY

여기까지가 첫 번째 핵심 프로토타입이다.

핵심 목표 문장:

> "판교역 8억 이하 아파트 보여줘."

실제 동작:

`AI 채팅 → 매물 검색 Tool → 지도 이동 → 매물 마커 강조 → 자연어 설명`

### 7단계
부동산법 RAG

### 8단계
관심매물 Context / Tool

### 9단계
POI / 실거래 / 분석 Tool

### 10단계
다단계 Agent

### 11단계
Streaming / UX 개선

### 12단계
로그 / 평가 데이터 축적

---

## 13. Later / Optional Features

아래 기능은 핵심 Agent가 완성된 후 필요 여부를 확인하고 진행한다.

### 부동산 분석 페이지 Tool
예:
- `select_analysis_station()`
- `select_analysis_region()`
- `set_analysis_trade_type()`
- `run_market_analysis()`

### App Knowledge
예:
- 서비스 소개
- 제작 목적
- 사용방법
- FAQ

### App Structure / Page Navigation
예:
- `navigate_page("about")`
- `navigate_page("analysis")`
- `navigate_page("favorites")`

이 추가 기능들은 사용자의 확인 없이 핵심 단계보다 먼저 구현하지 않는다.

---

## 14. Coding / Change Rules

작업 시 다음 원칙을 따른다.

1. 먼저 현재 코드 구조와 기존 구현을 읽는다.
2. 재사용 가능한 기존 함수/API가 있으면 우선 재사용한다.
3. 현재 단계에 필요한 최소 범위만 수정한다.
4. 요청하지 않은 리팩터링을 함께 수행하지 않는다.
5. 기존 기능이 깨지지 않도록 한다.
6. 변경 후 실행 또는 테스트 가능한 부분을 확인한다.
7. 어떤 파일을 왜 수정했는지 명확히 정리한다.
8. 다음 단계는 사용자가 요청하기 전까지 시작하지 않는다.
9. 임시 테스트 코드는 작업 완료 시 불필요하면 제거한다.
10. Secret/API Key를 출력하거나 Git에 저장하지 않는다.

---

## 15. Codex Response / Workflow Rule

각 단계 작업 시 다음 흐름을 따른다.

1. 관련 코드 분석
2. 현재 단계에서 필요한 변경 범위 설명
3. 구현
4. 실행/테스트
5. 변경 파일과 결과 요약
6. 현재 개발 계획에서 어디까지 완료되었는지 표시
7. 다음 단계는 설명만 하고 자동으로 구현하지 않는다

한 번에 전체 AI Agent를 완성하려 하지 않는다.

---

## 16. Core Principle

이 프로젝트에서 AI는 모든 기능을 직접 수행하는 프로그램이 아니다.

AI는:
- 자연어를 이해하고
- 현재 상태를 해석하고
- 적절한 Tool을 선택하고
- Tool 결과를 이해하고
- 다음 행동을 결정하고
- 사용자에게 설명한다.

실제 데이터 검색과 상태 변경은 Spring Boot / Frontend의 명시적 기능이 수행한다.

최종적으로 **"대화가 웹사이트의 통합 인터페이스"**가 되는 것을 목표로 한다.

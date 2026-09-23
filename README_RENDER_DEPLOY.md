# ZipChatGo Render 무료 테스트 배포

이 구성은 하나의 Git 저장소에서 다음 두 개의 Render **Free Web Service**를 각각 Docker로 빌드한다.

| 서비스 | Blueprint 이름 | Docker context | 기본 공개 URL 예시 |
|---|---|---|---|
| FastAPI AI server | `zipchatgo-ai` | `ai-server/` | `https://zipchatgo-ai.onrender.com` |
| Spring Boot web | `zipchatgo-spring` | 저장소 루트 | `https://zipchatgo-spring.onrender.com` |

Docker Hub에 애플리케이션 이미지를 올리거나 GitHub Actions/AWS EC2를 사용하지 않는다. Render가 Git 저장소의 Dockerfile을 직접 빌드한다. Dockerfile의 JDK/Python 공개 base image는 빌드 중 registry에서 내려받는다.

## 1. 배포 전 확인

1. 이 변경을 배포하려는 Git 브랜치에 commit/push한다.
2. `.env`와 실제 키/비밀번호가 commit되지 않았는지 확인한다.
3. 외부 TiDB가 Render의 인터넷 연결을 허용하는지 확인한다.
4. Render에서 사용할 32바이트 이상의 임의 문자열 하나를 준비한다. 이 값을 두 서비스의 `INTERNAL_API_KEY`에 **동일하게** 입력한다.

로컬 개발 기본값은 바뀌지 않는다.

- Spring: `http://127.0.0.1:8080`
- FastAPI: `http://127.0.0.1:8000`
- 로컬에서 `INTERNAL_API_KEY`가 비어 있으면 내부 키 검증은 비활성화된다.
- 로컬 FastAPI 문서는 기본적으로 `/docs`, `/redoc`, `/openapi.json`에서 활성화된다.

## 2. 권장 방법: Blueprint로 생성

1. GitHub에서 이 저장소와 배포할 branch가 push되어 있는지 확인한다.
2. Render Dashboard에 로그인하고 **New + > Blueprint**를 누른다.
3. 처음 연결하는 경우 **Connect GitHub**를 눌러 Render GitHub App에 해당 repository 접근 권한을 준다.
4. repository 목록에서 이 저장소의 **Connect**를 누른다.
5. 배포할 브랜치를 선택한다. `render.yaml`은 특정 브랜치를 하드코딩하지 않는다.
6. Blueprint Path에 저장소 루트의 `render.yaml`을 지정하고 이름을 정한다.
7. **Apply**를 누르기 전에 `sync: false`로 표시된 환경변수를 입력한다.
8. Blueprint가 `zipchatgo-ai`, `zipchatgo-spring` 두 Free Web Service를 생성하는지 확인하고 적용한다.

서비스 이름을 그대로 사용할 수 있다면 공개 URL은 보통 아래와 같다.

```text
FastAPI: https://zipchatgo-ai.onrender.com
Spring:  https://zipchatgo-spring.onrender.com
```

Blueprint 생성 화면에서 다음처럼 교차 URL을 입력한다.

```text
Spring AI_SERVER_URL=https://zipchatgo-ai.onrender.com
FastAPI SPRING_SERVER_BASE_URL=https://zipchatgo-spring.onrender.com
```

이름 충돌 등으로 Render가 다른 hostname을 부여하면 서비스 생성 후 각 서비스의 실제 공개 URL을 확인하고 두 환경변수를 실제 값으로 수정한 뒤 **Manual Deploy > Deploy latest commit**을 실행한다. 끝의 `/`는 넣지 않는다.

무료 Web Service는 private network 요청을 받을 수 없으므로 `onrender.com` 공개 HTTPS URL을 사용한다. `localhost` 또는 Render 내부 hostname을 넣으면 두 컨테이너가 서로 연결되지 않는다.

## 3. 수동 생성 방법

Blueprint를 쓰지 않을 경우 다음 설정으로 Web Service를 두 개 생성한다.

### FastAPI

```text
Runtime: Docker
Plan: Free
Region: Singapore
Dockerfile Path: ./ai-server/Dockerfile
Docker Build Context: ./ai-server
Health Check Path: /health
```

### Spring Boot

```text
Runtime: Docker
Plan: Free
Region: Singapore
Dockerfile Path: ./Dockerfile
Docker Build Context: .
Health Check Path: /health
```

두 서비스를 같은 region에 둔다. 무료 서비스 간 호출 자체는 공개 HTTPS URL을 사용한다.

## 4. 환경변수

### FastAPI (`zipchatgo-ai`)

| 이름 | 필요 여부 | 설명 |
|---|---|---|
| `OPENAI_API_KEY` | 필수 | OpenAI API 키 |
| `OPENAI_MODEL` | 권장 | 기본값 `gpt-4o-mini` |
| `SPRING_SERVER_BASE_URL` | 필수 | 실제 Spring 공개 URL |
| `INTERNAL_API_KEY` | 강력 권장 | Spring과 동일한 임의 secret |
| `LAW_VECTOR_STORE_ID` | 법률 RAG 사용 시 필수 | OpenAI vector store ID |
| `LAW_API_OC` | 국가법령 API 사용 시 필수 | 법률 API 식별값 |
| `ENABLE_API_DOCS` | 권장 | Render에서는 `false`; 로컬 기본값은 `true` |

`PORT`는 Render가 자동 주입하며 Docker command가 이 값을 사용한다.

### Spring Boot (`zipchatgo-spring`)

| 이름 | 필요 여부 | 설명 |
|---|---|---|
| `AI_SERVER_URL` | 필수 | 실제 FastAPI 공개 URL |
| `INTERNAL_API_KEY` | 강력 권장 | FastAPI와 동일한 임의 secret |
| `DB_HOST` | 필수 | TiDB hostname만 입력 (`https://` 제외) |
| `DB_PORT` | 필수 | TiDB port |
| `DB_DATABASE` | 필수 | database/schema 이름 |
| `DB_USERNAME` | 필수 | DB 사용자 |
| `DB_PASSWORD` | 필수 | DB 비밀번호 |
| `MOLIT_SERVICE_KEY` | MOLIT 기능 사용 시 필수 | 공공데이터 API 키 |
| `DEFAULT_LAWD_CD` | 권장 | 기본값 `41117` |
| `NAVER_MAPS_CLIENT_KEY` | 지도 사용 시 필수 | Naver Maps client key 및 도메인 등록 필요 |
| `SUPABASE_URL` | 업로드 기능 사용 시 필수 | Supabase project URL |
| `SUPABASE_SERVICE_KEY` | 업로드 기능 사용 시 필수 | Supabase service key |
| `SUPABASE_BUCKET` | 업로드 기능 사용 시 필수 | bucket 이름 |

`AI_SERVER_BASE_URL`은 기존 로컬 설정과의 호환을 위한 fallback이다. Render에서는 새 이름인 `AI_SERVER_URL`을 사용한다. `PORT`는 Render가 자동 주입하고 Spring의 `server.port=${PORT:8080}`이 사용한다.

## 5. 배포 후 확인 순서

1. FastAPI `GET https://<ai-host>/health`가 `{"status":"ok"}`인지 확인한다.
2. Spring `GET https://<spring-host>/health`가 `{"status":"ok"}`인지 확인한다.
3. Spring 홈페이지와 `/property/map`을 연다.
4. 지도용 Naver key의 Web Service URL이 허용 도메인에 등록됐는지 확인한다.
5. AI 채팅에서 간단한 질문을 보내 Spring → FastAPI 호출을 확인한다.
6. 매물 검색 질문으로 FastAPI → Spring → TiDB 경로도 확인한다.
7. 법률 RAG, POI, 파일 업로드는 해당 환경변수를 넣은 경우에만 별도로 확인한다.

각 서비스의 **Logs** 탭에서 build log와 runtime log를 구분해 확인한다. Spring은 `Started ZipchatgoApplication`, FastAPI는 Uvicorn의 application startup 완료와 `0.0.0.0:<PORT>` 바인딩을 확인한다. 키나 비밀번호를 진단 목적으로 로그에 출력하지 않는다.

`INTERNAL_API_KEY`가 FastAPI에 설정되어 있으면 `/agent/test`와 `/agent/chat`은 `X-Internal-API-Key` 헤더가 없거나 틀린 직접 요청에 `401`을 반환한다. `/health`는 Render health check를 위해 인증 없이 공개된다. Spring의 브라우저용 API는 프런트엔드가 직접 사용하므로 이번 구성에서 일괄 잠그지 않는다.

## 6. 자동 배포와 build filter

`render.yaml`은 commit push 시 자동 배포한다.

- `ai-server/**` 변경은 FastAPI만 다시 빌드한다.
- Spring `src/**`, Gradle 설정, 루트 Dockerfile 변경은 Spring만 다시 빌드한다.
- 공통 배포 설정인 `render.yaml` 변경은 Blueprint sync와 두 서비스 재검증 대상이다.

최초 배포 뒤에는 선택한 linked branch로 push하면 다음 순서로 진행된다.

```text
GitHub push
→ Render가 관련 buildFilter 확인
→ 해당 Dockerfile로 새 image build
→ health check 통과
→ 새 배포로 traffic 전환
```

Dashboard의 서비스 **Events**에서 어떤 commit이 자동 배포됐는지 확인할 수 있다. 자동 배포를 잠시 멈추려면 서비스 Settings에서 Auto-Deploy를 끄고, 다시 `commit`으로 돌릴 때 Blueprint 설정과 일치하는지 확인한다.

문제가 생기면 서비스의 **Events**에서 직전 성공 배포를 열고 **Rollback**을 선택한다. 무료 플랜의 rollback 보존 수는 제한적이므로 Git에서도 문제 commit을 되돌린 뒤 다시 push하는 것이 안전하다.

## 7. 무료 플랜 주의사항

- 무료 Web Service는 일정 시간 요청이 없으면 sleep한다. 첫 요청은 cold start 때문에 약 1분 이상 걸릴 수 있다.
- 두 서비스가 각각 instance 시간을 사용한다. 워크스페이스의 월 무료 시간을 함께 소비하므로 사용량을 확인한다.
- filesystem은 ephemeral이다. 컨테이너 내부에 업로드 파일이나 DB 데이터를 영구 저장하지 않는다. 현재 업로드 영속화는 Supabase 같은 외부 저장소를 사용해야 한다.
- 무료 Web Service는 private network 요청을 받을 수 없어 서비스 간 통신도 공개 URL을 사용한다.
- 외부 TiDB/OpenAI/MOLIT/Supabase 호출은 outbound traffic과 각 외부 서비스의 제한을 따른다.
- 메모리 부족이 실제 로그로 확인될 때만 `JAVA_TOOL_OPTIONS` 조정을 검토한다. 현재 Dockerfile은 JVM heap을 강제로 고정하지 않는다.

## 8. 보안 체크리스트

- `.env`, API key, DB password, Supabase service key를 Git에 commit하지 않는다.
- `render.yaml`에는 secret 값을 직접 쓰지 않고 `sync: false`만 사용한다.
- `INTERNAL_API_KEY`는 두 서비스에 같은 값을 넣되 다른 secret과 재사용하지 않는다.
- Render 배포에서는 `ENABLE_API_DOCS=false`를 유지한다.
- Naver Maps key에는 허용 URL을 설정하고, TiDB 계정에는 필요한 최소 권한만 부여한다.
- Render 로그에 request header, DB URL의 password, 전체 환경변수를 출력하지 않는다.

## 9. 흔한 오류

### Spring에서 FastAPI 연결 실패

- `AI_SERVER_URL`이 실제 FastAPI 공개 HTTPS URL인지 확인한다.
- FastAPI가 sleep 중이면 첫 호출이 늦거나 Spring 요청 timeout이 날 수 있다. 먼저 FastAPI `/health`를 열어 깨운 뒤 다시 시도한다.
- 양쪽 `INTERNAL_API_KEY`가 정확히 같은지 확인한다.

### FastAPI에서 Spring Tool 호출 실패

- `SPRING_SERVER_BASE_URL`이 실제 Spring 공개 URL인지 확인한다.
- `localhost`는 다른 Render 컨테이너를 가리키지 않는다.
- Spring `/health`와 매물 API가 외부에서 응답하는지 확인한다.

### Spring 기동 실패

- 로그의 최초 `Caused by`를 확인한다.
- `DB_HOST`, `DB_PORT`, `DB_DATABASE`, `DB_USERNAME`, `DB_PASSWORD`가 모두 있는지 확인한다.
- TiDB TLS/접근 허용 정책과 Render outbound 연결을 확인한다.
- Render가 주입한 `PORT`를 덮어쓰지 않는다.

### 지도만 표시되지 않음

- `NAVER_MAPS_CLIENT_KEY`와 Naver Cloud 허용 Web Service URL에 Render Spring URL을 추가했는지 확인한다.

### Docker build 실패

- Spring은 Java 21과 Gradle Wrapper를 사용한다.
- FastAPI는 `ai-server/requirements.txt`의 고정 버전을 설치한다.
- Docker Hub에 별도 image를 push할 필요가 없다. Render build log에서 base image pull 또는 dependency download 오류를 확인한다.

## 10. 로컬 테스트 및 실행

Render용 환경변수가 없어도 기존 로컬 실행 방식은 유지된다.

```powershell
# 터미널 1: Spring Boot
.\gradlew.bat bootRun

# 터미널 2: FastAPI
cd ai-server
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

로컬 `.env`에는 실제 값을 둘 수 있지만 Git에 추가하지 않는다. 선택적으로 내부 키까지 로컬에서 검증하려면 루트 `.env`의 `INTERNAL_API_KEY`를 두 프로세스가 동일하게 읽을 수 있게 설정한다. 값을 비워 두면 기존 로컬 요청에 대한 키 검증은 하지 않는다.

Docker가 설치된 환경에서는 다음처럼 Render에 올리기 전 image build만 확인할 수 있다. image push/login은 하지 않는다.

```powershell
docker build -t zipchatgo-spring-local .
docker build -t zipchatgo-ai-local .\ai-server
```

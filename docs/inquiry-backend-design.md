# 1:1 문의 백엔드 적용 설계

## 범위

`src/main/resources/templates/support/contact.html`의 문의 폼을 Spring Boot 서버에 연결한다. 현재 프런트엔드는 `localStorage`에만 저장하므로, 서버 검증 후 MySQL 8 또는 TiDB에 문의를 저장하는 것이 이번 작업의 범위다.

## 기술 제약

- Java 21, Spring Boot 4.1.1, Gradle
- Spring Web, Thymeleaf, Lombok, MySQL Driver, Spring Data JDBC, Spring Security만 사용
- 회원/관리자 기능은 후속 작업으로 남기며 현재 문의는 비회원 등록을 허용한다.
- Python/RPA, Docker, GitHub Actions, Render 배포는 이 기능의 실행 계약만 고려하고 구현 범위에서는 제외한다.

## 화면과 API 계약

| 항목 | 값 |
|---|---|
| 화면 | `GET /support/contact` |
| 등록 API | `POST /api/inquiries` |
| 요청 형식 | `application/x-www-form-urlencoded` |
| 응답 성공 | `201 Created`, `{ "message": "..." }` |
| 응답 실패 | `400 Bad Request`, `{ "message": "..." }` |
| 인증 | 공개 등록, `member_id`는 현재 `NULL` |

요청 필드는 `name`, `email`, `type`, `title`, `message`, `privacyAgreed`다. `type`은 `서비스 이용`, `계정 및 로그인`, `매물 정보`, `오류 신고`, `기타`만 허용한다.

## 서버 구성

- `SupportPageController`: Thymeleaf 문의 화면 라우팅
- `InquiryApiController`: 폼 요청 수신, 성공/실패 HTTP 응답
- `InquiryService`: 입력 검증, 상태 `RECEIVED` 지정, 생성 시각 기록
- `InquiryRepository`: Spring Data JDBC `CrudRepository`
- `Inquiry`: `inquiry` 테이블에 매핑되는 aggregate
- `SecurityConfig`: 모든 현재 경로를 공개하고 CSRF는 기본 활성화

문의 폼에는 Spring Security가 제공하는 CSRF hidden input을 포함한다. `contact.js`는 해당 폼을 `FormData`로 API에 전송하며 성공 시에만 폼을 초기화한다. 브라우저 `localStorage`에는 문의 내용을 저장하지 않는다.

## 데이터베이스

`src/main/resources/schema.sql`에 MySQL/TiDB 호환 DDL을 둔다. 운영 배포에서는 다음처럼 데이터베이스 연결 환경 변수를 설정하고 스키마를 적용한다.

```text
DB_URL=jdbc:mysql://<host>:4000/zipchatgo?useSSL=false&serverTimezone=UTC
DB_USERNAME=<database-user>
DB_PASSWORD=<database-password>
```

현재 프로젝트에는 migration 도구를 추가하지 않았으므로 운영에서는 배포 단계에서 `schema.sql`을 한 번 적용한다. 추후 스키마 변경이 잦아지면 Flyway 또는 Liquibase 도입을 별도 결정한다.

## 보안과 운영 고려사항

- CSRF 토큰은 폼 hidden field로 전송한다.
- 요청값 길이와 이메일 형식, 문의 유형, 개인정보 동의를 서버에서도 검사한다.
- 회원 연동 시 요청의 이름/이메일을 신뢰하지 않고 인증 주체의 회원 정보로 대체한다.
- 공개 API에는 향후 IP/이메일 기준 rate limit, 허니팟 또는 CAPTCHA, 중복 제출 방지 키를 추가한다.
- 관리자 답변 기능을 추가할 때 `status`, `answered_at`, 답변 본문과 관리자 권한 검사를 확장한다.
- 로그에는 문의 내용과 이메일을 남기지 않는다.

## 검증 항목

1. 정상 폼 제출이 `201`과 성공 메시지를 반환한다.
2. 동의하지 않은 요청, 잘못된 이메일, 허용되지 않은 유형, 길이 초과 요청이 `400`을 반환한다.
3. 성공 제출 후 화면에 성공 메시지가 표시되고 폼이 초기화된다.
4. CSRF 토큰이 없는 POST는 Security 기본 정책에 따라 차단된다.
5. MySQL 8과 TiDB에서 `schema.sql`이 정상 실행되고 문의 행이 저장된다.

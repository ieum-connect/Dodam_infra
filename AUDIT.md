# 도담 배포 구조 확인 — 2026-11-07

## 실제 확인한 버전
- frontend develop `3b502c4`: React/Vite, npm package-lock.json. VITE_API_BASE_URL 기본값은 상대 경로.
- backend develop `ee16762`: Java 17/Maven/Spring Boot 3.3.4, 8081, Flyway/PostgreSQL.
- ai-backend develop `6da9b00`: Python >=3.12, pyproject.toml, FastAPI `app.main:app`, `/health`.
- 원본 C:/dodam/{frontend,backend,ai-backend}에는 미커밋 변경이 있다. 보존하고 C:/dodam/deployment-sources에 최신 develop 별도 사본을 만들었다.
- 현재 배포 검증은 develop 기준이다. 프런트 PR #18 및 백엔드 #30/#31/#32의 기능이 병합됐다고 간주하지 않는다.

## 배포 연결
- Nginx가 프런트 정적 결과물을 제공하고 `/api`, `/api/`, `/oauth2/`, `/login/oauth2/`, `/logout`을 Spring으로 전달한다.
- Vite 개발 설정의 `/api/v1` 직접 AI 프록시는 운영에 복제하지 않는다. 복지 설명은 보호된 `/api/welfare-explanations` → Spring → AI 경로를 사용한다.
- AI는 호스트 포트 미노출. 내부 token은 양 서버에 동일하게 설정한다.
- Spring `/api/auth/config`는 공개 설정 응답으로 준비 확인에 사용한다. DB 전체 상태를 보장하는 전용 health API는 아니다. Flyway DB 조회를 별도로 수행한다.
- `/api/ai-chat-sessions/{id}/messages`는 JSON 동기 응답이다. SSE는 확인되지 않았다. 해당 경로와 복지 설명만 360초 읽기 제한을 둔다.
- 파일 20MB, multipart 요청 21MB, Nginx 21m. 문서 원본 및 AI 렌더링 이미지 경로는 `/data/object-storage` 공유 볼륨이다.
- PyMuPDF/Pillow를 사용하는 코드이며 Poppler 실행은 확인되지 않았다. 바이너리 wheel 설치와 실제 PDF 렌더링으로 시스템 의존성을 검증한다.
- pgvector/pgvector:pg16은 기존 Compose와 일치한다. 임베딩 컬럼은 vector(768), AI 설정도 768이다.
- PWA manifest/sw.js/푸시 구독·수신 코드는 이 develop에서 발견되지 않았다. 정재헌의 PR·파일명·scope·갱신·개인정보 캐시 제외 방침 확인이 필요하다. 별도 PWA를 만들지 않았다.

## 운영 전 해결할 사항
1. 문서 원본: LocalDocumentStorage.createSignedUrl은 서명 없이 expiresAt만 붙인다. LocalDocumentResourceConfig는 저장소를 정적으로 매핑한다. 로그인 인증은 있지만 아이별 접근 권한/서명 만료 검증을 이 경로에서 확인할 수 없다. 따라서 Nginx에서 `/local-documents`를 403으로 차단했다. 원본 보기 기능은 운영 준비 미완료이며 정재헌·백엔드 담당과 권한 확인 다운로드 API를 연결해야 한다. 차단을 해제하여 해결하지 않는다.
2. 인증: develop AuthCookieService의 Secure=false. HTTPS Nginx가 인증 쿠키 Secure/HttpOnly/SameSite=Lax를 추가하도록 구성했다. 최환우의 #32 병합 후 서버 자체 속성과 함께 재검증한다. 전달 헤더는 단일 공개 프록시에서 덮어쓰고 Spring은 framework로 처리한다.
3. 보안: 현재 Spring은 CSRF 검사를 비활성화한다. 실제 로그인 배포 전 쿠키 기반 변경 요청 보호 방침을 확인한다. 같은 도메인/쿠키 설정만으로 전체 보안 검증 완료로 보지 않는다.
4. AI 모델명은 저장소 기본값을 그대로 노출했다. 실제 계정 지원 여부와 LLM_API_KEY 명시 설정은 AI 담당 확인 사항이다. 비용 발생 호출은 사용자 명시 요청 전 금지한다.
5. AI pyproject에는 최소 버전 제약만 있고 잠금 파일이 없다. 생성 이미지 안 installed-dependencies.txt와 이미지 ID를 남기며 재배포는 동일 이미지로 한다. 의존성 잠금 파일은 정재헌과 협의한다.
6. 업로드 분석은 프로세스 내 작업 처리이므로 진행 중 서버 교체 시 실패·재시도 정책을 문서 담당과 확인한다. 자동 복구를 보장하지 않는다.
7. 실제 로컬 기동에서 최신 OpenAI SDK가 빈 embedding key로 MedicalRagEmbeddingProvider 생성 시 종료하는 것을 확인했다. 다른 담당자 코드는 바꾸지 않았다. 로컬만 식별 가능한 가짜 키와 막힌 loopback LLM 주소, 외부 통신 없는 Docker internal network로 기동한다. 실제 AI 기능 성공을 의미하지 않으며 운영은 유효한 키 설정 또는 담당자의 지연 초기화 수정이 필요하다.

## 미정
AWS 계정/리전/사양/디스크, 크레딧, 도메인, 관리자 IP, SSH 방식, 외부 백업 위치. 사용자 답변은 ‘미정’이다. AWS 리소스 및 인증서는 생성하지 않는다.

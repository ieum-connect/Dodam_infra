# 도담 AWS 배포 실행 가이드

기준일: 2026-11-18 · 대상: 현재 운영 구성 및 재배포 절차

운영 주소는 **https://dodam-ieum.duckdns.org/** 이다. 시드니(ap-southeast-2)의 단일 EC2에서 Docker Compose로 운영하며, 문서 원본과 분석 페이지는 비공개 Amazon S3에 저장한다. 이 문서는 초기 배포 계획을 대체한다. 개별 릴리스의 SHA·digest와 검증 결과는 해당 배포 기록에서 확인한다.

## 1. 현재 구성

- EC2: Nginx/React PWA, Spring Boot, FastAPI, PostgreSQL 16/pgvector.
- 공개 진입점: Nginx 80/443. HTTP는 HTTPS로 전환한다.
- 내부 포트: backend 8081, ai 8006, postgres 5432. 인터넷에 직접 공개하지 않는다.
- 인증서: Let's Encrypt와 Certbot. certbot은 tools 프로필의 일회성 실행 서비스다.
- 문서: 비공개 S3, SSE-S3 암호화, Versioning, EC2 IAM Role. 사용자 권한 확인 후 원본 전달 또는 짧은 만료의 서명 URL을 발급한다.
- 외부 연동: Kakao OAuth, OpenAI API, Firebase FCM.
- 이미지: GitHub Actions에서 Docker Hub 게시, 운영자가 EC2에 수동 반영.
- ECR·SSM 자동 배포, Kubernetes/EKS, ALB는 현재 배포 경로가 아니다.

브라우저는 같은 운영 도메인의 프론트와 Spring API를 사용한다. AI 호출은 Spring을 거치며 내부 토큰으로 인증한다. Nginx의 /local-documents 차단은 유지하지만, 이것이 인증된 원본 조회 기능의 미구현을 의미하지 않는다. S3는 프론트 정적 사이트 호스팅 용도가 아니다.

2026-11-18 읽기 전용 운영 점검에서 네 서비스 모두 healthy, NGINX_MODE=https, DOCUMENT_STORAGE_PROVIDER=s3, PUSH_ENABLED=true를 확인했다. 이 상태 점검은 모든 업무 기능이나 실제 기기 푸시 수신을 보증하지 않는다.

구성 파일: [Compose](compose.production.yml), [환경 변수 예제](.env.production.example), [S3 전환 기록](S3_DOCUMENT_STORAGE.md).

## 2. 실제 운영 경로와 환경 파일

현재 EC2의 작업 디렉터리는 /opt/dodam/infra, 환경 파일은 **.env.ec2-check**, Compose 프로젝트는 **dodam-ec2-check**다. 이름에 check가 있지만 실제 운영 자원이다. 기존 프로젝트 이름을 임의로 바꾸면 별도 컨테이너·볼륨이 만들어질 수 있다.

아래 명령은 EC2의 적절한 관리자 권한으로 실행한다.

```bash
cd /opt/dodam/infra
dc=(docker compose --env-file .env.ec2-check -p dodam-ec2-check -f compose.production.yml)
"${dc[@]}" config --quiet
"${dc[@]}" ps
"${dc[@]}" exec -T web nginx -t
curl -fsS https://dodam-ieum.duckdns.org/api/auth/config
```

운영 환경 파일의 COMPOSE_PROJECT_NAME도 dodam-ec2-check로 유지한다. scripts/deploy.sh, status.sh, backup.sh, renew.sh에는 반드시 .env.ec2-check를 인자로 전달한다. 스크립트 기본값인 .env.production은 신규 설치용 기본 이름이며 현재 운영 파일 이름과 다르다.

환경 파일·Firebase 서비스 계정·OAuth/AI 키는 저장소에 넣지 않는다. 전체 compose config나 환경 파일을 공개 로그에 출력하지 않는다.

## 3. PR 검증과 이미지 게시

PR 자동 검증과 운영 배포는 별개다.

- 앱 저장소 PR: 프론트 PWA 빌드, 백엔드 Maven 검증, AI Pytest.
- 인프라 PR: [release-images.yml](.github/workflows/release-images.yml)의 지정 경로 변경 시 이미지 빌드 검사, [storage-checks.yml](.github/workflows/storage-checks.yml)의 조건에 따른 스토리지 검사.
- PR 검사에서는 Docker Hub에 이미지를 게시하거나 EC2에 배포하지 않는다.
- 인프라 main에서 Release images를 수동 실행해야 게시할 수 있다. 게시 성공만으로 운영이 바뀌지는 않는다.

Release images 입력:

- release: 재사용하지 않는 소문자 릴리스 이름.
- web_sha, backend_sha, ai_sha: 각 앱 저장소의 정확한 40자리 소문자 commit SHA.
- publish: 실제 게시 시 true. false는 빌드만 수행한다.

현재 세 서비스 이미지는 모두 docker.io/choihwanwoo1234/dodam-web 저장소에 게시하며, 태그 앞의 web-/backend-/ai-로 구분한다. 태그는 서비스·릴리스·Actions run ID·attempt를 포함한다. Docker Hub 인증에는 DOCKERHUB_TOKEN secret을 사용한다.

게시 후 image-digests artifact의 image-digests.txt를 보관한다. 각 행은 서비스명, digest, 소스 SHA다. 서로 다른 앱에 하나의 SHA를 공통 적용하지 않는다. PR 빌드의 smoke SHA도 운영 최신 버전으로 취급하지 않는다.

## 4. 기존 운영 재배포

1. 병합된 배포 대상 세 SHA와 인프라 커밋을 확정하고 CI를 확인한다.
2. Release images를 실행하고 이미지 digest와 revision label을 대조한다.
3. 현재 환경 설정·실행 이미지·DB 백업을 접근 제한된 위치에 보관한다. S3 보존은 7절을 따른다.
4. EC2에서 각 서비스의 정확한 digest 이미지를 받는다.
5. 운영 환경 파일의 WEB_IMAGE, BACKEND_IMAGE, AI_IMAGE 중 변경 대상만 교체한다. DB·S3·인증·프로젝트 설정은 보존한다.
6. 배포 잠금을 확보한 단일 작업으로 컨테이너 교체와 검증을 수행한다.

```bash
# <digest>는 Actions artifact에서 확인한 서비스별 값으로 교체한다.
docker pull docker.io/choihwanwoo1234/dodam-web@sha256:<digest>
docker image inspect docker.io/choihwanwoo1234/dodam-web@sha256:<digest> \
  --format '{{index .Config.Labels "org.opencontainers.image.revision"}}'

# .env.ec2-check에 검증한 전체 이미지 참조를 반영한 뒤:
cd /opt/dodam/infra
(
  flock -n 9 || exit 1
  bash scripts/deploy.sh .env.ec2-check
) 9>/opt/dodam/.deploy.lock
bash scripts/status.sh .env.ec2-check
```

deploy.sh는 설정 생성·Compose 검사·기동(--no-build)·Nginx 검사/reload·상태 조회를 수행한다. 이미지 게시, 사전 백업, 자동 롤백은 하지 않는다. main에 없는 로컬 pull-deploy.sh를 필수 운영 명령으로 사용하지 않는다.

프론트만 교체하는 별도 릴리스 스크립트는 web만 --no-deps로 재생성할 수 있다. 일반 배포와 동일하게 Nginx 검사/reload, 실제 revision 및 외부 응답을 확인한다. 설정 원복과 이전 이미지 복귀는 실패를 확인한 운영자가 DB 호환성을 검토한 뒤 수행한다.

## 5. 신규 서버 최초 구성

이 절은 기존 서버를 초기화하는 절차가 아니다.

1. 시드니 EC2와 암호화 EBS, DNS, 보안 그룹을 준비한다. 웹 80/443, SSH는 관리자 IP로 제한하고 IMDSv2를 요구한다.
2. Docker Engine/Compose를 설치하고 linux/amd64 이미지와 CPU 호환성을 확인한다.
3. 인프라의 승인된 커밋을 설치하고 .env.production.example에서 신규 환경 파일을 만든다. 기존 운영 환경 파일을 덮어쓰지 않는다.
4. 도메인·PUBLIC_ORIGIN·COOKIE_SECURE·DB/JWT/내부 토큰·Kakao·AI 설정을 채운다.
5. S3 버킷과 EC2 IAM Role을 준비한다. 컨테이너 IMDSv2 접근 조건은 S3 문서를 따른다.
6. DOCUMENT_STORAGE_PROVIDER=s3, DOCUMENT_S3_BUCKET, DOCUMENT_S3_REGION을 설정한다. backend와 AI가 같은 저장소를 사용해야 한다.
7. FCM을 사용할 경우 PUSH_ENABLED와 Firebase 설정, 읽기 전용 서비스 계정 마운트를 준비한다. 테스트 로그인은 DEMO_LOGIN/DEMO_SHOWCASE_ONLY 정책에 맞춘다.
8. 검증된 이미지를 받고 NGINX_MODE=bootstrap으로 시작한다. 일반 HTTP 서비스는 준비 중 응답으로 제한한다.
9. 인증서를 발급한 뒤 https로 전환한다. 기존 운영 서버는 이미 HTTPS이므로 bootstrap으로 되돌리지 않는다.

```bash
# 현재 운영 파일 이름을 사용한 인증서 관리 예시
cd /opt/dodam/infra
docker compose --env-file .env.ec2-check -f compose.production.yml run --rm certbot \
  certonly --webroot -w /var/www/acme \
  -d dodam-ieum.duckdns.org --email <관리자-이메일>
# 최초 발급 후 NGINX_MODE=https로 설정
python3 scripts/configure.py .env.ec2-check
docker compose --env-file .env.ec2-check -f compose.production.yml exec -T web nginx -t
docker compose --env-file .env.ec2-check -f compose.production.yml exec -T web nginx -s reload
docker compose --env-file .env.ec2-check -f compose.production.yml run --rm certbot renew --dry-run
```

갱신 실행기는 scripts/renew.sh .env.ec2-check다. 예약 실행 등록 여부·최근 성공 로그·만료일은 별도로 확인한다. 스크립트 존재만으로 자동 갱신 설정 완료라고 판단하지 않는다.

Kakao Redirect URI는 https://dodam-ieum.duckdns.org/login/oauth2/code/kakao다. 실제 로그인·복귀·새로고침·로그아웃을 검증한다.

## 6. 배포 후 기능 확인

- 실행 이미지의 revision/digest가 릴리스 기록과 일치하고 네 서비스가 healthy인지 확인한다.
- HTTPS 인증서, HTTP redirect, /api/auth/config JSON, Nginx 설정을 확인한다.
- 로그인·아이 전환·가족별 데이터 접근·로그아웃을 확인한다.
- 문서 업로드·원본 조회·분석 결과와 승인 후 일정 생성을 확인한다.
- 과거 날짜·반복 종료일·달력 선택 날짜로 기록 등록/수정/삭제를 확인한다.
- PWA 설치 및 업데이트를 확인한다. 화면 새로고침과 서비스 워커 교체는 구분한다.
- FCM 구현과 실제 기기 수신은 구분하여 알림 수신·탭 이동·로그아웃 후 수신자 분리를 검증한다.
- 실제 AI 검증은 호출 비용과 문서 전송 범위를 확인하고 수행한다. health 응답만으로 분석 성공이라고 기록하지 않는다.

## 7. 백업·복구·롤백

```bash
cd /opt/dodam/infra
bash scripts/backup.sh .env.ec2-check
```

backup.sh는 web/ai/backend 쓰기를 중지한 뒤 DB custom dump, 로컬 uploads archive, 이미지 목록, checksum을 저장하고 서비스를 다시 시작한다. 점검 시간을 확보하고 재시작 상태를 확인한다.

**이 스크립트는 S3 객체를 백업하지 않는다.** 현재 문서는 S3에 있으므로 로컬 uploads.tar.gz만으로 문서 복구가 완료되지 않는다. 쓰기 중지 시점의 DB 참조 객체와 S3 버전을 함께 식별·보존하고 별도 저장소 보관·복원 절차를 검증한다. S3 Versioning만으로 독립 백업이 완성되지는 않는다.

복원은 별도 Compose 프로젝트·포트·새 볼륨에서 검증한다. 운영 DB를 덮어쓰거나 down -v를 실행하지 않는다. 현재 코드가 적용한 Flyway 스키마와 이전 이미지가 호환될 때만 이미지 롤백을 한다. S3 전환 이후 파일이 S3에만 존재할 수 있으므로 저장소 설정만 local로 되돌리지 않는다.

외부 백업 자동화·모니터링 대시보드·복원 훈련의 완료 여부는 운영 기록으로 확인한다. 이 가이드 수정은 그러한 기능을 새로 설치하거나 배포한 작업이 아니다.

## 8. 장애 확인 순서와 릴리스 기록

- 접속 실패: DNS·보안 그룹·EC2·web·인증서.
- 502: backend/ai health·내부 서비스 DNS·Nginx reload·로그.
- 문서 조회 실패: 가족 권한·S3 역할·bucket/region·object key·서명 URL 만료.
- AI 오류: 내부 토큰 일치·DB·외부 API/모델 접근·분석 작업 상태.
- 날짜 승인 실패: 화면 오류 안내·API 응답 코드·실제 운영 이미지 revision.
- 화면 미반영: 배포 digest·HTML 캐시·서비스 워커 업데이트.
- Flyway 실패: 적용 버전·checksum·로그. 이미 적용된 migration을 수정하거나 볼륨을 지워 해결하지 않는다.

배포 기록에는 시각/실행자, 앱별 SHA/digest, 인프라 SHA, 환경 파일/프로젝트, DB migration, 백업 및 S3 보존 위치, 검증 범위, 남은 이슈, 이전 버전과 복구 조건을 남긴다. 비밀값과 의료 문서 본문은 기록에서 제외한다.

[README](README.md) · [S3 문서](S3_DOCUMENT_STORAGE.md) · [검증 기록](RESULTS.md) · [EC2 초기 준비](EC2_SYDNEY.md)

# 도담 AWS 배포 실행 가이드

팀 이음 · 학술제 프로젝트 · 작성 기준 2026-11-07

로컬 검증 → AWS 준비 → 최초 배포 → HTTPS·로그인 → 기능 검증 → 자동화 → 운영·복구 순서로 진행한다. 기존 CNS TIL의 배포 가이드 형식을 도담의 React·Spring·FastAPI·PostgreSQL 구성에 맞췄다. 이 문서는 실행 계획이며 AWS 배포 완료 보고서가 아니다.

## 01. 현재 위치와 완료 기준

**확인 완료:** 세 앱 이미지 빌드, 네 컨테이너 기동, HTTP·프록시 등 20개 검사, 새 DB Flyway 24개 적용, 별도 DB 복원. 실제 실행 기록은 [RESULTS.md](RESULTS.md)에 있다. 빌드 성공은 전체 기능 테스트 성공과 다르다.

**아직 미실행:** AWS 생성, 운영 도메인·공개 HTTPS, 실제 카카오 로그인, 휴대전화 검증, ECR·SSM 자동 배포, 외부 백업과 모니터링. 이번 문서 작성에서도 유료 AI를 호출하지 않는다.

검증 소스는 frontend `3b502c4`, backend `ee16762`, ai-backend `6da9b00`이다. 이것이 이후에도 최신이라는 뜻은 아니다. 배포 직전 각 저장소의 병합 상태를 다시 확인하고 세 개의 전체 커밋 SHA를 기록한다. 미병합 PR과 로컬 변경을 배포 완료로 표시하지 않는다.

- [ ] 배포할 프론트·백엔드·AI·인프라 커밋이 정해졌다.
- [ ] 실제 HTTPS에서 로그인·권한·핵심 기능을 확인했다.
- [ ] 재시작 후 DB와 업로드 파일이 유지된다.
- [ ] 백업을 별도 환경에 복원하고 문서와 DB의 일치를 확인했다.
- [ ] 배포 버전, 결과, 남은 제한, 담당자를 기록했다.

## 02. 도담 배포 구성

**첫 배포안은 EC2 1대 + Docker Compose다.** Kubernetes와 다중 서버는 이번 필수 범위에 넣지 않는다. 단일 서버 장애 시 서비스가 중단되는 구성임을 전제로 백업과 복구 절차를 준비한다. 서버 사양은 예산과 실제 메모리 사용량을 확인한 뒤 결정한다.

```text
사용자 브라우저 / 설치형 앱
          │ HTTPS 443
          ▼
web : Nginx + React 정적 파일
          │ /api 등 실제 백엔드 경로
          ▼
backend : Spring Boot 8081 ──────► ai : FastAPI 8006
          │                         │
          └──── PostgreSQL + pgvector 5432
          └──── 공유 문서 저장소 uploads ────┘
```

EC2 밖에 공개하는 앱 포트는 80·443이다. 8081·8006·5432는 공개하지 않는다. AI 서버를 프론트가 직접 호출하지 않는다. 업로드 파일과 DB는 컨테이너를 교체해도 유지되는 별도 볼륨에 저장한다. Nginx에 원본 업로드 볼륨을 공개하지 않는다.

- `Dodam_frontend`: 화면과 프론트 빌드 소스.
- `Dodam_backend`: 인증·업무 API·DB 마이그레이션.
- `Dodam_AI_backend`: 문서 분석·AI 처리.
- `Dodam_infra`: Dockerfile, Compose, Nginx, 배포 실행기, 검증·복구 기록.

현재 실행 파일 위치는 `C:\dodam\infra`, 깨끗한 검증 소스는 `C:\dodam\deployment-sources`다. 별도 프로젝트의 환경 파일·키·DB는 가져오지 않는다.

## 03. 시작 전에 결정할 값과 공개 차단 사항

현재 사용 계정은 구글 로그인으로 만든 무료 플랜 프로젝트이며 리전은 **시드니(ap-southeast-2)**다. 공유된 화면의 크레딧은 100달러다. 서버·도메인·예산 한도는 아직 미정이다. 생성 화면의 구체적인 선택값은 [시드니 EC2 설정 안내](EC2_SYDNEY.md)를 따른다. 가이드의 `<...>`는 실제 값을 확인한 뒤 바꿀 입력란이다. 키나 비밀번호를 입력하는 란이 아니다.

- 계정과 리전, 예산 알림 수신자, 서비스 종료·자원 정리 시점.
- EC2 CPU 아키텍처·메모리·디스크, 관리자 접속 방식, 도메인과 고정 주소.
- 운영 키 보관 담당자, 백업 저장소·보존 기간·복원 담당자.
- 실제 배포할 커밋과 담당 기능의 병합 상태.

**서비스 공개 전에 해결하거나 제한을 합의할 항목**

- 원본 문서 정적 경로에 아이별 권한 검사가 없어 현재 `/local-documents`는 403으로 막았다. 권한을 확인하는 다운로드 경로가 준비되기 전 차단을 풀지 않는다. 현재 상태로 원본 보기까지 완료했다고 기록할 수 없다.
- AI 서버는 빈 임베딩 키로 기동되지 않았다. 운영 키·모델을 담당자와 확인하거나 지연 초기화 수정을 반영한다. 로컬 가짜 키를 운영에 사용하지 않는다.
- 현재 검증 버전에는 PWA manifest와 서비스 워커가 없다. 앱 전환 PR을 확인해야 한다. 설치 성공과 실제 푸시 수신은 별도 검증이다.
- 카카오 로그인·쿠키 관련 수정과 우리 담당 미병합 기능을 확인하고 다시 빌드한다.

완료 기준: 값을 확정한 담당자와 확인 날짜를 남긴다. AWS 무료 사용·크레딧 적용을 추정하지 않는다.

## 04. 유료 AI 호출 없이 로컬 검증

Windows PowerShell에서 실행한다. Docker Desktop의 Linux 컨테이너와 Python 3가 필요하다. 이미 `.env.production.local`이 있으면 생성기를 다시 실행하지 않는다. 생성기는 기존 파일을 덮어쓰지 않는다.

```powershell
Set-Location C:\dodam\infra
docker version
docker compose version
# 로컬 환경 파일이 없는 첫 실행에만:
python scripts/init-local.py
docker compose --env-file .env.production.local -f compose.production.yml config --quiet
.\scripts\build.ps1
docker compose --env-file .env.production.local -f compose.production.yml up -d --no-build --wait --wait-timeout 240
docker compose --env-file .env.production.local -f compose.production.yml ps
docker compose --env-file .env.production.local -f compose.production.yml exec -T web nginx -t
curl.exe -i http://localhost:4280/api/auth/config
```

로컬 파일은 가짜 임베딩 키와 차단된 LLM 주소, 앱 네트워크 외부 통신 차단을 사용한다. 운영 키를 넣지 않는다. Python이 PATH에 없다면 설치된 실행 파일의 절대 경로를 사용한다. 추가 검증 실행 방법은 `scripts/verify-local.py`, `scripts/verify-ops-local.py`의 입력과 검사 내용을 먼저 확인한다.

**정상:** 네 컨테이너 healthy, 로그인 화면 표시, 인증 설정 JSON 200, 데모 로그인 비활성화. **실패:** DB 비밀번호·마이그레이션·서비스 로그를 확인한다. 기존 DB 볼륨을 지워 해결하지 않는다. 502라면 backend·ai 기동과 서비스 이름을 확인한다.

## 05. AWS 서버 준비

AWS 콘솔에서 계정과 리전을 확인한다. 예산 알림을 먼저 설정한다. EC2·EBS·공인 IPv4·전송·도메인·백업·ECR 비용을 검토한다. 정확한 금액은 선택한 사양과 계정 조건으로 계산한다.

1. 지원되는 Ubuntu LTS와 이미지 빌드에 맞는 CPU 아키텍처를 선택한다. 현재 검증은 Linux amd64 기준이다.
2. EBS 암호화와 종료 시 디스크 처리 정책을 확인한다. 서비스 종료 전 데이터 보존 여부를 결정한다.
3. 보안 그룹은 웹 80·443, SSH를 쓸 경우 관리자 IP의 22만 허용한다. DB와 AI 포트는 열지 않는다.
4. IMDSv2를 요구하고 서버 역할에 필요한 권한만 부여한다.
5. 서버 running·상태 검사 통과·관리 접속을 확인한다. Docker Engine과 Compose 플러그인을 설치한다.
6. 고정 주소 필요 여부를 결정하고 도메인 A 레코드를 연결한다. 사용하지 않는 IPv6 AAAA 레코드는 두지 않는다.

Docker 설치 명령은 [README 4절](README.md#4-ec2-docker와-환경-준비)과 [Docker 공식 Ubuntu 설치 안내](https://docs.docker.com/engine/install/ubuntu/)를 따른다. Docker가 공개한 포트는 호스트 방화벽만으로 차단된다고 가정하지 말고 보안 그룹·Compose 설정도 확인한다.

```bash
# EC2 Ubuntu
uname -m
free -h
df -h
docker version
docker compose version
sudo install -d -m 700 /opt/dodam/infra
```

완료 기준: 관리자 접속, Docker 서버 응답, 아키텍처 일치, DNS 확인. 아직 웹 서비스 배포 완료는 아니다.

## 06. 최초 배포: 검증 이미지 전달

**현재 저장소가 지원하는 실행 경로다.** 로컬에서 이미지와 배포 파일을 묶고 EC2에 전달한다. 서버에서 소스를 빌드하지 않는다. 자동화는 10절의 후속 작업이다.

배포용 소스 세 개가 깨끗하고 승인된 커밋인지 확인한다. 새 RELEASE_TAG로 다시 빌드하고 빌드 후 소스를 변경하지 않는다. 동일 태그를 다른 이미지에 재사용하지 않는다. 현재 export 스크립트는 세 소스 SHA·인프라 SHA·이미지 ID를 기록하지만, 과거 빌드와 현재 소스가 같은지 자동 증명하지 않으므로 이 순서를 지킨다.

```powershell
# 로컬 PowerShell — .env.production.local의 RELEASE_TAG를 새 값으로 정한 뒤
Set-Location C:\dodam\infra
.\scripts\build.ps1
.\scripts\export-release.ps1
scp -i '<키 파일 경로>' releases/<RELEASE_TAG>/images.tar releases/<RELEASE_TAG>/infra.tar.gz releases/<RELEASE_TAG>/versions.json releases/<RELEASE_TAG>/checksum.json ubuntu@<서버 주소>:/home/ubuntu/
```

export는 인증서 이미지도 받으므로 인터넷 연결이 필요하다. 이것은 유료 AI 호출이 아니다. 전송 전 묶음에 실제 `.env`·키·개인 문서가 없는지 확인한다. 현재 체크섬은 images.tar 대상이다. infra.tar.gz와 versions.json도 배포 전 별도 SHA256을 계산해 전송 후 비교한다.

```bash
# EC2: sudo -i로 전환한 관리자 셸
cd /opt/dodam/infra
sha256sum /home/ubuntu/images.tar /home/ubuntu/infra.tar.gz /home/ubuntu/versions.json
# 로컬에서 계산한 각 해시와 비교한 뒤 계속한다.
docker load -i /home/ubuntu/images.tar
tar -xzf /home/ubuntu/infra.tar.gz
cp /home/ubuntu/versions.json deployed-versions.json
umask 077
cp .env.production.example .env.production
nano .env.production
chmod 600 .env.production
```

환경 파일의 주요 값:

- RELEASE_TAG: 전달한 세 이미지의 태그. PLATFORM: 서버 아키텍처.
- DOMAIN: 실제 호스트명. PUBLIC_ORIGIN: `https://실제호스트명`.
- BIND_ADDRESS=`0.0.0.0`, HTTP_PORT=`80`, HTTPS_PORT=`443`, NGINX_MODE=`bootstrap`, COOKIE_SECURE=`true`.
- POSTGRES_PASSWORD·JWT_SECRET·AI_INTERNAL_TOKEN: 각각 별도로 생성한 64자리 이상 난수 hex. 실제 값은 Git·채팅·스크린샷에 남기지 않는다.
- KAKAO_CLIENT_ID·KAKAO_CLIENT_SECRET: 도담 카카오 앱 설정과 일치.
- OPENAI_API_KEY·LLM_API_KEY·EMBEDDING_API_KEY: 담당자에게 용도별 확인. 모델 이름·임베딩 차원도 확인하고 예시 기본값을 운영 승인으로 취급하지 않는다.
- ISOLATE_NETWORK=`false`: 운영 외부 API 통신 허용. 로컬 검증 파일과 구분한다.
- GOV24_WELFARE_SERVICE_KEY: 복지 담당자에게 확인. 현재 Compose는 자동 동기화가 꺼져 있으므로 키만 넣었다고 복지 데이터 수집이 시작되지는 않는다.

```bash
bash scripts/deploy.sh .env.production
curl -i http://127.0.0.1/nginx-health
```

정상: 컨테이너 healthy·nginx-health 200. 일반 화면은 HTTPS 준비 중 503이다. bootstrap 상태에서 HTTP 로그인 화면을 공개하지 않는다.

## 07. HTTPS와 실제 로그인

도메인 DNS와 80 접근을 먼저 확인한다. 아래 `<도메인>`·`<이메일>`을 바꾼다. Certbot 이용 약관을 확인한 뒤 진행한다.

```bash
# EC2 관리자 셸, /opt/dodam/infra
docker compose --env-file .env.production -f compose.production.yml run --rm certbot certonly --webroot -w /var/www/acme -d <도메인> --email <이메일>
# 발급 성공 후 .env.production의 NGINX_MODE=https로 변경
nano .env.production
python3 scripts/configure.py .env.production
docker compose --env-file .env.production -f compose.production.yml exec -T web nginx -t
# 위 검사가 성공했을 때만:
docker compose --env-file .env.production -f compose.production.yml exec -T web nginx -s reload
curl -I http://<도메인>
curl -I https://<도메인>
docker compose --env-file .env.production -f compose.production.yml run --rm certbot renew --dry-run
```

정상: HTTP는 HTTPS로 308, HTTPS 인증서 유효, HTML은 no-cache. 실패하면 DNS A/AAAA·보안 그룹·인증서 경로를 확인한다. 인증서 경고를 무시하고 통과시키지 않는다. 자동 갱신은 README 6절의 renew.sh 예약 실행을 등록하고 로그·만료일을 확인한다.

카카오 개발자 콘솔에 실제 HTTPS 사이트와 `https://<도메인>/login/oauth2/code/kakao`를 등록한다. 실제 기기에서 로그인 → 복귀 → 새로고침 유지 → 로그아웃을 확인한다. 데모 계정으로 대체하지 않는다. Cookie Secure·HttpOnly·SameSite와 HTTPS 리다이렉트도 확인한다.

완료 기준: 외부 기기에서 인증서 오류 없이 접속하고 실제 로그인 유지·로그아웃이 동작한다.

## 08. 도담 기능 인수 검사

컨테이너 healthy는 프로세스 생존 확인이다. 업무 흐름 성공은 별도다. 합성 데이터와 검증용 계정으로 아래 항목을 확인하고 `RESULTS.md`에 배포 버전·결과·증거·이슈를 기록한다.

- 최환우: 로그인 유지, 가족별 접근 권한, 방문 기록, 메모·태그, 할 일 생성·조회·수정·삭제·완료, 캘린더 반영, 종료일·무기한 복약 반복, 앱 내 알림, 성장 그래프 기간별 표시.
- 정재헌 연동: 문서 업로드와 기존 병원 기록 연결, 진행·실패 표시, 원본 권한, 예방접종, 앱 설치·업데이트. 타 담당 기능은 확인 후 수정 요청한다.
- 유한세 연동: 문서 설명·채팅·복지 추천 화면과 API 오류 처리. 실제 유료 모델 호출은 사용자 명시 요청을 받은 경우에만 별도 실행한다.
- 앱 전환: manifest·서비스 워커·아이콘·캐시 정책. 실제 배포 파일명과 scope를 확인한다. 현재 검증 소스에서 sw.js와 manifest의 404는 미포함을 의미한다.
- 알림: 앱 안의 알림 목록과 실제 백그라운드 푸시를 구분한다. FCM·APNs·Web Push 중 어느 것도 확정 구현으로 기록하지 않는다.
- 개인정보: 다른 가족의 아이·문서 접근 차단, 로그아웃·계정 변경 후 이전 자료 노출 없음, 인증 API와 문서를 서비스 워커에 무분별하게 저장하지 않음.

실제 분석·채팅을 호출하지 않은 경우 “AI 서버 기동·연결 확인 / 유료 추론 미실행”으로 기록한다. 이를 AI 전체 기능 통과로 바꾸지 않는다.

## 09. 모니터링과 백업·복구

**현재 지원:** 로그 용량 제한, 컨테이너 healthcheck, status.sh, backup.sh, 인증서 갱신 스크립트. **추가할 것:** 외부 장애 알림, 메트릭 수집·대시보드, 외부 백업 자동화. 아직 Prometheus·Grafana를 설치했다고 기록하지 않는다.

첫 운영에서는 접속 실패·컨테이너 재시작·메모리·디스크·5xx·인증서 만료·백업 성공 여부를 확인한다. 메트릭 도입 시 Spring·AI의 실제 제공 지표를 확인하고 관리 화면은 인터넷에 직접 공개하지 않는다. AI 호출 수와 비용은 제공업체 사용량과 대조한다.

```bash
# EC2 관리자 셸
cd /opt/dodam/infra
bash scripts/status.sh .env.production
docker compose --env-file .env.production -f compose.production.yml logs --tail 100 backend
bash scripts/backup.sh .env.production
```

backup.sh는 web·ai·backend를 멈추므로 점검 시간을 안내하고 진행한다. DB와 업로드를 같은 시점으로 보관하고 재시작 후 healthy를 다시 확인한다. 백업 해시를 확인하고 접근 제한·암호화된 외부 저장소로 옮긴다. 같은 EC2 안에만 남은 백업은 서버 손실에 대비한 백업이 아니다.

복구는 운영 DB를 덮어쓰지 않고 별도 디렉터리·Compose 프로젝트·포트·볼륨에서 검증한다. README 9절의 복원 명령을 사용하되 프로젝트 이름과 볼륨이 운영과 다른지 먼저 검사한다. DB와 uploads를 한 세트로 복원한 후 문서 접근·가족 권한·핵심 기능을 확인한다. 복구 환경은 실제 AI 호출이 나가지 않도록 격리한다.

이미지 롤백은 이전 코드가 새 DB 스키마와 호환되는 경우에만 수행한다. RELEASE_TAG를 이전 값으로 바꾸고 deploy.sh로 반영한 뒤 검사한다. DB 마이그레이션을 삭제하거나 운영에 `down -v`를 실행하지 않는다. 현재 deploy.sh에는 자동 롤백이 없다.

## 10. 후속 자동화: ECR·GitHub Actions·SSM

**이 절은 구현할 설계다. 현재 저장소에 이 자동화 workflow는 없다.** 최초 배포와 복구를 검증한 뒤 연결한다. 수동 배포가 검증되지 않은 상태에서 push 즉시 운영 반영을 활성화하지 않는다.

```text
승인된 소스 커밋 3개 + 인프라 커밋
     → 무료 범위 테스트 / 이미지 빌드
     → ECR에 커밋별 이미지 게시
     → 배포 버전 묶음 검토
     → SSM으로 EC2에 지정 버전 전달
     → 컨테이너 교체 / 상태·기능 검사
     → 성공 기록 또는 호환성 확인 후 이전 앱 버전 복구
```

**A. 저장소와 이미지 계약**

ECR 저장소 제안 이름은 `dodam/frontend`, `dodam/backend`, `dodam/ai`다. 태그는 각 소스 전체 SHA, 운영에서는 이미지 digest까지 기록한다. 프론트·백·AI는 서로 다른 SHA이므로 하나의 `$GITHUB_SHA`를 세 앱 버전으로 사용하지 않는다. 인프라 릴리스 기록에 세 소스 SHA·세 이미지 digest·인프라 SHA를 묶는다.

현재 Compose는 `dodam-web:<RELEASE_TAG>` 같은 로컬 이미지 이름을 사용한다. ECR 도입 전 WEB_IMAGE·BACKEND_IMAGE·AI_IMAGE 같은 전체 이미지 참조를 받도록 수정하고 로컬·운영 두 경로를 검증해야 한다. 지금 ECR 주소만 환경 파일에 추가해서 동작한다고 가정하지 않는다.

**B. 빌드 위치와 비공개 소스 접근**

초기에는 인프라 workflow가 지정된 세 소스를 받아 기존 Dockerfile로 빌드하도록 구성한다. 비공개 앱 저장소를 읽는 권한은 저장소 범위를 제한한 GitHub App 등으로 부여한다. 기본 GITHUB_TOKEN만으로 다른 비공개 저장소를 읽을 수 있다고 가정하지 않는다. 앱 저장소 workflow로 분리할 경우 Dockerfile과 빌드 규칙의 소유권을 먼저 합의한다.

**C. AWS 권한**

GitHub는 OIDC 임시 권한을 사용하고 장기 AWS 액세스 키를 저장하지 않는 방향으로 구성한다. 빌드 역할은 지정 ECR 게시, 배포 역할은 지정 설정 저장소·인스턴스 명령 실행으로 제한한다. EC2 역할은 필요한 ECR 읽기·설정 읽기·SSM 권한을 갖는다. 비공개 S3 배포 묶음에는 비밀값과 의료 문서를 넣지 않는다.

OIDC 신뢰 정책은 실제 저장소 subject 형식을 확인해 작성한다. 특히 새 저장소에는 owner/repo의 불변 ID가 포함될 수 있으므로 예전 가이드의 문자열을 그대로 복사하지 않는다. GitHub `production` 환경과 허용 브랜치를 제한하고 제공되는 승인 기능도 확인한다. [GitHub 공식 OIDC 안내](https://docs.github.com/en/actions/how-tos/secure-your-work/security-harden-deployments/oidc-in-aws)

EC2에는 SSM Agent·관리 권한·서비스 통신 경로를 준비하고 Online을 확인한다. 상세 역할 조건은 [AWS 공식 안내](https://docs.aws.amazon.com/systems-manager/latest/userguide/session-manager-getting-started-instance-profile.html)를 확인한다. SSM 명령 요청 성공만으로 배포 성공 처리하지 않고 최종 명령 종료 상태와 서버 검사까지 기다린다.

**D. 만들어야 할 자동화 파일과 동작**

- CI workflow: 소스 SHA 입력·소스 조회·비용 없는 테스트·이미지 빌드·ECR 게시·digest 기록.
- release manifest: 세 앱과 인프라 버전, 마이그레이션, 검사 결과, 이전 릴리스.
- 배포 workflow: manifest 검토·SSM 호출·최종 실행 결과 수집. 동일 환경 동시 배포는 하나로 제한.
- 서버 실행기: 이미지 digest 확인·설정 검사·이미지 받기·교체·검증·성공 기록. 실패 시 자동 DB 되돌리기는 하지 않음.
- 운영 비밀값은 서버의 제한된 파일 또는 선택한 비밀 관리 서비스에서 주입. 배포 묶음이 운영 비밀값을 덮어쓰지 않도록 구성.

완료 기준: 비운영 환경에서 정상 배포와 의도적인 실패를 모두 시험하고, 실패 표시·이전 버전 복구·기록까지 확인한다. 그 후 운영에 적용한다.

## 11. 문제 발생 시 확인 순서

- **접속 불가:** DNS → 보안 그룹 → 서버 상태 → web 포트 → Nginx 설정.
- **502:** backend·ai 컨테이너 health → 로그 → 서비스 DNS·내부 포트. 외부 포트를 열어 우회하지 않는다.
- **로그인 반복:** 사이트 origin·카카오 callback·HTTPS 전달 헤더·쿠키·프론트 복귀 주소.
- **문서 403:** 현재 원본 경로 차단인지 확인. 권한 API 구현 없이 정적 경로를 공개하지 않는다.
- **AI 시작 실패:** 키 존재·모델 설정·DB와 pgvector 연결 확인. 진단을 위해 유료 요청을 자동 실행하지 않는다.
- **DB migration 실패:** 적용 버전·체크섬·실패 로그 확인. 기존 migration을 덮어쓰거나 운영 볼륨을 삭제하지 않는다.
- **새 화면 미반영:** 배포 이미지 SHA → HTML 캐시 → 서비스 워커 업데이트 순으로 확인.
- **SSM Offline 또는 AccessDenied:** Agent → EC2 역할 → 통신 경로 → 대상 리전·인스턴스 확인. 전체 관리자 권한으로 확대해 해결하지 않는다.

## 12. 배포 기록과 진행 순서

아래는 배포할 때마다 채우는 기록 양식이다. 실제 값이 생기기 전에는 배포 완료로 표시하지 않는다.

```text
배포 일시 / 실행자:
AWS 계정 식별 / 리전 / 인스턴스 식별:
서비스 HTTPS 주소:
프론트 SHA / 이미지 digest:
백엔드 SHA / 이미지 digest:
AI SHA / 이미지 digest:
인프라 SHA:
DB migration / 사전 백업 위치:
확인한 화면·API / 결과:
AI 유료 호출: 미실행 또는 별도 승인 범위와 결과
남은 문제 / 담당자 / 연결 이슈:
이전 버전 / 복구 가능 여부:
```

회의 기준 일정은 11월 9일 담당 기능 개선, 11월 10일 앱 전환, 11월 11~12일 통합 오류 수정, 11월 12~13일 배포, 11월 13~14일 최종 점검이다. 현재 코드 상태가 이 일정의 완료를 증명하지는 않는다. 배포는 최환우가 진행하고 문서·앱 전환은 정재헌, AI·복지 연동은 유한세와 확인한다.

**바로 진행할 순서:** 미병합 기능·차단 사항 확인 → AWS·도메인 결정 → 승인 버전으로 로컬 재검증 → 최초 EC2 배포 → HTTPS·실제 기기 검사 → 백업·복원 확인 → 자동화 연결. 새 기능 구현과 배포 완료를 구분해 기록한다.

참고: CNS TIL 배포_템플릿/배포_가이드라인.html, 도담 [README](README.md), [소스 점검](AUDIT.md), [실행 결과](RESULTS.md). 원본 가이드의 샘플 앱·Java·DB 설정은 도담에 복사하지 않았다.

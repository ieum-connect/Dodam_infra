# 도담(팀 이음) 단일 EC2 배포 안내

현재 계정은 **시드니(ap-southeast-2)** 프로젝트다. 서버 생성은 [시드니 EC2 설정 안내](EC2_SYDNEY.md)를 따른다. 운영 환경 생성기는 `scripts/init-production.py`, 서버 읽기 전용 점검은 `scripts/check-ec2.sh`다.

처음 진행할 때는 [단계별 배포 가이드](DEPLOYMENT_GUIDE.md) 또는 [브라우저용 가이드](도담_배포_가이드라인.html)를 먼저 읽는다. 최초 수동 배포와 후속 ECR·GitHub Actions·SSM 자동화 설계를 구분해 설명한다.

이 문서는 **로컬 검증 → AWS 준비 → HTTPS → PWA 확인** 순서다. SilverCare와 무관하다. 현재 소스와 운영 차단 사항은 [AUDIT.md](AUDIT.md), 실행 결과는 [검증 결과](RESULTS.md)에 기록한다. 개인 무료 플랜 프로젝트의 시드니 리전을 사용하며 서버·도메인은 미정이다. 현재 AWS 배포 완료 주소는 없다.

## 1. 구성과 사전 조건

목적: 검증 가능한 소스와 이미지 버전을 고정한다.

- 서비스명: `web`(Nginx+React), `backend`(Spring 8081), `ai`(FastAPI 8006), `postgres`(5432), 도구 `certbot`.
- 공개 포트는 web의 80/443뿐이다. 기본 BIND_ADDRESS=127.0.0.1은 로컬 검증용이며 EC2에서는 승인된 공개 배포 시 0.0.0.0으로 바꾼다.
- 초기 방식은 **로컬 Linux 이미지 빌드 → docker save → SSH/scp 전달 → docker load**다. EC2에서 앱 빌드를 하지 않는다. amd64는 현재 로컬 검증 대상이며 EC2 아키텍처 확정이 아니다. ARM을 선택하면 PLATFORM=linux/arm64로 별도 빌드·검증한다.
- 기존 작업 사본은 변경하지 않는다. SOURCE_ROOT 아래에는 승인된 커밋의 깨끗한 사본만 둔다. 배포 파일은 C:/dodam/infra, 검증 소스는 C:/dodam/deployment-sources다.
- 프런트는 npm ci와 npm run build를 사용한다. 운영 Vite 서버는 없다. VITE_API_BASE_URL은 빌드 시 빈 값으로 상대 경로를 사용하며 변경하려면 재빌드한다. VITE_ 변수에 비밀 키를 넣지 않는다.
- 공유 업로드 볼륨은 두 앱 UID 10001로 접근한다. Nginx에는 이 볼륨을 마운트하지 않는다.

## 2. 로컬 실행

목적: 외부 AI 호출 없이 DB·마이그레이션·앱 기동·프록시를 검증한다. Docker Desktop Linux 컨테이너와 Python 3가 필요하다.

[로컬 Windows PowerShell]
```powershell
Set-Location C:\dodam\infra
docker version
docker compose version
python scripts/init-local.py
docker compose --env-file .env.production.local -f compose.production.yml config --quiet
.\scripts\build.ps1
docker compose --env-file .env.production.local -f compose.production.yml up -d --no-build --wait --wait-timeout 240
docker compose --env-file .env.production.local -f compose.production.yml ps
docker compose --env-file .env.production.local -f compose.production.yml exec -T web nginx -t
curl.exe -i http://localhost:4280/api/auth/config
curl.exe -I http://localhost:4280/index.html
```

init-local.py는 이미 파일이 있으면 보존하고 중단한다. 로컬 전용 무작위 비밀번호/토큰을 생성한다. AI가 빈 임베딩 키로 기동되지 않아 로컬에는 식별 가능한 가짜 임베딩 키, 막힌 loopback LLM 주소, 앱/DB 외부 통신 차단 네트워크를 적용한다. 실제 운영 키는 이 파일에 넣지 않는다. Python이 PATH에 없으면 설치된 python.exe 절대 경로를 사용한다.

정상: 네 서비스 healthy, auth/config JSON, index.html 200 및 no-cache. 실패 시:
- Docker 연결 실패: Desktop Linux engine 확인.
- build 실패: build-local.log와 패키지 다운로드/네트워크 확인. 키를 추가해서 빌드를 고치지 않는다.
- DB 실패: postgres 로그 및 named volume 상태 확인. 이미 초기화된 DB의 비밀번호는 env 변경만으로 바뀌지 않는다.
- Flyway 실패: backend 로그의 버전/체크섬을 확인하고 적용된 migration을 수정하지 않는다.
- 502: backend/ai health와 DNS 서비스명 확인. 컨테이너에서 localhost는 자기 자신이다.

[로컬 Windows PowerShell]
```powershell
docker compose --env-file .env.production.local -f compose.production.yml logs --tail 100 backend
docker compose --env-file .env.production.local -f compose.production.yml logs --tail 100 ai
docker compose --env-file .env.production.local -f compose.production.yml exec -T postgres psql -U dodam -d dodam -c 'SELECT version, success FROM flyway_schema_history ORDER BY installed_rank;'
docker compose --env-file .env.production.local -f compose.production.yml exec -T ai python -c "import urllib.request; print(urllib.request.urlopen('http://localhost:8006/health').status)"
```

로그는 비밀 값·문서 내용이 없는지 확인한 뒤 공유한다. config 전체 출력을 사용하지 않는다. 로컬 HTTP는 실제 휴대전화 HTTPS/PWA 검증이 아니다.

## 3. AWS 선택과 비용 확인 — 아직 실행하지 않음

목적: 서버 생성 전에 계정·예산·도메인·백업 정책을 확정한다.

[AWS 콘솔]
1. 구글 로그인으로 기존 프로젝트에 접속하고 시드니(ap-southeast-2)를 확인. AWS Settings/청구 관리에서 실제 크레딧 조건·만료일 확인. Budgets에서 예산과 알림 수신자 설정. 현재 가입 방식에서는 리전 메뉴나 URL로 서울로 전환하지 않는다.
2. EC2 → Instances → Launch instances. 이름 `dodam-production`. Ubuntu LTS와 아키텍처를 선택하되 이미지 PLATFORM과 일치시킨다. 사양·gp3 디스크 용량은 부하/예산 확인 후 결정한다. 1GB RAM에서 세 앱+DB가 안정적이라고 가정하지 않는다.
3. Key pair(login) → 새 키 또는 승인된 기존 키. 개인키는 개인 PC에 보관하고 공유·저장소 업로드 금지. Network settings → 관리자 공인 IP/32만 SSH 22 허용, 웹 80/443 허용. 5432/8081/8006은 열지 않는다.
4. Storage → 암호화 활성화, 크기/종료 시 삭제 정책 확인. Advanced details → IMDSv2 required. Instance profile은 실제 필요한 권한만 부여한다.
5. EC2 → Elastic IP addresses에서 고정 IPv4 필요 여부 결정. 비용을 확인하고 선택하면 Allocate → Associate로 서버에 연결한다.
6. DNS 제공업체 또는 Route 53 → Hosted zones → 선택한 도메인의 A 레코드를 서버 IPv4로 설정한다. IPv6를 제공하지 않으면 잘못된 AAAA 레코드를 두지 않는다.

과금 항목: EC2 실행, EBS, 공인 IPv4, 데이터 전송, DNS/도메인, 외부 백업 저장·요청, 별도 AI API. 무료/크레딧 여부와 금액은 계정·리전·사양 확정 전 단정하지 않는다. [AWS IPv4 요금](https://aws.amazon.com/vpc/pricing/)과 [보안 그룹 공식 설명](https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/ec2-security-groups.html)을 확인한다.

정상 확인: 인스턴스 running, 상태 검사 통과, 관리 IP에서 SSH 가능, 공개된 인바운드는 위 세 포트뿐. 실패 시 키 경로/ubuntu 사용자/서버 상태/현재 관리자 IP/보안 그룹을 차례로 확인한다.

## 4. EC2 Docker와 환경 준비

아래 `<...>`는 아직 제공되지 않은 입력값이다. 실제 서버 주소·키·도메인 확정 후 대체한다.

[로컬 Windows PowerShell]
```powershell
ssh -i '<키 파일 절대 경로>' ubuntu@<서버 주소>
```

[AWS EC2 Ubuntu]
```bash
uname -m
cat /etc/os-release
df -h
free -h
docker version
docker compose version
```

Docker가 없고 지원되는 Ubuntu인 경우 [공식 apt 설치 안내](https://docs.docker.com/engine/install/ubuntu/)를 확인해 다음을 실행한다. 기존 충돌 패키지가 있으면 공식 문서에 따라 별도 정리하며 사용자 데이터는 삭제하지 않는다.

[AWS EC2 Ubuntu]
```bash
sudo apt-get update
sudo apt-get install -y ca-certificates curl python3
sudo install -m 0755 -d /etc/apt/keyrings
sudo curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
sudo chmod a+r /etc/apt/keyrings/docker.asc
. /etc/os-release
echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu ${UBUNTU_CODENAME:-$VERSION_CODENAME} stable" | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null
sudo apt-get update
sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
sudo docker version
sudo docker compose version
sudo install -d -m 700 /opt/dodam/infra
```

이후 Ubuntu 명령은 `sudo -i`로 들어간 관리자 셸 기준이다. Docker 권한을 일반 계정에 줄지 여부는 별도로 결정한다. 공식 Docker 저장소 설치 외 임의 스크립트는 실행하지 않는다.

## 5. 이미지 전달과 최초 HTTP 기동

목적: 운영 서버에 GitHub 토큰이나 소스 빌드 도구를 두지 않고 검증 이미지를 전달한다. 최종 승인 소스와 RELEASE_TAG로 빌드 후 export한다. 같은 태그를 다른 빌드에 재사용하지 않는다.

[로컬 Windows PowerShell]
```powershell
Set-Location C:\dodam\infra
.\scripts\export-release.ps1
scp -i '<키 파일 절대 경로>' releases/<RELEASE_TAG>/images.tar releases/<RELEASE_TAG>/infra.tar.gz releases/<RELEASE_TAG>/versions.json releases/<RELEASE_TAG>/checksum.json ubuntu@<서버 주소>:/home/ubuntu/
```

[AWS EC2 Ubuntu, 관리자 셸]
```bash
cd /opt/dodam/infra
sha256sum /home/ubuntu/images.tar
# 로컬 checksum.json의 Hash와 일치하는지 비교 후 진행
docker load -i /home/ubuntu/images.tar
tar -xzf /home/ubuntu/infra.tar.gz
cp /home/ubuntu/versions.json ./deployed-versions.json
umask 077
cp .env.production.example .env.production
nano .env.production
chmod 600 .env.production
```

입력: RELEASE_TAG는 전달 이미지와 동일, DOMAIN 실제 호스트명, PUBLIC_ORIGIN=https://해당호스트, NGINX_MODE=bootstrap, BIND_ADDRESS=0.0.0.0, HTTP_PORT=80, HTTPS_PORT=443, COOKIE_SECURE=true. POSTGRES_PASSWORD/JWT_SECRET/AI_INTERNAL_TOKEN은 각각 32바이트 이상 난수 hex로 안전한 비밀 관리 도구에서 생성해 입력한다. hex만 받는 이유는 DB URL 인코딩·Compose 치환 오류 방지다. 운영 DB 비밀번호는 로컬 값을 복사하지 않는다. 내부 토큰은 Compose가 두 앱에 같은 값을 전달한다.

Kakao 키는 해당 도담 앱 값만 입력한다. 운영 AI 기동에는 유효한 임베딩 키 설정 또는 담당자의 빈 키 지연 초기화 수정이 필요하다. 키·모델 확인 전 운영 배포를 진행하지 않는다. 로컬 가짜 키는 운영에 복사하지 않는다. ISOLATE_NETWORK=false는 운영 외부 API 연결용이다. 유료 호출 테스트는 사용자 명시 승인 후 수행한다. 일반 LLM_API_KEY와 문서 OPENAI_API_KEY, EMBEDDING_API_KEY를 구분한다. 환경 변경 후 컨테이너 재생성이 필요하다.

[AWS EC2 Ubuntu, 관리자 셸]
```bash
bash scripts/deploy.sh .env.production
curl -i http://127.0.0.1/nginx-health
```

정상: nginx-health 200, 일반 HTTP는 HTTPS 준비 중 503. bootstrap 단계는 개인정보와 로그인 화면을 HTTP로 제공하지 않는다. 실패 시 상태 확인 스크립트와 서비스 로그를 점검한다.

## 6. DNS·HTTPS 발급과 갱신

목적: 인증서 없는 상태에서 Nginx 기동 실패를 피하고 검증된 도메인만 HTTPS로 제공한다. Certbot webroot 방식 하나만 사용한다.

[로컬 Windows PowerShell]
```powershell
Resolve-DnsName <도담 도메인> -Type A
curl.exe -i http://<도담 도메인>/nginx-health
```

[AWS EC2 Ubuntu, 관리자 셸]
```bash
cd /opt/dodam/infra
docker compose --env-file .env.production -f compose.production.yml run --rm certbot certonly --webroot -w /var/www/acme -d <도담 도메인> --email <관리 이메일>
# 약관은 사용자가 읽고 동의. 발급 성공 후 NGINX_MODE=https로 수정
nano .env.production
python3 scripts/configure.py .env.production
docker compose --env-file .env.production -f compose.production.yml exec -T web nginx -t
docker compose --env-file .env.production -f compose.production.yml exec -T web nginx -s reload
curl -I http://<도담 도메인>
curl -I https://<도담 도메인>
curl -I https://<도담 도메인>/sw.js
curl -I https://<도담 도메인>/manifest.webmanifest
curl -I https://<도담 도메인>/index.html
docker compose --env-file .env.production -f compose.production.yml run --rm certbot renew --dry-run
```

정상: HTTP 308, 유효한 인증서, HTML no-cache. PWA 미병합 현재 sw.js/manifest는 404가 정상이며 HTML로 대체되면 실패다. API 미인증은 JSON 401 등 API 응답이어야 한다. 원본 /local-documents는 권한 API가 준비되기 전 403 유지한다. /internal과 /api/v1 직접 접근은 404다.

실패: A/AAAA 레코드·80 인바운드·webroot 공유 볼륨·인증서 도메인 경로 확인. Nginx 검사 실패 시 reload하지 말고 active/default.conf를 이전 설정으로 되돌린다. TLS 경고를 우회해 성공으로 기록하지 않는다.

[AWS EC2 Ubuntu, 관리자 셸]
```bash
crontab -e
# 다음 한 줄 추가 (하루 2회; 전용 로그 권한 제한)
17 3,15 * * * /bin/bash /opt/dodam/infra/scripts/renew.sh /opt/dodam/infra/.env.production >> /var/log/dodam-cert-renew.log 2>&1
```

갱신 성공 후 nginx -t 및 reload를 자동 실행한다. 실제 timer 실행·로그와 인증서 만료일을 확인해야 자동 갱신 검증 완료다. [Certbot 갱신 안내](https://eff-certbot.readthedocs.io/en/stable/using.html#renewing-certificates).

## 7. Kakao 로그인

[카카오 개발자 콘솔]
- 내 애플리케이션 → 도담 앱 → 앱 설정/플랫폼 → Web 사이트 도메인에 실제 HTTPS origin.
- 카카오 로그인 → 사용 설정 → 상태 ON. 앱 → 플랫폼 키 → REST API 키 → 리다이렉트 URI에 `https://<도담 도메인>/login/oauth2/code/kakao`.
- 앱 키에서 도담 REST API 키 확인, 사용 중이면 보안 항목의 client secret을 서버에 입력.
- 동의 항목은 실제 서비스가 사용하는 항목만 확인. 콘솔 개편으로 메뉴명이 다르면 ‘플랫폼/Web’, ‘카카오 로그인/Redirect URI’ 설정을 찾는다.

[현재 Kakao 공식 REST API 설정](https://developers.kakao.com/docs/ko/kakaologin/rest-api)을 확인한다.

FRONTEND_ORIGIN은 Compose PUBLIC_ORIGIN에서 동일하게 전달된다. 실제 휴대전화에서 로그인 시작 → 인증 → 콜백 → 화면 → 새로고침 유지 → 로그아웃 확인. Cookie Secure/HttpOnly/SameSite=Lax와 리다이렉트 HTTPS를 개발자 도구에서 확인한다. 설치형 앱의 복귀는 별도 검증한다.

## 8. PWA·푸시 및 기능 검증

정재헌에게 sw.js 파일명/등록 scope, manifest, 아이콘, 시작 URL, 업데이트 정책, 개인정보/API 캐시 제외를 확인받는다. 서버는 파일이 존재할 때만 제공하며 장기 캐시는 콘텐츠 해시 JS/CSS만 적용한다. Nginx 캐시 정책이 서비스 워커 내부 캐시 정책을 대신하지 않는다.

Web Push/FCM 방식은 아직 확인되지 않았다. VAPID/FCM 키를 임의로 필수 설정에 넣지 않는다. PWA 설치 성공과 실제 푸시 성공은 분리한다. 프런트는 권한·구독·수신·탭 이동, 백엔드는 사용자/기기 구독·발송·취소, 배포는 HTTPS와 서버 통신을 맡는다.

실제 기기: 허용·거절, 화면 닫힘 수신, 일정 변경/삭제/완료 후 중복 방지, 로그아웃/계정 변경 후 수신자 분리. 아직 실시하지 않았다.

기능별 결과는 `RESULTS.md`에 화면/API, 정상 여부, 재현 방법, 담당/이슈, 재확인을 남긴다. 로그인·가족·방문·메모/태그·일정·복약/알림·문서·AI·복지·예방접종·성장을 각각 기록한다. 미병합 기능은 기능 미구현/미포함, 키 없음은 환경 문제, Nginx 차단은 배포 제한으로 구분한다.

## 9. 백업·재배포·복구

목적: DB와 파일을 같은 시점으로 백업하고 이미지 버전과 DB 호환성을 구분한다. 먼저 별도 저장소의 암호화/접근권한/보존기간을 결정한다. 동일 EC2의 backups만으로 장애 복구가 충분하지 않다.

[AWS EC2 Ubuntu, 관리자 셸]
```bash
cd /opt/dodam/infra
bash scripts/backup.sh .env.production
# 백업 중 앱 쓰기 정지; 완료 후 자동 재시작. 해시 확인 후 승인된 외부 저장소로 암호화 전송
```

재배포: 새 sources 커밋/infra 커밋/이미지 태그/ID/migration 목록/백업 위치 기록 → 로컬 빌드 및 export → scp → load → RELEASE_TAG 갱신 → deploy.sh → 검증. 이전 이미지는 검증 완료 전 삭제하지 않는다. `latest`만 사용하지 않는다. down -v는 사용하지 않는다.

이미지 롤백: DB가 이전 코드와 호환됨을 먼저 확인한 뒤 env RELEASE_TAG를 이전 값으로 바꾸고 deploy.sh. Flyway 적용 파일을 수정·제거하지 않는다. DB 복원은 운영 DB 위에서 실행하지 않고 **새 프로젝트/새 볼륨**으로 먼저 복원한다.

[AWS EC2 Ubuntu, 관리자 셸 — 별도 복구 환경]
```bash
cp .env.production .env.restore
chmod 600 .env.restore
# COMPOSE_PROJECT_NAME=dodam-restore, BIND_ADDRESS=127.0.0.1,
# HTTP_PORT=5280, HTTPS_PORT=5443로 수정. 운영과 다른 볼륨인지 확인
nano .env.restore
docker compose --env-file .env.restore -f compose.production.yml up -d postgres
docker compose --env-file .env.restore -f compose.production.yml exec -T postgres pg_isready -U dodam -d dodam
docker compose --env-file .env.restore -f compose.production.yml exec -T postgres pg_restore -U dodam -d dodam --no-owner --exit-on-error < backups/<백업시각>/database.dump
docker compose --env-file .env.restore -f compose.production.yml run --rm --no-deps --entrypoint tar ai -C /data/object-storage -xzf - < backups/<백업시각>/uploads.tar.gz
docker compose --env-file .env.restore -f compose.production.yml up -d --no-build --wait
```

복구 환경에서 사용자 접근 권한/문서·DB 일치/로그인/핵심 기능을 확인한 뒤 정식 전환을 결정한다. 복원용 DB의 최초 vector extension과 dump 충돌 시 깨끗한 복구 DB에서 extension 생성 상태를 확인하며 운영 DB를 수정하지 않는다.

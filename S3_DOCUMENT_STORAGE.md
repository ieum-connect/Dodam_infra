# 도담 문서 S3 저장소

프런트엔드는 기존 EC2 Nginx/React PWA로 제공한다. S3 전환 대상은 문서 원본과 AI가 생성한 렌더링 PNG다. Docker Hub와 EC2/Docker Compose 배포를 유지한다.

## 구성

- 버킷: `dodam-documents-515517431993-ap-southeast-2`, 시드니
- 공개 접근 차단 4개 모두 활성화, Bucket owner enforced, SSE-S3 암호화, 버전 관리
- HTTP 접근 거부. 도담 웹 origin에서 GET/HEAD만 CORS 허용
- EC2 역할: `dodam-ec2-document-storage`. 해당 버킷의 ListBucket/GetBucketLocation과 객체 Get/Put/Delete만 허용
- 장기 AWS 키를 환경 변수나 GitHub secret에 등록하지 않음
- Spring은 사용자별 접근 권한을 확인하고 원본을 전달하거나 5분짜리 S3 GET URL을 발급
- FastAPI는 같은 object key로 원본을 읽고 페이지 이미지를 저장

## 배포 순서

1. `scripts/provision-document-s3.py` 내용을 확인하고 인증된 CloudShell에서 실행한다. 최초 구성 전용이며 기존 EC2 역할을 덮어쓰지 않는다. IAM 전파 후 생성한 instance profile을 대상 EC2에 연결한다.
2. Docker bridge 컨테이너에서 IMDSv2를 사용할 수 있도록 metadata hop limit 2, HttpTokens required를 유지한다. 실제 도담 EC2는 이미 이 설정이다.
3. S3 지원 backend/AI 이미지의 정확한 SHA로 `Release images` Actions를 실행한다. 게시된 digest 및 revision label을 검증한다.
4. EC2에서 S3 역할, 암호화, 버전 관리, SDK 읽기/쓰기, 서명 URL, 익명 접근 거부를 검증한다. Java는 Spring Boot 3.3의 Apache HTTP 의존성 충돌을 피하도록 URLConnection HTTP 클라이언트를 명시한다.
5. S3 지원 AI 이미지를 사용해 uploads 볼륨을 `/source:ro`로 마운트하고 `scripts/migrate-document-s3.py --bucket <bucket>`를 실행한다. 모든 파일을 다시 읽어 SHA-256으로 확인한다. 원본은 지우지 않는다.
6. API를 잠시 점검 상태로 전환하고 backend/AI를 중지해 쓰기를 멈춘 뒤 최종 복사를 반복한다. DB dump와 기존 env/compose를 백업한다.
7. `DOCUMENT_STORAGE_PROVIDER=s3`, `DOCUMENT_S3_BUCKET=<bucket>`, `DOCUMENT_S3_REGION=ap-southeast-2`와 새 backend/AI image digest를 설정한다.
8. `compose.production.yml`로 backend/AI를 시작한다. 건강 상태와 실제 문서 접근을 확인한 뒤 API를 다시 연다.

## 롤백

API를 다시 열기 전 실패하면 기존 env/compose와 이미지로 복구한다. API를 다시 연 뒤에는 새 파일이 S3에만 있을 수 있으므로 local로 단순 변경하면 안 된다. 쓰기를 중지하고 현재 DB가 참조하는 S3 객체를 local로 역동기화·검증하거나 S3 설정을 유지한 수정 이미지를 배포한다. 삭제된 객체의 과거 버전을 무작정 복구하지 않는다. S3 버전 및 기존 uploads 볼륨은 별도 보존 정책을 결정할 때까지 유지한다.

## 검증 기록

2026-11-16 21:06 KST 운영 전환 완료. 20개 파일, 7,888,461바이트의 전체 S3 read-back 해시 일치. 최종 동기화 때 추가 변경 파일 없음. 실제 Java/Python 배포 이미지와 EC2 IAM 역할로 S3 저장·읽기·서명 URL, AES256 암호화, 버전 관리, 익명 접근 거부를 검증했다. HTTPS 데모 문서 원본 해시가 전환 전과 같으며 S3 서명 페이지 URL도 200을 확인했다. 데모 목록 2건 중 1건의 원본 조회 실패는 전환 전부터 존재하며 동일 상태다.

- 최초 이미지 게시 검증: https://github.com/ieum-connect/Dodam_infra/actions/runs/43860117611
- 최종 S3 이미지 게시: https://github.com/ieum-connect/Dodam_infra/actions/runs/43862824121
- 운영 backend SHA: `2c3c44407c6337596a45a4c5ebd1c72ebf80a966` (`release/s3-production`, 기존 운영 커밋에 CI/S3 변경만 적용)
- 운영 backend digest: `sha256:9ab9eda1254708fc7f061e5e2ea2e4697c248adf1644c817a0b8dc87ace3a418`
- 운영 AI SHA: `fef67f03dc12cad612cd8de2170424b229af4b60`
- 운영 AI digest: `sha256:316aeef7d511ddd45859743144e4c583d0c290657db466d21d853edc2ab7af84`
- backend/AI/web/postgres 모두 healthy. 프런트 이미지와 DB 컨테이너는 그대로 유지
- 백업: EC2 `/opt/dodam/backups/20261116-s3` (DB dump, env, compose, Nginx 설정). 원본 uploads 볼륨 유지
- 코드 검토: backend PR #54, AI PR #24. 각 PR의 자동 검증은 통과했고 팀원 승인 후 develop 병합 필요

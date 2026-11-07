# 도담 EC2 생성 설정 — 시드니

현재 구글 로그인으로 생성한 프로젝트는 시드니(`ap-southeast-2`)에 배정되어 있다. 서울로 URL을 바꾸지 않는다. 아래는 첫 배포 설정안이며 AWS 자원을 생성한 기록이 아니다.

## EC2 → 인스턴스 시작에서 입력

1. **이름:** `dodam-production`. 태그는 Project=`dodam`, Team=`ieum`, Environment=`production`.
2. **운영체제:** Canonical의 Ubuntu Server **24.04 LTS**, **64비트 x86**. ARM이나 별도 유료 소프트웨어 AMI를 선택하지 않는다. AMI ID는 시드니 콘솔에서 확인하며 임의로 고정하지 않는다.
3. **인스턴스 유형:** **t3.medium (2 vCPU / 4GiB)**, 1대, 온디맨드. 초기 검증용 시작안이며 부하 검증 완료 사양은 아니다. 선택 불가·업그레이드 요구가 나오면 다른 사양이나 플랜을 바로 선택하지 말고 제한 내용을 확인한다.
4. **키 페어:** 새 RSA 키, 이름 `dodam-sydney`, `.pem` 형식. 개인 PC에 안전하게 보관하고 Git·채팅에 올리지 않는다. 이미 승인된 도담 키가 있다면 재사용 가능하다.
5. **네트워크:** 현재 프로젝트가 제공하는 VPC를 확인한다. 인터넷 게이트웨이로 나가는 공용 서브넷을 사용하고 공인 IPv4 자동 할당을 활성화한다. 기본 VPC가 없거나 설정이 잠겨 있으면 임의로 NAT Gateway를 추가하지 말고 프로젝트 네트워크를 확인한다.
6. **보안 그룹:** 이름 `dodam-web-sg`. SSH TCP 22는 **내 IP**만, HTTP TCP 80·HTTPS TCP 443은 `0.0.0.0/0`. 8081·8006·5432는 추가하지 않는다. 최초 HTTP는 인증서 검증용이며 앱 화면은 HTTPS 준비 전 503으로 막는다.
7. **스토리지:** gp3 **30GiB**, 암호화 활성화. 기본 IOPS·처리량을 유지한다. 앱 빌드는 PC에서 하고 서버에는 실행 이미지만 전달한다. 이미지·백업 누적으로 여유 공간이 줄면 정리·증설을 판단한다. 인스턴스 종료 시 삭제 옵션은 최종 정리·백업 계획과 함께 확인한다.
8. **고급 세부 정보:** 메타데이터 접근 활성화, **IMDSv2 필수**. T3 CPU 크레딧은 가능하면 **Standard**로 시작한다. 크레딧 소진 시 성능이 제한되므로 부하 검증 때 확인한다. Unlimited는 초과 CPU 비용을 검토한 뒤 선택한다.
9. **IAM 인스턴스 프로파일:** 초기 SSH 배포에는 추가 AWS 권한이 필요 없다. 프로젝트가 제공하는 프로파일이 있다면 임의 교체하지 않는다. SSM·ECR 연결 시 실제 정책을 확인하고 필요한 권한을 추가한다.
10. **사용자 데이터:** 비워 둔다. 키·DB 비밀번호·AI 키를 입력하지 않는다. 상세 모니터링은 초기에는 켜지 않고 기본 지표부터 확인한다.

생성 전에 요약에서 **시드니 / Ubuntu x86 / 1대 / t3.medium / gp3 30GiB / SSH 내 IP**를 확인한다. 콘솔의 시간당 비용과 크레딧 적용 조건을 확인한 뒤 생성한다. 크레딧 100달러가 이 사양의 장기 무료 운영을 보장하지 않는다.

## 이 사양을 시작안으로 잡은 근거

2026-11-07 로컬 배포 컨테이너의 대기 상태 측정: web 21.02MiB, AI 107.1MiB, backend 543.3MiB, DB 59.27MiB, 합계 약 731MiB. 호스트 OS·파일 캐시·문서 렌더링 최고 부하는 포함되지 않았다. 4GiB로 시작한 뒤 실제 동시 사용자·문서 처리 부하에서 OOM, 메모리·CPU 크레딧을 점검하고 필요하면 조정한다. 이번 측정에서 유료 AI 요청은 없었다.

비용은 EC2 시간당 단가 × 실행 시간에 EBS·공인 IPv4·전송·백업 등을 더한다. 테스트하지 않는 기간 서버를 중지하더라도 디스크 등 비용이 남을 수 있다. 중지 후 재시작하면 자동 공인 IPv4가 바뀔 수 있으므로 도메인을 고정하기 전 고정 주소 필요성과 비용을 검토한다.

## 생성 직후 할 일

상태 검사가 통과한 뒤 **인스턴스 ID·공인 IPv4·선택한 사양**을 확인한다. 개인키 파일 내용은 공유하지 않는다. 로그인 사용자는 `ubuntu`다.

```powershell
# 로컬 PowerShell — 실제 키 경로와 서버 주소로 바꾼다.
ssh -i '<개인키 경로>' ubuntu@<공인 IPv4>
scp -i '<개인키 경로>' C:/dodam/infra/scripts/check-ec2.sh ubuntu@<공인 IPv4>:/home/ubuntu/
```

첫 SSH 호스트 키는 신뢰할 수 있는 콘솔 정보와 대조한다. 서버에서 `bash ~/check-ec2.sh`로 리전·OS·아키텍처를 확인한 뒤 README 4절의 Docker 설치를 진행한다. 이 스크립트는 EC2 메타데이터와 로컬 상태만 읽으며 자원을 생성하지 않는다.

## 도메인 결정 후 환경 파일 생성

도메인은 아직 미정이다. 서버 생성은 가능하지만 현재 배포 설정으로 운영 앱을 공개하려면 도메인과 HTTPS가 필요하다. 도메인 결정 전 테스트용 HTTP 화면을 인터넷에 공개하지 않는다.

배포 묶음을 서버의 `/opt/dodam/infra`에 풀고 관리자 셸에서 실행한다.

```bash
cd /opt/dodam/infra
python3 scripts/init-production.py --domain <실제 도메인> --tag <검증한 이미지 태그>
nano .env.production
```

생성기는 시드니·공개 바인딩·HTTPS 준비 모드와 서로 다른 난수 DB/JWT/내부 토큰을 설정한다. 기존 파일이 있으면 중단하며 값을 출력하지 않는다. 실제 카카오·AI 키는 담당자에게 받아 서버에서 입력한다. 현재 AI는 빈 임베딩 키로 기동되지 않으므로 키와 모델 확인 없이 실행 완료를 기대하지 않는다. 환경 파일은 Git에 포함되지 않는다.

이후 [배포 가이드 6~9절](DEPLOYMENT_GUIDE.md)을 따른다. 기존 문서 원본 권한·실제 로그인·앱 전환의 미해결 사항은 그대로 점검 대상이다.

## 인프라 저장소의 준비 범위

Dockerfile·Compose·Nginx·배포/백업 스크립트는 기존 준비물을 사용한다. 이번 변경은 시드니 설정 예시, 서버 사전 점검, 운영 환경 생성, 상세 가이드다. ECR·GitHub Actions·SSM 자동 배포는 아직 없으며 이 파일을 만든 것으로 자동 배포 완료 처리하지 않는다. 실제 서버 정보와 도메인을 확인한 뒤 연결한다.

공식 근거: [프로젝트 리전](https://docs.aws.amazon.com/accounts/latest/reference/project-regions.html), [EC2 생성 항목](https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/ec2-instance-launch-parameters.html), [T3 사양](https://aws.amazon.com/ec2/instance-types/t3/), [Standard CPU 크레딧](https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/burstable-performance-instances-standard-mode.html).

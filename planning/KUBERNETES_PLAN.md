# 도담 Kubernetes 구성안과 100달러 운영 예산

> **보류된 비교 자료 — 2026-11-08:** 사용자가 11월 16일 시연 배포를 EC2 1대 + Docker Compose로 확정했다. 아래 추천·비용·구축 순서는 비교 당시의 안이며 현재 실행 계획이 아니다. 실제 실행은 상위 폴더의 README.md와 EC2_SYDNEY.md를 따른다.

작성: 2026-11-07 · 팀 이음 · 시드니 ap-southeast-2 · **설계 및 견적, 미구축**

## 판단

100달러로 Kubernetes를 직접 구축하고 장애 실험을 할 수 있다. 다만 장기 무료 운영 예산은 아니다. 추천안은 K3s 서버 노드 3대와 별도 데이터 서버 1대다. K3s는 Kubernetes 배포판이며 컨테이너 실행에는 containerd를 사용한다. 기존 Dockerfile로 만든 OCI 이미지를 ECR에서 받아 실행한다.

K3s안은 24시간 운영 시 예상 월 208.13달러, 하루 6.84달러다. 잔액 100달러를 전부 사용할 경우 약 14.6일, 20달러를 남기면 약 11.7일이다. 7일은 약 47.90달러, 10일은 약 68.43달러, 14일은 약 95.80달러다. 아래 가정에 따른 추정이며 실제 잔액·적용 가능 크레딧·부하·세금은 별도 확인한다.

계정의 EC2 vCPU 한도, t3.medium/t3.small 선택 가능 여부, VPC/서브넷/보안 그룹/IAM 권한을 먼저 확인한다. 이 구성은 총 8 vCPU이며 신규 계정 한도에 걸릴 수 있다. 제한이 있으면 생성 전에 해결 여부를 확인한다. 크레딧이 있어도 자원 한도가 자동 확대되지는 않는다.

## 권장 구성: 관리 노드도 한 대 장애를 견디는 K3s

- K3s server 3대: 각각 t3.medium, 2 vCPU / 4GiB, gp3 30GiB. 서로 다른 3개 AZ에 배치. 세 노드 모두 관리 기능과 앱 실행 역할을 수행한다. 내장 etcd 3개로 한 노드 장애 시 과반수를 유지한다.
- 데이터 서버 1대: t3.small, 2 vCPU / 2GiB. 루트 gp3 20GiB + 데이터 gp3 30GiB. PostgreSQL + pgvector, 초기 NFSv4 문서 공유 경로. 부하에 따라 메모리 증설 가능성을 남긴다.
- ALB 1개: 3개 AZ, HTTPS 진입점과 노드 상태 검사. 공개 IPv4 최소 3개를 계산한다. 인증서는 ACM에서 검증하고 도메인 비용은 따로 확인한다.
- 프론트/Nginx, 백엔드, AI: Deployment와 ClusterIP Service로 분리. 프론트·백·AI 각각 2개 복제본을 목표로 하되 로그인·공유 저장소·중복 작업 검증을 통과한 뒤 확장한다. 반친화성/분산 배치 규칙으로 서로 다른 노드에 배치한다.
- ALB → 고정 NodePort(예: 30080)의 Nginx → backend Service → ai Service 흐름. ALB가 TLS를 종료하므로 기존 Nginx HTTPS/리다이렉트 설정을 그대로 복사하지 않고 전달 프로토콜·쿠키·OAuth redirect를 다시 구성한다. 노드에 Certbot을 각각 설치하지 않는다.
- 컨트롤 API의 접근 주소는 고정된 관리 경로와 대체 노드 주소를 기록한다. 첫 설치·노드 추가는 살아 있는 server를 통해 수행한다. 앱용 ALB를 Kubernetes API 로드밸런서로 사용하지 않는다. API 진입점까지 자동 HA가 필요하면 별도 TCP LB 비용을 추가한다.
- 로그·상태·백업: 우선 kubectl, 노드 기본 지표, 보관기간 제한 로그, etcd 스냅샷, DB+문서 일관 백업. Prometheus/Grafana를 넣으면 메모리·디스크를 재측정한다. 외부 장애 알림은 별도 연결 작업이다.

```text
사용자 → 도메인 / ALB HTTPS (3 AZ)
                    ↓ 정상 노드에 전달
     ┌──────────────┼──────────────┐
  K3s A          K3s B          K3s C
  관리+앱         관리+앱         관리+앱
     └── frontend/backend/AI 복제본 분산 ──┘
                    ↓ 사설 IP
         데이터 EC2: PostgreSQL + NFS
                    ↓
          암호화된 별도 백업 저장소
```

**장애 대응 범위:** 앱/관리 노드 1대 장애 시 관리 쿼럼 유지 및 정상 복제본으로 접근하는 것을 검증한다. 데이터 서버는 단일 장애 지점이다. DB·문서 서버가 꺼지면 핵심 기능은 멈추며 백업 복구가 필요하다. 따라서 “서비스 전체 고가용성”이나 “무중단 보장”이라고 발표하지 않는다. AZ 장애도 데이터 서버가 있는 AZ라면 서비스 전체를 지킬 수 없다. 처리 중인 요청의 성공이나 OAuth 흐름 유지 역시 별도 테스트 대상이다.

## 네트워크·데이터 설계

크레딧 예산 때문에 첫 실습안은 NAT Gateway 없이 EC2마다 공인 IPv4를 부여해 이미지 다운로드와 외부 API 통신에 사용한다. 이것이 모든 인바운드를 공개한다는 뜻은 아니다. EC2 4개 + ALB 3개 = 공인 IPv4 최소 7개를 비용에 넣었다. 사설 노드 + NAT로 바꾸면 별도 시간당·트래픽 비용이 든다.

- ALB: 80/443 공개. NodePort는 ALB 보안 그룹에서 오는 것만 허용한다.
- 노드: SSH는 관리자 IP만. Kubernetes API 6443은 관리자와 클러스터 내부만. etcd 2379/2380, kubelet 10250, 선택한 CNI의 내부 통신은 노드 보안 그룹 사이에만 허용한다. VXLAN 등 CNI 포트를 인터넷에 열지 않는다.
- 데이터: PostgreSQL 5432, NFSv4 2049는 앱 노드 보안 그룹만 허용한다. NFS export, UID/GID 10001, 권한·백업·전송 보호를 검증한다. 실제 개인정보 투입 전 EFS TLS 마운트 또는 S3 어댑터 전환을 별도로 검토한다. 초기 장애 실습은 합성 데이터로 한다.
- NFS는 현재 로컬 경로 방식과 호환되도록 모든 backend/AI Pod의 `/data/object-storage`에 동일한 RWX 경로로 마운트한다. 각 노드 hostPath를 따로 만들어서는 서로의 문서를 읽을 수 없다.
- DB·업로드·etcd 백업을 구분한다. etcd 백업은 아이의 건강 기록 DB나 문서 백업을 대신하지 않는다.
- 데이터까지 자동 장애 전환하려면 RDS Multi-AZ의 pgvector 지원 버전 확인, EFS Regional/S3 연동 등이 추가로 필요하다. 이는 이번 예산에 넣지 않았으며 별도 견적이 필요하다.

## 다른 선택지와 공정한 비교

1. **단일 EC2 Compose:** t3.medium 1대, gp3 30GiB, IPv4 1개, ALB 없음. 월 55.07달러, 100달러 약 55.2일. 서버 장애 자동 대체 없음.
2. **kubeadm 기본형:** 관리 1대(t3.medium) + 작업 2대(t3.medium) + 데이터 1대(t3.small), 총 gp3 140GiB, ALB 2 AZ, IPv4 6개. 월 204.48달러, 약 14.9일. Sporty와 비슷한 역할 분리, 관리 노드와 데이터 서버는 단일 장애 지점.
3. **K3s 관리 HA형(권장):** 관리+작업 3대(t3.medium) + 데이터 1대(t3.small), 총 gp3 140GiB, ALB 3 AZ, IPv4 7개. 월 208.13달러, 약 14.6일. 관리 노드 한 대 장애까지 대응하지만 데이터 서버는 단일 구성.
4. **Sporty 사양 재현 + ALB:** 관리 t3.medium + 작업 t3.large 2대 + 데이터 t3.large 1대, gp3 140GiB, ALB 2 AZ, IPv4 6개. 월 339.38달러, 약 9.0일. 실제 Sporty는 NodePort 진입이었으며 이 견적은 자동 진입점 전환 비교를 위해 ALB를 추가했다. 실제 과거 청구액이 아니다.
5. **EKS 표준 지원:** 관리형 control plane 1개 + 작업 t3.medium 2대 + 데이터 t3.small 1대, gp3 110GiB, ALB 2 AZ, IPv4 5개. 월 232.41달러, 약 13.1일. 표준 control plane 관리료 0.10달러/시간 포함. Auto Mode·확장 지원·추가 NAT는 사용하지 않는 가정이다.

EKS는 운영 관리 부담을 줄이는 장점이 있지만, 작은 구성에서 관리료 약 73달러/730시간이 예산의 큰 부분이다. EC2에 직접 설치하는 kubeadm/K3s에는 EKS 관리료가 없다. K3s를 추천하는 이유는 같은 앱 서버 수로 관리 쿼럼까지 구성할 수 있기 때문이며, 팀이 kubeadm 학습 연속성을 더 중요하게 보면 기본형을 선택할 수 있다.

## 계산 근거와 제외 항목

Linux / Shared / On-Demand / 시드니 / 730시간을 월 환산 기준으로 사용한다. AWS 공개 Price List CSV에서 확인한 값은 함께 저장한 JSON에 원본 SKU와 단위까지 남겼다.

- t3.small: 0.0264 USD/시간, t3.medium: 0.0528, t3.large: 0.1056.
- gp3: 0.096 USD/GB-월. 기본 IOPS·처리량만 사용.
- 공인 IPv4: 0.005 USD/주소·시간. ALB 주소와 EC2 주소를 모두 포함.
- ALB: 0.0252 USD/시간 + 평균 **1 LCU** 가정 × 0.008 USD/LCU·시간. 트래픽 증가·스케일아웃 시 비용 증가 가능.
- EKS 표준 지원: 0.10 USD/클러스터·시간.
- 모든 안에 ECR/S3 백업·소량 로그·AZ 간 트래픽 등 **월 10달러 계획 여유분**을 추가. AWS의 확정 패키지 요금이 아니며 실제 사용량 기반 별도 산출을 대체하지 않는다.
- 별도 제외: 도메인 구매, 세금, OpenAI 등 외부 API, GPU, RDS/EFS, NAT Gateway, 유료 관측 서비스, T3 Unlimited 초과 CPU, 대규모 전송/이미지/백업. 10달러 여유분을 넘는 사용량은 수명 단축 요인이다.

월 예상액 = 서버 시간당 합 × 730 + 디스크 + IPv4 + ALB + EKS + 여유분.
일 예상액 = 월 예상액 ÷ 730 × 24. 운영 일수 = 사용 가능 크레딧 ÷ 일 예상액.
실제 gp3 월별 시간은 달력과 청구 기준에 따라 달라질 수 있으므로 이는 예산 환산이다. 기존 잔액·추가 획득 크레딧·무료 사용량 공제·세금 충당은 임의 적용하지 않았다.

하루 8시간만 모든 EC2를 실행하고 나머지는 중지할 경우 K3s안은 약 25.7일까지 늘어나는 계산이다. 이때 EBS, 보유 IPv4, ALB, 여유분은 24시간 유지하는 보수적 가정이다. 서비스는 하루 16시간 꺼지며, 클러스터 정상 종료·재시작·주소 유지 자동화는 아직 없다. EKS도 노드만 중지하면 관리료가 계속 든다. 비교 화면에서 예산·시간·LCU·여유분을 바꿔 볼 수 있다.

## 코드에서 먼저 확인해야 할 사항

배포 검증 스냅샷 frontend 3b502c4 / backend ee16762 / AI 6da9b00 및 로컬 reminders 작업 사본을 읽었다. 최신 PR 전체를 이번 견적으로 재리뷰한 것은 아니다. 구현 시 최신 병합 버전을 다시 확인한다.

- backend의 `SecurityConfig`에 oauth2Login, 계정 전환/로그인 컨트롤러에 HttpSession 저장 코드가 있다. JWT가 있다고 전체 인증이 무상태라고 단정할 수 없다. 복제본 2개에 번갈아 요청해 로그인·콜백·계정 전환을 시험한다. 필요하면 Spring Session JDBC 등 공유 세션을 구현한다. sticky session만으로 장애 시 세션 보존을 주장하지 않는다.
- backend `LocalDocumentStorage`와 AI `LocalDocumentStorage`가 로컬 디렉터리를 사용한다. 공용 마운트 또는 스토리지 어댑터가 선행되어야 한다. 운영 원본 권한 경로의 기존 문제도 해결해야 한다.
- reminders 작업 사본에는 15초 스케줄러와 DB 행 잠금·전달 마커가 있다. 중복 방지 장치는 보이지만 다중 프로세스에서 복약 반복·알림이 정확히 한 번 처리되는지는 테스트해야 한다. 코드 확인을 검증 완료로 바꾸지 않는다.
- 각 서비스의 startup/readiness/liveness와 종료 유예를 정한다. DB·외부 AI 실패가 모든 Pod 재시작 폭주로 이어지지 않도록 한다. 실제 유료 호출 없는 health endpoint를 사용한다.
- DB 마이그레이션은 별도 배포 단계/Job으로 한 번 실행하는 방향을 검토한다. 현재 앱 자동 Flyway와 중복 실행하지 않도록 설정 변경이 필요하다. 이전 버전과 DB 호환성을 확인하고 롤백한다.

## 구축 순서와 통과 조건

1. 100달러 중 20달러 보존, 실습 7~10일을 우선 운영 계획으로 잡는다. AWS 실제 잔액·서비스 사용 조건·총 vCPU 8개 한도·세 AZ 접근을 확인한다.
2. 로컬에서 manifests와 합성 데이터로 공용 저장소·로그인·다중 실행 테스트를 먼저 한다. 유료 AI 호출은 하지 않는다.
3. 네트워크와 노드를 코드로 관리하고 버전을 고정해 K3s 설치, etcd 세 노드와 스냅샷을 확인한다. kubeconfig·토큰·SSH 키는 Git에서 제외한다.
4. 데이터 서버와 제한된 NFS 마운트·DB를 준비한다. ALB와 HTTPS, readiness, Pod 분산 배치, resource requests/limits를 검증한다.
5. ECR에 각 앱 SHA/digest를 게시하고 GitHub Actions에서 승인한 버전 묶음을 배포한다. apply → rollout → 기능 검사 → 결과 기록. DB를 무조건 되돌리는 자동 롤백은 넣지 않는다.
6. Pod 강제 종료 → 노드 drain → 노드 실제 중지 → 새 이미지 실패 → 백업 복원 순서로 실험한다. 중단 시간·5xx·데이터 손실·로그인 유지·알림 중복을 측정한다. drain 성공을 갑작스러운 노드 장애 성공으로 대신하지 않는다.
7. 앱/관리 노드 장애 복구는 테스트 목표다. 데이터 노드 장애는 자동 복구 대상이 아니므로 별도 복원 실험과 복구 시간을 기록한다. ALB 장애 대상 제외까지 걸리는 시간도 측정한다.

이번 작업은 구성안과 비용 계산만 작성했다. 기존 단일 EC2 PR을 Kubernetes 구현 완료로 변경하거나 AWS 자원을 생성하지 않았다. 구성 결정 후 별도 인프라 이슈/PR에서 manifests·설치·자동화를 구현한다.

## 공식 출처

- [EC2/EBS 시드니 공개 단가 CSV](https://pricing.us-east-1.amazonaws.com/offers/v1.0/aws/AmazonEC2/current/ap-southeast-2/index.csv)
- [ELB 시드니 공개 단가 CSV](https://pricing.us-east-1.amazonaws.com/offers/v1.0/aws/AWSELB/current/ap-southeast-2/index.csv)
- [공인 IPv4 요금](https://aws.amazon.com/vpc/pricing/)
- [EKS 요금](https://aws.amazon.com/eks/pricing/)
- [K3s embedded etcd 고가용성](https://docs.k3s.io/datastore/ha-embedded)
- [현재 가입 방식 지원 서비스](https://docs.aws.amazon.com/accounts/latest/reference/supported-services-sign-up-new.html)

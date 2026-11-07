# 배포 방식 검토 기록

2026-11-08 사용자가 **단일 EC2 + Docker Compose**를 선택했다. 이 폴더는 당시 Kubernetes 대안과 AWS 공개 단가를 보존하는 참고 자료다. 여기 적힌 4대 생성·K3s 추천은 현재 배포 지시가 아니다.

실행 문서: [Compose 배포 안내](../README.md), [EC2 생성 설정](../EC2_SYDNEY.md).

공개 요금 CSV에서 필요한 행만 추출한 JSON과 오프라인 비용 계산기를 보관한다. 실제 AWS 사용료 청구 내역이나 현재 크레딧 잔액이 아니다. `build-cost-comparison.py`는 로컬 계산·HTML 생성만 수행하고 AWS 자원을 만들지 않는다.

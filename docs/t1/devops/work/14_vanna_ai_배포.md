# 14. Vanna AI + ChromaDB 배포 (AI Layer)

> **목표**: 자연어 질의(Text-to-SQL) 처리를 위한 Vanna AI 및 Vector DB 구축 방법론 정의  
> **참조**: [devops_implementation_guide.md](../devops_implementation_guide.md#14-ai-layer-vanna-ai)

## 1. 아키텍처 및 배포 전략

### 구성 요소
- **ChromaDB**: Helm Chart를 이용한 Vector DB 구축. 데이터 영속성을 위해 EBS(gp2) 5Gi 볼륨을 바인딩함.
- **Vanna API**: FastAPI 기반의 커스텀 파이썬 애플리케이션. 
  - **버전 전략**: 최신 2.0 버전의 아키텍처 변경 이슈를 피하기 위해 안정적인 `0.7.9` 버전을 사용함.
  - **이미지**: ECR(`capa-vanna-api`)에 업로드된 커스텀 이미지 사용.
- **연동 방식**: Vanna 파드의 환경 변수를 통해 ChromaDB 서비스 주소(`chromadb.chromadb.svc.cluster.local`) 정보를 주입함.

### 관리 자동화
- **인프라**: Terraform을 통해 Namespace, ECR, IAM Role, K8s 배포를 일괄 관리.
- **보안**: Anthropic API Key는 K8s Secret으로 격리 관리하며, IRSA를 통해 AWS 리소스 접근 권한을 획득함.

## 2. 세부 배포 단계

### 단계 1: 환경 준비 (Local)
- `services/vanna-api/` 내에 Dockerfile 및 소스 코드(`main.py`) 준비.
- `requirements.txt`에 `vanna[chromadb]==0.7.9` 명시.

### 단계 2: 이미지 빌드 및 ECR 업로드
- Docker Desktop을 사용하여 이미지 빌드 후 AWS ECR로 `push`.
- 빌드 시 `build-essential` 등 컴파일 라이브러리가 포함된 베이스 이미지(`python:3.11`) 사용 권장.

### 단계 3: Terraform 인프라 정의
- `10-applications.tf`: ChromaDB용 Namespace 및 Helm Release(`amikos-tech/chromadb`) 정의.
- `11-k8s-apps.tf`: Vanna API용 Namespace, Secret, Deployment, Service 정의.
- `04-iam-roles.tf`: Athena 및 S3 조회를 위한 IAM Role 및 IRSA 설정.

### 단계 4: 자원 배포
- `terraform apply`를 실행하여 네임스페이스 생성 및 Helm 차트, 쿠버네티스 리소스 순차 배포.

## 3. 검증 방법론 (How-to Verify)

배포 후 정상 작동 여부는 다음 절차를 통해 확인한다.
1.  **리소스 상태**: `kubectl get pods -n chromadb,vanna` 명령으로 파드 실행 상태 점검.
2.  **스토리지 바인딩**: `kubectl get pvc -n chromadb`로 EBS 볼륨 할당 확인.
3.  **API 응답**: `/health` 엔드포인트 호출을 통해 서비스 준비 상태 확인.

---

- **기록 (결과 보고)**: [14_complete.md](../progress/14_complete.md)
- **이전 단계**: [13_report_generator_배포.md](./13_report_generator_배포.md)
- **다음 단계**: [15_slack_bot_echo.md](./15_slack_bot_echo.md)

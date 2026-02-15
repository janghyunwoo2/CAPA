# 14. Vanna AI + ChromaDB 배포 (AI Layer)

> **목표**: 자연어 질의(Text-to-SQL) 처리를 위한 Vanna AI 및 Vector DB 구축  
> **참조**: [devops_implementation_guide.md](../devops_implementation_guide.md#14-ai-layer-vanna-ai)  
> **소요 시간**: 약 20분

## 1. 배포 전략

### 아키텍처
- **ChromaDB**: Helm Release (Vector DB, EBS 5Gi)
- **Vanna API**: 커스텀 Dockerfile (Report Generator와 동일 방식)
  - 이미지: `capa-vanna-api:latest` (ECR)
  - Terraform Deployment 정의 (Service, IRSA)
- **모든 환경 변수/시크릿**: Terraform 관리

### 개발자 워크플로우
1. `services/vanna-api/` 소스 수정
2. `docker build → ECR push` (또는 GitHub Actions 자동)
3. `kubectl set image` 또는 Terraform 재배포로 업데이트

## 2. 배포 단계

### 단계 1: 개발 구조 준비
- `services/vanna-api/Dockerfile` 작성 (Python 기반 + Vanna 라이브러리)
- `services/vanna-api/src/main.py` (FastAPI 앱)
- `services/vanna-api/requirements.txt`

### 단계 2: ECR Repository + IAM Role 확인
- `capa-vanna-api` ECR 이미 생성되어 있는지 확인
- `capa-vanna-role` IAM Role 확인 (Athena, S3 권한)

### 단계 3: Terraform 수정 (10-applications.tf)
- Namespace: `chromadb`, `vanna`
- Helm Release: `chromadb` (depends_on: EBS CSI Driver)
- Kubernetes Deployment: `vanna-api` (커스텀 이미지)
- Kubernetes Service: `vanna-api` (LoadBalancer)
- ServiceAccount: `vanna-sa` (IRSA 연결)

### 단계 4: Docker 이미지 빌드 & 푸시
`cd services/vanna-api && docker build -t capa-vanna-api:latest . && docker push ...`

### 단계 5: Terraform 배포
`terraform apply` → 모든 K8s 리소스 배포

### 단계 6: 검증
- Pod 상태: `kubectl get pods -n chromadb,vanna`
- PVC 바인딩: `kubectl get pvc -n chromadb`
- Vanna Health: `kubectl port-forward -n vanna svc/vanna-api 8000:8000 && curl localhost:8000/health`

## 3. 리소스 현황

- EKS: CPU 33~50% 사용, 메모리 33~47% 사용 (충분)
- 추가: ChromaDB 512Mi + Vanna 512Mi
- 포트: 8000 (네임스페이스 격리)

---

- **이전 단계**: [13_report_generator_배포.md](./13_report_generator_배포.md)
- **다음 단계**: [15_slack_bot_echo.md](./15_slack_bot_echo.md)

# 13. Report Generator 배포 (Analytics)

> **목표**: 정기 리포트 생성을 위한 Report Generator 서비스 배포
> **참조**: [devops_implementation_guide.md](../devops_implementation_guide.md#32-리소스-목록-확장)
> **소요 시간**: 약 15분

## 1. 사전 준비

- [ ] **소스 코드 준비**: `services/report-generator` (개발팀 제공)
- [ ] **ECR Repository 생성**: `capa-report-generator` (Terraform `06-eks.tf`에 포함 여부 확인)
- [ ] **IAM Role 확인**: Athena 쿼리 및 S3 저장 권한 필요

## 2. 작업 절차

### 2.1 컨테이너 이미지 빌드 (Hello World)

초기에는 실제 로직 없이 Health Check만 가능한 간단한 서버로 배포합니다.

**Dockerfile (`services/report-generator/Dockerfile`)**:
```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY src/ .
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
```

**main.py**:
```python
from fastapi import FastAPI
app = FastAPI()

@app.get("/health")
def health_check():
    return {"status": "ok", "service": "report-generator"}
```

**빌드 및 푸시**:
```bash
aws ecr get-login-password --region ap-northeast-2 | docker login --username AWS --password-stdin <ACCOUNT_ID>.dkr.ecr.ap-northeast-2.amazonaws.com
docker build -t capa-report-generator:latest ./services/report-generator
docker tag capa-report-generator:latest <ACCOUNT_ID>.dkr.ecr.ap-northeast-2.amazonaws.com/capa-report-generator:latest
docker push <ACCOUNT_ID>.dkr.ecr.ap-northeast-2.amazonaws.com/capa-report-generator:latest
```

### 2.2 Helm 배포

**Terraform 파일**: `infrastructure/terraform/environments/dev/apps/helm-report-generator.tf` (신규 작성 필요)

```hcl
resource "helm_release" "report_generator" {
  name             = "report-generator"
  chart            = "../../charts/generic-service"
  namespace        = "report"
  create_namespace = true

  set {
    name  = "image.repository"
    value = "<ACCOUNT_ID>.dkr.ecr.ap-northeast-2.amazonaws.com/capa-report-generator"
  }
  set {
    name  = "image.tag"
    value = "latest"
  }
}
```

## 3. 검증

### 3.1 Pod 상태 확인

```bash
kubectl get pods -n report
```

### 3.2 Health Check

```bash
kubectl port-forward -n report svc/report-generator 8000:8000
curl http://localhost:8000/health
```
- `{"status": "ok"}` 응답 확인

## 4. 문제 해결

- **ImagePullBackOff**: ECR 리포지토리 주소 오타 또는 권한 문제 (Node Role 확인)
- **CrashLoopBackOff**: Dockerfile `CMD` 오류 또는 의존성 설치 실패

---

- **이전 단계**: [12_redash_배포.md](./12_redash_배포.md)
- **다음 단계**: [14_vanna_ai_배포.md](./14_vanna_ai_배포.md)

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

### 2.2 Terraform으로 리소스 생성

모든 구성 요소는 `10-applications.tf` 안에 있습니다. 이미지가 ECR에 올라간 후, Terraform apply를 통해 동일한 네임스페이스, 서비스 어카운트, IAM 역할, 배포를 생성합니다.

```powershell
# 작업 디렉토리를 dev/base로 이동
cd infrastructure\terraform\environments\dev\base

# 변경 사항만 적용 (선택)
terraform plan -out=tfplan
# 리소스를 모두 배포
terraform apply tfplan
```

필요한 리소스는 다음과 같습니다:

* `aws_ecr_repository.report_generator` – ECR 저장소
* `aws_iam_role.report_generator` – IRSA용 역할
* `kubernetes_namespace.report` – 네임스페이스
* `kubernetes_service_account.report_sa` – 서비스 어카운트
* `kubernetes_deployment.report_generator` – 파드
* `kubernetes_service.report_generator` – 클러스터IP 서비스

환경 변수는 Terraform에서 하드코딩/참조되므로 별도 values 파일은 없습니다.

terraform 구성에서 이미지 경로는 아래와 같이 정의되어 있습니다:

```hcl
image             = "${aws_ecr_repository.report_generator.repository_url}:latest"
```

```powershell
# 변경이 있다면 다시 plan -> apply
terraform plan
terraform apply
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

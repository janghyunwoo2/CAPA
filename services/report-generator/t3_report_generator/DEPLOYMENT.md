# Report Generator 배포 가이드

> **목표**: FastAPI 기반 Report Generator 서비스를 EKS에 배포  
> **배포 방식**: ECR 이미지 푸시 + Terraform 리소스 생성  
> **소요 시간**: 약 20분

---

## 📋 사전 준비

### 필수 도구
- AWS CLI 설정 완료 (크레덴셜 구성됨)
- Docker 설치 및 실행 중
- kubectl 설정 완료 (EKS 클러스터 접근 가능)
- Terraform v1.14.3+ 설치 완료

### 환경 변수 설정
```powershell
# AWS 계정 정보
$ACCOUNT_ID = "827913617635"
$REGION = "ap-northeast-2"
$ECR_REPO = "capa-report-generator"
$ECR_URI = "$ACCOUNT_ID.dkr.ecr.$REGION.amazonaws.com/$ECR_REPO"
```

---

## 🚀 Step 1: ECR 로그인

```powershell
aws ecr get-login-password --region $REGION | docker login --username AWS --password-stdin "$ACCOUNT_ID.dkr.ecr.$REGION.amazonaws.com"
```

**예상 출력**:
```
Login Succeeded
```

---

## 🐳 Step 2: Docker 이미지 빌드

```powershell
cd c:\Users\3571\Desktop\projects\CAPA\services\report-generator

docker build -t capa-report-generator:latest .
```

**예상 출력**:
```
Sending build context to Docker daemon  ...
Step 1/7 : FROM python:3.11-slim
...
Successfully built <IMAGE_ID>
Successfully tagged capa-report-generator:latest
```

---

## 🏷️ Step 3: ECR 태그 지정

```powershell
docker tag capa-report-generator:latest "$ECR_URI:latest"
```

**확인**:
```powershell
docker images | grep capa-report-generator
```

---

## 📤 Step 4: ECR에 푸시

```powershell
docker push "$ECR_URI:latest"
```

**예상 출력**:
```
The push refers to repository [827913617635.dkr.ecr.ap-northeast-2.amazonaws.com/capa-report-generator]
...
latest: digest: sha256:abc123... size: 2345
```

---

## 🏗️ Step 5.5: Terraform 적용

### 5.5.1 Terraform Plan
```powershell
cd c:\Users\3571\Desktop\projects\CAPA\infrastructure\terraform\environments\dev

# Plan 생성
terraform plan -out=tfplan
```

**확인 내용** (출력에서 확인):
```
+ aws_ecr_repository.report_generator              (ECR 저장소)
+ aws_iam_role.report_generator                    (IAM Role for IRSA)
+ aws_iam_role_policy.report_generator             (IAM 정책)
+ kubernetes_namespace.report                      (네임스페이스)
+ kubernetes_service_account.report_generator_sa   (서비스 어카운트)
+ kubernetes_service.report_generator              (K8s Service)
+ kubernetes_deployment.report_generator           (K8s Deployment)
```

### 5.5.2 Terraform Apply
```powershell
# 실제 배포
terraform apply tfplan
```

**예상 출력**:
```
Apply complete! Resources added: 7.

Outputs:
(관련 출력)
```

---

## ✅ Step 6: ECR 이미지 확인

```powershell
aws ecr describe-images --repository-name $ECR_REPO --region $REGION --query 'imageDetails[0]'
```

---

## 🔍 Step 7: Kubernetes 리소스 검증

### 7.1 Namespace와 ServiceAccount 확인
```powershell
# Namespace 확인
kubectl get namespace report

# ServiceAccount 확인 (IRSA 설정)
kubectl get sa -n report
kubectl describe sa report-generator-sa -n report
```

**확인 항목**: `eks.amazonaws.com/role-arn` 어노테이션 존재

### 7.2 Deployment 상태 확인
```powershell
# Deployment 확인
kubectl get deployment -n report
kubectl describe deployment report-generator -n report

# Pod 상태 확인
kubectl get pods -n report
kubectl describe pod -n report <POD_NAME>
```

**Pod이 Running 상태가 될 때까지 대기** (보통 1-2분)

### 7.3 Service와 LoadBalancer IP 확인
```powershell
# Service 확인
kubectl get svc -n report
kubectl describe svc report-generator -n report

# External IP/Hostname 확인
EXTERNAL_IP = kubectl get svc report-generator -n report -o jsonpath='{.status.loadBalancer.ingress[0].hostname}'
echo $EXTERNAL_IP
```

---

## 🧪 Step 8: Health Check 테스트

```powershell
# Health Check 엔드포인트
curl http://$EXTERNAL_IP:8000/health

# 예상 응답
# {"status": "ok"}
```

**응답이 없으면 Pod 로그 확인**:
```powershell
kubectl logs -n report <POD_NAME>
kubectl logs -n report <POD_NAME> --tail=50 -f
```

---

## 📊 Step 9: 리소스 사용량 확인

```powershell
# Pod 리소스 사용량
kubectl top pod -n report

# 노드 리소스 사용량
kubectl top node

# IRSA IAM Role 확인
kubectl -n report describe pod <POD_NAME> | grep -A 5 "aws.amazon.com"
```

---

## 🔧 Step 10: 환경변수 검증

```powershell
# Pod 환경변수 확인
kubectl exec -n report <POD_NAME> -- env | grep -E "^(REPORT|ATHENA|AWS_)"

# 예상 출력
# AWS_REGION=ap-northeast-2
# ATHENA_DATABASE=capa_db
# REPORT_S3_BUCKET=capa-data-lake-827913617635
```

**예상 출력**:
```json
{
    "repositoryName": "capa-report-generator",
    "imageId": {
        "imageDigest": "sha256:abc123...",
        "imageTag": "latest"
    },
    "imageSizeInBytes": 234567,
    "imagePushedAt": "2026-02-15T..."
}
```

---

## 🔧 Step 6: Terraform 배포

### 6.1 Plan 생성
```powershell
cd c:\Users\3571\Desktop\projects\CAPA\infrastructure\terraform\environments\dev\base

terraform plan -out=tfplan
```

**확인 항목**:
- `kubernetes_deployment.report_generator` 생성
- `kubernetes_service_account.report_generator_sa` 생성
- `kubernetes_service.report_generator` 생성

### 6.2 Apply 실행
```powershell
terraform apply tfplan
```

**예상 출력**:
```
Apply complete! Resources: X added, 0 changed, 0 destroyed.
```

---

## 🎯 Step 7: Pod 상태 확인

```powershell
# Pod 상태 확인
kubectl get pods -n report

# Pod 상세 정보
kubectl describe pod -n report -l app=report-generator

# Service 확인
kubectl get svc -n report
```

**예상 Pod 상태**:
```
NAME                              READY   STATUS    RESTARTS   AGE
report-generator-xxxx-yyyy        1/1     Running   0          30s
```

---

## 🧪 Step 8: Health Check 검증

### 8.1 Pod이 Ready 상태가 될 때까지 대기
```powershell
kubectl wait --for=condition=ready pod -l app=report-generator -n report --timeout=300s
```

### 8.2 Port Forward 설정
```powershell
kubectl port-forward -n report svc/report-generator 8000:8000
```

**출력**:
```
Forwarding from 127.0.0.1:8000 -> 8000
Forwarding from [::1]:8000 -> 8000
Listening on port 8000.
```

### 8.3 Health Check 테스트 (다른 터미널)
```powershell
curl http://localhost:8000/health
```

**예상 응답**:
```json
{
  "status": "healthy",
  "service": "report-generator",
  "timestamp": "2026-02-15T..."
}
```

### 8.4 API 문서 확인
```powershell
# Swagger UI
# http://localhost:8000/docs

# ReDoc
# http://localhost:8000/redoc
```

---

## 📊 Step 9: 로그 확인

```powershell
# 실시간 로그
kubectl logs -n report -l app=report-generator -f

# 최근 로그
kubectl logs -n report -l app=report-generator --tail=50
```

---

## 🔄 이후 배포 (새 이미지 적용)

새로운 코드를 배포할 때는 Terraform 변경 없이 아래만 실행하면 됩니다:

```powershell
# 1. 이미지 빌드 및 푸시
cd c:\Users\3571\Desktop\projects\CAPA\services\report-generator
docker build -t capa-report-generator:latest .
docker tag capa-report-generator:latest "$ECR_URI:latest"
docker push "$ECR_URI:latest"

# 2. Pod 자동 재시작 (imagePullPolicy: Always로 인해 자동 적용)
kubectl rollout restart deployment/report-generator -n report

# 3. 롤아웃 상태 확인
kubectl rollout status deployment/report-generator -n report
```

---

## 🛑 정리 (필요 시)

### Kubernetes 리소스 삭제
```powershell
kubectl delete namespace report
```

### ECR 리포지토리 삭제
```powershell
aws ecr delete-repository --repository-name $ECR_REPO --region $REGION --force
```

### Docker 로컬 이미지 삭제
```powershell
docker rmi capa-report-generator:latest
docker rmi "$ECR_URI:latest"
```

---

## 🐛 문제 해결

### ImagePullBackOff 오류
```powershell
# Pod 상태 확인
kubectl describe pod -n report <POD_NAME>

# ECR 이미지 확인
aws ecr describe-images --repository-name $ECR_REPO --region $REGION
```

**해결**: ECR URI가 정확한지 확인, Node IAM Role에 ECR 접근 권한 확인

### CrashLoopBackOff 오류
```powershell
# 로그 확인
kubectl logs -n report <POD_NAME>
```

**해결**: requirements.txt 또는 main.py의 문법 오류 확인, Dockerfile CMD 확인

### Connection Refused
```powershell
# Pod이 Ready 상태인지 확인
kubectl get pods -n report -o wide

# Port가 올바른지 확인
kubectl get svc -n report report-generator
```

---

## ✨ 체크리스트

- [ ] ECR 로그인 완료
- [ ] Docker 이미지 빌드 성공
- [ ] ECR 푸시 완료
- [ ] Terraform apply 완료
- [ ] Pod이 Running 상태
- [ ] Health Check 200 OK
- [ ] Swagger UI 접속 가능

---

**배포 완료!** 🎉

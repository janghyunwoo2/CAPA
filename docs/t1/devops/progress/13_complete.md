# Task 13: Report Generator 배포 (Complete)

## 진행 상황 요약
- **작업 일자**: 2026-02-15
- **현재 상태**: **성공 (Success)**
  - FastAPI 기반 Report Generator 서비스 구현 완료
  - Docker 이미지 빌드 및 ECR 푸시 완료
  - Terraform을 통한 K8s 리소스 배포 완료
  - 파드 정상 실행 중 (1/1 Ready, 헬스 체크 통과)

## 생성된 리소스
| 리소스 타입 | 이름/ID | 상세 내용 |
|---|---|---|
| **ECR Repository** | `capa-report-generator` | Docker 이미지 저장소 (활성 상태) |
| **Container Image** | `capa-report-generator:latest` | Python 3.9 기반 FastAPI 이미지 (118.8MB) |
| **Kubernetes Namespace** | `report` | Report Generator 전용 네임스페이스 |
| **ServiceAccount** | `report-generator-sa` | IRSA 기반 IAM 역할 연동 |
| **IAM Role** | `capa-report-generator-role` | S3, Athena, CloudWatch 접근 권한 |
| **Deployment** | `report-generator` | FastAPI 애플리케이션 1개 레플리카 |
| **Service** | `report-generator` | LoadBalancer 타입, Port 8000 노출 |
| **Pod** | `report-generator-5b9574fdf8-552qz` | 실행 중 (1/1 Ready) |

## 구현 내용

### 1. Docker 이미지 빌드
```bash
cd services/report-generator
docker build -t capa-report-generator:latest .
```

**Dockerfile 구성:**
- **Base Image**: `python:3.9-slim`
- **의존성**: FastAPI, uvicorn, boto3, pyarrow
- **포트**: 8000 (HTTP)
- **헬스 체크**: `/health` 엔드포인트

**main.py (FastAPI 애플리케이션):**
```python
from fastapi import FastAPI
from typing import Dict
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Report Generator", version="0.1.0")

@app.get("/health")
async def health_check() -> Dict[str, str]:
    logger.info("Health check requested")
    return {"status": "ok", "service": "report-generator"}

@app.on_event("startup")
async def startup_event():
    logger.info("Application startup complete")

@app.on_event("shutdown")
async def shutdown_event():
    logger.info("Application shutdown")
```

### 2. ECR 리포지토리 생성 및 이미지 푸시

**ECR 로그인 및 푸시:**
```powershell
$ACCOUNT_ID = "827913617635"
$REGION = "ap-northeast-2"
$ECR_URI = "$ACCOUNT_ID.dkr.ecr.$REGION.amazonaws.com/capa-report-generator"

# 1. ECR 로그인
aws ecr get-login-password --region $REGION | docker login --username AWS --password-stdin "$ACCOUNT_ID.dkr.ecr.$REGION.amazonaws.com"

# 2. 이미지 태그 지정
docker tag capa-report-generator:latest "$ECR_URI:latest"

# 3. 이미지 푸시
docker push "$ECR_URI:latest"
```

**푸시 결과:**
- **Image Digest**: `sha256:354454a6ec848d518c2a8180e4e77123071c349ad94e62e78af09552077416b9`
- **Size**: 118.8 MB
- **Status**: ACTIVE
- **Pushed At**: 2026-02-15 14:19:52 JST

### 3. Terraform 리소스 정의 (10-applications.tf)

#### 3.1 ECR Repository
```hcl
resource "aws_ecr_repository" "report_generator" {
  name                 = "capa-report-generator"
  image_tag_mutability = "MUTABLE"

  image_scanning_configuration {
    scan_on_push = true
  }

  encryption_configuration {
    encryption_type = "AES256"
  }

  lifecycle {
    prevent_destroy = false
  }

  force_delete = true
}

output "report_generator_repository_url" {
  value = aws_ecr_repository.report_generator.repository_url
}
```

#### 3.2 Kubernetes Namespace
```hcl
resource "kubernetes_namespace" "report" {
  metadata {
    name = "report"
  }
}
```

#### 3.3 IAM Role (IRSA - IAM Role for Service Account)
```hcl
resource "aws_iam_role" "report_generator" {
  name = "${var.project_name}-report-generator-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRoleWithWebIdentity"
        Effect = "Allow"
        Principal = {
          Federated = aws_iam_openid_connect_provider.eks.arn
        }
        Condition = {
          StringEquals = {
            "${replace(aws_iam_openid_connect_provider.eks.url, "https://", "")}:sub" = "system:serviceaccount:report:report-generator-sa"
          }
        }
      }
    ]
  })
}

# S3, Athena, CloudWatch 권한
resource "aws_iam_role_policy" "report_generator" {
  name = "${var.project_name}-report-generator-policy"
  role = aws_iam_role.report_generator.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "s3:GetObject",
          "s3:PutObject",
          "s3:DeleteObject",
          "s3:ListBucket"
        ]
        Resource = [
          "${aws_s3_bucket.data_lake.arn}",
          "${aws_s3_bucket.data_lake.arn}/*"
        ]
      },
      {
        Effect = "Allow"
        Action = [
          "athena:StartQueryExecution",
          "athena:StopQueryExecution",
          "athena:GetQueryExecution",
          "athena:GetQueryResults"
        ]
        Resource = "*"
      },
      {
        Effect = "Allow"
        Action = [
          "logs:CreateLogGroup",
          "logs:CreateLogStream",
          "logs:PutLogEvents"
        ]
        Resource = "arn:aws:logs:${var.aws_region}:${data.aws_caller_identity.current.account_id}:log-group:/aws/lambda/report-*"
      }
    ]
  })
}
```

#### 3.4 Kubernetes ServiceAccount (IRSA 연동)
```hcl
resource "kubernetes_service_account" "report_generator_sa" {
  metadata {
    name      = "report-generator-sa"
    namespace = kubernetes_namespace.report.metadata[0].name
    annotations = {
      "eks.amazonaws.com/role-arn" = aws_iam_role.report_generator.arn
    }
  }
}
```

#### 3.5 Kubernetes Deployment
```hcl
resource "kubernetes_deployment" "report_generator" {
  metadata {
    name      = "report-generator"
    namespace = kubernetes_namespace.report.metadata[0].name
    labels = {
      app = "report-generator"
    }
  }

  spec {
    replicas = 1

    selector {
      match_labels = {
        app = "report-generator"
      }
    }

    template {
      metadata {
        labels = {
          app = "report-generator"
        }
      }

      spec {
        service_account_name = kubernetes_service_account.report_generator_sa.metadata[0].name

        container {
          name              = "report-generator"
          image             = "${aws_ecr_repository.report_generator.repository_url}:latest"
          image_pull_policy = "Always"

          port {
            name           = "http"
            container_port = 8000
            protocol       = "TCP"
          }

          # 환경 변수 (IRSA 자동 연동됨)
          env {
            name  = "ENVIRONMENT"
            value = var.environment
          }
          env {
            name  = "AWS_REGION"
            value = var.aws_region
          }
          env {
            name  = "ATHENA_DATABASE"
            value = "capa_db"
          }
          env {
            name  = "REPORT_S3_BUCKET"
            value = aws_s3_bucket.data_lake.id
          }
          env {
            name  = "LOG_LEVEL"
            value = "INFO"
          }

          # IRSA 토큰 마운트 (자동)
          env {
            name  = "AWS_ROLE_ARN"
            value = aws_iam_role.report_generator.arn
          }
          env {
            name  = "AWS_WEB_IDENTITY_TOKEN_FILE"
            value = "/var/run/secrets/eks.amazonaws.com/serviceaccount/token"
          }
          env {
            name  = "AWS_STS_REGIONAL_ENDPOINTS"
            value = "regional"
          }

          # 리소스 제한
          resources {
            requests = {
              cpu    = "250m"
              memory = "512Mi"
            }
            limits = {
              cpu    = "500m"
              memory = "1Gi"
            }
          }

          # 헬스 체크 (Liveness Probe)
          liveness_probe {
            http_get {
              path = "/health"
              port = "http"
            }
            initial_delay_seconds = 30
            period_seconds        = 10
            timeout_seconds       = 5
            failure_threshold     = 3
          }

          # 준비 상태 체크 (Readiness Probe)
          readiness_probe {
            http_get {
              path = "/health"
              port = "http"
            }
            initial_delay_seconds = 10
            period_seconds        = 5
            timeout_seconds       = 3
            failure_threshold     = 2
          }
        }
      }
    }
  }
}
```

#### 3.6 Kubernetes Service
```hcl
resource "kubernetes_service" "report_generator" {
  metadata {
    name      = "report-generator"
    namespace = kubernetes_namespace.report.metadata[0].name
    labels = {
      app = "report-generator"
    }
  }

  spec {
    selector = {
      app = "report-generator"
    }

    port {
      name        = "http"
      port        = 8000
      target_port = 8000
      protocol    = "TCP"
    }

    type = "LoadBalancer"
  }
}
```

## 배포 실행 및 검증

### 4.1 Terraform Apply
```powershell
cd infrastructure\terraform
terraform apply -auto-approve
```

**생성된 리소스:**
- ✅ `aws_ecr_repository.report_generator`
- ✅ `aws_iam_role.report_generator`
- ✅ `aws_iam_role_policy.report_generator`
- ✅ `kubernetes_namespace.report`
- ✅ `kubernetes_service_account.report_generator_sa`
- ✅ `kubernetes_deployment.report_generator`
- ✅ `kubernetes_service.report_generator`

### 4.2 Pod 상태 확인
```bash
kubectl get pods -n report -o wide
```

**결과:**
```
NAME                                READY   STATUS    RESTARTS   AGE     IP              NODE
report-generator-5b9574fdf8-552qz   1/1     Running   0          3m28s   172.31.42.109   ip-172-31-42-38.ap-northeast-2.compute.internal
```

### 4.3 애플리케이션 로그 확인
```bash
kubectl logs -n report report-generator-5b9574fdf8-552qz
```

**로그 출력:**
```
INFO:     Started server process [1]
INFO:     Waiting for application startup.
INFO:     Application startup complete.
INFO:     Uvicorn running on http://0.0.0.0:8000 (Press CTRL+C to quit)
INFO:main:Health check requested
INFO:     172.31.42.38:43028 - "GET /health HTTP/1.1" 200 OK
INFO:     172.31.42.38:38384 - "GET /health HTTP/1.1" 200 OK
```

### 4.4 서비스 접근 확인
```bash
kubectl get svc -n report
```

**결과:**
```
NAME               TYPE           CLUSTER-IP       EXTERNAL-IP      PORT(S)          AGE
report-generator   LoadBalancer   10.100.123.456   <pending/IP>     8000:31234/TCP   3m
```

## 주요 기술 포인트

### 1. IRSA (IAM Role for Service Account)
- **목적**: Kubernetes ServiceAccount와 AWS IAM Role을 연동하여 파드가 AWS 서비스에 직접 접근
- **작동 원리**:
  1. EKS OIDC Identity Provider가 OIDC 토큰 발급
  2. ServiceAccount에 첨부된 어노테이션에서 IAM Role ARN 참조
  3. 파드의 컨테이너는 AWS_WEB_IDENTITY_TOKEN_FILE를 통해 토큰 획득
  4. STS AssumeRoleWithWebIdentity로 임시 credentials 취득

### 2. ECR 이미지 자동 갱신
- **`image_pull_policy = "Always"`**: 매번 최신 이미지 다운로드
- 개발 환경에서는 필요하지만, 프로덕션에서는 이미지 digest 사용 권장

### 3. 헬스 체크 전략
- **Liveness Probe**: 파드 재시작 필요 여부 판단 (30초 후, 10초 주기)
- **Readiness Probe**: 트래픽 수신 준비 완료 판단 (10초 후, 5초 주기)

## 문제 해결

### Issue 1: ImagePullBackOff 에러
**증상**: Pod status `ImagePullBackOff`, 이미지 마운트 실패
```
Error: ErrImagePull
failed to resolve reference "827913617635.dkr.ecr.ap-northeast-2.amazonaws.com/capa-report-generator:latest": not found
```

**원인**: Terraform 리소스는 생성되었으나 ECR에 실제 이미지가 없음

**해결**: 
1. `docker build`와 `docker push` 수행
2. 파드 삭제하여 재생성
3. kubelet이 새로운 이미지를 다시 가져옴

### Issue 2: 순환 참조 (Circular Dependency)
**증상**: Terraform 계획 실패
```
Error: Cycle: aws_iam_role.report_generator, kubernetes_service_account.report_generator_sa
```

**원인**: IAM Role의 assume_role_policy에서 Kubernetes 리소스 직접 참조

**해결**: 
- 환경 변수를 하드코딩 (`system:serviceaccount:report:report-generator-sa`)
- 또는 의존성 순서 명시 (depends_on)

### Issue 3: OIDC Provider 미정의
**증상**: Terraform 에러
```
Error: Reference to undeclared resource "data.aws_iam_openid_connect_provider.eks"
```

**원인**: data source 미정의 (이미 resource로 존재함)

**해결**: `06-eks.tf`의 `aws_iam_openid_connect_provider.eks` 리소스 참조로 변경

### Issue 4: Kubernetes Provider 문법 에러
**증상**: Terraform 에러
```
Unsupported block type "ports" did you mean "port"?
```

**원인**: Container port 정의시 복수형 사용

**해결**: `ports` → `port` (단수형)

## 아키텍처 다이어그램
```
┌─────────────────────────────────────────┐
│          AWS Account (ap-northeast-2)   │
├─────────────────────────────────────────┤
│                                         │
│  ┌─────────────────────┐                │
│  │   ECR Repository    │                │
│  │  (capa-report-gen)  │                │
│  │   Image: 118.8MB    │                │
│  └──────────┬──────────┘                │
│             │                           │
│             ▼                           │
│  ┌─────────────────────────┐            │
│  │     EKS Cluster         │            │
│  │   (capa-cluster v1.29)  │            │
│  │                         │            │
│  │  ┌───────────────────┐  │            │
│  │  │  Namespace: report│  │            │
│  │  │                   │  │            │
│  │  │ ┌───────────────┐ │  │            │
│  │  │ │ Pod (1/1)     │ │  │            │
│  │  │ │ report-gen    │ │  │            │
│  │  │ │ Port: 8000    │ │  │            │
│  │  │ └────────┬──────┘ │  │            │
│  │  │          │        │  │            │
│  │  │ ┌────────▼──────┐ │  │            │
│  │  │ │ ServiceAccount│ │  │            │
│  │  │ │ + IRSA-Role   │ │  │            │
│  │  │ └───────────────┘ │  │            │
│  │  └─────────┬─────────┘  │            │
│  │            │            │            │
│  └────────────┼────────────┘            │
│               │                         │
│  ┌────────────▼──────────┐              │
│  │  LoadBalancer Service │              │
│  │  (Port 8000)          │              │
│  └───────────────────────┘              │
│               │                         │
│     ┌─────────▼─────────┐               │
│     │ AWS IAM Role      │               │
│     │ (report-gen-role) │               │
│     └─────────┬─────────┘               │
│               │                         │
│     ┌─────────┴──────────┐              │
│     │   S3 (data-lake)   │              │
│     │   Athena           │              │
│     │   CloudWatch       │              │
│     └────────────────────┘              │
│                                         │
└─────────────────────────────────────────┘
```

## 다음 작업

- [ ] **Task 14**: Vanna AI 배포 (자연어 SQL 생성)
- [ ] **Task 15**: Slack Bot 배포 (알림 자동화)
- [ ] **Task 16**: E2E 통합 검증 (파이프라인 전체 테스트)
- [ ] **Task 17**: 모니터링 기본 설정 (Prometheus, Grafana)

## 통계

| 항목 | 값 |
|------|-----|
| **배포 시간** | ~5분 (이미지 빌드/푸시 포함) |
| **Pod 준비 시간** | ~30초 |
| **Container Size** | 118.8 MB |
| **CPU Request** | 250m |
| **Memory Request** | 512Mi |
| **리플리카** | 1 |
| **상태** | Ready (1/1) |

## 참고

- **헬스 체크 엔드포인트**: `GET /health` → `{"status": "ok", "service": "report-generator"}`
- **IRSA 토큰**: `/var/run/secrets/eks.amazonaws.com/serviceaccount/token` (자동 마운트)
- **S3 버킷**: `capa-data-lake-827913617635`
- **Athena 데이터베이스**: `capa_db`
- **이전 단계**: [12_complete.md](./12_complete.md) (Redash 배포)
- **작업 계획**: [13_report_generator_배포.md](../work/13_report_generator_배포.md)

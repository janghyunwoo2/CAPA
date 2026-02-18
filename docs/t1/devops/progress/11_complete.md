# Task 11: Airflow 배포 (Complete)

## 진행 상황 요약
- **작업 일자**: 2026-02-13
- **현재 상태**: **성공 (Success)**
  - Terraform을 통한 Helm Chart (`airflow`) 배포 완료
  - **EKS 1.30 호환성 이슈로 인해 1.29 버전으로 다운그레이드 결정 및 적용**
  - PostgreSQL 이미지 ECR 푸시 및 연동 완료

## 생성된 리소스
| 리소스 타입 | 이름/ID | 상세 내용 |
|---|---|---|
| **EKS Cluster** | `capa-cluster` | **Version 1.29** (다운그레이드 적용) |
| **EKS Pod** | `airflow-webserver` | Airflow 웹 UI 서버 (LoadBalancer 연결) |
| **EKS Pod** | `airflow-scheduler` | DAG 스케줄링 및 실행 관리 |
| **EKS Pod** | `airflow-triggerer` | Async Operator 처리 |
| **EKS Pod** | `airflow-postgresql-0` | 메타데이터 DB (StatefulSet) |
| **Service** | `airflow-webserver` | 외부 접속용 Classic Load Balancer (Port 8080) |
| **StorageClass** | `gp2` | EBS CSI Driver 기반 스토리지 클래스 (1.29+ 호환) |
| **ECR Image** | `capa/postgres:11` | Airflow DB용 커스텀 이미지 (수동 푸시) |

## 구현된 파일
### 1. 06-eks.tf
```hcl
# EKS Cluster 정의 (버전 변경)
resource "aws_eks_cluster" "main" {
  name     = "${var.project_name}-cluster"
  role_arn = aws_iam_role.eks_cluster.arn
  version  = "1.29" # 1.30 -> 1.29 다운그레이드
  # ...
}
```

### 2. 10-applications.tf
```hcl
# Airflow Helm Release 정의
resource "helm_release" "airflow" {
  name       = "airflow"
  # ...
  # 필수 의존성 명시
  depends_on = [
    kubernetes_storage_class.gp2,
    aws_iam_role_policy_attachment.airflow_s3_access
  ]
}
```

### 3. airflow.yaml (Helm Values)
```yaml
# PostgreSQL 이미지 설정 (ECR 사용)
postgresql:
  image:
    registry: 827913617635.dkr.ecr.ap-northeast-2.amazonaws.com
    repository: capa/postgres
    tag: "11"
```

### 4. 05-storage-class.tf
```hcl
# EBS CSI Driver용 StorageClass (EKS 1.29+ 필수)
resource "kubernetes_storage_class" "gp2" {
  metadata { name = "gp2" }
  storage_provisioner = "ebs.csi.aws.com"
  volume_binding_mode = "WaitForFirstConsumer"
}
```

## 검증 결과 (Verification)
### 1. Pod 상태
```powershell
kubectl get pods -n airflow
```

**결과**:
| 이름 | 상태 | Ready |
|---|---|---|
| `airflow-postgresql-0` | **Running** | 1/1 |
| `airflow-scheduler-xxxx` | **Running** | 1/1 |
| `airflow-webserver-xxxx` | **Running** | 1/1 |
| `airflow-triggerer-xxxx` | **Running** | 1/1 |

### 2. Webserver 접속
```powershell
kubectl get svc -n airflow airflow-webserver
```
- **URL**: `http://a015fd856c89f45b8a62247f8b61fc74-2092633233.ap-northeast-2.elb.amazonaws.com:8080`
- **접속 확인**: 계정 `admin` / `admin` 으로 로그인 성공.

## 문제 해결 (Troubleshooting)

### 1. EKS 1.30 버전 호환성 실패 (Root Cause: Downgrade)
- **문제**: EKS 1.30환경에서 다양한 애드온 및 Provider 호환성 문제 지속 발생.
- **해결**:
  - 안정적인 배포를 위해 **EKS 버전을 1.29로 다운그레이드** 결정.
  - 1.29 버전 기준으로 Addon 및 설정 최적화.

### 2. PVC Pending (StorageClass)
- **문제**: 배포 초기 `PVC Pending` 발생.
- **원인**: EKS 1.29에서도 In-tree EBS provisioner가 제거되어 EBS CSI Driver 사용이 필수.
- **해결**: `kubernetes_storage_class`를 `ebs.csi.aws.com` 프로비저너로 명시적 정의.

### 3. PostgreSQL ImagePullBackOff
- **문제**: `airflow-postgresql-0` Pod가 이미지 Pull 실패.
- **원인**: Terraform으로 생성된 ECR 리포지토리가 비어 있었음.
- **해결**: Docker Hub에서 `postgres:11` pull 후 ECR 태그를 달아 수동 Push 수행.

## 향후 계획
### Task 12: Redash 배포
- Airflow와 동일하게 Helm 기반 배포
- 데이터 시각화 환경 구축

### 유지보수
- GitSync 동작 주기적 확인 (DAG 업데이트 반영 여부)
- CloudWatch Logs 연동 상태 점검

---

**이전 단계**: [10_complete.md (가상)](./10_helm_values_준비.md)  
**다음 단계**: Task 12 - Redash 배포

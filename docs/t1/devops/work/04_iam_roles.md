# 작업 04: IAM Roles 생성 (IRSA 준비)

> **Phase**: 1 (Terraform Base Layer)  
> **담당**: Security Ops  
> **예상 소요**: 5분  
> **선행 작업**: 03_terraform_backend.md

---

## 1. 목표

EKS Pod들이 AWS 리소스에 안전하게 접근하도록 IRSA(IAM Roles for Service Accounts) 기반 IAM Role을 생성합니다.

---

## 2. IRSA란?

| 방식 | Access Key 하드코딩 | IRSA (권장) |
|------|-------------------|-------------|
| **자격 증명** | `.env`에 Access Key 저장 | Pod마다 IAM Role 자동 부여 |
| **보안** | ❌ Git 노출 위험 | ✅ 코드에 자격 증명 없음 |
| **권한 제어** | ❌ 모든 Pod 동일 권한 | ✅ Pod별 최소 권한 |
| **순환** | ❌ 수동 교체 | ✅ 자동 갱신 |

---

## 3. 생성할 IAM Roles

| Role 이름 | 용도 | 권한 |
|-----------|------|------|
| `capa-eks-cluster-role` | EKS Cluster | EKS 관리 |
| `capa-eks-node-role` | EKS Node Group | EC2, ECR, CNI |
| `capa-firehose-role` | Kinesis Firehose | S3 PutObject |
| `capa-airflow-role` | Airflow Pod | S3 읽기/쓰기, Athena |
| `capa-bot-role` | Slack Bot Pod | Athena 쿼리 |
| `capa-redash-role` | Redash Pod | Athena 쿼리 |
| `capa-vanna-role` | Vanna AI Pod | Athena 쿼리, S3 읽기 |
| `capa-report-role` | Report Generator | Athena 쿼리, S3 쓰기 |
| `capa-alarm-role` | CloudWatch Alarm | SNS Publish |
| `capa-autoscaler-role` | Cluster Autoscaler | Auto Scaling |

---

## 4. 실행 단계

### 4.1 Terraform 파일 생성

`infrastructure/terraform/environments/dev/base/02-iam.tf`:

```hcl
# ============================================
# 1. EKS Cluster IAM Role
# ============================================
resource "aws_iam_role" "eks_cluster" {
  name = "capa-eks-cluster-role"
  
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Principal = {
        Service = "eks.amazonaws.com"
      }
      Action = "sts:AssumeRole"
    }]
  })
}

resource "aws_iam_role_policy_attachment" "eks_cluster_policy" {
  policy_arn = "arn:aws:iam::aws:policy/AmazonEKSClusterPolicy"
  role       = aws_iam_role.eks_cluster.name
}

# ============================================
# 2. EKS Node Group IAM Role
# ============================================
resource "aws_iam_role" "eks_node" {
  name = "capa-eks-node-role"
  
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Principal = {
        Service = "ec2.amazonaws.com"
      }
      Action = "sts:AssumeRole"
    }]
  })
}

resource "aws_iam_role_policy_attachment" "eks_node_policies" {
  for_each = toset([
    "arn:aws:iam::aws:policy/AmazonEKSWorkerNodePolicy",
    "arn:aws:iam::aws:policy/AmazonEKS_CNI_Policy",
    "arn:aws:iam::aws:policy/AmazonEC2ContainerRegistryReadOnly",
    "arn:aws:iam::aws:policy/AmazonSSMManagedInstanceCore"
  ])
  
  policy_arn = each.value
  role       = aws_iam_role.eks_node.name
}

# ============================================
# 3. Kinesis Firehose IAM Role
# ============================================
resource "aws_iam_role" "firehose" {
  name = "capa-firehose-role"
  
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Principal = {
        Service = "firehose.amazonaws.com"
      }
      Action = "sts:AssumeRole"
    }]
  })
}

resource "aws_iam_role_policy" "firehose_s3" {
  name = "firehose-s3-policy"
  role = aws_iam_role.firehose.id
  
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "s3:PutObject",
          "s3:PutObjectAcl"
        ]
        Resource = "arn:aws:s3:::capa-data-lake-*/*"
      },
      {
        Effect = "Allow"
        Action = ["s3:ListBucket"]
        Resource = "arn:aws:s3:::capa-data-lake-*"
      }
    ]
  })
}

# ============================================
# 4. CloudWatch Alarm IAM Role (SNS Publish)
# ============================================
resource "aws_iam_role" "cloudwatch_alarm" {
  name = "capa-alarm-role"
  
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Principal = {
        Service = "cloudwatch.amazonaws.com"
      }
      Action = "sts:AssumeRole"
    }]
  })
}

resource "aws_iam_role_policy" "alarm_policy" {
  name = "alarm-sns-policy"
  role = aws_iam_role.cloudwatch_alarm.id
  
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Action = "sns:Publish"
      Resource = "arn:aws:sns:*:*:capa-alerts"
    }]
  })
}
```

### 4.2 IRSA Roles (EKS OIDC 생성 후)

> **Note**: 아래 Role들은 `base/02-iam.tf`가 아니라 `apps/02-irsa.tf` (가칭) 또는 각 Helm 배포 시 생성할 수 있습니다. 여기서는 목록만 정의합니다.

- `capa-airflow-role`: `AmazonAthenaFullAccess` + `AmazonS3FullAccess` (배포 시 축소 권장)
- `capa-redash-role`: `AmazonAthenaFullAccess`
- `capa-vanna-role`: `AmazonAthenaFullAccess` + S3 Read
- `capa-report-role`: `AmazonAthenaFullAccess` + S3 Write
- `capa-bot-role`: `AmazonAthenaFullAccess`

### 4.2 Providers 설정

`infrastructure/terraform/environments/dev/base/01-providers.tf`:

```hcl
terraform {
  required_version = ">= 1.5.0"
  
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

provider "aws" {
  region = var.aws_region
  
  default_tags {
    tags = {
      Project     = "CAPA"
      Environment = "dev"
      ManagedBy   = "Terraform"
    }
  }
}
```

### 4.3 Variables 설정

`infrastructure/terraform/environments/dev/base/variables.tf`:

```hcl
variable "aws_region" {
  description = "AWS Region"
  type        = string
  default     = "ap-northeast-2"
}

variable "project_name" {
  description = "Project name"
  type        = string
  default     = "capa"
}

variable "environment" {
  description = "Environment (dev/staging/prod)"
  type        = string
  default     = "dev"
}
```

### 4.4 Terraform 실행

```powershell
cd infrastructure\terraform\environments\dev\base

# 초기화
terraform init

# Plan 확인
terraform plan

# 적용
terraform apply

# 예상 출력:
# aws_iam_role.eks_cluster: Creating...
# aws_iam_role.eks_node: Creating...
# aws_iam_role.firehose: Creating...
# ... (정책 연결)
# Apply complete! Resources: 7 added, 0 changed, 0 destroyed.
```

---

## 5. 검증 방법

### 5.1 IAM Role 생성 확인

```powershell
# AWS CLI로 확인
aws iam list-roles --query "Roles[?starts_with(RoleName, 'capa-')].RoleName" --output table

# 예상 출력:
# ----------------------------
# |       ListRoles           |
# +---------------------------+
# |  capa-eks-cluster-role    |
# |  capa-eks-node-role       |
# |  capa-firehose-role       |
# ----------------------------
```

### 5.2 정책 연결 확인

```powershell
# EKS Cluster Role 정책 확인
aws iam list-attached-role-policies --role-name capa-eks-cluster-role

# 예상 출력:
# AttachedPolicies:
# - PolicyName: AmazonEKSClusterPolicy
```

### 5.3 Terraform Output 확인

```powershell
terraform output
```

### 5.4 성공 기준

- [ ] `capa-eks-cluster-role` 생성됨
- [ ] `capa-eks-node-role` 생성됨
- [ ] `capa-firehose-role` 생성됨
- [ ] `capa-alarm-role` 생성됨
- [ ] 각 Role에 정책이 연결됨
- [ ] `terraform apply` 오류 없이 완료

---

## 6. 실패 시 대응

| 오류 | 원인 | 해결 방법 |
|------|------|-----------|
| `EntityAlreadyExists` | Role 이름 중복 | 기존 Role 삭제 or 이름 변경 |
| `AccessDenied (iam:CreateRole)` | IAM 권한 부족 | 관리자 권한 확인 |
| `InvalidInput` | JSON 문법 오류 | `jsonencode()` 확인 |

---

## 7. 다음 단계

✅ **IAM Roles 생성 완료** → `05_data_pipeline_기본.md`로 이동

> ⚠️ **Note**: Airflow/Bot IRSA Roles는 EKS OIDC Provider 생성 후 추가 (06_eks_cluster.md 이후)

---

## 8. 결과 기록

**실행자**: _______________  
**실행 일시**: _______________  
**결과**: ⬜ 성공 / ⬜ 실패  

**생성된 Roles**:
- [ ] capa-eks-cluster-role
- [ ] capa-eks-node-role
- [ ] capa-firehose-role
- [ ] capa-alarm-role

**메모**:
```
(실행 로그, 발생한 이슈 기록)
```

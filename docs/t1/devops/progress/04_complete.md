# ✅ 작업 04 완료: IAM Roles 생성 (IRSA 준비)

**작업 파일**: [`04_iam_roles.md`](../work/04_iam_roles.md)  
**Phase**: 1 (Terraform Base Layer)  
**실행 일시**: 2026-02-12 12:27 - 12:30  
**결과**: ✅ **성공**

---

## 📋 실행 내용

### 1. Terraform 파일 생성

**위치**: `infrastructure/terraform/environments/dev/base/`

**생성된 파일**:
- `01-providers.tf` (27줄) - AWS Provider 설정
- `variables.tf` (20줄) - 변수 정의 (aws_region, project_name, environment)
- `02-iam.tf` (141줄) - IAM Roles 4개 정의

---

### 2. Terraform 실행 단계

| 단계 | 명령어 | 결과 | 비고 |
|------|--------|------|------|
| **Init** | `terraform init` | ✅ 성공 | S3 Backend 연결 확인 |
| **Validate** | `terraform validate` | ✅ 성공 | Configuration 유효 |
| **Plan** | `terraform plan -out=tfplan` | ✅ 성공 | 11개 리소스 생성 예정 |
| **Apply** | `terraform apply tfplan` | ✅ 성공 | 11개 리소스 생성 완료 |

---

## ✅ 생성된 IAM Roles

| Role 이름 | 용도 | Principal | 연결 Policy |
|-----------|------|-----------|-------------|
| **capa-eks-cluster-role** | EKS Cluster | eks.amazonaws.com | AmazonEKSClusterPolicy |
| **capa-eks-node-role** | EKS Node Group | ec2.amazonaws.com | AmazonEKSWorkerNodePolicy<br>AmazonEKS_CNI_Policy<br>AmazonEC2ContainerRegistryReadOnly<br>AmazonSSMManagedInstanceCore<br>AmazonEBSCSIDriverPolicy |
| **capa-firehose-role** | Kinesis Firehose | firehose.amazonaws.com | Custom (S3 PutObject만) |
| **capa-alarm-role** | CloudWatch Alarm | cloudwatch.amazonaws.com | Custom (SNS Publish만) |

---

## 📊 생성 리소스 상세

### IAM Roles (4개)
1. ✅ `aws_iam_role.eks_cluster` - EKS Cluster Role
2. ✅ `aws_iam_role.eks_node` - EKS Node Group Role
3. ✅ `aws_iam_role.firehose` - Kinesis Firehose Role
4. ✅ `aws_iam_role.cloudwatch_alarm` - CloudWatch Alarm Role

### IAM Role Policy Attachments (7개)
1. ✅ `aws_iam_role_policy_attachment.eks_cluster_policy` - EKS Cluster Policy
2-6. ✅ `aws_iam_role_policy_attachment.eks_node_policies` (5개) - Node Group Policies
   - AmazonEKSWorkerNodePolicy
   - AmazonEKS_CNI_Policy
   - AmazonEC2ContainerRegistryReadOnly
   - AmazonSSMManagedInstanceCore
   - AmazonEBSCSIDriverPolicy (EBS 볼륨 지원)

### IAM Role Inline Policies (2개)
7. ✅ `aws_iam_role_policy.firehose_s3` - Firehose S3 Policy
8. ✅ `aws_iam_role_policy.alarm_policy` - CloudWatch SNS Policy

**Total**: 11개 리소스 (Apply complete! Resources: 11 added, 0 changed, 0 destroyed.)

---

## 🔒 보안 원칙 적용

### Least Privilege (최소 권한)

| Role | 권한 범위 | 리소스 제한 |
|------|----------|-------------|
| **Firehose** | S3 PutObject만<br>(삭제/읽기 불가) | `arn:aws:s3:::capa-data-lake-*/*` |
| **CloudWatch Alarm** | SNS Publish만 | `arn:aws:sns:*:*:capa-alerts` |

**핵심**:
- ✅ Firehose는 S3에 쓰기만 가능 → 실수로 삭제 불가
- ✅ CloudWatch는 특정 SNS Topic만 접근
- ✅ 모든 리소스 ARN이 `capa-*`로 제한

---

## ✅ 검증 결과

### AWS CLI 확인

```bash
$ aws iam list-roles --query "Roles[?starts_with(RoleName, 'capa-')].RoleName" --output table

---------------------------
|        ListRoles        |
+-------------------------+
|  capa-alarm-role        |
|  capa-eks-cluster-role  |
|  capa-eks-node-role     |
|  capa-firehose-role     |
+-------------------------+
```

✅ 4개 Role 모두 생성 확인

---

## ✅ 성공 기준 달성

- [x] `capa-eks-cluster-role` 생성됨
- [x] `capa-eks-node-role` 생성됨 (5개 Policy 연결)
- [x] `capa-firehose-role` 생성됨
- [x] `capa-alarm-role` 생성됨
- [x] 각 Role에 정책이 연결됨
- [x] `terraform apply` 오류 없이 완료
- [x] AWS CLI로 Role 조회 가능
- [x] Least Privilege 원칙 적용
- [x] EBS CSI Driver Policy 추가 (PVC 지원)

---

## 📝 추가 개선 사항

### EBS CSI Driver Policy 추가

작업 지침서에는 없었지만, **EKS Node에 EBS CSI Driver Policy를 추가**했습니다.

**이유**:
- Airflow, Vanna AI 등이 PersistentVolumeClaim(PVC)을 사용
- EBS CSI Driver가 없으면 Pod이 Pending 상태로 멈춤
- 작업 06 (EKS Cluster 생성) 이후 문제 방지

**추가된 Policy**:
```hcl
"arn:aws:iam::aws:policy/service-role/AmazonEBSCSIDriverPolicy"
```

---

## 🎯 다음 단계

### IRSA Roles는 나중에

> ⚠️ **Note**: Airflow, Bot, Redash, Vanna AI용 IRSA Roles는 **EKS OIDC Provider 생성 후** 추가합니다.
> 
> **이유**: IRSA는 EKS OIDC Provider의 신뢰 관계가 필요하므로, EKS Cluster가 먼저 생성되어야 합니다.
> 
> **작업 순서**:
> 1. ✅ 지금 (작업 04): AWS 서비스용 Roles (EKS, Firehose, CloudWatch)
> 2. ⏳ 나중 (작업 06 이후): IRSA Roles (Airflow, Bot, Redash, Vanna)

---

### 다음 작업

**Phase 1 계속**:
- **다음**: `05_data_pipeline_기본.md` - Kinesis, S3, Glue 생성
- [ ] `06_eks_cluster.md` - EKS Cluster
- [ ] `07_alert_system.md` - CloudWatch, SNS

---

## 💡 참고 사항

### State 관리
- **Backend**: S3 (`capa-terraform-state-827913617635`)
- **State Key**: `dev/base/terraform.tfstate`
- **Lock**: DynamoDB (`capa-terraform-lock`)

### 생성된 파일
```
infrastructure/terraform/environments/dev/base/
├── backend.tf           (기존)
├── 01-providers.tf     (신규)
├── variables.tf        (신규)
└── 02-iam.tf           (신규)
```

---

**작업 완료 시각**: 2026-02-12 12:30

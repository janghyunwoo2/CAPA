# Terraform Modules 디렉토리

## 목적
재사용 가능한 Terraform 모듈을 관리합니다.

## 모듈 목록 (예정)

### `kinesis/`
**리소스**:
- `aws_kinesis_stream` (실시간 로그 수집)
- `aws_kinesis_firehose_delivery_stream` (S3 전송)

**출력**:
- `stream_name`
- `stream_arn`
- `firehose_arn`

### `s3/`
**리소스**:
- `aws_s3_bucket` (Data Lake)
- `aws_s3_bucket_lifecycle_configuration` (비용 최적화)
- `aws_s3_bucket_versioning`

**출력**:
- `bucket_id`
- `bucket_arn`

### `glue/`
**리소스**:
- `aws_glue_catalog_database`
- `aws_glue_catalog_table`

**출력**:
- `database_name`
- `table_names`

### `eks/`
**리소스**:
- `aws_eks_cluster`
- `aws_eks_node_group`
- `aws_iam_openid_connect_provider` (IRSA)
- `aws_eks_addon` (EBS CSI Driver)

**출력**:
- `cluster_id`
- `cluster_endpoint`
- `cluster_name`
- `oidc_provider_arn`

### `iam/`
**리소스**:
- IAM Roles for Service Accounts (IRSA)
- Least Privilege Policies

**출력**:
- `role_arns` (각 서비스별)

## 사용 방법

`base/main.tf`에서 모듈 호출:

```hcl
module "eks" {
  source = "../../modules/eks"
  
  cluster_name = "capa-eks-dev"
  node_instance_type = "t3.medium"
  desired_size = 2
  min_size = 2
  max_size = 4
}
```

## 참고 사항
- 각 모듈은 독립적으로 테스트 가능
- 버전 관리 권장 (Git 태그 활용)
- 변수는 명확한 설명(description) 포함

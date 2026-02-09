# 인프라 (IaC - Terraform)

AWS 리소스를 Terraform으로 관리합니다.

## 구조

```
infra/terraform/
├── main.tf           # 모듈 호출
├── variables.tf      # 전역 변수
├── outputs.tf        # 출력값
└── modules/
    ├── kinesis/      # Kinesis Data Stream + Firehose
    ├── s3/           # S3 버킷
    ├── glue/         # Glue 카탈로그
    └── iam/          # IAM 역할/정책
```

## 빠른 시작

### 초기화
```bash
cd infra/terraform
terraform init
```

### 개발 환경 배포
```bash
terraform plan -var-file="environments/dev/terraform.tfvars"
terraform apply -var-file="environments/dev/terraform.tfvars"
```

### 프로덕션 환경 배포
```bash
terraform plan -var-file="environments/prod/terraform.tfvars"
terraform apply -var-file="environments/prod/terraform.tfvars"
```

## 환경 변수

- `AWS_PROFILE`: AWS 프로필 지정 (기본값: default)
- `AWS_REGION`: AWS 리전 (기본값: ap-northeast-2)

### Terraform 변수 (`terraform.tfvars`)
```hcl
aws_region    = "ap-northeast-2"
aws_account_id = "123456789012"
environment    = "dev"
```

## 모듈 설명

### kinesis/
- Kinesis Data Stream (온디맨드)
- Kinesis Data Firehose
- Parquet 변환 설정

### s3/
- S3 버킷 생성
- 버전 관리 설정
- 파티션 정의

### glue/
- Glue 카탈로그 데이터베이스
- 자동 스키마 감지

### iam/
- Firehose 실행 역할
- Airflow 실행 역할

## 상태 관리

### 로컬 상태 (현재)
- `terraform.tfstate` (로컬에 저장)

### S3 백엔드 (프로덕션 권장)
```hcl
terraform {
  backend "s3" {
    bucket         = "capa-terraform-state"
    key            = "terraform.tfstate"
    region         = "ap-northeast-2"
    encrypt        = true
    dynamodb_table = "capa-terraform-lock"
  }
}
```

## 참고

- [Terraform AWS Provider](https://registry.terraform.io/providers/hashicorp/aws/latest/docs)
- [AWS Kinesis Pricing](https://aws.amazon.com/kinesis/pricing/)

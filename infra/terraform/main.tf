# CAPA 프로젝트 메인 Terraform 설정
# Kinesis Data Stream, Firehose, S3, Glue, IAM 리소스 정의

terraform {
  required_version = ">= 1.0"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }

  # 백엔드 설정 (선택: S3에 state 저장)
  # backend "s3" {
  #   bucket         = "capa-terraform-state"
  #   key            = "terraform.tfstate"
  #   region         = "ap-northeast-2"
  #   encrypt        = true
  #   dynamodb_table = "capa-terraform-lock"
  # }
}

provider "aws" {
  region = var.aws_region

  default_tags {
    tags = {
      Project     = "CAPA"
      Environment = var.environment
      ManagedBy   = "Terraform"
    }
  }
}

# 환경별 모듈 호출
module "s3" {
  source = "./modules/s3"
  
  environment = var.environment
  bucket_name = "capa-logs-${var.aws_account_id}-${var.aws_region}"
}

module "glue" {
  source = "./modules/glue"
  
  environment = var.environment
  s3_path     = module.s3.bucket_arn
  
  depends_on = [module.s3]
}

module "kinesis" {
  source = "./modules/kinesis"
  
  environment              = var.environment
  stream_name              = "capa-ad-logs-${var.environment}"
  retention_period         = var.kinesis_retention_hours
  firehose_role_arn        = module.iam.firehose_role_arn
  s3_bucket_arn            = module.s3.bucket_arn
  glue_database_name       = module.glue.database_name
  buffer_size_mb           = var.firehose_buffer_size_mb
  buffer_interval_seconds  = var.firehose_buffer_interval_seconds
  
  depends_on = [module.s3, module.glue, module.iam]
}

module "iam" {
  source = "./modules/iam"
  
  environment              = var.environment
  kinesis_stream_arn       = "arn:aws:kinesis:${var.aws_region}:${var.aws_account_id}:stream/capa-ad-logs-${var.environment}"
  s3_bucket_arn            = module.s3.bucket_arn
  firehose_role_name       = "capa-firehose-role-${var.environment}"
  airflow_role_name        = "capa-airflow-role-${var.environment}"
}

module "eks" {
  source = "./modules/eks"
  
  cluster_name    = "capa-${var.environment}"
  environment     = var.environment
  kubernetes_version = "1.28"
  desired_size    = var.environment == "prod" ? 3 : 2
  min_size        = var.environment == "prod" ? 2 : 1
  max_size        = var.environment == "prod" ? 10 : 5
  instance_types  = var.environment == "prod" ? ["t3.large"] : ["t3.medium"]
  s3_bucket_arn   = module.s3.bucket_arn
}

# Outputs
output "kinesis_stream_name" {
  value       = module.kinesis.stream_name
  description = "Kinesis Stream 이름"
}

output "kinesis_stream_arn" {
  value       = module.kinesis.stream_arn
  description = "Kinesis Stream ARN"
}

output "firehose_name" {
  value       = module.kinesis.firehose_name
  description = "Kinesis Firehose 이름"
}

output "s3_bucket_name" {
  value       = module.s3.bucket_name
  description = "S3 버킷 이름"
}

output "s3_bucket_arn" {
  value       = module.s3.bucket_arn
  description = "S3 버킷 ARN"
}

output "glue_database_name" {
  value       = module.glue.database_name
  description = "Glue 데이터베이스 이름"
}

output "glue_tables" {
  value = {
    impression  = module.glue.impression_table_name
    click       = module.glue.click_table_name
    conversion  = module.glue.conversion_table_name
  }
  description = "Glue 테이블 이름들"
}

output "firehose_role_arn" {
  value       = module.iam.firehose_role_arn
  description = "Firehose 실행 역할 ARN"
}

output "airflow_role_arn" {
  value       = module.iam.airflow_role_arn
  description = "Airflow 실행 역할 ARN"
}

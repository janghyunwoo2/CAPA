# Terraform Providers Configuration
# 작업: 04_iam_roles.md (Phase 1)
# 용도: AWS Provider 설정 및 기본 태그 정의

terraform {
  required_version = ">= 1.5.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "5.80.0"
    }
  }
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

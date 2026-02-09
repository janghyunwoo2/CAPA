# Glue 모듈 변수

variable "environment" {
  description = "환경 (dev, prod)"
  type        = string
}

variable "s3_path" {
  description = "S3 경로 (Bucket ARN)"
  type        = string
}

variable "database_name" {
  description = "Glue 데이터베이스 이름"
  type        = string
  default     = "capa"
}

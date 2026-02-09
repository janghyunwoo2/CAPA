# Terraform 변수 정의

variable "aws_region" {
  description = "AWS 리전"
  type        = string
  default     = "ap-northeast-2"
}

variable "aws_account_id" {
  description = "AWS Account ID"
  type        = string
}

variable "environment" {
  description = "환경 (dev, prod)"
  type        = string
  validation {
    condition     = contains(["dev", "prod"], var.environment)
    error_message = "environment는 dev 또는 prod여야 합니다."
  }
}

variable "kinesis_retention_hours" {
  description = "Kinesis Data Stream 보존 기간 (시간)"
  type        = number
  default     = 24
}

variable "firehose_buffer_size_mb" {
  description = "Firehose 버퍼 크기 (MB)"
  type        = number
  default     = 128
}

variable "firehose_buffer_interval_seconds" {
  description = "Firehose 버퍼 간격 (초)"
  type        = number
  default     = 60
}

variable "enable_logging" {
  description = "CloudWatch 로깅 활성화"
  type        = bool
  default     = true
}

variable "tags" {
  description = "공통 태그"
  type        = map(string)
  default = {
    Project = "CAPA"
    Team    = "DataEngineering"
  }
}

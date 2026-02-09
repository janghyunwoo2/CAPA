# IAM 모듈 변수

variable "environment" {
  description = "환경 (dev, prod)"
  type        = string
}

variable "kinesis_stream_arn" {
  description = "Kinesis Stream ARN"
  type        = string
}

variable "s3_bucket_arn" {
  description = "S3 버킷 ARN"
  type        = string
}

variable "firehose_role_name" {
  description = "Firehose 실행 역할 이름"
  type        = string
}

variable "airflow_role_name" {
  description = "Airflow 실행 역할 이름"
  type        = string
}

# Kinesis 모듈 변수

variable "environment" {
  type = string
}

variable "stream_name" {
  type = string
}

variable "retention_period" {
  type    = number
  default = 24
}

variable "firehose_role_arn" {
  type = string
}

variable "s3_bucket_arn" {
  type = string
}

variable "glue_database_name" {
  type = string
}

variable "buffer_size_mb" {
  type    = number
  default = 128
}

variable "buffer_interval_seconds" {
  type    = number
  default = 60
}

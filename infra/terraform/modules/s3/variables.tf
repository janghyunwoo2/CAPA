# S3 모듈 변수

variable "environment" {
  description = "환경 (dev, prod)"
  type        = string
}

variable "bucket_name" {
  description = "S3 버킷 이름"
  type        = string
}

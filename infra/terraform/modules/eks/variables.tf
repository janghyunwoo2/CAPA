# EKS 모듈 변수

variable "cluster_name" {
  description = "EKS 클러스터 이름"
  type        = string
}

variable "environment" {
  description = "환경 (dev, prod)"
  type        = string
}

variable "kubernetes_version" {
  description = "Kubernetes 버전"
  type        = string
  default     = "1.28"
}

variable "desired_size" {
  description = "원하는 Node 개수"
  type        = number
  default     = 2
}

variable "min_size" {
  description = "최소 Node 개수"
  type        = number
  default     = 1
}

variable "max_size" {
  description = "최대 Node 개수"
  type        = number
  default     = 5
}

variable "instance_types" {
  description = "EC2 인스턴스 타입"
  type        = list(string)
  default     = ["t3.medium"]
}

variable "disk_size" {
  description = "EBS 볼륨 크기 (GB)"
  type        = number
  default     = 50
}

variable "s3_bucket_arn" {
  description = "S3 버킷 ARN (Airflow 로그용)"
  type        = string
}

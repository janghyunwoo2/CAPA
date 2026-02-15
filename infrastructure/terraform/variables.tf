# Terraform Variables
# 작업: 04_iam_roles.md (Phase 1)
# 용도: 환경별 변수 정의

variable "aws_region" {
  description = "AWS Region"
  type        = string
  default     = "ap-northeast-2"
}

variable "aws_access_key" {
  description = "AWS Access Key ID"
  type        = string
  sensitive   = true
}

variable "aws_secret_key" {
  description = "AWS Secret Access Key"
  type        = string
  sensitive   = true
}

variable "project_name" {
  description = "Project name"
  type        = string
  default     = "capa"
}

variable "environment" {
  description = "Environment (dev/staging/prod)"
  type        = string
  default     = "dev"
}

variable "team_members_arns" {
  description = "EKS 접근 권한을 부여할 팀원들의 IAM ARN 목록 (terraform.tfvars에서 설정)"
  type        = list(string)
  default     = []
}

variable "alert_email" {
  description = "Email address for alert notifications"
  type        = string
  default     = "admin@example.com" # TODO: 실제 이메일 주소로 변경
}

variable "slack_bot_token" {
  description = "Slack Bot Token (xoxb-...)"
  type        = string
  sensitive   = true
  default     = ""
}

variable "slack_app_token" {
  description = "Slack App Level Token (xapp-...)"
  type        = string
  sensitive   = true
  default     = ""
}

# ------------------------------------------------------------------------------
# Redash Secrets
# ------------------------------------------------------------------------------
variable "redash_postgresql_password" {
  description = "Password for Redash PostgreSQL database"
  type        = string
  sensitive   = true
}

variable "redash_cookie_secret" {
  description = "Secret key for Redash cookie generation"
  type        = string
  sensitive   = true
}

variable "redash_secret_key" {
  description = "Secret key for Redash data encryption"
  type        = string
  sensitive   = true
}

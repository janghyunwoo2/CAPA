# Terraform Variables
# 작업: 04_iam_roles.md (Phase 1)
# 용도: 환경별 변수 정의

variable "aws_region" {
  description = "AWS Region"
  type        = string
  default     = "ap-northeast-2"
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

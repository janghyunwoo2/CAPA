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

variable "slack_channel_id" {
  description = "Slack Channel ID to send reports (C...)"
  type        = string
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

# ------------------------------------------------------------------------------
# Vanna AI Secrets
# ------------------------------------------------------------------------------
variable "anthropic_api_key" {
  description = "Anthropic API Key for Claude (Vanna AI)"
  type        = string
  sensitive   = true
}

# ------------------------------------------------------------------------------
# Text-to-SQL Secrets
# ------------------------------------------------------------------------------
variable "redash_api_key" {
  description = "Redash API Key (Admin > Settings > API Key)"
  type        = string
  sensitive   = true
  default     = ""
}

variable "internal_api_token" {
  description = "내부 서비스 간 인증 토큰 (vanna-api ↔ slack-bot, openssl rand -hex 32)"
  type        = string
  sensitive   = true
  default     = ""
}

# ------------------------------------------------------------------------------
# Kubernetes Deployment Image Tag
# ------------------------------------------------------------------------------
variable "image_tag" {
  description = "ECR 이미지 태그 (CI/CD 파이프라인에서 주입, 예: git SHA 또는 semver)"
  type        = string
  default     = "latest"
}

# ------------------------------------------------------------------------------
# Redash Public URL
# ------------------------------------------------------------------------------
variable "redash_public_url" {
  description = "Redash 외부 접근 URL (vanna-api가 차트 링크 생성 시 사용)"
  type        = string
  default     = ""
}

# ------------------------------------------------------------------------------
# Phase 2: Feature Flags
# ------------------------------------------------------------------------------
variable "phase2_rag_enabled" {
  description = "3단계 RAG 파이프라인 활성화 (벡터 → Reranker → LLM 선별)"
  type        = bool
  default     = false
}

variable "phase2_feedback_enabled" {
  description = "Phase 2 피드백 루프 활성화 (DynamoDB 저장만, 즉시 학습 비활성)"
  type        = bool
  default     = false
}

variable "async_query_enabled" {
  description = "비동기 쿼리 처리 활성화 (POST /query → 202 + 폴링)"
  type        = bool
  default     = false
}

variable "dynamodb_enabled" {
  description = "DynamoDB History 저장소 활성화 (false 시 JSON Lines 파일 사용)"
  type        = bool
  default     = false
}

# ------------------------------------------------------------------------------
# Phase 2: DynamoDB 테이블명
# ------------------------------------------------------------------------------
variable "dynamodb_history_table" {
  description = "쿼리 이력 DynamoDB 테이블명 (capa-{env}-query-history)"
  type        = string
  default     = "capa-dev-query-history"
}

variable "dynamodb_feedback_table" {
  description = "피드백 DynamoDB 테이블명 (capa-{env}-pending-feedbacks)"
  type        = string
  default     = "capa-dev-pending-feedbacks"
}

variable "dynamodb_async_table" {
  description = "비동기 Task DynamoDB 테이블명 (capa-{env}-async-tasks)"
  type        = string
  default     = "capa-dev-async-tasks"
}

variable "dynamodb_query_hash_table" {
  description = "SQL 해시 인덱스 DynamoDB 테이블명 (capa-{env}-query-hash-index)"
  type        = string
  default     = "capa-dev-query-hash-index"
}

# ------------------------------------------------------------------------------
# Phase 2: Reranker 설정
# ------------------------------------------------------------------------------
variable "reranker_model_name" {
  description = "Cross-Encoder Reranker 모델명 (HuggingFace Hub)"
  type        = string
  default     = "cross-encoder/ms-marco-MiniLM-L-6-v2"
}

variable "reranker_top_k" {
  description = "Reranker 상위 K개 후보 유지 수"
  type        = number
  default     = 5
}


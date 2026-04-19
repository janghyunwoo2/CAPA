# ==============================================================================
# CAPA Infrastructure - DynamoDB Tables (Phase 2 Text-to-SQL)
# ==============================================================================
# FR-11: History 저장소 전환 (JSON Lines → DynamoDB)
# FR-16: 피드백 루프 품질 제어 (pending_feedbacks 테이블)
#
# 무료 요금 범위 (테이블 + GSI 전체 합산 25 WCU/RCU 이하):
#   query_history 테이블 5 + feedback-status-index GSI 3 + channel-index GSI 3
#   + session_id-turn_number-index GSI 3
#   + pending_feedbacks 테이블 7 + status-index GSI 4 = 합계 25 WCU/RCU
# FR-20: session_id-turn_number-index GSI 추가 (멀티턴 이력 조회), query_history 8→5 조정
# ==============================================================================

resource "aws_dynamodb_table" "query_history" {
  name         = "${var.project_name}-${var.environment}-query-history"
  billing_mode = "PROVISIONED"
  hash_key     = "history_id"

  write_capacity = 5
  read_capacity  = 5

  attribute {
    name = "history_id"
    type = "S"
  }

  attribute {
    name = "feedback"
    type = "S"
  }

  attribute {
    name = "timestamp"
    type = "S"
  }

  attribute {
    name = "slack_channel_id"
    type = "S"
  }

  attribute {
    name = "session_id"
    type = "S"
  }

  attribute {
    name = "turn_number"
    type = "N"
  }

  global_secondary_index {
    name            = "feedback-status-index"
    hash_key        = "feedback"
    range_key       = "timestamp"
    projection_type = "ALL"
    write_capacity  = 3
    read_capacity   = 3
  }

  global_secondary_index {
    name            = "channel-index"
    hash_key        = "slack_channel_id"
    range_key       = "timestamp"
    projection_type = "ALL"
    write_capacity  = 3
    read_capacity   = 3
  }

  global_secondary_index {
    name            = "session_id-turn_number-index"
    hash_key        = "session_id"
    range_key       = "turn_number"
    projection_type = "ALL"
    write_capacity  = 3
    read_capacity   = 3
  }

  ttl {
    attribute_name = "ttl"
    enabled        = true
  }

  tags = {
    Project     = "CAPA"
    Environment = var.environment
    ManagedBy   = "Terraform"
    Feature     = "text-to-sql-phase2"
  }
}

resource "aws_dynamodb_table" "pending_feedbacks" {
  name         = "${var.project_name}-${var.environment}-pending-feedbacks"
  billing_mode = "PROVISIONED"
  hash_key     = "feedback_id"

  write_capacity = 7
  read_capacity  = 7

  attribute {
    name = "feedback_id"
    type = "S"
  }

  attribute {
    name = "status"
    type = "S"
  }

  attribute {
    name = "created_at"
    type = "S"
  }

  global_secondary_index {
    name            = "status-index"
    hash_key        = "status"
    range_key       = "created_at"
    projection_type = "ALL"
    write_capacity  = 4
    read_capacity   = 4
  }

  ttl {
    attribute_name = "ttl"
    enabled        = true
  }

  tags = {
    Project     = "CAPA"
    Environment = var.environment
    ManagedBy   = "Terraform"
    Feature     = "text-to-sql-phase2"
  }
}

# ------------------------------------------------------------------------------
# AsyncQueryManager용 DynamoDB 테이블 (ASYNC_QUERY_ENABLED=true 시 사용)
# terraform import aws_dynamodb_table.async_tasks capa-dev-async-tasks 로 기존 테이블 가져옴
# ------------------------------------------------------------------------------
resource "aws_dynamodb_table" "async_tasks" {
  name         = "${var.project_name}-${var.environment}-async-tasks"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "task_id"

  attribute {
    name = "task_id"
    type = "S"
  }

  ttl {
    attribute_name = "ttl"
    enabled        = true
  }

  tags = {
    Project     = "CAPA"
    Environment = var.environment
    ManagedBy   = "Terraform"
    Feature     = "text-to-sql-phase2"
  }
}

# ------------------------------------------------------------------------------
# IAM Policy: vanna-api → DynamoDB 접근 권한
# ------------------------------------------------------------------------------
resource "aws_iam_policy" "vanna_dynamodb" {
  name        = "${var.project_name}-${var.environment}-vanna-dynamodb"
  description = "vanna-api DynamoDB query_history + pending_feedbacks + async_tasks 읽기/쓰기 권한"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "dynamodb:GetItem",
          "dynamodb:PutItem",
          "dynamodb:UpdateItem",
          "dynamodb:DeleteItem",
          "dynamodb:Query",
          "dynamodb:Scan",
        ]
        Resource = [
          aws_dynamodb_table.query_history.arn,
          "${aws_dynamodb_table.query_history.arn}/index/*",
          aws_dynamodb_table.pending_feedbacks.arn,
          "${aws_dynamodb_table.pending_feedbacks.arn}/index/*",
          aws_dynamodb_table.async_tasks.arn,
          "${aws_dynamodb_table.async_tasks.arn}/index/*",
        ]
      }
    ]
  })

  tags = {
    Project     = "CAPA"
    Environment = var.environment
    ManagedBy   = "Terraform"
  }
}

resource "aws_iam_role_policy_attachment" "vanna_dynamodb" {
  role       = "${var.project_name}-vanna-role"
  policy_arn = aws_iam_policy.vanna_dynamodb.arn
}

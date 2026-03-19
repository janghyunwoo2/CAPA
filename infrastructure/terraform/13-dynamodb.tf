# ==============================================================================
# CAPA Infrastructure - DynamoDB Tables (Phase 2 Text-to-SQL)
# ==============================================================================
# FR-11: History 저장소 전환 (JSON Lines → DynamoDB)
# FR-16: 피드백 루프 품질 제어 (pending_feedbacks 테이블)
#
# 무료 요금 범위 (테이블 + GSI 전체 합산 25 WCU/RCU 이하):
#   query_history 테이블 8 + feedback-status-index GSI 3 + channel-index GSI 3
#   + pending_feedbacks 테이블 7 + status-index GSI 4 = 합계 25 WCU/RCU
# ==============================================================================

resource "aws_dynamodb_table" "query_history" {
  name           = "${var.project_name}-${var.environment}-query-history"
  billing_mode   = "PROVISIONED"
  hash_key       = "history_id"

  write_capacity = 8
  read_capacity  = 8

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

  global_secondary_index {
    name               = "feedback-status-index"
    hash_key           = "feedback"
    range_key          = "timestamp"
    projection_type    = "ALL"
    write_capacity     = 3
    read_capacity      = 3
  }

  global_secondary_index {
    name               = "channel-index"
    hash_key           = "slack_channel_id"
    range_key          = "timestamp"
    projection_type    = "ALL"
    write_capacity     = 3
    read_capacity      = 3
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
  name           = "${var.project_name}-${var.environment}-pending-feedbacks"
  billing_mode   = "PROVISIONED"
  hash_key       = "feedback_id"

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
    name               = "status-index"
    hash_key           = "status"
    range_key          = "created_at"
    projection_type    = "ALL"
    write_capacity     = 4
    read_capacity      = 4
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
  description = "vanna-api DynamoDB query_history + pending_feedbacks 읽기/쓰기 권한"

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

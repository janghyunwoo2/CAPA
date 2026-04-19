# SNS Topic Configuration
# 작업: 07_alert_system.md (Phase 1)
# 용도: Alert 알림 전송

# SNS Topic for Alerts
resource "aws_sns_topic" "capa_alerts" {
  name         = "capa-alerts-${var.environment}"
  display_name = "CAPA Alert Notifications"
  
  tags = {
    Name        = "capa-alerts-${var.environment}"
    Environment = var.environment
    ManagedBy   = "Terraform"
    Project     = "CAPA"
  }
}

# SNS Topic Policy (CloudWatch Alarms가 Publish 가능하도록)
resource "aws_sns_topic_policy" "capa_alerts" {
  arn = aws_sns_topic.capa_alerts.arn
  
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "AllowCloudWatchPublish"
        Effect = "Allow"
        Principal = {
          Service = "cloudwatch.amazonaws.com"
        }
        Action   = "SNS:Publish"
        Resource = aws_sns_topic.capa_alerts.arn
      }
    ]
  })
}

# Email Subscription (테스트용 - 실제 환경에서는 변수로 관리)
# 참고: 구독 승인 이메일을 확인하고 승인해야 알림 수신 가능
resource "aws_sns_topic_subscription" "email_alerts" {
  topic_arn = aws_sns_topic.capa_alerts.arn
  protocol  = "email"
  endpoint  = var.alert_email # variables.tf에 정의 필요
  
  # 이메일 구독은 수동 승인 필요
  # AWS Console에서 구독 확인 링크 클릭 필요
}

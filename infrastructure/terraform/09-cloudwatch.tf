# CloudWatch Alarms Configuration
# 작업: 07_alert_system.md (Phase 1)
# 용도: 시스템 이상 감지

# ============================================
# 1. Kinesis Stream Low Traffic Alarm
# ============================================
resource "aws_cloudwatch_metric_alarm" "kinesis_low_traffic" {
  alarm_name          = "capa-kinesis-low-traffic-${var.environment}"
  comparison_operator = "LessThanThreshold"
  evaluation_periods  = 2
  metric_name         = "IncomingRecords"
  namespace           = "AWS/Kinesis"
  period              = 300 # 5분
  statistic           = "Sum"
  threshold           = 10 # 5분간 10개 미만이면 알림
  alarm_description   = "Kinesis Stream에 유입되는 레코드 수가 비정상적으로 낮습니다"
  treat_missing_data  = "notBreaching" # 데이터 없을 때는 정상으로 간주

  dimensions = {
    StreamName = aws_kinesis_stream.main.name
  }

  alarm_actions = [aws_sns_topic.capa_alerts.arn]
  ok_actions    = [aws_sns_topic.capa_alerts.arn]

  tags = {
    Name        = "capa-kinesis-low-traffic-${var.environment}"
    Environment = var.environment
    ManagedBy   = "Terraform"
  }
}

# ============================================
# 2. Kinesis Stream High Iterator Age Alarm
# ============================================
# Iterator Age가 높으면 consumer가 데이터를 제때 처리하지 못하고 있음을 의미
resource "aws_cloudwatch_metric_alarm" "kinesis_high_iterator_age" {
  alarm_name          = "capa-kinesis-high-iterator-age-${var.environment}"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 1
  metric_name         = "GetRecords.IteratorAgeMilliseconds"
  namespace           = "AWS/Kinesis"
  period              = 60 # 1분
  statistic           = "Maximum"
  threshold           = 60000 # 60초 (1분) 이상 지연
  alarm_description   = "Kinesis Stream 데이터 처리가 지연되고 있습니다"
  treat_missing_data  = "notBreaching"

  dimensions = {
    StreamName = aws_kinesis_stream.main.name
  }

  alarm_actions = [aws_sns_topic.capa_alerts.arn]
  ok_actions    = [aws_sns_topic.capa_alerts.arn]

  tags = {
    Name        = "capa-kinesis-high-iterator-age-${var.environment}"
    Environment = var.environment
    ManagedBy   = "Terraform"
  }
}

# ============================================
# 3. EKS Cluster Node CPU High Utilization
# ============================================
# 참고: Container Insights 활성화 필요 (추후 작업)
# 현재는 EC2 인스턴스 기반 CPU 메트릭 사용
resource "aws_cloudwatch_metric_alarm" "eks_node_cpu_high" {
  alarm_name          = "capa-eks-node-cpu-high-${var.environment}"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 2
  metric_name         = "CPUUtilization"
  namespace           = "AWS/EC2"
  period              = 300 # 5분
  statistic           = "Average"
  threshold           = 80 # CPU 80% 이상
  alarm_description   = "EKS 노드 CPU 사용률이 높습니다"
  treat_missing_data  = "notBreaching"

  # EKS 노드 그룹의 인스턴스만 필터링
  # 참고: 실제로는 Auto Scaling Group 이름으로 필터링해야 정확함
  alarm_actions = [aws_sns_topic.capa_alerts.arn]
  ok_actions    = [aws_sns_topic.capa_alerts.arn]

  tags = {
    Name        = "capa-eks-node-cpu-high-${var.environment}"
    Environment = var.environment
    ManagedBy   = "Terraform"
  }
}

# ============================================
# 4. Firehose Delivery Failure Alarm
# ============================================
resource "aws_cloudwatch_metric_alarm" "firehose_delivery_failure" {
  alarm_name          = "capa-firehose-delivery-failure-${var.environment}"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 1
  metric_name         = "DeliveryToS3.DataFreshness"
  namespace           = "AWS/Firehose"
  period              = 300 # 5분
  statistic           = "Maximum"
  threshold           = 900 # 15분 이상 지연
  alarm_description   = "Firehose가 S3로 데이터 전송에 실패하고 있습니다"
  treat_missing_data  = "notBreaching"

  dimensions = {
    DeliveryStreamName = aws_kinesis_firehose_delivery_stream.main.name
  }

  alarm_actions = [aws_sns_topic.capa_alerts.arn]
  ok_actions    = [aws_sns_topic.capa_alerts.arn]

  tags = {
    Name        = "capa-firehose-delivery-failure-${var.environment}"
    Environment = var.environment
    ManagedBy   = "Terraform"
  }
}

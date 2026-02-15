# Terraform Outputs
# 작업: 07_alert_system.md (Phase 1)
# 용도: Apps Layer 및 외부에서 참조할 값 출력
# 참고: EKS 관련 outputs는 06-eks.tf에 정의됨

# ============================================
# Data Pipeline Outputs
# ============================================
output "kinesis_stream_name" {
  description = "Kinesis Data Stream name"
  value       = aws_kinesis_stream.main.name
}

output "kinesis_stream_arn" {
  description = "Kinesis Data Stream ARN"
  value       = aws_kinesis_stream.main.arn
}

output "firehose_delivery_stream_name" {
  description = "Kinesis Firehose Delivery Stream name"
  value       = aws_kinesis_firehose_delivery_stream.main.name
}

output "s3_bucket_name" {
  description = "S3 Data Lake bucket name"
  value       = aws_s3_bucket.data_lake.id
}

output "s3_bucket_arn" {
  description = "S3 Data Lake bucket ARN"
  value       = aws_s3_bucket.data_lake.arn
}

output "glue_database_name" {
  description = "Glue Catalog database name"
  value       = aws_glue_catalog_database.main.name
}

output "glue_table_name" {
  description = "Glue Catalog table name"
  value       = aws_glue_catalog_table.raw.name
}

# TODO: Athena Workgroup은 아직 생성되지 않음 (Task 08 이후 추가 예정)
# output "athena_workgroup_name" {
#   description = "Athena Workgroup name"
#   value       = aws_athena_workgroup.main.name
# }

# ============================================
# IAM Role Outputs (for IRSA)
# ============================================
# TODO: Airflow, Slack Bot Role은 Apps Layer 배포 시 추가 예정 (Task 11, 15)
# output "airflow_role_arn" {
#   description = "IAM Role ARN for Airflow ServiceAccount"
#   value       = aws_iam_role.airflow.arn
# }

# output "slack_bot_role_arn" {
#   description = "IAM Role ARN for Slack Bot ServiceAccount"
#   value       = aws_iam_role.slack_bot.arn
# }

output "firehose_role_arn" {
  description = "IAM Role ARN for Kinesis Firehose"
  value       = aws_iam_role.firehose.arn
}

output "eks_cluster_role_arn" {
  description = "IAM Role ARN for EKS Cluster"
  value       = aws_iam_role.eks_cluster.arn
}

output "eks_node_role_arn" {
  description = "IAM Role ARN for EKS Node Group"
  value       = aws_iam_role.eks_node.arn
}

# ============================================
# Alert System Outputs
# ============================================
output "sns_topic_arn" {
  description = "SNS Topic ARN for alerts"
  value       = aws_sns_topic.capa_alerts.arn
}

output "sns_topic_name" {
  description = "SNS Topic name"
  value       = aws_sns_topic.capa_alerts.name
}

output "cloudwatch_alarm_kinesis_low_traffic" {
  description = "CloudWatch Alarm for Kinesis low traffic"
  value       = aws_cloudwatch_metric_alarm.kinesis_low_traffic.arn
}

output "cloudwatch_alarm_kinesis_high_iterator_age" {
  description = "CloudWatch Alarm for Kinesis high iterator age"
  value       = aws_cloudwatch_metric_alarm.kinesis_high_iterator_age.arn
}

output "cloudwatch_alarm_firehose_delivery_failure" {
  description = "CloudWatch Alarm for Firehose delivery failure"
  value       = aws_cloudwatch_metric_alarm.firehose_delivery_failure.arn
}

output "cloudwatch_alarm_eks_node_cpu_high" {
  description = "CloudWatch Alarm for EKS Node CPU high"
  value       = aws_cloudwatch_metric_alarm.eks_node_cpu_high.arn
}

# ============================================
# Airflow Outputs
# ============================================
output "airflow_webserver_url" {
  description = "Airflow Webserver URL (LoadBalancer)"
  value       = "http://${data.kubernetes_service.airflow_webserver.status.0.load_balancer.0.ingress.0.hostname}:8080"
}


output "airflow_admin_account" {
  description = "Airflow Admin Credentials (Default)"
  value       = "admin / admin"
}

# ============================================
# AI Application Endpoints (Internal)
# ============================================

output "vanna_api_internal_url" {
  description = "Internal URL for Vanna AI API"
  value       = "http://vanna-api.vanna.svc.cluster.local:8000"
}

output "report_generator_internal_url" {
  description = "Internal URL for Report Generator"
  value       = "http://report-generator.report.svc.cluster.local:8000"
}

output "slack_bot_internal_url" {
  description = "Internal URL for Slack Bot (Health Check)"
  value       = "http://slack-bot.slack-bot.svc.cluster.local:3000"
}

output "chromadb_internal_url" {
  description = "Internal URL for ChromaDB"
  value       = "http://chromadb.chromadb.svc.cluster.local:8000"
}

# ============================================
# AI Application ECR Repositories
# ============================================

output "ecr_vanna_api_url" {
  description = "ECR Repository URL for Vanna AI API"
  value       = aws_ecr_repository.vanna_api.repository_url
}

output "ecr_report_generator_url" {
  description = "ECR Repository URL for Report Generator"
  value       = aws_ecr_repository.report_generator.repository_url
}

output "ecr_slack_bot_url" {
  description = "ECR Repository URL for Slack Bot"
  value       = aws_ecr_repository.slack_bot.repository_url
}

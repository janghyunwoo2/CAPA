# IAM 모듈 출력

output "firehose_role_arn" {
  value       = aws_iam_role.firehose_role.arn
  description = "Firehose 역할 ARN"
}

output "firehose_role_name" {
  value       = aws_iam_role.firehose_role.name
  description = "Firehose 역할 이름"
}

output "airflow_role_arn" {
  value       = aws_iam_role.airflow_role.arn
  description = "Airflow 역할 ARN"
}

output "airflow_role_name" {
  value       = aws_iam_role.airflow_role.name
  description = "Airflow 역할 이름"
}

# Glue 모듈 출력

output "database_name" {
  value       = aws_glue_catalog_database.ad_logs.name
  description = "Glue 데이터베이스 이름"
}

output "database_arn" {
  value       = aws_glue_catalog_database.ad_logs.arn
  description = "Glue 데이터베이스 ARN"
}

output "impression_table_name" {
  value       = aws_glue_catalog_table.impression.name
  description = "Impression 테이블 이름"
}

output "click_table_name" {
  value       = aws_glue_catalog_table.click.name
  description = "Click 테이블 이름"
}

output "conversion_table_name" {
  value       = aws_glue_catalog_table.conversion.name
  description = "Conversion 테이블 이름"
}

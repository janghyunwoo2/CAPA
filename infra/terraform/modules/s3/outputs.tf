# S3 모듈 출력

output "bucket_name" {
  value       = aws_s3_bucket.capa_logs.id
  description = "S3 버킷 이름"
}

output "bucket_arn" {
  value       = aws_s3_bucket.capa_logs.arn
  description = "S3 버킷 ARN"
}

output "bucket_region" {
  value       = aws_s3_bucket.capa_logs.region
  description = "S3 버킷 리전"
}

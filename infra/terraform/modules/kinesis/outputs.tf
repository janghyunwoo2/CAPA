# Kinesis 모듈 출력

output "stream_arn" {
  value = aws_kinesis_stream.ad_logs_stream.arn
}

output "stream_name" {
  value = aws_kinesis_stream.ad_logs_stream.name
}

output "firehose_name" {
  value = aws_kinesis_firehose_delivery_stream.ad_logs_firehose.name
}

output "firehose_arn" {
  value = aws_kinesis_firehose_delivery_stream.ad_logs_firehose.arn
}

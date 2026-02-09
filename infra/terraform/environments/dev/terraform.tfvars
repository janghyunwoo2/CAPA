# 개발 환경 Terraform 변수

aws_region    = "ap-northeast-2"
aws_account_id = "123456789012"  # 실제 계정 ID로 변경
environment    = "dev"

kinesis_retention_hours      = 24
firehose_buffer_size_mb      = 64
firehose_buffer_interval_seconds = 60

enable_logging = true

tags = {
  Project     = "CAPA"
  Environment = "dev"
  Team        = "DataEngineering"
  CostCenter  = "Engineering"
}

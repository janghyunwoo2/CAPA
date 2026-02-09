# 프로덕션 환경 Terraform 변수

aws_region    = "ap-northeast-2"
aws_account_id = "987654321098"  # 실제 계정 ID로 변경
environment    = "prod"

kinesis_retention_period     = 24
firehose_buffer_size_mb      = 128
firehose_buffer_interval_seconds = 300

enable_logging = true

tags = {
  Project     = "CAPA"
  Environment = "prod"
  Team        = "DataEngineering"
  CostCenter  = "ProductionOps"
}

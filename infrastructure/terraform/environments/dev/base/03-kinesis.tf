# Kinesis Data Stream and Firehose
# 작업: 05_data_pipeline_기본.md (Phase 1)
# 용도: 로그 수집 및 S3 전송

# ============================================
# 1. Kinesis Data Stream
# ============================================
resource "aws_kinesis_stream" "main" {
  name             = "${var.project_name}-stream"
  shard_count      = 1  # MVP: 1 shard (1MB/s 쓰기)
  retention_period = 24 # 24시간 보관

  shard_level_metrics = [
    "IncomingBytes",
    "IncomingRecords",
    "OutgoingBytes",
    "OutgoingRecords"
  ]

  stream_mode_details {
    stream_mode = "PROVISIONED"
  }

  tags = {
    Name = "${var.project_name}-kinesis-stream"
  }
}

# ============================================
# 2. Kinesis Firehose Delivery Stream
# ============================================
resource "aws_kinesis_firehose_delivery_stream" "main" {
  name        = "${var.project_name}-firehose"
  destination = "extended_s3"

  kinesis_source_configuration {
    kinesis_stream_arn = aws_kinesis_stream.main.arn
    role_arn           = aws_iam_role.firehose.arn
  }

  extended_s3_configuration {
    role_arn            = aws_iam_role.firehose.arn
    bucket_arn          = aws_s3_bucket.data_lake.arn
    prefix              = "raw/year=!{timestamp:yyyy}/month=!{timestamp:MM}/day=!{timestamp:dd}/"
    error_output_prefix = "errors/!{firehose:error-output-type}/"
    buffering_size      = 64 # Parquet 변환 시 최소 64MB 필수
    buffering_interval  = 60 # 60초 버퍼
    compression_format  = "UNCOMPRESSED"

    # Parquet 변환
    data_format_conversion_configuration {
      input_format_configuration {
        deserializer {
          open_x_json_ser_de {}
        }
      }

      output_format_configuration {
        serializer {
          parquet_ser_de {}
        }
      }

      schema_configuration {
        database_name = aws_glue_catalog_database.main.name
        table_name    = aws_glue_catalog_table.raw.name
        role_arn      = aws_iam_role.firehose.arn
      }
    }
  }
}

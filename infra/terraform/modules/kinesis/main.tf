# Kinesis Data Stream 모듈

resource "aws_kinesis_stream" "ad_logs_stream" {
  name             = var.stream_name
  retention_period = var.retention_period
  stream_mode_details {
    stream_mode = "ON_DEMAND"  # 온디맨드 모드 (자동 스케일링)
  }

  tags = {
    Name        = var.stream_name
    Environment = var.environment
  }
}

# Kinesis Firehose - Parquet 변환 + S3 저장
resource "aws_kinesis_firehose_delivery_stream" "ad_logs_firehose" {
  name            = "capa-firehose-${var.environment}"
  kinesis_source_configuration {
    kinesis_stream_arn = aws_kinesis_stream.ad_logs_stream.arn
    role_arn           = var.firehose_role_arn
  }

  extended_s3_destination_configuration {
    role_arn           = var.firehose_role_arn
    bucket_arn         = var.s3_bucket_arn
    prefix             = "event_type=!{partitionKeyFromQuery:event_type}/year=!{timestamp:yyyy}/month=!{timestamp:MM}/day=!{timestamp:dd}/hour=!{timestamp:HH}/"
    error_output_prefix = "error/!{firehose:error-output-type}/year=!{timestamp:yyyy}/month=!{timestamp:MM}/day=!{timestamp:dd}/!{timestamp:HH}:!{timestamp:mm}/"
    
    buffer_size     = var.buffer_size_mb
    buffer_interval = var.buffer_interval_seconds

    cloudwatch_logging_options {
      enabled         = true
      log_group_name  = aws_cloudwatch_log_group.firehose_logs.name
      log_stream_name = aws_cloudwatch_log_stream.firehose_stream.name
    }

    # Parquet 변환 설정
    data_format_conversion_configuration {
      input_format_configuration {
        deserializer {
          open_x_serialize_de_serializer {}
        }
      }

      output_format_configuration {
        serializer {
          parquet_ser_de {}
        }
      }

      schema_configuration {
        database_name = var.glue_database_name
        table_name    = "ad_logs"
        role_arn      = var.firehose_role_arn
        region        = data.aws_region.current.name
      }

      enabled = true
    }

    dynamic_partitioning_configuration {
      enabled = true
    }

    processing_configuration {
      enabled = true

      processors {
        type = "AppendDelimiterToRecord"
      }
    }
  }

  depends_on = [aws_kinesis_stream.ad_logs_stream]
}

# CloudWatch 로그 그룹
resource "aws_cloudwatch_log_group" "firehose_logs" {
  name              = "/aws/kinesisfirehose/capa-${var.environment}"
  retention_in_days = 7
}

resource "aws_cloudwatch_log_stream" "firehose_stream" {
  name           = "S3Delivery"
  log_group_name = aws_cloudwatch_log_group.firehose_logs.name
}

# 현재 리전 가져오기
data "aws_region" "current" {}

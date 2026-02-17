# Glue Catalog (메타데이터)
# 작업: 05_data_pipeline_기본.md (Phase 1)
# 용도: Athena 쿼리를 위한 스키마 정의

# ============================================
# 1. Glue Database
# ============================================
resource "aws_glue_catalog_database" "main" {
  name = "${var.project_name}_db"
}

# ============================================
# 2. Glue Table (ad_events_raw)
# ============================================
# ============================================
# 2. Glue Table (ad_events_raw) - DEPRECATED
# Legacy: 정적 스키마 정의 (초기 버전)
# ============================================
# resource "aws_glue_catalog_table" "raw" {
#   name          = "ad_events_raw"
#   database_name = aws_glue_catalog_database.main.name
#
#   table_type = "EXTERNAL_TABLE"
#
#   parameters = {
#     "classification" = "parquet"
#     "EXTERNAL"       = "TRUE"
#   }
#
#   storage_descriptor {
#     location      = "s3://${aws_s3_bucket.data_lake.bucket}/raw/"
#     input_format  = "org.apache.hadoop.hive.ql.io.parquet.MapredParquetInputFormat"
#     output_format = "org.apache.hadoop.hive.ql.io.parquet.MapredParquetOutputFormat"
#
#     ser_de_info {
#       serialization_library = "org.apache.hadoop.hive.ql.io.parquet.serde.ParquetHiveSerDe"
#     }
#
#     columns {
#       name = "event_id"
#       type = "string"
#     }
#
#     columns {
#       name    = "event_type"
#       type    = "string"
#       comment = "impression, click, conversion"
#     }
#
#     columns {
#       name = "timestamp"
#       type = "bigint"
#     }
#
#     columns {
#       name = "campaign_id"
#       type = "string"
#     }
#
#     columns {
#       name = "user_id"
#       type = "string"
#     }
#
#     columns {
#       name = "device_type"
#       type = "string"
#     }
#
#     columns {
#       name = "bid_price"
#       type = "double"
#     }
#   }
#
#   partition_keys {
#     name = "year"
#     type = "string"
#   }
#
#   partition_keys {
#     name = "month"
#     type = "string"
#   }
#
#   partition_keys {
#     name = "day"
#     type = "string"
#   }
# }

# ============================================
# 3. Glue Crawler (New)
# 용도: S3 데이터 스키마 및 파티션 자동 인식
# ============================================

# 3.1 IAM Role for Crawler
resource "aws_iam_role" "glue_crawler" {
  name = "${var.project_name}-glue-crawler-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "glue.amazonaws.com"
        }
      }
    ]
  })
}

# 3.2 IAM Policy Attachment (AWSManaged)
# AWSGlueServiceRole: Glue 실행에 필요한 기본 권한
resource "aws_iam_role_policy_attachment" "glue_service" {
  role       = aws_iam_role.glue_crawler.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSGlueServiceRole"
}

# 3.3 IAM Policy (S3 Access)
# S3 버킷 읽기 권한
resource "aws_iam_role_policy" "crawler_s3" {
  name = "${var.project_name}-crawler-s3-policy"
  role = aws_iam_role.glue_crawler.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "s3:GetObject",
          "s3:PutObject",
          "s3:ListBucket" # 필수
        ]
        Resource = [
          aws_s3_bucket.data_lake.arn,
          "${aws_s3_bucket.data_lake.arn}/*"
        ]
      }
    ]
  })
}

# 3.4 Glue Crawler
resource "aws_glue_crawler" "main" {
  name          = "${var.project_name}-log-crawler"
  database_name = aws_glue_catalog_database.main.name
  role          = aws_iam_role.glue_crawler.arn

  s3_target {
    path = "s3://${aws_s3_bucket.data_lake.bucket}/raw/"
  }

  table_prefix = "ad_events_"

  # 스키마 변경 감지 설정
  schema_change_policy {
    update_behavior = "UPDATE_IN_DATABASE"
    delete_behavior = "DEPRECATE_IN_DATABASE"
  }

  # 태그 설정
  tags = {
    Name = "${var.project_name}-crawler"
  }
}

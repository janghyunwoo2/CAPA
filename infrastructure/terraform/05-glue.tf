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
resource "aws_glue_catalog_table" "raw" {
  name          = "ad_events_raw"
  database_name = aws_glue_catalog_database.main.name

  table_type = "EXTERNAL_TABLE"

  parameters = {
    "classification" = "parquet"
    "EXTERNAL"       = "TRUE"
  }

  storage_descriptor {
    location      = "s3://${aws_s3_bucket.data_lake.bucket}/raw/"
    input_format  = "org.apache.hadoop.hive.ql.io.parquet.MapredParquetInputFormat"
    output_format = "org.apache.hadoop.hive.ql.io.parquet.MapredParquetOutputFormat"

    ser_de_info {
      serialization_library = "org.apache.hadoop.hive.ql.io.parquet.serde.ParquetHiveSerDe"
    }

    columns {
      name = "event_id"
      type = "string"
    }

    columns {
      name    = "event_type"
      type    = "string"
      comment = "impression, click, conversion"
    }

    columns {
      name = "timestamp"
      type = "bigint"
    }

    columns {
      name = "campaign_id"
      type = "string"
    }

    columns {
      name = "user_id"
      type = "string"
    }

    columns {
      name = "device_type"
      type = "string"
    }

    columns {
      name = "bid_price"
      type = "double"
    }
  }

  partition_keys {
    name = "year"
    type = "string"
  }

  partition_keys {
    name = "month"
    type = "string"
  }

  partition_keys {
    name = "day"
    type = "string"
  }
}

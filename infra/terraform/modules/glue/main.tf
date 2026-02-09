# Glue Database
resource "aws_glue_catalog_database" "ad_logs" {
  name        = "capa_${var.environment}"
  description = "CAPA 광고 로그 데이터베이스"

  tags = {
    Name        = "capa_${var.environment}"
    Environment = var.environment
  }
}

# Impression 이벤트 테이블
resource "aws_glue_catalog_table" "impression" {
  name          = "impression"
  database_name = aws_glue_catalog_database.ad_logs.name
  table_type    = "EXTERNAL_TABLE"
  parameters = {
    EXTERNAL_TABLE_DEF = "YES"
    classification     = "parquet"
  }

  storage_descriptor {
    location      = "${var.s3_path}/event_type=impression/"
    input_format  = "org.apache.hadoop.hive.ql.io.parquet.MapredParquetInputFormat"
    output_format = "org.apache.hadoop.hive.ql.io.parquet.MapredParquetOutputFormat"

    ser_de_info {
      serialization_library = "org.apache.hadoop.hive.ql.io.parquet.serde.ParquetHiveSerDe"
    }

    columns {
      name = "event_type"
      type = "string"
    }
    columns {
      name = "event_id"
      type = "string"
    }
    columns {
      name = "timestamp"
      type = "string"
    }
    columns {
      name = "user_id"
      type = "string"
    }
    columns {
      name = "ad_id"
      type = "string"
    }
    columns {
      name = "campaign_id"
      type = "string"
    }
    columns {
      name = "shop_id"
      type = "string"
    }
    columns {
      name = "placement"
      type = "string"
    }
    columns {
      name = "platform"
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
  partition_keys {
    name = "hour"
    type = "string"
  }

  depends_on = [aws_glue_catalog_database.ad_logs]
}

# Click 이벤트 테이블
resource "aws_glue_catalog_table" "click" {
  name          = "click"
  database_name = aws_glue_catalog_database.ad_logs.name
  table_type    = "EXTERNAL_TABLE"
  parameters = {
    EXTERNAL_TABLE_DEF = "YES"
    classification     = "parquet"
  }

  storage_descriptor {
    location      = "${var.s3_path}/event_type=click/"
    input_format  = "org.apache.hadoop.hive.ql.io.parquet.MapredParquetInputFormat"
    output_format = "org.apache.hadoop.hive.ql.io.parquet.MapredParquetOutputFormat"

    ser_de_info {
      serialization_library = "org.apache.hadoop.hive.ql.io.parquet.serde.ParquetHiveSerDe"
    }

    columns {
      name = "event_type"
      type = "string"
    }
    columns {
      name = "event_id"
      type = "string"
    }
    columns {
      name = "timestamp"
      type = "string"
    }
    columns {
      name = "user_id"
      type = "string"
    }
    columns {
      name = "ad_id"
      type = "string"
    }
    columns {
      name = "impression_id"
      type = "string"
    }
    columns {
      name = "shop_id"
      type = "string"
    }
    columns {
      name = "clickspot_x"
      type = "int"
    }
    columns {
      name = "clickspot_y"
      type = "int"
    }
    columns {
      name = "cpc_cost"
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
  partition_keys {
    name = "hour"
    type = "string"
  }

  depends_on = [aws_glue_catalog_database.ad_logs]
}

# Conversion 이벤트 테이블
resource "aws_glue_catalog_table" "conversion" {
  name          = "conversion"
  database_name = aws_glue_catalog_database.ad_logs.name
  table_type    = "EXTERNAL_TABLE"
  parameters = {
    EXTERNAL_TABLE_DEF = "YES"
    classification     = "parquet"
  }

  storage_descriptor {
    location      = "${var.s3_path}/event_type=conversion/"
    input_format  = "org.apache.hadoop.hive.ql.io.parquet.MapredParquetInputFormat"
    output_format = "org.apache.hadoop.hive.ql.io.parquet.MapredParquetOutputFormat"

    ser_de_info {
      serialization_library = "org.apache.hadoop.hive.ql.io.parquet.serde.ParquetHiveSerDe"
    }

    columns {
      name = "event_type"
      type = "string"
    }
    columns {
      name = "event_id"
      type = "string"
    }
    columns {
      name = "timestamp"
      type = "string"
    }
    columns {
      name = "user_id"
      type = "string"
    }
    columns {
      name = "shop_id"
      type = "string"
    }
    columns {
      name = "click_id"
      type = "string"
    }
    columns {
      name = "ad_id"
      type = "string"
    }
    columns {
      name = "action_type"
      type = "string"
    }
    columns {
      name = "item_count"
      type = "int"
    }
    columns {
      name = "total_amount"
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
  partition_keys {
    name = "hour"
    type = "string"
  }

  depends_on = [aws_glue_catalog_database.ad_logs]
}

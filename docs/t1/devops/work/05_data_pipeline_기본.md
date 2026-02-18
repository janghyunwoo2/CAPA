# 작업 05: Kinesis + S3 + Glue 데이터 파이프라인 기본

> [!IMPORTANT]
> **2026-02-17 업데이트**: 스키마 관리 방식이 **Glue Crawler(`capa-log-crawler`)**를 통한 자동 인식 방식으로 전환되었습니다. 
> `infrastructure/terraform/05-glue.tf`의 정적 테이블 정의는 주석 처리되었으며, 대안으로 Crawler가 제공됩니다.

> **Phase**: 1 (Terraform Base Layer)  
> **담당**: Infra Architect  
> **예상 소요**: 10분  
> **선행 작업**: 04_iam_roles.md

---

## 1. 목표

실시간 로그를 수집하는 Kinesis → S3 (Parquet) → Glue Catalog 파이프라인을 구축합니다.

---

## 2. 파이프라인 구조

```
Log Generator → Kinesis Stream → Kinesis Firehose → S3 (Parquet) → Glue Catalog → Athena
```

---

## 3. 실행 단계

### 3.1 Kinesis Data Stream 생성

`infrastructure/terraform/environments/dev/base/03-kinesis.tf`:

```hcl
resource "aws_kinesis_stream" "main" {
  name             = "${var.project_name}-stream"
  shard_count      = 1  # MVP: 1 shard (1MB/s 쓰기)
  retention_period = 24  # 24시간 보관
  
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
```

### 3.2 S3 Bucket 생성

`infrastructure/terraform/environments/dev/base/04-s3.tf`:

```hcl
resource "aws_s3_bucket" "data_lake" {
  bucket = "${var.project_name}-data-lake-${data.aws_caller_identity.current.account_id}"
  
  tags = {
    Name = "${var.project_name}-data-lake"
  }
}

resource "aws_s3_bucket_versioning" "data_lake" {
  bucket = aws_s3_bucket.data_lake.id
  
  versioning_configuration {
    status = "Enabled"
  }
}

# Lifecycle Policy (비용 절감)
resource "aws_s3_bucket_lifecycle_configuration" "data_lake" {
  bucket = aws_s3_bucket.data_lake.id
  
  rule {
    id     = "delete-old-logs"
    status = "Enabled"
    
    expiration {
      days = 90  # 90일 후 삭제
    }
  }
}

data "aws_caller_identity" "current" {}
```

### 3.3 Kinesis Firehose 생성

`infrastructure/terraform/environments/dev/base/03-kinesis.tf` (추가):

```hcl
resource "aws_kinesis_firehose_delivery_stream" "main" {
  name        = "${var.project_name}-firehose"
  destination = "extended_s3"
  
  kinesis_source_configuration {
    kinesis_stream_arn = aws_kinesis_stream.main.arn
    role_arn           = aws_iam_role.firehose.arn
  }
  
  extended_s3_configuration {
    role_arn           = aws_iam_role.firehose.arn
    bucket_arn         = aws_s3_bucket.data_lake.arn
    prefix             = "raw/year=!{timestamp:yyyy}/month=!{timestamp:MM}/day=!{timestamp:dd}/"
    error_output_prefix = "errors/!{firehose:error-output-type}/"
    buffering_size     = 5   # 5MB 버퍼
    buffering_interval = 60  # 60초 버퍼
    compression_format = "UNCOMPRESSED"
    
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
```

### 3.4 Glue Catalog 생성

`infrastructure/terraform/environments/dev/base/05-glue.tf`:

```hcl
resource "aws_glue_catalog_database" "main" {
  name = "${var.project_name}_db"
}

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
      name = "event_type"
      type = "string"
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
```

### 3.5 Terraform 실행

```powershell
cd infrastructure\terraform\environments\dev\base

# Plan 확인
terraform plan

# 적용
terraform apply

# 예상 출력:
# aws_kinesis_stream.main: Creating...
# aws_s3_bucket.data_lake: Creating...
# aws_glue_catalog_database.main: Creating...
# ... (완료까지 약 3분)
# Apply complete! Resources: 8 added, 0 changed, 0 destroyed.
```

---

## 4. 검증 방법

### 4.1 Kinesis Stream 확인

```powershell
aws kinesis describe-stream --stream-name capa-stream

# 예상 출력:
# StreamStatus: "ACTIVE"
# ShardCount: 1
```

### 4.2 S3 Bucket 확인

```powershell
aws s3 ls | Select-String "capa-data-lake"

# 예상 출력: capa-data-lake-123456789012
```

### 4.3 Glue Catalog 확인

```powershell
aws glue get-database --name capa_db
aws glue get-table --database-name capa_db --name ad_events_raw

# 예상 출력: Table 정보 출력
```

### 4.4 Firehose 확인

```powershell
aws firehose describe-delivery-stream --delivery-stream-name capa-firehose

# 예상 출력:
# DeliveryStreamStatus: "ACTIVE"
```

### 4.5 성공 기준

- [ ] Kinesis Stream `capa-stream` ACTIVE
- [ ] S3 Bucket `capa-data-lake-*` 생성됨
- [ ] Glue Database `capa_db` 생성됨
- [ ] Glue Table `ad_events_raw` 생성됨
- [ ] Firehose `capa-firehose` ACTIVE
- [ ] `terraform apply` 오류 없이 완료

---

## 5. 실패 시 대응

| 오류 | 원인 | 해결 방법 |
|------|------|-----------|
| `ResourceInUseException` | 이름 중복 | 기존 리소스 삭제 or 이름 변경 |
| `InvalidParameterException` | Glue 스키마 오류 | Column 타입 확인 |
| `AccessDenied (Firehose)` | IAM Role 권한 부족 | 04_iam_roles.md 확인 |

---

## 6. 다음 단계

✅ **데이터 파이프라인 기본 구축 완료** → `06_eks_cluster.md`로 이동

> ⚠️ **Note**: 실제 데이터 테스트는 `07_log_generator.md`에서 진행

---

## 7. 결과 기록

**실행자**: _______________  
**실행 일시**: _______________  
**결과**: ⬜ 성공 / ⬜ 실패  

**생성된 리소스**:
- [ ] Kinesis Stream: capa-stream
- [ ] S3 Bucket: capa-data-lake-_______________
- [ ] Glue DB: capa_db
- [ ] Glue Table: ad_events_raw
- [ ] Firehose: capa-firehose

**메모**:
```
(실행 로그, 발생한 이슈 기록)
```

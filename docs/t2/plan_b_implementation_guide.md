# 구조 B 구현 가이드: Stream 1개 + Firehose 동적 파티셔닝

## 목표 아키텍처

```
Generator → kinesis.put_record() → Stream (1개, 기존 유지)
                                       │
                                       ├→ Firehose (동적 파티셔닝)
                                       │       ↓
                                       │   S3/raw/event_type=impression/year=.../
                                       │   S3/raw/event_type=click/year=.../
                                       │   S3/raw/event_type=conversion/year=.../
                                       │       ↓
                                       │   Crawler 3개 → Athena Table 3개
                                       │
                                       ├→ (미래) Lambda: 이상 탐지
                                       └→ (미래) Lambda: 실시간 대시보드
```

---

## 변경 요약

| 구분 | 파일 | 변경 내용 |
|------|------|----------|
| Terraform | `03-kinesis.tf` | Firehose에 동적 파티셔닝 설정 추가 |
| Terraform | `05-glue.tf` | Crawler 3개 추가 (impression, click, conversion) |
| Python (롤백) | `kinesis_sender.py` | FirehoseSender → KinesisSender로 롤백 (Stream에 전송) |
| Python (롤백) | `main.py` | Firehose 설정 → Kinesis Stream 설정으로 롤백 |
| Python (신규) | `generator.py` | 3개 generate 메서드에 `event_type` 필드 추가 |
| AWS 콘솔 | Firehose 3개 | 수동 생성한 capa-fh-imp/clk/cvs-00 삭제 |
| AWS 콘솔 | Glue Table | `ad_events_raw` 스키마에 `event_type` 포함 확인 |
| AWS 콘솔 | S3 기존 데이터 | 파티셔닝 전 데이터 정리/이동 |

---

## Step 1: Terraform - Firehose 동적 파티셔닝 설정

### 1.1 `03-kinesis.tf` 수정

**변경 전:**
```hcl
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
    buffering_size      = 64
    buffering_interval  = 60
    compression_format  = "UNCOMPRESSED"

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
        table_name    = "ad_events_raw"
        role_arn      = aws_iam_role.firehose.arn
      }
    }
  }
}
```

**변경 후:**
```hcl
resource "aws_kinesis_firehose_delivery_stream" "main" {
  name        = "${var.project_name}-firehose"
  destination = "extended_s3"

  # ✅ Kinesis Stream 소스 유지 (다중 소비자용)
  kinesis_source_configuration {
    kinesis_stream_arn = aws_kinesis_stream.main.arn
    role_arn           = aws_iam_role.firehose.arn
  }

  extended_s3_configuration {
    role_arn            = aws_iam_role.firehose.arn
    bucket_arn          = aws_s3_bucket.data_lake.arn

    # ✅ 변경: 동적 파티셔닝 prefix (event_type별 폴더 분리)
    prefix              = "raw/event_type=!{partitionKeyFromQuery:event_type}/year=!{timestamp:yyyy}/month=!{timestamp:MM}/day=!{timestamp:dd}/"
    error_output_prefix = "errors/!{firehose:error-output-type}/"

    buffering_size      = 64
    buffering_interval  = 60
    compression_format  = "UNCOMPRESSED"

    # ✅ 추가: 동적 파티셔닝 활성화
    dynamic_partitioning_configuration {
      enabled = true
    }

    # ✅ 추가: 동적 파티셔닝 프로세서 (JSON에서 event_type 추출)
    processing_configuration {
      enabled = true

      processors {
        type = "MetadataExtraction"

        parameters {
          parameter_name  = "JsonParsingEngine"
          parameter_value = "JQ-1.6"
        }

        parameters {
          parameter_name  = "MetadataExtractionQuery"
          parameter_value = "{event_type: .event_type}"
        }
      }
    }

    # Parquet 변환 (기존 유지)
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
        table_name    = "ad_events_raw"
        role_arn      = aws_iam_role.firehose.arn
      }
    }
  }
}
```

**변경 포인트 3가지:**
1. `prefix`: `event_type=!{partitionKeyFromQuery:event_type}/` 추가
2. `dynamic_partitioning_configuration` 블록 추가
3. `processing_configuration` 블록 추가 (JQ로 event_type 추출)

---

### 1.2 주의: Parquet 변환 + 동적 파티셔닝 병행 시

동적 파티셔닝과 Parquet 변환을 동시에 사용하려면:
- **Firehose가 JSON 원본에서 event_type을 추출** → 폴더 분기
- **그 후 Parquet으로 변환** → S3 저장

이때 `event_type` 필드를 추출하려면 **데이터가 JSON 형태**여야 합니다.
현재 Generator가 JSON으로 전송하고 있으므로 문제 없습니다.

⚠️ **만약 동적 파티셔닝 + Parquet 변환이 충돌하는 경우:**
- Parquet 변환을 비활성화하고, JSON 그대로 S3에 저장
- 이후 Glue ETL Job 또는 Athena CTAS로 Parquet 변환

---

## Step 2: Terraform - Glue Crawler 3개 추가

### 2.1 `05-glue.tf`에 추가

기존 Crawler 1개(통합)를 **3개로 분리**합니다.

**기존 Crawler 주석 처리 또는 삭제:**
```hcl
# 기존 통합 Crawler → 주석 처리
# resource "aws_glue_crawler" "main" { ... }
```

**새로운 Crawler 3개 추가:**
```hcl
# ============================================
# 4. Glue Crawler - 이벤트 타입별 3개
# 용도: S3 파티션별 Athena 테이블 자동 생성
# ============================================

# 4.1 Impression Crawler
resource "aws_glue_crawler" "impression" {
  name          = "${var.project_name}-impression-crawler"
  database_name = aws_glue_catalog_database.main.name
  role          = aws_iam_role.glue_crawler.arn

  s3_target {
    path = "s3://${aws_s3_bucket.data_lake.bucket}/raw/event_type=impression/"
  }

  table_prefix = "ad_"

  schema_change_policy {
    update_behavior = "UPDATE_IN_DATABASE"
    delete_behavior = "DEPRECATE_IN_DATABASE"
  }

  tags = {
    Name = "${var.project_name}-impression-crawler"
  }
}

# 4.2 Click Crawler
resource "aws_glue_crawler" "click" {
  name          = "${var.project_name}-click-crawler"
  database_name = aws_glue_catalog_database.main.name
  role          = aws_iam_role.glue_crawler.arn

  s3_target {
    path = "s3://${aws_s3_bucket.data_lake.bucket}/raw/event_type=click/"
  }

  table_prefix = "ad_"

  schema_change_policy {
    update_behavior = "UPDATE_IN_DATABASE"
    delete_behavior = "DEPRECATE_IN_DATABASE"
  }

  tags = {
    Name = "${var.project_name}-click-crawler"
  }
}

# 4.3 Conversion Crawler
resource "aws_glue_crawler" "conversion" {
  name          = "${var.project_name}-conversion-crawler"
  database_name = aws_glue_catalog_database.main.name
  role          = aws_iam_role.glue_crawler.arn

  s3_target {
    path = "s3://${aws_s3_bucket.data_lake.bucket}/raw/event_type=conversion/"
  }

  table_prefix = "ad_"

  schema_change_policy {
    update_behavior = "UPDATE_IN_DATABASE"
    delete_behavior = "DEPRECATE_IN_DATABASE"
  }

  tags = {
    Name = "${var.project_name}-conversion-crawler"
  }
}
```

**Crawler가 생성하는 Athena 테이블 이름:**
| Crawler | S3 경로 | 생성되는 테이블 이름 |
|---------|---------|-------------------|
| impression | `raw/event_type=impression/` | `ad_event_type_impression` (자동 명명) |
| click | `raw/event_type=click/` | `ad_event_type_click` |
| conversion | `raw/event_type=conversion/` | `ad_event_type_conversion` |

> ℹ️ 테이블 이름은 Crawler가 S3 폴더 구조를 기반으로 자동 생성합니다.
> `table_prefix = "ad_"` + 폴더명 조합으로 결정됩니다.

---

## Step 3: Python 코드 롤백 (Firehose → Kinesis Stream)

### 3.1 `kinesis_sender.py` 롤백

현재 `FirehoseSender` → 원래 `KinesisSender`로 롤백합니다.
Generator가 **Kinesis Stream에 `kinesis.put_record()`로 전송**하도록 복원합니다.

```python
"""
Kinesis Sender - AWS Kinesis Data Stream으로 로그 전송
구조 B: Generator → Stream → Firehose(동적 파티셔닝) → S3
"""

import json
import boto3
from typing import Dict, Optional
from botocore.exceptions import ClientError


class KinesisSender:
    """AWS Kinesis Data Stream으로 로그를 전송하는 클래스"""
    
    def __init__(
        self,
        stream_name: str,
        region: str = "ap-northeast-2",
        aws_access_key_id: Optional[str] = None,
        aws_secret_access_key: Optional[str] = None
    ):
        self.stream_name = stream_name
        self.region = region
        
        session_kwargs = {"region_name": region}
        if aws_access_key_id and aws_secret_access_key:
            session_kwargs["aws_access_key_id"] = aws_access_key_id
            session_kwargs["aws_secret_access_key"] = aws_secret_access_key
        
        try:
            self.client = boto3.client("kinesis", **session_kwargs)
            print(f"✅ Kinesis 클라이언트 생성 성공 (Stream: {stream_name}, Region: {region})", flush=True)
        except Exception as e:
            print(f"❌ Kinesis 클라이언트 생성 실패: {e}", flush=True)
            self.client = None
        
        self.success_count = 0
        self.error_count = 0
    
    def send(self, log: Dict) -> bool:
        if not self.client:
            print(json.dumps(log, ensure_ascii=False), flush=True)
            return False
        
        try:
            log_copy = log.copy()
            log_copy.pop('_internal', None)
            
            data = json.dumps(log_copy, ensure_ascii=False)
            
            response = self.client.put_record(
                StreamName=self.stream_name,
                Data=data + "\n",
                PartitionKey=log.get("user_id", "default")
            )
            
            self.success_count += 1
            
            event_type = "impression"
            if log.get("conversion_id"):
                event_type = "conversion"
            elif log.get("click_id"):
                event_type = "click"
                
            print(
                f"[OK] Sent: {event_type} - Shard: {response['ShardId']}",
                flush=True
            )
            return True
            
        except ClientError as e:
            self.error_count += 1
            error_code = e.response.get("Error", {}).get("Code", "Unknown")
            error_msg = e.response.get("Error", {}).get("Message", str(e))
            print(f"[ERROR] Kinesis 전송 실패 [{error_code}]: {error_msg}", flush=True)
            return False
            
        except Exception as e:
            self.error_count += 1
            print(f"[ERROR] Kinesis 전송 오류: {type(e).__name__}: {e}", flush=True)
            return False
    
    def get_stats(self) -> Dict[str, int]:
        return {
            "success": self.success_count,
            "error": self.error_count,
            "total": self.success_count + self.error_count
        }
```

### 3.2 `main.py` 롤백

```python
from kinesis_sender import KinesisSender  # FirehoseSender → KinesisSender

class Config:
    # Kinesis 설정 (Stream 1개)
    ENABLE_KINESIS = True
    KINESIS_STREAM_NAME = os.getenv("KINESIS_STREAM_NAME", "capa-stream")
    AWS_REGION = os.getenv("AWS_DEFAULT_REGION", "ap-northeast-2")
    
    # AWS 자격증명
    AWS_ACCESS_KEY_ID = os.getenv("AWS_ACCESS_KEY_ID")
    AWS_SECRET_ACCESS_KEY = os.getenv("AWS_SECRET_ACCESS_KEY")
    
    # 로그 생성 설정
    CTR_RATE = 0.10
    CVR_RATE = 0.20

# Sender 초기화 부분
sender = None
if Config.ENABLE_KINESIS:
    sender = KinesisSender(
        stream_name=Config.KINESIS_STREAM_NAME,
        region=Config.AWS_REGION,
        aws_access_key_id=Config.AWS_ACCESS_KEY_ID,
        aws_secret_access_key=Config.AWS_SECRET_ACCESS_KEY
    )
```

---

## Step 4: Generator에 event_type 필드 추가

⚠️ **중요**: Firehose 동적 파티셔닝이 JQ로 `event_type` 필드를 읽으려면, **모든 로그에 `event_type` 필드가 있어야** 합니다.

현재 Generator 코드를 확인하면:
- `generate_impression()` → `event_type` 필드 **없음** ❌
- `generate_click()` → `event_type` 필드 **없음** ❌  
- `generate_conversion()` → `event_type` 필드 **없음** ❌

각 로그에 `event_type` 필드를 추가해야 합니다:

```python
# generator.py 수정

def generate_impression(self) -> Dict:
    impression = {
        "event_type": "impression",       # ← 추가 필수!
        "event_id": str(uuid.uuid4()),
        # ... 나머지 동일 ...
    }

def generate_click(self, impression: Dict) -> Dict:
    click = {
        "event_type": "click",             # ← 추가 필수!
        "event_id": str(uuid.uuid4()),
        # ... 나머지 동일 ...
    }

def generate_conversion(self, click: Dict) -> Dict:
    conversion = {
        "event_type": "conversion",        # ← 추가 필수!
        "event_id": str(uuid.uuid4()),
        # ... 나머지 동일 ...
    }
```

---

## Step 5: 실행 순서

### 5.1 Terraform 적용
```bash
cd infrastructure/terraform
terraform plan    # 변경사항 확인
terraform apply   # 적용
```

### 5.2 Python 코드 롤백
```bash
# kinesis_sender.py 롤백
# main.py 롤백
# generator.py에 event_type 필드 추가
```

### 5.3 테스트 실행
```bash
python services/data_pipeline_t2/log_gen_t2/realtime/main.py
```

### 5.4 S3 확인
```
s3://capa-data-lake-xxxx/raw/
  ├── event_type=impression/
  │   └── year=2026/month=02/day=26/xxx.parquet
  ├── event_type=click/
  │   └── year=2026/month=02/day=26/xxx.parquet
  └── event_type=conversion/
      └── year=2026/month=02/day=26/xxx.parquet
```

### 5.5 Crawler 실행
```bash
# AWS CLI로 Crawler 실행
aws glue start-crawler --name capa-impression-crawler
aws glue start-crawler --name capa-click-crawler
aws glue start-crawler --name capa-conversion-crawler
```

### 5.6 Athena 테이블 확인
```sql
-- Athena에서 테이블 목록 확인
SHOW TABLES IN capa_db;

-- 각 테이블 쿼리
SELECT * FROM ad_event_type_impression LIMIT 10;
SELECT * FROM ad_event_type_click LIMIT 10;
SELECT * FROM ad_event_type_conversion LIMIT 10;
```

---

## AWS 콘솔 설정 체크리스트

Terraform 외에 **AWS 콘솔에서 직접 확인/설정해야 하는 항목**들입니다.

### 1. 기존 Firehose 3개 정리 (콘솔에서 수동 생성한 것)

이전에 AWS 콘솔에서 수동 생성한 3개 Firehose가 있습니다:
- `capa-fh-imp-00`
- `capa-fh-clk-00`
- `capa-fh-cvs-00`

> ⚠️ **Terraform 적용 전에 위 3개를 콘솔에서 삭제**해야 합니다.
> 삭제하지 않으면 Terraform이 관리하는 `capa-firehose`와 별도로 비용이 발생합니다.

**삭제 경로:** AWS Console → Amazon Data Firehose → Delivery streams → 선택 → Delete

### 2. Glue Table 스키마 확인 (`ad_events_raw`)

Firehose가 Parquet 변환 시 참조하는 `ad_events_raw` 테이블에 **모든 이벤트 타입의 필드 + `event_type` 필드**가 포함되어 있어야 합니다.

**확인 경로:** AWS Console → AWS Glue → Tables → `ad_events_raw`

현재 Crawler가 자동 생성한 스키마에 `event_type` 필드가 없을 수 있습니다.
이 경우 아래 방법 중 하나로 해결합니다:

#### 방법 A: Crawler 재실행으로 스키마 갱신
1. Generator에 `event_type` 필드 추가 후 로그를 몇 건 전송
2. Crawler 재실행 → 자동으로 `event_type` 컬럼 인식
3. Firehose가 갱신된 스키마로 Parquet 변환

#### 방법 B: Glue 콘솔에서 수동 컬럼 추가
1. AWS Console → Glue → Tables → `ad_events_raw` → Edit schema
2. `event_type` (string) 컬럼 추가
3. 저장

#### 방법 C: Terraform으로 정적 테이블 정의
`05-glue.tf`에서 주석 처리된 `aws_glue_catalog_table.raw`를 복원하고, 모든 필드가 포함된 통합 스키마를 정의합니다. (아래 "통합 Glue Table 스키마" 섹션 참조)

### 3. S3 기존 데이터 정리

동적 파티셔닝 적용 전에 S3에 쌓인 기존 데이터는 `event_type=` 파티션 없이 저장되어 있습니다.

```
# 기존 경로 (파티셔닝 전)
s3://capa-data-lake-xxx/raw/year=2026/month=02/day=25/xxx.parquet

# 새 경로 (파티셔닝 후)
s3://capa-data-lake-xxx/raw/event_type=impression/year=2026/month=02/day=26/xxx.parquet
```

**조치:**
- 기존 데이터가 많지 않으면 삭제 후 재생성
- 보존이 필요하면 `raw_legacy/` 등으로 이동

```bash
# 기존 데이터 이동 (선택)
aws s3 mv s3://capa-data-lake-xxx/raw/ s3://capa-data-lake-xxx/raw_legacy/ --recursive

# 또는 삭제
aws s3 rm s3://capa-data-lake-xxx/raw/ --recursive
```

### 4. Firehose IAM Role 권한 확인

동적 파티셔닝 활성화 시 Firehose IAM Role에 추가 권한이 필요할 수 있습니다.
기존 S3 PutObject 권한이 있으면 대부분 동작하지만, 아래를 확인하세요:

**확인 경로:** AWS Console → IAM → Roles → `capa-firehose-role` → Permissions

필수 권한:
```json
{
  "Effect": "Allow",
  "Action": [
    "s3:PutObject",
    "s3:PutObjectAcl",
    "s3:AbortMultipartUpload",
    "s3:GetBucketLocation",
    "s3:ListBucket",
    "s3:ListBucketMultipartUploads"
  ],
  "Resource": [
    "arn:aws:s3:::capa-data-lake-*",
    "arn:aws:s3:::capa-data-lake-*/*"
  ]
}
```

### 5. Kinesis Stream Enhanced Fan-Out (미래 확장용)

현재는 불필요하지만, 다중 소비자를 추가할 때 필요합니다.
Enhanced Fan-Out을 사용하려면:

**설정 경로:** AWS Console → Kinesis → Data Streams → `capa-stream` → Enhanced fan-out

```bash
# CLI로 소비자 등록 (미래에 Lambda 연결 시)
aws kinesis register-stream-consumer \
  --stream-arn arn:aws:kinesis:ap-northeast-2:ACCOUNT_ID:stream/capa-stream \
  --consumer-name capa-anomaly-detector
```

### 6. 통합 Glue Table 스키마 (Parquet 변환용)

Firehose가 참조하는 `ad_events_raw` 테이블은 **impression + click + conversion의 모든 필드를 통합**한 슈퍼셋이어야 합니다. 아래는 Generator의 실제 필드를 기반으로 한 통합 스키마입니다:

| # | 컬럼명 | 타입 | impression | click | conversion | 설명 |
|---|--------|------|:---:|:---:|:---:|------|
| 1 | `event_type` | string | ✅ | ✅ | ✅ | **신규 추가** - 동적 파티셔닝 키 |
| 2 | `event_id` | string | ✅ | ✅ | ✅ | UUID |
| 3 | `timestamp` | bigint | ✅ | ✅ | ✅ | epoch ms |
| 4 | `impression_id` | string | ✅ | ✅ | ✅ | |
| 5 | `user_id` | string | ✅ | ✅ | ✅ | |
| 6 | `ad_id` | string | ✅ | ✅ | ✅ | |
| 7 | `campaign_id` | string | ✅ | ✅ | ✅ | |
| 8 | `advertiser_id` | string | ✅ | ✅ | ✅ | |
| 9 | `platform` | string | ✅ | ✅ | | |
| 10 | `device_type` | string | ✅ | ✅ | | |
| 11 | `os` | string | ✅ | | | |
| 12 | `delivery_region` | string | ✅ | | ✅ | |
| 13 | `user_lat` | double | ✅ | | | |
| 14 | `user_long` | double | ✅ | | | |
| 15 | `store_id` | string | ✅ | | ✅ | |
| 16 | `food_category` | string | ✅ | | | |
| 17 | `ad_position` | string | ✅ | | | |
| 18 | `ad_format` | string | ✅ | | | |
| 19 | `user_agent` | string | ✅ | | | |
| 20 | `ip_address` | string | ✅ | | | |
| 21 | `session_id` | string | ✅ | | | |
| 22 | `keyword` | string | ✅ | | | |
| 23 | `cost_per_impression` | double | ✅ | | | |
| 24 | `click_id` | string | | ✅ | ✅ | |
| 25 | `click_position_x` | int | | ✅ | | |
| 26 | `click_position_y` | int | | ✅ | | |
| 27 | `landing_page_url` | string | | ✅ | | |
| 28 | `cost_per_click` | double | | ✅ | | |
| 29 | `conversion_id` | string | | | ✅ | |
| 30 | `conversion_type` | string | | | ✅ | |
| 31 | `conversion_value` | double | | | ✅ | |
| 32 | `product_id` | string | | | ✅ | |
| 33 | `quantity` | int | | | ✅ | |
| 34 | `attribution_window` | string | | | ✅ | |

> ℹ️ impression에만 있는 필드가 click/conversion 이벤트에 들어오면 `null`로 채워집니다. Parquet/Athena 모두 이를 정상 처리합니다.

### 6.1 슈퍼셋 테이블 생성 방법 (3가지)

슈퍼셋 테이블 `ad_events_raw`를 만드는 방법은 3가지입니다.
**Firehose가 Parquet 변환 시 이 테이블의 스키마를 참조**하므로, 동적 파티셔닝 적용 전에 반드시 완성해야 합니다.

#### 방법 A: Terraform으로 정적 테이블 정의 (권장 ⭐)

`05-glue.tf`에서 주석 처리된 `aws_glue_catalog_table.raw`를 복원하고, 위 34개 필드를 모두 정의합니다.
**Terraform으로 관리하면 코드로 스키마 변경 이력을 추적**할 수 있어 가장 권장됩니다.

```hcl
# 05-glue.tf에 추가 (기존 주석 처리된 블록 대체)

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

    # ========== 공통 필드 (impression + click + conversion) ==========
    columns {
      name    = "event_type"
      type    = "string"
      comment = "impression, click, conversion - 동적 파티셔닝 키"
    }

    columns {
      name = "event_id"
      type = "string"
    }

    columns {
      name    = "timestamp"
      type    = "bigint"
      comment = "epoch milliseconds"
    }

    columns {
      name = "impression_id"
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
      name = "advertiser_id"
      type = "string"
    }

    # ========== impression + click 공통 ==========
    columns {
      name = "platform"
      type = "string"
    }

    columns {
      name = "device_type"
      type = "string"
    }

    # ========== impression 전용 ==========
    columns {
      name = "os"
      type = "string"
    }

    columns {
      name = "delivery_region"
      type = "string"
    }

    columns {
      name = "user_lat"
      type = "double"
    }

    columns {
      name = "user_long"
      type = "double"
    }

    columns {
      name = "store_id"
      type = "string"
    }

    columns {
      name = "food_category"
      type = "string"
    }

    columns {
      name = "ad_position"
      type = "string"
    }

    columns {
      name = "ad_format"
      type = "string"
    }

    columns {
      name = "user_agent"
      type = "string"
    }

    columns {
      name = "ip_address"
      type = "string"
    }

    columns {
      name = "session_id"
      type = "string"
    }

    columns {
      name = "keyword"
      type = "string"
    }

    columns {
      name = "cost_per_impression"
      type = "double"
    }

    # ========== click 전용 ==========
    columns {
      name = "click_id"
      type = "string"
    }

    columns {
      name = "click_position_x"
      type = "int"
    }

    columns {
      name = "click_position_y"
      type = "int"
    }

    columns {
      name = "landing_page_url"
      type = "string"
    }

    columns {
      name = "cost_per_click"
      type = "double"
    }

    # ========== conversion 전용 ==========
    columns {
      name = "conversion_id"
      type = "string"
    }

    columns {
      name = "conversion_type"
      type = "string"
    }

    columns {
      name = "conversion_value"
      type = "double"
    }

    columns {
      name = "product_id"
      type = "string"
    }

    columns {
      name = "quantity"
      type = "int"
    }

    columns {
      name = "attribution_window"
      type = "string"
    }
  }

  # ⚠️ partition_keys 제거
  # 동적 파티셔닝 prefix로 S3 폴더가 나뉘지만,
  # 이 테이블은 Firehose의 Parquet 스키마 참조용이므로 파티션 키를 정의하지 않음.
  # Athena 쿼리용 테이블은 Crawler가 별도로 생성함.
}
```

**적용:**
```bash
cd infrastructure/terraform
terraform plan    # ad_events_raw 테이블 생성 확인
terraform apply
```

> ⚠️ **주의:** 기존에 Crawler가 자동 생성한 `ad_events_raw` 테이블이 이미 존재하면 충돌합니다.
> 이 경우 Glue 콘솔에서 기존 테이블을 먼저 삭제하거나, `terraform import`로 가져와야 합니다.
>
> ```bash
> # 기존 테이블 import (이미 존재하는 경우)
> terraform import aws_glue_catalog_table.raw capa_db:ad_events_raw
> ```

#### 방법 B: Glue 콘솔에서 수동 생성/수정

Terraform 없이 빠르게 테스트하고 싶을 때 사용합니다.

**1) 기존 테이블이 있는 경우 (스키마 수정):**
1. AWS Console → AWS Glue → Data Catalog → Tables
2. `ad_events_raw` 클릭 → **Edit schema**
3. **Add column** 버튼으로 누락된 필드 추가
4. 위 34개 필드 테이블을 참고하여 모든 컬럼이 있는지 확인
5. 특히 `event_type` (string) 컬럼이 없으면 반드시 추가
6. **Save** 클릭

**2) 기존 테이블이 없는 경우 (새로 생성):**
1. AWS Console → AWS Glue → Data Catalog → Tables → **Add table**
2. Table name: `ad_events_raw`
3. Database: `capa_db`
4. Data store: S3 → `s3://capa-data-lake-xxx/raw/`
5. Data format: **Parquet**
6. Schema: 위 34개 필드를 하나씩 추가
7. **Create** 클릭

> ℹ️ 콘솔에서 만든 테이블은 Terraform state에 포함되지 않으므로, 나중에 Terraform으로 전환하려면 `terraform import` 필요.

#### 방법 C: Athena DDL로 생성

SQL에 익숙하면 Athena 쿼리 에디터에서 직접 테이블을 생성할 수 있습니다.

```sql
-- Athena 쿼리 에디터에서 실행
-- ⚠️ 기존 ad_events_raw 테이블이 있으면 먼저 삭제
DROP TABLE IF EXISTS capa_db.ad_events_raw;

CREATE EXTERNAL TABLE capa_db.ad_events_raw (
  -- 공통 필드
  event_type          STRING COMMENT 'impression, click, conversion',
  event_id            STRING,
  `timestamp`         BIGINT COMMENT 'epoch milliseconds',
  impression_id       STRING,
  user_id             STRING,
  ad_id               STRING,
  campaign_id         STRING,
  advertiser_id       STRING,
  
  -- impression + click
  platform            STRING,
  device_type         STRING,
  
  -- impression 전용
  os                  STRING,
  delivery_region     STRING,
  user_lat            DOUBLE,
  user_long           DOUBLE,
  store_id            STRING,
  food_category       STRING,
  ad_position         STRING,
  ad_format           STRING,
  user_agent          STRING,
  ip_address          STRING,
  session_id          STRING,
  keyword             STRING,
  cost_per_impression DOUBLE,
  
  -- click 전용
  click_id            STRING,
  click_position_x    INT,
  click_position_y    INT,
  landing_page_url    STRING,
  cost_per_click      DOUBLE,
  
  -- conversion 전용
  conversion_id       STRING,
  conversion_type     STRING,
  conversion_value    DOUBLE,
  product_id          STRING,
  quantity            INT,
  attribution_window  STRING
)
STORED AS PARQUET
LOCATION 's3://capa-data-lake-xxx/raw/'
TBLPROPERTIES ('classification'='parquet');
```

**실행 방법:**
1. AWS Console → Athena → Query editor
2. Database: `capa_db` 선택
3. 위 SQL 붙여넣기 → **Run** 클릭
4. `Query successful` 확인

> ⚠️ `s3://capa-data-lake-xxx/raw/` 부분을 실제 버킷 이름으로 변경하세요.
> ⚠️ `timestamp`는 Athena 예약어이므로 백틱(`)으로 감싸야 합니다.

### 6.2 방법 비교

| 항목 | 방법 A (Terraform) | 방법 B (콘솔) | 방법 C (Athena DDL) |
|------|:---:|:---:|:---:|
| 코드 관리 (IaC) | ✅ | ❌ | ❌ |
| 실행 속도 | 보통 | 빠름 | 빠름 |
| 팀 공유/재현성 | ✅ | ❌ | ✅ (SQL 저장 시) |
| 스키마 변경 이력 | ✅ (Git) | ❌ | ❌ |
| Terraform state 관리 | ✅ | ❌ (import 필요) | ❌ (import 필요) |
| 추천 상황 | 프로덕션 | 빠른 테스트 | SQL 선호 시 |

**권장:** 방법 A (Terraform)로 관리하되, 빠른 검증이 필요할 때 방법 C (Athena DDL)로 먼저 테스트

### 6.3 스키마 동기화 주의사항

```
Generator (Python)  ←→  Glue Table (스키마)  ←→  Firehose (Parquet 변환)
                                ↓
                         Athena (쿼리)
```

**필드를 추가/변경할 때 반드시 3곳을 동시에 수정해야 합니다:**

1. **Generator** (`generator.py`): 실제 JSON에 필드 추가
2. **Glue Table** (`ad_events_raw`): 스키마에 컬럼 추가
3. **Crawler 재실행**: Athena 쿼리 테이블에 반영

Glue Table에 없는 필드가 JSON에 포함되면:
- Parquet 변환 시 **해당 필드가 무시됨** (데이터 손실)
- `error_output_prefix`로 빠지진 않지만, Parquet 파일에 포함되지 않음

Glue Table에 있지만 JSON에 없는 필드:
- Parquet 파일에서 `null`로 채워짐 (정상 동작)

---

## 로그 생성기 수정 상세 가이드

### 현재 상태 진단

현재 로그 생성기 코드는 **이전 방법 2(Firehose 3개 직접 전송) 구조**로 변경된 상태입니다.
구조 B를 적용하려면 아래 **3개 파일**을 수정해야 합니다.

### 1. `kinesis_sender.py` — 전체 롤백

| 항목 | 현재 (잘못된 상태) | 변경 후 (구조 B) |
|------|-----------------|----------------|
| 클래스명 | `FirehoseSender` | `KinesisSender` |
| boto3 클라이언트 | `boto3.client("firehose")` | `boto3.client("kinesis")` |
| 전송 방식 | `firehose.put_record(DeliveryStreamName=...)` | `kinesis.put_record(StreamName=..., PartitionKey=...)` |
| 초기화 파라미터 | `firehose_names: Dict[str, str]` (3개 매핑) | `stream_name: str` (1개) |
| 이벤트 라우팅 | 코드에서 event_type별 Firehose 분기 | 없음 (Firehose 동적 파티셔닝이 처리) |
| PartitionKey | 없음 (Firehose는 불필요) | `user_id` (Kinesis Shard 분배용) |

**핵심 변경점:**
- Generator는 단순히 **모든 이벤트를 Stream 1개에 전송**
- 이벤트 타입별 분리는 **Firehose 동적 파티셔닝**이 자동 처리
- Generator 코드에서 라우팅 로직 완전 제거

**롤백 코드:**
```python
"""
Kinesis Sender - AWS Kinesis Data Stream으로 로그 전송
구조 B: Generator → Stream → Firehose(동적 파티셔닝) → S3
"""

import json
import boto3
from typing import Dict, Optional
from botocore.exceptions import ClientError


class KinesisSender:
    """AWS Kinesis Data Stream으로 로그를 전송하는 클래스"""
    
    def __init__(
        self,
        stream_name: str,
        region: str = "ap-northeast-2",
        aws_access_key_id: Optional[str] = None,
        aws_secret_access_key: Optional[str] = None
    ):
        self.stream_name = stream_name
        self.region = region
        
        session_kwargs = {"region_name": region}
        if aws_access_key_id and aws_secret_access_key:
            session_kwargs["aws_access_key_id"] = aws_access_key_id
            session_kwargs["aws_secret_access_key"] = aws_secret_access_key
        
        try:
            self.client = boto3.client("kinesis", **session_kwargs)
            print(f"✅ Kinesis 클라이언트 생성 성공 (Stream: {stream_name}, Region: {region})", flush=True)
        except Exception as e:
            print(f"❌ Kinesis 클라이언트 생성 실패: {e}", flush=True)
            self.client = None
        
        self.success_count = 0
        self.error_count = 0
    
    def send(self, log: Dict) -> bool:
        if not self.client:
            print(json.dumps(log, ensure_ascii=False), flush=True)
            return False
        
        try:
            log_copy = log.copy()
            log_copy.pop('_internal', None)
            
            data = json.dumps(log_copy, ensure_ascii=False)
            
            # ✅ Kinesis Stream에 전송 (PartitionKey = user_id)
            response = self.client.put_record(
                StreamName=self.stream_name,
                Data=data + "\n",
                PartitionKey=log.get("user_id", "default")
            )
            
            self.success_count += 1
            event_type = log.get("event_type", "unknown")
            print(
                f"[OK] Sent: {event_type} → Stream ({response['ShardId']})",
                flush=True
            )
            return True
            
        except ClientError as e:
            self.error_count += 1
            error_code = e.response.get("Error", {}).get("Code", "Unknown")
            error_msg = e.response.get("Error", {}).get("Message", str(e))
            print(f"[ERROR] Kinesis 전송 실패 [{error_code}]: {error_msg}", flush=True)
            return False
            
        except Exception as e:
            self.error_count += 1
            print(f"[ERROR] Kinesis 전송 오류: {type(e).__name__}: {e}", flush=True)
            return False
    
    def get_stats(self) -> Dict[str, int]:
        return {
            "success": self.success_count,
            "error": self.error_count,
            "total": self.success_count + self.error_count
        }
```

### 2. `main.py` — 전체 롤백

| 항목 | 현재 (잘못된 상태) | 변경 후 (구조 B) |
|------|-----------------|----------------|
| import | `from kinesis_sender import FirehoseSender` | `from kinesis_sender import KinesisSender` |
| 설정 변수 | `FIREHOSE_IMPRESSION/CLICK/CONVERSION` (3개) | `KINESIS_STREAM_NAME` (1개) |
| 활성화 플래그 | `ENABLE_FIREHOSE = True` | `ENABLE_KINESIS = True` |
| Sender 초기화 | `FirehoseSender(firehose_names={...})` | `KinesisSender(stream_name="capa-stream")` |
| 통계 출력 | `sender.get_stats_by_type()` (타입별) | `sender.get_stats()` (전체) |

**핵심 변경점:**
- Config에서 Firehose 3개 환경변수 → Kinesis Stream 1개 환경변수
- Sender 초기화가 단순해짐 (stream_name 하나만 전달)
- 메인 루프 로직은 동일 (impression → click → conversion 순서)

**롤백 코드 (변경 부분만):**
```python
from kinesis_sender import KinesisSender  # ← 변경

class Config:
    # Kinesis 설정 (Stream 1개)
    ENABLE_KINESIS = True
    KINESIS_STREAM_NAME = os.getenv("KINESIS_STREAM_NAME", "capa-stream")
    AWS_REGION = os.getenv("AWS_DEFAULT_REGION", "ap-northeast-2")
    
    # AWS 자격증명
    AWS_ACCESS_KEY_ID = os.getenv("AWS_ACCESS_KEY_ID")
    AWS_SECRET_ACCESS_KEY = os.getenv("AWS_SECRET_ACCESS_KEY")
    
    # 로그 생성 설정
    CTR_RATE = 0.10
    CVR_RATE = 0.20

# Sender 초기화
sender = None
if Config.ENABLE_KINESIS:
    sender = KinesisSender(
        stream_name=Config.KINESIS_STREAM_NAME,
        region=Config.AWS_REGION,
        aws_access_key_id=Config.AWS_ACCESS_KEY_ID,
        aws_secret_access_key=Config.AWS_SECRET_ACCESS_KEY
    )
```

### 3. `generator.py` — `event_type` 필드 추가

이것은 롤백이 아닌 **신규 수정**입니다.
Firehose 동적 파티셔닝이 JQ 표현식 `{event_type: .event_type}`으로 파티션 키를 추출하려면,
**모든 JSON 로그에 `event_type` 필드가 반드시 포함**되어 있어야 합니다.

#### 수정 위치와 내용

**`generate_impression()` 메서드:**
```python
def generate_impression(self) -> Dict:
    impression = {
        "event_type": "impression",       # ← 신규 추가 (첫 번째 필드로)
        "event_id": str(uuid.uuid4()),
        "timestamp": int(datetime.now().timestamp() * 1000),
        "impression_id": str(uuid.uuid4()),
        # ... 나머지 필드 동일 ...
    }
```

**`generate_click()` 메서드:**
```python
def generate_click(self, impression: Dict) -> Dict:
    click = {
        "event_type": "click",             # ← 신규 추가
        "event_id": str(uuid.uuid4()),
        "timestamp": int(datetime.now().timestamp() * 1000),
        "click_id": str(uuid.uuid4()),
        # ... 나머지 필드 동일 ...
    }
```

**`generate_conversion()` 메서드:**
```python
def generate_conversion(self, click: Dict) -> Dict:
    conversion = {
        "event_type": "conversion",        # ← 신규 추가
        "event_id": str(uuid.uuid4()),
        "timestamp": int(datetime.now().timestamp() * 1000),
        "conversion_id": str(uuid.uuid4()),
        # ... 나머지 필드 동일 ...
    }
```

#### 왜 `event_type`이 필요한가?

```
[로그 생성기]                    [Firehose]                        [S3]
                                                                
{"event_type":"impression",     JQ: {event_type:.event_type}     event_type=impression/
 "event_id":"...",         →    결과: "impression"            →  year=2026/month=02/...
 "user_id":"..."}               prefix에 삽입                     xxx.parquet
```

1. Generator가 `event_type` 필드를 포함한 JSON을 Kinesis Stream에 전송
2. Firehose가 Stream에서 데이터를 읽어옴
3. `processing_configuration`의 JQ 쿼리가 JSON에서 `event_type` 값 추출
4. 추출된 값이 S3 prefix의 `!{partitionKeyFromQuery:event_type}` 위치에 삽입
5. 이벤트 타입별로 다른 S3 폴더에 저장됨

> ⚠️ **`event_type` 필드가 없으면** Firehose가 파티션 키를 추출할 수 없어 `error_output_prefix` 경로로 빠집니다.

#### `_internal` 필드와의 관계

`_internal` 필드는 `kinesis_sender.py`의 `send()` 메서드에서 전송 전에 제거됩니다:
```python
log_copy = log.copy()
log_copy.pop('_internal', None)  # _internal은 전송하지 않음
```

`event_type`은 `_internal` 안에 넣으면 안 됩니다.
**반드시 최상위 필드로** 포함해야 Firehose JQ가 읽을 수 있습니다.

---

## 주의사항

### 동적 파티셔닝 + Parquet 변환 호환성

AWS 문서에 따르면 동적 파티셔닝과 `data_format_conversion_configuration`(Parquet 변환)을 **동시에 사용할 수 있습니다.** 단, 다음 조건을 충족해야 합니다:

1. `buffering_size` ≥ 64MB (Parquet 변환 최소 요구)
2. JQ 쿼리는 **변환 전 JSON 원본**에서 실행됨
3. Glue Table 스키마에 `event_type` 필드가 포함되어 있어야 함

만약 호환성 문제 발생 시:
- Parquet 변환을 비활성화하고 JSON으로 저장
- 이후 Glue ETL Job이나 Athena CTAS로 Parquet 변환

### Firehose 재생성 필요

⚠️ **동적 파티셔닝은 기존 Firehose에 추가할 수 없는 경우가 있습니다.**
이 경우 Terraform이 기존 Firehose를 삭제하고 새로 생성합니다.
`terraform plan`에서 `forces replacement` 메시지가 뜨면 정상입니다.

### Glue Table 스키마 (Parquet 변환용)

Firehose가 참조하는 `ad_events_raw` Glue Table에 **모든 이벤트의 필드가 포함**되어야 합니다.
impression에만 있는 필드, conversion에만 있는 필드 모두 하나의 통합 스키마에 들어갑니다.
해당 필드가 없는 이벤트는 `null`로 채워집니다.

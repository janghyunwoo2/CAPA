# Kinesis Firehose에서 3개의 Athena 테이블로 분리하는 방법

## 문제 상황
- 현재: 로그 생성기가 Impression, Click, Conversion 로그를 하나의 Kinesis로 전송 → 하나의 S3 폴더 → 하나의 Athena 테이블
- 목표: 이벤트 타입별로 3개의 폴더와 3개의 Athena 테이블로 분리

## 핵심 이슈
**Firehose의 `schema_configuration`에서는 Glue 테이블을 딱 1개만 지정할 수 있음**
- 이는 **Parquet 변환(직렬화)용 스키마 참조**일 뿐, 데이터 라우팅이나 Athena 테이블 생성과는 무관
- 동적 파티셔닝만으로는 "3개의 Athena 테이블"이 자동 생성되지 않음 → **Crawler가 별도로 생성해줘야 함**

> **⚠️ 중요 개념 분리**
> | 구분 | Firehose가 참조하는 Glue Table | Athena에서 쿼리하는 Glue Table |
> |------|------|------|
> | **역할** | Parquet 직렬화 스키마 (컬럼 구조 정의) | 실제 쿼리 대상 테이블 |
> | **개수** | 1개 (통합 스키마) | 여러 개 가능 (Crawler가 생성) |
> | **생성 주체** | Terraform 정적 정의 | Glue Crawler 자동 생성 |
> | **같은 테이블?** | ❌ **아님** — 완전히 별개의 테이블이어도 됨 |

## 해결 방법

### 방법 1: 동적 파티셔닝 + Glue Crawler 3개 ⭐ (MVP 추천)

#### 아키텍처 흐름
```
Log Generator → Kinesis Stream → Firehose (동적 파티셔닝)
                                           ↓
                    S3: raw/event_type=impression/
                        raw/event_type=click/
                        raw/event_type=conversion/
                                           ↓
                    Crawler 3개 → Athena Table 3개
```

#### 구현 방법

##### 1.1 Firehose 동적 파티셔닝 설정
```hcl
# 03-kinesis.tf 수정
resource "aws_kinesis_firehose_delivery_stream" "main" {
  # ... 기존 설정 ...
  
  extended_s3_configuration {
    # 동적 파티셔닝 활성화
    prefix = "raw/event_type=!{partitionKeyFromQuery:event_type}/year=!{timestamp:yyyy}/month=!{timestamp:MM}/day=!{timestamp:dd}/"
    
    # 동적 파티셔닝 프로세서 추가
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
  }
}
```

##### 1.2 Glue Crawler 3개 생성
```hcl
# 05-glue.tf에 추가
# Impression Crawler
resource "aws_glue_crawler" "impression" {
  name          = "${var.project_name}-impression-crawler"
  database_name = aws_glue_catalog_database.main.name
  role          = aws_iam_role.glue_crawler.arn
  
  s3_target {
    path = "s3://${aws_s3_bucket.data_lake.bucket}/raw/event_type=impression/"
  }
  
  table_prefix = "ad_"  # 테이블명: ad_impression
}

# Click Crawler
resource "aws_glue_crawler" "click" {
  name          = "${var.project_name}-click-crawler"
  database_name = aws_glue_catalog_database.main.name
  role          = aws_iam_role.glue_crawler.arn
  
  s3_target {
    path = "s3://${aws_s3_bucket.data_lake.bucket}/raw/event_type=click/"
  }
  
  table_prefix = "ad_"  # 테이블명: ad_click
}

# Conversion Crawler
resource "aws_glue_crawler" "conversion" {
  name          = "${var.project_name}-conversion-crawler"
  database_name = aws_glue_catalog_database.main.name
  role          = aws_iam_role.glue_crawler.arn
  
  s3_target {
    path = "s3://${aws_s3_bucket.data_lake.bucket}/raw/event_type=conversion/"
  }
  
  table_prefix = "ad_"  # 테이블명: ad_conversion
}
```

#### 장단점
| 장점 | 단점 |
|------|------|
| ✅ 인프라 변경 최소화 | ❌ Parquet 스키마가 통합되어 빈 필드 발생 |
| ✅ 로그 생성기 코드 수정 불필요 | ❌ Crawler 실행 주기 관리 필요 |
| ✅ 빠른 구현 가능 | ❌ 이벤트별 스키마 최적화 어려움 |

---

### 방법 2: Firehose 3개 + Glue Table 3개 ⭐⭐ (운영 추천)

#### 아키텍처 흐름
```
                    ┌→ Firehose(impression) → S3/impression/ → ad_impression 테이블
                    │
Log Generator → 분기 ├→ Firehose(click) → S3/click/ → ad_click 테이블
                    │
                    └→ Firehose(conversion) → S3/conversion/ → ad_conversion 테이블
```

#### 동작 원리

```
[Log Generator (Python)]
  │  event_type 필드를 읽어서 분기
  │
  ├─ event_type == "impression"
  │   └→ firehose.put_record(DeliveryStreamName="capa-firehose-impression", ...)
  │       └→ Firehose(impression)
  │           ├─ Glue Table "ad_impression" 참조 → impression 전용 스키마로 Parquet 변환
  │           └─ S3: raw/impression/year=2026/month=02/day=26/xxx.parquet
  │
  ├─ event_type == "click"
  │   └→ firehose.put_record(DeliveryStreamName="capa-firehose-click", ...)
  │       └→ Firehose(click)
  │           ├─ Glue Table "ad_click" 참조 → click 전용 스키마로 Parquet 변환
  │           └─ S3: raw/click/year=2026/month=02/day=26/xxx.parquet
  │
  └─ event_type == "conversion"
      └→ firehose.put_record(DeliveryStreamName="capa-firehose-conversion", ...)
          └→ Firehose(conversion)
              ├─ Glue Table "ad_conversion" 참조 → conversion 전용 스키마(revenue, price 포함)로 Parquet 변환
              └─ S3: raw/conversion/year=2026/month=02/day=26/xxx.parquet

[Athena 쿼리]
  ├─ SELECT * FROM ad_impression  → S3/impression/ 폴더 읽기
  ├─ SELECT * FROM ad_click       → S3/click/ 폴더 읽기
  └─ SELECT * FROM ad_conversion  → S3/conversion/ 폴더 읽기 (revenue, price 컬럼 있음)
```

> **핵심 포인트**
> - Firehose 1개 = Glue Table 1개 = S3 폴더 1개 = Athena 테이블 1개 → **완전한 1:1:1:1 매핑**
> - 각 Firehose가 자기 전용 Glue Table을 참조하므로, 이벤트별로 **다른 컬럼 구조**의 Parquet 생성 가능
> - Crawler 불필요 — Terraform으로 Glue Table을 직접 정의하면 Athena에서 바로 쿼리 가능
> - 라우팅 로직은 **애플리케이션(Python) 코드**에서 담당 (Firehose는 라우팅하지 않음)

#### 구현 방법

##### 2.1 Firehose 3개 생성
```hcl
# 03-kinesis.tf 수정
# Impression Firehose
resource "aws_kinesis_firehose_delivery_stream" "impression" {
  name = "${var.project_name}-firehose-impression"
  
  # ... 설정 ...
  
  extended_s3_configuration {
    prefix = "raw/impression/year=!{timestamp:yyyy}/month=!{timestamp:MM}/day=!{timestamp:dd}/"
    
    data_format_conversion_configuration {
      schema_configuration {
        database_name = aws_glue_catalog_database.main.name
        table_name    = "ad_impression"  # impression 전용 테이블
        role_arn      = aws_iam_role.firehose.arn
      }
    }
  }
}

# Click과 Conversion도 동일하게 생성
```

##### 2.2 Glue Table 3개 생성
```hcl
# 05-glue.tf에 추가
resource "aws_glue_catalog_table" "impression" {
  name          = "ad_impression"
  database_name = aws_glue_catalog_database.main.name
  
  storage_descriptor {
    columns {
      name = "event_id"
      type = "string"
    }
    columns {
      name = "campaign_id"
      type = "string"
    }
    # impression 전용 필드
  }
}

resource "aws_glue_catalog_table" "conversion" {
  name          = "ad_conversion"
  database_name = aws_glue_catalog_database.main.name
  
  storage_descriptor {
    columns {
      name = "event_id"
      type = "string"
    }
    columns {
      name = "revenue"
      type = "double"
    }
    columns {
      name = "price"
      type = "double"
    }
    # conversion 전용 필드
  }
}
```

##### 2.3 로그 생성기 코드 수정
```python
# generator.py
class AdLogGenerator:
    def __init__(self):
        self.kinesis = boto3.client('kinesis')
        self.firehose = boto3.client('firehose')
        
        # Firehose 이름 매핑
        self.firehose_streams = {
            'impression': 'capa-firehose-impression',
            'click': 'capa-firehose-click',
            'conversion': 'capa-firehose-conversion'
        }
    
    def send_log(self, log_data):
        event_type = log_data['event_type']
        stream_name = self.firehose_streams[event_type]
        
        # 이벤트 타입별로 다른 Firehose로 전송
        self.firehose.put_record(
            DeliveryStreamName=stream_name,
            Record={'Data': json.dumps(log_data)}
        )
```

#### 장단점
| 장점 | 단점 |
|------|------|
| ✅ 이벤트별 스키마 완전 분리 | ❌ 인프라 리소스 3배 |
| ✅ conversion만의 revenue/price 필드 최적화 | ❌ 로그 생성기 코드 수정 필요 |
| ✅ Crawler 없이 즉시 쿼리 가능 | ❌ 초기 구축 시간 증가 |
| ✅ 스키마 버전 관리 용이 | ❌ Terraform 코드량 증가 |

---

## 방법 비교표

| 구분 | 방법 1 (동적 파티셔닝) | 방법 2 (Firehose 3개) |
|------|----------------------|---------------------|
| **Kinesis Stream** | 1개 (기존 유지) | 1개 (기존 유지) |
| **Firehose** | 1개 (동적 파티셔닝) | 3개 |
| **Glue Table (Firehose용)** | 1개 (통합 스키마) | 3개 (개별 스키마) |
| **Crawler** | 3개 필요 | 불필요 |
| **로그 생성기 수정** | 불필요 | 필요 (분기 로직) |
| **S3 구조** | event_type=xxx 파티션 | 별도 폴더 |
| **스키마 유연성** | 낮음 | 높음 |
| **구현 복잡도** | 낮음 | 중간 |
| **운영 복잡도** | 중간 (Crawler 관리) | 낮음 |

---

## 추천 시나리오

### MVP/PoC 단계
- **방법 1** 추천
- 빠른 구현과 검증에 집중
- 나중에 방법 2로 마이그레이션 가능

### Production 운영
- **방법 2** 추천
- 스키마 분리로 성능 최적화
- 각 이벤트별 독립적인 진화 가능

### Hybrid 접근법
1. 초기: 방법 1로 빠르게 구축
2. 데이터 패턴 파악 후 방법 2로 전환
3. 전환 시 dual-write로 무중단 마이그레이션

---

## 참고사항

### Firehose 동적 파티셔닝 제약
- JQ 표현식은 단순해야 함 (복잡한 로직 불가)
- 파티션 키는 최대 10개까지
- 처리 지연 시간 약간 증가 (1-2초)

### Crawler vs 정적 테이블
- Crawler: 스키마 자동 감지, 실행 주기 필요
- 정적 테이블: 즉시 사용 가능, 수동 관리 필요

### 비용 고려사항
- Firehose: 처리 데이터 양 기준 과금 (개수 무관)
- Crawler: 실행 시간 기준 과금
- Glue Table: 메타데이터 저장 비용 (매우 저렴)
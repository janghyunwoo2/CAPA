# Kinesis Stream 유지 + 3개 테이블 분리 아키텍처 옵션

## 배경

- Kinesis Stream은 **다중 소비자 확장**을 위해 반드시 유지
- 현재는 S3 저장만 하지만, 향후 실시간 이상 탐지, 대시보드 등 소비자 추가 예정
- 이벤트 타입(impression, click, conversion)별로 **S3 폴더 및 Athena 테이블 3개**로 분리 필요

---

## 문제점: 왜 단순하게 안 되는가

### ❌ Generator → firehose.put_record()
```
Generator → firehose.put_record() → Firehose (KinesisStreamAsSource)
                                     ↑
                        "나는 Stream에서 받는 모드야. put_record 거부!"
```
Firehose가 KinesisStreamAsSource 모드이면 `put_record()` API 호출이 **거부**됩니다.

### ❌ Stream 1개 → Firehose 3개 (각각 필터링)
```
Generator → Stream → Firehose(imp)  "impression만 가져가기" ← 불가능!
                   → Firehose(clk)  "click만 가져가기" ← 불가능!
                   → Firehose(cvs)  "conversion만 가져가기" ← 불가능!
```
Firehose는 Stream에서 **전체 데이터를 그대로 복사**해갑니다. 특정 event_type만 필터링하는 기능이 없습니다.

---

## 가능한 구조 3가지

### 구조 A: Stream 3개 + Firehose 3개

```
               ┌→ Stream(imp) → Firehose(imp) → S3/impression/
               │                     ↓
               │               (미래) Lambda: imp 이상 탐지
               │
Generator → 분기 ├→ Stream(clk) → Firehose(clk) → S3/click/
               │                     ↓
               │               (미래) Lambda: 클릭 사기 감지
               │
               └→ Stream(cvs) → Firehose(cvs) → S3/conversion/
                                     ↓
                               (미래) Lambda: 매출 알림
```

#### 동작 원리
1. Generator가 `event_type`을 확인하여 **해당 Stream에 `kinesis.put_record()` 전송**
2. 각 Firehose가 자기 Stream에서 데이터를 자동으로 pull
3. 각 Firehose가 자기 전용 Glue Table 스키마로 Parquet 변환 → S3 저장

#### 장단점
| 장점 | 단점 |
|------|------|
| ✅ 이벤트별 독립적인 다중 소비자 가능 | ❌ Stream 3개 = 샤드 비용 3배 |
| ✅ 이벤트별 스키마 완전 분리 | ❌ Terraform 리소스 많음 |
| ✅ 이벤트별 독립적 처리량 조절 | ❌ Generator 코드 분기 필요 |
| ✅ 한 이벤트 장애가 다른 이벤트에 영향 없음 | |

#### Terraform 변경사항
- Kinesis Stream 2개 추가 (총 3개)
- Firehose 이름 변경 (기존 1개 → 3개로 분리)
- Glue Table 3개 정의
- Generator 코드에서 Stream 분기 로직 추가

---

### 구조 B: Stream 1개 + Firehose 동적 파티셔닝 ⭐ (추천)

```
Generator → Stream (1개, 통합) → Firehose (동적 파티셔닝)
                │                       ↓
                │              S3/event_type=impression/year=.../
                │              S3/event_type=click/year=.../
                │              S3/event_type=conversion/year=.../
                │                       ↓
                │              Crawler 3개 → Athena Table 3개
                │
                ├→ (미래) Lambda: 이상 탐지
                ├→ (미래) Lambda: 실시간 대시보드
                └→ (미래) KDA: 실시간 CTR 집계
```

#### 동작 원리
1. Generator가 기존처럼 `kinesis.put_record()` → **Stream 1개에 전송** (코드 변경 거의 없음)
2. Firehose가 Stream에서 전체 데이터를 pull
3. Firehose **동적 파티셔닝**: JSON에서 `event_type` 필드를 읽어 S3 prefix에 반영
4. S3에 `event_type=impression/`, `event_type=click/`, `event_type=conversion/` 폴더로 자동 분리
5. Glue Crawler 3개가 각 폴더를 스캔하여 Athena 테이블 3개 생성

#### 장단점
| 장점 | 단점 |
|------|------|
| ✅ 기존 코드 변경 거의 없음 | ❌ Parquet 스키마가 통합(빈 필드 발생) |
| ✅ Stream 1개로 비용 최소화 | ❌ Crawler 실행 주기 관리 필요 |
| ✅ 다중 소비자 확장 가능 (Stream에 붙이면 됨) | ❌ 이벤트별 독립 스케일링 불가 |
| ✅ Firehose 설정만 수정 | |

#### Terraform 변경사항
- Kinesis Stream: **변경 없음** (기존 유지)
- Firehose: `prefix` 수정 + `processing_configuration` 추가 (동적 파티셔닝)
- Glue Crawler 3개 추가 (각 S3 폴더별)
- Generator 코드: **변경 없음**

#### Firehose 동적 파티셔닝 설정 예시
```hcl
resource "aws_kinesis_firehose_delivery_stream" "main" {
  # ... 기존 설정 유지 ...
  
  # kinesis_source_configuration 유지 (Stream에서 읽기)
  kinesis_source_configuration {
    kinesis_stream_arn = aws_kinesis_stream.main.arn
    role_arn           = aws_iam_role.firehose.arn
  }

  extended_s3_configuration {
    # 동적 파티셔닝 prefix
    prefix = "raw/event_type=!{partitionKeyFromQuery:event_type}/year=!{timestamp:yyyy}/month=!{timestamp:MM}/day=!{timestamp:dd}/"
    
    # 동적 파티셔닝 프로세서
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
    
    # 동적 파티셔닝 활성화
    dynamic_partitioning_configuration {
      enabled = true
    }
    
    # ... Parquet 변환 등 기존 설정 유지 ...
  }
}
```

---

### 구조 C: Stream 1개 + Lambda 라우터 + Firehose 3개

```
Generator → Stream → Lambda (라우터)
                │         ├→ firehose.put_record("capa-fh-imp-00") → S3/impression/
                │         ├→ firehose.put_record("capa-fh-clk-00") → S3/click/
                │         └→ firehose.put_record("capa-fh-cvs-00") → S3/conversion/
                │
                ├→ (미래) Lambda: 이상 탐지
                └→ (미래) Lambda: 실시간 대시보드
```

#### 동작 원리
1. Generator가 기존처럼 `kinesis.put_record()` → Stream 1개에 전송
2. **Lambda(라우터)**가 Stream에서 데이터를 읽음
3. Lambda가 `event_type`을 확인하여 해당 Firehose에 `firehose.put_record()` 전송
4. 3개의 Firehose는 **Direct PUT 모드** (KinesisStreamAsSource 아님)
5. 각 Firehose가 전용 Glue Table로 Parquet 변환 → S3 저장

#### 장단점
| 장점 | 단점 |
|------|------|
| ✅ 이벤트별 스키마 완전 분리 | ❌ Lambda 비용 추가 (호출 수 기반) |
| ✅ Stream 1개로 다중 소비자 가능 | ❌ Lambda 장애 시 데이터 유실 가능 |
| ✅ Generator 코드 변경 없음 | ❌ 구조 복잡도 증가 |
| ✅ 각 Firehose가 정확한 스키마 사용 | ❌ Lambda 코드 관리 필요 |

#### Lambda 라우터 코드 예시
```python
import json
import boto3

firehose = boto3.client('firehose')

FIREHOSE_MAP = {
    'impression': 'capa-fh-imp-00',
    'click': 'capa-fh-clk-00',
    'conversion': 'capa-fh-cvs-00',
}

def handler(event, context):
    for record in event['Records']:
        payload = json.loads(
            base64.b64decode(record['kinesis']['data']).decode('utf-8')
        )
        
        # event_type 판별
        if payload.get('conversion_id'):
            event_type = 'conversion'
        elif payload.get('click_id'):
            event_type = 'click'
        else:
            event_type = 'impression'
        
        # 해당 Firehose로 전송
        firehose.put_record(
            DeliveryStreamName=FIREHOSE_MAP[event_type],
            Record={'Data': json.dumps(payload) + '\n'}
        )
```

---

## 3가지 구조 비교표

| 항목 | 구조 A (Stream 3개) | 구조 B (동적 파티셔닝) ⭐ | 구조 C (Lambda 라우터) |
|------|-------------------|---------------------|---------------------|
| **Kinesis Stream** | 3개 | 1개 | 1개 |
| **Firehose** | 3개 (KinesisAsSource) | 1개 (동적 파티셔닝) | 3개 (Direct PUT) |
| **Lambda** | 불필요 | 불필요 | 1개 (라우터) |
| **Glue Table (스키마)** | 3개 (개별) | 1개 (통합) | 3개 (개별) |
| **Crawler** | 불필요 | 3개 | 불필요 |
| **Generator 코드 변경** | 분기 로직 추가 | 변경 없음 | 변경 없음 |
| **스키마 유연성** | 높음 | 낮음 (통합 스키마) | 높음 |
| **다중 소비자** | 이벤트별 독립 | 통합 Stream에 연결 | 통합 Stream에 연결 |
| **비용** | 높음 (Stream 3개) | 최소 | 중간 (Lambda 추가) |
| **구현 복잡도** | 중간 | 낮음 | 높음 |
| **운영 복잡도** | 중간 | 낮음 | 높음 (Lambda 모니터링) |

---

## 추천

### MVP 단계 → 구조 B (동적 파티셔닝)
- 기존 코드 변경 없이 Firehose 설정만 수정
- Stream 1개로 비용 최소화 + 다중 소비자 확장 가능
- Crawler 3개로 Athena 테이블 자동 생성

### 운영 단계 (이벤트별 독립 처리 필요 시) → 구조 A (Stream 3개)
- 이벤트별 완전히 독립된 파이프라인
- 한 이벤트의 장애가 다른 이벤트에 영향 없음
- 이벤트별 독립적 스케일링 및 다중 소비자

### 스키마 분리가 중요하지만 비용 절감 필요 시 → 구조 C (Lambda 라우터)
- Stream 1개로 비용 절감 + 스키마 완전 분리
- 단, Lambda 관리 부담 추가

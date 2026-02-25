# Kinesis 및 Firehose 통합 가이드

## 1. 개요

이 가이드는 광고 로그 생성기에 AWS Kinesis Data Streams와 Firehose를 통합하여 실시간 스트리밍 아키텍처를 구축하는 방법을 설명합니다. 현재 배치 방식의 `ad_log_generator.py`를 실시간 스트리밍 방식으로 전환하는 과정을 다룹니다.

## 2. 아키텍처 비교 분석

### 2.1 현재 시스템 구조

#### 배치 방식 (ad_log_generator.py)
```
[로그 생성] → [DataFrame 구성] → [Parquet 압축] → [S3 직접 업로드]
```

**특징:**
- 시간별로 대량 데이터를 한 번에 처리
- 10,000개 이상의 레코드를 메모리에 보관 후 저장
- 파티셔닝: `/year=/month=/day=/hour=` 구조

#### 실시간 스트리밍 방식 (main.py, t3_log_generator)
```
[로그 생성] → [JSON 직렬화] → [Kinesis Streams] → [Firehose] → [S3]
```

**특징:**
- 레코드 단위로 즉시 전송
- 24시간 데이터 버퍼링으로 안전성 보장
- 자동 파일 생성 및 압축

### 2.2 성능 및 비용 비교

| 구분 | 배치 방식 | 스트리밍 방식 | 하이브리드 방식 |
|------|----------|--------------|----------------|
| **지연시간** | 1시간 | 1-2분 | 1-2분 |
| **처리량** | 매우 높음 | 중간 | 높음 |
| **데이터 손실 위험** | 높음 | 매우 낮음 | 낮음 |
| **구현 복잡도** | 낮음 | 중간 | 높음 |
| **월 예상 비용** | ~$50 | ~$200-500 | ~$250-550 |
| **확장성** | 수동 | 자동 | 자동 |

## 3. 파일 구조 권장사항

### 3.1 프로덕션 환경: 모듈화된 구조 (권장)

```
log-generator/
├── pyproject.toml          # 의존성 관리
├── .env                    # 환경 변수
├── main.py                 # 진입점
├── generator.py            # 로그 생성 로직
├── kinesis_sender.py       # Kinesis 전송 모듈
├── s3_writer.py           # S3 직접 저장 모듈 (옵션)
└── config.py              # 설정 관리
```

**장점:**
- 각 기능이 독립적으로 관리되어 유지보수 용이
- 단위 테스트 작성 용이
- 재사용 가능한 컴포넌트
- 팀 협업에 유리

**단점:**
- 초기 설정 복잡도 증가
- 파일 간 의존성 관리 필요

### 3.2 프로토타입/POC: 단일 파일 구조

```
ad_log_generator_streaming.py  # 모든 로직 포함
```

**장점:**
- 빠른 프로토타이핑
- 배포 및 실행 간단
- 의존성 최소화

**단점:**
- 코드가 길어지면 관리 어려움
- 재사용성 낮음

### 3.3 권장 접근 방법

1. **초기 개발**: 단일 파일로 시작하여 빠르게 검증
2. **안정화 단계**: 기능별로 모듈 분리
3. **프로덕션 배포**: 완전히 모듈화된 구조로 전환

## 4. Kinesis와 Firehose의 역할 및 구현

### 4.1 AWS Kinesis Data Streams

**핵심 역할:**
- **실시간 버퍼**: 1-7일간 데이터 보존으로 장애 대응
- **병렬 처리**: 샤드별 분산으로 초당 수천 건 처리
- **다중 소비**: 동일 데이터를 여러 시스템에서 활용

**구현 시 주의사항:**
```python
# PartitionKey 설정이 중요 - 균등 분산을 위해
partition_key = f"{user_id}_{timestamp.strftime('%Y%m%d%H')}"
```

### 4.2 AWS Kinesis Data Firehose

**핵심 역할:**
- **자동 전송**: Kinesis → S3 자동 배치 처리
- **형식 변환**: JSON → Parquet 실시간 변환
- **압축 최적화**: GZIP/Snappy로 스토리지 절감

**최적 설정값:**
- Buffer Size: 128MB (대용량 처리 시)
- Buffer Interval: 60초 (실시간성 요구 시)
- Compression: GZIP (압축률 우선) 또는 Snappy (속도 우선)

## 5. 통합 구현 방법

### 5.1 모듈화된 구조 구현 (프로덕션 권장)

#### kinesis_sender.py
```python
import json
import boto3
import logging
from typing import Dict, List, Optional
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)

class KinesisSender:
    """AWS Kinesis Data Streams 전송 모듈"""
    
    def __init__(self, stream_name: str, region: str = "ap-northeast-2", 
                 batch_size: int = 500):
        self.stream_name = stream_name
        self.batch_size = batch_size
        self.client = boto3.client("kinesis", region_name=region)
        self.batch_buffer = []
        self.stats = {"success": 0, "error": 0}
        
    def send_single(self, record: Dict) -> bool:
        """단일 레코드 전송"""
        try:
            response = self.client.put_record(
                StreamName=self.stream_name,
                Data=json.dumps(record, ensure_ascii=False) + "\n",
                PartitionKey=self._get_partition_key(record)
            )
            self.stats["success"] += 1
            return True
        except ClientError as e:
            self.stats["error"] += 1
            logger.error(f"Kinesis 전송 실패: {e.response['Error']['Code']}")
            return False
    
    def send_batch(self, records: List[Dict]) -> dict:
        """배치 전송 (최대 500개)"""
        if not records:
            return {"success": 0, "failed": 0}
        
        kinesis_records = [
            {
                "Data": json.dumps(record, ensure_ascii=False) + "\n",
                "PartitionKey": self._get_partition_key(record)
            }
            for record in records[:self.batch_size]
        ]
        
        try:
            response = self.client.put_records(
                StreamName=self.stream_name,
                Records=kinesis_records
            )
            failed = response.get('FailedRecordCount', 0)
            success = len(kinesis_records) - failed
            
            self.stats["success"] += success
            self.stats["error"] += failed
            
            return {"success": success, "failed": failed}
        except Exception as e:
            logger.error(f"배치 전송 실패: {e}")
            return {"success": 0, "failed": len(records)}
    
    def _get_partition_key(self, record: Dict) -> str:
        """파티션 키 생성 (균등 분산)"""
        # user_id와 시간을 조합하여 균등 분산
        user_id = record.get("user_id", "default")
        event_type = record.get("event_type", "unknown")
        return f"{user_id}_{event_type}"

#### generator.py
```python
import uuid
import random
from datetime import datetime
from typing import Dict, List, Optional
from faker import Faker

class AdLogGenerator:
    """광고 로그 생성 핵심 로직"""
    
    def __init__(self, config: dict):
        self.faker = Faker('ko_KR')
        self.config = config
        
        # 마스터 데이터 초기화
        self.users = [f"user_{i:06d}" for i in range(1, config.get('user_count', 100001))]
        self.ads = [f"ad_{i:04d}" for i in range(1, config.get('ad_count', 1001))]
        self.campaigns = [f"campaign_{i:02d}" for i in range(1, 6)]
        
    def generate_impression(self) -> Dict:
        """노출 로그 생성"""
        timestamp = datetime.now()
        
        impression = {
            "event_id": str(uuid.uuid4()),
            "event_type": "impression",
            "timestamp": timestamp.isoformat(),
            "user_id": random.choice(self.users),
            "ad_id": random.choice(self.ads),
            "campaign_id": random.choice(self.campaigns),
            "device_type": random.choice(["mobile", "desktop", "tablet"]),
            "ad_position": random.choice(["top", "middle", "bottom"]),
            "keyword": self.faker.word(),
            "user_agent": self.faker.user_agent()
        }
        
        return impression
    
    def generate_click(self, impression: Dict) -> Optional[Dict]:
        """클릭 로그 생성 (CTR 기반)"""
        # CTR 계산 (위치별 가중치)
        ctr_weights = {"top": 0.15, "middle": 0.10, "bottom": 0.05}
        ctr = ctr_weights.get(impression.get("ad_position"), 0.08)
        
        if random.random() < ctr:
            return {
                "event_id": str(uuid.uuid4()),
                "event_type": "click",
                "impression_id": impression["event_id"],
                "timestamp": datetime.now().isoformat(),
                "user_id": impression["user_id"],
                "ad_id": impression["ad_id"],
                "campaign_id": impression["campaign_id"],
            }
        return None
    
    def generate_conversion(self, click: Dict) -> Optional[Dict]:
        """전환 로그 생성 (CVR 기반)"""
        if random.random() < 0.05:  # 5% CVR
            return {
                "event_id": str(uuid.uuid4()),
                "event_type": "conversion",
                "click_id": click["event_id"],
                "timestamp": datetime.now().isoformat(),
                "user_id": click["user_id"],
                "conversion_type": random.choice(["purchase", "signup", "download"]),
                "conversion_value": round(random.uniform(1000, 50000), 2)
            }
        return None"

#### config.py
```python
import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    """환경 변수 기반 설정 관리"""
    
    # 실행 모드
    EXECUTION_MODE = os.getenv("EXECUTION_MODE", "batch")  # batch, streaming, hybrid
    
    # AWS 설정
    AWS_REGION = os.getenv("AWS_REGION", "ap-northeast-2")
    AWS_ACCESS_KEY_ID = os.getenv("AWS_ACCESS_KEY_ID")
    AWS_SECRET_ACCESS_KEY = os.getenv("AWS_SECRET_ACCESS_KEY")
    
    # Kinesis 설정
    ENABLE_KINESIS = os.getenv("ENABLE_KINESIS", "false").lower() == "true"
    KINESIS_STREAM_NAME = os.getenv("KINESIS_STREAM_NAME", "capa-ad-logs-dev")
    KINESIS_BATCH_SIZE = int(os.getenv("KINESIS_BATCH_SIZE", "500"))
    
    # S3 설정
    S3_BUCKET_NAME = os.getenv("S3_BUCKET_NAME", "capa-data-lake")
    S3_PREFIX = os.getenv("S3_PREFIX", "raw/ad-logs")
    
    # 생성 설정
    USERS_COUNT = int(os.getenv("USERS_COUNT", "10000"))
    ADS_COUNT = int(os.getenv("ADS_COUNT", "1000"))
    LOGS_PER_SECOND = int(os.getenv("LOGS_PER_SECOND", "100"))
    
    @classmethod
    def validate(cls):
        """설정 값 검증"""
        if cls.ENABLE_KINESIS and not cls.KINESIS_STREAM_NAME:
            raise ValueError("KINESIS_STREAM_NAME은 필수입니다.")
        
        if cls.EXECUTION_MODE not in ["batch", "streaming", "hybrid"]:
            raise ValueError(f"잘못된 실행 모드: {cls.EXECUTION_MODE}")
```

#### main.py
```python
#!/usr/bin/env python3
"""
통합 광고 로그 생성기
배치/스트리밍/하이브리드 모드 지원
"""

import time
import signal
import logging
from datetime import datetime

from config import Config
from generator import AdLogGenerator
from kinesis_sender import KinesisSender

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class AdLogService:
    """통합 로그 생성 서비스"""
    
    def __init__(self):
        Config.validate()
        
        # 각 구성 요소 초기화
        self.generator = AdLogGenerator({"user_count": Config.USERS_COUNT})
        self.kinesis_sender = None
        
        if Config.ENABLE_KINESIS:
            self.kinesis_sender = KinesisSender(
                stream_name=Config.KINESIS_STREAM_NAME,
                region=Config.AWS_REGION,
                batch_size=Config.KINESIS_BATCH_SIZE
            )
        
        self.running = True
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
    
    def _signal_handler(self, signum, frame):
        logger.info("종료 신호 수신...")
        self.running = False
    
    def run_streaming_mode(self):
        """실시간 스트리밍 모드"""
        logger.info("🚀 스트리밍 모드 시작")
        
        while self.running:
            try:
                # 노출 생성 및 전송
                impression = self.generator.generate_impression()
                if self.kinesis_sender:
                    self.kinesis_sender.send_single(impression)
                
                # 클릭 확률 처리
                click = self.generator.generate_click(impression)
                if click and self.kinesis_sender:
                    time.sleep(random.uniform(0.5, 2))
                    self.kinesis_sender.send_single(click)
                    
                    # 전환 확률 처리
                    conversion = self.generator.generate_conversion(click)
                    if conversion:
                        time.sleep(random.uniform(1, 5))
                        self.kinesis_sender.send_single(conversion)
                
                # 초당 로그 수 조절
                time.sleep(1.0 / Config.LOGS_PER_SECOND)
                
            except Exception as e:
                logger.error(f"로그 생성 오류: {e}")
    
    def run_hybrid_mode(self):
        """하이브리드 모드 - 실시간 + 배치"""
        logger.info("🔄 하이브리드 모드 시작")
        
        batch_buffer = []
        batch_start_time = datetime.now()
        
        while self.running:
            # 로그 생성
            impression = self.generator.generate_impression()
            batch_buffer.append(impression)
            
            # 배치 크기 또는 시간 초과 시 전송
            if len(batch_buffer) >= 500 or \
               (datetime.now() - batch_start_time).seconds >= 60:
                
                if self.kinesis_sender:
                    result = self.kinesis_sender.send_batch(batch_buffer)
                    logger.info(f"배치 전송: {result}")
                
                # S3로도 저장 (구현 필요)
                # self.save_to_s3(batch_buffer)
                
                batch_buffer = []
                batch_start_time = datetime.now()
    
    def print_statistics(self):
        """통계 출력"""
        if self.kinesis_sender:
            stats = self.kinesis_sender.stats
            logger.info(f"\n통계: 성공 {stats['success']:,}, 실패 {stats['error']:,}")

def main():
    import argparse
    
    parser = argparse.ArgumentParser(description='통합 광고 로그 생성기')
    parser.add_argument('--mode', 
                        choices=['batch', 'streaming', 'hybrid'],
                        default=Config.EXECUTION_MODE,
                        help='실행 모드')
    
    args = parser.parse_args()
    
    # 환경 변수 업데이트
    os.environ['EXECUTION_MODE'] = args.mode
    
    service = AdLogService()
    
    try:
        if args.mode == 'streaming':
            service.run_streaming_mode()
        elif args.mode == 'hybrid':
            service.run_hybrid_mode()
        else:
            logger.info("📦 배치 모드는 기존 ad_log_generator.py 사용")
    finally:
        service.print_statistics()

if __name__ == "__main__":
    main()
```

### 5.2 단일 파일 구조 구현 (프로토타입용)

```python
#!/usr/bin/env python3
"""
광고 로그 생성기 - 단일 파일 버전 (POC용)
"""

import os
import time
import json
import random
import uuid
import boto3
from datetime import datetime
from typing import Dict, Optional
from dotenv import load_dotenv

load_dotenv()

class SimpleAdLogGenerator:
    def __init__(self):
        # Kinesis 클라이언트
        self.kinesis_enabled = os.getenv("ENABLE_KINESIS", "false").lower() == "true"
        if self.kinesis_enabled:
            self.kinesis_client = boto3.client(
                'kinesis',
                region_name=os.getenv("AWS_REGION", "ap-northeast-2")
            )
            self.stream_name = os.getenv("KINESIS_STREAM_NAME", "capa-ad-logs")
        
        # 마스터 데이터
        self.users = [f"user_{i:06d}" for i in range(1, 1001)]
        self.ads = [f"ad_{i:04d}" for i in range(1, 101)]
    
    def send_to_kinesis(self, record: Dict):
        if not self.kinesis_enabled:
            print(json.dumps(record), flush=True)
            return
        
        try:
            self.kinesis_client.put_record(
                StreamName=self.stream_name,
                Data=json.dumps(record) + "\n",
                PartitionKey=record.get("user_id", "default")
            )
        except Exception as e:
            print(f"Kinesis error: {e}")
    
    def run(self):
        print(f"Starting... (Kinesis: {self.kinesis_enabled})")
        
        while True:
            # 노출
            impression = {
                "event_id": str(uuid.uuid4()),
                "event_type": "impression",
                "timestamp": datetime.now().isoformat(),
                "user_id": random.choice(self.users),
                "ad_id": random.choice(self.ads),
            }
            self.send_to_kinesis(impression)
            
            # 10% 클릭
            if random.random() < 0.10:
                time.sleep(random.uniform(0.5, 2))
                click = {
                    "event_id": str(uuid.uuid4()),
                    "event_type": "click",
                    "impression_id": impression["event_id"],
                    "timestamp": datetime.now().isoformat(),
                    "user_id": impression["user_id"]
                }
                self.send_to_kinesis(click)
            
            time.sleep(0.1)  # 10 logs/sec

if __name__ == "__main__":
    generator = SimpleAdLogGenerator()
    generator.run()
```

## 6. Firehose 설정 및 구성

### 6.1 Terraform으로 Firehose 구성

```hcl
# Kinesis Data Stream
resource "aws_kinesis_stream" "ad_logs" {
  name = "capa-ad-logs-stream"
  
  # On-Demand 모드 (자동 스케일링)
  stream_mode_details {
    stream_mode = "ON_DEMAND"
  }
  
  tags = {
    Environment = "production"
    Purpose     = "ad-log-streaming"
  }
}

# Firehose Delivery Stream
resource "aws_kinesis_firehose_delivery_stream" "ad_logs" {
  name        = "capa-ad-logs-firehose"
  destination = "extended_s3"

  kinesis_source_configuration {
    kinesis_stream_arn = aws_kinesis_stream.ad_logs.arn
    role_arn          = aws_iam_role.firehose_role.arn
  }

  extended_s3_configuration {
    role_arn   = aws_iam_role.firehose_role.arn
    bucket_arn = aws_s3_bucket.data_lake.arn
    
    # 파티셔닝 - Athena 최적화
    prefix = "raw/streaming/log_type=!{partitionKeyFromQuery:log_type}/dt=!{timestamp:yyyy-MM-dd}/hour=!{timestamp:HH}/"
    error_output_prefix = "errors/!{timestamp:yyyy/MM/dd}/"
    
    # 버퍼 설정 - 대용량 처리 최적화
    buffer_size     = 128  # MB
    buffer_interval = 60   # seconds
    
    # 압축 - 스토리지 절감
    compression_format = "GZIP"
    
    # Parquet 변환
    data_format_conversion_configuration {
      enabled = true
      
      output_format_configuration {
        serializer {
          parquet_ser_de {
            compression = "SNAPPY"  # Parquet 내부 압축
          }
        }
      }
      
      schema_configuration {
        database_name = aws_glue_catalog_database.logs.name
        table_name    = aws_glue_catalog_table.ad_logs.name
        role_arn      = aws_iam_role.glue_catalog_role.arn
      }
    }
    
    # 동적 파티셔닝
    processing_configuration {
      enabled = true
      
      processors {
        type = "MetadataExtraction"
        parameters {
          parameter_name  = "MetadataExtractionQuery"
          parameter_value = "{log_type: .event_type}"
        }
        parameters {
          parameter_name  = "JsonParsingEngine"
          parameter_value = "JQ-1.6"
        }
      }
    }
  }
}

# Glue Catalog 테이블
resource "aws_glue_catalog_table" "ad_logs" {
  name          = "ad_logs_streaming"
  database_name = aws_glue_catalog_database.logs.name
  
  table_type = "EXTERNAL_TABLE"
  
  parameters = {
    "projection.enabled"  = "true"
    "projection.dt.type"  = "date"
    "projection.dt.range" = "2026-01-01,NOW"
    "projection.dt.format" = "yyyy-MM-dd"
    "projection.hour.type" = "integer"
    "projection.hour.range" = "0,23"
    "projection.hour.digits" = "2"
  }
  
  storage_descriptor {
    location      = "s3://${aws_s3_bucket.data_lake.id}/raw/streaming/"
    input_format  = "org.apache.hadoop.hive.ql.io.parquet.MapredParquetInputFormat"
    output_format = "org.apache.hadoop.hive.ql.io.parquet.MapredParquetOutputFormat"
    
    ser_de_info {
      serialization_library = "org.apache.hadoop.hive.serde2.lazy.LazySimpleSerDe"
    }
    
    columns {
      name = "event_id"
      type = "string"
    }
    columns {
      name = "event_type"
      type = "string"
    }
    columns {
      name = "timestamp"
      type = "timestamp"
    }
    columns {
      name = "user_id"
      type = "string"
    }
    # ... 기타 컴럼들
  }
  
  partition_keys {
    name = "log_type"
    type = "string"
  }
  partition_keys {
    name = "dt"
    type = "date"
  }
  partition_keys {
    name = "hour"
    type = "int"
  }
}
```

## 7. 마이그레이션 전략 및 실무 가이드

### 7.1 단계별 마이그레이션 계획

#### Phase 1: POC 및 검증 (1주)
- 개발 환경에서 Kinesis/Firehose 테스트
- 단일 파일 버전으로 기본 기능 검증
- 성능 및 비용 분석

#### Phase 2: 모듈화 및 하이브리드 운영 (2주)
- 코드를 모듈화된 구조로 리팩토링
- 기존 배치와 스트리밍 병렬 운영
- 데이터 일관성 검증
- 모니터링 대시보드 구축

#### Phase 3: 전면 전환 (1주)
- 다운스트림 시스템 업데이트
- Athena 테이블 경로 변경
- 배치 방식 중단
- 프로덕션 모니터링 강화

### 7.2 실무 팁 및 주의사항

#### 비용 최적화 전략

**Kinesis Streams:**
- **On-Demand**: 트래픽이 불규칙하거나 초기 단계
  - 비용: $0.08/GB ingested + $0.04/GB retrieved
- **Provisioned**: 예측 가능한 트래픽
  - 비용: $0.015/shard-hour (약 $11/month per shard)
  - 1 shard = 1MB/sec 또는 1000 records/sec

**비용 예시 (월 1억 건 기준):**
- On-Demand: ~$300-500/month
- Provisioned (10 shards): ~$110/month + data transfer

#### 데이터 중복 처리

```python
# Kinesis 재시도로 인한 중복 방지
class DeduplicationHandler:
    def __init__(self, ttl_seconds=3600):
        self.seen_ids = {}
        self.ttl = ttl_seconds
    
    def is_duplicate(self, event_id: str) -> bool:
        now = time.time()
        
        # 만료된 항목 제거
        self.seen_ids = {
            k: v for k, v in self.seen_ids.items() 
            if now - v < self.ttl
        }
        
        # 중복 확인
        if event_id in self.seen_ids:
            return True
        
        self.seen_ids[event_id] = now
        return False
```

#### 모니터링 필수 메트릭

```python
# CloudWatch 커스텀 메트릭 전송
import boto3

cloudwatch = boto3.client('cloudwatch')

def send_metrics(success_count, error_count):
    cloudwatch.put_metric_data(
        Namespace='CAPA/LogGenerator',
        MetricData=[
            {
                'MetricName': 'LogsGenerated',
                'Value': success_count,
                'Unit': 'Count'
            },
            {
                'MetricName': 'LogErrors',
                'Value': error_count,
                'Unit': 'Count'
            }
        ]
    )
```

#### 성능 최적화 팁

1. **배치 처리 활용**
   - 개별 put_record 대신 put_records 사용
   - 최대 500건씩 배치 처리

2. **파티션 키 최적화**
   - Hot partition 방지를 위해 균등 분산
   - user_id + timestamp 조합 사용

3. **에러 핸들링**
   - Exponential backoff로 재시도
   - DLQ(Dead Letter Queue) 구현

## 8. 환경 변수 설정

```bash
# .env 파일 예시
ENABLE_KINESIS=true
KINESIS_STREAM_NAME=capa-ad-logs-prod
AWS_REGION=ap-northeast-2
AWS_ACCESS_KEY_ID=your_access_key
AWS_SECRET_ACCESS_KEY=your_secret_key

# 실행 모드
EXECUTION_MODE=hybrid  # batch, streaming, hybrid

# 배치 설정 (hybrid 모드용)
BATCH_SIZE=10000
TARGET_FILE_SIZE_MB=150
```

## 9. 성능 비교

| 지표 | 배치 방식 | 스트리밍 방식 |
|------|----------|--------------|
| 데이터 지연시간 | 1시간 | 1-2분 |
| 처리량 | 높음 (대량 배치) | 중간 (실시간) |
| 데이터 손실 위험 | 있음 | 매우 낮음 |
| 운영 복잡도 | 낮음 | 중간 |
| 비용 | 낮음 | 중간-높음 |
| 확장성 | 수동 | 자동 |

## 10. 결론

Kinesis와 Firehose 통합은 실시간 데이터 처리와 안전성을 크게 향상시킵니다. 초기에는 하이브리드 모드로 시작하여 시스템 안정성을 확인한 후 완전한 스트리밍 모드로 전환하는 것을 권장합니다.
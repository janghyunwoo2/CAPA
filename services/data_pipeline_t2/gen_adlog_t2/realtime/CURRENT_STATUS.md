# 현재 상태 정리

## 로그 생성기 설정
- event_type 필드 없음
- impression, click, conversion 이벤트가 모두 하나의 Kinesis 스트림으로 전송

## S3 디렉토리 구조
```
s3://capa-data-lake-827913617635/raw/
└── year=2026/
    └── month=02/
        └── day=25/
            └── hour=14/
                ├── firehose-2026-02-25-14-00-00-xxxxx.parquet
                └── firehose-2026-02-25-14-01-00-xxxxx.parquet
```

## Firehose 설정
- Stream: capa-firehose
- S3 Prefix: `raw/year=!{timestamp:yyyy}/month=!{timestamp:MM}/day=!{timestamp:dd}/hour=!{timestamp:HH}/`
- Format: Parquet
- Buffer: 60초 또는 1MB

## 데이터 확인
```bash
# S3 데이터 확인
python check_s3_single_path.py
```

## Athena 쿼리
모든 이벤트가 하나의 테이블에 저장되며, event_id로 구분:

```sql
-- 테이블 생성
CREATE EXTERNAL TABLE IF NOT EXISTS ad_logs (
    event_id string,
    timestamp bigint,
    impression_id string,
    click_id string,
    conversion_id string,
    user_id string,
    ad_id string,
    campaign_id string,
    advertiser_id string,
    -- 기타 필드
)
PARTITIONED BY (
    year int,
    month int,  
    day int,
    hour int
)
STORED AS PARQUET
LOCATION 's3://capa-data-lake-827913617635/raw/';

-- impressions 조회 (impression_id가 있는 레코드)
SELECT * FROM ad_logs
WHERE impression_id IS NOT NULL
  AND click_id IS NULL
  AND conversion_id IS NULL
  AND year = 2026 AND month = 2 AND day = 25;

-- clicks 조회 (click_id가 있는 레코드)  
SELECT * FROM ad_logs
WHERE click_id IS NOT NULL
  AND year = 2026 AND month = 2 AND day = 25;

-- conversions 조회 (conversion_id가 있는 레코드)
SELECT * FROM ad_logs  
WHERE conversion_id IS NOT NULL
  AND year = 2026 AND month = 2 AND day = 25;
```
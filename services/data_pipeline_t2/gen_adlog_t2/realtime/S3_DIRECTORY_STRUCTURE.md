# S3 디렉토리 구조 가이드

## 목표 구조

ad_log_generator.py와 동일한 S3 구조를 사용합니다:

```
s3://capa-data-lake-827913617635/raw/
├── impressions/
│   └── year=2026/
│       └── month=02/
│           └── day=25/
│               └── hour=14/
│                   ├── impressions_20260225_14_abc123.parquet.zstd
│                   └── firehose-2026-02-25-14-00-00-xxxxx.parquet
├── clicks/
│   └── year=2026/
│       └── month=02/
│           └── day=25/
│               └── hour=14/
│                   └── clicks_20260225_14_def456.parquet.zstd
└── conversions/
    └── year=2026/
        └── month=02/
            └── day=25/
                └── hour=14/
                    └── conversions_20260225_14_ghi789.parquet.zstd
```

## 설정 완료 사항

### 1. generator.py에서 event_type 필드
- `impressions`: 노출 이벤트
- `clicks`: 클릭 이벤트  
- `conversions`: 전환 이벤트

### 2. 필요한 Firehose 설정

AWS Console에서 `capa-firehose` 수정:

1. **Dynamic Partitioning 활성화**
   - Enable Dynamic Partitioning: `Yes`

2. **S3 Prefix 설정**
   ```
   raw/!{partitionKeyFromQuery:event_type}/year=!{timestamp:yyyy}/month=!{timestamp:MM}/day=!{timestamp:dd}/hour=!{timestamp:HH}/
   ```

3. **Processing Configuration**
   - Type: MetadataExtraction
   - JsonParsingEngine: JQ-1.6
   - MetadataExtractionQuery: `{event_type: .event_type}`

4. **Error Output Prefix**
   ```
   errors/!{firehose:error-output-type}/year=!{timestamp:yyyy}/month=!{timestamp:MM}/day=!{timestamp:dd}/
   ```

## 데이터 확인 방법

### 1. S3 데이터 확인
```bash
# 새로운 확인 스크립트 실행
python check_s3_data_v2.py
```

### 2. AWS CLI로 확인
```bash
# impressions 확인
aws s3 ls s3://capa-data-lake-827913617635/raw/impressions/ --recursive

# clicks 확인
aws s3 ls s3://capa-data-lake-827913617635/raw/clicks/ --recursive

# conversions 확인
aws s3 ls s3://capa-data-lake-827913617635/raw/conversions/ --recursive
```

### 3. Athena 쿼리
```sql
-- 오늘의 impressions 카운트
SELECT COUNT(*) as impression_count
FROM impressions
WHERE year = 2026 AND month = 2 AND day = 25;

-- 시간별 이벤트 카운트
SELECT 
    hour,
    COUNT(*) as event_count
FROM impressions
WHERE year = 2026 AND month = 2 AND day = 25
GROUP BY hour
ORDER BY hour;
```

## 주의사항

1. **Buffer Time**: Firehose는 60초마다 또는 1MB가 쌓이면 S3에 씁니다
2. **파일 형식**: Parquet 형식으로 자동 변환됩니다
3. **파티션**: year, month, day, hour로 파티셔닝되어 쿼리 성능이 향상됩니다
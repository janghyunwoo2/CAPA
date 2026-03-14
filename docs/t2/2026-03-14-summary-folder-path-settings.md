# Summary 폴더 경로 설정 현황 분석

**작성일**: 2026-03-14  
**목적**: summary 폴더로 경로가 설정된 모든 파일과 설정 내용 정리

---

## 📋 요약

현재 CAPA 프로젝트에서 summary 폴더는 ETL 프로세스의 결과물(Parquet 파일)을 저장하는 용도로 사용되고 있으며, 다음 두 개의 테이블 데이터가 저장됩니다:
- `ad_combined_log`: 시간별 요약 데이터
- `ad_combined_log_summary`: 일별 요약 데이터

---

## 🗂️ Summary 폴더 경로가 설정된 파일 목록

### 1. **설정 파일 (Config Files)**

#### 📄 services/data_pipeline_t2/etl_summary_t2/config.py
```python
# 라인 47-48: 테이블별 S3 경로
S3_PATHS = {
    "impressions": f"s3://{S3_BUCKET}/{RAW_DATA_PREFIX}/impressions",
    "clicks": f"s3://{S3_BUCKET}/{RAW_DATA_PREFIX}/clicks",
    "conversions": f"s3://{S3_BUCKET}/{RAW_DATA_PREFIX}/conversions",
    "ad_combined_log": f"s3://{S3_BUCKET}/summary/ad_combined_log",  # ✅ summary 폴더에 저장
    "ad_combined_log_summary": f"s3://{S3_BUCKET}/summary/ad_combined_log_summary"  # ✅ summary 폴더에 저장
}

# 라인 52-53: S3 파티셔닝 경로
SUMMARY_HOURLY_PATH = f"s3://{S3_BUCKET}/summary/ad_combined_log"  # ✅ summary 폴더 추가
SUMMARY_DAILY_PATH = f"s3://{S3_BUCKET}/summary/ad_combined_log_summary"  # ✅ summary 폴더 추가

# 버킷명: capa-data-lake-827913617635
```

#### 📄 services/data_pipeline_t2/dags/etl_modules/config.py
```python
# 동일한 설정 (위와 완전 동일)
S3_PATHS = {
    "ad_combined_log": f"s3://{S3_BUCKET}/summary/ad_combined_log",
    "ad_combined_log_summary": f"s3://{S3_BUCKET}/summary/ad_combined_log_summary"
}

SUMMARY_HOURLY_PATH = f"s3://{S3_BUCKET}/summary/ad_combined_log"
SUMMARY_DAILY_PATH = f"s3://{S3_BUCKET}/summary/ad_combined_log_summary"
```

### 2. **ETL 처리 파일 (ETL Processing Files)**

#### 📄 services/data_pipeline_t2/etl_summary_t2/hourly_etl.py
```python
# 라인 19: import
from .config import DATABASE, S3_PATHS, PARTITION_FORMATS, SUMMARY_HOURLY_PATH, AWS_REGION, ATHENA_OUTPUT_LOCATION

# 라인 195: 테이블 생성 시 LOCATION 지정
LOCATION '{S3_PATHS["ad_combined_log"]}'  # → s3://capa-data-lake-827913617635/summary/ad_combined_log

# 라인 217: 파티션 경로 생성
s3_partition_path = f"{S3_PATHS['ad_combined_log']}/year={self.year}/month={self.month}/day={self.day}/hour={self.hour}/"

# 라인 318: 버킷명 추출
bucket_name = S3_PATHS['ad_combined_log'].split('/')[2]
```

#### 📄 services/data_pipeline_t2/etl_summary_t2/daily_etl.py
```python
# 라인 228: 테이블 생성 시 LOCATION 지정
LOCATION '{S3_PATHS["ad_combined_log_summary"]}'  # → s3://capa-data-lake-827913617635/summary/ad_combined_log_summary

# 라인 250: 파티션 경로 생성
s3_partition_path = f"{S3_PATHS['ad_combined_log_summary']}/year={self.year}/month={self.month}/day={self.day}/"

# 라인 382: 버킷명 추출
bucket_name = S3_PATHS['ad_combined_log_summary'].split('/')[2]
```

### 3. **DAG 파일들 (Airflow DAG Files)**

- **01_ad_hourly_summary.py**: "S3 Parquet (summary/ad_combined_log/)" 언급
- **02_ad_daily_summary.py**: "S3 Parquet (summary/ad_combined_log_summary/)" 언급
- **05_ad_hourly_summary_period.py**: `HOURLY_SUMMARY_PATH = f"s3://{S3_BUCKET}/ad_combined_log"` (summary 없음)

---

## 🔍 Athena 쿼리 결과 저장 경로 (CSV/Metadata 문제와 관련)

### OutputLocation 설정
```python
# config.py (두 파일 모두 동일)
ATHENA_TEMP_RESULTS_PATH = f"s3://{S3_BUCKET}/.athena-temp/"  # ✅ 격리된 경로

# athena_utils.py에서 사용
ResultConfiguration={'OutputLocation': ATHENA_TEMP_RESULTS_PATH}
```

**중요**: Athena 쿼리 결과는 `.athena-temp/` 경로에 저장되도록 설정되어 있으며, summary 폴더와는 별도입니다.

---

## 📊 S3 폴더 구조

```
s3://capa-data-lake-827913617635/
├── raw/                           # 원시 데이터
│   ├── impressions/
│   ├── clicks/
│   └── conversions/
├── summary/                       # ETL 결과 (Parquet)
│   ├── ad_combined_log/          # 시간별 요약
│   │   └── year=2026/month=03/day=14/hour=10/
│   │       └── ad_combined_log.parquet
│   └── ad_combined_log_summary/  # 일별 요약
│       └── year=2026/month=03/day=14/
│           └── ad_combined_log_summary.parquet
└── .athena-temp/                 # Athena 쿼리 임시 결과
    ├── {query_id}.csv
    └── {query_id}.csv.metadata
```

---

## ⚠️ 확인 필요 사항

1. **CSV/Metadata 파일 위치**:
   - 설정상으로는 `.athena-temp/`에 저장되어야 함
   - 하지만 사용자 보고에 따르면 `summary/` 폴더에 쌓이고 있음
   - AWS 콘솔 설정과 코드 설정의 불일치 가능성

2. **05_ad_hourly_summary_period.py**:
   ```python
   HOURLY_SUMMARY_PATH = f"s3://{S3_BUCKET}/ad_combined_log"  # summary 없음
   ```
   - 이 DAG만 summary 폴더를 사용하지 않음
   - 의도적인지 확인 필요

3. **중복 파일**:
   - `etl_summary_t2/`와 `dags/etl_modules/` 폴더에 동일한 파일들이 중복 존재
   - 관리 복잡성 증가

---

## 🎯 권장 사항

1. **즉시 확인**:
   - AWS Athena 콘솔에서 실제 Query result location 확인
   - 워크그룹 설정이 코드 설정을 덮어쓰고 있는지 확인

2. **코드 정리**:
   - 중복된 config 파일 통합 고려
   - 05_ad_hourly_summary_period.py의 경로 일관성 확인

3. **모니터링**:
   - S3 Browser에서 실제로 어느 경로에 CSV가 생성되는지 확인
   - CloudWatch Logs에서 ETL 실행 시 로그 확인
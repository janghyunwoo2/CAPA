# CAPA 광고 데이터 파이프라인 구동 방식

최종 업데이트: 2026-03-12 16:48

## 📋 Overview

CAPA 광고 데이터 파이프라인은 실시간 광고 로그를 수집, 처리, 분석하는 엔드투엔드 시스템입니다.

## 🏗️ 시스템 아키텍처

### 1. 데이터 수집 (Raw Data Collection)
```
광고 로그 → Kinesis Data Firehose → S3 (Parquet 형식)
```

- **로그 타입**: impressions, clicks, conversions
- **저장 경로**: `s3://capa-data-lake-827913617635/raw/{log_type}/`
- **형식**: Parquet (ZSTD 압축)
- **파티셔닝**: year/month/day/hour

### 2. ETL 처리 (Summary Generation)

#### Hourly ETL (시간별 집계)
- **실행 주기**: 매시 10분 (UTC)
- **처리 내용**: impressions + clicks 조인
- **출력 테이블**: `ad_combined_log`
- **저장 경로**: `s3://capa-data-lake-827913617635/ad_combined_log/`

#### Daily ETL (일별 집계)  
- **실행 주기**: 매일 02:00 (UTC)
- **처리 내용**: 24시간 hourly 데이터 + conversions 조인
- **출력 테이블**: `ad_combined_log_summary`
- **저장 경로**: `s3://capa-data-lake-827913617635/ad_combined_log_summary/`

## 🚀 실행 방법

### 1. 로컬 개발 환경

#### ETL 직접 실행
```powershell
# data_pipeline_t2 디렉토리에서 실행
cd services/data_pipeline_t2

# Hourly ETL 실행
python -m etl_summary_t2.run_etl hourly --target-hour "2026-03-12 15:00:00"

# Daily ETL 실행
python -m etl_summary_t2.run_etl daily --target-date 2026-03-12

# 백필 실행 (과거 데이터 재처리)
python -m etl_summary_t2.run_etl backfill --start-date 2026-03-01 --end-date 2026-03-12 --type daily
```

### 2. Airflow 환경

#### DAG 구성
- `03_ad_hourly_summary`: Hourly ETL (매시 10분 실행)
- `04_ad_daily_summary`: Daily ETL (매일 02:00 실행) 
- `03_ad_hourly_summary_test`: 수동 테스트용
- `04_ad_daily_summary_test`: 수동 테스트용

#### 환경 설정
```bash
# Airflow 환경변수
export AIRFLOW_HOME=/path/to/airflow
export USE_KPO=false  # 로컬: false, K8s: true

# DAG 복사
cp services/data_pipeline_t2/dags/*.py $AIRFLOW_HOME/dags/
```

## 🔧 주요 구성 요소

### 1. ETL 패키지 (`etl_summary_t2`)
- **hourly_etl.py**: 시간별 집계 로직
- **daily_etl.py**: 일별 집계 로직  
- **athena_utils.py**: Athena 쿼리 실행 유틸리티
- **config.py**: AWS 설정 및 테이블 스키마

### 2. 시간대 처리
- **Airflow**: UTC 기준으로 스케줄 관리
- **ETL 로직**: KST 시간대로 변환하여 처리
- **S3 파티션**: KST 기준 year/month/day/hour

### 3. 테이블 스키마

#### ad_combined_log (Hourly)
| 컬럼명 | 타입 | 설명 |
|--------|------|------|
| campaign_id | string | 캠페인 ID |
| device_type | string | 디바이스 유형 |
| dt | string | 집계 시간 (YYYY-MM-DD-HH) |
| impressions | bigint | 노출 수 |
| clicks | bigint | 클릭 수 |
| ctr | double | 클릭률 (%) |
| year, month, day, hour | string | 파티션 키 |

#### ad_combined_log_summary (Daily)
| 컬럼명 | 타입 | 설명 |
|--------|------|------|
| campaign_id | string | 캠페인 ID |
| device_type | string | 디바이스 유형 |  
| impression_count | bigint | 일별 총 노출 수 |
| click_count | bigint | 일별 총 클릭 수 |
| conversion_count | bigint | 일별 총 전환 수 |
| ctr | double | 일별 클릭률 (%) |
| cvr | double | 일별 전환율 (%) |
| year, month, day | string | 파티션 키 |

## 🐛 문제 해결

### 1. ModuleNotFoundError
```powershell
# pyproject.toml이 있는 디렉토리에서
cd services/data_pipeline_t2
uv pip install -e .
```

### 2. Athena 파티션 인식 오류
```sql
-- 파티션 메타데이터 갱신
MSCK REPAIR TABLE database.table_name;
```

### 3. 시간대 관련 오류
- Airflow 스케줄러는 UTC 기준
- ETL 로직 내부에서 KST로 변환하여 처리
- S3 파티션은 KST 기준으로 저장

## 📚 참고 문서

- [ETL 구현 가이드](etl_summary.md)
- [Airflow DAG 구성](etl_summary_airflow_dag.md)
- [문제 해결 타임라인](2026-03-10_hourly_etl_complete_troubleshooting_timeline.md)
- [시간대 처리 분석](2026-03-12-1529_airflow_etl_시간대처리_분석.md)
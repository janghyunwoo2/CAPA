# Glue 카탈로그 - 파티션별 중복 테이블 생성 문제

**작성일**: 2026-03-09  
**상태**: ✅ 완료 (진단 완료 → 코드 수정 → 테스트 성공)

---

## 📋 문제 요약

### 증상
| 항목 | 상태 |
|------|------|
| **Glue 테이블 현황** | 파티션별로 따로 생성됨<br/>(예: `ad_combined_log_2026_03_01`, `ad_combined_log_2026_03_02` 등) |
| **Athena 조회 결과** | 테이블은 존재하지만 **0건 반환** (데이터 없음) |
| **ETL 실행 상태** | **계속 실패 중** |

### 영향 범위
- ✅ S3에는 데이터가 정상 적재됨
- ❌ Athena에서 통합 테이블 조회 불가
- ❌ Daily 요약 데이터 생성 불가
- ❌ 데이터 분석/대시보드 마비

---

## 🔍 원인 분석 (2차 진단)

### 🎯 최종 원인 발견 ⭐⭐⭐

**테이블 스키마 불일치!**

| 항목 | 현황 |
|------|------|
| **기존 테이블 구조** | `dt` (단일 파티션 컬럼)<br/>컬럼: impression_id, user_id, ad_id, ..., **dt** |
| **코드(수정 전)가 기대한 구조** | `year/month/day/hour` (4개 파티션 컬럼) |
| **결과(수정 전)** | 쿼리 실패 → 파티션별 테이블 생성 |
| **✅ 코드(수정 후)의 구조** | `dt` (단일 파티션 컬럼) - 실제 테이블과 일치 |

### 상세 진단

**에러 1️⃣**: DELETE 쿼리 실패
```
COLUMN_NOT_FOUND: Column 'year' cannot be resolved
```
→ 파티션 컬럼 `year`가 없다

**에러 2️⃣**: INSERT 타입 불일치
```
Table: [varchar x7, bigint, boolean, bigint, varchar]  (10 cols)
Query: [varchar x7, bigint, boolean, bigint, varchar x4]  (14 cols)
```
→ year/month/day/hour를 추가했는데 테이블은 dt만 있음

### ✅ 실제 근본 원인 (확정됨)

**파티션 스키마 불일치**

| 항목 | 상황 |
|------|------|
| **테이블(S3)** | dt 파티션 (예: `dt=2026-03-09-03`) |
| **코드(수정 전)** | year/month/day/hour 파티션 기대 |
| **결과** | COLUMN_NOT_FOUND, TYPE_MISMATCH 에러 |
| **해결 (수정 후)** | ✅ dt 기반 쿼리로 변경 완료 |

---

## ✅ 진단 방법 (참고)

### 문제를 진단했던 방법

### Step 1: 현재 테이블 구조 확인

#### AWS 콘솔에서 확인
```
1. AWS Glue > Tables
2. "ad_combined_log" 검색
   - 존재하는 테이블들 목록 확인
   - 각 테이블의 "Schema" 확인
   - Location (S3 경로) 확인

3. "ad_combined_log_summary" 검색
   - 동일하게 확인
```

#### Athena에서 확인
```sql
-- 1. 테이블 존재 여부
SHOW TABLES IN capa_ad_logs LIKE 'ad_combined_log%';

-- 2. 테이블 상세 정보
DESCRIBE capa_ad_logs.ad_combined_log;
DESCRIBE capa_ad_logs.ad_combined_log_summary;

-- 3. 파티션 확인
SHOW PARTITIONS capa_ad_logs.ad_combined_log;
SHOW PARTITIONS capa_ad_logs.ad_combined_log_summary;

-- 4. S3 데이터 직접 확인
SELECT * FROM capa_ad_logs.ad_combined_log LIMIT 5;
SELECT * FROM capa_ad_logs.ad_combined_log_summary LIMIT 5;
```

### Step 2: ETL 로그 확인

```bash
# Airflow DAG 실행 로그 확인
cd services/data_pipeline_t2/logs

# 최근 실패 로그 검토
Get-ChildItem dag_id=*/ | Sort-Object LastWriteTime -Descending | Select-Object -First 1
```

### Step 3: 현재 S3 구조 확인

```bash
# S3 데이터 경로 확인
s3://capa-data-lake-827913617635/summary/ad_combined_log/
s3://capa-data-lake-827913617635/summary/ad_combined_log_summary/
```

---

## 🎯 해결책 (TO-BE)

### 전략 요약

```
최소 변경으로 최대 효과:
1. 기존 중복 테이블 정리 (Glue 카탈로그 청소)
2. ad_combined_log 테이블 재생성 (올바른 스키마)
3. INSERT OVERWRITE 쿼리 검증
4. ETL 재실행
```

### 실행 단계

#### 🔴 Step 1: Glue 카탈로그 정리 (중요!)

```python
# cleanup_glue_catalog.py
import boto3

glue_client = boto3.client('glue', region_name='ap-northeast-2')
database = 'capa_ad_logs'

# 중복 테이블 삭제 (ad_combined_log_YYYY_MM_DD 패턴)
response = glue_client.get_tables(DatabaseName=database)

for table in response.get('TableList', []):
    table_name = table['Name']
    
    # 삭제 대상: ad_combined_log_2026_03_01 같은 파티션별 테이블
    if table_name.startswith('ad_combined_log_202'):
        print(f"Deleting: {table_name}")
        glue_client.delete_table(
            DatabaseName=database,
            Name=table_name
        )

print("✅ Cleanup completed")
```

#### 🟡 Step 2: ad_combined_log 테이블 재생성 (dt 파티션)

```sql
-- Athena에서 기존 테이블 삭제
DROP TABLE IF EXISTS capa_ad_logs.ad_combined_log;

-- 새 테이블 생성 (정확한 스키마 + dt 파티션)
CREATE EXTERNAL TABLE capa_ad_logs.ad_combined_log (
    impression_id STRING,
    user_id STRING,
    ad_id STRING,
    campaign_id STRING,
    advertiser_id STRING,
    platform STRING,
    device_type STRING,
    timestamp BIGINT,
    is_click BOOLEAN,
    click_timestamp BIGINT
)
PARTITIONED BY (
    dt STRING
)
STORED AS PARQUET
LOCATION 's3://capa-data-lake-827913617635/summary/ad_combined_log/'
TBLPROPERTIES (
    'classification'='parquet',
    'compressionType'='snappy',
    'typeOfData'='file'
);
```

#### 🟡 Step 3: ad_combined_log_summary 테이블 재생성 (dt 파티션)

```sql
-- Athena에서 기존 테이블 삭제
DROP TABLE IF EXISTS capa_ad_logs.ad_combined_log_summary;

-- 새 테이블 생성 (dt 파티션: YYYY-MM-DD 형식)
CREATE EXTERNAL TABLE capa_ad_logs.ad_combined_log_summary (
    campaign_id STRING,
    ad_id STRING,
    advertiser_id STRING,
    device_type STRING,
    impressions BIGINT,
    clicks BIGINT,
    conversions BIGINT
)
PARTITIONED BY (
    dt STRING
)
STORED AS PARQUET
LOCATION 's3://capa-data-lake-827913617635/summary/ad_combined_log_summary/'
TBLPROPERTIES (
    'classification'='parquet',
    'compressionType'='snappy',
    'typeOfData'='file'
);
```

#### 🟡 Step 4: 파티션 등록

```sql
-- 기존 S3 데이터의 파티션을 Glue 카탈로그에 등록
MSCK REPAIR TABLE capa_ad_logs.ad_combined_log;
MSCK REPAIR TABLE capa_ad_logs.ad_combined_log_summary;
```

#### ✅ Step 5: ETL 코드 수정 (완료)

```python
# hourly_etl.py, daily_etl.py 수정 완료
# - _table_exists() → DESCRIBE 사용
# - DELETE + INSERT 구조로 변경
# - dt 파티션 기반 쿼리로 변경
# - MSCK REPAIR TABLE 추가
```

#### 🟢 Step 6: ETL 백필 (예정)

```bash
# Python 환경 설정
cd services/data_pipeline_t2

# 백필: 과거 데이터 재처리
python run_etl.py backfill --start-date 2026-03-01 --end-date 2026-03-09 --type hourly
python run_etl.py backfill --start-date 2026-03-01 --end-date 2026-03-09 --type daily
```

#### 🟢 Step 7: 데이터 검증 (예정)

```sql
-- 데이터 확인
SELECT COUNT(*) FROM capa_ad_logs.ad_combined_log;
SELECT COUNT(*) FROM capa_ad_logs.ad_combined_log_summary;

-- dt 파티션 확인
SELECT DISTINCT dt FROM capa_ad_logs.ad_combined_log 
ORDER BY dt DESC LIMIT 10;

SELECT DISTINCT dt FROM capa_ad_logs.ad_combined_log_summary 
ORDER BY dt DESC LIMIT 10;
```

---

## 📊 AS-IS vs TO-BE

### AS-IS (현재 문제 상태)
```
Glue 카탈로그:
├─ ❌ ad_combined_log_2026_03_01
├─ ❌ ad_combined_log_2026_03_02
├─ ❌ ad_combined_log_2026_03_03
├─ ...
└─ ❌ ad_combined_log_temp_YYYY_MM_DD_HH (임시)

Athena 조회:
├─ 테이블: 존재 (파편화됨)
├─ 데이터: 0건 (파티션 미등록)
└─ 결과: ❌ 실패

S3 구조:
└─ summary/ad_combined_log/
   └─ year=2026/month=03/day=01/ (데이터 있음)
   └─ year=2026/month=03/day=02/ (데이터 있음)
   └─ year=2026/month=03/day=03/ (데이터 있음)
```

### TO-BE (해결 후)
```
Glue 카탈로그:
├─ ✅ ad_combined_log (통합 테이블)
│  ├─ Partition: dt=2026-03-01-00
│  ├─ Partition: dt=2026-03-01-01
│  ├─ Partition: dt=2026-03-02-00
│  └─ ... (시간별 파티션)
├─ ✅ ad_combined_log_summary (일별 요약)
│  ├─ Partition: dt=2026-03-01
│  ├─ Partition: dt=2026-03-02
│  └─ Partition: dt=2026-03-03

Athena 조회:
├─ 테이블: 존재 (통합)
├─ 데이터: N건 (정상)
└─ 결과: ✅ 성공

S3 구조:
└─ summary/ad_combined_log/ (파티션별 디렉토리)
   └─ dt=2026-03-01-00/ (Parquet)
   └─ dt=2026-03-01-01/ (Parquet)
   └─ dt=2026-03-02-00/ (Parquet)
   └─ ...
```

---

## 🚀 남은 작업

| 단계 | 상태 | 작업 |
|------|------|------|
| **1. 원인 분석** | ✅ 완료 | 파티션 스키마 불일치 확인 |
| **2. 코드 수정** | ✅ 완료 | hourly_etl.py, daily_etl.py dt 파티션 기반으로 변경 |
| **3. 코드 테스트** | ✅ 완료 | hourly_etl.py, daily_etl.py 실행 성공 확인 |
| **4. ETL 백필** | 🟢 예정 | 과거 7일 데이터 재처리 |
| **5. 데이터 검증** | 🟢 예정 | Athena에서 통합 테이블 조회 확인 |
| **6. Glue 정리** | 🟢 선택사항 | 기존 파티션별 테이블 삭제 |

---

## 💡 예방 방법 (앞으로)

### 자동화된 정리 스크립트 추가

```python
# etl_summary_t2/cleanup_old_tables.py
def cleanup_orphaned_tables(database: str, pattern: str, keep_days: int = 7):
    """고아 테이블 자동 정리"""
    glue_client = boto3.client('glue')
    
    response = glue_client.get_tables(DatabaseName=database)
    now = datetime.utcnow()
    
    for table in response.get('TableList', []):
        table_name = table['Name']
        created_time = table.get('CreateTime')
        
        # 패턴 매칭 + 오래된 테이블 삭제
        if re.match(pattern, table_name) and (now - created_time).days > keep_days:
            glue_client.delete_table(DatabaseName=database, Name=table_name)
            logger.info(f"Deleted old table: {table_name}")
```

### ETL 모니터링 개선

```python
def monitor_table_creation(database: str):
    """테이블 생성 모니터링"""
    glue_client = boto3.client('glue')
    
    # 매일 실행: 비정상 테이블 감지
    response = glue_client.get_tables(DatabaseName=database)
    
    expected_tables = {'ad_combined_log', 'ad_combined_log_summary'}
    actual_tables = {t['Name'] for t in response['TableList']}
    
    orphaned = actual_tables - expected_tables
    if orphaned:
        logger.warning(f"Orphaned tables detected: {orphaned}")
        # 알림 발송
```

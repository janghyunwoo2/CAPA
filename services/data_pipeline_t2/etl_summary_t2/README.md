# ETL Summary T2 - 사용법 가이드

광고 로그 데이터를 S3에서 조회하여 summary 테이블로 집계하는 ETL 패키지입니다.

---

## 📋 목차

1. [개요](#개요)
2. [구조 및 파일 설명](#구조-및-파일-설명)
3. [설치 및 환경 설정](#설치-및-환경-설정)
4. [사용 방법](#사용-방법)
5. [각 모듈 상세 사용법](#각-모듈-상세-사용법)
6. [예제](#예제)
7. [트러블슈팅](#트러블슈팅)

---

## 🚀 빠른 시작 (Quick Start)

```powershell
# 1. 올바른 디렉토리로 이동 (매우 중요!)
cd C:\Users\Dell5371\Desktop\projects\CAPA\services\data_pipeline_t2

# 2. 패키지 설치 (처음 1회만)
pip install -e .

# 3. 의존성 설치
pip install -r etl_summary_t2/requirements.txt

# 4. AWS 자격증명 설정
# services/data_pipeline_t2/.env 파일 생성하고 다음 입력:
# AWS_ACCESS_KEY_ID=AKIA...
# AWS_SECRET_ACCESS_KEY=...
# AWS_DEFAULT_REGION=ap-northeast-2

# 5. 테스트 실행
python -m etl_summary_t2.run_etl hourly

# 출력이 다음처럼 나오면 성공:
# Processing hour: 2026-03-10-14
# ✅ Table exists
```

---

## 개요

### 목적
- **Hourly ETL**: impressions + clicks 조인 → `ad_combined_log` (시간별 생성)
- **Daily ETL**: ad_combined_log + conversions 조인 → `ad_combined_log_summary` (일별 생성)

### 특징
- ✅ Athena 기반 데이터 쿼리
- ✅ PyArrow로 Parquet 형식 저장
- ✅ S3 파티션 자동 갱신 (MSCK REPAIR)
- ✅ 타입 안정성 (명시적 스키마 정의)
- ✅ 재시도 로직 포함

### 데이터 흐름

```
Raw Data (S3)
├── raw/impressions/year=.../hour=.../ (Kinesis Firehose)
├── raw/clicks/year=.../hour=.../
└── raw/conversions/year=.../hour=.../

             ↓ (Hourly ETL)

Summary Data (S3)
├── summary/ad_combined_log/year=/month=/day=/hour=/ (27 columns)
│   └── ad_combined_log.parquet (impression + click JOIN)
│
└── summary/ad_combined_log_summary/year=/month=/day=/ (35 columns)
    └── ad_combined_log_summary.parquet (hourly + conversion JOIN)
```

---

## 구조 및 파일 설명

### 파일 구조

```
etl_summary_t2/
├── __init__.py                 # 패키지 초기화
├── config.py                   # AWS, S3, Athena 설정
├── athena_utils.py             # Athena 쿼리 실행 유틸리티
├── hourly_etl.py               # 시간별 ETL 클래스
├── daily_etl.py                # 일별 ETL 클래스
├── run_etl.py                  # 통합 실행 스크립트
├── requirements.txt            # 파이썬 패키지 의존성
├── SUMMARY_QUERIES.md          # SQL 쿼리 참고
└── README.md                   # 이 파일
```

### 각 파일 설명

| 파일 | 역할 | 주요 내용 |
|------|------|---------|
| **config.py** | 설정 파일 | AWS 자격증명, S3 경로, Athena 설정 |
| **athena_utils.py** | 유틸리티 | Athena 쿼리 실행, 상태 확인, 결과 조회 |
| **hourly_etl.py** | Hourly ETL | impression + click 조인 |
| **daily_etl.py** | Daily ETL | hourly + conversion 조인 |
| **run_etl.py** | 실행 스크립트 | CLI 진입점, 백필 등 |
| **__init__.py** | 패키지 정의 | 공개 인터페이스 정의 |

---

## 설치 및 환경 설정

### ⚠️ 먼저 수행할 작업

```bash
# 프로젝트 루트 디렉토리로 이동
cd c:\Users\Dell5371\Desktop\projects\CAPA

# 또는 프롬프트에 표시된 위치에서 상대 경로 사용
cd services/data_pipeline_t2
```

### 1️⃣ 패키지 설치

```bash
# services/data_pipeline_t2/ 디렉토리에서 실행
cd services/data_pipeline_t2

# uv 사용 (권장)
uv pip install -e .

# 또는 pip 사용
pip install -e .
```

### 2️⃣ 의존성 설치

```bash
# requirements.txt에서 의존성 설치
uv pip install -r etl_summary_t2/requirements.txt

# 주요 패키지
# - boto3 >= 1.26.0 (AWS SDK)
# - botocore >= 1.29.0 (AWS SDK 코어)
# - python-dotenv >= 0.19.0 (.env 파일 로드)
# - pandas, pyarrow, pyathena (데이터 처리)
```

### 3️⃣ 설치 확인

```bash
# 패키지가 제대로 설치되었는지 확인
python -c "import etl_summary_t2; print('✅ Package installed successfully')"
```

### 4️⃣ AWS 자격증명 설정

#### 방법 A: .env 파일 (권장)

```bash
# services/data_pipeline_t2/.env 생성
AWS_ACCESS_KEY_ID=AKIA...
AWS_SECRET_ACCESS_KEY=...
AWS_DEFAULT_REGION=ap-northeast-2
```

#### 방법 B: 환경 변수

```powershell
# PowerShell에서 실행
$env:AWS_ACCESS_KEY_ID="AKIA..."
$env:AWS_SECRET_ACCESS_KEY="..."
$env:AWS_DEFAULT_REGION="ap-northeast-2"
```

#### 방법 C: AWS CLI 프로필

```bash
aws configure --profile capa
export AWS_PROFILE=capa
```

### 5️⃣ config.py 설정 확인

```python
# services/data_pipeline_t2/etl_summary_t2/config.py
AWS_REGION = "ap-northeast-2"
S3_BUCKET = "capa-data-lake-827913617635"
DATABASE = "capa_ad_logs"
ATHENA_OUTPUT_LOCATION = "s3://bucket/athena-results/"
```

---

## 사용 방법

### 기본 명령어

**⚠️ 중요**: 다음 명령들은 `services/data_pipeline_t2/` 디렉토리에서 실행해야 합니다.

```bash
cd services/data_pipeline_t2
```

#### Hourly ETL 실행

```bash
# 직전 시간 데이터 처리
python -m etl_summary_t2.run_etl hourly

# 특정 시간 데이터 처리
python -m etl_summary_t2.run_etl hourly --target-hour 2026-03-10-14
```

#### Daily ETL 실행

```bash
# 어제 데이터 처리
python -m etl_summary_t2.run_etl daily

# 특정 날짜 데이터 처리
python -m etl_summary_t2.run_etl daily --target-date 2026-03-09
```

#### 백필 (과거 데이터 재처리)

**⚠️ 중요: 백필 실행 순서**

Daily 백필은 hourly 데이터에 의존합니다. 따라서:
- ✅ **Daily 백필만 요청해도 자동으로 hourly 백필이 먼저 실행됨** (개선됨)
- ❌ 수동으로 hourly를 먼저 실행할 필요 없음

**의존 관계**:
```
hourly ETL (impressions + clicks → ad_combined_log)
    ↓ (필수!)
daily ETL (ad_combined_log + conversions → ad_combined_log_summary)
```

**⚠️ 먼저 다음 디렉토리로 이동**:
```bash
cd services/data_pipeline_t2
```

**가장 간단한 사용법 (자동 순서 조정)**:
```bash
# Daily 백필만 실행하면, 자동으로 hourly 백필이 먼저 실행됨
python -m etl_summary_t2.run_etl backfill --start-date 2026-03-01 --end-date 2026-03-10 --type daily
```

**수동으로 각각 실행하는 경우**:

Bash 사용 (Linux/Mac):
```bash
# 1단계: Hourly 백필 (2026-03-01 ~ 2026-03-10)
python -m etl_summary_t2.run_etl backfill \
  --start-date 2026-03-01 \
  --end-date 2026-03-10 \
  --type hourly

# 2단계: Daily 백필 (2026-03-01 ~ 2026-03-10)
python -m etl_summary_t2.run_etl backfill \
  --start-date 2026-03-01 \
  --end-date 2026-03-10 \
  --type daily
```

PowerShell 사용 (Windows):
```powershell
# 1단계: Hourly 백필 (2026-03-01 ~ 2026-03-10)
python -m etl_summary_t2.run_etl backfill `
  --start-date 2026-03-01 `
  --end-date 2026-03-10 `
  --type hourly

# 2단계: Daily 백필 (2026-03-01 ~ 2026-03-10)
python -m etl_summary_t2.run_etl backfill `
  --start-date 2026-03-01 `
  --end-date 2026-03-10 `
  --type daily
```

한 줄 명령 (모든 OS):
```bash
# 먼저 services/data_pipeline_t2 디렉토리로 이동
cd services/data_pipeline_t2

# 1단계: Hourly 백필
python -m etl_summary_t2.run_etl backfill --start-date 2026-03-01 --end-date 2026-03-10 --type hourly

# 2단계: Daily 백필
python -m etl_summary_t2.run_etl backfill --start-date 2026-03-01 --end-date 2026-03-10 --type daily
```

---

## 각 모듈 상세 사용법

### 1️⃣ config.py

**역할**: AWS 설정 및 S3 경로 중앙 관리

```python
from config import (
    DATABASE,           # Athena 데이터베이스명
    S3_PATHS,          # 테이블별 S3 경로
    ATHENA_OUTPUT_LOCATION,  # 쿼리 결과 저장 경로
    AWS_REGION,        # AWS 리전
    S3_BUCKET,         # S3 버킷명
)

# 사용 예시
print(S3_PATHS['ad_combined_log'])
# 출력: s3://bucket/summary/ad_combined_log
```

**수정 항목**:
- `S3_BUCKET`: 실제 버킷명 (기본값: capa-data-lake-827913617635)
- `AWS_REGION`: 리전 선택
- `DATABASE`: Athena 데이터베이스명

---

### 2️⃣ athena_utils.py

**역할**: Athena 쿼리 실행 및 관리

#### 주요 메서드

```python
from athena_utils import AthenaQueryExecutor

executor = AthenaQueryExecutor()

# 1. 쿼리 실행 (완료까지 대기)
query_id = executor.execute_query("""
    SELECT COUNT(*) FROM impressions
    WHERE year='2026' AND month='03' AND day='10'
""")

# 2. 결과 조회
results = executor.get_query_results(query_id)
for row in results:
    print(row)

# 3. 테이블 존재 여부 확인
try:
    check_id = executor.execute_query("DESCRIBE ad_combined_log")
    print("✅ Table exists")
except:
    print("❌ Table does not exist")
```

#### 재시도 로직

```python
# 최대 3회 재시도 (기본값)
# 각 재시도 간 30초 대기 (기본값)
# 타임아웃: 300초 (5분)

# config.py에서 수정 가능
MAX_RETRIES = 3
RETRY_DELAY_SECONDS = 30
QUERY_TIMEOUT_SECONDS = 300
```

---

### 3️⃣ hourly_etl.py

**역할**: 시간별 데이터 집계 (impression + click JOIN)

#### 기본 사용법

```python
from hourly_etl import HourlyETL
from datetime import datetime

# 방법 1: 기본값 (현재 시간 - 1시간)
etl = HourlyETL()
etl.run()

# 방법 2: 특정 시간 지정
target = datetime(2026, 3, 10, 14, 0, 0)  # 2026-03-10 14:00
etl = HourlyETL(target_hour=target)
etl.run()
```

#### 생성 테이블

| 컬럼 | 개수 | 출처 |
|------|------|------|
| impression_id, user_id, ... | 20 | impressions 테이블 |
| click_id, landing_page_url, ... | 6 | clicks 테이블 |
| is_click | 1 | impression과 click JOIN 여부 |
| year, month, day, hour | 4 | 파티션 키 |
| **합계** | **31** | - |

#### 저장 위치

```
s3://bucket/summary/ad_combined_log/
└── year=2026/month=03/day=10/hour=14/
    └── ad_combined_log.parquet
```

#### 데이터 처리 과정

```
1. 테이블 존재 여부 확인
   ↓
2. 없으면 CREATE EXTERNAL TABLE (1회만)
   ↓
3. SELECT 쿼리 실행 (impressions + clicks JOIN)
   ↓
4. Athena 메타데이터에서 결과 조회
   ↓
5. PyArrow로 Parquet 변환 (스키마 명시적 정의)
   ↓
6. S3에 업로드
   ↓
7. MSCK REPAIR TABLE (파티션 갱신)
   ↓
8. 결과 검증
```

---

### 4️⃣ daily_etl.py

**역할**: 일별 데이터 집계 (ad_combined_log + conversion JOIN)

#### 기본 사용법

```python
from daily_etl import DailyETL
from datetime import datetime

# 방법 1: 기본값 (어제)
etl = DailyETL()
etl.run()

# 방법 2: 특정 날짜 지정
target = datetime(2026, 3, 9, 0, 0, 0)  # 2026-03-09
etl = DailyETL(target_date=target)
etl.run()
```

#### 생성 테이블

| 컬럼 | 개수 | 출처 |
|------|------|------|
| impression_id, ... | 20 | hourly (impressions) |
| click_id, ... | 6 | hourly (clicks) |
| is_click | 1 | hourly |
| conversion_id, ... | 7 | conversions 테이블 |
| is_conversion | 1 | hourly와 conversion JOIN 여부 |
| year, month, day | 3 | 파티션 키 |
| **합계** | **38** | - |

#### 저장 위치

```
s3://bucket/summary/ad_combined_log_summary/
└── year=2026/month=03/day=09/
    └── ad_combined_log_summary.parquet
```

#### 특징

- ✅ 24시간 데이터 존재 여부 확인 (8시간 미만이면 경고)
- ✅ ad_combined_log (hourly, 24개)와 conversions 조인
- ✅ 매일 02:00 UTC에 실행 권장 (전날 데이터 완전 적재 후)

---

### 5️⃣ run_etl.py

**역할**: 통합 실행 스크립트 (CLI)

#### CLI 사용법

```bash
# 헬프 표시
python -m etl_summary_t2.run_etl --help

# Hourly 헬프
python -m etl_summary_t2.run_etl hourly --help

# Daily 헬프
python -m etl_summary_t2.run_etl daily --help
```

#### Python에서 직접 호출

```python
from run_etl import run_hourly, run_daily, run_backfill

# Hourly 실행
run_hourly()
run_hourly(target_hour="2026-03-10-14")

# Daily 실행
run_daily()
run_daily(target_date="2026-03-09")

# 백필 실행
run_backfill(
    start_date="2026-03-01",
    end_date="2026-03-10",
    etl_type="hourly"  # 또는 "daily"
)
```

---

## 예제

### 예제 1: 오늘의 Hourly ETL 실행

```bash
# 1. 올바른 디렉토리로 이동
cd C:\Users\Dell5371\Desktop\projects\CAPA\services\data_pipeline_t2

# 2. 직전 시간 데이터 처리
python -m etl_summary_t2.run_etl hourly

# 예상 출력:
# 2026-03-10 15:30:45 - HourlyETL - INFO - Processing hour: 2026-03-10-14
# 2026-03-10 15:30:46 - HourlyETL - INFO - ✅ Table exists
# 2026-03-10 15:30:47 - HourlyETL - INFO - Querying data...
# ...
# 2026-03-10 15:31:20 - HourlyETL - INFO - ✅ Hourly ETL completed
```

### 예제 2: 특정 날짜의 Daily ETL 실행

```bash
# services/data_pipeline_t2 디렉토리에서 실행
cd C:\Users\Dell5371\Desktop\projects\CAPA\services\data_pipeline_t2

python -m etl_summary_t2.run_etl daily --target-date 2026-03-09

# 결과: 2026-03-09의 모든 hourly 데이터(24개)를 하나의 daily 파일로 집계
# 저장 위치: s3://bucket/summary/ad_combined_log_summary/year=2026/month=03/day=09/
```

### 예제 3: Python 코드에서 사용

```python
from hourly_etl import HourlyETL
from datetime import datetime, timedelta

# 지난 일주일 Hourly ETL 재처리
today = datetime.now()
for i in range(7):
    target = today - timedelta(days=i)
    for hour in range(24):
        target_hour = target.replace(hour=hour)
        print(f"Processing {target_hour.strftime('%Y-%m-%d %H:00')}")
        
        etl = HourlyETL(target_hour=target_hour)
        etl.run()
```

### 예제 4: 에러 처리

```python
from hourly_etl import HourlyETL

try:
    etl = HourlyETL()
    etl.run()
except Exception as e:
    print(f"❌ ETL failed: {str(e)}")
    # 로그 파일 확인, AWS 권한 확인 등
```

---

## 트러블슈팅

### ❌ ModuleNotFoundError: No module named 'etl_summary_t2'

```
Error: ModuleNotFoundError: No module named 'etl_summary_t2'
```

**원인**: 현재 디렉토리가 잘못됨 또는 패키지가 설치되지 않음

**해결책**:
```powershell
# 1. 올바른 디렉토리로 이동 (매우 중요!)
cd C:\Users\Dell5371\Desktop\projects\CAPA\services\data_pipeline_t2

# 2. 패키지 설치 (처음 1회만)
pip install -e .

# 3. 다시 명령 실행
python -m etl_summary_t2.run_etl hourly
```

**확인 방법**:
```powershell
# 패키지가 제대로 설치되었는지 확인
python -c "import etl_summary_t2; print('✅ OK')"

# 현재 디렉토리 확인
pwd  # 또는 cd

# PYTHONPATH 확인
python -c "import sys; print(sys.path)"
```

---

### ❌ AWS 자격증명 오류

```
ERROR: AWS_ACCESS_KEY_ID not found
```

**해결책**:
```bash
# 1. .env 파일 확인
cat services/data_pipeline_t2/.env

# 2. 환경 변수 확인
echo $env:AWS_ACCESS_KEY_ID  # PowerShell
echo $AWS_ACCESS_KEY_ID      # bash

# 3. 자격증명 설정
export AWS_ACCESS_KEY_ID="AKIA..."
export AWS_SECRET_ACCESS_KEY="..."
```

### ❌ Athena 쿼리 타임아웃

```
Query timed out after 300 seconds
```

**해결책**:
- 쿼리 복잡도 확인
- S3 데이터 존재 여부 확인
- 네트워크 연결 확인

```python
# config.py에서 타임아웃 증가
QUERY_TIMEOUT_SECONDS = 600  # 10분
```

### ❌ 테이블 이미 존재 오류

```
CREATE TABLE failed: table already exists
```

**해결책**:
```sql
-- Athena에서 직접 실행
DROP TABLE IF EXISTS capa_ad_logs.ad_combined_log;
```

### ❌ S3 권한 부족

```
AccessDenied: Access Denied
```

**해결책**:
- IAM 권한 확인
- S3 버킷 정책 확인
- Athena 결과 저장 경로 권한 확인

### ℹ️ 로그 레벨 설정

```python
# config.py에서
LOG_LEVEL = "DEBUG"  # 또는 INFO, WARNING, ERROR
```

---

## Airflow 통합

### DAG 예제

```python
# airflow_dag.py
from airflow import DAG
from airflow.operators.python import PythonOperator
from datetime import datetime, timedelta

from etl_summary_t2.run_etl import run_hourly, run_daily

dag = DAG(
    'ad_summary_etl',
    start_date=datetime(2026, 3, 1),
    schedule_interval='0 * * * *',  # 매시간
)

hourly_task = PythonOperator(
    task_id='hourly_etl',
    python_callable=run_hourly,
    dag=dag,
)

daily_task = PythonOperator(
    task_id='daily_etl',
    python_callable=run_daily,
    dag=dag,
    execution_timeout=timedelta(minutes=30),
)
```

---

## 성능 최적화

### 1. 데이터 파티셔닝
- S3 경로: `year=/month=/day=/hour=/`
- Athena의 파티션 프루닝으로 스캔 데이터 최소화

### 2. Parquet 압축
- 형식: `parquet + snappy` (기본값)
- 저장 공간 ~80% 감소

### 3. 병렬 처리
```python
# 여러 시간을 동시에 처리
from concurrent.futures import ThreadPoolExecutor

def process_hours():
    with ThreadPoolExecutor(max_workers=4) as executor:
        for hour in range(24):
            executor.submit(run_hourly, f"2026-03-10-{hour:02d}")

process_hours()
```

---

## 참고 자료

- [SUMMARY_QUERIES.md](SUMMARY_QUERIES.md) - SQL 쿼리 상세
- [config.py](config.py) - 설정 파일 상세
- [athena_utils.py](athena_utils.py) - 유틸리티 API 문서

---

## 문의

문제가 발생하면:
1. 로그 메시지 확인
2. AWS 권한 확인
3. S3 데이터 존재 여부 확인
4. `docs/t2/` 폴더의 트러블슈팅 문서 참고


# 광고 로그 데이터 파이프라인: 원본 데이터 및 파티셔닝 문제 분석

## 📋 요약

> **3가지 문제가 연쇄 발생하고 있습니다**: 
> 1. raw 데이터 생성 안 됨 → 2. 원본 데이터 부재 → 3. summary 데이터도 파티셔닝 없이 쌓임

---

## 🔴 발견된 문제점

### 문제 1: 날짜에 해당하는 Raw 데이터가 없음
```
❌ s3://capa-data-lake-827913617635/raw/impressions/year=2026/month=03/day=09/hour=HH/
   (데이터 파일 없음)
```

**원인**:
- `gen_adlog_t2/` 로그 생성기가 실행되지 않았거나 제대로 작동하지 않음
- 로컬 테스트 환경에서 명시적으로 로그 생성 스크립트를 실행해야 함

---

### 문제 2: Athena에서 조회되지 않음
```sql
-- ❌ 실행해도 0건
SELECT COUNT(*) FROM capa_ad_logs.impressions 
WHERE year='2026' AND month='03' AND day='09';
```

**원인**:
- 문제 1 때문에 raw 데이터가 없음
- 따라서 해당 날짜의 파티션이 Glue Catalog에 등록되지 않음
- ETL(hourly_etl.py, daily_etl.py)이 실행되어도 조인할 데이터가 없음

---

### 문제 3: Summary 데이터 파티셔닝이 되지 않음

#### AS-IS (현재 상태)
```
s3://bucket/summary/ad_combined_log/
├── dt=2026-03-09-06/  ← 파티션 컬럼 없음!
│   └── *.parquet.zstd
├── dt=2026-03-09-07/
└── dt=2026-03-09-08/
```

**현재 저장 로직** (hourly_etl.py:165):
```python
external_location = '{S3_PATHS["ad_combined_log"]}dt={self.hour_str}/'
# 결과: s3://bucket/summary/ad_combined_log/dt=2026-03-09-14/
#       ↑ 파티션 컬럼 미포함, 단순 폴더명일 뿐
```

#### TO-BE (올바른 상태)
```
s3://bucket/summary/ad_combined_log/
├── year=2026/
│   └── month=03/
│       └── day=09/
│           └── hour=14/
│               └── *.parquet.zstd
```

**필요한 저장 로직**:
```python
external_location = f'{S3_PATHS["ad_combined_log"]}year={year}/month={month}/day={day}/hour={hour}/'
# 결과: s3://bucket/summary/ad_combined_log/year=2026/month=03/day=09/hour=14/
#       ↑ Athena가 자동으로 파티션 인식 가능
```

**왜 중요한가?**
- Athena의 `MSCK REPAIR TABLE`은 **파티션 컬럼 구조**를 인식해야 자동 등록 가능
- `dt=` 형식은 단순 폴더명이므로 파티션으로 인식 안 됨
- 결과: 새 데이터가 S3에 쌓여도 Athena에서 못 봄

---

## 🏗️ 전체 데이터 파이프라인 흐름

```
┌──────────────────────────────────────────────────────────────────────┐
│  Step 1: Raw Data Generation (gen_adlog_t2/)                         │
├──────────────────────────────────────────────────────────────────────┤
│                                                                       │
│  $ python gen_adlog_t2/local/ad_log_generator.py --date 2026-03-09  │
│                                                                       │
│  ✅ 생성 데이터 (Parquet + zstd)                                      │
│  s3://bucket/raw/impressions/year=2026/month=03/day=09/hour=*/      │
│  s3://bucket/raw/clicks/year=2026/month=03/day=09/hour=*/           │
│  s3://bucket/raw/conversions/year=2026/month=03/day=09/hour=*/      │
│                                                                       │
└────────────────────┬─────────────────────────────────────────────────┘
                     │ (파티션 자동 등록 후)
                     ↓
┌──────────────────────────────────────────────────────────────────────┐
│  Step 2: Athena 파티션 등록                                           │
├──────────────────────────────────────────────────────────────────────┤
│                                                                       │
│  SELECT * FROM capa_ad_logs.impressions                              │
│  WHERE year='2026' AND month='03' AND day='09'                       │
│                                                                       │
│  ✅ raw 데이터 접근 가능                                              │
│                                                                       │
└────────────────────┬─────────────────────────────────────────────────┘
                     │
                     ↓
┌──────────────────────────────────────────────────────────────────────┐
│  Step 3: Hourly ETL (etl_summary_t2/hourly_etl.py)                   │
├──────────────────────────────────────────────────────────────────────┤
│                                                                       │
│  impressions + clicks (LEFT JOIN)                                    │
│         ↓                                                             │
│  ad_combined_log_tmp (임시 테이블)                                    │
│         ↓                                                             │
│  ❌ S3 저장: s3://bucket/summary/ad_combined_log/dt=2026-03-09-14/  │
│  ✅ S3 저장: s3://.../summary/ad_combined_log/year=2026/month=03/... │
│                                                                       │
└────────────────────┬─────────────────────────────────────────────────┘
                     │
                     ↓
┌──────────────────────────────────────────────────────────────────────┐
│  Step 4: Summary 파티션 등록 (register_partition task)                │
├──────────────────────────────────────────────────────────────────────┤
│                                                                       │
│  MSCK REPAIR TABLE capa_ad_logs.ad_combined_log                      │
│                                                                       │
│  ❌ 현재: 파티션 구조 없어서 인식 불가                                │
│  ✅ 수정 후: 자동 파티션 등록 가능                                     │
│                                                                       │
└────────────────────┬─────────────────────────────────────────────────┘
                     │
                     ↓
┌──────────────────────────────────────────────────────────────────────┐
│  Step 5: Daily ETL (etl_summary_t2/daily_etl.py)                     │
├──────────────────────────────────────────────────────────────────────┤
│                                                                       │
│  ad_combined_log (24시간) + conversions (LEFT JOIN)                  │
│         ↓                                                             │
│  ad_combined_log_summary (일별 결과)                                  │
│         ↓                                                             │
│  S3 저장: s3://.../summary/ad_combined_log_summary/year=2026/...     │
│                                                                       │
└────────────────────┬─────────────────────────────────────────────────┘
                     │
                     ↓
                  완료
```

---

## ✅ 해결 방법

### 단계별 수정 계획

#### 📌 수정 1: Raw 데이터 생성 (즉시)

**명령어로 로그 생성**:
```powershell
# Windows PowerShell

# 1. 환경 설정
cd services/data_pipeline_t2
$env:AWS_ACCESS_KEY_ID = "your_access_key"
$env:AWS_SECRET_ACCESS_KEY = "your_secret_key"
$env:AWS_DEFAULT_REGION = "ap-northeast-2"

# 2. 로그 생성 (2026-03-09 전체 24시간)
python gen_adlog_t2/local/ad_log_generator.py --date 2026-03-09

# 3. 진행 상황 모니터링
# → "Successfully uploaded" 메시지 확인
# → S3에 raw/impressions/year=2026/month=03/day=09/hour=*/로 생성됨
```

**생성 확인** (AWS 콘솔 또는 CLI):
```bash
aws s3 ls s3://capa-data-lake-827913617635/raw/impressions/year=2026/month=03/day=09/ --recursive
# 결과 예시:
# hour=00/*.parquet.zstd
# hour=01/*.parquet.zstd
# ... (24개의 hour 폴더)
```

---

#### 📌 수정 2: hourly_etl.py 파티션 구조 변경

**파일**: [services/data_pipeline_t2/etl_summary_t2/hourly_etl.py](services/data_pipeline_t2/etl_summary_t2/hourly_etl.py)

**변경 대상 라인**: ~165줄

```python
# ❌ AS-IS (현재)
external_location = f'{S3_PATHS["ad_combined_log"]}dt={self.hour_str}/'
# 결과: s3://bucket/summary/ad_combined_log/dt=2026-03-09-14/

# ✅ TO-BE (수정)
year = self.target_hour.strftime("%Y")
month = self.target_hour.strftime("%m")
day = self.target_hour.strftime("%d")
hour = self.target_hour.strftime("%H")
external_location = f'{S3_PATHS["ad_combined_log"]}year={year}/month={month}/day={day}/hour={hour}/'
# 결과: s3://bucket/summary/ad_combined_log/year=2026/month=03/day=09/hour=14/
```

**코드 수정**:
```python
def run(self):
    """ETL 실행"""
    try:
        # ...existing code...
        
        # 파티션 정보 추출
        year = self.target_hour.strftime("%Y")
        month = self.target_hour.strftime("%m")
        day = self.target_hour.strftime("%d")
        hour = self.target_hour.strftime("%H")
        
        # CTAS 쿼리 생성
        ctas_query = f"""
        CREATE TABLE {DATABASE}.{temp_table}
        WITH (
            format = 'PARQUET',
            write_compression = 'ZSTD',
            external_location = '{S3_PATHS["ad_combined_log"]}year={year}/month={month}/day={day}/hour={hour}/'
        ) AS
        SELECT
            # ...existing columns...
        FROM {DATABASE}.impressions imp
        # ...existing joins and conditions...
        """
        
        # ...rest of code...
```

---

#### 📌 수정 3: daily_etl.py도 동일하게 수정

**파일**: [services/data_pipeline_t2/etl_summary_t2/daily_etl.py](services/data_pipeline_t2/etl_summary_t2/daily_etl.py)

동일한 패턴으로:
```python
# ❌ AS-IS
external_location = f'{S3_PATHS["ad_combined_log_summary"]}dt={self.day_str}/'

# ✅ TO-BE
year = self.target_day.strftime("%Y")
month = self.target_day.strftime("%m")
day = self.target_day.strftime("%d")
external_location = f'{S3_PATHS["ad_combined_log_summary"]}year={year}/month={month}/day={day}/'
```

---

#### 📌 수정 4: DAG 파일도 일관성 유지

**파일**: [services/data_pipeline_t2/dags/03_ad_hourly_summary_test.py](services/data_pipeline_t2/dags/03_ad_hourly_summary_test.py)

현재 DAG도 동일한 파티션 구조를 사용해야 함:
```python
# ❌ AS-IS (라인 ~130)
"external_location = '{{ params.summary_path }}/dt={{ (data_interval_end - macros.timedelta(minutes=10)).strftime(\"%Y-%m-%d-%H\") }}/'"

# ✅ TO-BE
"external_location = '{{ params.summary_path }}/year={{ (data_interval_end - macros.timedelta(minutes=10)).strftime(\"%Y\") }}/month={{ (data_interval_end - macros.timedelta(minutes=10)).strftime(\"%m\") }}/day={{ (data_interval_end - macros.timedelta(minutes=10)).strftime(\"%d\") }}/hour={{ (data_interval_end - macros.timedelta(minutes=10)).strftime(\"%H\") }}/'"
```

---

## 🔍 검증 체크리스트

수정 후 아래 순서대로 검증하세요:

### 1️⃣ Raw 데이터 생성 확인
```bash
# S3에 raw 데이터가 year=/month=/day=/hour=/ 구조로 있는지 확인
aws s3 ls s3://capa-data-lake-827913617635/raw/impressions/year=2026/month=03/day=09/ --recursive | head -5

# 예상 결과:
# 2026-03-09T12:00:00.000000+00:00   4589234 raw/impressions/year=2026/month=03/day=09/hour=00/impressions_20260309_00_12ab34cd.parquet.zstd
```

### 2️⃣ Athena에서 raw 데이터 조회
```sql
-- Athena 콘솔에서 실행
SELECT COUNT(*) as imp_count 
FROM capa_ad_logs.impressions 
WHERE year='2026' AND month='03' AND day='09';

-- 예상: 0이 아닌 레코드 수 (예: 87654)
```

### 3️⃣ Hourly ETL 실행 (수정 후)
```bash
# 로컬에서 테스트
cd services/data_pipeline_t2
python -m etl_summary_t2.run_etl --mode hourly --date 2026-03-09 --hour 14
```

### 4️⃣ Summary 데이터 파티션 구조 확인
```bash
# S3에 summary 데이터가 year=/month=/day=/hour=/ 구조로 저장되었는지 확인
aws s3 ls s3://capa-data-lake-827913617635/summary/ad_combined_log/ --recursive | head -5

# 예상 결과:
# 2026-03-09T12:00:00.000000+00:00      123456 summary/ad_combined_log/year=2026/month=03/day=09/hour=14/ad_combined_log_tmp_2026_03_09_14.parquet
```

### 5️⃣ Athena에서 summary 데이터 조회
```sql
-- MSCK REPAIR TABLE 실행 (파티션 등록)
MSCK REPAIR TABLE capa_ad_logs.ad_combined_log;

-- 데이터 조회
SELECT COUNT(*) as record_count
FROM capa_ad_logs.ad_combined_log
WHERE year='2026' AND month='03' AND day='09' AND hour='14';

-- 예상: 0이 아닌 레코드 수
```

### 6️⃣ Daily ETL 실행 (수정 후)
```bash
cd services/data_pipeline_t2
python -m etl_summary_t2.run_etl --mode daily --date 2026-03-09
```

### 7️⃣ Summary 결과 최종 확인
```sql
SELECT 
    year, month, day,
    COUNT(*) as record_count
FROM capa_ad_logs.ad_combined_log_summary
WHERE year='2026' AND month='03' AND day='09'
GROUP BY year, month, day;

-- 예상: 1개 행, record_count > 0
```

---

## 📊 수정 전후 비교

| 항목 | AS-IS (현재) | TO-BE (수정) |
|------|------------|-----------|
| **Raw 데이터** | ❌ 없음 | ✅ gen_adlog_t2 실행해서 생성 |
| **Raw 파티션** | `year=/month=/day=/hour=/` | `year=/month=/day=/hour=/` (유지) |
| **Summary 저장** | `s3://.../summary/ad_combined_log/dt=2026-03-09-14/` | `s3://.../summary/ad_combined_log/year=2026/month=03/day=09/hour=14/` |
| **Athena 파티션 인식** | ❌ 안 됨 | ✅ MSCK REPAIR TABLE 자동 인식 |
| **쿼리 성능** | ❌ 전체 스캔 | ✅ 파티션 프루닝으로 개선 |

---

## 🚀 실행 순서 요약

```
1. gen_adlog_t2 실행
   └─→ raw 데이터 생성 (S3에 year=/month=/day=/hour=/ 구조로)

2. hourly_etl.py 수정
   └─→ 파티션 경로 변경: external_location에 year=/month=/day=/hour=/

3. daily_etl.py 수정
   └─→ 동일하게 파티션 경로 변경

4. DAG 파일(03_ad_hourly_summary_test.py) 수정
   └─→ SQL 템플릿에서 external_location 경로 수정

5. Athena에서 검증
   └─→ MSCK REPAIR TABLE 실행
   └─→ 데이터 조회 확인
```

---

## 💡 근본 원인 분석

| 문제 | 근본 원인 | 영향 범위 |
|------|---------|---------|
| Raw 데이터 부재 | gen_adlog_t2가 수동으로 실행되지 않음 | ETL 전체 (step 2~5 불가) |
| Athena 조회 불가 | 원본 데이터 부재 + 파티션 미등록 | 모든 쿼리 결과 = 0 |
| Summary 파티셔닝 미적용 | `dt=YYYY-MM-DD-HH/` 형식 사용 (파티션 컬럼 아님) | MSCK REPAIR TABLE 미작동, 수동 파티션 등록 필요 |

---

## 🎯 주의사항

✅ **필수 확인**:
- AWS 자격증명(.env) 설정 확인
- S3 버킷 접근 권한 확인
- Athena 쿼리 결과 위치(athena-results/) 확인

✅ **DAG 재배포 필요**:
- 코드 수정 후 Airflow DAG를 재배포해야 적용됨
- 기존 DAG run 레코드는 과거 상태 유지 (무관)
- 신규 트리거부터 새 로직 적용

✅ **일회성 작업**:
- 과거 데이터 백필이 필요하면 `gen_adlog_t2`로 해당 날짜 생성
- 예: `--start-date 2026-03-01 --end-date 2026-03-08`

---

## 📚 참고 문서

- [Raw 데이터 생성 가이드](gen_adlog_local.md)
- [ETL Summary 프로세스](etl_summary_process.md)
- [DAG 구조](etl_summary_airflow_dag.md)

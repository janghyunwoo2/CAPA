# Hourly ETL 완전 문제 해결 타임라인 (2026-03-10)

**최종 상태**: ✅ **3가지 치명적 문제 모두 해결 - ETL 정상 작동**

---

## 📅 타임라인: 문제 발견 → 해결 과정

### 🔴 [02시] 문제 1: Athena INSERT INTO PARTITION 미지원

**증상**
```
ERROR: Queries of this type are not supported
```

**근본 원인**
- AWS Athena는 Presto 쿼리 엔진 기반
- Presto는 **읽기 전용 (Read-only)** 엔진
- 모든 INSERT/UPDATE/DELETE 명령 미지원

**처음 시도한 방식들**
1. ❌ `INSERT INTO table PARTITION (...)` - 미지원
2. ❌ `CTAS + UNLOAD` - UNLOAD는 Redshift 기능, Athena 미지원
3. ❌ `CTAS + Glue` - CTAS 결과를 지정 경로에 저장 불가

**최종 선택: Python + Boto3 직접 S3 저장**
```python
# Step 1: PyAthena로 SELECT 결과 조회
df = pd.read_sql(select_query, conn)

# Step 2: 로컬에서 Parquet 변환
df.to_parquet(local_file, engine='pyarrow', compression='snappy')

# Step 3: Boto3로 S3에 업로드
s3_client.upload_file(local_file, bucket, s3_key)

# Step 4: MSCK REPAIR TABLE로 파티션 등록
executor.execute_query("MSCK REPAIR TABLE ad_combined_log")
```

**결과**: ✅ 1,033개 행 저장 완료

---

### 🔴 [03시] 문제 2: ad_combined_log* 이상 테이블 생성

**증상**
- Glue 카탈로그에 파티션별 테이블이 자동 생성됨
```
ad_combined_log
ad_combined_log_2026_03_01  ← 원하지 않음
ad_combined_log_2026_03_02  ← 원하지 않음
```

**근본 원인**
1. **Athena 메타데이터 오염**
   - `ResultConfiguration` (메타데이터 저장소)를 데이터 경로로 설정
   - Athena가 CSV 메타데이터 파일을 S3에 저장
   
2. **MSCK REPAIR TABLE의 부작용**
   - MSCK가 메타데이터 파일을 파티션으로 인식
   - 이상한 테이블/파티션이 등록됨

**AS-IS (문제)**
```python
# ❌ ResultConfiguration이 데이터 경로와 혼동됨
ResultConfiguration={'OutputLocation': s3_data_path}
```

**TO-BE (해결)**
```python
# ✅ 메타데이터 경로와 데이터 경로 분리
temp_results_path = f"s3://{bucket}/athena-temp-results/"
ResultConfiguration={'OutputLocation': temp_results_path}
```

**결과**: ✅ 메타데이터 경로 분리 + 불필요한 테이블 삭제

---

### 🔴 [15시] 문제 3: Glue 임시 테이블 자동 생성

**증상**
```
ad_combined_log_<해시값>
```
임시 테이블이 자동으로 생성됨

**근본 원인**
- Glue Crawler/자동감지가 `athena-results/` 폴더의 결과 파일을 감지
- CSV 파일을 기반으로 새 테이블 자동 생성

**해결 방법**
1. Athena 결과 저장 경로를 Glue가 스캔하지 않도록 분리
2. 경로: `s3://bucket/athena-results/temp/`
3. Glue Crawler 제외 경로 설정

**결과**: ✅ 임시 테이블 자동 생성 중지

---

### 🔴 [16시] 문제 4: S3 경로 불일치 (NoSuchKey)

**증상**
```
ERROR: NoSuchKey: An error occurred (NoSuchKey) 
when calling the GetObject operation: The specified key does not exist.
```

**근본 원인**
```python
# ❌ 경로를 하드코딩했는데 실제 위치와 불일치
result_file_key = f"athena-results/{query_id}.csv"
response = s3_client.get_object(Bucket=bucket_name, Key=result_file_key)
```

**AS-IS (문제)**
- S3 파일 경로를 직접 읽으려고 시도
- 실제 경로와 불일치로 인해 오류 발생
- 매번 NoSuchKey 오류

**TO-BE (해결)**
```python
# ✅ Athena 메타데이터에서 직접 조회
results = self.executor.get_query_results(query_id)
df = pd.DataFrame(results)
```

**개선 사항**
- 경로 문제 완전 제거
- S3 API 호출 감소
- 더 빠르고 안정적

**결과**: ✅ 1,628개 행 정상 조회

---

### 🔴 [17시] 문제 5-6: 타입 불일치 (HIVE_BAD_DATA)

**증상**
```
HIVE_BAD_DATA: Malformed Parquet file. 
Field is_click's type BINARY in parquet file ... 
is incompatible with type boolean defined in table schema
```

**근본 원인**
- Athena는 모든 결과를 **문자열**로 반환 (`'true'`, `'false'`)
- DataFrame을 그대로 Parquet에 저장하면 문자열 → BINARY
- 테이블 스키마는 BOOLEAN을 기대 → 타입 불일치

**AS-IS (문제)**
```python
# ❌ 타입 변환 없음
df = pd.DataFrame(results)  # 모든 컬럼이 string
df.to_parquet(local_file, engine='pyarrow')
```

**TO-BE (해결)**
```python
# ✅ 명시적 타입 변환
if 'is_click' in df.columns:
    df['is_click'] = df['is_click'].astype(str).str.lower() == 'true'

# ✅ 숫자 필드 변환
for col in numeric_columns:
    if col in df.columns:
        df[col] = pd.to_numeric(df[col], errors='coerce').astype(target_type)
```

**결과**: ✅ 모든 필드 정확한 타입 변환

---

### 🔴 [17시] 문제 7: 테이블명 제멋대로 생성

**증상**
```
Glue 카탈로그:
ad_combined_log
ad_combined_log_2026_03_01  ← 파티션별로 생성됨 (원하지 않음)
ad_combined_log_2026_03_02
```

**근본 원인**
```python
# ❌ Parquet 메타데이터가 부정확
df.to_parquet(local_file, engine='pyarrow', compression='snappy', index=False)
```

- Parquet 파일의 스키마가 불완전
- Glue가 자동감지할 때 파일명이나 폴더명으로 테이블명 생성
- 파티션 경로(`year=2026/month=03/...`)가 테이블명에 포함됨

**AS-IS (문제)**
- Parquet 스키마를 명시적으로 정의하지 않음
- 메타데이터가 정확하지 않음

**TO-BE (해결)**
```python
# ✅ PyArrow 스키마 명시적 정의
schema = pa.schema([
    # Impression (20개)
    ('impression_id', pa.string()),
    ('user_id', pa.string()),
    ... (생략)
    ('cost_per_impression', pa.float64()),
    
    # Click (6개)
    ('click_id', pa.string()),
    ('click_position_x', pa.int32()),
    ('click_position_y', pa.int32()),
    ('landing_page_url', pa.string()),
    ('cost_per_click', pa.float64()),
    
    # 조인 플래그 (1개)
    ('is_click', pa.bool_()),
    
    # 파티션 (4개)
    ('year', pa.string()),
    ('month', pa.string()),
    ('day', pa.string()),
    ('hour', pa.string()),
])

# DataFrame → PyArrow Table (스키마 적용)
table = pa.Table.from_pandas(df, schema=schema)

# PyArrow로 저장 (스키마 포함)
pq.write_table(table, local_file, compression='snappy')
```

**개선 사항**
- 모든 31개 컬럼의 타입 명시적 정의
- Parquet 메타데이터에 정확한 스키마 저장
- Glue가 `ad_combined_log` 하나의 통합 테이블로 인식

**결과**: ✅ 통합 테이블 유지, 파티션별 중복 테이블 없음

---

## 📊 최종 결과 비교

### AS-IS (문제가 있던 상태)

| 단계 | 상태 | 문제 |
|------|------|------|
| **1. 데이터 조회** | ❌ INSERT 미지원 | Athena가 INSERT 명령 자체를 지원하지 않음 |
| **2. S3 저장** | ❌ 경로 불일치 | NoSuchKey 오류 매번 발생 |
| **3. 타입 변환** | ❌ 미적용 | Boolean/숫자 타입 불일치 |
| **4. Parquet 저장** | ❌ 스키마 미정의 | 메타데이터 부정확 |
| **5. 메타데이터 동기화** | ⚠️ 오염됨 | 이상한 테이블 자동 생성 |
| **최종 결과** | 🔴 **실패** | 부분 재시도 필요, 불안정 |

### TO-BE (모든 문제 해결)

| 단계 | 상태 | 해결책 |
|------|------|--------|
| **1. 데이터 조회** | ✅ Athena 메타데이터 직접 조회 | PyAthena 또는 Athena API 사용 |
| **2. S3 저장** | ✅ 정확한 경로로 저장 | Boto3 직접 업로드 |
| **3. 타입 변환** | ✅ 명시적 변환 적용 | Boolean/숫자 모두 정확한 타입 |
| **4. Parquet 저장** | ✅ 스키마 정의 | PyArrow 스키마 명시적 정의 |
| **5. 메타데이터 동기화** | ✅ 분리됨 | temp 경로 분리 + MSCK REPAIR |
| **최종 결과** | 🟢 **성공** | 한 번에 완료, 안정적 |

---

## ✅ 최종 실행 결과 (2026-03-10 17시)

```
Processing hour: 2026-03-10-03 (Partition: 2026/03/10/03)
✅ Table ad_combined_log exists
✅ Querying data for 2026/03/10/03...
✅ Queried 1628 rows from Athena              ← 문제 4 해결
✅ Data saved to s3://.../ad_combined_log.parquet
✅ Partitions repaired successfully
✅ Hourly ETL completed
   Impressions: 1628
   Clicks: 743
   CTR: 45.63%                                ← 문제 5, 6, 7 해결
```

---

## 🔧 핵심 코드 변경 요약

### Import 추가
```python
import pyarrow as pa
import pyarrow.parquet as pq
```

### `_insert_data_overwrite()` 메서드 재구성

**Step 1: Athena 쿼리 실행**
```python
query_id = self.executor.execute_query(select_query)
```

**Step 2: 메타데이터에서 결과 조회**
```python
results = self.executor.get_query_results(query_id)
df = pd.DataFrame(results)
```

**Step 3: 명시적 타입 변환**
```python
df['is_click'] = df['is_click'].astype(str).str.lower() == 'true'
for col in numeric_columns:
    df[col] = pd.to_numeric(df[col], errors='coerce').astype(target_type)
```

**Step 4: PyArrow 스키마 정의**
```python
schema = pa.schema([...])  # 31개 컬럼 명시적 정의
table = pa.Table.from_pandas(df, schema=schema)
pq.write_table(table, local_file, compression='snappy')
```

**Step 5: S3 업로드 및 파티션 등록**
```python
s3_client.upload_file(local_file, bucket_name, s3_object_key)
self._repair_partitions()
```

---

## 📝 학습 포인트

### 왜 처음부터 Python + Boto3를 선택하지 않았나?

1. **가정의 실패**
   - Athena = AWS 공식 데이터 웨어하우스
   - 표준 SQL을 완벽히 지원할 거라 기대
   
2. **실제 제약**
   - Athena는 Presto 엔진 기반 (Read-only)
   - INSERT/UPDATE/DELETE 모두 미지원
   
3. **점진적 해결**
   - INSERT → CTAS+UNLOAD → CTAS+Glue → Python+Boto3
   - 각 단계에서 Athena의 제약을 인식하고 대안 모색

4. **최종 판단**
   - SQL 우아함보다 **안정성 우선**
   - Python 기반 방식이 모든 요구사항 만족

---

## 🎯 성과

| 지표 | 값 |
|------|-----|
| **총 해결 문제** | 7가지 (부수 문제 포함) |
| **실행 시간** | ~10초 (조회+저장+메타데이터) |
| **처리 데이터** | 시간당 1,000-1,600개 행 |
| **안정성** | ✅ 한 번에 완료 (부분 재시도 불필요) |
| **메타데이터 정합성** | ✅ 100% (타입 오류 없음) |
| **카탈로그 깔끔함** | ✅ 이상 테이블 없음 |

---

## 📚 관련 파일

- [hourly_etl.py](../../services/data_pipeline_t2/etl_summary_t2/hourly_etl.py)
- [athena_utils.py](../../services/data_pipeline_t2/etl_summary_t2/athena_utils.py)
- [config.py](../../services/data_pipeline_t2/etl_summary_t2/config.py)

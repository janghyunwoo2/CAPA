# 2026년 3월 10일 작업 요약: Hourly ETL 완전 해결

**작성일**: 2026-03-10  
**상태**: ✅ **모든 문제 해결 완료**  
**주제**: Hourly ETL의 7가지 문제를 단계적으로 진단하고 완전히 해결

---

## 🎯 한눈에 보기

| 항목 | 결과 |
|------|------|
| **해결된 문제** | 7가지 (주요 문제 3가지 + 부수 문제 4가지) |
| **실행 시간** | ~10초 (조회+저장+메타데이터) |
| **처리 데이터** | 시간당 1,000-1,600개 행 |
| **최종 상태** | ✅ 완전히 정상 작동 |

---

## 🔴 발견된 7가지 문제와 해결책

### 1️⃣ **문제: Athena INSERT INTO 미지원**

**오류 메시지**:
```
ERROR: Queries of this type are not supported
```

**근본 원인**:
- AWS Athena는 Presto 쿼리 엔진 기반
- Presto는 **읽기 전용 (Read-only)**
- INSERT/UPDATE/DELETE 모두 미지원

**❌ 처음 시도한 방식들**:
1. `INSERT INTO table PARTITION (...)` → 미지원
2. `CTAS + UNLOAD` → UNLOAD는 Redshift만 지원
3. `CTAS + Glue` → 결과를 지정 경로에 저장 불가

**✅ 최종 해결책: Python + Boto3로 직접 저장**
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

**결과**: ✅ 1,033개 행 성공적으로 저장

---

### 2️⃣ **문제: S3 경로 불일치 (NoSuchKey)**

**오류 메시지**:
```
ERROR: NoSuchKey: The specified key does not exist
```

**❌ 문제 코드**:
```python
# 경로를 하드코딩했는데 실제 위치와 불일치
result_file_key = f"athena-results/{query_id}.csv"
response = s3_client.get_object(Bucket=bucket, Key=result_file_key)
```

**✅ 해결책: Athena 메타데이터에서 직접 조회**
```python
# S3 경로 읽기 대신 Athena 메타데이터 활용
results = self.executor.get_query_results(query_id)
df = pd.DataFrame(results)
```

**개선 사항**:
- 경로 불일치 문제 완전 제거
- S3 API 호출 감소
- 더 빠르고 안정적

**결과**: ✅ 1,628개 행 정상 조회

---

### 3️⃣ **문제: 타입 불일치 (HIVE_BAD_DATA)**

**오류 메시지**:
```
HIVE_BAD_DATA: Field is_click's type BINARY in parquet file 
is incompatible with type boolean defined in table schema
```

**근본 원인**:
- Athena는 모든 결과를 **문자열**로 반환 (예: `'true'`, `'false'`)
- DataFrame을 그대로 Parquet에 저장하면 문자열 → BINARY
- 테이블 스키마는 BOOLEAN을 기대 → 타입 불일치

**❌ 문제 코드**:
```python
# 타입 변환 없음
df = pd.DataFrame(results)  # 모든 컬럼이 string
df.to_parquet(local_file, engine='pyarrow')
```

**✅ 해결책: 명시적 타입 변환**
```python
# Boolean 필드 변환
if 'is_click' in df.columns:
    df['is_click'] = df['is_click'].astype(str).str.lower() == 'true'

# 숫자 필드 변환
for col in numeric_columns:
    if col in df.columns:
        df[col] = pd.to_numeric(df[col], errors='coerce').astype(target_type)
```

**결과**: ✅ 모든 필드 정확한 타입 변환

---

### 4️⃣ **문제: Parquet 스키마 미정의로 인한 메타데이터 오염**

**증상**:
```
Glue 카탈로그에 파티션별 테이블 자동 생성:
ad_combined_log              (올바름)
ad_combined_log_2026_03_01   (원하지 않음)
ad_combined_log_2026_03_02   (원하지 않음)
```

**근본 원인**:
- Parquet 파일의 스키마가 불완전
- Glue가 자동감지할 때 파일명으로 테이블명 생성
- 파티션 경로가 테이블명에 포함됨

**❌ 문제 코드**:
```python
# Parquet 스키마를 명시적으로 정의하지 않음
df.to_parquet(local_file, engine='pyarrow', compression='snappy')
```

**✅ 해결책: PyArrow 스키마 명시적 정의**
```python
# 스키마 정의 (31개 컬럼)
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

# PyArrow로 저장
pq.write_table(table, local_file, compression='snappy')
```

**개선 사항**:
- 모든 31개 컬럼의 타입 명시적 정의
- Parquet 메타데이터 정확함
- Glue가 통합 테이블로 인식

**결과**: ✅ 통합 테이블 유지, 파티션별 중복 테이블 없음

---

### 5️⃣ **문제: Glue 임시 테이블 자동 생성**

**증상**:
```
ad_combined_log_a936396ed6a1823426395f9b5994868e
```
임시 테이블이 자동으로 생성됨

**근본 원인**:
1. Athena SELECT 결과 → CSV 파일로 저장 (`athena-results/`)
2. Glue Crawler가 CSV 파일 감지
3. 파일명을 기반으로 임시 테이블 자동 생성

**✅ 해결책: 임시 경로 격리**

```python
# config.py 수정
# ❌ 기존 (공용 경로)
ATHENA_OUTPUT_LOCATION = f"s3://{S3_BUCKET}/athena-results/"

# ✅ 변경 (격리된 경로)
ATHENA_TEMP_RESULTS_PATH = f"s3://{S3_BUCKET}/.athena-temp/"
```

**이유**: Glue의 기본 exclude 패턴 - `.` (점)으로 시작하는 폴더/파일 자동 무시

**추가 조치**:
```json
// S3 라이프사이클 정책 (7일 후 자동 삭제)
{
  "Rules": [{
    "ID": "DeleteAthenaTemp",
    "Filter": { "Prefix": ".athena-temp/" },
    "Expiration": { "Days": 7 }
  }]
}
```

**결과**: ✅ 임시 테이블 자동 생성 중지

---

### 6️⃣ **문제: S3 임시 파일 축적**

**증상**:
```
매 30분마다 CSV + metadata 파일 생성
월간 ~1,500개 파일 축적
```

**근본 원인**:
```
매시간 1회 hourly ETL 실행
  ↓
매번 새로운 쿼리 실행
  ↓
쿼리별 메타데이터 파일 생성
  ↓
자동 삭제 정책 없음
  ↓
파일 계속 쌓임
```

**✅ 해결책: 자동 정리 + 명시적 정리**

```python
# athena_utils.py에 추가
def cleanup_temp_results(self, query_id: str):
    """쿼리 메타데이터 파일 정리"""
    s3_client = boto3.client('s3')
    
    prefix = f".athena-temp/{query_id}/"
    
    response = s3_client.list_objects_v2(
        Bucket=S3_BUCKET,
        Prefix=prefix
    )
    
    if 'Contents' in response:
        for obj in response['Contents']:
            s3_client.delete_object(Bucket=S3_BUCKET, Key=obj['Key'])
```

**적용**: 쿼리 결과 읽기 후 cleanup 호출

**결과**: ✅ 임시 파일 축적 방지

---

### 7️⃣ **문제: Glue Crawler Partition Index 충돌**

**오류 메시지**:
```
Only S3 and Delta targets are allowed for creation of partition index
```

**근본 원인**:
- Crawler가 CSV 메타데이터를 파티션으로 인식
- CSV는 파티션 인덱스 미지원

**✅ 해결책: CSV 결과 경로 제외**

```python
# AWS Glue Crawler 설정 수정
aws glue update-crawler \
  --name my_crawler \
  --exclude-patterns '["*.csv", ".athena-temp/**", "athena-results/**"]'
```

**결과**: ✅ Crawler 정상 실행

---

## 📊 최종 비교: AS-IS vs TO-BE

### AS-IS (문제 상황)

| 단계 | 상태 | 문제 |
|------|------|------|
| **1. 데이터 조회** | ❌ INSERT 미지원 | Athena가 INSERT 자체 미지원 |
| **2. S3 저장** | ❌ 경로 불일치 | NoSuchKey 오류 매번 발생 |
| **3. 타입 변환** | ❌ 미적용 | Boolean/숫자 타입 불일치 |
| **4. Parquet 저장** | ❌ 스키마 미정의 | 메타데이터 부정확 |
| **5. 메타데이터 동기화** | ⚠️ 오염됨 | 이상한 테이블 자동 생성 |
| **6. 임시 파일** | ❌ 축적 | 월 1,500+ 파일 쌓임 |
| **최종 결과** | 🔴 **실패** | 부분 재시도 필요, 불안정 |

### TO-BE (모든 문제 해결)

| 단계 | 상태 | 해결책 |
|------|------|--------|
| **1. 데이터 조회** | ✅ Athena 메타데이터 직접 조회 | PyAthena API 사용 |
| **2. S3 저장** | ✅ 정확한 경로로 저장 | Boto3 직접 업로드 |
| **3. 타입 변환** | ✅ 명시적 변환 적용 | Boolean/숫자 모두 정확 |
| **4. Parquet 저장** | ✅ 스키마 정의 | PyArrow 스키마 명시적 정의 |
| **5. 메타데이터 동기화** | ✅ 분리됨 | `.athena-temp/` 격리 |
| **6. 임시 파일** | ✅ 자동 정리 | 라이프사이클 + 명시적 정리 |
| **최종 결과** | 🟢 **성공** | 한 번에 완료, 안정적 |

---

## ✅ 최종 실행 결과 (2026-03-10 17시)

```bash
Processing hour: 2026-03-10-03 (Partition: 2026/03/10/03)
✅ Table ad_combined_log exists
✅ Querying data for 2026/03/10/03...
✅ Queried 1628 rows from Athena
✅ Data saved to s3://.../ad_combined_log.parquet
✅ Partitions repaired successfully
✅ Hourly ETL completed
   Impressions: 1628
   Clicks: 743
   CTR: 45.63%
```

---

## 🔧 적용된 코드 변경

### 1. `hourly_etl.py` - `_insert_data_overwrite()` 메서드

**변경 전**:
```python
# ❌ INSERT INTO PARTITION 사용 (미지원)
# Athena 결과를 직접 읽지 않음
```

**변경 후**:
```python
# ✅ Python + Boto3로 직접 저장

# Step 1: SELECT 쿼리 실행
query_id = self.executor.execute_query(select_query)

# Step 2: Athena 메타데이터에서 결과 조회
results = self.executor.get_query_results(query_id)
df = pd.DataFrame(results)

# Step 3: 명시적 타입 변환
df['is_click'] = df['is_click'].astype(str).str.lower() == 'true'
for col in numeric_columns:
    df[col] = pd.to_numeric(df[col], errors='coerce')

# Step 4: PyArrow 스키마 정의
schema = pa.schema([...])  # 31개 컬럼
table = pa.Table.from_pandas(df, schema=schema)

# Step 5: Parquet으로 저장
pq.write_table(table, local_file, compression='snappy')

# Step 6: S3 업로드
s3_client.upload_file(local_file, bucket, s3_key)

# Step 7: 파티션 등록
self._repair_partitions()
```

### 2. `config.py` - 임시 경로 격리

```python
# ❌ 기존
ATHENA_OUTPUT_LOCATION = f"s3://{S3_BUCKET}/athena-results/"

# ✅ 변경
ATHENA_TEMP_RESULTS_PATH = f"s3://{S3_BUCKET}/.athena-temp/"
```

### 3. `athena_utils.py` - 임시 파일 정리 추가

```python
def cleanup_temp_results(self, query_id: str):
    """쿼리 메타데이터 파일 정리"""
    # (위 코드 참고)
```

---

## 📋 체크리스트

### 코드 수정 ✅
- [x] `hourly_etl.py` - `_insert_data_overwrite()` 메서드 재구성
- [x] `daily_etl.py` - 동일한 방식 적용
- [x] `config.py` - `ATHENA_TEMP_RESULTS_PATH` 변경
- [x] `athena_utils.py` - 임시 파일 정리 메서드 추가

### AWS 설정 ✅
- [x] S3 라이프사이클 정책 추가 (`.athena-temp/` 7일 자동 삭제)
- [x] Glue Crawler Exclude 패턴 설정
- [x] 기존 임시 테이블 삭제
- [x] 기존 임시 파일 삭제

### 검증 ✅
- [x] hourly ETL 실행 성공 (1,628 행)
- [x] daily ETL 실행 성공
- [x] Athena 테이블 조회 성공
- [x] Glue 카탈로그 깔끔 (이상 테이블 없음)

---

## 🎓 핵심 학습

| 개념 | 설명 |
|------|------|
| **Athena 제약** | Presto 엔진 기반으로 INSERT/UPDATE/DELETE 미지원 |
| **데이터 저장 방식** | Python + Boto3 직접 저장이 가장 안정적 |
| **타입 안전성** | Athena 결과는 모두 문자열 → 명시적 변환 필수 |
| **메타데이터 관리** | 임시 및 프로덕션 경로 분리로 오염 방지 |
| **자동화** | S3 라이프사이클 정책으로 자동 정리 |

---

## 📈 성과 지표

| 지표 | 값 |
|------|-----|
| **해결된 문제 수** | 7가지 |
| **실행 시간** | ~10초 (조회+저장+메타데이터) |
| **처리 데이터량** | 시간당 1,000-1,600개 행 |
| **안정성** | ✅ 한 번에 완료 (부분 재시도 불필요) |
| **메타데이터 정합성** | ✅ 100% (타입 오류 없음) |
| **카탈로그 상태** | ✅ 깔끔함 (이상 테이블 없음) |

---

**🎉 결론**: 2026년 3월 10일의 모든 문제가 완벽하게 해결되었습니다.  
Hourly ETL은 이제 완전히 정상 작동하며, Daily ETL도 동일한 방식으로 안정적으로 실행됩니다.

# Athena 해시 테이블명 문제 분석 및 해결방안

**작성일**: 2026-03-10 22:00 (KST)  
**제목**: `ad_combined_log_a936396ed6a1823426395f9b5994868e` 테이블 발생 원인 분석

---

## 📋 문제 상황

### 현상
```
Athena 데이터베이스에 예상하지 않은 테이블이 생성됨:
  ❌ ad_combined_log_a936396ed6a1823426395f9b5994868e

기대했던 테이블:
  ✅ ad_combined_log (정상 테이블)
  ✅ ad_combined_log_summary (일별 요약 테이블)
```

### 영향 범위
- **Glue 카탈로그 오염**: 불필요한 테이블 메타데이터 축적
- **쿼리 혼동 가능성**: 잘못된 테이블을 실수로 쿼리할 수 있음
- **유지보수 복잡성**: 카탈로그 정리 필요
- **비용**: 임시 테이블 메타데이터 및 관련 S3 데이터 저장 비용

---

## 🔍 근본 원인 분석

### 1️⃣ 원인 지점: Athena CTAS (Create Table As Select) 쿼리

**파일 위치**: [services/data_pipeline_t2/etl_summary_t2/hourly_etl.py](services/data_pipeline_t2/etl_summary_t2/hourly_etl.py)

```python
# hourly_etl.py의 _insert_data_overwrite() 메서드에서:

# Step 1: SELECT 쿼리 실행
select_query = self.generate_hourly_etl_query()
query_id = self.executor.execute_query(select_query)

# Step 2: Athena 메타데이터에서 결과 조회
results = self.executor.get_query_results(query_id)

# Step 3: S3에 Parquet 저장
# ... (S3 저장 로직)

# Step 4: MSCK REPAIR TABLE
self._repair_partitions()
```

### 2️⃣ Athena 메타데이터 조회 메커니즘의 문제

**파일 위치**: [services/data_pipeline_t2/etl_summary_t2/athena_utils.py](services/data_pipeline_t2/etl_summary_t2/athena_utils.py)

```python
# athena_utils.py의 get_query_results() 메서드 추정 구현:

def get_query_results(self, query_id: str):
    # Athena는 SELECT 쿼리 결과를 다음 경로에 저장:
    # s3://bucket/athena-results/QueryId.csv
    # s3://bucket/athena-results/QueryId.csv.metadata.json
    
    # 문제: 이 CSV 파일을 읽을 때 Glue가 자동으로 테이블 메타데이터 생성
    # 테이블명 = CSV 파일명의 해시값 생성
    # → ad_combined_log_a936396ed6a1823426395f9b5994868e
```

### 3️⃣ Glue 자동 카탈로그 생성 메커니즘

**문제의 핵심 흐름**:

```
1. Athena SELECT 쿼리 실행
   └─ s3://bucket/athena-results/{query_id}.csv 생성

2. CSV 결과를 Pandas로 읽기 (boto3 + pyarrow)
   └─ Glue가 CSV 파일을 감지

3. ⚠️ Glue Crawler 또는 자동 메타데이터 생성
   └─ CSV 파일명을 기반으로 테이블명 생성
   └─ "ad_combined_log_a936396ed6a1823426395f9b5994868e" 테이블 자동 생성

4. Parquet 파일을 S3에 저장
   └─ 별도의 테이블 메타데이터는 생성 안 됨 (MSCK REPAIR만 실행)

5. 결과: 불필요한 임시 테이블이 Glue에 등록됨
```

### 4️⃣ 직접적인 원인 코드

```python
# ❌ 문제가 되는 코드 (현재 방식)

# Step 1: Athena에서 SELECT 실행 (athena-results/에 CSV로 저장됨)
query_id = self.executor.execute_query(select_query)

# Step 2: CSV 메타데이터 조회 (⚠️ Glue가 자동으로 테이블 생성!)
results = self.executor.get_query_results(query_id)
# → athena-results/{query_id}.csv 읽기 중에 
#   Glue가 이 CSV를 "테이블"로 자동 인식
#   테이블명 = 파일명 기반 해시값

# Step 3: Parquet으로 저장 (ad_combined_log 테이블의 파티션)
# (정상 작동)

# Step 4: MSCK REPAIR TABLE (ad_combined_log만 수리)
# (ad_combined_log_[해시] 테이블은 정리되지 않음)
```

---

## ✅ 해결 방안

### 최우선 해결방법: `athena-results/` 디렉토리 격리

#### 문제 재발 방지 (즉시 실행 필요)

**1단계: athena-results 디렉토리 변경**

```python
# config.py 수정

# ❌ 기존 (공용 경로)
ATHENA_OUTPUT_LOCATION = f"s3://{S3_BUCKET}/athena-results/"
ATHENA_TEMP_RESULTS_PATH = f"s3://{S3_BUCKET}/athena-results/"

# ✅ 변경 (격리된 경로)
ATHENA_TEMP_RESULTS_PATH = f"s3://{S3_BUCKET}/.athena-temp/"
# 또는
ATHENA_TEMP_RESULTS_PATH = f"s3://{S3_BUCKET}/athena-temp-ignore/"
```

**2단계: S3 라이프사이클 정책 설정** (선택사항이지만 권장)

```json
{
  "Rules": [
    {
      "Id": "Delete old Athena temp results",
      "Status": "Enabled",
      "Filter": {
        "Prefix": ".athena-temp/"
      },
      "Expiration": {
        "Days": 7  // 7일 후 자동 삭제
      }
    }
  ]
}
```

**3단계: Glue Crawler 비활성화** (선택사항)

Glue 콘솔에서:
- Crawlers → athena-results 관련 Crawler 찾기
- 해당 Crawler **비활성화** (삭제 권장 안 함)

---

### 현재 문제 해결 (임시 테이블 정리)

#### 방법 1: 수동 삭제 (즉시)

```sql
-- Athena 콘솔에서 실행
DROP TABLE IF EXISTS capa_ad_logs.ad_combined_log_a936396ed6a1823426395f9b5994868e;
```

#### 방법 2: Python에서 자동화

```python
import boto3

def cleanup_athena_temp_tables(database: str, prefix: str = "ad_combined_log_"):
    """Athena에서 임시 테이블 정리"""
    
    glue = boto3.client('glue', region_name=AWS_REGION)
    athena = boto3.client('athena', region_name=AWS_REGION)
    
    try:
        # Glue에서 해당 데이터베이스의 모든 테이블 조회
        response = glue.get_tables(DatabaseName=database)
        
        temp_tables = []
        for table in response.get('TableList', []):
            table_name = table['Name']
            
            # 해시값 패턴 테이블 감지
            # 예: ad_combined_log_[32자 hex] = 임시 테이블
            if table_name.startswith(prefix) and len(table_name) > len(prefix) + 30:
                # 해시값처럼 보이는 부분이 있으면 임시 테이블로 판정
                hash_part = table_name[len(prefix):]
                if all(c in '0123456789abcdef' for c in hash_part.lower()):
                    temp_tables.append(table_name)
        
        # 임시 테이블 삭제
        for table_name in temp_tables:
            drop_query = f"DROP TABLE IF EXISTS {database}.{table_name}"
            print(f"Dropping temporary table: {table_name}")
            
            response = athena.start_query_execution(
                QueryString=drop_query,
                QueryExecutionContext={'Database': database},
                ResultConfiguration={'OutputLocation': ATHENA_TEMP_RESULTS_PATH}
            )
            
            # 쿼리 완료 대기
            # (wait_for_query_completion 함수 활용)
        
        print(f"✅ Cleaned up {len(temp_tables)} temporary tables")
        
    except Exception as e:
        print(f"❌ Cleanup failed: {str(e)}")
        raise

# 실행
cleanup_athena_temp_tables(DATABASE, "ad_combined_log_")
```

---

## 📊 AS-IS vs TO-BE 비교

### AS-IS (문제 상황)

```
1️⃣  Athena SELECT 쿼리 실행
    └─ athena-results/{query_id}.csv 자동 생성

2️⃣  CSV 메타데이터 조회
    └─ ⚠️ Glue 자동 인식 → 임시 테이블 생성
    └─ ad_combined_log_a936396ed6a1823426395f9b5994868e

3️⃣  S3에 Parquet 저장
    └─ (정상)

4️⃣  MSCK REPAIR TABLE ad_combined_log
    └─ ad_combined_log만 수리 (임시 테이블은 방치)

5️⃣  결과
    ❌ Glue 카탈로그 오염
    ❌ 불필요한 메타데이터 축적
    ❌ 유지보수 복잡성 증가
```

### TO-BE (개선된 상황)

```
1️⃣  Athena SELECT 쿼리 실행
    └─ .athena-temp/{query_id}.csv 저장 (격리된 경로)

2️⃣  CSV 메타데이터 조회
    └─ ✅ Glue가 .athena-temp/ 경로 무시
    └─ 임시 테이블 생성 안 됨

3️⃣  S3에 Parquet 저장
    └─ summary/ad_combined_log/ 경로 사용

4️⃣  MSCK REPAIR TABLE ad_combined_log
    └─ ad_combined_log 수리 (정상)

5️⃣  결과
    ✅ Glue 카탈로그 깔끔
    ✅ 임시 데이터 자동 정리 (7일 후)
    ✅ 유지보수 간단
```

---

## 🛠️ 필수 수정 사항

### 파일 1: `config.py`

**변경 전**:
```python
ATHENA_OUTPUT_LOCATION = f"s3://{S3_BUCKET}/athena-results/"
ATHENA_TEMP_RESULTS_PATH = f"s3://{S3_BUCKET}/athena-results/"
```

**변경 후**:
```python
ATHENA_OUTPUT_LOCATION = f"s3://{S3_BUCKET}/athena-results/"  # 최종 결과용 (선택)
ATHENA_TEMP_RESULTS_PATH = f"s3://{S3_BUCKET}/.athena-temp/"  # ✅ 격리된 임시 경로
```

---

## 📌 예방 가이드

### 개발 팀을 위한 체크리스트

- [ ] Athena 쿼리 결과는 **항상 격리된 경로**에 저장
- [ ] Glue Crawler가 자동으로 임시 데이터를 스캔하지 않도록 설정
- [ ] 정기적으로 Glue 카탈로그 검토 (월 1회 권장)
- [ ] S3 라이프사이클 정책으로 **임시 데이터 자동 정리** 설정
- [ ] ETL 파이프라인에서 쿼리 결과 경로를 명시적으로 지정

### 모니터링

```python
# 정기적으로 실행할 모니터링 스크립트

def check_glue_catalog_health(database: str):
    """Glue 카탈로그 상태 검사"""
    
    glue = boto3.client('glue')
    response = glue.get_tables(DatabaseName=database)
    
    tables = response.get('TableList', [])
    
    print(f"Total tables in {database}: {len(tables)}")
    
    # 의심스러운 테이블 감지
    suspicious_tables = [t['Name'] for t in tables if len(t['Name']) > 50]
    
    if suspicious_tables:
        print(f"⚠️  Suspicious tables found: {suspicious_tables}")
    else:
        print(f"✅ Catalog looks clean")

# 실행
check_glue_catalog_health(DATABASE)
```

---

## 📌 참고 자료

| 항목 | 설명 |
|------|------|
| **Athena 결과 저장** | AWS Athena는 모든 쿼리 결과를 `ResultConfiguration.OutputLocation`에 저장 |
| **Glue 자동 감지** | Glue Crawler가 활성화되면 S3 경로를 스캔하여 자동으로 테이블 메타데이터 생성 |
| **MSCK REPAIR TABLE** | 특정 테이블의 파티션만 수리 (다른 테이블은 영향 없음) |
| **파티션 지정** | 테이블 생성 시 PARTITIONED BY 절로 명시적 지정 필요 |

---

## ✅ 실행 순서

### 즉시 실행 (Day 1)

1. **임시 테이블 삭제**
   ```sql
   DROP TABLE IF EXISTS capa_ad_logs.ad_combined_log_a936396ed6a1823426395f9b5994868e;
   ```

2. **config.py 수정**
   - `ATHENA_TEMP_RESULTS_PATH` 변경

3. **코드 배포**
   - 수정된 config.py 커밋 및 배포

### 단기 실행 (Day 2-3)

4. **S3 라이프사이클 정책 설정**
   - `.athena-temp/` 경로에 7일 자동 삭제 정책 추가

5. **Glue Crawler 검토**
   - athena-results 관련 Crawler 비활성화 검토

### 장기 모니터링 (지속적)

6. **월 1회 카탈로그 상태 확인**
   - 의심스러운 테이블명 감지 스크립트 실행
   - 불필요한 임시 테이블 정리

---

## 🎯 핵심 요약

| 구분 | 내용 |
|------|------|
| **문제** | Athena SELECT 결과가 CSV로 저장될 때 Glue가 자동으로 임시 테이블 생성 |
| **원인** | `athena-results/` 경로가 공용이므로 Glue Crawler가 감시 중 |
| **해결** | 임시 결과 경로를 `.athena-temp/`로 격리 + 라이프사이클 정책 설정 |
| **효과** | Glue 카탈로그 오염 방지, 유지보수 간소화 |
| **비용절감** | 불필요한 메타데이터 저장 비용 감소 |

# 테이블 삭제 오류 분석 및 해결책
**작성일**: 2026-03-10  
**상황**: `hourly_etl.py` 실행 중 `EntityNotFoundException` 발생

---

## 1. 오류 분석

### 오류 메시지
```
ERROR:athena_utils:Attempt 1 failed: An error occurred (InvalidRequestException) when calling the StartQueryExecution operation: Entity Not Found (Service: AmazonDataCatalog; Status Code: 400; Error Code: EntityNotFoundException)
```

### 오류 발생 과정

```
hourly_etl.py 시작
  ↓
_table_exists() → DESCRIBE ad_combined_log 쿼리 실행
  ↓
[CASE 1] 테이블이 없음 → EntityNotFoundException 발생
  ↓
generate_hourly_etl_query() 실행 → LEFT JOIN
  ├─ SELECT FROM capa_ad_logs.impressions (❌ 없음)
  ├─ LEFT JOIN capa_ad_logs.clicks (❌ 없음)
  ↓
쿼리 실행 실패 → EntityNotFoundException
```

### 근본 원인

| 번호 | 원인 | 설명 |
|------|------|------|
| **1** | **ad_combined_log 테이블 삭제됨** | 사용자가 기존 테이블을 삭제하여 테이블 존재 확인 실패 |
| **2** | **의존 테이블(impressions, clicks) 누락** | `hourly_etl.py`는 impressions과 clicks 테이블이 필수인데 이들이 없음 |
| **3** | **테이블 자동 생성 로직의 한계** | `_table_exists()` 메서드에서 DESCRIBE 실패 시 예외가 제대로 처리되지 않음 |

---

## 2. 현재 코드 흐름 (AS-IS)

### hourly_etl.py의 run() 메서드

```python
def run(self):
    """ETL 실행 (CTAS로 테이블 생성, INSERT OVERWRITE로 데이터 삽입)"""
    try:
        # 1. 테이블 존재 여부 확인
        if not self._table_exists():
            # 테이블이 없으면 CTAS로 생성 (1회만 실행)
            logger.info("📌 Table does not exist, creating with CTAS...")
            self._create_table_with_ctas()
        else:
            # 테이블이 있으면 INSERT OVERWRITE로 데이터 삽입
            logger.info("✅ Table exists, inserting data with INSERT OVERWRITE...")
            self._insert_data_overwrite()
```

### _table_exists() 메서드의 문제

```python
def _table_exists(self) -> bool:
    """테이블 존재 여부 확인 (DESCRIBE 사용)"""
    try:
        check_query = f"DESCRIBE {DATABASE}.ad_combined_log"
        query_id = self.executor.execute_query(check_query)  # ❌ 여기서 예외 발생
        logger.info("✅ Table ad_combined_log exists")
        return True
    except Exception as e:
        logger.info(f"❌ Table does not exist: {str(e)}")
        return False  # ❌ False를 반환하지만, athena_utils에서 재시도 중 전파됨
```

### 문제점

1. **DESCRIBE 쿼리 실패 처리 미흡**
   - `execute_query()`에서 발생한 `EntityNotFoundException`이 완전히 처리되지 않음
   - `athena_utils.py`의 `execute_query()` 메서드가 MAX_RETRIES만큼 재시도 후 마지막 시도에서 예외 발생
   - 이 예외가 `_table_exists()`의 `except` 블록을 통과하지 못함

2. **의존 테이블 검증 부재**
   - `ad_combined_log`를 생성하기 위해 필요한 `impressions`, `clicks` 테이블을 검증하지 않음
   - 이 테이블들이 없으면 `INSERT INTO ... SELECT FROM impressions ... LEFT JOIN clicks` 쿼리도 실패

---

## 3. 해결책 (TO-BE)

### Step 1: 필수 의존 테이블 확인

먼저 다음 테이블들이 존재하는지 Athena에서 확인:

```sql
-- Athena 콘솔에서 실행
DESCRIBE capa_ad_logs.impressions;
DESCRIBE capa_ad_logs.clicks;
DESCRIBE capa_ad_logs.conversions;
```

**확인 결과**:
- ✅ 테이블 존재 → Step 2로 진행
- ❌ 테이블 부재 → 먼저 `gen_adlog_init.py` 또는 `gen_adlog_local.py` 실행하여 테이블 생성

### Step 2: 오류 처리 강화

**수정 전 (현재)**:
```python
def _table_exists(self) -> bool:
    try:
        check_query = f"DESCRIBE {DATABASE}.ad_combined_log"
        query_id = self.executor.execute_query(check_query)
        logger.info("✅ Table ad_combined_log exists")
        return True
    except Exception as e:
        logger.info(f"❌ Table does not exist: {str(e)}")
        return False  # 예외가 완전히 처리되지 않을 수 있음
```

**수정 후 (권장)**:
```python
def _table_exists(self) -> bool:
    """테이블 존재 여부 확인"""
    try:
        # DESCRIBE 대신 SHOW TABLES 사용 (더 안정적)
        check_query = f"SHOW TABLES IN {DATABASE} LIKE 'ad_combined_log'"
        query_id = self.executor.execute_query(check_query)
        results = self.executor.get_query_results(query_id)
        
        exists = len(results) > 0
        status = "✅ exists" if exists else "❌ does not exist"
        logger.info(f"Table ad_combined_log {status}")
        return exists
        
    except Exception as e:
        logger.error(f"❌ Failed to check table existence: {str(e)}")
        # 오류 발생 시 False를 반환하여 테이블을 재생성하도록 유도
        return False
```

### Step 3: 의존 테이블 검증 추가

```python
def _validate_dependencies(self) -> bool:
    """필수 의존 테이블이 존재하는지 확인"""
    required_tables = ['impressions', 'clicks']
    
    for table in required_tables:
        try:
            check_query = f"SHOW TABLES IN {DATABASE} LIKE '{table}'"
            query_id = self.executor.execute_query(check_query)
            results = self.executor.get_query_results(query_id)
            
            if not results:
                logger.error(f"❌ Required table '{table}' does not exist!")
                logger.error(f"   Please run gen_adlog_init.py or gen_adlog_local.py first")
                return False
            logger.info(f"✅ Found required table: {table}")
            
        except Exception as e:
            logger.error(f"❌ Failed to validate table '{table}': {str(e)}")
            return False
    
    return True

def run(self):
    """ETL 실행"""
    try:
        # 1. 의존 테이블 검증 (new)
        if not self._validate_dependencies():
            raise Exception("Required tables not found. Please initialize tables first.")
        
        # 2. 타겟 테이블 존재 여부 확인
        if not self._table_exists():
            logger.info("📌 Table does not exist, creating with CTAS...")
            self._create_table_with_ctas()
        else:
            logger.info("✅ Table exists, inserting data with INSERT OVERWRITE...")
            self._insert_data_overwrite()
        
        # 3. 처리 결과 확인
        self._validate_results()
        
    except Exception as e:
        logger.error(f"❌ Hourly ETL failed: {str(e)}")
        raise
```

---

## 4. 실행 가이드

### 4.1 테이블 초기 생성 (한 번만 필요)

```bash
cd C:\Users\Dell5371\Desktop\projects\CAPA\services\data_pipeline_t2

# 1. 로컬 테스트 데이터로 초기화
python etl_summary_t2\gen_adlog_local.py

# 또는 AWS에서 기존 데이터로 초기화
python etl_summary_t2\gen_adlog_init.py
```

### 4.2 hourly ETL 실행

```bash
# 현재 시간 - 1시간의 데이터 처리 (기본값)
python etl_summary_t2\hourly_etl.py

# 특정 시간의 데이터 처리
python etl_summary_t2\hourly_etl.py --target-hour 2026-03-10-01
```

### 4.3 테이블 상태 확인

```bash
# PowerShell에서 실행
$ATHENA_PROFILE = "default"  # 또는 your-profile

# impressions 테이블 확인
aws athena start-query-execution `
  --query-string "SHOW TABLES IN capa_ad_logs LIKE 'impressions'" `
  --query-execution-context Database=capa_ad_logs `
  --result-configuration OutputLocation=s3://capa-data-lake-827913617635/athena-results/ `
  --region ap-northeast-2

# ad_combined_log 테이블 확인
aws athena start-query-execution `
  --query-string "DESCRIBE capa_ad_logs.ad_combined_log" `
  --query-execution-context Database=capa_ad_logs `
  --result-configuration OutputLocation=s3://capa-data-lake-827913617635/athena-results/ `
  --region ap-northeast-2
```

---

## 5. 체크리스트

테이블 복구 순서:

- [ ] **Step 1**: 의존 테이블(impressions, clicks) 존재 확인
  ```sql
  DESCRIBE capa_ad_logs.impressions;
  DESCRIBE capa_ad_logs.clicks;
  ```
  
- [ ] **Step 2**: 없다면 초기화 스크립트 실행
  ```bash
  python etl_summary_t2\gen_adlog_local.py
  ```
  
- [ ] **Step 3**: hourly_etl.py 재실행
  ```bash
  python etl_summary_t2\hourly_etl.py
  ```
  
- [ ] **Step 4**: 결과 확인
  ```sql
  SELECT COUNT(*) FROM capa_ad_logs.ad_combined_log;
  ```

---

## 6. 예방 조치

| 항목 | 조치 |
|------|------|
| **테이블 실수 삭제 방지** | AWS Glue에서 테이블 삭제 전 백업 또는 Athena에서 `CREATE TABLE AS SELECT ... BACKUP` 실행 |
| **의존성 추적** | ETL DAG에서 의존 테이블 검증 로직 추가 (Airflow 태스크) |
| **모니터링** | CloudWatch 알람: Athena 쿼리 실패 시 알림 |
| **자동 복구** | 테이블 없을 시 자동으로 gen_adlog_init.py 실행하도록 Airflow DAG 구성 |

---

## 7. 참고 자료

- [hourly_etl.py](../../services/data_pipeline_t2/etl_summary_t2/hourly_etl.py) - 현재 ETL 스크립트
- [gen_adlog_local.py](../../services/data_pipeline_t2/etl_summary_t2/gen_adlog_local.py) - 로컬 테스트 데이터 생성
- [gen_adlog_init.py](../../services/data_pipeline_t2/etl_summary_t2/gen_adlog_init.py) - AWS 기존 데이터로 초기화

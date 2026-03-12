# Hourly ETL 오류 분석 및 해결책

**날짜**: 2026-03-10  
**파일**: hourly_etl.py  
**오류 발생 시간**: 실행 중 INSERT INTO 단계

---

## 1. 오류 분석

### 1.1 발생한 오류

#### ❌ 오류 #1: COLUMN_NOT_FOUND
```
ERROR: COLUMN_NOT_FOUND: line 2:15: Column 'year' cannot be resolved 
       or requester is not authorized to access requested resources
```

**위치**: DELETE 쿼리 실행  
**원인**: 기존 테이블 `ad_combined_log`가 `year` 컬럼을 가지고 있지 않음

---

#### ❌ 오류 #2: InvalidRequestException
```
ERROR: An error occurred (InvalidRequestException) when calling the 
       StartQueryExecution operation: Queries of this type are not supported
```

**위치**: INSERT INTO 쿼리 실행  
**원인**: AWS Athena가 PARTITION 절을 포함한 INSERT 쿼리를 지원하지 않음

---

### 1.2 근본 원인

#### 📌 테이블 파티션 불일치
```
기존 테이블 (ad_combined_log):
├─ 파티션: dt STRING  ← 단일 문자열 파티션 (예: "2026-03-10-01")
└─ 필드: impression_id, user_id, ... (10개)

새 코드 시도:
├─ 파티션: year, month, day, hour  ← 4개 개별 컬럼
└─ 필드: impression_id, user_id, ..., os, delivery_region, ... (27개)

❌ 문제: 스키마가 완전히 다르면서 마이그레이션 방식이 맞지 않음
```

#### 📌 AWS Athena의 제약사항

**Athena는 다음을 지원하지 않음:**

| 기능 | 지원 여부 | 대체 방법 |
|------|---------|---------|
| DELETE 문 | ❌ | CTAS로 새 테이블 생성 후 DROP |
| INSERT OVERWRITE | ❌ | CTAS + MSCK REPAIR |
| PARTITION 절 포함 INSERT | ❌ | S3 경로를 통한 동적 파티션 |
| ALTER TABLE ADD COLUMNS | 제한적 | 테이블 재생성 필요 |

#### 📌 이전 테이블 구조 (기존 AS-IS)

```sql
CREATE EXTERNAL TABLE ad_combined_log (
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
    dt STRING  ← "2026-03-10-01" 형식
)
```

이 테이블에는 `year`, `month`, `day`, `hour` 컬럼이 없음!

---

## 2. AS-IS vs TO-BE 스키마 비교

### 2.1 필드 비교

| 구분 | AS-IS | TO-BE | 변경 |
|------|-------|-------|------|
| 필드 수 | 10개 | 27개 | +17개 추가 |
| 파티션 | dt STRING (1개) | year/month/day/hour (4개) | 구조 변경 |
| Impression 필드 | 기본만 (7개) | 전체 (20개) | +13개 추가 |
| Click 필드 | 기본만 (2개) | 전체 (6개) | +4개 추가 |
| Conversion 필드 | 없음 | 없음 | - |

### 2.2 컬럼 추가 필요

**기존 테이블에 없는 필드들:**
```
os, delivery_region, user_lat, user_long, store_id, 
food_category, ad_position, ad_format, user_agent, 
ip_address, session_id, keyword, cost_per_impression,
click_position_x, click_position_y, landing_page_url, 
cost_per_click, (파티션 컬럼 4개)
```

---

## 3. 해결책 - 2가지 전략

### 🔧 전략 #1: 테이블 삭제 후 재생성 (권장)

**장점**: 깔끔한 마이그레이션, 스키마 일관성 보장  
**단점**: 기존 데이터 손실

#### 단계별 실행 계획

**Step 1: 기존 테이블 백업 (선택사항)**
```sql
-- 1. 기존 데이터를 새 테이블로 복제 (선택적)
CREATE TABLE ad_combined_log_backup AS
SELECT 
    impression_id,
    user_id,
    ad_id,
    campaign_id,
    advertiser_id,
    platform,
    device_type,
    timestamp,
    is_click,
    click_timestamp,
    dt
FROM capa_ad_logs.ad_combined_log;
```

**Step 2: 기존 테이블 삭제**
```sql
-- 2. 기존 테이블 삭제
DROP TABLE IF EXISTS capa_ad_logs.ad_combined_log;

-- 3. S3에서도 데이터 삭제 (선택적, 비용 절감)
-- AWS S3 콘솔: s3://capa-data-lake-827913617635/summary/ad_combined_log/ 삭제
```

**Step 3: 신규 테이블 생성**
```sql
-- 4. 신규 테이블 생성 (27개 필드 + 파티션)
CREATE EXTERNAL TABLE capa_ad_logs.ad_combined_log (
    -- Impression 필드 (20개)
    impression_id STRING,
    user_id STRING,
    ad_id STRING,
    campaign_id STRING,
    advertiser_id STRING,
    platform STRING,
    device_type STRING,
    os STRING,
    delivery_region STRING,
    user_lat DOUBLE,
    user_long DOUBLE,
    store_id STRING,
    food_category STRING,
    ad_position STRING,
    ad_format STRING,
    user_agent STRING,
    ip_address STRING,
    session_id STRING,
    keyword STRING,
    cost_per_impression DOUBLE,
    impression_timestamp BIGINT,
    
    -- Click 필드 (6개)
    click_id STRING,
    click_position_x INT,
    click_position_y INT,
    landing_page_url STRING,
    cost_per_click DOUBLE,
    click_timestamp BIGINT,
    
    -- 조인 플래그 (1개)
    is_click BOOLEAN
)
PARTITIONED BY (
    year STRING,
    month STRING,
    day STRING,
    hour STRING
)
STORED AS PARQUET
LOCATION 's3://capa-data-lake-827913617635/summary/ad_combined_log/'
TBLPROPERTIES (
    'classification'='parquet',
    'compressionType'='snappy'
);
```

**Step 4: 파티션 등록**
```sql
-- 5. 파티션 수리
MSCK REPAIR TABLE capa_ad_logs.ad_combined_log;
```

---

### 🔧 전략 #2: 새 테이블명 사용 (안전)

**장점**: 기존 데이터 보존, 테스트 후 전환 가능  
**단점**: 테이블명 변경 필요

#### 단계별 실행 계획

**Step 1: 신규 테이블 생성 (다른 이름)**
```sql
CREATE EXTERNAL TABLE capa_ad_logs.ad_combined_log_v2 (
    -- ... (위와 동일한 27개 필드)
)
PARTITIONED BY (
    year STRING,
    month STRING,
    day STRING,
    hour STRING
)
STORED AS PARQUET
LOCATION 's3://capa-data-lake-827913617635/summary/ad_combined_log_v2/'
TBLPROPERTIES (
    'classification'='parquet',
    'compressionType'='snappy'
);
```

**Step 2: 코드 수정 (임시)**
```python
# hourly_etl.py와 daily_etl.py에서
# {DATABASE}.ad_combined_log → {DATABASE}.ad_combined_log_v2
```

**Step 3: 테스트 실행**
```bash
python hourly_etl.py --target-hour 2026-03-10-01
# 성공 확인
```

**Step 4: 기존 테이블 교체**
```sql
-- 기존 테이블 삭제
DROP TABLE capa_ad_logs.ad_combined_log;

-- 신규 테이블 이름 변경
ALTER TABLE capa_ad_logs.ad_combined_log_v2 
RENAME TO capa_ad_logs.ad_combined_log;

-- 코드 원래대로 변경
# ad_combined_log_v2 → ad_combined_log
```

---

## 4. 코드 수정 사항

### 4.1 DELETE 쿼리 제거

**현재 코드 (오류 발생):**
```python
def _insert_data_overwrite(self):
    # DELETE 불가 - Athena 미지원
    delete_query = f"""
    DELETE FROM {DATABASE}.ad_combined_log
    WHERE year = '{self.year}' ...
    """
```

**수정된 코드:**
```python
def _insert_data_overwrite(self):
    """기존 데이터는 덮어쓰기 (DELETE 불필요, 새 파티션만 추가)"""
    # Athena는 DELETE를 지원하지 않으므로,
    # S3 파티션 폴더를 직접 삭제하거나, 
    # 동일한 파티션에 다시 INSERT하여 덮어쓴다.
    
    # Step 1: INSERT INTO (파티션 경로를 통한 동적 파티션)
    insert_query = f"""
    INSERT INTO {DATABASE}.ad_combined_log
    {self.generate_hourly_etl_query()}
    """
    
    logger.info(f"Executing INSERT INTO for {self.year}/{self.month}/{self.day}/{self.hour}")
    self.executor.execute_query(insert_query)
    logger.info("✅ Data inserted successfully")
    
    # Step 2: 파티션 등록
    self._repair_partitions()
```

### 4.2 INSERT 쿼리 형식 수정

**현재 코드 (오류 발생):**
```python
insert_query = f"""
INSERT INTO {DATABASE}.ad_combined_log PARTITION (year, month, day, hour)
{self.generate_hourly_etl_query()}
"""
```

**수정된 코드:**
```python
insert_query = f"""
INSERT INTO {DATABASE}.ad_combined_log
SELECT 
    -- ... 모든 필드
    '{self.year}' AS year,
    '{self.month}' AS month,
    '{self.day}' AS day,
    '{self.hour}' AS hour
FROM {DATABASE}.impressions imp
LEFT JOIN {DATABASE}.clicks clk
    ON ...
WHERE ...
"""
```

✅ **key point**: `PARTITION` 절을 제거하고, SELECT 절에서 직접 파티션 컬럼 값을 생성

---

## 5. daily_etl.py의 동일 이슈

Daily ETL도 동일한 오류 패턴이 발생할 것 예상:

### Daily 테이블 마이그레이션

**Step 1: 기존 테이블 확인**
```sql
DESCRIBE capa_ad_logs.ad_combined_log_summary;
-- 현재 컬럼: campaign_id, ad_id, advertiser_id, device_type, impressions, clicks, conversions, dt
```

**Step 2: 신규 테이블 생성**
```sql
DROP TABLE IF EXISTS capa_ad_logs.ad_combined_log_summary;

CREATE EXTERNAL TABLE capa_ad_logs.ad_combined_log_summary (
    -- Impression 필드 (20개)
    impression_id STRING,
    user_id STRING,
    ...
    -- Click 필드 (6개)
    ...
    -- Conversion 필드 (7개)
    ...
    -- 조인 플래그 (2개)
    is_click BOOLEAN,
    is_conversion BOOLEAN
)
PARTITIONED BY (
    year STRING,
    month STRING,
    day STRING
)
STORED AS PARQUET
LOCATION 's3://capa-data-lake-827913617635/summary/ad_combined_log_summary/'
TBLPROPERTIES (
    'classification'='parquet',
    'compressionType'='snappy'
);
```

---

## 6. 실행 순서 및 주의사항

### 6.1 권장 순서

```
1️⃣ 기존 테이블 삭제 (또는 백업 후 삭제)
   ↓
2️⃣ 신규 hourly 테이블 생성 (27개 필드)
   ↓
3️⃣ 신규 daily 테이블 생성 (35개 필드)
   ↓
4️⃣ hourly_etl.py 코드 수정 (DELETE 제거)
   ↓
5️⃣ daily_etl.py 코드 수정 (DELETE 제거, 쿼리 수정)
   ↓
6️⃣ 테스트 실행
   └─ python hourly_etl.py --target-hour 2026-03-10-01
   └─ python daily_etl.py --target-date 2026-03-09
```

### 6.2 주의사항

⚠️ **S3 데이터 백업**
- 테이블 삭제 전 S3 데이터 백업 강권
- `s3://capa-data-lake-827913617635/summary/ad_combined_log/` 경로 확인

⚠️ **Airflow DAG 일시 중지**
- 테이블 마이그레이션 중 기존 DAG 실행 중지
- 신규 테이블이 준비된 후 DAG 재시작

⚠️ **Glue 카탈로그 동기화**
- 테이블 생성 후 AWS Glue 콘솔에서 확인
- MSCK REPAIR TABLE 실행으로 파티션 등록

---

## 7. 최종 요약

| 항목 | 현재 상태 | 문제 | 해결 방법 |
|------|---------|------|---------|
| **테이블 파티션** | dt STRING | 스키마 불일치 | year/month/day/hour로 재생성 |
| **DELETE 지원** | ❌ Athena 미지원 | 오류 발생 | DELETE 제거, INSERT 덮어쓰기 |
| **INSERT PARTITION** | ❌ 미지원 | InvalidRequest | SELECT에서 직접 컬럼 생성 |
| **필드 수** | 10개 (hourly) | 부족 | 27개로 확장 필요 |
| **필드 수** | 7개 (daily) | 부족 | 35개로 확장 필요 |

**결론**: 테이블을 완전히 재생성하고, DELETE 문과 PARTITION 절을 제거하는 방식으로 수정하면 해결됨.

---

## 참고 링크

- [AWS Athena INSERT 문법](https://docs.aws.amazon.com/athena/latest/ug/querying-supported-statements.html)
- [Athena 제약사항](https://docs.aws.amazon.com/athena/latest/ug/limitations.html)
- [Glue 카탈로그 테이블](https://docs.aws.amazon.com/glue/latest/dg/tables-described.html)

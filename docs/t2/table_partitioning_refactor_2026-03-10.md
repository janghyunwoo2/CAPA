# ETL 테이블 파티셔닝 구조 개선 계획

**작성일**: 2026-03-10  
**대상**: hourly_etl.py, daily_etl.py, config.py  
**목표**: Athena 쿼리 성능 최적화를 위한 파티션 구조 통일화

---

## 1. 현재 상태 (AS-IS)

### 1.1 테이블 구조

#### ad_combined_log (Hourly)
```
CREATE EXTERNAL TABLE ad_combined_log (
    -- Impression 필드
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
    
    -- Click 필드
    click_id STRING,
    click_position_x INT,
    click_position_y INT,
    landing_page_url STRING,
    cost_per_click DOUBLE,
    click_timestamp BIGINT,
    
    -- 조인 플래그
    is_click BOOLEAN
)
PARTITIONED BY (
    dt STRING  ← 단일 문자열 파티션 (예: "2026-02-24-14")
)
```

#### ad_combined_log_summary (Daily)
```
CREATE EXTERNAL TABLE ad_combined_log_summary (
    -- Hourly 필드와 동일 (impression 20 + click 6 + is_click 1)
    -- Impression 필드
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
    
    -- Click 필드
    click_id STRING,
    click_position_x INT,
    click_position_y INT,
    landing_page_url STRING,
    cost_per_click DOUBLE,
    click_timestamp BIGINT,
    
    -- 조인 플래그 (Hourly와 동일)
    is_click BOOLEAN,
    
    -- Conversion 필드만 추가
    conversion_id STRING,
    conversion_type STRING,
    conversion_value DOUBLE,
    product_id STRING,
    quantity INT,
    attribution_window STRING,
    conversion_timestamp BIGINT,
    is_conversion BOOLEAN
)
PARTITIONED BY (
    year STRING  ← 개별 파티션 컬럼
    month STRING  ← 개별 파티션 컬럼
    day STRING  ← 개별 파티션 컬럼
)
```

### 1.2 S3 저장 경로

```
S3 구조:
├─ summary/
   ├─ ad_combined_log/
   │  └─ (파티션 구조 없음 - 모든 데이터가 루트에 저장됨)
   └─ ad_combined_log_summary/
      └─ (파티션 구조 없음 - 모든 데이터가 루트에 저장됨)
```

### 1.3 문제점

1. **파티션 부재**: 파티션 파일 구조가 없어 S3 스캔 범위 최적화 불가
2. **Athena 성능 저하**: WHERE 절에 연도/월/일/시 조건이 있어도 S3 전체 스캔 발생
3. **비용 증가**: 불필요한 데이터 스캔으로 Athena 요금 증가
4. **일관성 부족**: 원본 raw 테이블(impressions, clicks, conversions)은 year/month/day/hour 파티션 사용하지만 summary 테이블은 dt 문자열 사용

---

## 2. 개선된 상태 (TO-BE)

### 2.1 테이블 구조

#### ad_combined_log (Hourly)
```
CREATE EXTERNAL TABLE ad_combined_log (
    -- Impression 필드
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
    
    -- Click 필드
    click_id STRING,
    click_position_x INT,
    click_position_y INT,
    landing_page_url STRING,
    cost_per_click DOUBLE,
    click_timestamp BIGINT,
    
    -- 조인 플래그
    is_click BOOLEAN
)
PARTITIONED BY (
    year STRING,      ← 개별 파티션 컬럼
    month STRING,     ← 개별 파티션 컬럼
    day STRING,       ← 개별 파티션 컬럼
    hour STRING       ← 개별 파티션 컬럼
)
STORED AS PARQUET
LOCATION 's3://capa-data-lake-827913617635/summary/ad_combined_log/'
```

#### ad_combined_log_summary (Daily)
```
CREATE EXTERNAL TABLE ad_combined_log_summary (
    -- Hourly 필드와 동일 (impression 20 + click 6 + is_click 1)
    -- Impression 필드
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
    
    -- Click 필드
    click_id STRING,
    click_position_x INT,
    click_position_y INT,
    landing_page_url STRING,
    cost_per_click DOUBLE,
    click_timestamp BIGINT,
    
    -- 조인 플래그 (Hourly 상속)
    is_click BOOLEAN,
    
    -- Conversion 필드만 추가
    conversion_id STRING,
    conversion_type STRING,
    conversion_value DOUBLE,
    product_id STRING,
    quantity INT,
    attribution_window STRING,
    conversion_timestamp BIGINT,
    is_conversion BOOLEAN
)
PARTITIONED BY (
    year STRING,      ← 개별 파티션 컬럼
    month STRING,     ← 개별 파티션 컬럼
    day STRING        ← 개별 파티션 컬럼
)
STORED AS PARQUET
LOCATION 's3://capa-data-lake-827913617635/summary/ad_combined_log_summary/'
TBLPROPERTIES (
    'parquet.compression'='snappy'
)
```

**필드 구성 (상속 방식)**:
- Hourly 상속: 27개 (impression 20 + click 6 + is_click 1)
- Daily 추가: 8개 (conversion 7 + is_conversion 1)
- **총 35개 필드**

### 2.2 S3 저장 경로 구조

```
S3 구조:
├─ summary/
   ├─ ad_combined_log/
   │  └─ year=2026/
   │     └─ month=02/
   │        └─ day=24/
   │           └─ hour=14/
   │              └─ *.parquet
   └─ ad_combined_log_summary/
      └─ year=2026/
         └─ month=02/
            └─ day=24/
               └─ *.parquet
```

### 2.3 개선사항 및 데이터 흐름

1. **계층적 ETL 구조**
   - Hourly: impressions LEFT JOIN clicks → ad_combined_log
   - Daily: ad_combined_log (24건) LEFT JOIN conversions → ad_combined_log_summary

2. **파티션 파일 구조**: S3에서 year=/month=/day=/[hour=] 디렉토리 구조로 저장
3. **Athena 성능 향상**: WHERE 절의 파티션 컬럼 조건으로 S3 스캔 최소화
4. **비용 절감**: 필요한 파티션만 스캔하여 Athena 요금 감소
5. **확장성**: 향후 weekly, monthly 테이블 추가 시 동일한 패턴 적용 가능

---

## 3. 구현 변경 사항

### 3.1 hourly_etl.py 변경사항

#### 쿼리 변경점

**현재 코드:**
```python
def generate_hourly_etl_query(self) -> str:
    query = f"""
    SELECT 
        imp.impression_id,
        imp.user_id,
        imp.ad_id,
        imp.campaign_id,
        imp.advertiser_id,
        imp.platform,
        imp.device_type,
        imp.timestamp,
        CASE WHEN clk.click_id IS NOT NULL THEN true ELSE false END AS is_click,
        clk.timestamp AS click_timestamp,
        '{self.hour_str}' AS dt
    FROM {DATABASE}.impressions imp
    LEFT JOIN {DATABASE}.clicks clk
        ON imp.impression_id = clk.impression_id
    WHERE imp.year = '{self.year}' ...
    """
```

**개선 코드:**
```python
def generate_hourly_etl_query(self) -> str:
    query = f"""
    SELECT 
        -- Impression 필드
        imp.impression_id,
        imp.user_id,
        imp.ad_id,
        imp.campaign_id,
        imp.advertiser_id,
        imp.platform,
        imp.device_type,
        imp.os,
        imp.delivery_region,
        imp.user_lat,
        imp.user_long,
        imp.store_id,
        imp.food_category,
        imp.ad_position,
        imp.ad_format,
        imp.user_agent,
        imp.ip_address,
        imp.session_id,
        imp.keyword,
        imp.cost_per_impression,
        imp.timestamp AS impression_timestamp,
        
        -- Click 필드
        clk.click_id,
        clk.click_position_x,
        clk.click_position_y,
        clk.landing_page_url,
        clk.cost_per_click,
        clk.timestamp AS click_timestamp,
        
        -- 조인 플래그
        CASE WHEN clk.click_id IS NOT NULL THEN true ELSE false END AS is_click,
        
        -- 파티션 컬럼
        '{self.year}' AS year,
        '{self.month}' AS month,
        '{self.day}' AS day,
        '{self.hour}' AS hour
    FROM {DATABASE}.impressions imp
    LEFT JOIN {DATABASE}.clicks clk
        ON imp.impression_id = clk.impression_id
        AND clk.year = '{self.year}'
        AND clk.month = '{self.month}'
        AND clk.day = '{self.day}'
        AND clk.hour = '{self.hour}'
    WHERE imp.year = '{self.year}'
        AND imp.month = '{self.month}'
        AND imp.day = '{self.day}'
        AND imp.hour = '{self.hour}'
    """
```

#### 테이블 생성 변경점

**현재 코드:**
```sql
CREATE EXTERNAL TABLE IF NOT EXISTS {DATABASE}.ad_combined_log (
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
LOCATION '{S3_PATHS["ad_combined_log"]}'
```

**개선 코드:**
```sql
CREATE EXTERNAL TABLE IF NOT EXISTS {DATABASE}.ad_combined_log (
    -- Impression 필드
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
    
    -- Click 필드
    click_id STRING,
    click_position_x INT,
    click_position_y INT,
    landing_page_url STRING,
    cost_per_click DOUBLE,
    click_timestamp BIGINT,
    
    -- 조인 플래그
    is_click BOOLEAN
)
PARTITIONED BY (
    year STRING,
    month STRING,
    day STRING,
    hour STRING
)
STORED AS PARQUET
LOCATION '{S3_PATHS["ad_combined_log"]}'
TBLPROPERTIES (
    'classification'='parquet',
    'compressionType'='snappy'
)
```

#### INSERT 쿼리 변경점

**현재 코드:**
```sql
INSERT INTO {DATABASE}.ad_combined_log
SELECT ... FROM ...
```

**개선 코드:**
```sql
INSERT INTO {DATABASE}.ad_combined_log PARTITION (year, month, day, hour)
SELECT ... FROM ...
```

---

### 3.2 daily_etl.py 변경사항

#### 쿼리 변경점

**현재 코드:**
```python
def generate_daily_etl_query(self) -> str:
    # Raw 테이블에서 직접 읽음
    query = f"""
    SELECT ...
    FROM impressions, clicks, conversions ...
    """
    """
```

**개선 코드:**
```python
def generate_daily_etl_query(self) -> str:
    # ad_combined_log (hourly) 24건 + conversions 하루치 조합
    query = f"""
    SELECT 
        -- Impression 필드
        acl.impression_id,
        acl.user_id,
        acl.ad_id,
        acl.campaign_id,
        acl.advertiser_id,
        acl.platform,
        acl.device_type,
        acl.os,
        acl.delivery_region,
        acl.user_lat,
        acl.user_long,
        acl.store_id,
        acl.food_category,
        acl.ad_position,
        acl.ad_format,
        acl.user_agent,
        acl.ip_address,
        acl.session_id,
        acl.keyword,
        acl.cost_per_impression,
        acl.impression_timestamp,
        
        -- Click 필드
        acl.click_id,
        acl.click_position_x,
        acl.click_position_y,
        acl.landing_page_url,
        acl.cost_per_click,
        acl.click_timestamp,
        
        -- Conversion 필드
        conv.conversion_id,
        conv.conversion_type,
        conv.conversion_value,
        conv.product_id,
        conv.quantity,
        conv.attribution_window,
        conv.timestamp AS conversion_timestamp,
        
        -- 조인 플래그
        acl.is_click,
        CASE WHEN conv.conversion_id IS NOT NULL THEN true ELSE false END AS is_conversion,
        
        -- 파티션 컬럼
        '{self.year}' AS year,
        '{self.month}' AS month,
        '{self.day}' AS day
    FROM {DATABASE}.ad_combined_log acl  -- Hourly 테이블 (24건)
    LEFT JOIN {DATABASE}.conversions conv
        ON acl.impression_id = conv.impression_id
        AND conv.year = '{self.year}'
        AND conv.month = '{self.month}'
        AND conv.day = '{self.day}'
    WHERE acl.year = '{self.year}'
        AND acl.month = '{self.month}'
        AND acl.day = '{self.day}'
    """
```

#### 테이블 생성 변경점

**현재 코드:**
```sql
CREATE EXTERNAL TABLE IF NOT EXISTS {DATABASE}.ad_combined_log_summary (
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
LOCATION '{S3_PATHS["ad_combined_log_summary"]}'
```

**개선 코드:**
```sql
CREATE EXTERNAL TABLE IF NOT EXISTS {DATABASE}.ad_combined_log_summary (
    -- Impression 필드
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
    
    -- Click 필드
    click_id STRING,
    click_position_x INT,
    click_position_y INT,
    landing_page_url STRING,
    cost_per_click DOUBLE,
    click_timestamp BIGINT,
    
    -- Conversion 필드
    conversion_id STRING,
    conversion_type STRING,
    conversion_value DOUBLE,
    product_id STRING,
    quantity INT,
    attribution_window STRING,
    conversion_timestamp BIGINT,
    
    -- 조인 플래그
    is_click BOOLEAN,
    is_conversion BOOLEAN
)
PARTITIONED BY (
    year STRING,
    month STRING,
    day STRING
)
STORED AS PARQUET
LOCATION '{S3_PATHS["ad_combined_log_summary"]}'
TBLPROPERTIES (
    'classification'='parquet',
    'compressionType'='snappy'
)
```

#### INSERT 쿼리 변경점

**현재 코드:**
```sql
INSERT INTO {DATABASE}.ad_combined_log_summary
SELECT ... FROM ...
```

**개선 코드:**
```sql
INSERT INTO {DATABASE}.ad_combined_log_summary PARTITION (year, month, day)
SELECT ... FROM ...
```

---

### 3.3 config.py 변경사항

#### S3_PATHS 변경

**현재 코드:**
```python
S3_PATHS = {
    "ad_combined_log": f"s3://{S3_BUCKET}/summary/ad_combined_log/",
    "ad_combined_log_summary": f"s3://{S3_BUCKET}/summary/ad_combined_log_summary/"
}
```

**개선 코드:**
```python
S3_PATHS = {
    "ad_combined_log": f"s3://{S3_BUCKET}/{SUMMARY_PREFIX}/ad_combined_log/",
    "ad_combined_log_summary": f"s3://{S3_BUCKET}/{SUMMARY_PREFIX}/ad_combined_log_summary/"
}
```
*(기본적으로 동일하지만, 파티션 구조는 S3의 실제 디렉토리 레이아웃에 의해 자동으로 관리됨)*

#### PARTITION_KEYS 변경

**현재 코드:**
```python
PARTITION_KEYS = {
    "ad_combined_log": ["year", "month", "day", "hour"],
    "ad_combined_log_summary": ["year", "month", "day"]
}
```

**개선 코드:**
```python
PARTITION_KEYS = {
    "ad_combined_log": ["year", "month", "day", "hour"],
    "ad_combined_log_summary": ["year", "month", "day"]
}
```
*(이미 올바르게 정의되어 있으므로 유지)*

---

## 4. 추가 고려사항

### 4.1 CREATE TABLE IF NOT EXISTS 로직

현재 `_table_exists()` 메서드는 정상 작동하므로 유지:

```python
def _table_exists(self) -> bool:
    """테이블 존재 여부 확인 (DESCRIBE 사용)"""
    try:
        check_query = f"DESCRIBE {DATABASE}.ad_combined_log"
        query_id = self.executor.execute_query(check_query)
        logger.info("✅ Table exists")
        return True
    except Exception as e:
        logger.info(f"❌ Table does not exist: {str(e)}")
        return False
```

- ✅ 테이블이 존재하지 않을 때만 `_create_table_with_ctas()` 호출
- ✅ 테이블이 존재할 때는 `_insert_data_overwrite()` 호출

### 4.2 마이그레이션 전략

기존 데이터가 있다면:

1. **옵션 1**: 신규 테이블명 사용 후 데이터 복제
   - `ad_combined_log_v2` 와 같이 새로운 테이블 생성
   - 파티션 구조로 데이터 마이그레이션
   - 검증 후 테이블 이름 변경

2. **옵션 2**: 기존 테이블 백업 후 재생성
   - `ad_combined_log_backup` 으로 이름 변경
   - 새로운 파티션 구조로 테이블 재생성
   - 데이터 복제

---

## 5. 예상 효과

| 항목 | AS-IS | TO-BE | 개선도 |
|------|-------|-------|--------|
| 파티션 구조 | dt (문자열) | year/month/day/hour | 구조화됨 |
| S3 스캔 범위 | 100% | 1~5% | 95% 감소 |
| Athena 비용 | 기준 | 기준 × 0.01~0.05 | 95~99% 절감 |
| 쿼리 응답 시간 | 30~60초 | 1~3초 | 10~60배 향상 |
| Hourly 데이터 포함도 | 제한적 | 100% (imp/clk) | 완전성 확보 |
| Daily 데이터 포함도 | 제한적 | 100% (imp/clk/cvs) | 완전성 확보 |
| Hourly 컬럼 수 | ~10개 | ~40개 | 4배 확장 |
| Daily 컬럼 수 | ~10개 | ~47개 | 4.7배 확장 |
| 원본 테이블 일관성 | ✗ | ✓ | 개선 |
| 분석 지표 | 기본 (건수) | 심화 (비용, CVR, ROI 등) | 다양성 향상 |

---

## 6. 구현 일정

1. **검증 (1일)**: 기존 코드 동작 확인, 테스트 환경 준비
2. **코드 수정 (1일)**: hourly_etl.py, daily_etl.py, config.py 수정
3. **테스트 (1일)**: 로컬 및 개발 환경에서 파티션 생성 확인
4. **배포 (1일)**: Airflow DAG에 반영, 프로덕션 실행

---

## 7. 참고사항

### 테이블 구조 관련
- ✅ 테이블명 통일: `ad_combined_log` (hourly), `ad_combined_log_summary` (daily)
- ✅ **계층적 구조**: hourly → daily (daily는 hourly를 기반으로 conversion 추가)
- ✅ Hourly 데이터: impressions LEFT JOIN clicks (conversion은 데이터 소량으로 비효율)
- ✅ Daily 데이터: ad_combined_log (hourly 24건) LEFT JOIN conversions (일괄 처리)
- ✅ NULL 처리: 클릭/전환이 없는 경우 해당 필드는 NULL (LEFT JOIN)
- ✅ 조인 플래그: hourly는 `is_click`, daily는 `is_click + is_conversion`

### 파티셔닝 관련
- ✅ CTAS 전략: CREATE IF NOT EXISTS + DESCRIBE 기반 확인
- ✅ 파티셔닝: S3 경로에 year=/month=/day=/hour= 구조 자동 생성
- ✅ INSERT 전략: PARTITION 명시적 선언으로 동적 파티션 생성

### 호환성 및 쿼리
- ✅ 데이터 파이프라인: raw 테이블 → hourly 테이블 → daily 테이블 (계층적)
- ✅ 재사용성: hourly 테이블 데이터를 daily에서 재사용하여 중복 계산 제거
- ✅ 확장성: weekly, monthly 추가 시 daily 테이블 활용 가능

### 데이터 품질 및 파이프라인
- ✅ 실시간성: Hourly는 매시간 집계 (impression + click 실시간 추적)
- ✅ 완전성: Daily는 매일 02시 이후 집계 (conversion 데이터 포함)
- ✅ 속성 보존: 모든 impression, click, conversion 필드를 그대로 저장
- ✅ 추적 가능성: is_click, is_conversion 플래그로 데이터 존재 여부 명시

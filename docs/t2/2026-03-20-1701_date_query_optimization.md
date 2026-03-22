# 날짜 쿼리 최적화 분석

## 현재 상황

### AS-IS: 복잡한 날짜 조건
```sql
WHERE 
    date_parse(concat(CAST(year AS VARCHAR), '-', 
                     LPAD(CAST(month AS VARCHAR), 2, '0'), '-', 
                     LPAD(CAST(day AS VARCHAR), 2, '0')), '%Y-%m-%d')
    BETWEEN week_start AND week_end
```

### TO-BE: 간단한 날짜 조건 (희망사항)
```sql
WHERE dt >= '2026-02-27' and dt < '2026-03-05'
```

## 문제점 분석

### 1. 테이블 구조 문제
현재 `ad_combined_log_summary` 테이블은 날짜를 분리된 컬럼으로 저장:
- `year`: 2026
- `month`: 3
- `day`: 20
- `hour`: 17 (hourly 테이블의 경우)

단일 `dt` 또는 `date` 컬럼이 없어서 복잡한 변환이 필요합니다.

### 2. 파티셔닝 구조
S3 파티셔닝이 `year=2026/month=03/day=20/` 형태로 되어 있어, 테이블 구조도 이에 맞춰져 있습니다.

## 해결 방법

### 방법 1: View 생성 (권장)
```sql
CREATE OR REPLACE VIEW ad_combined_log_summary_v AS
SELECT 
    *,
    date_parse(concat(CAST(year AS VARCHAR), '-', 
                     LPAD(CAST(month AS VARCHAR), 2, '0'), '-', 
                     LPAD(CAST(day AS VARCHAR), 2, '0')), '%Y-%m-%d') as dt
FROM ad_combined_log_summary;
```

**장점**:
- 기존 테이블 구조 변경 없음
- 즉시 적용 가능
- 쿼리 단순화

**사용 예시**:
```sql
-- View 사용 시
SELECT * FROM ad_combined_log_summary_v
WHERE dt >= DATE('2026-02-27') AND dt < DATE('2026-03-05')
```

### 방법 2: ETL 프로세스 수정
`services/data_pipeline_t2/etl_summary_t2/daily_etl.py` 수정:
```python
# DataFrame에 dt 컬럼 추가
df['dt'] = pd.to_datetime(df[['year', 'month', 'day']])

# Parquet 저장 시 dt 컬럼 포함
df.to_parquet(temp_file_path, ...)
```

**장점**:
- 쿼리 성능 향상
- 날짜 연산 단순화

**단점**:
- 기존 데이터 재처리 필요
- ETL 프로세스 수정 필요

### 방법 3: Athena Generated Column 활용 (Athena 3 이상)
```sql
ALTER TABLE ad_combined_log_summary
ADD COLUMN dt date GENERATED ALWAYS AS (
    date_parse(concat(CAST(year AS VARCHAR), '-', 
                     LPAD(CAST(month AS VARCHAR), 2, '0'), '-', 
                     LPAD(CAST(day AS VARCHAR), 2, '0')), '%Y-%m-%d')
) STORED;
```

**주의**: AWS Athena 버전 확인 필요

## 즉시 사용 가능한 대안

### CTE를 활용한 쿼리 템플릿
```sql
WITH date_enhanced AS (
    SELECT 
        *,
        date_parse(concat(CAST(year AS VARCHAR), '-', 
                         LPAD(CAST(month AS VARCHAR), 2, '0'), '-', 
                         LPAD(CAST(day AS VARCHAR), 2, '0')), '%Y-%m-%d') as dt
    FROM ad_combined_log_summary
)
SELECT * FROM date_enhanced
WHERE dt >= DATE('{{ start_date }}') 
  AND dt < DATE('{{ end_date }}')
```

### 파티션 프루닝을 활용한 최적화
```sql
-- 파티션 조건을 먼저 적용하여 스캔 범위 축소
WHERE year = 2026 
  AND month = 3
  AND day BETWEEN 1 AND 7
  AND date_parse(...) BETWEEN '2026-03-01' AND '2026-03-07'
```

## 권장 사항

### 단기 해결책
1. **View 생성** (방법 1) - 즉시 적용 가능
2. Redash에서 공통 CTE 템플릿 활용

### 장기 해결책
1. **ETL 프로세스 개선** (방법 2)
   - 새로운 데이터부터 dt 컬럼 추가
   - 기존 데이터는 점진적으로 마이그레이션

### Redash 쿼리 개선 예시
```sql
-- 개선된 주간 분석 쿼리
WITH date_params AS (
    SELECT 
        DATE('{{ week_end_date }}') - INTERVAL '6' DAY as week_start,
        DATE('{{ week_end_date }}') as week_end
),
data_with_dt AS (
    SELECT 
        *,
        date_parse(concat(CAST(year AS VARCHAR), '-', 
                         LPAD(CAST(month AS VARCHAR), 2, '0'), '-', 
                         LPAD(CAST(day AS VARCHAR), 2, '0')), '%Y-%m-%d') as dt
    FROM ad_combined_log_summary
    WHERE 
        -- 파티션 프루닝을 위한 조건 추가
        year = YEAR(DATE('{{ week_end_date }}'))
        AND month IN (
            MONTH(DATE('{{ week_end_date }}') - INTERVAL '6' DAY),
            MONTH(DATE('{{ week_end_date }}'))
        )
)
SELECT 
    advertiser_id,
    SUM(CASE WHEN is_conversion THEN conversion_value ELSE 0 END) as weekly_revenue
    -- ... 나머지 집계
FROM data_with_dt
CROSS JOIN date_params
WHERE dt BETWEEN week_start AND week_end
GROUP BY advertiser_id
```

## 성능 비교

### 현재 방식
- 모든 행에 대해 문자열 연결과 파싱 수행
- 인덱스 활용 불가

### 개선 후
- View 또는 Generated Column으로 사전 계산
- 파티션 프루닝으로 스캔 범위 축소
- 날짜 비교 연산 단순화

## 결론

현재는 테이블 구조상 `dt >= '2026-02-27'` 형태의 간단한 쿼리를 직접 사용할 수 없습니다. 하지만 View 생성이나 CTE 활용으로 쿼리를 단순화할 수 있으며, 장기적으로는 ETL 프로세스를 개선하여 dt 컬럼을 추가하는 것을 권장합니다.
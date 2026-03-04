# Athena 기간별 데이터 조회 쿼리 모음

> **중요**: 이 문서의 쿼리들은 2026년 2월 16-22일 데이터를 기준으로 작성되었습니다.
> 다른 날짜의 데이터를 조회하려면 WHERE 절의 날짜를 변경하세요.

## 0. 데이터 확인 쿼리 (먼저 실행)

### 0-1. 실제 저장된 데이터 날짜 확인
```sql
-- 파티션된 모든 날짜 확인
SELECT DISTINCT year, month, day
FROM capa_ad_logs.impressions
WHERE year = 2026
ORDER BY year, month, day;
```

### 0-2. 각 날짜별 데이터 건수 확인
```sql
-- 2월 전체 데이터 건수 확인
SELECT year, month, day, COUNT(*) as count
FROM capa_ad_logs.impressions
WHERE year = 2026 AND month = 2
GROUP BY year, month, day
ORDER BY year, month, day;
```

## 1. 기간별 데이터 조회 기본 패턴

### 1-1. 특정 날짜 데이터 조회
```sql
-- 2026년 2월 16일 전체 데이터 (실제 생성한 날짜)
SELECT * FROM capa_ad_logs.impressions
WHERE year = 2026 AND month = 2 AND day = 16
LIMIT 100;
```

### 1-2. 날짜 범위 데이터 조회
```sql
-- 2026년 2월 16일부터 22일까지 데이터 (실제 생성한 기간)
SELECT * FROM capa_ad_logs.impressions
WHERE year = 2026 AND month = 2 
  AND day BETWEEN 16 AND 22
ORDER BY timestamp DESC;
```

### 1-3. 특정 시간대 데이터 조회
```sql
-- 2026년 2월 20일 점심시간(11-14시) 데이터
SELECT * FROM capa_ad_logs.impressions
WHERE year = 2026 AND month = 2 AND day = 20
  AND hour BETWEEN 11 AND 14
ORDER BY timestamp;
```

## 2. 기간별 통계 분석

### 2-1. 일별 노출/클릭/전환 통계
```sql
WITH daily_stats AS (
    SELECT 
        i.year,
        i.month,
        i.day,
        COUNT(DISTINCT i.impression_id) as impressions,
        COUNT(DISTINCT c.click_id) as clicks,
        COUNT(DISTINCT cv.conversion_id) as conversions
    FROM capa_ad_logs.impressions i
    LEFT JOIN capa_ad_logs.clicks c 
        ON i.impression_id = c.impression_id
        AND i.year = c.year AND i.month = c.month AND i.day = c.day
    LEFT JOIN capa_ad_logs.conversions cv 
        ON c.click_id = cv.click_id
        AND c.year = cv.year AND c.month = cv.month AND c.day = cv.day
    WHERE i.year = 2026 AND i.month = 2
        AND i.day BETWEEN 16 AND 22
    GROUP BY i.year, i.month, i.day
)
SELECT 
    CONCAT(year, '-', LPAD(CAST(month AS VARCHAR), 2, '0'), '-', LPAD(CAST(day AS VARCHAR), 2, '0')) as date,
    impressions,
    clicks,
    conversions,
    ROUND(CAST(clicks AS DOUBLE) / impressions * 100, 2) as ctr,
    ROUND(CAST(conversions AS DOUBLE) / impressions * 100, 4) as cvr
FROM daily_stats
ORDER BY year, month, day;
```

### 2-2. 시간별 트렌드 분석 (특정 기간)
```sql
-- 최근 3일간 시간별 트렌드
SELECT 
    CONCAT(year, '-', LPAD(CAST(month AS VARCHAR), 2, '0'), '-', LPAD(CAST(day AS VARCHAR), 2, '0'), ' ', LPAD(CAST(hour AS VARCHAR), 2, '0'), ':00') as datetime,
    COUNT(*) as impressions,
    SUM(cost_per_impression) as total_cost
FROM capa_ad_logs.impressions
WHERE year = 2026 AND month = 2 
    AND day BETWEEN 20 AND 22
GROUP BY year, month, day, hour
ORDER BY year, month, day, hour;
```

### 2-3. 주간 비교 분석
```sql
-- 이번주 vs 지난주 비교
WITH this_week AS (
    SELECT 
        COUNT(*) as impressions,
        COUNT(DISTINCT user_id) as unique_users,
        AVG(cost_per_impression) as avg_cpm
    FROM capa_ad_logs.impressions
    WHERE year = 2026 AND month = 2 
        AND day BETWEEN 16 AND 22  -- 실제 생성한 주간 데이터
),
previous_week AS (
    SELECT 
        COUNT(*) as impressions,
        COUNT(DISTINCT user_id) as unique_users,
        AVG(cost_per_impression) as avg_cpm
    FROM capa_ad_logs.impressions
    WHERE year = 2026 AND month = 2 
        AND day BETWEEN 9 AND 15  -- 이전주
)
SELECT 
    'This Week' as period,
    tw.impressions,
    tw.unique_users,
    tw.avg_cpm
FROM this_week tw
UNION ALL
SELECT 
    'Previous Week' as period,
    pw.impressions,
    pw.unique_users,
    pw.avg_cpm
FROM previous_week pw;
```

## 3. 특정 기간 상세 분석

### 3-1. 기간별 광고주 성과 순위
```sql
-- 2월 16-22일 광고주별 성과 TOP 10 (실제 데이터 기간)
SELECT 
    advertiser_id,
    COUNT(DISTINCT impression_id) as impressions,
    COUNT(DISTINCT user_id) as reach,
    SUM(cost_per_impression) as total_spend,
    AVG(cost_per_impression) as avg_cpm
FROM capa_ad_logs.impressions
WHERE year = 2026 AND month = 2 
    AND day BETWEEN 16 AND 22
GROUP BY advertiser_id
ORDER BY impressions DESC
LIMIT 10;
```

### 3-2. 피크 시간대 분석 (특정 기간)
```sql
-- 2월 16-22일 시간대별 평균 트래픽 (실제 데이터 기간)
SELECT 
    hour,
    AVG(hourly_impressions) as avg_impressions,
    MAX(hourly_impressions) as max_impressions,
    MIN(hourly_impressions) as min_impressions
FROM (
    SELECT 
        year, month, day, hour,
        COUNT(*) as hourly_impressions
    FROM capa_ad_logs.impressions
    WHERE year = 2026 AND month = 2 
        AND day BETWEEN 16 AND 22
    GROUP BY year, month, day, hour
) hourly_data
GROUP BY hour
ORDER BY hour;
```

### 3-3. 전환 퍼널 분석 (기간별)
```sql
-- 특정 기간의 전환 퍼널
WITH funnel_data AS (
    SELECT 
        i.year, i.month, i.day,
        COUNT(DISTINCT i.impression_id) as impressions,
        COUNT(DISTINCT c.click_id) as clicks,
        COUNT(DISTINCT cv.conversion_id) as conversions,
        COUNT(DISTINCT CASE WHEN cv.conversion_type = 'view_content' THEN cv.conversion_id END) as view_content,
        COUNT(DISTINCT CASE WHEN cv.conversion_type = 'add_to_cart' THEN cv.conversion_id END) as add_to_cart,
        COUNT(DISTINCT CASE WHEN cv.conversion_type = 'purchase' THEN cv.conversion_id END) as purchases
    FROM capa_ad_logs.impressions i
    LEFT JOIN capa_ad_logs.clicks c 
        ON i.impression_id = c.impression_id
    LEFT JOIN capa_ad_logs.conversions cv 
        ON c.click_id = cv.click_id
    WHERE i.year = 2026 AND i.month = 2
        AND i.day BETWEEN 16 AND 22
    GROUP BY i.year, i.month, i.day
)
SELECT 
    'Impressions' as stage, SUM(impressions) as count, 100.0 as percentage
FROM funnel_data
UNION ALL
SELECT 
    'Clicks' as stage, SUM(clicks) as count, 
    ROUND(SUM(clicks) * 100.0 / SUM(impressions), 2) as percentage
FROM funnel_data
UNION ALL
SELECT 
    'View Content' as stage, SUM(view_content) as count,
    ROUND(SUM(view_content) * 100.0 / SUM(impressions), 2) as percentage
FROM funnel_data
UNION ALL
SELECT 
    'Add to Cart' as stage, SUM(add_to_cart) as count,
    ROUND(SUM(add_to_cart) * 100.0 / SUM(impressions), 2) as percentage
FROM funnel_data
UNION ALL
SELECT 
    'Purchase' as stage, SUM(purchases) as count,
    ROUND(SUM(purchases) * 100.0 / SUM(impressions), 2) as percentage
FROM funnel_data;
```

## 4. 고급 기간 필터링

### 4-1. 최근 N일 데이터 (동적)
```sql
-- 최근 7일 데이터
WITH date_range AS (
    SELECT 
        YEAR(CURRENT_DATE - INTERVAL '7' DAY) as start_year,
        MONTH(CURRENT_DATE - INTERVAL '7' DAY) as start_month,
        DAY(CURRENT_DATE - INTERVAL '7' DAY) as start_day,
        YEAR(CURRENT_DATE) as end_year,
        MONTH(CURRENT_DATE) as end_month,
        DAY(CURRENT_DATE) as end_day
)
SELECT 
    i.*
FROM capa_ad_logs.impressions i
CROSS JOIN date_range dr
WHERE (i.year > dr.start_year OR 
       (i.year = dr.start_year AND i.month > dr.start_month) OR
       (i.year = dr.start_year AND i.month = dr.start_month AND i.day >= dr.start_day))
  AND (i.year < dr.end_year OR 
       (i.year = dr.end_year AND i.month < dr.end_month) OR
       (i.year = dr.end_year AND i.month = dr.end_month AND i.day <= dr.end_day))
LIMIT 1000;
```

### 4-2. 특정 요일만 조회
```sql
-- 최근 2주간 주말(토,일)만 조회
SELECT 
    year, month, day,
    DATE(CONCAT(CAST(year AS VARCHAR), '-', 
                LPAD(CAST(month AS VARCHAR), 2, '0'), '-', 
                LPAD(CAST(day AS VARCHAR), 2, '0'))) as date,
    COUNT(*) as impressions
FROM capa_ad_logs.impressions
WHERE year = 2026 AND month = 2
    AND day BETWEEN 16 AND 22
    AND DAY_OF_WEEK(DATE(CONCAT(CAST(year AS VARCHAR), '-', 
                                 LPAD(CAST(month AS VARCHAR), 2, '0'), '-', 
                                 LPAD(CAST(day AS VARCHAR), 2, '0')))) IN (6, 7)
GROUP BY year, month, day
ORDER BY year, month, day;
```

### 4-3. 월간 추이 분석
```sql
-- 2026년 1-2월 월간 비교
SELECT 
    year,
    month,
    COUNT(DISTINCT impression_id) as impressions,
    COUNT(DISTINCT user_id) as unique_users,
    COUNT(DISTINCT advertiser_id) as active_advertisers,
    SUM(cost_per_impression) as total_revenue,
    AVG(cost_per_impression) as avg_cpm
FROM capa_ad_logs.impressions
WHERE year = 2026 AND month IN (1, 2)
GROUP BY year, month
ORDER BY year, month;
```

## 5. 빠른 조회를 위한 팁

1. **항상 파티션 키 사용**: year, month, day, hour를 WHERE 절에 포함
2. **필요한 컬럼만 선택**: `SELECT *` 대신 필요한 컬럼만 지정
3. **LIMIT 사용**: 큰 데이터셋 조회 시 먼저 작은 샘플로 테스트
4. **날짜 계산 최적화**: 가능하면 파티션 키로 직접 필터링

## 예시: 실제 데이터 빠르게 확인
```sql
-- 2026년 2월 16-22일 전체 요약 통계
SELECT 
    COUNT(*) as total_impressions,
    COUNT(DISTINCT user_id) as unique_users,
    COUNT(DISTINCT ad_id) as unique_ads,
    MIN(timestamp) as first_impression,
    MAX(timestamp) as last_impression
FROM capa_ad_logs.impressions
WHERE year = 2026 AND month = 2 AND day BETWEEN 16 AND 22;
```

## 문제 해결: 데이터가 조회되지 않을 때
```sql
-- 1. 먼저 어떤 날짜의 데이터가 있는지 확인
SELECT DISTINCT year, month, day, COUNT(*) as records
FROM capa_ad_logs.impressions
WHERE year = 2026
GROUP BY year, month, day
ORDER BY year, month, day;

-- 2. 특정 파티션 경로의 파일 확인 (AWS CLI 사용)
-- aws s3 ls s3://capa-data-lake-827913617635/raw/impressions/year=2026/month=02/
```
# Redash 최근 기간 조회 쿼리 가이드

## 개요
이 가이드는 Redash에서 파티셔닝된 데이터를 대상으로 자주 사용되는 최근 기간을 조회하는 방법을 설명합니다. 특히 전일, 최근 일주일, 전월 등 비즈니스에서 자주 사용하는 기간을 효율적으로 조회하는 쿼리 템플릿을 제공합니다.

파티셔닝된 데이터(year/month/day)에서 날짜 계산을 통해 동적으로 기간을 설정하면, 사용자가 매번 날짜를 입력하지 않아도 자동으로 원하는 기간의 데이터를 조회할 수 있습니다.

## CURRENT_DATE 이해하기 (SQL 초보자용)

`CURRENT_DATE`는 **"오늘 날짜"**를 의미하는 SQL 명령어입니다. SQL을 처음 접하는 분들을 위해 쉽게 설명드리겠습니다.

### 일상 생활로 비유하면:
- 매일 일기를 쓸 때 "오늘은 2026년 3월 18일..."이라고 쓰는 것처럼
- SQL에서 `CURRENT_DATE`는 자동으로 오늘 날짜를 알려줍니다
- 즉, 쿼리를 실행할 때마다 그 날의 날짜를 자동으로 가져옵니다

### 왜 편리한가요?
```sql
-- ❌ 매번 날짜를 직접 써야 한다면...
WHERE date = '2026-03-18'  -- 내일이 되면 또 수정해야 함

-- ✅ CURRENT_DATE를 사용하면...
WHERE date = CURRENT_DATE  -- 언제 실행해도 "오늘" 날짜를 자동으로 사용
```

### 파티셔닝된 데이터와의 연결:
우리 데이터가 `year=YYYY/month=MM/day=DD/` 형태로 파티셔닝되어 있으므로:

```sql
-- "어제" 데이터를 보고 싶다면
DATE_ADD('day', -1, CURRENT_DATE)  -- 오늘에서 1일을 뺍니다

-- 실제 동작:
-- CURRENT_DATE가 오늘 날짜라면 → 그 전날이 됩니다
-- 그래서 year=YYYY/month=MM/day=(DD-1)/ 파티션을 찾아갑니다
```

### 실제 사용 예시:
```sql
-- 전일(어제) 데이터 조회
WITH yesterday_params AS (
    SELECT 
        -- CURRENT_DATE에서 1일을 빼면 어제가 됩니다
        YEAR(DATE_ADD('day', -1, CURRENT_DATE)) as year_val,     -- 어제의 연도
        MONTH(DATE_ADD('day', -1, CURRENT_DATE)) as month_val,   -- 어제의 월
        DAY(DATE_ADD('day', -1, CURRENT_DATE)) as day_val        -- 어제의 일
)
-- 이제 이 값들로 파티션을 찾아갑니다
WHERE year = year_val    -- 어제의 year 파티션
  AND month = month_val  -- 어제의 month 파티션
  AND day = day_val      -- 어제의 day 파티션
```

### 주요 장점:
1. **자동화**: 매일 쿼리를 수정할 필요가 없습니다
2. **실수 방지**: 날짜를 잘못 입력할 걱정이 없습니다
3. **스케줄링 최적**: Airflow 같은 도구로 자동 실행할 때 특히 유용합니다

간단히 말해서, **CURRENT_DATE = "오늘이 며칠이야?"를 SQL이 알아서 대답해주는 기능**입니다!

## 1. 전일 하루 조회
어제 하루 동안의 데이터만 조회하는 쿼리입니다. 일별 성과를 확인하거나 일일 리포트를 생성할 때 유용합니다.

### 쿼리 예시
```sql
-- 전일 하루 데이터 조회 (고정된 날짜 계산)
WITH yesterday_params AS (
    SELECT 
        CAST(YEAR(DATE_ADD('day', -1, CURRENT_DATE)) AS VARCHAR) as year_val,
        LPAD(CAST(MONTH(DATE_ADD('day', -1, CURRENT_DATE)) AS VARCHAR), 2, '0') as month_val,
        LPAD(CAST(DAY(DATE_ADD('day', -1, CURRENT_DATE)) AS VARCHAR), 2, '0') as day_val
)
SELECT 
    advertiser_id,
    campaign_id,
    SUM(impressions) as total_impressions,
    SUM(clicks) as total_clicks,
    ROUND(CAST(SUM(clicks) AS DOUBLE) / CAST(SUM(impressions) AS DOUBLE) * 100, 2) as ctr
FROM ad_hourly_summary
CROSS JOIN yesterday_params
WHERE year = year_val
  AND month = month_val
  AND day = day_val
GROUP BY advertiser_id, campaign_id
ORDER BY total_impressions DESC;
```

### 파라미터를 활용한 유연한 방식
```sql
-- 기준일을 파라미터로 받아 그 전일을 조회
WITH target_date AS (
    SELECT 
        CASE 
            WHEN '{{reference_date}}' = '' THEN CURRENT_DATE
            ELSE DATE('{{reference_date}}')
        END as ref_date
),
yesterday_params AS (
    SELECT 
        CAST(YEAR(DATE_ADD('day', -1, ref_date)) AS VARCHAR) as year_val,
        LPAD(CAST(MONTH(DATE_ADD('day', -1, ref_date)) AS VARCHAR), 2, '0') as month_val,
        LPAD(CAST(DAY(DATE_ADD('day', -1, ref_date)) AS VARCHAR), 2, '0') as day_val
    FROM target_date
)
SELECT 
    advertiser_id,
    campaign_id,
    year || '-' || month || '-' || day as date,
    SUM(impressions) as total_impressions,
    SUM(clicks) as total_clicks
FROM ad_hourly_summary
CROSS JOIN yesterday_params
WHERE year = year_val
  AND month = month_val
  AND day = day_val
GROUP BY advertiser_id, campaign_id, year, month, day;
```

**파라미터 설정**:
- `reference_date`: Type = Text, Title = "기준일 (YYYY-MM-DD)", Default Value = '' (빈 값이면 CURRENT_DATE 사용)

## 2. 전일까지의 최근 일주일 조회
어제를 포함한 최근 7일간의 데이터를 조회합니다. 주간 트렌드 분석이나 주간 리포트에 활용할 수 있습니다.

### 쿼리 예시
```sql
-- 전일 포함 최근 7일간 데이터 조회
WITH date_range AS (
    SELECT 
        DATE_ADD('day', -7, CURRENT_DATE) as start_date,
        DATE_ADD('day', -1, CURRENT_DATE) as end_date
),
date_params AS (
    SELECT 
        CAST(YEAR(start_date) AS VARCHAR) as start_year,
        LPAD(CAST(MONTH(start_date) AS VARCHAR), 2, '0') as start_month,
        LPAD(CAST(DAY(start_date) AS VARCHAR), 2, '0') as start_day,
        CAST(YEAR(end_date) AS VARCHAR) as end_year,
        LPAD(CAST(MONTH(end_date) AS VARCHAR), 2, '0') as end_month,
        LPAD(CAST(DAY(end_date) AS VARCHAR), 2, '0') as end_day,
        CAST(start_date AS VARCHAR) as start_date_str,
        CAST(end_date AS VARCHAR) as end_date_str
    FROM date_range
)
SELECT 
    year || '-' || month || '-' || day as date,
    advertiser_id,
    campaign_id,
    SUM(impressions) as daily_impressions,
    SUM(clicks) as daily_clicks,
    SUM(conversions) as daily_conversions
FROM ad_daily_summary
CROSS JOIN date_params
WHERE 
    -- 날짜를 문자열로 비교하여 범위 체크
    (year || '-' || month || '-' || day) >= start_date_str
    AND (year || '-' || month || '-' || day) <= end_date_str
GROUP BY year, month, day, advertiser_id, campaign_id
ORDER BY date DESC, daily_impressions DESC;
```

### 파티션 최적화 버전
```sql
-- 파티션을 고려한 최적화 쿼리 (같은 월 내에서만 조회)
WITH date_range AS (
    SELECT 
        DATE_ADD('day', -7, CURRENT_DATE) as start_date,
        DATE_ADD('day', -1, CURRENT_DATE) as end_date
),
date_params AS (
    SELECT 
        CAST(YEAR(end_date) AS VARCHAR) as year_val,
        LPAD(CAST(MONTH(end_date) AS VARCHAR), 2, '0') as month_val,
        LPAD(CAST(DAY(start_date) AS VARCHAR), 2, '0') as start_day,
        LPAD(CAST(DAY(end_date) AS VARCHAR), 2, '0') as end_day
    FROM date_range
    -- 시작일과 종료일이 같은 년월인 경우만 처리
    WHERE YEAR(start_date) = YEAR(end_date) 
      AND MONTH(start_date) = MONTH(end_date)
)
SELECT 
    year || '-' || month || '-' || day as date,
    SUM(impressions) as total_impressions,
    SUM(clicks) as total_clicks,
    SUM(conversions) as total_conversions,
    COUNT(DISTINCT advertiser_id) as active_advertisers
FROM ad_daily_summary
CROSS JOIN date_params
WHERE year = year_val
  AND month = month_val
  AND day BETWEEN start_day AND end_day
GROUP BY year, month, day
ORDER BY date DESC;
```

## 3. 전월 한달 조회
이전 달 전체의 데이터를 조회합니다. 월간 성과 분석이나 월간 리포트 생성에 사용됩니다.

### 쿼리 예시
```sql
-- 전월 전체 데이터 조회
WITH last_month_params AS (
    SELECT 
        CAST(YEAR(DATE_ADD('month', -1, DATE_TRUNC('month', CURRENT_DATE))) AS VARCHAR) as year_val,
        LPAD(CAST(MONTH(DATE_ADD('month', -1, DATE_TRUNC('month', CURRENT_DATE))) AS VARCHAR), 2, '0') as month_val
)
SELECT 
    advertiser_id,
    campaign_id,
    SUM(impressions) as monthly_impressions,
    SUM(clicks) as monthly_clicks,
    SUM(conversions) as monthly_conversions,
    ROUND(SUM(cost), 2) as monthly_cost,
    ROUND(CAST(SUM(clicks) AS DOUBLE) / NULLIF(CAST(SUM(impressions) AS DOUBLE), 0) * 100, 2) as avg_ctr,
    ROUND(CAST(SUM(conversions) AS DOUBLE) / NULLIF(CAST(SUM(clicks) AS DOUBLE), 0) * 100, 2) as avg_cvr,
    ROUND(SUM(cost) / NULLIF(SUM(conversions), 0), 2) as cpa
FROM ad_daily_summary
CROSS JOIN last_month_params
WHERE year = year_val
  AND month = month_val
GROUP BY advertiser_id, campaign_id
HAVING SUM(impressions) > 0
ORDER BY monthly_cost DESC;
```

### 일별 상세 포함 버전
```sql
-- 전월 일별 상세 데이터
WITH last_month_params AS (
    SELECT 
        CAST(YEAR(DATE_ADD('month', -1, DATE_TRUNC('month', CURRENT_DATE))) AS VARCHAR) as year_val,
        LPAD(CAST(MONTH(DATE_ADD('month', -1, DATE_TRUNC('month', CURRENT_DATE))) AS VARCHAR), 2, '0') as month_val,
        DATE_ADD('month', -1, DATE_TRUNC('month', CURRENT_DATE)) as month_start,
        DATE_ADD('day', -1, DATE_TRUNC('month', CURRENT_DATE)) as month_end
)
SELECT 
    year || '-' || month || '-' || day as date,
    CASE 
        WHEN DAYOFWEEK(DATE(year || '-' || month || '-' || day)) IN (1,7) THEN '주말'
        ELSE '평일'
    END as day_type,
    SUM(impressions) as daily_impressions,
    SUM(clicks) as daily_clicks,
    SUM(conversions) as daily_conversions,
    ROUND(SUM(cost), 2) as daily_cost,
    COUNT(DISTINCT advertiser_id) as active_advertisers,
    COUNT(DISTINCT campaign_id) as active_campaigns
FROM ad_daily_summary
CROSS JOIN last_month_params
WHERE year = year_val
  AND month = month_val
GROUP BY year, month, day
ORDER BY date;
```

## 4. 동적 기간 선택 쿼리
사용자가 원하는 기간 타입을 선택하면 자동으로 해당 기간의 데이터를 조회하는 통합 쿼리입니다.

```sql
-- 기간 타입 파라미터를 통한 동적 조회
WITH period_calc AS (
    SELECT 
        CASE '{{period_type}}'
            WHEN '전일' THEN DATE_ADD('day', -1, CURRENT_DATE)
            WHEN '최근7일' THEN DATE_ADD('day', -7, CURRENT_DATE)
            WHEN '전월' THEN DATE_ADD('month', -1, DATE_TRUNC('month', CURRENT_DATE))
            ELSE DATE_ADD('day', -1, CURRENT_DATE)
        END as start_date,
        CASE '{{period_type}}'
            WHEN '전일' THEN DATE_ADD('day', -1, CURRENT_DATE)
            WHEN '최근7일' THEN DATE_ADD('day', -1, CURRENT_DATE)
            WHEN '전월' THEN DATE_ADD('day', -1, DATE_TRUNC('month', CURRENT_DATE))
            ELSE DATE_ADD('day', -1, CURRENT_DATE)
        END as end_date
),
period_params AS (
    SELECT 
        CAST(start_date AS VARCHAR) as start_date_str,
        CAST(end_date AS VARCHAR) as end_date_str,
        '{{period_type}}' as period_name
    FROM period_calc
)
SELECT 
    period_name as 조회기간,
    advertiser_id,
    SUM(impressions) as total_impressions,
    SUM(clicks) as total_clicks,
    SUM(conversions) as total_conversions,
    ROUND(SUM(cost), 2) as total_cost,
    COUNT(DISTINCT year || '-' || month || '-' || day) as days_count
FROM ad_daily_summary
CROSS JOIN period_params
WHERE (year || '-' || month || '-' || day) >= start_date_str
  AND (year || '-' || month || '-' || day) <= end_date_str
GROUP BY period_name, advertiser_id
ORDER BY total_cost DESC;
```

**파라미터 설정**:
- `period_type`: Type = Dropdown List, Title = "조회 기간"
  - Options: ["전일", "최근7일", "전월"]
  - Default Value = "전일"

## 5. 성능 최적화 팁

### 파티션 활용 최대화
1. **단일 파티션 조회**: 가능하면 year, month를 고정하고 day만 범위 조회
2. **월 경계 처리**: 월을 넘어가는 기간은 UNION ALL로 분리 처리
3. **문자열 비교 주의**: 날짜를 문자열로 비교할 때는 형식 통일 (YYYY-MM-DD)

### 쿼리 최적화 예시
```sql
-- 월 경계를 넘는 최근 7일 조회 최적화
WITH date_range AS (
    SELECT 
        DATE_ADD('day', -7, CURRENT_DATE) as start_date,
        DATE_ADD('day', -1, CURRENT_DATE) as end_date
)
-- 이전 달 부분
SELECT * FROM (
    SELECT 
        year, month, day,
        SUM(impressions) as impressions,
        SUM(clicks) as clicks
    FROM ad_daily_summary
    WHERE year = CAST(YEAR(DATE_ADD('day', -7, CURRENT_DATE)) AS VARCHAR)
      AND month = LPAD(CAST(MONTH(DATE_ADD('day', -7, CURRENT_DATE)) AS VARCHAR), 2, '0')
      AND day >= LPAD(CAST(DAY(DATE_ADD('day', -7, CURRENT_DATE)) AS VARCHAR), 2, '0')
    GROUP BY year, month, day
)
UNION ALL
-- 현재 달 부분
SELECT * FROM (
    SELECT 
        year, month, day,
        SUM(impressions) as impressions,
        SUM(clicks) as clicks
    FROM ad_daily_summary
    WHERE year = CAST(YEAR(CURRENT_DATE) AS VARCHAR)
      AND month = LPAD(CAST(MONTH(CURRENT_DATE) AS VARCHAR), 2, '0')
      AND day <= LPAD(CAST(DAY(DATE_ADD('day', -1, CURRENT_DATE)) AS VARCHAR), 2, '0')
    GROUP BY year, month, day
)
ORDER BY year, month, day;
```

## 6. 사용 시 주의사항

### 타임존 고려
- Athena는 UTC 기준으로 동작하므로, 한국 시간 기준으로 조회하려면 조정 필요
- `AT TIME ZONE 'Asia/Seoul'` 사용 또는 9시간 추가

### 데이터 지연 고려
- 실시간 데이터가 아닌 경우, 전일 데이터가 없을 수 있음
- NULL 체크나 데이터 존재 여부 확인 로직 추가 권장

### 파라미터 기본값 설정
- 사용자 편의를 위해 적절한 기본값 설정
- 빈 값 처리 로직 포함

## 결론
이러한 최근 기간 조회 쿼리들을 활용하면 Redash 대시보드에서 자동으로 업데이트되는 리포트를 만들 수 있습니다. 파티셔닝된 데이터의 특성을 잘 활용하여 성능을 최적화하면서도 유연한 기간 조회가 가능합니다.

각 쿼리는 비즈니스 요구사항에 맞게 수정하여 사용하시면 됩니다. 특히 집계 함수나 그룹핑 기준은 실제 분석 목적에 따라 조정하세요.
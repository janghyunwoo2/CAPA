# Summary 테이블 Athena 쿼리 모음

> **중요**: 이 문서는 ETL을 통해 생성된 summary 테이블들에 대한 쿼리입니다.
> - `ad_combined_log`: 시간별 impression + click 조인 데이터
> - `ad_combined_log_summary`: 일별 집계 데이터 (CTR, CVR 포함)

## 0. Summary 테이블 데이터 확인

### 0-1. 사용 가능한 파티션 확인
```sql
-- ad_combined_log 파티션 확인 (시간별)
SHOW PARTITIONS capa_ad_logs.ad_combined_log;

-- ad_combined_log_summary 파티션 확인 (일별)
SHOW PARTITIONS capa_ad_logs.ad_combined_log_summary;
```

### 0-2. 최근 생성된 데이터 확인
```sql
-- 최근 24시간 시간별 데이터
SELECT dt, COUNT(*) as record_count
FROM capa_ad_logs.ad_combined_log
WHERE dt >= date_format(current_timestamp - interval '24' hour, '%Y-%m-%d-%H')
GROUP BY dt
ORDER BY dt DESC;

-- 최근 7일 일별 요약
SELECT dt, SUM(impressions) as total_impressions, SUM(clicks) as total_clicks
FROM capa_ad_logs.ad_combined_log_summary
WHERE dt >= date_format(current_date - interval '7' day, '%Y-%m-%d')
GROUP BY dt
ORDER BY dt DESC;
```

## 1. 시간별 상세 분석 (ad_combined_log)

### 1-1. 특정 시간대 클릭률 분석
```sql
-- 2026년 2월 24일 각 시간대별 CTR
SELECT 
    dt,
    COUNT(*) as impressions,
    SUM(CASE WHEN is_click THEN 1 ELSE 0 END) as clicks,
    ROUND(SUM(CASE WHEN is_click THEN 1 ELSE 0 END) * 100.0 / COUNT(*), 2) as ctr
FROM capa_ad_logs.ad_combined_log
WHERE dt LIKE '2026-02-24%'
GROUP BY dt
ORDER BY dt;
```

### 1-2. 플랫폼별 시간대 성과
```sql
-- 특정 날짜의 플랫폼별 시간대 트렌드
SELECT 
    SUBSTR(dt, 12, 2) as hour,
    platform,
    COUNT(*) as impressions,
    SUM(CASE WHEN is_click THEN 1 ELSE 0 END) as clicks,
    ROUND(AVG(CASE WHEN is_click THEN 1 ELSE 0 END) * 100, 2) as ctr
FROM capa_ad_logs.ad_combined_log
WHERE dt LIKE '2026-02-24%'
GROUP BY SUBSTR(dt, 12, 2), platform
ORDER BY hour, platform;
```
```sql
-- 하루 동안의 플랫폼별 CTR
SELECT 
    platform,
    COUNT(*) as impressions,
    SUM(CASE WHEN is_click THEN 1 ELSE 0 END) as clicks,
    ROUND(AVG(CASE WHEN is_click THEN 1 ELSE 0 END) * 100, 2) as ctr
FROM capa_ad_logs.ad_combined_log
WHERE dt LIKE '2026-02-16%'
GROUP BY platform
ORDER BY platform;
```
### 1-3. 클릭 반응 시간 분석
```sql
-- 노출 후 클릭까지 걸린 시간 분포
SELECT 
    CASE 
        WHEN (click_timestamp - timestamp) / 1000 < 10 THEN '0-10초'
        WHEN (click_timestamp - timestamp) / 1000 < 30 THEN '10-30초'
        WHEN (click_timestamp - timestamp) / 1000 < 60 THEN '30-60초'
        WHEN (click_timestamp - timestamp) / 1000 < 300 THEN '1-5분'
        ELSE '5분 이상'
    END as click_delay,
    COUNT(*) as click_count,
    ROUND(COUNT(*) * 100.0 / SUM(COUNT(*)) OVER(), 2) as percentage
FROM capa_ad_logs.ad_combined_log
WHERE dt = '2026-02-24-14'
    AND is_click = true
    AND click_timestamp IS NOT NULL
GROUP BY 1
ORDER BY 
    CASE click_delay
        WHEN '0-10초' THEN 1
        WHEN '10-30초' THEN 2
        WHEN '30-60초' THEN 3
        WHEN '1-5분' THEN 4
        ELSE 5
    END;
```

### 1-4. 실시간 모니터링 쿼리
```sql
-- 최근 1시간 5분 단위 트래픽
WITH time_buckets AS (
    SELECT 
        dt,
        FLOOR(timestamp / 300000) * 300000 as bucket_time,  -- 5분(300초) 단위
        COUNT(*) as impressions,
        SUM(CASE WHEN is_click THEN 1 ELSE 0 END) as clicks
    FROM capa_ad_logs.ad_combined_log
    WHERE dt = date_format(current_timestamp - interval '1' hour, '%Y-%m-%d-%H')
    GROUP BY dt, FLOOR(timestamp / 300000)
)
SELECT 
    dt,
    from_unixtime(bucket_time/1000) as time_bucket,
    impressions,
    clicks,
    ROUND(clicks * 100.0 / impressions, 2) as ctr
FROM time_buckets
ORDER BY bucket_time;
```

## 2. 일별 요약 분석 (ad_combined_log_summary)

### 2-1. 캠페인 성과 대시보드
```sql
-- 최근 7일 캠페인별 성과 추이
SELECT 
    campaign_id,
    dt,
    SUM(impressions) as impressions,
    SUM(clicks) as clicks,
    SUM(conversions) as conversions,
    ROUND(SUM(clicks) * 100.0 / SUM(impressions), 2) as ctr,
    ROUND(SUM(conversions) * 100.0 / SUM(clicks), 2) as cvr
FROM capa_ad_logs.ad_combined_log_summary
WHERE dt >= date_format(current_date - interval '7' day, '%Y-%m-%d')
GROUP BY campaign_id, dt
ORDER BY campaign_id, dt;
```

### 2-2. 광고주별 ROI 분석
```sql
-- 광고주별 주간 성과 및 효율성
WITH advertiser_performance AS (
    SELECT 
        advertiser_id,
        SUM(impressions) as total_impressions,
        SUM(clicks) as total_clicks,
        SUM(conversions) as total_conversions,
        AVG(ctr) as avg_ctr,
        AVG(cvr) as avg_cvr
    FROM capa_ad_logs.ad_combined_log_summary
    WHERE dt BETWEEN '2026-02-17' AND '2026-02-23'
    GROUP BY advertiser_id
)
SELECT 
    advertiser_id,
    total_impressions,
    total_clicks,
    total_conversions,
    ROUND(avg_ctr, 2) as avg_ctr,
    ROUND(avg_cvr, 2) as avg_cvr,
    ROUND(total_conversions * 1000.0 / total_impressions, 2) as conversions_per_1k_impressions
FROM advertiser_performance
WHERE total_impressions > 1000
ORDER BY total_conversions DESC
LIMIT 20;
```

### 2-3. 디바이스별 전환 퍼널
```sql
-- 디바이스 타입별 전환 퍼널 분석
SELECT 
    device_type,
    SUM(impressions) as impressions,
    SUM(clicks) as clicks,
    SUM(conversions) as conversions,
    ROUND(SUM(clicks) * 100.0 / SUM(impressions), 2) as impression_to_click,
    ROUND(SUM(conversions) * 100.0 / SUM(clicks), 2) as click_to_conversion,
    ROUND(SUM(conversions) * 100.0 / SUM(impressions), 4) as overall_conversion_rate
FROM capa_ad_logs.ad_combined_log_summary
WHERE dt BETWEEN '2026-02-01' AND '2026-02-23'
GROUP BY device_type
ORDER BY overall_conversion_rate DESC;
```

### 2-4. 일별 트렌드 비교
```sql
-- 주중 vs 주말 성과 비교
WITH daily_metrics AS (
    SELECT 
        dt,
        CASE 
            WHEN day_of_week(date(dt)) IN (1,7) THEN '주말'
            ELSE '주중'
        END as day_type,
        SUM(impressions) as impressions,
        SUM(clicks) as clicks,
        SUM(conversions) as conversions,
        AVG(ctr) as avg_ctr,
        AVG(cvr) as avg_cvr
    FROM capa_ad_logs.ad_combined_log_summary
    WHERE dt >= '2026-02-01'
    GROUP BY dt, 2
)
SELECT 
    day_type,
    COUNT(DISTINCT dt) as days,
    ROUND(AVG(impressions)) as avg_daily_impressions,
    ROUND(AVG(clicks)) as avg_daily_clicks,
    ROUND(AVG(conversions)) as avg_daily_conversions,
    ROUND(AVG(avg_ctr), 2) as avg_ctr,
    ROUND(AVG(avg_cvr), 2) as avg_cvr
FROM daily_metrics
GROUP BY day_type;
```

## 3. 시간별-일별 결합 분석

### 3-1. 시간대별 성과와 일별 요약 비교
```sql
-- 특정 날짜의 시간별 상세와 일별 요약 검증
WITH hourly_agg AS (
    SELECT 
        SUBSTR(dt, 1, 10) as date,
        COUNT(*) as hourly_impressions,
        SUM(CASE WHEN is_click THEN 1 ELSE 0 END) as hourly_clicks
    FROM capa_ad_logs.ad_combined_log
    WHERE dt LIKE '2026-02-23%'
    GROUP BY SUBSTR(dt, 1, 10)
),
daily_summary AS (
    SELECT 
        dt as date,
        SUM(impressions) as daily_impressions,
        SUM(clicks) as daily_clicks
    FROM capa_ad_logs.ad_combined_log_summary
    WHERE dt = '2026-02-23'
    GROUP BY dt
)
SELECT 
    h.date,
    h.hourly_impressions as hourly_total,
    d.daily_impressions as daily_total,
    h.hourly_impressions - d.daily_impressions as difference,
    ROUND((h.hourly_impressions - d.daily_impressions) * 100.0 / d.daily_impressions, 2) as diff_percentage
FROM hourly_agg h
JOIN daily_summary d ON h.date = d.date;
```

### 3-2. 피크 시간 광고 성과
```sql
-- 각 광고의 최고 성과 시간대 찾기
WITH hourly_performance AS (
    SELECT 
        ad_id,
        SUBSTR(dt, 12, 2) as hour,
        COUNT(*) as impressions,
        SUM(CASE WHEN is_click THEN 1 ELSE 0 END) as clicks,
        ROUND(SUM(CASE WHEN is_click THEN 1 ELSE 0 END) * 100.0 / COUNT(*), 2) as ctr
    FROM capa_ad_logs.ad_combined_log
    WHERE dt >= '2026-02-20-00' AND dt <= '2026-02-23-23'
    GROUP BY ad_id, SUBSTR(dt, 12, 2)
),
ranked_hours AS (
    SELECT 
        ad_id,
        hour,
        impressions,
        clicks,
        ctr,
        ROW_NUMBER() OVER (PARTITION BY ad_id ORDER BY ctr DESC, impressions DESC) as rank
    FROM hourly_performance
    WHERE impressions >= 100  -- 최소 노출 수 필터
)
SELECT 
    ad_id,
    hour as peak_hour,
    impressions,
    clicks,
    ctr
FROM ranked_hours
WHERE rank = 1
ORDER BY ctr DESC
LIMIT 50;
```

## 4. 고급 분석 쿼리

### 4-1. 이동 평균 CTR 추이
```sql
-- 7일 이동평균 CTR
WITH daily_metrics AS (
    SELECT 
        dt,
        SUM(impressions) as impressions,
        SUM(clicks) as clicks,
        ROUND(SUM(clicks) * 100.0 / SUM(impressions), 2) as daily_ctr
    FROM capa_ad_logs.ad_combined_log_summary
    WHERE dt >= date_format(current_date - interval '30' day, '%Y-%m-%d')
    GROUP BY dt
)
SELECT 
    dt,
    daily_ctr,
    ROUND(AVG(daily_ctr) OVER (
        ORDER BY dt 
        ROWS BETWEEN 6 PRECEDING AND CURRENT ROW
    ), 2) as ctr_7day_ma
FROM daily_metrics
ORDER BY dt;
```

### 4-2. 광고 조합 최적화
```sql
-- 가장 효과적인 광고-디바이스 조합 TOP 20
SELECT 
    ad_id,
    device_type,
    SUM(impressions) as total_impressions,
    SUM(clicks) as total_clicks,
    SUM(conversions) as total_conversions,
    ROUND(AVG(ctr), 2) as avg_ctr,
    ROUND(AVG(cvr), 2) as avg_cvr,
    ROUND(SUM(conversions) * 1000.0 / SUM(impressions), 2) as conversion_per_1k
FROM capa_ad_logs.ad_combined_log_summary
WHERE dt >= '2026-02-01'
GROUP BY ad_id, device_type
HAVING SUM(impressions) >= 1000
ORDER BY conversion_per_1k DESC
LIMIT 20;
```

### 4-3. 이상 탐지 쿼리
```sql
-- CTR 이상치 감지 (평균 대비 2배 이상/이하)
WITH ctr_stats AS (
    SELECT 
        AVG(ctr) as avg_ctr,
        STDDEV(ctr) as stddev_ctr
    FROM capa_ad_logs.ad_combined_log_summary
    WHERE dt >= date_format(current_date - interval '14' day, '%Y-%m-%d')
)
SELECT 
    s.dt,
    s.campaign_id,
    s.ad_id,
    s.impressions,
    s.clicks,
    s.ctr,
    cs.avg_ctr,
    ROUND(s.ctr - cs.avg_ctr, 2) as ctr_diff,
    CASE 
        WHEN s.ctr > cs.avg_ctr + 2 * cs.stddev_ctr THEN 'Unusually High'
        WHEN s.ctr < cs.avg_ctr - 2 * cs.stddev_ctr THEN 'Unusually Low'
        ELSE 'Normal'
    END as ctr_status
FROM capa_ad_logs.ad_combined_log_summary s
CROSS JOIN ctr_stats cs
WHERE s.dt = date_format(current_date - interval '1' day, '%Y-%m-%d')
    AND (s.ctr > cs.avg_ctr + 2 * cs.stddev_ctr 
         OR s.ctr < cs.avg_ctr - 2 * cs.stddev_ctr)
    AND s.impressions >= 100
ORDER BY ABS(s.ctr - cs.avg_ctr) DESC;
```

## 5. 리포트용 쿼리

### 5-1. 주간 리포트 요약
```sql
-- 지난주 전체 성과 요약
WITH week_summary AS (
    SELECT 
        date_trunc('week', date(dt)) as week_start,
        SUM(impressions) as total_impressions,
        SUM(clicks) as total_clicks,
        SUM(conversions) as total_conversions,
        COUNT(DISTINCT campaign_id) as active_campaigns,
        COUNT(DISTINCT ad_id) as active_ads
    FROM capa_ad_logs.ad_combined_log_summary
    WHERE dt BETWEEN date_format(current_date - interval '7' day, '%Y-%m-%d') 
        AND date_format(current_date - interval '1' day, '%Y-%m-%d')
    GROUP BY date_trunc('week', date(dt))
)
SELECT 
    date_format(week_start, '%Y-%m-%d') as week_starting,
    total_impressions,
    total_clicks,
    total_conversions,
    ROUND(total_clicks * 100.0 / total_impressions, 2) as overall_ctr,
    ROUND(total_conversions * 100.0 / total_clicks, 2) as overall_cvr,
    active_campaigns,
    active_ads
FROM week_summary;
```

### 5-2. 일별 성과 히트맵 데이터
```sql
-- 요일별-시간대별 CTR 히트맵용 데이터
SELECT 
    day_of_week(date(SUBSTR(dt, 1, 10))) as day_of_week,
    SUBSTR(dt, 12, 2) as hour,
    COUNT(*) as impressions,
    SUM(CASE WHEN is_click THEN 1 ELSE 0 END) as clicks,
    ROUND(AVG(CASE WHEN is_click THEN 1 ELSE 0 END) * 100, 2) as ctr
FROM capa_ad_logs.ad_combined_log
WHERE dt >= date_format(current_date - interval '14' day, '%Y-%m-%d-%H')
GROUP BY day_of_week(date(SUBSTR(dt, 1, 10))), SUBSTR(dt, 12, 2)
HAVING COUNT(*) >= 100
ORDER BY day_of_week, hour;
```

## 성능 최적화 팁

1. **파티션 활용**: 항상 dt 컬럼을 WHERE 절에 포함
2. **집계 테이블 우선**: 가능하면 ad_combined_log_summary 사용
3. **날짜 범위 제한**: 큰 기간 조회 시 단계적으로 확대
4. **필요 컬럼만 선택**: SELECT * 대신 필요한 컬럼만 지정

## 주의사항

- ad_combined_log는 시간별 파티션 (dt='YYYY-MM-DD-HH')
- ad_combined_log_summary는 일별 파티션 (dt='YYYY-MM-DD')
- timestamp는 milliseconds 단위
- CTR/CVR은 이미 계산된 백분율 값
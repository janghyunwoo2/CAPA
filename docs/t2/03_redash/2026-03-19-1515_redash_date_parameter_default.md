# Redash에서 날짜 파라미터 기본값 설정 방법

## 요청사항
- 기본값: CURRENT_DATE - 1 (전일 데이터 자동 조회)
- 파라미터: 사용자가 날짜를 수동으로 변경 가능

## AS-IS (현재 상태)
현재는 두 가지 방식의 쿼리를 별도로 작성해 사용 중:
1. **파라미터 방식**: 년/월/일을 수동으로 입력 필요
2. **CURRENT_DATE 방식**: 항상 어제 날짜로 고정, 변경 불가

## TO-BE (개선된 방식)
하나의 쿼리로 기본값(어제)과 파라미터 변경을 모두 지원

## 구현 방법

### 1. Redash 날짜 파라미터 활용
Redash의 Date 파라미터 타입을 사용하여 구현:

```sql
-- 날짜 파라미터를 사용한 통합 쿼리
WITH date_params AS (
    SELECT 
        -- Redash 파라미터로 받은 날짜를 파티션 형식으로 변환
        CAST(YEAR(DATE('{{ target_date }}')) AS VARCHAR) as year_val,
        LPAD(CAST(MONTH(DATE('{{ target_date }}')) AS VARCHAR), 2, '0') as month_val,
        LPAD(CAST(DAY(DATE('{{ target_date }}')) AS VARCHAR), 2, '0') as day_val,
        DATE('{{ target_date }}') as target_date
)
SELECT 
    COUNT(*) as total_impressions,
    SUM(CASE WHEN is_click THEN 1 ELSE 0 END) as total_clicks,
    SUM(cost_per_impression) + SUM(CASE WHEN is_click THEN cost_per_click ELSE 0 END) as total_cost,
    SUM(CASE WHEN is_conversion THEN conversion_value ELSE 0 END) as total_revenue,
    SUM(CASE WHEN is_conversion THEN 1 ELSE 0 END) as total_conversions
FROM ad_combined_log_summary
CROSS JOIN date_params
WHERE 
    year = year_val
    AND month = month_val
    AND day = day_val
```

### 2. Redash에서 파라미터 설정
1. 쿼리 편집 화면에서 `{{ target_date }}` 파라미터 생성
2. 파라미터 타입을 "Date"로 설정
3. 기본값 설정: "yesterday" 또는 동적 기본값 사용

### 3. 동적 기본값 설정 방법

#### 옵션 1: Redash 파라미터 설정에서 직접 설정
```
Parameter Name: target_date
Type: Date
Default value: yesterday
```

#### 옵션 2: 쿼리 내부에서 COALESCE로 처리
```sql
WITH date_params AS (
    SELECT 
        -- 파라미터가 없으면 어제 날짜 사용
        COALESCE(
            TRY(DATE('{{ target_date }}')), 
            DATE_ADD('day', -1, CURRENT_DATE)
        ) as effective_date
),
parsed_date AS (
    SELECT 
        effective_date,
        CAST(YEAR(effective_date) AS VARCHAR) as year_val,
        LPAD(CAST(MONTH(effective_date) AS VARCHAR), 2, '0') as month_val,
        LPAD(CAST(DAY(effective_date) AS VARCHAR), 2, '0') as day_val
    FROM date_params
)
-- 메인 쿼리
SELECT * FROM ad_combined_log_summary
CROSS JOIN parsed_date
WHERE 
    year = year_val
    AND month = month_val
    AND day = day_val
```

## 실제 활용 예시

### 일간 KPI 요약 (개선된 버전)
```sql
-- 전체 KPI 요약 - 기본값은 어제, 파라미터로 변경 가능
WITH date_params AS (
    SELECT 
        DATE('{{ target_date }}') as target_date,
        CAST(YEAR(DATE('{{ target_date }}')) AS VARCHAR) as year_val,
        LPAD(CAST(MONTH(DATE('{{ target_date }}')) AS VARCHAR), 2, '0') as month_val,
        LPAD(CAST(DAY(DATE('{{ target_date }}')) AS VARCHAR), 2, '0') as day_val
),
summary AS (
    SELECT 
        COUNT(*) as total_impressions,
        SUM(CASE WHEN is_click THEN 1 ELSE 0 END) as total_clicks,
        SUM(cost_per_impression) + SUM(CASE WHEN is_click THEN cost_per_click ELSE 0 END) as total_cost,
        SUM(CASE WHEN is_conversion THEN conversion_value ELSE 0 END) as total_revenue,
        SUM(CASE WHEN is_conversion THEN 1 ELSE 0 END) as total_conversions,
        COUNT(DISTINCT advertiser_id) as active_advertisers,
        COUNT(DISTINCT campaign_id) as active_campaigns,
        COUNT(DISTINCT ad_id) as active_ads
    FROM ad_combined_log_summary
    CROSS JOIN date_params
    WHERE 
        year = year_val
        AND month = month_val
        AND day = day_val
)
SELECT 
    target_date as "조회날짜",
    total_impressions as "총_노출수",
    total_clicks as "총_클릭수",
    total_cost as "총_광고비",
    total_revenue as "총_매출",
    total_conversions as "총_전환수",
    active_advertisers as "활성_광고주수",
    active_campaigns as "활성_캠페인수",
    active_ads as "활성_광고수",
    CASE WHEN total_impressions > 0 
         THEN ROUND(CAST(total_clicks AS DOUBLE) / total_impressions * 100, 2)
         ELSE 0 END as "전체_CTR",
    CASE WHEN total_clicks > 0 
         THEN ROUND(total_cost / total_clicks, 0)
         ELSE 0 END as "전체_CPC",
    CASE WHEN total_clicks > 0 
         THEN ROUND(CAST(total_conversions AS DOUBLE) / total_clicks * 100, 2)
         ELSE 0 END as "전체_CVR",
    CASE WHEN total_cost > 0 
         THEN ROUND(total_revenue / total_cost, 2)
         ELSE 0 END as "전체_ROAS"
FROM summary
CROSS JOIN date_params
```

### 시간별 트렌드 분석 (개선된 버전)
```sql
-- 시간별 노출수와 클릭수 추이 - 기본값은 어제, 파라미터로 변경 가능
WITH date_params AS (
    SELECT 
        DATE('{{ target_date }}') as target_date,
        CAST(YEAR(DATE('{{ target_date }}')) AS VARCHAR) as year_val,
        LPAD(CAST(MONTH(DATE('{{ target_date }}')) AS VARCHAR), 2, '0') as month_val,
        LPAD(CAST(DAY(DATE('{{ target_date }}')) AS VARCHAR), 2, '0') as day_val
)
SELECT 
    target_date as "조회날짜",
    hour as "시간",
    COUNT(*) as "노출수",
    SUM(CASE WHEN is_click THEN 1 ELSE 0 END) as "클릭수",
    SUM(cost_per_impression) + SUM(CASE WHEN is_click THEN cost_per_click ELSE 0 END) as "광고비",
    SUM(CASE WHEN is_click THEN 15000.0 ELSE 0 END) as "매출",
    COUNT(DISTINCT advertiser_id) as "활성_광고주수"
FROM ad_combined_log
CROSS JOIN date_params
WHERE 
    year = year_val
    AND month = month_val
    AND day = day_val
GROUP BY target_date, hour
ORDER BY hour
```

## 장점

### 1. 사용 편의성
- **자동화**: 매일 쿼리를 수정할 필요 없음
- **유연성**: 필요시 특정 날짜 조회 가능
- **대시보드 호환**: 자동 새로고침 시 어제 날짜로 자동 갱신

### 2. 유지보수
- **단일 쿼리**: 파라미터 방식과 자동 방식을 하나로 통합
- **코드 중복 제거**: 동일 로직의 쿼리 두 개를 관리할 필요 없음
- **확장성**: 날짜 범위 쿼리로 쉽게 확장 가능

### 3. 운영 효율성
- **보고서 자동화**: 매일 자동으로 전일 보고서 생성
- **수동 분석**: 특정 날짜 분석이 필요할 때 즉시 가능
- **알림 설정**: 특정 조건 충족 시 자동 알림 가능

## 추가 활용 팁

### 1. 날짜 범위 쿼리
```sql
-- 시작일과 종료일 파라미터 사용
WITH date_range AS (
    SELECT 
        DATE('{{ start_date }}') as start_date,
        DATE('{{ end_date }}') as end_date
)
SELECT * FROM ad_combined_log_summary
CROSS JOIN date_range
WHERE 
    DATE(CONCAT(year, '-', month, '-', day)) 
    BETWEEN start_date AND end_date
```

### 2. 상대적 날짜 계산
```sql
-- 최근 7일 데이터 조회
WITH date_range AS (
    SELECT 
        DATE_ADD('day', -7, CURRENT_DATE) as start_date,
        DATE_ADD('day', -1, CURRENT_DATE) as end_date
)
```

### 3. 월초/월말 자동 계산
```sql
-- 이번 달 1일부터 어제까지
WITH date_range AS (
    SELECT 
        DATE_TRUNC('month', CURRENT_DATE) as start_date,
        DATE_ADD('day', -1, CURRENT_DATE) as end_date
)
```

## 구현 시 주의사항

1. **타임존 고려**: Athena는 UTC 기준이므로 한국 시간 고려 필요
2. **파티션 최적화**: 날짜 파티션 조건은 항상 WHERE 절에 포함
3. **데이터 지연**: ETL 완료 시간을 고려하여 조회 시점 결정
4. **캐싱 설정**: 자주 조회되는 어제 데이터는 적절한 캐싱 설정

## 마이그레이션 가이드

### 기존 쿼리에서 전환하기
1. 기존 파라미터 방식 쿼리 복사
2. `{{ year }}`, `{{ month }}`, `{{ day }}` 파라미터를 `{{ target_date }}` 하나로 변경
3. date_params CTE 추가하여 날짜 파싱
4. Redash에서 target_date 파라미터 타입을 Date로 설정
5. 기본값을 "yesterday"로 설정
6. 테스트 후 기존 쿼리 비활성화

이러한 방식으로 구현하면 일일 보고서는 자동으로 전일 데이터를 조회하면서도, 필요시 특정 날짜를 선택하여 과거 데이터를 분석할 수 있습니다.
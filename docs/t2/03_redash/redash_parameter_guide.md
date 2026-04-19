# Redash 파티셔닝된 데이터 쿼리 파라미터 사용 매뉴얼

## 개요
안녕하세요! 이 매뉴얼은 Redash에서 year/month/day로 파티셔닝된 데이터를 다룰 때, 파라미터를 사용하여 쿼리를 동적으로 필터링하는 방법을 친절하고 자세하게 설명합니다. 파티셔닝된 데이터(예: S3에 저장된 Parquet 파일)를 효율적으로 조회하고 싶으신가요? 이 가이드를 따라하시면 쉽게 설정할 수 있습니다. 파라미터를 활용하면 특정 기간의 데이터만 빠르고 정확하게 가져올 수 있어요!

## 파라미터 추가 방법
Redash 쿼리 에디터에서 파티셔닝된 데이터를 대상으로 하는 쿼리를 작성 중이시라면, 파라미터를 추가해 보세요. 파라미터는 쿼리를 더 유연하게 만들어 줍니다. 아래 단계대로 따라 해 보세요:

1. **쿼리 에디터 열기**: Redash 대시보드에서 새로운 쿼리를 만들거나 기존 쿼리를 편집하세요.
2. **파라미터 추가**: 키보드 단축키 **Ctrl + P**를 누르거나, 에디터 하단의 **Add New Parameter** 버튼을 클릭하세요. 이렇게 하면 파라미터 설정 팝업이 나타납니다.
3. **파라미터 설정**:
   - **Name**: 파라미터의 고유한 이름을 입력하세요. 예를 들어, `year`, `month`, `start_day`, `end_day`처럼 직관적인 이름을 사용하면 좋습니다. 이 이름은 쿼리에서 사용할 거예요.
   - **Title**: 대시보드에 표시될 친근한 라벨을 설정하세요. 예: "년도", "월", "시작일", "종료일". 사용자가 쉽게 이해할 수 있도록 하세요.
   - **Type**: **Text**를 선택하세요. 텍스트 타입을 사용하면 파티션 키와 직접 매칭되어 더 효율적입니다.
   - **Default Value**: 기본값을 설정할 수 있어요. 예를 들어, 연도는 '2026', 월은 '03', 일은 '01' 형식으로 설정하세요. (선택사항이지만, 추천해요!)

이렇게 설정하면 쿼리가 더 사용자 친화적으로 변합니다. 파라미터를 추가한 후에는 쿼리를 저장하고 테스트해 보세요.

## 파티셔닝된 데이터에 파라미터 적용 예시
이제 실제 쿼리에 파라미터를 적용해 보겠습니다. 데이터가 year/month/day로 파티셔닝되어 있다면, Text 타입 파라미터를 WHERE 절에서 사용하여 데이터를 필터링할 수 있어요. 이렇게 하면 불필요한 데이터를 스캔하지 않아 성능이 좋아집니다.

### 1. 파라미터 설정 예시
먼저, 다음과 같이 파라미터를 만드세요:
- **year**: Type = Text, Title = "년도" (예: '2026')
- **month**: Type = Text, Title = "월" (예: '03')
- **start_day**: Type = Text, Title = "시작일" (예: '01')
- **end_day**: Type = Text, Title = "종료일" (예: '31')

### 2. 쿼리 작성 (Athena SQL 예시)
아래는 간단한 쿼리 예시입니다. 파라미터를 사용하여 year, month, day를 필터링하세요:

```sql
SELECT
    column1,
    column2,
    SUM(impressions) as total_impressions
FROM your_table
WHERE year = '{{year}}'
  AND month = '{{month}}'
  AND day BETWEEN '{{start_day}}' AND '{{end_day}}'
GROUP BY column1, column2
ORDER BY total_impressions DESC
```

**설명**:
- `{{year}}`는 텍스트로 입력된 연도 값을 그대로 사용합니다. 예: '2026'
- `{{month}}`는 두 자리 월 값을 사용합니다. 예: '03' (3월)
- `{{start_day}}`와 `{{end_day}}`는 조회할 일자 범위를 지정합니다. 예: '01'부터 '31'까지
- 파라미터를 작은따옴표로 감싸서 문자열로 비교하여 타입 불일치 오류를 방지하세요.
- 텍스트 타입을 사용하면 파티션 키와 정확히 일치하여 쿼리가 가장 효율적입니다!

### 3. 대시보드 적용
- 쿼리를 저장한 후, 대시보드에 이 쿼리를 추가하세요.
- 대시보드에서 파라미터 컨트롤(텍스트 입력 상자)이 자동으로 표시됩니다.
- 사용자가 값을 입력하면 쿼리가 자동으로 재실행되어 해당 파티션의 데이터만 조회합니다. 정말 편리하죠?

## 고급 사용법: 기간 조회를 위한 텍스트 파라미터
특정 기간의 데이터를 조회하고 싶으신가요? 텍스트 파라미터를 활용하면 여러 파티션을 효율적으로 조회할 수 있습니다.

### 설정 방법
- **year**: Type = Text, Title = "연도" (예: '2026')
- **month**: Type = Text, Title = "월" (예: '03')
- **start_day**: Type = Text, Title = "시작일" (예: '01')
- **end_day**: Type = Text, Title = "종료일" (예: '31')

### 쿼리 예시
```sql
-- 방법 1: 텍스트 파라미터로 직접 비교 (가장 효율적)
SELECT *
FROM your_table
WHERE year = '{{year}}'
  AND month = '{{month}}'
  AND day BETWEEN '{{start_day}}' AND '{{end_day}}'
  
-- 방법 2: 여러 파티션 조회 (기간이 긴 경우)
SELECT *
FROM your_table
WHERE (year = '{{year_start}}' 
       AND month = '{{month_start}}'
       AND day >= '{{day_start}}')
   OR (year = '{{year_end}}'
       AND month = '{{month_end}}'
       AND day <= '{{day_end}}')
   OR (CAST(year AS INTEGER) * 10000 + CAST(month AS INTEGER) * 100 + CAST(day AS INTEGER)
       BETWEEN CAST('{{year_start}}' AS INTEGER) * 10000 + CAST('{{month_start}}' AS INTEGER) * 100 + CAST('{{day_start}}' AS INTEGER)
       AND CAST('{{year_end}}' AS INTEGER) * 10000 + CAST('{{month_end}}' AS INTEGER) * 100 + CAST('{{day_end}}' AS INTEGER))
```

**설명**:
- **방법 1**: 같은 년/월 내에서 일자 범위를 조회할 때 가장 효율적입니다. 파티션 프루닝이 완벽하게 작동합니다.
- **방법 2**: 여러 달에 걸친 기간을 조회할 때는 별도의 시작/종료 파라미터를 사용합니다. 텍스트 타입을 사용하여 파티션 키와 직접 매칭이 되므로 필요한 파티션만 읽습니다.
- `CONCAT` 대신 파티션 키를 직접 비교하면 Athena가 불필요한 파티션을 건너뛸 수 있어 성능이 크게 향상됩니다!

### 실전 예시: 텍스트 파라미터를 활용한 사용자 정의 기간 조회
```sql
-- 파티셔닝된 광고 성과 데이터에서 사용자 정의 기간 조회
SELECT 
    advertiser_id,
    campaign_id,
    SUM(impressions) as total_impressions,
    SUM(clicks) as total_clicks
FROM ad_hourly_summary
WHERE year = '{{year}}'
  AND month = '{{month}}'
  AND day BETWEEN '{{start_day}}' AND '{{end_day}}'
GROUP BY advertiser_id, campaign_id
ORDER BY total_impressions DESC
```

**성능 비교**:
- ❌ CONCAT 방식: 모든 파티션 스캔 → 쿼리 시간 30초+
- ✅ 파티션 키 직접 사용: 7개 파티션만 스캔 → 쿼리 시간 2-3초

## 팁 및 주의사항
- **성능 최적화**: 파티셔닝된 데이터에서는 WHERE 절에 파라미터를 꼭 사용하세요. 파티션 키(year, month, day)를 정확히 필터링해야 불필요한 스캔을 방지할 수 있습니다. 예를 들어, year만 필터링하면 month와 day도 함께 지정하는 게 좋습니다.
- **파티션 프루닝 확인**: Athena 콘솔에서 쿼리 실행 후 "Data scanned" 지표를 확인하세요. 파티션이 제대로 적용되면 스캔된 데이터 양이 크게 줄어듭니다.
- **CONCAT 피하기**: `WHERE CONCAT(year, '-', month, '-', day) = '2023-03-15'` 같은 방식은 피하세요. 대신 `WHERE year='2023' AND month='03' AND day='15'`를 사용하세요.
- **테스트 필수**: 파라미터를 추가한 후 쿼리를 실행해 보세요. 파티션이 올바르게 적용되는지, 데이터가 제대로 나오는지 확인하세요. 작은 데이터로 먼저 테스트하는 걸 추천합니다.
- **문서화**: 쿼리 설명에 파라미터 사용법을 기록하세요. 나중에 다른 사람이 봐도 쉽게 이해할 수 있어요.
- **보안**: 파라미터를 사용할 때는 SQL 인젝션에 주의하세요. Redash는 기본적으로 안전하지만, 복잡한 쿼리에서는 검토하세요.
- **업데이트**: Redash 버전에 따라 기능이 다를 수 있으니, 최신 버전을 사용하세요.

## 문제 해결
Redash 파라미터 사용 중 문제가 생기셨나요? 아래를 참고하세요:

- **파라미터가 표시되지 않음**: 대시보드에서 쿼리를 새로고침해 보세요. 또는 브라우저 캐시를 지우고 다시 시도하세요.
- **값 형식**: 텍스트 파라미터는 입력한 값을 그대로 사용합니다. 예를 들어, 연도는 '2026', 월은 '03', 일은 '01' 형식으로 입력해야 합니다. 파티션 키와 일치하도록 형식을 통일하세요.
- **쿼리 실패**: 파라미터 값이 NULL이 아닌지 확인하세요. 기본값을 설정하면 도움이 됩니다. 또한, 파티션 키가 데이터와 일치하는지 검토하세요. Athena 콘솔에서 직접 쿼리를 테스트해 보세요.
- **성능 문제**: 범위 파라미터를 사용할 때 데이터가 너무 많으면 느려질 수 있어요. 필요하다면 파티션을 더 세분화하거나, 캐싱을 고려하세요.
- **더 많은 도움**: Redash 공식 문서나 커뮤니티를 확인하세요. 문제가 지속되면 로그를 확인해 보세요.

## 실제 사용 예시: capa_ad_logs 테이블 쿼리

CAPA 프로젝트의 `capa_ad_logs.ad_combined_log_summary` 테이블을 조회하는 예시입니다:

```sql
-- 텍스트 파라미터를 사용한 정확한 쿼리
SELECT
  *
FROM
  capa_ad_logs.ad_combined_log_summary
WHERE year = '{{year}}'
  AND month = '{{month}}'
  AND day BETWEEN '{{start_day}}' AND '{{end_day}}'
LIMIT 10;
```

**파라미터 설정**:
- `year`: Type = Text, Title = "년도", Default Value = '2026'
- `month`: Type = Text, Title = "월", Default Value = '03'
- `start_day`: Type = Text, Title = "시작일", Default Value = '01'
- `end_day`: Type = Text, Title = "종료일", Default Value = '31'

**주의사항**:
- YEAR(), MONTH(), DAY() 같은 날짜 함수를 텍스트 파라미터에 사용하면 타입 오류가 발생합니다
- 파티션 키는 문자열 타입이므로 텍스트 파라미터를 직접 사용하는 것이 가장 효율적입니다

이 매뉴얼을 따라 하시면 파티셔닝된 데이터의 효율적인 쿼리 대시보드를 쉽게 구축할 수 있습니다. 궁금한 점이 있으면 언제든 물어보세요! 😊
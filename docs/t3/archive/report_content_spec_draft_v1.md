# Report Generator - 리포트 콘텐츠 상세 스펙 (초안 v1)

**작성일**: 2026-03-09
**작성자**: Developer
**상태**: 초안 (Reviewer 검수 대기)

---

## 1. 리포트 개요

### 1.1 리포트 종류

| 항목 | 주간 리포트 | 월간 리포트 |
|---|---|---|
| **발송 주기** | 매주 월요일 08:00 KST | 매월 1일 08:00 KST |
| **대상 기간** | 지난주 월~일 (7일) | 지난달 1일~말일 |
| **비교 기준** | 전주 동기간 대비 | 전월 동기간 대비 |
| **발송 채널** | Slack + PDF 첨부 | Slack + PDF 첨부 |
| **주요 대상** | 팀장 (운영 최적화) | CEO (전략 수립) + 팀장 |
| **페이지 수** | 3~4페이지 | 4~5페이지 |

### 1.2 데이터 출처

- **테이블**: `capa_db.ad_events_raw` (Athena/Glue)
- **파티션**: year / month / day
- **주요 컬럼**: event_type, campaign_id, shop_id, user_id, device_type, bid_price, cpc_cost, total_amount, conversion_type, timestamp

---

## 2. 리포트 구성 (섹션별 상세)

### 섹션 1: 헤더

```
제목: "CAPA 광고 성과 리포트"
부제: "주간 리포트 (2026-03-02 ~ 2026-03-08)" 또는 "월간 리포트 (2026-02-01 ~ 2026-02-28)"
생성일시: "2026-03-09 08:00 KST"
```

---

### 섹션 2: Executive Summary (경영진 요약)

**목적**: CEO가 1분 안에 핵심을 파악할 수 있도록 간결한 요약 제공

**구성요소**:

#### 2-1. KPI 카드 (4개)

| KPI | 정의 | 단위 | SQL 계산식 |
|---|---|---|---|
| **총 매출** | 전환 이벤트의 total_amount 합계 | 만원 | `SUM(CASE WHEN event_type='conversion' THEN total_amount ELSE 0 END)` |
| **총 광고비** | 클릭 이벤트의 cpc_cost 합계 | 만원 | `SUM(CASE WHEN event_type='click' THEN cpc_cost ELSE 0 END)` |
| **CTR** | 클릭수 / 노출수 x 100 | % | `clicks / impressions * 100` |
| **ROAS** | 매출 / 광고비 x 100 | % | `total_revenue / total_cost * 100` |

각 KPI에 표시할 정보:
- 현재 기간 값
- 이전 기간 값 (전주 or 전월)
- 변화율 (%) = (현재 - 이전) / 이전 x 100
- 변화 방향 표시 (증가/감소/유지)

**예시 출력**:
```
총 매출: 5,230만원 (전주 대비 +8.2%)
총 광고비: 1,200만원 (전주 대비 +3.1%)
CTR: 7.25% (전주 대비 -0.15%p)
ROAS: 435.8% (전주 대비 +5.1%p)
```

#### 2-2. 핵심 하이라이트 (3개)

자동으로 추출하는 주요 변화 사항:
1. **가장 크게 성장한 카테고리**: "분식 카테고리 매출이 전주 대비 +15% 성장"
2. **가장 크게 하락한 카테고리**: "카페 카테고리 CTR이 전주 대비 -12% 하락"
3. **주목할 변화**: "전체 ROAS가 400% 이상을 유지하여 광고 효율 양호"

---

### 섹션 3: 주요 지표 상세

**목적**: 팀장이 전체 성과를 숫자로 파악

#### 3-1. 전체 성과 테이블

| 지표 | 이번 기간 | 이전 기간 | 변화 | 변화율 |
|---|---|---|---|---|
| 노출 (Impressions) | 1,250,000 | 1,180,000 | +70,000 | +5.9% |
| 클릭 (Clicks) | 90,625 | 85,260 | +5,365 | +6.3% |
| 전환 (Conversions) | 2,719 | 2,558 | +161 | +6.3% |
| 매출 (Revenue) | 5,230만원 | 4,830만원 | +400만원 | +8.2% |
| 광고비 (Cost) | 1,200만원 | 1,164만원 | +36만원 | +3.1% |
| CTR | 7.25% | 7.40% | -0.15%p | -2.0% |
| CVR | 3.00% | 3.00% | 0.00%p | 0.0% |
| CPC | 132원 | 137원 | -5원 | -3.6% |
| ROAS | 435.8% | 414.9% | +20.9%p | +5.0% |

**SQL (이번 기간)**:
```sql
SELECT
    COUNT(CASE WHEN event_type='impression' THEN 1 END) AS impressions,
    COUNT(CASE WHEN event_type='click' THEN 1 END) AS clicks,
    COUNT(CASE WHEN event_type='conversion' THEN 1 END) AS conversions,
    SUM(CASE WHEN event_type='conversion' THEN total_amount ELSE 0 END) AS revenue,
    SUM(CASE WHEN event_type='click' THEN cpc_cost ELSE 0 END) AS cost,
    ROUND(CAST(clicks AS DOUBLE) / NULLIF(impressions, 0) * 100, 2) AS ctr,
    ROUND(CAST(conversions AS DOUBLE) / NULLIF(clicks, 0) * 100, 2) AS cvr,
    ROUND(cost / NULLIF(clicks, 0), 0) AS cpc,
    ROUND(revenue / NULLIF(cost, 0) * 100, 1) AS roas
FROM capa_db.ad_events_raw
WHERE CAST(from_unixtime(timestamp/1000) AS date)
      BETWEEN CAST('{start_date}' AS date) AND CAST('{end_date}' AS date)
```

**비교 기간 SQL**: 동일 쿼리를 이전 기간(전주/전월)에 대해 실행

---

### 섹션 4: 일별 트렌드

**목적**: 팀장이 기간 내 성과 변동 패턴을 파악

#### 4-1. 일별 트렌드 차트

- **차트 유형**: 라인 차트 (matplotlib)
- **X축**: 날짜 (YYYY-MM-DD)
- **Y축 (좌)**: 매출 (만원)
- **Y축 (우)**: CTR (%)
- **라인 2개**: 매출 (파란색), CTR (주황색)

#### 4-2. 일별 데이터 테이블

| 날짜 | 노출 | 클릭 | 전환 | 매출 | CTR | ROAS |
|---|---|---|---|---|---|---|
| 2026-03-02 | 180,000 | 12,960 | 389 | 745만원 | 7.20% | 430% |
| 2026-03-03 | 175,000 | 12,775 | 383 | 730만원 | 7.30% | 425% |
| ... | ... | ... | ... | ... | ... | ... |

**SQL**:
```sql
SELECT
    CAST(from_unixtime(timestamp/1000) AS date) AS date,
    COUNT(CASE WHEN event_type='impression' THEN 1 END) AS impressions,
    COUNT(CASE WHEN event_type='click' THEN 1 END) AS clicks,
    COUNT(CASE WHEN event_type='conversion' THEN 1 END) AS conversions,
    SUM(CASE WHEN event_type='conversion' THEN total_amount ELSE 0 END) AS revenue,
    SUM(CASE WHEN event_type='click' THEN cpc_cost ELSE 0 END) AS cost,
    ROUND(CAST(clicks AS DOUBLE) / NULLIF(impressions, 0) * 100, 2) AS ctr,
    ROUND(revenue / NULLIF(cost, 0) * 100, 1) AS roas
FROM capa_db.ad_events_raw
WHERE CAST(from_unixtime(timestamp/1000) AS date)
      BETWEEN CAST('{start_date}' AS date) AND CAST('{end_date}' AS date)
GROUP BY CAST(from_unixtime(timestamp/1000) AS date)
ORDER BY date
```

---

### 섹션 5: 카테고리별 성과

**목적**: CEO는 카테고리 순위로 전략 판단, 팀장은 카테고리별 문제점 파악

#### 5-1. 카테고리별 성과 테이블

| 순위 | 카테고리 | 노출 | 클릭 | 전환 | 매출 | 광고비 | CTR | CVR | ROAS | 전기간 대비 매출 변화 |
|---|---|---|---|---|---|---|---|---|---|---|
| 1 | 분식 | 250,000 | 22,500 | 675 | 1,200만원 | 250만원 | 9.00% | 3.00% | 480% | +15% |
| 2 | 치킨 | 220,000 | 17,600 | 528 | 1,050만원 | 220만원 | 8.00% | 3.00% | 477% | +5% |
| 3 | 피자 | 200,000 | 14,000 | 420 | 850만원 | 180만원 | 7.00% | 3.00% | 472% | +3% |
| 4 | 한식 | 190,000 | 11,400 | 342 | 700만원 | 190만원 | 6.00% | 3.00% | 368% | -2% |
| 5 | 중식 | 180,000 | 10,800 | 324 | 650만원 | 185만원 | 6.00% | 3.00% | 351% | +1% |
| 6 | 카페 | 210,000 | 10,500 | 315 | 580만원 | 175만원 | 5.00% | 3.00% | 331% | -8% |

정렬: ROAS 내림차순

#### 5-2. 카테고리별 매출 비교 바 차트

- **차트 유형**: 가로 바 차트
- 이번 기간 vs 이전 기간 비교 (그룹화 바 차트)

**SQL**:
```sql
SELECT
    campaign_id,
    COUNT(CASE WHEN event_type='impression' THEN 1 END) AS impressions,
    COUNT(CASE WHEN event_type='click' THEN 1 END) AS clicks,
    COUNT(CASE WHEN event_type='conversion' THEN 1 END) AS conversions,
    SUM(CASE WHEN event_type='conversion' THEN total_amount ELSE 0 END) AS revenue,
    SUM(CASE WHEN event_type='click' THEN cpc_cost ELSE 0 END) AS cost,
    ROUND(CAST(clicks AS DOUBLE) / NULLIF(impressions, 0) * 100, 2) AS ctr,
    ROUND(CAST(conversions AS DOUBLE) / NULLIF(clicks, 0) * 100, 2) AS cvr,
    ROUND(revenue / NULLIF(cost, 0) * 100, 1) AS roas
FROM capa_db.ad_events_raw
WHERE CAST(from_unixtime(timestamp/1000) AS date)
      BETWEEN CAST('{start_date}' AS date) AND CAST('{end_date}' AS date)
GROUP BY campaign_id
ORDER BY roas DESC
```

---

### 섹션 6: 상점(Shop)별 성과

**목적**: 팀장이 성과 우수/부진 상점을 식별하여 관리

#### 6-1. Top 10 상점 (ROAS 기준)

| 순위 | Shop ID | 노출 | 클릭 | 전환 | 매출 | ROAS |
|---|---|---|---|---|---|---|
| 1 | shop_001 | 5,200 | 468 | 14 | 28만원 | 560% |
| 2 | shop_015 | 4,800 | 432 | 13 | 25만원 | 520% |
| ... | ... | ... | ... | ... | ... | ... |

#### 6-2. Bottom 10 상점 (ROAS 기준)

| 순위 | Shop ID | 노출 | 클릭 | 전환 | 매출 | ROAS |
|---|---|---|---|---|---|---|
| 1 | shop_042 | 3,100 | 155 | 2 | 3만원 | 120% |
| 2 | shop_038 | 2,800 | 140 | 1 | 2만원 | 95% |
| ... | ... | ... | ... | ... | ... | ... |

**SQL**:
```sql
SELECT
    shop_id,
    COUNT(CASE WHEN event_type='impression' THEN 1 END) AS impressions,
    COUNT(CASE WHEN event_type='click' THEN 1 END) AS clicks,
    COUNT(CASE WHEN event_type='conversion' THEN 1 END) AS conversions,
    SUM(CASE WHEN event_type='conversion' THEN total_amount ELSE 0 END) AS revenue,
    SUM(CASE WHEN event_type='click' THEN cpc_cost ELSE 0 END) AS cost,
    ROUND(revenue / NULLIF(cost, 0) * 100, 1) AS roas
FROM capa_db.ad_events_raw
WHERE CAST(from_unixtime(timestamp/1000) AS date)
      BETWEEN CAST('{start_date}' AS date) AND CAST('{end_date}' AS date)
GROUP BY shop_id
HAVING COUNT(CASE WHEN event_type='impression' THEN 1 END) >= 100
ORDER BY roas DESC
```

- Top 10: `LIMIT 10` (roas DESC)
- Bottom 10: `ORDER BY roas ASC LIMIT 10`
- 최소 노출 100 이상인 상점만 포함 (통계적 유의성)

---

### 섹션 7: 비용 분석 (월간 리포트 전용)

**목적**: CEO가 광고비 대비 수익성을 판단

#### 7-1. 비용 효율 요약

| 지표 | 이번 달 | 전월 | 변화율 |
|---|---|---|---|
| 총 광고비 | 5,200만원 | 4,800만원 | +8.3% |
| CPC (클릭당 비용) | 132원 | 137원 | -3.6% |
| CPM (천 노출당 비용) | 960원 | 990원 | -3.0% |
| ROAS | 435% | 415% | +4.8% |
| 순이익 (매출 - 광고비) | 1억 7,500만원 | 1억 5,100만원 | +15.9% |

#### 7-2. 일별 광고비 추이 차트

- **차트 유형**: 영역 차트 (Area chart)
- 일별 광고비와 매출을 동시에 표시

**SQL (CPM 계산 추가)**:
```sql
SELECT
    SUM(CASE WHEN event_type='click' THEN cpc_cost ELSE 0 END) AS total_cost,
    ROUND(total_cost / NULLIF(COUNT(CASE WHEN event_type='click' THEN 1 END), 0), 0) AS cpc,
    ROUND(total_cost / NULLIF(COUNT(CASE WHEN event_type='impression' THEN 1 END), 0) * 1000, 0) AS cpm,
    SUM(CASE WHEN event_type='conversion' THEN total_amount ELSE 0 END) AS revenue,
    ROUND(revenue / NULLIF(total_cost, 0) * 100, 1) AS roas,
    revenue - total_cost AS net_profit
FROM capa_db.ad_events_raw
WHERE CAST(from_unixtime(timestamp/1000) AS date)
      BETWEEN CAST('{start_date}' AS date) AND CAST('{end_date}' AS date)
```

---

### 섹션 8: 디바이스별 성과 (월간 리포트 전용)

**목적**: 팀장이 PC vs 모바일 광고 전략을 조정

#### 8-1. 디바이스별 성과 테이블

| 디바이스 | 노출 | 클릭 | 전환 | 매출 | CTR | ROAS |
|---|---|---|---|---|---|---|
| Mobile | 950,000 | 71,250 | 2,138 | 4,100만원 | 7.50% | 450% |
| PC | 300,000 | 19,375 | 581 | 1,130만원 | 6.46% | 390% |

**SQL**:
```sql
SELECT
    device_type,
    COUNT(CASE WHEN event_type='impression' THEN 1 END) AS impressions,
    COUNT(CASE WHEN event_type='click' THEN 1 END) AS clicks,
    COUNT(CASE WHEN event_type='conversion' THEN 1 END) AS conversions,
    SUM(CASE WHEN event_type='conversion' THEN total_amount ELSE 0 END) AS revenue,
    SUM(CASE WHEN event_type='click' THEN cpc_cost ELSE 0 END) AS cost,
    ROUND(CAST(clicks AS DOUBLE) / NULLIF(impressions, 0) * 100, 2) AS ctr,
    ROUND(revenue / NULLIF(cost, 0) * 100, 1) AS roas
FROM capa_db.ad_events_raw
WHERE CAST(from_unixtime(timestamp/1000) AS date)
      BETWEEN CAST('{start_date}' AS date) AND CAST('{end_date}' AS date)
GROUP BY device_type
```

---

### 섹션 9: 시간대별 트래픽 (월간 리포트 전용)

**목적**: 팀장이 피크 시간대를 파악하여 예산 배치 최적화

#### 9-1. 시간대별 노출/클릭 차트

- **차트 유형**: 바 차트 (X축: 시간대 0~23시, Y축: 노출수)
- 클릭은 라인으로 오버레이

**SQL**:
```sql
SELECT
    DATE_FORMAT(from_unixtime(timestamp/1000), '%H') AS hour,
    COUNT(CASE WHEN event_type='impression' THEN 1 END) AS impressions,
    COUNT(CASE WHEN event_type='click' THEN 1 END) AS clicks,
    ROUND(CAST(clicks AS DOUBLE) / NULLIF(impressions, 0) * 100, 2) AS ctr
FROM capa_db.ad_events_raw
WHERE CAST(from_unixtime(timestamp/1000) AS date)
      BETWEEN CAST('{start_date}' AS date) AND CAST('{end_date}' AS date)
GROUP BY DATE_FORMAT(from_unixtime(timestamp/1000), '%H')
ORDER BY hour
```

---

### 섹션 10: 전환 퍼널 분석 (월간 리포트 전용)

**목적**: 팀장이 전환 경로에서 이탈 구간을 파악

#### 10-1. 전환 퍼널 테이블

| 단계 | 건수 | 전환율 | 이탈율 |
|---|---|---|---|
| 노출 (Impression) | 1,250,000 | 100% | - |
| 클릭 (Click) | 90,625 | 7.25% (CTR) | 92.75% |
| 메뉴조회 (view_menu) | 1,496 | 1.65% | 98.35% |
| 장바구니 (add_to_cart) | 816 | 0.90% | 45.5% |
| 주문 (order) | 408 | 0.45% | 50.0% |

**SQL**:
```sql
SELECT
    COUNT(CASE WHEN event_type='impression' THEN 1 END) AS impressions,
    COUNT(CASE WHEN event_type='click' THEN 1 END) AS clicks,
    COUNT(CASE WHEN conversion_type='view_menu' THEN 1 END) AS view_menu,
    COUNT(CASE WHEN conversion_type='add_to_cart' THEN 1 END) AS add_to_cart,
    COUNT(CASE WHEN conversion_type='order' THEN 1 END) AS orders
FROM capa_db.ad_events_raw
WHERE CAST(from_unixtime(timestamp/1000) AS date)
      BETWEEN CAST('{start_date}' AS date) AND CAST('{end_date}' AS date)
```

---

## 3. 주간 vs 월간 리포트 비교

| 섹션 | 주간 리포트 | 월간 리포트 |
|---|---|---|
| 1. 헤더 | O | O |
| 2. Executive Summary (KPI 4개 + 하이라이트) | O | O |
| 3. 주요 지표 상세 (전기간 비교) | O | O |
| 4. 일별 트렌드 (차트 + 테이블) | O | O |
| 5. 카테고리별 성과 (테이블 + 차트) | O | O |
| 6. 상점별 성과 (Top/Bottom 10) | O | O |
| 7. 비용 분석 | - | O |
| 8. 디바이스별 성과 | - | O |
| 9. 시간대별 트래픽 | - | O |
| 10. 전환 퍼널 분석 | - | O |

---

## 4. 기존 코드 대비 변경사항 요약

### 4.1 athena_client.py 수정 필요

| 항목 | 현재 | 변경 |
|---|---|---|
| `query_kpi_summary()` | ROAS 없음 | ROAS 추가 (revenue, cost, roas 컬럼) |
| `query_shop_performance()` | `user_id` 기준 GROUP BY | `shop_id` 기준 GROUP BY |
| `query_daily_summary()` | revenue 없음, cost가 bid_price 합계 | revenue (total_amount), cost (cpc_cost) 분리 |
| `query_category_performance()` | ROAS 없음 | revenue, cost, cvr, roas 추가 |
| (신규) `query_kpi_comparison()` | 없음 | 이전 기간과 현재 기간 비교 쿼리 |
| (신규) `query_device_performance()` | 없음 | 디바이스별 성과 (월간 전용) |
| (신규) `query_hourly_traffic()` | 없음 | 시간대별 트래픽 (월간 전용) |
| (신규) `query_conversion_funnel()` | 없음 | 전환 퍼널 (월간 전용) |

### 4.2 report_writer.py 수정 필요

- 프롬프트를 주간/월간에 따라 다른 구조로 변경
- Claude LLM 인사이트 제거 -> 지표 중심 보고서로 전환
- (참고: `report_content_review_team.md`에서 "지표 중심, Claude AI 분석 제거"로 결정됨)

### 4.3 pdf_exporter.py 수정 필요

- 차트 추가: 카테고리 바 차트, 시간대별 차트
- 테이블 스타일 개선: 변화율에 색상 적용 (증가=초록, 감소=빨강)
- 페이지 구성: 섹션별 명확한 구분

### 4.4 bot.py 수정 필요

- 날짜 범위 파라미터 지원 ("주간", "월간", "7일", "30일")
- 자동 스케줄 실행 (Airflow DAG 연동 또는 내장 스케줄러)

---

## 5. 쿼리 실행 수

| 리포트 유형 | 쿼리 수 | 상세 |
|---|---|---|
| 주간 | 6개 | KPI(현재) + KPI(전주) + 일별 + 카테고리(현재) + 카테고리(전주) + 상점 |
| 월간 | 10개 | 위 6개 + 디바이스 + 시간대별 + 전환퍼널 + 비용(일별) |

---

## 6. 기술적 제약 및 고려사항

1. **Athena 비용**: 쿼리당 $0.005~0.01 (파티션 활용). 주간 6개 + 월간 10개 = 월 약 $0.30 추가
2. **PDF 페이지 수**: 주간 3~4페이지, 월간 4~5페이지 (가독성 우선)
3. **한글 폰트**: NanumGothic (Docker) / Malgun Gothic (Windows) 이미 지원
4. **차트 품질**: matplotlib 150dpi, 차트 크기 16cm x 6cm
5. **Claude LLM 인사이트 제거**: 지표 기반 자동 하이라이트 생성으로 대체 (비용 절감)

---

## 7. 지표 정의서

| 지표 | 약어 | 공식 | 의미 |
|---|---|---|---|
| 노출수 | Impressions | COUNT(event_type='impression') | 광고가 사용자에게 표시된 횟수 |
| 클릭수 | Clicks | COUNT(event_type='click') | 광고를 클릭한 횟수 |
| 전환수 | Conversions | COUNT(event_type='conversion') | 클릭 후 전환(주문 등) 발생 횟수 |
| 매출 | Revenue | SUM(total_amount) WHERE conversion | 전환에서 발생한 매출 합계 |
| 광고비 | Cost | SUM(cpc_cost) WHERE click | 클릭에서 발생한 비용 합계 |
| CTR | Click-Through Rate | Clicks / Impressions x 100 | 노출 대비 클릭 비율 |
| CVR | Conversion Rate | Conversions / Clicks x 100 | 클릭 대비 전환 비율 |
| CPC | Cost Per Click | Cost / Clicks | 클릭당 평균 비용 |
| CPM | Cost Per Mille | Cost / Impressions x 1000 | 천 노출당 비용 |
| ROAS | Return on Ad Spend | Revenue / Cost x 100 | 광고비 대비 매출 비율 |

---

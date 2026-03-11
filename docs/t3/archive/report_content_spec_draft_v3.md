# Report Generator - 리포트 콘텐츠 상세 스펙 (v3 최종) 

**작성일**: 2026-03-09
**작성자**: Developer
**상태**: v3 (Reviewer 최종 검수 대기)
**변경 이력**: v1 -> v2 (피드백 7건 + 추가 2건) -> v3 (CVR threshold 조정 + 이상 감지 통합 정리)

---

## 0. 리포트 공통 사항

### 0-1. 리포트 종류 및 대상

| 구분 | 주간 리포트 | 월간 리포트 |
|---|---|---|
| **발송 시점** | 매주 월요일 08:00 KST | 매월 1일 08:00 KST |
| **데이터 기간** | 직전 7일 (월~일) | 직전 1개월 |
| **비교 기간** | 전주 (7일) | 전월 |
| **주요 대상** | 마케팅팀장 | CEO + 마케팅팀장 |
| **부가 대상** | CEO (Executive Summary 1페이지만 확인) | - |
| **분량 목표** | 3~4페이지 (Executive Summary 1p + 상세 2~3p) | 5~6페이지 |
| **발송 채널** | Slack + PDF 첨부 | Slack + PDF 첨부 |

**CEO 수신 정책:**
- 주간 리포트: CEO도 Slack에서 수신하지만, **1페이지 Executive Summary만으로 충분**하도록 설계. 나머지 상세 섹션은 팀장 전용.
- 월간 리포트: CEO가 주도적으로 확인. 전체 섹션 대상.

### 0-2. 데이터 출처

- **테이블**: `capa_db.ad_events_raw` (Athena/Glue)
- **파티션**: year / month / day
- **주요 컬럼**: event_type, campaign_id, shop_id, user_id, device_type, bid_price, cpc_cost, total_amount, conversion_type, timestamp

### 0-3. 출력 형식

- PDF (ReportLab + matplotlib), Slack 채널 업로드
- A4 세로, 한글(나눔고딕/맑은고딕), 마크다운 -> PDF 변환

### 0-4. TIER 3 제외 항목

| TIER 3 항목 | 포함 여부 | 사유 |
|---|---|---|
| 비용 지표 (CPC, CPM, 광고비 총액) | 포함 (월간) | 섹션 7 |
| ROI / ROAS | 포함 (주간+월간) | 전 섹션에 반영 |
| 디바이스 타입별 | 포함 (월간) | 섹션 8 |
| 시간대별 트래픽 | 포함 (월간) | 섹션 9 |
| 지역별 성과 | **제외** | `ad_events_raw` 테이블에 지역(region) 컬럼 미존재. 데이터 수집 파이프라인에 지역 정보가 포함되지 않아 기술적으로 불가 |
| 캠페인별 성과 | **카테고리별 성과로 통합** | 현재 스키마에서 `campaign_id`가 카테고리(분식/치킨/피자 등)와 1:1 매핑. 별도 섹션 불필요, 섹션 5에서 처리 |
| 전환 퍼널 | 포함 (주간+월간) | 섹션 7(주간) / 섹션 10(월간) |

### 0-5. 리포트 전체 구조

**주간 리포트 (팀장 중심, CEO는 섹션 1~2만):**
```
1. 헤더 (리포트 제목 + 기간)
2. Executive Summary (KPI 카드+목표 달성율+하이라이트/경고)  <- CEO 여기까지
--- 이하 팀장 상세 ---
3. KPI 상세 & 전기 대비 변화 (순이익 포함)
4. 일별 트렌드 차트 (볼륨 + 효율)
5. 카테고리별 성과 (이상 감지 + 주간 추이)
6. 상점별 성과 (Top 10 / Bottom 10, 이상 감지)
7. 전환 퍼널 분석
8. 액션 아이템 (규칙 기반 자동 생성)
```

**월간 리포트 (CEO + 팀장):**
```
1. 헤더 (리포트 제목 + 기간)
2. Executive Summary (KPI 카드+목표 달성율+하이라이트/경고)
3. KPI 상세 & 전기 대비 변화 (순이익 포함)
4. 일별 트렌드 차트 (볼륨 + 효율)
5. 카테고리별 성과 (이상 감지)
6. 상점별 성과 (Top 10 / Bottom 10, 이상 감지)
7. 비용 효율성 분석 (CPC, CPM, ROAS 상세)
8. 디바이스별 성과 (PC vs 모바일)
9. 시간대별 트래픽 분포
10. 전환 퍼널 분석
11. 액션 아이템 (규칙 기반 자동 생성)
```

---

## 1. 헤더 섹션

**포함 내용:**
- 리포트 제목: "CAPA 광고 성과 주간 리포트" 또는 "CAPA 광고 성과 월간 리포트"
- 리포트 기간: "2026-03-02 ~ 2026-03-08"
- 비교 기간: "전주: 2026-02-23 ~ 2026-03-01"
- 생성 일시: "2026-03-09 08:00"

**근거:** TIER 1 - "리포트 기간" (CEO/팀장 모두 최고 중요도)

---

## 2. Executive Summary (경영진 요약)

**목적**: CEO가 이 1페이지만 보고도 의사결정 가능하도록 설계. 1페이지 내 완결.

### 2-1. 핵심 KPI 카드 (목표 달성율 포함)

4개의 KPI 카드를 한 행에 나란히 배치 (PDF 테이블 형태):

| KPI | 실적 | 목표 | 달성율 | 전기 대비 |
|---|---|---|---|---|
| 총 매출 | 15,234,000원 | 15,000,000원 | **101.6%** | +8.4% |
| 총 ROAS | 342.1% | 300% | **114.0%** | +15.2%p |
| 총 CTR | 7.10% | 7.0% | **101.4%** | +0.30%p |
| 총 전환 | 4,321건 | 4,000건 | **108.0%** | +5.7% |

**목표치 관리 방식:**
- `config.yaml` 파일에서 월간/주간 목표 설정
```yaml
targets:
  weekly:
    revenue: 15000000
    roas: 300
    ctr: 7.0
    conversions: 4000
  monthly:
    revenue: 60000000
    roas: 300
    ctr: 7.0
    conversions: 16000
```
- 목표 미설정 시 해당 행 생략 (달성율 컬럼 자체를 숨김)

**SQL (현재 기간)**:
```sql
SELECT
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
```

**비교 기간 SQL**: 동일 쿼리를 이전 기간(전주/전월)에 대해 실행

**근거:** TIER 1 - "주요 KPI 숫자", "핵심 비율", "전주/전월 대비 변화" + TIER 2 - "목표 대비 달성율"

### 2-2. 보조 KPI (한 줄)

| 노출 | 클릭 | 광고비 | 순이익 |
|---|---|---|---|
| 1,234,567회 (+12.3%) | 87,654회 (-2.1%) | 4,456,000원 (+6.1%) | **10,778,000원** (+9.8%) |

- 순이익 = 매출 - 광고비 (= SUM(total_amount) - SUM(cpc_cost))

---

## 3. KPI 상세 & 전기 대비 변화

**목적**: 팀장이 전체 성과를 숫자로 파악

| 지표 | 이번 기간 | 전기 | 변화 | 변화율(%) |
|---|---|---|---|---|
| 노출 (Impressions) | 1,234,567 | 1,100,000 | +134,567 | +12.3% |
| 클릭 (Clicks) | 87,654 | 89,521 | -1,867 | -2.1% |
| 전환 (Conversions) | 4,321 | 4,088 | +233 | +5.7% |
| 매출 (Revenue) | 15,234,000원 | 14,052,000원 | +1,182,000 | +8.4% |
| 광고비 (Cost) | 4,456,000원 | 4,200,000원 | +256,000 | +6.1% |
| **순이익 (Net Profit)** | **10,778,000원** | **9,852,000원** | **+926,000** | **+9.8%** |
| CTR (%) | 7.10 | 6.80 | - | +0.30%p |
| CVR (%) | 4.93 | 5.03 | - | -0.10%p |
| CPC (원) | 50.8 | 46.9 | - | +8.3% |
| ROAS (%) | 342.1 | 326.9 | - | +15.2%p |

**계산 공식:**
- CTR = clicks / impressions * 100
- CVR = conversions / clicks * 100
- CPC = SUM(cpc_cost) / clicks
- ROAS = SUM(total_amount) / SUM(cpc_cost) * 100
- 순이익 = SUM(total_amount) - SUM(cpc_cost)

**SQL**: 섹션 2-1과 동일 쿼리 재활용 (현재 기간 + 비교 기간)

**근거:** TIER 1 전체 + TIER 3 "비용 지표", "ROI/ROAS"

---

## 4. 일별 트렌드 차트

**목적**: CEO는 매출 트렌드, 팀장은 일별 이상치와 요일별 패턴 파악

### 차트 1: 볼륨 차트 (Volume)
- **차트 유형**: 라인 차트 (matplotlib)
- 라인 3개: 노출(Impressions), 클릭(Clicks), 전환(Conversions)
- Y축: 건수 (좌측)
- X축: 날짜 (MM-DD 형식, 요일 표기)
- 기존 `_create_trend_chart()` 유지/개선

### 차트 2: 효율 차트 (Efficiency)
- **차트 유형**: 이중 Y축 차트
- 좌측 Y축: 매출(원) - 막대 그래프
- 우측 Y축: ROAS(%) - 라인 그래프
- CTR(%) 라인 추가 (우측 Y축)

### 차트 하단 보조 테이블 (주간 리포트만):

| 날짜 | 요일 | 노출 | 클릭 | 전환 | 매출 | 광고비 | CTR | ROAS |
|---|---|---|---|---|---|---|---|---|
| 03-02 | 월 | 180,000 | 12,600 | 620 | 2,100K | 610K | 7.0% | 344% |
| 03-03 | 화 | 175,000 | 12,250 | 610 | 2,050K | 590K | 7.0% | 347% |
| ... | ... | ... | ... | ... | ... | ... | ... | ... |
| 03-08 | 일 | 165,000 | 11,550 | 580 | 1,900K | 570K | 7.0% | 333% |

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

**근거:** TIER 2 - "일별 트렌드 차트 (매출, 클릭)"

---

## 5. 카테고리별 성과

**목적**: CEO는 카테고리 순위로 전략 판단, 팀장은 카테고리별 문제점 파악

**참고:** campaign_id = 카테고리 (1:1 매핑). TIER 3 "캠페인별 성과"를 이 섹션에서 통합 처리.

- 정렬: 매출 내림차순
- 전체 카테고리 표시 (분식, 치킨, 피자, 한식, 중식, 카페 등)
- 마지막 행: "합계"

### 5-1. 카테고리별 성과 테이블

| 순위 | 카테고리 | 노출 | 클릭 | 전환 | 매출(원) | 광고비(원) | CTR | CVR | ROAS | 매출 변화 | 주간 추이 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | 치킨 | 280,000 | 22,400 | 1,120 | 4,500K | 1,200K | 8.0% | 5.0% | 375% | +8.2% | 월->화->수v목^금^토^일v |
| 2 | 분식 | 250,000 | 22,500 | 900 | 3,800K | 950K | 9.0% | 4.0% | 400% | **+15.2%** | 월->화^수^목->금^토^일v |
| 3 | 피자 | 200,000 | 14,000 | 700 | 3,200K | 800K | 7.0% | 5.0% | 400% | +3.1% | |
| 4 | 한식 | 180,000 | 10,800 | 540 | 2,000K | 600K | 6.0% | 5.0% | 333% | -1.5% | |
| 5 | 중식 | 170,000 | 10,200 | 510 | 1,800K | 550K | 6.0% | 5.0% | 327% | +2.0% | |
| 6 | 카페 | 154,567 | 7,754 | 551 | 934K | 356K | **5.0%** | 7.1% | 262% | -4.8% | |
| - | **합계** | **1,234,567** | **87,654** | **4,321** | **15,234K** | **4,456K** | **7.1%** | **4.9%** | **342%** | +8.4% | |

**"주간 추이" 컬럼 (주간 리포트에만 표시):**
- 요일별 매출 방향 표시: ^(상승) v(하락) ->(유지)
- 별도 캠페인별 성과 섹션 불필요 (카테고리 테이블에서 흡수)

### 5-2. 카테고리별 매출 비교 바 차트

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
ORDER BY revenue DESC
```

**근거:** TIER 2 - "카테고리별 성과 테이블 (순위, 수치)"

---

## 6. 상점(Shop)별 성과

**목적**: 팀장이 성과 우수/부진 상점을 식별하여 관리

### 6-1. Top 10 상점 (매출 기준)

| 순위 | 상점 ID | 카테고리 | 노출 | 클릭 | 전환 | 매출(원) | CTR | ROAS | 매출 변화 |
|---|---|---|---|---|---|---|---|---|---|
| 1 | shop_0042 | 치킨 | 15,200 | 1,216 | 61 | 245K | 8.0% | 380% | +5.2% |
| 2 | shop_0128 | 분식 | 14,800 | 1,332 | 53 | 230K | 9.0% | 410% | +12.3% |
| ... | ... | ... | ... | ... | ... | ... | ... | ... | ... |

### 6-2. Bottom 10 상점 (ROAS 기준, 최소 노출 100건 이상)

| 순위 | 상점 ID | 카테고리 | 노출 | 클릭 | 전환 | 매출(원) | CTR | ROAS | 상태 |
|---|---|---|---|---|---|---|---|---|---|
| 1 | shop_0891 | 카페 | 2,500 | 75 | 2 | 8K | 3.0% | **45%** | 손실 |
| 2 | shop_0732 | 중식 | 1,800 | 54 | 1 | 5K | 3.0% | **62%** | 손실 |
| ... | ... | ... | ... | ... | ... | ... | ... | ... | ... |

### 6-3. Bottom 10 추가 정보

- 전주 대비 ROAS 추이 (개선 중인지 악화 중인지)

**SQL**:
```sql
SELECT
    shop_id,
    campaign_id,
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
GROUP BY shop_id, campaign_id
HAVING COUNT(CASE WHEN event_type='impression' THEN 1 END) >= 100
ORDER BY roas DESC
```

- Top 10: `ORDER BY revenue DESC LIMIT 10`
- Bottom 10: `ORDER BY roas ASC LIMIT 10`
- **중요**: 기존 코드의 `user_id` -> `shop_id`로 버그 수정 반영

**근거:** TIER 2 - "상점별 성과 (Top 10 / Bottom 10)"

---

## 7. 비용 효율성 분석 (월간 리포트 전용)

**목적**: CEO가 광고비 대비 수익성을 판단

| 지표 | 이번 달 | 전월 | 변화율 |
|---|---|---|---|
| 총 광고비 | 18,500,000원 | 17,200,000원 | +7.6% |
| 총 매출 | 62,300,000원 | 58,100,000원 | +7.2% |
| 순이익 | 43,800,000원 | 40,900,000원 | +7.1% |
| CPC (클릭당 비용) | 52.3원 | 48.1원 | +8.7% |
| CPM (1,000 노출당 비용) | 3,720원 | 3,580원 | +3.9% |
| ROAS | 336.8% | 337.8% | -0.3%p |

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

**근거:** TIER 3 - "비용 지표 (CPC, CPM, 광고비 총액)", "ROI/ROAS"

---

## 8. 디바이스별 성과 (월간 리포트 전용)

**목적**: 팀장이 PC vs 모바일 광고 전략을 조정

| 디바이스 | 노출 | 클릭 | 전환 | 매출(원) | CTR | CVR | 노출 비중 |
|---|---|---|---|---|---|---|---|
| 모바일 | 4,120,000 | 301,760 | 15,088 | 52,500K | 7.3% | 5.0% | 84.0% |
| PC | 1,030,000 | 62,830 | 2,887 | 9,800K | 6.1% | 4.6% | 16.0% |

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
    ROUND(CAST(conversions AS DOUBLE) / NULLIF(clicks, 0) * 100, 2) AS cvr,
    ROUND(revenue / NULLIF(cost, 0) * 100, 1) AS roas
FROM capa_db.ad_events_raw
WHERE CAST(from_unixtime(timestamp/1000) AS date)
      BETWEEN CAST('{start_date}' AS date) AND CAST('{end_date}' AS date)
GROUP BY device_type
```

**근거:** TIER 3 - "디바이스 타입별 (PC vs 모바일)"

---

## 9. 시간대별 트래픽 분포 (월간 리포트 전용)

**목적**: 팀장이 피크 시간대를 파악하여 예산 배치 최적화

### 9-1. 시간대별 차트

- **차트 유형**: 막대 차트
- X축: 시간대 (00시~23시)
- Y축: 평균 노출수 (일평균)
- 피크 시간대 (11-13시, 17-20시) 색상 강조

### 9-2. 보조 테이블 (피크 시간대 Top 5만)

| 시간대 | 일평균 노출 | 일평균 클릭 | CTR | 전체 대비 비중 |
|---|---|---|---|---|
| 12:00-13:00 | 110,000 | 9,350 | 8.5% | 8.9% |
| 18:00-19:00 | 105,000 | 8,400 | 8.0% | 8.5% |
| 19:00-20:00 | 98,000 | 7,840 | 8.0% | 7.9% |
| 11:00-12:00 | 95,000 | 7,600 | 8.0% | 7.7% |
| 17:00-18:00 | 88,000 | 6,600 | 7.5% | 7.1% |

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

**근거:** TIER 3 - "시간대별 트래픽 (언제가 피크)"

---

## 10. 전환 퍼널 분석 (주간: 섹션 7 / 월간: 섹션 10)

**목적**: CEO는 전체 전환 효율 파악, 팀장은 이탈 구간 식별

### 10-1. 퍼널 시각화

```
노출 (Impression): 1,234,567건 ==================== 100%
    | CTR 7.10%
클릭 (Click):         87,654건 ===                   7.10%
    | 메뉴 조회율 55.0%
메뉴 조회:            48,210건 ==                    3.90%
    | 장바구니율 54.5%
장바구니:             26,296건 =                     2.13%
    | 주문율 16.4%
주문 (Order):          4,321건 |                     0.35%
```

### 10-2. 퍼널 테이블

| 단계 | 건수 | 전체 대비 | 이전 단계 전환율 | 전기 대비 변화 |
|---|---|---|---|---|
| 노출 (Impression) | 1,234,567 | 100.0% | - | +12.3% |
| 클릭 (Click) | 87,654 | 7.10% | 7.10% | -2.1% |
| 메뉴 조회 (view_menu) | 48,210 | 3.90% | 55.0% | +1.2% |
| 장바구니 (add_to_cart) | 26,296 | 2.13% | 54.5% | -0.5% |
| 주문 (order) | 4,321 | 0.35% | 16.4% | +5.7% |

**이상 감지:** 전기 대비 전환율 5%p 이상 하락한 단계: 빨간색 표시

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

**근거:** TIER 3 - "전환 퍼널 (impression -> click -> order)"

---

## 11. 주간 vs 월간 리포트 비교

| 섹션 | 주간 리포트 | 월간 리포트 |
|---|---|---|
| 1. 헤더 | O | O |
| 2. Executive Summary (KPI+목표+하이라이트/경고) | O | O |
| 3. KPI 상세 (순이익 포함) | O | O |
| 4. 일별 트렌드 (볼륨+효율 차트 2개) | O | O |
| 5. 카테고리별 성과 (이상 감지+주간 추이) | O (주간 추이 포함) | O |
| 6. 상점별 성과 (Top/Bottom 10, 이상 감지) | O | O |
| 7. 비용 효율성 분석 (CPC, CPM 상세) | - | O |
| 8. 디바이스별 성과 | - | O |
| 9. 시간대별 트래픽 | - | O |
| 10. 전환 퍼널 분석 | O (섹션 7 위치) | O |
| 11. 액션 아이템 (규칙 기반) | O (섹션 8 위치) | O |

---

## 13. 기존 코드 대비 변경사항 요약

### 13-1. athena_client.py 수정 필요

| 항목 | 현재 | 변경 |
|---|---|---|
| `query_kpi_summary()` | ROAS 없음 | revenue, cost, roas, net_profit 추가 |
| `query_shop_performance()` | `user_id` 기준 GROUP BY | **`shop_id` 기준 GROUP BY (버그 수정)** |
| `query_daily_summary()` | revenue 없음, cost가 bid_price 합계 | revenue (total_amount), cost (cpc_cost) 분리 |
| `query_category_performance()` | ROAS 없음 | revenue, cost, cvr, roas 추가 |
| (신규) `query_device_performance()` | 없음 | 디바이스별 성과 (월간 전용) |
| (신규) `query_hourly_traffic()` | 없음 | 시간대별 트래픽 (월간 전용) |
| (신규) `query_conversion_funnel()` | 없음 | 전환 퍼널 (주간+월간) |
| 비교 기간 로직 | 없음 | 모든 쿼리에 대해 전기(전주/전월) 재실행 |

### 13-2. 신규 파일

| 파일 | 용도 |
|---|---|
| `config.yaml` | 목표치 설정 |

### 13-3. 기존 파일 수정

| 파일 | 변경 내용 |
|---|---|
| `report_writer.py` | Claude LLM 프롬프트 삭제 -> 지표 기반 마크다운 직접 생성 |
| `pdf_exporter.py` | 차트 2개 추가 (효율 차트, 시간대별) |
| `bot.py` | 주간/월간 분기 로직, 날짜 범위 파라미터 지원 |

### 13-4. 쿼리 실행 수

| 리포트 유형 | 쿼리 수 | 상세 |
|---|---|---|
| 주간 | 7개 | KPI(현재+전주) + 일별 + 카테고리(현재+전주) + 상점(현재+전주) + 퍼널 |
| 월간 | 11개 | 위 7개 + 디바이스 + 시간대별 + 비용(현재+전월) |

---

## 14. 지표 정의서

| 지표 | 약어 | 공식 | 의미 |
|---|---|---|---|
| 노출수 | Impressions | COUNT(event_type='impression') | 광고가 사용자에게 표시된 횟수 |
| 클릭수 | Clicks | COUNT(event_type='click') | 광고를 클릭한 횟수 |
| 전환수 | Conversions | COUNT(event_type='conversion') | 클릭 후 전환(주문 등) 발생 횟수 |
| 매출 | Revenue | SUM(total_amount) WHERE conversion | 전환에서 발생한 매출 합계 |
| 광고비 | Cost | SUM(cpc_cost) WHERE click | 클릭에서 발생한 비용 합계 |
| 순이익 | Net Profit | Revenue - Cost | 매출에서 광고비를 뺀 순수익 |
| CTR | Click-Through Rate | Clicks / Impressions x 100 | 노출 대비 클릭 비율 |
| CVR | Conversion Rate | Conversions / Clicks x 100 | 클릭 대비 전환 비율 |
| CPC | Cost Per Click | Cost / Clicks | 클릭당 평균 비용 |
| CPM | Cost Per Mille | Cost / Impressions x 1000 | 천 노출당 비용 |
| ROAS | Return on Ad Spend | Revenue / Cost x 100 | 광고비 대비 매출 비율 |

---

## 15. 변경 이력

### v1 -> v2 변경 (피드백 9건)

| 피드백 # | 내용 | 반영 위치 |
|---|---|---|
| #1 | 목표 대비 달성율 추가 | 섹션 2-1 KPI 카드에 목표/달성율 컬럼 통합, config.yaml |
| #2 | CEO 주간 리포트 범위 명확화 | 섹션 0-1 리포트 종류 테이블, CEO는 섹션 1~2만 |
| #3 | 이상 감지/경고 표시 | 섹션 2-3 하이라이트&경고, 섹션 3/5/6/10 이상 감지 셀 색상 규칙 |
| #4 | 규칙 기반 액션 아이템 | 섹션 11 액션 아이템 (9개 규칙, config.yaml threshold, 출력 예시) |
| #5 | 지역별/캠페인별 누락 사유 | 섹션 0-4 TIER 3 제외 항목 테이블 |
| #6 | 일별 트렌드 차트 개선 | 섹션 4 차트 2개 분리 (볼륨+효율) |
| #7 | 주간에 순이익 추가 | 섹션 2-2 보조 KPI, 섹션 3 KPI 상세 테이블에 순이익 행 |
| #8 (추가) | 섹션 5/11 캠페인 중복 해소 | 섹션 5에 주간 추이 컬럼 추가, 캠페인별 성과 별도 섹션 삭제 |
| #9 (추가) | 목표 달성율 위치 조정 | 섹션 12 삭제, 섹션 2-1 Executive Summary에 통합 |

### v2 -> v3 변경

| 항목 | 변경 내용 | 반영 위치 |
|---|---|---|
| CVR threshold 조정 | CVR 하락 경고 기준: 10% -> 15% (Reviewer 요청) | 섹션 11-1 효율 관련 액션, 섹션 11-3 config.yaml |

### 피드백 반영 총괄 체크

| 필수 항목 | 상태 | 반영 위치 |
|---|---|---|
| 이상 감지/경고 표시 | 반영 완료 | 섹션 2-3 (성과 2+경고 2), 섹션 3 (셀 색상), 섹션 5-2 (셀 색상 4규칙), 섹션 6-3 (ROAS 태그), 섹션 10 (퍼널 이상 감지) |
| 규칙 기반 액션 아이템 | 반영 완료 | 섹션 11-1 (9개 규칙), 11-2 (출력 테이블), 11-3 (config.yaml), 11-4 (구현 방식) |

| 권장 항목 | 상태 | 반영 위치 |
|---|---|---|
| CEO 주간 수신 범위 | 반영 완료 | 섹션 0-1 테이블 + CEO 수신 정책 |
| 지역별 제외 사유 | 반영 완료 | 섹션 0-4 TIER 3 제외 항목 |
| 캠페인/카테고리 중복 해소 | 반영 완료 | 섹션 5 (campaign_id=카테고리 1:1, 주간 추이 흡수) |
| 목표 달성율 Executive Summary 통합 | 반영 완료 | 섹션 2-1 KPI 카드 |

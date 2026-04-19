# ChromaDB 시딩 업그레이드 작업 보고서

> **작업일**: 2026-03-22
> **작업자**: t1
> **대상 파일**: `services/vanna-api/scripts/seed_chromadb.py`
> **참조 설계 문서**: `docs/t1/text-to-sql/00_mvp_develop/02-design/05-sample-queries.md`

---

## 1. 작업 개요

### 1.1 문제 발견

`seed_chromadb.py`의 QA 예제가 테스트 시 한 테이블로만 쿼리가 생성되는 현상을 발견.
원인 분석 결과, QA 예제 10개 전부가 `ad_combined_log_summary`만 사용하는 **완전 편향 시딩**으로 확인됨.

| 테이블 | 수정 전 | 수정 후 |
|--------|:------:|:------:|
| `ad_combined_log` (hourly) | 0개 (0%) | 3개 (14%) |
| `ad_combined_log_summary` (daily) | 10개 (100%) | 18개 (86%) |
| **합계** | **10개** | **21개** |

### 1.2 작업 흐름

```
편향 발견
  → 1차 수정 (ad_combined_log 시간대 예제 + 지역/채널/월간 예제 추가)
  → GAP 분석 1차 (55%) — CPA/CPC 없음, 다양성 부족
  → 2차 수정 (CPA/CPC/3개월추이/주중-주말/주간채널 예제 추가)
  → GAP 분석 2차 (83%) — ROAS NULLIF 누락, 전환 0 예제 없음
  → 3차 수정 (ROAS NULLIF 수정, food_category CVR NULLIF 추가)
```

---

## 2. 변경 내용 상세

### 2.1 신규 추가된 QA 예제 (11개)

| # | 질문 | 사용 테이블 | 카테고리 | 추가 이유 |
|---|------|-----------|---------|---------|
| 11 | 오늘 시간대별 노출/클릭 분포, 피크타임 | `ad_combined_log` | C06 시간대 | hourly 테이블 편향 해소 |
| 12 | 어제 오후(14~18시) vs 저녁(19~23시) 클릭 비교 | `ad_combined_log` | C06 시간대 | 시간대 CASE WHEN 패턴 |
| 13 | 어제 기기별 시간대별 클릭 패턴 분석 | `ad_combined_log` | C06 시간대 | 다차원 시간대 분석 |
| 14 | 어제 서울 지역구별 노출수, CTR, 전환수 순위 | `ad_combined_log_summary` | C07 지역별 | delivery_region 차원 추가 |
| 15 | 이번 달 광고채널별(platform) 노출/클릭/전환율 | `ad_combined_log_summary` | C08 채널별 | platform 차원 (월간) |
| 16 | 지난달 대비 이번달 노출/클릭/전환 증감률 | `ad_combined_log_summary` | C09 기간비교 | CTE 월간 비교 패턴 |
| 17 | 광고주별 전환 1건당 광고비(CPA) | `ad_combined_log_summary` | C04 CPA | CPA 지표 예제 신규 |
| 18 | 광고 포맷별(ad_format) 클릭당 비용(CPC) | `ad_combined_log_summary` | C05 CPC | CPC 지표 예제 신규, month='01' 분산 |
| 19 | 지난 7일간 광고채널별(platform) CTR/CVR | `ad_combined_log_summary` | C08 채널별 | platform 차원 (주간, day BETWEEN) |
| 20 | 지난 3개월(1월/2월/3월) 월별 추이 | `ad_combined_log_summary` | C10 3개월 추이 | month IN 패턴 신규 |
| 21 | 이번 달 주중(월~금) vs 주말(토~일) 기기별 클릭 | `ad_combined_log_summary` | C11 주중/주말 | day_of_week() 함수 패턴 신규 |

### 2.2 기존 예제 버그 수정 (2건)

| 예제 | 수정 내용 | 사유 |
|------|---------|------|
| 예제 4 (ROAS) | 분모 `NULLIF(..., 0)` 추가 | `DOCUMENTATION_BUSINESS_METRICS` 규칙 위반 — 광고비 합계 0 시 Division by Zero 가능 |
| 예제 6 (food_category CVR) | 분모 `NULLIF(SUM(CAST(is_click AS INT)), 0)` 추가 | CVR 계산 규칙 일관성 (HAVING 병행 유지) |

---

## 3. 과적합 방지 설계

### 3.1 GROUP BY 차원 다양화

| 차원 | 사용 예제 수 |
|------|:----------:|
| campaign_id | 4개 |
| device_type | 2개 |
| platform | 2개 |
| food_category | 1개 |
| delivery_region | 1개 |
| advertiser_id | 1개 |
| ad_format | 1개 |
| hour | 2개 |
| day | 2개 |
| year, month | 1개 |
| week_type (주중/주말) | 1개 |

→ 11개 차원에 고르게 분산. campaign_id 집중도 최소화.

### 3.2 날짜 범위 분산

| month 값 | 사용 예제 |
|---------|---------|
| `'01'` | 예제 18 (CPC) |
| `'02'` | 예제 2 (광고비), 예제 16 (지난달) |
| `'03'` | 예제 1, 3, 4, 5, 6, 7, 8, 9, 11, 12, 13, 14, 15, 17, 19, 21 |
| `IN ('01','02','03')` | 예제 20 (3개월 추이) |
| day BETWEEN | 예제 3, 7, 10, 19 |

→ 3개 월에 걸쳐 분산. 특정 날짜 암기 방지.

### 3.3 SQL 패턴 다양화

| 패턴 | 예제 |
|------|------|
| GROUP BY + ORDER BY | 대다수 |
| CTE WITH ... AS | 예제 10, 16, 20 (비교형) |
| CASE WHEN (다차원 집계) | 예제 12, 21 |
| HAVING (조건부 필터) | 예제 4, 6, 7, 17 |
| day_of_week() 함수 | 예제 21 |
| month IN (...) 패턴 | 예제 20 |
| BETWEEN 날짜 범위 | 예제 3, 7, 10, 19 |
| DISTINCT | 예제 7 |

---

## 4. GAP 분석 결과

### 4.1 1차 분석 (수정 전)

| 항목 | 결과 |
|------|------|
| ad_combined_log 예제 | 0개 → **편향 확인** |
| 전체 Match Rate | **55%** ❌ |
| 주요 GAP | CPA/CPC 없음, 시간대 분석 없음, 지역/채널 없음 |

### 4.2 2차 분석 (수정 후)

| 카테고리 | 결과 |
|---------|:----:|
| C01 CTR | ✅ PASS |
| C02 CVR | ✅ PASS |
| C03 ROAS | ✅ PASS |
| C04 CPA | ✅ PASS |
| C05 CPC | ✅ PASS |
| C06 시간대별 (ad_combined_log) | ✅ PASS |
| C07 지역별 | ✅ PASS |
| C08 광고채널별 | ✅ PASS |
| C09 기간 비교 | ✅ PASS |
| C10 3개월 추이 | ✅ PASS |
| C11 주중/주말 | ✅ PASS |
| C12 전환 0 탐지 | ⚠️ 부분 (클릭 0만, 전환 0 미포함) |
| **카테고리 커버리지** | **12/12 (100%)** |
| **종합 Match Rate** | **83%** |

---

## 5. 잔여 GAP (백로그)

| GAP | 내용 | 우선순위 |
|-----|------|:------:|
| GAP-2 | "전환이 0인 캠페인" 예제 미존재 (현재는 "클릭 0" 예제만 있음) | Medium |
| REC-3 | 설계서 59개 질의 대비 QA 예제 21개(36%) — 추가 보완 가능 | Low |

---

## 6. 현재 QA 예제 전체 목록 (21개)

| # | 질문 요약 | 테이블 | 주요 지표 |
|---|---------|-------|---------|
| 1 | 어제 전체 CTR | summary | CTR |
| 2 | 지난달 캠페인별 광고비 | summary | ad_spend |
| 3 | 이번주 일별 클릭률 추이 | summary | CTR |
| 4 | ROAS 100% 이상 캠페인 | summary | ROAS |
| 5 | 기기별 클릭수 비교 | summary | CTR |
| 6 | food_category별 CVR TOP 5 | summary | CVR |
| 7 | 최근 7일 클릭 0인 캠페인 | summary | 이상 탐지 |
| 8 | 일별 CPI 최고 날짜 | summary | cost_per_impression |
| 9 | 캠페인별 일별 광고비 분포 | summary | ad_spend |
| 10 | 지난주 vs 이번주 노출수 증감 | summary | 성장률 |
| 11 | 오늘 시간대별 노출/클릭 분포 | **log** | CTR by hour |
| 12 | 오후 vs 저녁 클릭 비교 | **log** | CTR CASE WHEN |
| 13 | 기기별 시간대별 클릭 패턴 | **log** | clicks by device+hour |
| 14 | 서울 지역구별 노출/CTR/전환 | summary | CTR, conversions |
| 15 | 이번 달 채널별(platform) 성과 | summary | CTR, CVR |
| 16 | 지난달 대비 이번달 증감률 | summary | 성장률 3지표 |
| 17 | 광고주별 CPA | summary | CPA |
| 18 | 광고 포맷별 CPC | summary | CPC |
| 19 | 지난 7일 채널별 CTR/CVR | summary | CTR, CVR |
| 20 | 3개월 월별 추이 | summary | CTR, CVR |
| 21 | 주중 vs 주말 기기별 클릭 | summary | CTR by week_type |

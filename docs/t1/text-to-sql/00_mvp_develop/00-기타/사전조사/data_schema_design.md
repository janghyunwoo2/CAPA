# Text-to-SQL 데이터 스키마 설계

> **작성일**: 2026-03-06  
> **목적**: target_user_queries.md의 40개 질문을 100% 커버하기 위한 테이블 설계  
> **제약**: 노출/클릭/전환(판매) 3개 테이블은 반드시 유지

---

## 현재 구조의 한계

| 빠진 데이터 | 커버 불가 질문 |
|------------|--------------|
| 캠페인 상태/시작일/종료일/예산 | 활성 캠페인 필터, 신규/종료 캠페인, 예산 대비 소진율 |
| "매출"과 "광고비" 정의 | ROAS, CPA 계산 |
| A/B 테스트 그룹 | A/B 비교 (→ 범위 밖으로 제거) |
| 성별/연령/지역 | 성별·지역별 분석 |

---

## 제안 스키마: 3 + 2 구조

**원칙**: 이벤트 테이블 3개(불변) + 디멘션 테이블 2개(신규)

```
┌─────────────────────────────────────────────────────┐
│                  이벤트 테이블 (S3 원시 로그)            │
│                                                     │
│  impressions ──FK──▶ clicks ──FK──▶ conversions     │
│  (노출)              (클릭)         (전환/판매)       │
└─────────────────────────────────────────────────────┘
         │                                    │
         │ campaign_id                        │ user_id
         ▼                                    ▼
┌──────────────────┐              ┌──────────────────┐
│  campaigns       │              │  users           │
│  (캠페인 마스터)   │              │  (사용자 디멘션)   │
└──────────────────┘              └──────────────────┘
```

---

## 테이블 상세 설계

### 1. impressions (노출) — 유지 + 컬럼 보강

> S3 경로: `s3://capa-data-lake/raw/impressions/year/month/day/hour/`

| 컬럼 | 타입 | 설명 | 신규 여부 |
|------|------|------|----------|
| impression_id | STRING | 노출 고유 ID (PK) | 기존 |
| campaign_id | STRING | 캠페인 ID (FK → campaigns) | 기존 |
| ad_id | STRING | 광고 소재 ID | 기존 |
| user_id | STRING | 사용자 ID (FK → users) | 기존 |
| timestamp | TIMESTAMP | 노출 발생 시각 | 기존 |
| bid_price | DOUBLE | 입찰가 (원) = **광고비** | 기존 |
| device_type | STRING | mobile / desktop / tablet | 기존 |
| geo_country | STRING | 국가 코드 | 기존 |

**파티셔닝**: year / month / day / hour

---

### 2. clicks (클릭) — 유지

> S3 경로: `s3://capa-data-lake/raw/clicks/year/month/day/hour/`

| 컬럼 | 타입 | 설명 | 신규 여부 |
|------|------|------|----------|
| click_id | STRING | 클릭 고유 ID (PK) | 기존 |
| impression_id | STRING | 연결된 노출 ID (FK → impressions) | 기존 |
| user_id | STRING | 사용자 ID | 기존 |
| timestamp | TIMESTAMP | 클릭 발생 시각 | 기존 |
| cpc_cost | DOUBLE | CPC 비용 (원) | 기존 |

**파티셔닝**: year / month / day / hour

---

### 3. conversions (전환/판매) — 유지

> S3 경로: `s3://capa-data-lake/raw/conversions/year/month/day/hour/`

| 컬럼 | 타입 | 설명 | 신규 여부 |
|------|------|------|----------|
| event_id | STRING | 전환 고유 ID (PK) | 기존 |
| click_id | STRING | 연결된 클릭 ID (FK → clicks) | 기존 |
| user_id | STRING | 사용자 ID | 기존 |
| timestamp | TIMESTAMP | 전환 발생 시각 | 기존 |
| action_type | STRING | view_menu / add_to_cart / order | 기존 |
| total_amount | DOUBLE | 전환 매출 (원) = **매출** | 기존 |

**파티셔닝**: year / month / day / hour

---

### 4. campaigns (캠페인 마스터) — 🆕 신규

> S3 경로: `s3://capa-data-lake/master/campaigns/`  
> 업데이트 주기: 캠페인 생성/수정 시 (또는 일 1회 배치)

| 컬럼 | 타입 | 설명 |
|------|------|------|
| campaign_id | STRING | 캠페인 ID (PK) |
| campaign_name | STRING | 캠페인 이름 |
| advertiser_id | STRING | 광고주 ID |
| status | STRING | active / paused / ended |
| start_date | DATE | 캠페인 시작일 |
| end_date | DATE | 캠페인 종료일 |
| daily_budget | DOUBLE | 일일 예산 (원) |

**이 테이블로 해결되는 질문**:
- "클릭수 0인 **활성** 캠페인" → `WHERE status = 'active'`
- "bid_price 합계 vs **일일 예산**" → `daily_budget` 비교
- "**신규** 캠페인 첫 주 성과" → `start_date` 기준 필터
- "신규/종료 캠페인 수" → `start_date`, `end_date` 기준

---

### 5. users (사용자 디멘션) — 🆕 신규

> S3 경로: `s3://capa-data-lake/master/users/`  
> 업데이트 주기: 사용자 가입/수정 시 (또는 일 1회 배치)

| 컬럼 | 타입 | 설명 |
|------|------|------|
| user_id | STRING | 사용자 ID (PK) |
| gender | STRING | male / female / unknown |
| age_group | STRING | 10대 / 20대 / 30대 / 40대 / 50대+ |
| region | STRING | 서울 / 경기 / 부산 / 인천 / ... |

**이 테이블로 해결되는 질문 (신규 추가 가능)**:
- "**성별** 노출/클릭/전환 비율"
- "**지역별** 전환율 TOP 5"
- "**20대 여성** 타겟 캠페인 성과"
- "**서울** 지역 시간대별 클릭 추이"

---

## 비즈니스 용어 정의

위 스키마에서 용어 혼란을 방지하기 위한 정의:

| 용어 | 정의 | 계산식 |
|------|------|--------|
| **광고비 (Cost)** | 노출 시 발생하는 입찰 비용 | `SUM(impressions.bid_price)` |
| **CPC 비용** | 클릭 시 실제 과금 비용 | `SUM(clicks.cpc_cost)` |
| **매출 (Revenue)** | 전환(주문) 시 발생한 매출 | `SUM(conversions.total_amount)` |
| **CTR** | 클릭률 | `COUNT(clicks) / COUNT(impressions) × 100` |
| **CVR** | 전환률 | `COUNT(conversions) / COUNT(clicks) × 100` |
| **ROAS** | 광고 수익률 | `SUM(total_amount) / SUM(bid_price) × 100` |
| **CPA** | 전환당 비용 | `SUM(cpc_cost) / COUNT(conversions)` |
| **CPC** | 클릭당 비용 | `SUM(cpc_cost) / COUNT(clicks)` |

---

## 검증: 40개 질문 커버리지

| 구분 | 기존 (3테이블) | 제안 (3+2테이블) |
|------|:-------------:|:---------------:|
| AD Ops | 8/10 | **10/10** |
| PM / 기획자 | 8/10 | **10/10** |
| 세일즈 | 7/10 | **10/10** |
| 퍼포먼스 마케터 | 8/10 | **9/10** |
| **합계** | **31/40 (77.5%)** | **39/40 (97.5%)** |

> A/B 테스트 비교 1건만 커버 불가 → 이 질문은 **삭제하거나** "캠페인 간 성과 비교"로 변경하면 40/40 달성

---

## 성별/지역 추가 질문 예시 (users 테이블 활용)

### AD Ops 추가

| # | 질문 |
|---|------|
| 1 | "서울 지역 어제 시간대별 노출 분포" |
| 2 | "지역별 CTR 비교 (서울 vs 경기 vs 부산)" |

### 세일즈 추가

| # | 질문 |
|---|------|
| 1 | "20대 여성 타겟 캠페인 전환율 TOP 5" |
| 2 | "성별 광고 매출 비율" |

### 퍼포먼스 마케터 추가

| # | 질문 |
|---|------|
| 1 | "성별 × 디바이스별 ROAS 비교" |
| 2 | "지역별 전환 금액(total_amount) 순위" |
| 3 | "30대 남성의 시간대별 클릭 패턴" |
| 4 | "연령대별 CPA 비교" |

---

## JOIN 관계도

```
impressions ←─ impression_id ── clicks ←─ click_id ── conversions
     │                                                      │
     │ campaign_id                                          │ user_id
     ▼                                                      ▼
  campaigns                                               users
     │
     └─ advertiser_id (향후 advertisers 테이블 확장 가능)
```

**주요 JOIN 패턴**:

```sql
-- CTR 계산: impressions + clicks
SELECT i.campaign_id,
       COUNT(DISTINCT i.impression_id) AS impressions,
       COUNT(DISTINCT c.click_id) AS clicks,
       ROUND(COUNT(DISTINCT c.click_id) * 100.0 
             / COUNT(DISTINCT i.impression_id), 2) AS ctr
FROM impressions i
LEFT JOIN clicks c ON i.impression_id = c.impression_id
GROUP BY i.campaign_id;

-- ROAS 계산: impressions + clicks + conversions
SELECT i.campaign_id,
       SUM(i.bid_price) AS cost,
       SUM(cv.total_amount) AS revenue,
       ROUND(SUM(cv.total_amount) / SUM(i.bid_price) * 100, 2) AS roas
FROM impressions i
LEFT JOIN clicks c ON i.impression_id = c.impression_id
LEFT JOIN conversions cv ON c.click_id = cv.click_id
GROUP BY i.campaign_id;

-- 성별별 전환: users JOIN
SELECT u.gender,
       COUNT(cv.event_id) AS conversions,
       SUM(cv.total_amount) AS revenue
FROM conversions cv
JOIN users u ON cv.user_id = u.user_id
GROUP BY u.gender;
```

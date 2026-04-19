# [Design] RAG 시딩 품질 개선

## Executive Summary

| 항목 | 내용 |
|------|------|
| **Feature** | rag-seeding-quality |
| **참조 Plan** | `docs/t1/text-to-sql/10_rag-seeding-quality/01-plan/features/rag-seeding-quality.plan.md` |
| **작성일** | 2026-03-25 |
| **수정 대상 파일** | `services/vanna-api/scripts/seed_chromadb.py` (단일 파일) |

---

## 1. 현재 구조 분석

### 1.1 ChromaDB 컬렉션 매핑

```
seed_chromadb.py
├── train_ddl()           → Vanna train(ddl=...)          → ChromaDB: sql-ddl 컬렉션
├── train_documentation() → Vanna train(documentation=...) → ChromaDB: sql-documentation 컬렉션
└── train_qa_examples()   → Vanna train(question=..., sql=...) → ChromaDB: sql-qa 컬렉션
```

`train_documentation()`의 현재 `all_docs` 목록:

| 변수명 | 항목 수 | 현재 포맷 |
|--------|--------|----------|
| `DOCS_BUSINESS_METRICS` | 6 | 섹션형 (정의/의미/⚠️규칙) |
| `DOCS_ATHENA_RULES` | 4 | 섹션형 (금지/대체/예시) |
| `DOCS_POLICIES` | 9 | Key-Value 나열형 |
| `DOCS_NONEXISTENT_COLUMNS` | 1 | 불릿 리스트형 |
| `DOCS_CATEGORICAL_VALUES` | 1 | 대시 리스트형 |
| `DOCS_GLOSSARY` | 1 | Key:Value 형 |
| `DOCS_SCHEMA_MAPPER` | 3 | 섹션+불릿형 |
| `DOCS_NEGATIVE_EXAMPLES` | **0 (미존재)** | — |

### 1.2 발견된 추가 문제: QA 예제 CTR 불일치 (중요)

코드 전수 조사 결과, **QA_EXAMPLES(70개) 전체가 DOCS_BUSINESS_METRICS 규칙과 모순**됨:

```sql
-- QA_EXAMPLES 현재 (ROUND + *100 + _percent suffix)
ROUND(SUM(CAST(is_click AS INT)) * 100.0 / COUNT(*), 2) AS ctr_percent

-- DOCS_BUSINESS_METRICS 규칙 (0~1 비율, *100 금지)
COUNT(CASE WHEN is_click = true THEN 1 END) * 1.0 / NULLIF(COUNT(*), 0) AS ctr
```

**영향**: ChromaDB sql-qa 컬렉션에서 유사 질문을 검색할 때 `ctr_percent` 패턴의 SQL이 예제로 반환됨
→ LLM이 docs의 "금지" 규칙보다 실제 QA 예제를 우선 참조하여 `ctr_percent`를 생성

**설계 결정**: QA_EXAMPLES CTR/CVR 컬럼명도 함께 수정 (FR-RSQ-04로 추가)

---

## 2. 상세 설계

### 2.1 FR-RSQ-01: Documentation 문장형 변환

#### 변환 전/후 비교 예시

**DOCS_BUSINESS_METRICS — CTR 항목**

*AS-IS:*
```
CTR (Click-Through Rate) — 클릭률 (0~1 비율)
정의: (클릭 수) / (노출 수) → 결과는 0~1 비율로 반환
의미: 사용자가 광고를 본 후 클릭할 확률
⚠️ SQL 출력 규칙: * 1.0 비율(0~1) 그대로 반환. * 100 퍼센트 변환·ROUND·_percent suffix 절대 금지
올바른 Athena 계산식: COUNT(CASE WHEN is_click = true THEN 1 END) * 1.0 / NULLIF(COUNT(*), 0) AS ctr
잘못된 예(금지): ROUND(SUM(is_click)*100.0/COUNT(*), 2) AS ctr_percent
```

*TO-BE:*
```
CTR(클릭률)은 사용자가 광고를 본 후 실제로 클릭할 확률을 나타내는 지표로,
클릭 수를 노출 수로 나눈 값입니다. 결과값은 반드시 0에서 1 사이의 비율로 반환해야 하며,
100을 곱한 퍼센트 변환, ROUND 함수 적용, _percent suffix 사용은 절대 금지입니다.
올바른 Athena 계산식: COUNT(CASE WHEN is_click = true THEN 1 END) * 1.0 / NULLIF(COUNT(*), 0) AS ctr
잘못된 예(절대 금지): ROUND(SUM(CAST(is_click AS INT)) * 100.0 / COUNT(*), 2) AS ctr_percent
```

**DOCS_ATHENA_RULES — 파티션 조건 항목**

*AS-IS:*
```
Athena 파티션 조건 (필수 — 누락 시 풀스캔으로 비용 급증)
ad_combined_log 테이블: year, month, day, hour 파티션 필수
  단일 시점: WHERE year='2026' AND month='03' AND day='14' AND hour='09'
  ...
항상 파티션 컬럼(year/month/day)을 WHERE 절 맨 앞에 위치
```

*TO-BE:*
```
Athena에서 ad_combined_log 테이블을 조회할 때는 year, month, day, hour 파티션 조건이
반드시 WHERE 절에 포함되어야 합니다. 파티션 조건이 누락되면 전체 데이터를 스캔하므로
비용이 급증하고 쿼리 성능이 크게 저하됩니다.
단일 시점 예시: WHERE year='2026' AND month='03' AND day='14' AND hour='09'
파티션 컬럼(year, month, day)은 항상 WHERE 절의 가장 앞에 위치해야 합니다.
날짜 하드코딩은 금지이며, date_format(date_add('day', -1, current_date), '%d')와 같은
동적 날짜 표현을 반드시 사용해야 합니다.
```

**DOCS_POLICIES — device_type 코드값**

*AS-IS:*
```
device_type 코드값 정의
'mobile': 모바일 기기
'tablet': 태블릿 기기
'desktop': 데스크톱 컴퓨터
'others': 기타 기기
```

*TO-BE:*
```
device_type 컬럼은 광고가 노출된 기기 유형을 나타내며, 허용되는 값은
'mobile'(모바일 기기), 'tablet'(태블릿 기기), 'desktop'(데스크톱 컴퓨터),
'others'(기타 기기) 네 가지입니다. WHERE 조건에 기기 유형을 지정할 때는
반드시 이 소문자 값을 정확히 사용해야 하며, 'Mobile'처럼 대문자를 사용하면
쿼리 결과가 반환되지 않습니다.
```

#### 변환 대상 전체 목록

| 변수명 | 항목 수 | 주요 변환 포인트 |
|--------|--------|----------------|
| `DOCS_BUSINESS_METRICS` | 6 | CTR/CVR/ROAS/CPA/CPC 각 지표를 주어+서술어로 |
| `DOCS_ATHENA_RULES` | 4 | 파티션/날짜함수/타입/제한사항 의무형 문장 |
| `DOCS_POLICIES` | 9 | 코드값 정의를 "허용값은 ~입니다" 문장형 |
| `DOCS_NONEXISTENT_COLUMNS` | 1 | "~컬럼은 존재하지 않아 오류가 발생합니다" |
| `DOCS_CATEGORICAL_VALUES` | 1 | "~컬럼의 허용값은 ~이며, 이외의 값은 쿼리 오류를 유발합니다" |
| `DOCS_GLOSSARY` | 1 | "~은(는) ~을 의미합니다" 정의 문장형 |
| `DOCS_SCHEMA_MAPPER` | 3 | "~키워드가 질문에 포함되면 반드시 ~ 테이블을 사용해야 합니다" |

---

### 2.2 FR-RSQ-02: DDL 컬럼별 인라인 주석 추가

#### ad_combined_log 컬럼 주석 설계

```sql
CREATE EXTERNAL TABLE ad_combined_log (
    -- Impression 관련 컬럼
    impression_id STRING,            -- 노출 이벤트 고유 ID (UUID 형식)
    user_id STRING,                   -- 광고를 본 사용자 ID (user_000001~user_100000)
    ad_id STRING,                     -- 광고 소재 ID (ad_0001~ad_1000)
    campaign_id STRING,               -- 캠페인 ID (campaign_01~campaign_05)
    advertiser_id STRING,             -- 광고주 ID (advertiser_01~advertiser_30)
    platform STRING,                  -- 노출 플랫폼 (web|app_ios|app_android|tablet_ios|tablet_android)
    device_type STRING,               -- 기기 유형 (mobile|tablet|desktop|others)
    os STRING,                        -- 운영체제 (ios|android|macos|windows)
    delivery_region STRING,           -- 배달 지역 (강남구|서초구 등 서울 25개 자치구)
    user_lat DOUBLE,                  -- 사용자 위도 (서울 범위: 37.4~37.7)
    user_long DOUBLE,                 -- 사용자 경도 (서울 범위: 126.8~127.1)
    store_id STRING,                  -- 매장 ID (store_0001~store_5000)
    food_category STRING,             -- 음식 카테고리 (chicken|pizza|korean|chinese|dessert 외 10개)
    ad_position STRING,               -- 광고 위치 (home_top_rolling|list_top_fixed|search_ai_recommend|checkout_bottom)
    ad_format STRING,                 -- 광고 포맷 (display|native|video|discount_coupon)
    user_agent STRING,                -- 브라우저/앱 User-Agent 문자열
    ip_address STRING,                -- 사용자 IP 주소
    session_id STRING,                -- 세션 ID
    keyword STRING,                   -- 검색 키워드 (검색 연동 광고용)
    cost_per_impression DOUBLE,       -- 노출 1회당 광고비 (0.005~0.10)
    impression_timestamp BIGINT,      -- 노출 발생 시각 (Unix timestamp, from_unixtime()로 변환)

    -- Click 관련 컬럼
    click_id STRING,                  -- 클릭 이벤트 ID (클릭 미발생 시 NULL)
    click_position_x INT,             -- 클릭 X 좌표 (픽셀)
    click_position_y INT,             -- 클릭 Y 좌표 (픽셀)
    landing_page_url STRING,          -- 클릭 후 이동한 랜딩 페이지 URL
    cost_per_click DOUBLE,            -- 클릭 1회당 광고비 (0.1~5.0)
    click_timestamp BIGINT,           -- 클릭 발생 시각 (Unix timestamp)

    -- Flag
    is_click BOOLEAN,                 -- 클릭 발생 여부 (true=클릭, false=노출만, CTR/CVR 계산에 필수)

    -- Partition 컬럼 (반드시 WHERE 조건에 포함)
    year STRING,                      -- 파티션: 연도 (예: '2026') — WHERE 절 누락 시 풀스캔
    month STRING,                     -- 파티션: 월 (예: '03') — WHERE 절 누락 시 풀스캔
    day STRING,                       -- 파티션: 일 (예: '25') — WHERE 절 누락 시 풀스캔
    hour STRING                       -- 파티션: 시간 (예: '09') — ad_combined_log 전용, 시간대별 분석 필수
)
```

#### ad_combined_log_summary 추가 컬럼 주석 설계

```sql
    -- Conversion 관련 컬럼 (이 컬럼들은 ad_combined_log에 없음, summary 전용)
    conversion_id STRING,             -- 전환 이벤트 ID (전환 미발생 시 NULL)
    conversion_type STRING,           -- 전환 유형 (purchase|signup|download|view_content|add_to_cart)
    conversion_value DOUBLE,          -- 전환 매출액 (1.0~10000.0, ROAS 계산에 사용)
    product_id STRING,                -- 전환 상품 ID (prod_00001~prod_10000)
    quantity INT,                     -- 구매 수량 (1~10)
    attribution_window STRING,        -- 전환 귀속 기간 (1day|7day|30day)
    conversion_timestamp BIGINT,      -- 전환 발생 시각 (Unix timestamp)

    -- Conversion Flag
    is_conversion BOOLEAN,            -- 전환 발생 여부 (true=전환, CVR/ROAS/CPA 계산에 필수)

    -- Partition (hour 없음 — 일별 집계 전용)
    year STRING,                      -- 파티션: 연도
    month STRING,                     -- 파티션: 월
    day STRING                        -- 파티션: 일 (hour 파티션 없음 — 시간대별 분석 불가)
```

---

### 2.3 FR-RSQ-03: DOCS_NEGATIVE_EXAMPLES 신설

#### 변수 위치

```python
# seed_chromadb.py 구조 (변경 후)
# ========================= Documentation 정의 =========================
DOCS_BUSINESS_METRICS: list[str] = [...]
DOCS_ATHENA_RULES: list[str] = [...]
DOCS_POLICIES: list[str] = [...]
DOCS_NONEXISTENT_COLUMNS: list[str] = [...]
DOCS_CATEGORICAL_VALUES: list[str] = [...]
DOCS_GLOSSARY: list[str] = [...]
DOCS_SCHEMA_MAPPER: list[str] = [...]
DOCS_NEGATIVE_EXAMPLES: list[str] = [...]   # ← 신규 추가 (DOCS_SCHEMA_MAPPER 다음)
```

#### `train_documentation()` 함수 수정

```python
# 변경 전
all_docs = [
    ("DOCS_BUSINESS_METRICS", DOCS_BUSINESS_METRICS),
    ("DOCS_ATHENA_RULES", DOCS_ATHENA_RULES),
    ("DOCS_POLICIES", DOCS_POLICIES),
    ("DOCS_NONEXISTENT_COLUMNS", DOCS_NONEXISTENT_COLUMNS),
    ("DOCS_CATEGORICAL_VALUES", DOCS_CATEGORICAL_VALUES),
    ("DOCS_GLOSSARY", DOCS_GLOSSARY),
    ("DOCS_SCHEMA_MAPPER", DOCS_SCHEMA_MAPPER),
]

# 변경 후 (DOCS_NEGATIVE_EXAMPLES 추가)
all_docs = [
    ("DOCS_BUSINESS_METRICS", DOCS_BUSINESS_METRICS),
    ("DOCS_ATHENA_RULES", DOCS_ATHENA_RULES),
    ("DOCS_POLICIES", DOCS_POLICIES),
    ("DOCS_NONEXISTENT_COLUMNS", DOCS_NONEXISTENT_COLUMNS),
    ("DOCS_CATEGORICAL_VALUES", DOCS_CATEGORICAL_VALUES),
    ("DOCS_GLOSSARY", DOCS_GLOSSARY),
    ("DOCS_SCHEMA_MAPPER", DOCS_SCHEMA_MAPPER),
    ("DOCS_NEGATIVE_EXAMPLES", DOCS_NEGATIVE_EXAMPLES),  # ← 추가
]
```

#### DOCS_NEGATIVE_EXAMPLES 6개 항목 (Plan 기반)

| # | 패턴명 | 핵심 |
|---|--------|------|
| 1 | CTR 퍼센트 변환 금지 | `ctr_percent` → `ctr` (0~1) |
| 2 | 파티션 날짜 하드코딩 금지 | `'2026'` → `date_format(current_date, '%Y')` |
| 3 | CVR 분모 혼동 | `COUNT(*)` (노출수) → `COUNT(CASE WHEN is_click THEN 1 END)` (클릭수) |
| 4 | OFFSET 미지원 | `OFFSET 1` → `ROW_NUMBER() OVER (...) = 2` |
| 5 | 존재하지 않는 컬럼 | `campaign_name` → `campaign_id` |
| 6 | conversion 컬럼 테이블 오용 | `ad_combined_log`에서 `is_conversion` → `ad_combined_log_summary` |

---

### 2.4 FR-RSQ-04: DOCS_BUSINESS_METRICS CTR/CVR 규칙 수정 (추가 발견)

> **Plan 외 추가 scope**: 코드 조사 중 발견된 DOCS 규칙의 오류. QA 예제가 정답이며 DOCS 규칙을 수정.

#### 판단 근거

| 관점 | DOCS 규칙 (0~1 비율) | QA 예제 (퍼센트 %) |
|------|--------------------|--------------------|
| 사용자 체감 | "CTR이 0.023" → 비직관적 | "CTR이 2.3%" → 즉시 이해 |
| 비즈니스 현장 | 실무에서 사용 안 함 | Google Ads, Meta Ads 등 업계 표준 |
| Redash 표시 | 대시보드에서 이상하게 보임 | 자연스럽게 표시됨 |

→ **QA 예제(퍼센트 형식)가 올바르고, DOCS 규칙이 잘못 작성된 것**

#### 수정 대상: DOCS_BUSINESS_METRICS CTR/CVR 항목

```python
# AS-IS (잘못된 규칙)
"""CTR (Click-Through Rate) — 클릭률 (0~1 비율)
정의: (클릭 수) / (노출 수) → 결과는 0~1 비율로 반환
⚠️ SQL 출력 규칙: * 1.0 비율(0~1) 그대로 반환. * 100 퍼센트 변환·ROUND·_percent suffix 절대 금지
올바른 Athena 계산식: COUNT(CASE WHEN is_click = true THEN 1 END) * 1.0 / NULLIF(COUNT(*), 0) AS ctr
잘못된 예(금지): ROUND(SUM(is_click)*100.0/COUNT(*), 2) AS ctr_percent"""

# TO-BE (수정된 규칙 — 퍼센트 형식을 정답으로)
"""CTR(클릭률)은 사용자가 광고를 본 후 실제로 클릭할 확률을 나타내는 지표로,
클릭 수를 노출 수로 나눈 후 100을 곱한 퍼센트(%) 값으로 반환합니다.
올바른 Athena 계산식: ROUND(SUM(CAST(is_click AS INT)) * 100.0 / NULLIF(COUNT(*), 0), 2) AS ctr_percent
주의: NULLIF로 노출수 0인 경우 Division by Zero 방지 필수"""
```

```python
# AS-IS (잘못된 규칙)
"""CVR (Conversion Rate) — 전환율 (0~1 비율)
⚠️ SQL 출력 규칙: * 1.0 비율(0~1) 반환. * 100 퍼센트 변환·_percent suffix 절대 금지"""

# TO-BE
"""CVR(전환율)은 광고를 클릭한 사용자 중 전환까지 이른 비율을 나타내며,
전환 수를 클릭 수로 나눈 후 100을 곱한 퍼센트(%) 값으로 반환합니다.
분모는 반드시 클릭수여야 하며 전체 노출수(COUNT(*))를 분모로 사용하면 안 됩니다.
올바른 Athena 계산식: ROUND(SUM(CAST(is_conversion AS INT)) * 100.0 / NULLIF(SUM(CAST(is_click AS INT)), 0), 2) AS cvr_percent
주의: ad_combined_log_summary 테이블 필수 (is_conversion 컬럼이 여기에만 존재)"""
```

#### DOCS_NEGATIVE_EXAMPLES도 반영

FR-RSQ-03의 오답 패턴 1번도 함께 수정:

```python
# AS-IS (패턴 1 — 퍼센트를 금지로 설명)
"""[오답 패턴 1] CTR 퍼센트 변환 금지 ..."""

# TO-BE (패턴 1 — NULLIF 누락을 금지로 변경)
"""[오답 패턴 1] CTR/CVR 계산 시 NULLIF 누락 금지
CTR이나 CVR을 계산할 때 분모에 NULLIF를 사용하지 않으면 노출수가 0인 경우 Division by Zero 오류가 발생합니다.
잘못된 쿼리: SUM(CAST(is_click AS INT)) * 100.0 / COUNT(*) AS ctr_percent
올바른 쿼리: ROUND(SUM(CAST(is_click AS INT)) * 100.0 / NULLIF(COUNT(*), 0), 2) AS ctr_percent
CVR도 동일하게 NULLIF(SUM(CAST(is_click AS INT)), 0)을 분모로 사용해야 합니다."""
```

**QA_EXAMPLES는 수정하지 않음** — 현재 퍼센트 형식이 정답이므로 그대로 유지.

---

## 3. 수정 범위 요약

| FR | 대상 | 변경 유형 | 규모 |
|----|------|----------|------|
| FR-RSQ-01 | `DOCS_*` 7개 변수, 25개 항목 | 내용 재작성 | 대규모 |
| FR-RSQ-02 | `DDL_AD_COMBINED_LOG`, `DDL_AD_COMBINED_LOG_SUMMARY` | 인라인 주석 추가 | 소규모 |
| FR-RSQ-03 | `DOCS_NEGATIVE_EXAMPLES` 변수 신설, `train_documentation()` | 신규 추가 | 중규모 |
| FR-RSQ-04 | `DOCS_BUSINESS_METRICS` CTR/CVR 규칙 + `DOCS_NEGATIVE_EXAMPLES` 패턴 1 | 규칙 방향 수정 (0~1 → %) | 소규모 |

---

## 4. 구현 순서 (Do 단계)

```
Step 1: FR-RSQ-03 — DOCS_NEGATIVE_EXAMPLES 변수 신설 + train_documentation() 수정
Step 2: FR-RSQ-02 — DDL 컬럼별 인라인 주석 추가 (2개 테이블)
Step 3: FR-RSQ-01 — DOCS_* 7개 변수 문장형 변환
Step 4: FR-RSQ-04 — DOCS_BUSINESS_METRICS CTR/CVR 규칙 수정 (0~1 → %, QA 예제는 유지)
Step 5: Docker exec으로 재시딩 실행 → 로그 검증
```

---

## 5. 테스트 계획

### 5.1 정적 검증 (코드 리뷰)

| 체크 포인트 | 기준 |
|------------|------|
| 모든 Documentation이 문장형 | 주어+서술어 구조, "합니다/않습니다" 어미 |
| DDL 인라인 주석 | `--` 주석으로 12개 이상 컬럼 설명 포함 |
| `DOCS_NEGATIVE_EXAMPLES` | 6개 항목, `train_documentation()`에 등록 |
| QA_EXAMPLES CTR | `ctr_percent` 패턴 미존재, `ctr` (0~1) 사용 |
| QA_EXAMPLES CVR | `cvr_percent` 패턴 미존재, `cvr` (0~1) 사용 |

### 5.2 동적 검증 (재시딩 후)

```bash
# Docker exec 재시딩
docker exec capa-vanna-api python scripts/seed_chromadb.py

# 예상 로그 (성공 시)
# ✓ [DOCS_NEGATIVE_EXAMPLES] 문서 N/M 학습 완료  ← 새 항목 확인
# ✓ ChromaDB 시딩 완료!
```

### 5.3 기존 단위 테스트 회귀 검증

```bash
docker exec capa-vanna-api pytest tests/unit/ -v
# seed_chromadb.py는 단위 테스트 대상 없음 — 재시딩 성공 로그로 대체
```

---

## 6. 연관 문서

| 문서 | 경로 |
|------|------|
| Plan 문서 | `docs/t1/text-to-sql/10_rag-seeding-quality/01-plan/features/rag-seeding-quality.plan.md` |
| 시딩 스크립트 | `services/vanna-api/scripts/seed_chromadb.py` |
| Reranker 비활성화 | `docs/t1/text-to-sql/09_reranker-deactivation/` |
| RAG 검색 최적화 설계 | `docs/t1/text-to-sql/07_rag-retrieval-optimization/02-design/` |

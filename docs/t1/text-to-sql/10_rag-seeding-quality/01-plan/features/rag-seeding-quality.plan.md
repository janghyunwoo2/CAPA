# [Plan] RAG 시딩 품질 개선

## Executive Summary

| 항목 | 내용 |
|------|------|
| **Feature** | rag-seeding-quality |
| **FR ID** | FR-RSQ-01 ~ FR-RSQ-03 |
| **작성일** | 2026-03-25 |
| **담당** | t1 |
| **참고 문서** | 우아한형제들 기술 블로그 (Document-style 임베딩), `docs/t1/text-to-sql/00_mvp_develop/02-design/` |

### Value Delivered (4관점)

| 관점 | 내용 |
|------|------|
| **Problem** | ChromaDB 임베딩 데이터가 완전 문장형이 아닌 섹션/구조화 포맷으로 저장되어 ko-sroberta-multitask 임베딩 매칭 성능이 저하됨. DDL 컬럼별 COMMENT 부재 및 오답 패턴이 각 항목 내 분산되어 LLM이 반복적으로 동일한 실수를 범함 |
| **Solution** | `seed_chromadb.py` Documentation 전체를 완전 자연어 문장형으로 재작성, DDL 컬럼별 인라인 주석 추가, `DOCS_NEGATIVE_EXAMPLES` 전용 섹션 신설 |
| **Function UX Effect** | 자연어 질문의 임베딩 유사도 향상으로 관련 문서 검색 품질 개선, 오답 패턴 명시로 반복 실수 해소 |
| **Core Value** | 임베딩 품질이 RAG 정확도의 근본이며, 고품질 Document-style 텍스트는 cross-encoder 없이도 충분한 검색 품질을 보장 — `09_reranker-deactivation`과 시너지 |

---

## 1. 배경 및 목적

### 1.1 현황

| 항목 | 현재 상태 | 목표 상태 |
|------|-----------|---------|
| Documentation 포맷 | 섹션형/구조화 (Key-Value 중간 형태) | 완전 자연어 문장형 (Document-style) |
| DDL COMMENT | 테이블 레벨만 존재 | 주요 컬럼 단위 인라인 주석 추가 |
| 오답 노트 | 각 항목 내 인라인으로 분산 포함 | `DOCS_NEGATIVE_EXAMPLES` 전용 섹션 |

### 1.2 개선 근거

**우아한형제들 기술 블로그 권장 패턴:**
- `ko-sroberta-multitask`는 완전한 문장 형태에서 최상의 임베딩 벡터를 생성
- Key-Value 단순 나열은 의미 압축 효율이 낮아 임베딩 품질 저하
- 한글 비즈니스 용어와 영문 컬럼명이 혼재하는 환경에서는 문장 맥락(context)이 매칭 성능에 결정적

**AS-IS (현재):**
```
CTR (Click-Through Rate) — 클릭률 (0~1 비율)
정의: (클릭 수) / (노출 수) → 결과는 0~1 비율로 반환
의미: 사용자가 광고를 본 후 클릭할 확률
⚠️ SQL 출력 규칙: ...
```

**TO-BE (목표):**
```
CTR(클릭률)은 사용자가 광고를 본 후 클릭할 확률을 의미하며, 계산식은 클릭 수를 노출 수로 나눈 값입니다.
결과값은 0에서 1 사이의 비율로 반환해야 하며, 100을 곱한 퍼센트 변환 및 _percent suffix는 절대 금지입니다.
올바른 Athena 계산식: COUNT(CASE WHEN is_click = true THEN 1 END) * 1.0 / NULLIF(COUNT(*), 0) AS ctr
```

---

## 2. 구현 계획

### 2.1 수정 파일 목록

| # | 파일 | 변경 내용 |
|---|------|----------|
| ① | `services/vanna-api/scripts/seed_chromadb.py` | Documentation 문장형 변환 + DDL COMMENT 추가 + DOCS_NEGATIVE_EXAMPLES 신설 |

단일 파일 수정이지만 변경량이 많으므로 3개 FR로 분리하여 순차 적용.

---

### 2.2 FR-RSQ-01: Documentation 문장형 변환

**변환 대상 변수 및 항목 수:**

| 변수명 | 항목 수 | 주요 변환 내용 |
|--------|--------|--------------|
| `DOCS_BUSINESS_METRICS` | 6개 | CTR/CVR/ROAS/CPA/CPC/공통규칙 완전 문장형 |
| `DOCS_ATHENA_RULES` | 4개 | 파티션/날짜함수/타입캐스팅/제한사항 문장형 |
| `DOCS_POLICIES` | 9개 | 코드값 정의 문장형 |
| `DOCS_GLOSSARY` | 1개 | 용어사전 문장형 |
| `DOCS_SCHEMA_MAPPER` | 3개 | 테이블 선택 기준 문장형 |

**변환 원칙:**
- 주어+서술어 구조의 완성된 문장 사용
- 제약조건은 "~해야 합니다", "~금지입니다", "~절대 사용하지 않습니다" 어미로 명시
- 한글 비즈니스 용어와 영문 컬럼명을 문장 안에 자연스럽게 병기
- SQL 코드 예제는 유지 (임베딩 대상 텍스트에 포함되어 쿼리 유사도에 기여)
- 기존 경고 기호(⚠️) 앞에 문장형 설명 선행

---

### 2.3 FR-RSQ-02: DDL 컬럼별 COMMENT 추가

두 테이블(`ad_combined_log`, `ad_combined_log_summary`) 주요 컬럼에 인라인 주석 추가:

```sql
-- 예시 (ad_combined_log)
impression_id STRING,           -- 노출 이벤트 고유 ID (UUID 형식)
user_id STRING,                  -- 광고를 본 사용자 ID (user_000001~user_100000)
ad_id STRING,                    -- 광고 소재 ID (ad_0001~ad_1000)
campaign_id STRING,              -- 캠페인 ID (campaign_01~campaign_05)
advertiser_id STRING,            -- 광고주 ID (advertiser_01~advertiser_30)
platform STRING,                 -- 광고 노출 플랫폼 (web|app_ios|app_android|tablet_ios|tablet_android)
device_type STRING,              -- 기기 유형 (mobile|tablet|desktop|others)
is_click BOOLEAN,                -- 클릭 발생 여부 (true=클릭, false=노출만)
cost_per_impression DOUBLE,      -- 노출 1회당 광고비 (0.005~0.10)
cost_per_click DOUBLE,           -- 클릭 1회당 광고비 (0.1~5.0)
year STRING,   -- 파티션 컬럼 — 반드시 WHERE 조건에 포함 (예: '2026')
month STRING,  -- 파티션 컬럼 — 반드시 WHERE 조건에 포함 (예: '03')
day STRING,    -- 파티션 컬럼 — 반드시 WHERE 조건에 포함 (예: '25')
hour STRING,   -- 파티션 컬럼, ad_combined_log 전용 — 시간대별 분석 시 필수 (예: '09')

-- 예시 (ad_combined_log_summary 추가 컬럼)
conversion_id STRING,            -- 전환 이벤트 ID (NULL이면 전환 미발생)
conversion_type STRING,          -- 전환 유형 (purchase|signup|download|view_content|add_to_cart)
conversion_value DOUBLE,         -- 전환으로 발생한 매출액 (1.0~10000.0)
is_conversion BOOLEAN,           -- 전환 발생 여부 (true=전환, false=전환 없음)
```

---

### 2.4 FR-RSQ-03: DOCS_NEGATIVE_EXAMPLES 전용 섹션 신설

LLM이 자주 틀리는 쿼리 패턴을 별도 변수로 분리 — ChromaDB에 독립 항목으로 시딩:

```python
DOCS_NEGATIVE_EXAMPLES: list[str] = [
    """[오답 패턴 1] CTR 퍼센트 변환 금지
CTR을 계산할 때 퍼센트(100 곱하기) 변환을 하면 안 됩니다.
잘못된 쿼리: SELECT ROUND(SUM(CAST(is_click AS INT)) * 100.0 / COUNT(*), 2) AS ctr_percent
올바른 쿼리: SELECT COUNT(CASE WHEN is_click = true THEN 1 END) * 1.0 / NULLIF(COUNT(*), 0) AS ctr
CTR은 0에서 1 사이의 비율로 반환해야 하며, _percent suffix도 절대 사용하지 않습니다.""",

    """[오답 패턴 2] 파티션 조건 날짜 하드코딩 금지
Athena 쿼리에서 날짜를 직접 상수로 입력하면 시간이 지나면 틀린 쿼리가 됩니다.
잘못된 쿼리: WHERE year='2026' AND month='03' AND day='25'
올바른 쿼리 (어제): WHERE year=date_format(date_add('day',-1,current_date),'%Y') AND month=date_format(date_add('day',-1,current_date),'%m') AND day=date_format(date_add('day',-1,current_date),'%d')
파티션 조건은 반드시 current_date 기반의 동적 날짜 표현을 사용해야 합니다.""",

    """[오답 패턴 3] CVR 분모 혼동 (노출수 대신 클릭수 사용)
CVR(전환율)의 분모는 반드시 클릭수여야 하며, 전체 노출수를 분모로 사용하면 안 됩니다.
잘못된 쿼리: COUNT(CASE WHEN is_conversion=true THEN 1 END) / NULLIF(COUNT(*), 0) AS cvr
올바른 쿼리: COUNT(CASE WHEN is_conversion=true THEN 1 END) * 1.0 / NULLIF(COUNT(CASE WHEN is_click=true THEN 1 END), 0) AS cvr
COUNT(*)는 전체 노출수이므로 CVR이 아닌 CTR의 분모가 됩니다.""",

    """[오답 패턴 4] Athena 미지원 OFFSET 사용 금지
Athena(Presto/Trino)는 OFFSET 구문을 지원하지 않으므로 N번째 순위 조회에 사용하면 안 됩니다.
잘못된 쿼리: ORDER BY click_count DESC LIMIT 1 OFFSET 1
올바른 쿼리: SELECT device_type FROM (SELECT device_type, ROW_NUMBER() OVER (ORDER BY click_count DESC) AS rn FROM ...) WHERE rn = 2
N번째로 높은 값을 구할 때는 반드시 ROW_NUMBER() 윈도우 함수를 사용해야 합니다.""",

    """[오답 패턴 5] 존재하지 않는 컬럼 사용 금지
아래 컬럼들은 스키마에 존재하지 않아 Athena 쿼리 실행 시 오류가 발생합니다.
금지 컬럼: campaign_name, ad_name, advertiser_name, channel, gender, age
대체 방법: campaign_id (campaign_01~05), ad_id (ad_0001~1000), advertiser_id (advertiser_01~30) 사용
이름(name) 대신 ID 컬럼만 존재하므로 GROUP BY나 WHERE 조건에 name 계열 컬럼을 절대 쓰면 안 됩니다.""",

    """[오답 패턴 6] conversion 관련 컬럼을 ad_combined_log에서 조회 금지
conversion_id, conversion_value, is_conversion, conversion_type, attribution_window 컬럼은
ad_combined_log_summary 테이블에만 존재하며 ad_combined_log에는 없습니다.
잘못된 쿼리: SELECT COUNT(CASE WHEN is_conversion=true THEN 1 END) FROM ad_combined_log
올바른 쿼리: SELECT COUNT(CASE WHEN is_conversion=true THEN 1 END) FROM ad_combined_log_summary
CVR, ROAS, CPA 등 전환 관련 지표는 반드시 ad_combined_log_summary 테이블을 사용해야 합니다.""",
]
```

---

## 3. 시딩 재실행 계획

수정 완료 후 ChromaDB 전체 재시딩 필요:

```bash
# Docker 컨테이너 내에서 재시딩 실행
docker exec capa-vanna-api python scripts/seed_chromadb.py
```

> 참고: 기존 ChromaDB 데이터는 재시딩 시 Vanna SDK가 기존 컬렉션을 덮어씀. 별도 초기화 불필요.

---

## 4. 성공 기준

| 항목 | 기준 | 검증 방법 |
|------|------|---------|
| 문장형 변환 | 모든 Documentation 항목이 완전 문장형 | 코드 리뷰 (주어+서술어 구조 확인) |
| DDL COMMENT | 주요 컬럼 12개 이상 인라인 주석 추가 | 코드 리뷰 |
| DOCS_NEGATIVE_EXAMPLES | 6개 이상 오답 패턴 등록 | 코드 리뷰 |
| ChromaDB 재시딩 | 스크립트 오류 없이 완료 | Docker 로그 확인 |
| 기존 단위 테스트 | pytest PASS 유지 | pytest 실행 |

---

## 5. 구현 순서

```
1. [FR-RSQ-03] DOCS_NEGATIVE_EXAMPLES 신설 (신규 추가, 기존 코드 영향 없음)
2. [FR-RSQ-02] DDL 컬럼별 인라인 주석 추가
3. [FR-RSQ-01] Documentation 전체 문장형 변환 (변경량 최대)
4. [검증] docker exec으로 재시딩 실행 → 로그 오류 없음 확인
5. [선택] Slack 테스트 질문 → 응답 품질 체감 확인
```

---

## 6. 연관 문서

| 문서 | 경로 |
|------|------|
| ChromaDB 시딩 스크립트 | `services/vanna-api/scripts/seed_chromadb.py` |
| Reranker 비활성화 계획 | `docs/t1/text-to-sql/09_reranker-deactivation/01-plan/` |
| RAG 검색 최적화 설계 | `docs/t1/text-to-sql/07_rag-retrieval-optimization/02-design/` |
| Text-to-SQL 전체 설계 | `docs/t1/text-to-sql/00_mvp_develop/02-design/` |

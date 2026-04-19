# [Plan] RAG 파이프라인 통합 최적화

## Executive Summary

| 항목 | 내용 |
|------|------|
| **Feature** | pipeline-rag-optimization |
| **FR ID** | FR-PRO-01 ~ FR-PRO-07 |
| **작성일** | 2026-03-25 |
| **담당** | t1 |
| **참고 문서** | `10_rag-seeding-quality`, `11_dynamic-ddl-injection`, `12_retrieval-config-optimization` Plan/Design 문서, 우아한형제들 기술 블로그 (Document-style 임베딩) |
| **통합 사유** | 3개 피처가 `seed_chromadb.py`, `query_pipeline.py`, `rag_retriever.py`를 공유 수정점으로 두어 독립 구현 시 충돌 발생. 충돌 해소 분석 결과를 반영하여 단일 Plan으로 통합 |

### Value Delivered (4관점)

| 관점 | 내용 |
|------|------|
| **Problem** | ① Documentation이 섹션/구조화 포맷이라 ko-sroberta 임베딩 매칭 성능 저하 ② DDL 벡터 검색이 NLU 임베딩 모델과 괴리되어 잘못된 테이블 선택 위험 ③ ChromaDB 컬렉션이 L2 거리 지표로 생성되어 코사인 최적화 모델과 불일치 |
| **Solution** | Documentation 완전 문장형 변환 + QA 메타데이터 기반 DDL 역추적(벡터 검색 제거) + ChromaDB cosine 지표 강제 + n_results 상향 |
| **Function UX Effect** | 자연어 질문의 임베딩 유사도 향상, DDL 오선택 해소, Few-shot 프롬프팅 효과 극대화 |
| **Core Value** | 임베딩 모델 특성에 정합된 검색 인프라 위에 고품질 시딩 데이터를 얹어 SQL 정확도의 근본적 개선 달성 |

---

## 1. 배경 및 목적

### 1.1 현황 (AS-IS)

| 영역 | 현재 상태 | 문제 |
|------|-----------|------|
| Documentation 포맷 | 섹션형/Key-Value 나열 | ko-sroberta 임베딩 매칭 성능 저하 |
| DDL 결정 | SchemaMapper(키워드 규칙) + DDL 벡터 검색 이중 경로 | NLU 모델이 SQL DDL 구문을 자연어와 다르게 임베딩, SchemaMapper는 신규 패턴에 취약 |
| DDL 소스 | `seed_chromadb.py` + `_TABLE_DDL` dict 두 곳에 중복 | 관리 비용 증가, 동기화 실수 위험 |
| 오답 패턴 | 각 Documentation 내 인라인 분산 | LLM이 반복적으로 동일 실수 |
| ChromaDB 거리 지표 | L2 (기본값) | 코사인 유사도 최적화 모델과 불일치 |
| Score 변환식 | `1/(1+distance)` (L2 기준) | cosine distance 범위(0~1)와 부정합 |
| QA 검색 개수 | Top-K = 10 | DDL 토큰 절감 후에도 Few-shot 수 미확대 |

### 1.2 목표 상태 (TO-BE)

| 영역 | 목표 |
|------|------|
| Documentation 포맷 | 완전 자연어 문장형 (Document-style) |
| DDL 결정 | QA 예제 메타데이터 역추적 → `_TABLE_DDL` dict 단일 소스 직접 주입 |
| DDL 소스 | `_TABLE_DDL` dict 단일화 (컬럼별 인라인 주석 포함) |
| 오답 패턴 | `DOCS_NEGATIVE_EXAMPLES` 전용 섹션으로 독립 |
| ChromaDB 거리 지표 | `{"hnsw:space": "cosine"}` 강제 적용 |
| Score 변환식 | `max(0.0, 1.0 - distance)` (cosine 기준) |
| QA 검색 개수 | n_results = 20 (Phase 2 이후 top_k 컷 없음 — n_results가 SQL 예제 수 직접 결정) |
| SchemaMapper | 완전 제거 |
| DDL 벡터 검색 | 완전 제거 |

---

## 2. 통합 설계 — 충돌 해소 반영

### 2.1 원본 3개 Plan 간 충돌 해소 결과

| # | 충돌 지점 | 선택 | 버림 |
|---|----------|------|------|
| 1 | DDL 주석 적용 위치 | `_TABLE_DDL` dict에 인라인 주석 추가 | `seed_chromadb.py` DDL 상수에 주석 추가 (#11이 해당 상수 삭제) |
| 6 | CTR 0~1 vs 퍼센트 | **퍼센트가 정답** (Design FR-RSQ-04 기준, QA 예제와 일치, 업계 표준) | 0~1 비율 강제 (Plan FR-RSQ-03 패턴 1 원안) |
| A | `get_related_ddl_with_score()` score 수정 | 수정 건너뛰기 | #12가 score 공식 변경 → #11이 해당 메서드 삭제 (작업 낭비) |
| B | DOCS_NEGATIVE_EXAMPLES 패턴 3 CVR | percent 형식으로 통일 | 0~1 형식 유지 (Design 누락) |

### 2.2 구현 순서 (충돌 회피 순서)

```
Phase 1: ChromaDB 컬렉션 cosine 재생성 + Score 변환식 교체
  → 이후 모든 시딩이 cosine 컬렉션 위에서 실행됨

Phase 2: Dynamic DDL Injection + SchemaMapper 제거
  → DDL 단일 소스(_TABLE_DDL) 확정, DDL 벡터 검색 제거

Phase 3: RAG 시딩 품질 개선
  → Phase 2에서 확정된 _TABLE_DDL에 인라인 주석 추가
  → Documentation 문장형 변환 + DOCS_NEGATIVE_EXAMPLES 신설

Phase 4: n_results 상향 + 최종 재시딩 + 검증
```

---

## 3. FR 상세 구현 계획

### 3.1 Phase 1: ChromaDB Retrieval 설정 최적화

#### FR-PRO-01: ChromaDB 컬렉션 cosine 지표 강제

**배경**: `ko-sroberta-multitask`는 코사인 유사도 기반 학습 모델이나, ChromaDB 컬렉션이 기본값 L2로 생성되어 HNSW 인덱스 탐색 경로가 cosine 최적 이웃을 놓칠 수 있음.

**기술 제약**: ChromaDB는 컬렉션 생성 후 `hnsw:space` 변경 불가 → 삭제 후 재생성 필요.

**수정 파일**:

| 파일 | 변경 내용 |
|------|----------|
| `scripts/seed_chromadb.py` | 시딩 시작 전 기존 컬렉션 삭제 + cosine 메트릭으로 재생성 로직 추가 |
| `src/query_pipeline.py` | `_VannaAthena.__init__`에서 cosine 메타데이터 주입 방식 확인 및 오버라이드 |

**재생성 대상 컬렉션**: `sql-collection`, `documentation-collection` (2개)
- `ddl-collection`은 Phase 2에서 DDL 벡터 검색을 제거하므로 **삭제만 수행, 재생성 불필요**

```python
# seed_chromadb.py — 시딩 시작 전
for name in ["sql-collection", "documentation-collection"]:
    try:
        chroma_client.delete_collection(name)
    except Exception:
        pass
# ddl-collection은 삭제만 (Phase 2에서 미사용)
try:
    chroma_client.delete_collection("ddl-collection")
except Exception:
    pass
# 이후 VannaAthena 인스턴스 생성 → cosine 메트릭으로 자동 재생성
```

**검증**: `chroma_client.get_collection("sql-collection").metadata` → `{"hnsw:space": "cosine"}`

#### FR-PRO-02: Score 변환식 L2 → cosine 교체

**수정 대상**: `query_pipeline.py`의 2개 메서드 (DDL 메서드는 Phase 2에서 삭제되므로 **건너뜀**)

| 메서드 | 변경 |
|--------|------|
| `get_similar_question_sql()` | `1/(1+d)` → `max(0.0, 1.0 - d)` |
| `get_related_documentation_with_score()` | `1/(1+d)` → `max(0.0, 1.0 - d)` |
| ~~`get_related_ddl_with_score()`~~ | ~~수정 안 함~~ (Phase 2에서 DDL 벡터 검색 자체 제거) |

```python
# AS-IS (L2)
"score": 1.0 / (1.0 + dist)

# TO-BE (cosine)
"score": max(0.0, 1.0 - dist)
```

`rag_retriever.py`의 `_retrieve_sql_examples_with_score()` 주석도 cosine 기준으로 업데이트.

---

### 3.2 Phase 2: Dynamic DDL Injection + SchemaMapper 제거

#### FR-PRO-03: QA 메타데이터 기반 DDL 역추적

**설계**: QA 예제 시딩 시 `metadata.tables`에 참조 테이블 저장 → 검색 시 QA metadata에서 테이블 역추적 → `_TABLE_DDL` dict에서 DDL 직접 주입.

**3단계 플로우**:

```
[Step 1 — 시딩]  seed_chromadb.py
  add_question_sql(question, sql, tables=["ad_combined_log"])
    → ChromaDB sql_collection metadata: {"sql": sql, "tables": "['ad_combined_log']"}
  ※ DDL 시딩(train(ddl=...)) 제거 — ddl_collection 사용 안 함

[Step 2 — 검색]  retrieve_v2(question, keywords)
  get_similar_question_sql() 호출 → 유사 QA 예제 Top-K 추출

[Step 3 — DDL 역추적 + 동적 주입]
  Top-K QA 예제 metadata["tables"] 파싱 → set으로 중복 제거
  → _TABLE_DDL[table] (Python dict) 에서 DDL 원본 조회
  → RAGContext.ddl_context에 적재
  ※ fallback: tables 파싱 불가 시 _TABLE_DDL 전체 주입 (2개 테이블)
```

**수정 파일**:

| # | 파일 | 변경 내용 |
|---|------|----------|
| ① | `src/query_pipeline.py` | `add_question_sql()` 오버라이드에 tables metadata 추가, Step 3.5 SchemaMapper 블록 제거, `SCHEMA_MAPPER_ENABLED` 제거 |
| ② | `src/pipeline/rag_retriever.py` | `retrieve_v2()` schema_hint 파라미터 제거, `_retrieve_candidates()` DDL 역추적 로직 교체, `_extract_tables_from_qa_results()` 신규, DDL 벡터 검색 메서드 제거 |
| ③ | `src/pipeline/schema_mapper.py` | **파일 삭제** |
| ④ | `src/models/rag.py` | `SchemaHint` 모델 제거 |
| ⑤ | `src/models/domain.py` | `SchemaHint` import 및 `ctx.schema_hint` 필드 제거 |
| ⑥ | `scripts/seed_chromadb.py` | DDL 상수 및 `train(ddl=...)` 호출 제거, `add_question_sql()`에 `tables` 파라미터 추가 |
| ⑦ | `docker-compose.local-e2e.yml` | `SCHEMA_MAPPER_ENABLED` 제거 |

**핵심 코드**:

```python
# query_pipeline.py — add_question_sql 오버라이드
def add_question_sql(self, question: str, sql: str, tables: list[str] | None = None, **kwargs) -> str:
    id = deterministic_uuid(question + sql) + "-sql"
    metadata: dict = {"sql": sql}
    if tables:
        metadata["tables"] = str(tables)
    self.sql_collection.add(documents=question, metadatas=[metadata], ids=[id])
    return id

# rag_retriever.py — DDL 역추적
def _extract_tables_from_qa_results(self, qa_results: list) -> set[str]:
    tables: set[str] = set()
    for item in qa_results:
        if not isinstance(item, dict):
            continue
        raw = item.get("tables", "")
        if not raw:
            continue
        try:
            import ast
            parsed = ast.literal_eval(raw)
            if isinstance(parsed, list):
                tables.update(t for t in parsed if isinstance(t, str))
        except Exception:
            pass
    return tables
```

**안전성**:

| 시나리오 | 동작 |
|---------|------|
| QA metadata에 `tables` 있음 | 역추적 → 해당 DDL만 주입 |
| QA metadata에 `tables` 없음 (구버전 시딩) | 자동 fallback → `_TABLE_DDL` 전체 주입 (2개 테이블) |

---

### 3.3 Phase 3: RAG 시딩 품질 개선

#### FR-PRO-04: `_TABLE_DDL` dict 인라인 주석 추가

> **충돌 #1 해소**: 원래 #10은 `seed_chromadb.py`의 DDL 상수에 주석을 추가했으나, Phase 2에서 해당 상수가 삭제됨. DDL 단일 소스인 `_TABLE_DDL` dict에 주석을 적용.

**수정 파일**: `src/pipeline/rag_retriever.py` — `_TABLE_DDL` dict

```python
_TABLE_DDL: dict[str, str] = {
    "ad_combined_log": """CREATE EXTERNAL TABLE ad_combined_log (
    impression_id STRING,           -- 노출 이벤트 고유 ID (UUID 형식)
    user_id STRING,                  -- 광고를 본 사용자 ID (user_000001~user_100000)
    ad_id STRING,                    -- 광고 소재 ID (ad_0001~ad_1000)
    campaign_id STRING,              -- 캠페인 ID (campaign_01~campaign_05)
    advertiser_id STRING,            -- 광고주 ID (advertiser_01~advertiser_30)
    platform STRING,                 -- 노출 플랫폼 (web|app_ios|app_android|tablet_ios|tablet_android)
    device_type STRING,              -- 기기 유형 (mobile|tablet|desktop|others)
    os STRING,                       -- 운영체제 (ios|android|macos|windows)
    delivery_region STRING,          -- 배달 지역 (강남구|서초구 등 서울 25개 자치구)
    ...
    is_click BOOLEAN,                -- 클릭 발생 여부 (true=클릭, false=노출만)
    year STRING,                     -- 파티션: 연도 — WHERE 절 누락 시 풀스캔
    month STRING,                    -- 파티션: 월 — WHERE 절 누락 시 풀스캔
    day STRING,                      -- 파티션: 일 — WHERE 절 누락 시 풀스캔
    hour STRING                      -- 파티션: 시간 — ad_combined_log 전용
)
PARTITIONED BY (year STRING, month STRING, day STRING, hour STRING)
STORED AS PARQUET
COMMENT '광고 노출 및 클릭 이벤트 (시간 단위 로그)'""",
    ...
}
```

전체 컬럼 주석은 #10 Design 문서(`rag-seeding-quality.design.md` §2.2) 기준으로 적용.

#### FR-PRO-05: Documentation 완전 문장형 변환

**수정 파일**: `scripts/seed_chromadb.py` — 7개 변수, 25개 항목 재작성

| 변수명 | 항목 수 | 변환 원칙 |
|--------|--------|----------|
| `DOCS_BUSINESS_METRICS` | 6 | 주어+서술어 완성 문장, **CTR/CVR은 퍼센트 형식이 정답** |
| `DOCS_ATHENA_RULES` | 4 | 의무형 문장 ("반드시 ~해야 합니다") |
| `DOCS_POLICIES` | 9 | "허용값은 ~입니다" 문장형 |
| `DOCS_NONEXISTENT_COLUMNS` | 1 | "~컬럼은 존재하지 않아 오류가 발생합니다" |
| `DOCS_CATEGORICAL_VALUES` | 1 | "~컬럼의 허용값은 ~이며, 이외의 값은 오류를 유발합니다" |
| `DOCS_GLOSSARY` | 1 | "~은(는) ~을 의미합니다" |
| `DOCS_SCHEMA_MAPPER` | 3 | **삭제 또는 테이블 용도 설명 문서로 교체** (SchemaMapper 제거 후 불필요) |

**CTR/CVR 규칙 (충돌 #6 해소)**:

```python
# CTR — 퍼센트가 정답 (QA 예제와 일치, 업계 표준)
"""CTR(클릭률)은 사용자가 광고를 본 후 실제로 클릭할 확률을 나타내는 지표로,
클릭 수를 노출 수로 나눈 후 100을 곱한 퍼센트(%) 값으로 반환합니다.
올바른 Athena 계산식: ROUND(SUM(CAST(is_click AS INT)) * 100.0 / NULLIF(COUNT(*), 0), 2) AS ctr_percent
주의: NULLIF로 노출수 0인 경우 Division by Zero 방지 필수"""

# CVR — 퍼센트, 분모는 클릭수
"""CVR(전환율)은 광고를 클릭한 사용자 중 전환까지 이른 비율을 나타내며,
전환 수를 클릭 수로 나눈 후 100을 곱한 퍼센트(%) 값으로 반환합니다.
분모는 반드시 클릭수여야 하며 전체 노출수(COUNT(*))를 분모로 사용하면 안 됩니다.
올바른 Athena 계산식: ROUND(SUM(CAST(is_conversion AS INT)) * 100.0 / NULLIF(SUM(CAST(is_click AS INT)), 0), 2) AS cvr_percent
주의: ad_combined_log_summary 테이블 필수 (is_conversion 컬럼이 여기에만 존재)"""
```

#### FR-PRO-06: DOCS_NEGATIVE_EXAMPLES 전용 섹션 신설

6개 오답 패턴을 독립 변수로 분리 → ChromaDB에 독립 항목으로 시딩:

| # | 패턴명 | 핵심 |
|---|--------|------|
| 1 | CTR/CVR NULLIF 누락 금지 | 분모에 NULLIF 필수 (충돌 #6 해소 반영) |
| 2 | 파티션 날짜 하드코딩 금지 | `'2026'` → `date_format(current_date, '%Y')` |
| 3 | CVR 분모 혼동 | `COUNT(*)` (노출수) → `SUM(CAST(is_click AS INT))` (클릭수), **퍼센트 형식 반영** (충돌 #B 해소) |
| 4 | OFFSET 미지원 | `OFFSET 1` → `ROW_NUMBER() OVER (...) = 2` |
| 5 | 존재하지 않는 컬럼 | `campaign_name` → `campaign_id` |
| 6 | conversion 컬럼 테이블 오용 | `ad_combined_log`에서 `is_conversion` → `ad_combined_log_summary` |

**패턴 3 수정 (충돌 #B 해소)**:

```python
"""[오답 패턴 3] CVR 분모 혼동 (노출수 대신 클릭수 사용)
CVR(전환율)의 분모는 반드시 클릭수여야 하며, 전체 노출수를 분모로 사용하면 안 됩니다.
잘못된 쿼리: ROUND(SUM(CAST(is_conversion AS INT)) * 100.0 / NULLIF(COUNT(*), 0), 2) AS cvr_percent
올바른 쿼리: ROUND(SUM(CAST(is_conversion AS INT)) * 100.0 / NULLIF(SUM(CAST(is_click AS INT)), 0), 2) AS cvr_percent
COUNT(*)는 전체 노출수이므로 CVR이 아닌 CTR의 분모가 됩니다."""
```

---

### 3.4 Phase 4: n_results 상향 + 최종 재시딩

#### FR-PRO-07: n_results 상향

**배경**: Phase 2에서 `retrieve_v2()`를 단순화하면 `candidates[:top_k]` 컷이 사라진다. 이후 `n_results`가 SQL 예제 수를 직접 결정하므로 n_results 상향이 Few-shot 확대에 직결된다.

**수정**: `src/query_pipeline.py` — `get_similar_question_sql()`

```python
# AS-IS
n_results = self.n_results_sql          # 기본값 10
if PHASE2_RAG_ENABLED:
    n_results = max(n_results, 10)      # PHASE2에서도 10

# TO-BE
n_results = self.n_results_sql          # 기본값 유지
if PHASE2_RAG_ENABLED:
    n_results = max(n_results, 20)      # DDL 역추적 후보 풀 확대 + Few-shot 증가
```

**환경변수 (선택)**: `N_RESULTS_SQL_PHASE2` (기본값: `20`) — 롤백 용이.

---

## 4. 수정 대상 파일 전체 요약

| # | 파일 | Phase | 변경 유형 | 주요 수정 |
|---|------|-------|----------|----------|
| 1 | `src/query_pipeline.py` | 1,2,4 | 수정 | cosine 설정, score 변환식(2개 메서드), `add_question_sql` tables metadata, Step 3.5 제거, n_results 상향 |
| 2 | `src/pipeline/rag_retriever.py` | 1,2,3 | 수정 | score 주석 업데이트, `retrieve_v2()` 단순화(schema_hint 제거), DDL 역추적 로직 교체, `_TABLE_DDL` 인라인 주석 추가, DDL 벡터 검색 메서드 **주석처리** |
| 3 | `scripts/seed_chromadb.py` | 1,2,3 | 수정 | 컬렉션 cosine 재생성, DDL 상수/시딩 제거, QA tables metadata 추가, Documentation 문장형 변환, DOCS_NEGATIVE_EXAMPLES 추가 |
| 4 | `src/pipeline/schema_mapper.py` | 2 | **삭제** | 파일 전체 제거 |
| 5 | `src/models/rag.py` | 2 | 수정 | `SchemaHint` 모델 제거 |
| 6 | `src/models/domain.py` | 2 | 수정 | `SchemaHint` import/필드 제거 |
| 7 | `docker-compose.local-e2e.yml` | 2,4 | 수정 | 환경변수 업데이트 |

---

## 5. 환경변수 변경

| 변수 | 변경 | 기본값 |
|------|------|--------|
| `N_RESULTS_SQL_PHASE2` | **신규 (선택)** | `20` |
| `SCHEMA_MAPPER_ENABLED` | **제거** | — |
| `RERANKER_ENABLED` | 기본값 변경 `true` → `false` | `false` ✅ 완료 |
| `LLM_FILTER_ENABLED` | 기본값 변경 `true` → `false` | `false` ✅ 완료 |

---

## 6. 구현 일정

| Day | Phase | 작업 내용 | 산출물 |
|-----|-------|----------|--------|
| Day 1 | **Phase 1** | ChromaDB cosine 컬렉션 재생성 + score 변환식 교체 (2개 메서드) | `query_pipeline.py`, `seed_chromadb.py` 수정 |
| Day 1~2 | **Phase 2** | DDL 역추적 구현 + SchemaMapper 제거 + DDL 시딩 제거 | `rag_retriever.py`, `query_pipeline.py`, `schema_mapper.py` 삭제, 모델 정리 |
| Day 2~3 | **Phase 3** | `_TABLE_DDL` 주석 추가 + Documentation 문장형 변환 + DOCS_NEGATIVE_EXAMPLES 신설 | `rag_retriever.py`, `seed_chromadb.py` 수정 |
| Day 3 | **Phase 4** | n_results 상향 + 최종 재시딩 + 검증 | `query_pipeline.py` 수정, 검증 로그 |

**총 예상 기간**: 3일

---

## 7. 성공 기준

| 항목 | 기준 | 검증 방법 |
|------|------|---------|
| 컬렉션 거리 지표 | `sql-collection`, `documentation-collection` 모두 cosine | `collection.metadata["hnsw:space"]` 확인 |
| DDL 정확도 | 질문 관련 테이블 DDL만 RAGContext에 포함 | Docker 로그 RAGContext 확인 |
| SchemaMapper 제거 | Step 3.5 로그 없음, `schema_mapper.py` 미존재 | 로그 + 파일 확인 |
| DDL 시딩 제거 | `ddl-collection` 미존재 또는 count=0 | ChromaDB 컬렉션 확인 |
| Documentation 문장형 | 모든 항목이 주어+서술어 구조 | 코드 리뷰 |
| DDL 인라인 주석 | `_TABLE_DDL` dict 내 주요 컬럼 인라인 주석 | 코드 리뷰 |
| DOCS_NEGATIVE_EXAMPLES | 6개 항목 등록 | 코드 리뷰 |
| n_results | PHASE2=true 시 20개 | `get_similar_question_sql()` 반환 개수 확인 |
| 기존 단위 테스트 | pytest 전체 PASS | pytest 실행 |
| 재시딩 | 스크립트 오류 없이 완료 | Docker 로그 |

---

## 8. 위험 요소 및 대응

| 위험 | 가능성 | 대응 |
|------|--------|------|
| Vanna `ChromaDB_VectorStore`가 `hnsw:space` 주입 미지원 | 중간 | `__init__` 후 컬렉션 직접 교체 오버라이드로 우회 |
| cosine distance 부동소수점 오차 (1.0 초과) | 낮음 | `max(0.0, 1.0 - dist)` 방어 처리 |
| 기존 QA 예제에 `tables` metadata 없음 (구버전 시딩) | 높음 | fallback → `_TABLE_DDL` 전체 주입 (2개 테이블) |
| EKS PVC 마운트 ChromaDB 마이그레이션 | 중간 | 로컬/E2E 환경 우선, EKS는 별도 절차 (본 Plan 범위 외) |

---

## 9. 연관 문서

| 문서 | 경로 |
|------|------|
| RAG 시딩 품질 Plan | `docs/t1/text-to-sql/10_rag-seeding-quality/01-plan/` |
| RAG 시딩 품질 Design | `docs/t1/text-to-sql/10_rag-seeding-quality/02-design/` |
| Dynamic DDL Injection Plan | `docs/t1/text-to-sql/11_dynamic-ddl-injection/01-plan/` |
| Retrieval Config Optimization Plan | `docs/t1/text-to-sql/12_retrieval-config-optimization/01-plan/` |
| Reranker 비활성화 | `docs/t1/text-to-sql/09_reranker-deactivation/` |
| RAG 검색 최적화 설계 | `docs/t1/text-to-sql/07_rag-retrieval-optimization/` |
| 시딩 스크립트 | `services/vanna-api/scripts/seed_chromadb.py` |
| RAG Retriever | `services/vanna-api/src/pipeline/rag_retriever.py` |
| Query Pipeline | `services/vanna-api/src/query_pipeline.py` |

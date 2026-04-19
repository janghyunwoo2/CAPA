# [Design] RAG 파이프라인 통합 최적화

## Executive Summary

| 항목 | 내용 |
|------|------|
| **Feature** | pipeline-rag-optimization |
| **참조 Plan** | `docs/t1/text-to-sql/13_pipeline-rag-optimization/01-plan/features/pipeline-rag-optimization.plan.md` |
| **작성일** | 2026-03-25 |
| **수정 대상 파일** | `query_pipeline.py`, `rag_retriever.py`, `seed_chromadb.py`, `schema_mapper.py`, `models/rag.py`, `models/domain.py`, `docker-compose.local-e2e.yml` |

---

## 1. 현재 구조 분석

### 1.1 RAG 파이프라인 전체 흐름 (AS-IS)

```
query_pipeline.py run()
  Step 3: KeywordExtractor
  Step 3.5: SchemaMapper (SCHEMA_MAPPER_ENABLED=true 시)
              → SchemaHint(tables, is_definitive)
  Step 4: retrieve_v2(question, keywords, schema_hint)
              → _retrieve_candidates()
                    is_definitive=True  → _TABLE_DDL dict 직접
                    is_definitive=False → _retrieve_ddl_with_score() (DDL 벡터 검색)
                    + _retrieve_documentation_with_score()
                    + _retrieve_sql_examples_with_score()
              → candidates[:top_k]  (Reranker 비활성화)
              → LLM 필터 스킵       (LLM_FILTER_ENABLED=false)
              → RAGContext
  Step 5: SQLGenerator → SQL
```

### 1.2 목표 흐름 (TO-BE)

```
query_pipeline.py run()
  Step 3: KeywordExtractor
  # Step 3.5 SchemaMapper 제거
  Step 4: retrieve_v2(question, keywords)  ← schema_hint 파라미터 제거
              1. get_similar_question_sql(n_results=20) → QA 예제
              2. _extract_tables_from_qa_results()     → 테이블 집합
              3. _TABLE_DDL[table]                     → DDL 직접 주입
              4. _retrieve_documentation()             → Documentation
              → RAGContext 직접 구성
  Step 5: SQLGenerator → SQL
```

### 1.3 수정 파일 전체 요약

| 파일 | Phase | 처리 |
|------|-------|------|
| `src/query_pipeline.py` | 1,2,4 | 수정 |
| `src/pipeline/rag_retriever.py` | 1,2,3 | 수정 |
| `scripts/seed_chromadb.py` | 1,2,3 | 수정 |
| `src/pipeline/schema_mapper.py` | 2 | **삭제** |
| `src/models/rag.py` | 2 | 수정 (주석처리) |
| `src/models/domain.py` | 2 | 수정 |
| `docker-compose.local-e2e.yml` | 2 | 수정 |

---

## 2. Phase 1: ChromaDB Retrieval 설정 최적화

### 2.1 FR-PRO-01: ChromaDB 컬렉션 cosine 지표 강제

**수정 파일**: `scripts/seed_chromadb.py`

ChromaDB는 컬렉션 생성 후 `hnsw:space` 변경 불가 → 시딩 시작 전 삭제+재생성.

```python
# seed_chromadb.py 상단 — VannaAthena 인스턴스 생성 직전에 추가

def reset_collections(chroma_host: str, chroma_port: int) -> None:
    """기존 컬렉션 삭제 후 cosine 메트릭으로 재생성 준비."""
    import chromadb
    client = chromadb.HttpClient(host=chroma_host, port=chroma_port)

    # sql-collection, documentation-collection: cosine으로 재생성
    for name in ["sql-collection", "documentation-collection"]:
        try:
            client.delete_collection(name)
            logger.info(f"컬렉션 삭제 완료: {name}")
        except Exception:
            pass  # 존재하지 않으면 무시

    # ddl-collection: Phase 2에서 미사용 → 삭제만
    try:
        client.delete_collection("ddl-collection")
        logger.info("ddl-collection 삭제 완료 (Phase 2 이후 미사용)")
    except Exception:
        pass
```

**수정 파일**: `src/query_pipeline.py` — `_VannaAthena.__init__`

Vanna의 `ChromaDB_VectorStore`가 `get_or_create_collection()` 내부 호출 시 cosine 메타데이터를 주입할 수 있는지 확인 필요. 지원하지 않을 경우 `__init__` 이후 컬렉션 직접 교체:

```python
# _VannaAthena.__init__ 내부 — ChromaDB_VectorStore 초기화 후
def __init__(self, config=None):
    ChromaDB_VectorStore.__init__(self, config=config)
    Anthropic_Chat.__init__(self, config=config)
    # cosine 메트릭 강제 적용 (L2 기본값 우회)
    self._ensure_cosine_collections()

def _ensure_cosine_collections(self) -> None:
    """sql-collection, documentation-collection의 hnsw:space=cosine 보장."""
    for col_attr in ["sql_collection", "documentation_collection"]:
        col = getattr(self, col_attr, None)
        if col and col.metadata.get("hnsw:space") != "cosine":
            # 이미 삭제 후 재생성된 상태라면 cosine으로 재생성
            client = self._client  # ChromaDB_VectorStore 내부 client
            name = col.name
            client.delete_collection(name)
            setattr(self, col_attr, client.create_collection(
                name=name,
                metadata={"hnsw:space": "cosine"},
                embedding_function=_KO_EMBEDDING_FUNCTION,
            ))
            logger.info(f"{name}: cosine 메트릭으로 재생성 완료")
```

**검증**: 재시딩 후 `collection.metadata["hnsw:space"] == "cosine"` 확인.

---

### 2.2 FR-PRO-02: Score 변환식 L2 → cosine 교체

**수정 파일**: `src/query_pipeline.py`

수정 대상 2개 메서드 (`get_related_ddl_with_score()`는 Phase 2에서 주석처리 → 건너뜀):

#### `get_similar_question_sql()` (line ~125)

```python
# AS-IS
"score": 1.0 / (1.0 + dist)

# TO-BE
"score": max(0.0, 1.0 - dist)   # cosine distance: 0=동일, 1=직교
```

#### `get_related_documentation_with_score()` (line ~173)

```python
# AS-IS
{"text": doc, "score": 1.0 / (1.0 + dist)}

# TO-BE
{"text": doc, "score": max(0.0, 1.0 - dist)}
```

**수정 파일**: `src/pipeline/rag_retriever.py` — `_retrieve_sql_examples_with_score()` 주석 업데이트

```python
def _retrieve_sql_examples_with_score(self, query: str) -> list[dict]:
    """SQL 예제를 ChromaDB cosine distance 기반 score와 함께 반환.

    Returns:
        list of {"text": str, "score": float}
        score = 1.0 - cosine_distance  (0~1, 클수록 유사)
    """
```

---

## 3. Phase 2: retrieve_v2 단순화 + Dynamic DDL Injection + SchemaMapper 제거

### 3.1 FR-PRO-03: retrieve_v2() 재구현

**수정 파일**: `src/pipeline/rag_retriever.py`

#### 환경변수 제거

```python
# 제거 대상 (모듈 상단)
RERANKER_TOP_K: int = int(os.getenv("RERANKER_TOP_K", "7"))           # 제거
RERANKER_TOP_K_DEFINITIVE: int = int(os.getenv(...))                   # 제거
LLM_FILTER_ENABLED: bool = os.getenv("LLM_FILTER_ENABLED", "false")... # 제거 (기본값 변경 완료)
```

#### `retrieve_v2()` 전면 재구현

```python
# AS-IS 시그니처
async def retrieve_v2(
    self, question: str, keywords: list[str], schema_hint: Optional[SchemaHint] = None
) -> RAGContext:

# TO-BE 시그니처
async def retrieve_v2(
    self, question: str, keywords: list[str]
) -> RAGContext:
    """단순 RAG 검색 + Dynamic DDL Injection.

    Phase 1 스타일: 검색 → RAGContext 직접 구성 (Reranker/LLM필터 없음)
    DDL은 QA metadata에서 역추적하여 _TABLE_DDL dict에서 직접 주입.
    """
    search_query = question
    if keywords:
        search_query = f"{question} {' '.join(keywords)}"

    try:
        # 1. QA 예제 검색 (n_results는 get_similar_question_sql 내부에서 결정)
        qa_results = self._vanna.get_similar_question_sql(question=search_query)

        # 2. DDL 역추적: QA metadata["tables"] → _TABLE_DDL dict
        tables = self._extract_tables_from_qa_results(qa_results)
        if not tables:
            tables = set(_TABLE_DDL.keys())  # fallback: 전체 주입
        ddl_context = [_TABLE_DDL[t] for t in sorted(tables) if t in _TABLE_DDL]

        # 3. SQL 예제 텍스트 추출
        sql_examples = [
            f"Q: {item['question']}\nSQL: {item['sql']}"
            for item in qa_results
            if isinstance(item, dict) and item.get("sql")
        ]

        # 4. Documentation 검색
        doc_context = self._retrieve_documentation(search_query)

        logger.info(
            f"RAG 검색 완료: DDL {len(ddl_context)}건 "
            f"(tables={sorted(tables)}), "
            f"Docs {len(doc_context)}건, "
            f"SQL 예제 {len(sql_examples)}건"
        )
        return RAGContext(
            ddl_context=ddl_context,
            documentation_context=doc_context,
            sql_examples=sql_examples,
        )
    except Exception as e:
        logger.error(f"RAG 검색 실패: {e}, 빈 컨텍스트로 진행")
        return RAGContext()
```

#### `_extract_tables_from_qa_results()` 신규 추가

```python
def _extract_tables_from_qa_results(self, qa_results: list) -> set[str]:
    """QA 예제 metadata["tables"] 파싱 → 테이블 이름 집합 반환.

    ChromaDB metadata 값은 str 타입 → ast.literal_eval로 list 복원.
    예: "['ad_combined_log', 'ad_combined_log_summary']" → {'ad_combined_log', ...}
    """
    import ast
    tables: set[str] = set()
    for item in qa_results:
        if not isinstance(item, dict):
            continue
        raw = item.get("tables", "")
        if not raw:
            continue
        try:
            parsed = ast.literal_eval(raw)
            if isinstance(parsed, list):
                tables.update(t for t in parsed if isinstance(t, str))
        except Exception:
            pass
    return tables
```

#### 주석처리 대상 메서드 (파일 내 유지, 비활성화)

```python
# 주석처리 — Phase 2 이후 미사용
# def _retrieve_candidates(self, query, schema_hint=None): ...
# def _retrieve_ddl_with_score(self, query): ...
# def _retrieve_ddl(self, query): ...
# def _should_skip_llm_filter(self, schema_hint): ...
# def _llm_filter(self, question, candidates): ...
# def _candidates_to_rag_context(self, candidates): ...
```

---

### 3.2 query_pipeline.py 수정

#### `add_question_sql()` 오버라이드 — tables metadata 추가

```python
# AS-IS
def add_question_sql(self, question: str, sql: str, **kwargs) -> str:
    id = deterministic_uuid(question + sql) + "-sql"
    self.sql_collection.add(
        documents=question,
        metadatas=[{"sql": sql}],
        ids=[id],
    )
    return id

# TO-BE
def add_question_sql(self, question: str, sql: str, tables: list[str] | None = None, **kwargs) -> str:
    """question만 document로 저장, SQL과 tables는 metadata로 분리."""
    id = deterministic_uuid(question + sql) + "-sql"
    metadata: dict = {"sql": sql}
    if tables:
        metadata["tables"] = str(tables)  # ChromaDB metadata는 str만 허용
    self.sql_collection.add(
        documents=question,
        metadatas=[metadata],
        ids=[id],
    )
    return id
```

#### 모듈 상단 환경변수 제거/정리

```python
# 제거
SCHEMA_MAPPER_ENABLED = os.getenv("SCHEMA_MAPPER_ENABLED", "false").lower() == "true"

# 유지 (이미 기본값 변경 완료)
RERANKER_ENABLED = os.getenv("RERANKER_ENABLED", "false").lower() == "true"
```

#### Reranker 초기화 블록 주석처리

```python
# __init__ 내부
if PHASE2_RAG_ENABLED:
    _phase2_client = _anthropic_client
    # 주석처리: Reranker 영구 비활성화
    # if RERANKER_ENABLED:
    #     from .pipeline.reranker import CrossEncoderReranker
    #     _reranker = CrossEncoderReranker()
    # else:
    #     _reranker = None
    _reranker = None
    logger.info("Reranker 비활성화 (영구)")
else:
    _reranker = None
    _phase2_client = None
```

#### Step 3.5 SchemaMapper 블록 제거

```python
# run() 내부 — Step 3.5 전체 제거 (schema_mapper import 포함)
# 제거: if SCHEMA_MAPPER_ENABLED and self._schema_mapper is not None: ...

# Step 4: retrieve_v2 호출 시 schema_hint 파라미터 제거
if PHASE2_RAG_ENABLED:
    ctx.rag_context = await self._rag_retriever.retrieve_v2(
        question=ctx.refined_question,
        keywords=ctx.keywords,
        # schema_hint 제거
    )
```

#### `__init__` 내 SchemaMapper 초기화 제거

```python
# 제거
if SCHEMA_MAPPER_ENABLED:
    from .pipeline.schema_mapper import SchemaMapper
    self._schema_mapper: Optional[Any] = SchemaMapper()
else:
    self._schema_mapper = None
```

---

### 3.3 models/rag.py — SchemaHint 제거, 나머지 주석처리

```python
# 제거: SchemaHint 클래스 (SchemaMapper 제거에 따라)
# class SchemaHint(BaseModel): ...

# 주석처리: 3단계 RAG 전용 모델 (코드 참조용 보존)
# class CandidateDocument(BaseModel): ...
# class RerankResult(BaseModel): ...
# class LLMFilterResult(BaseModel): ...
```

---

### 3.4 models/domain.py — schema_hint 필드 제거

```python
# 제거
from .rag import SchemaHint  # import 제거

class PipelineContext(BaseModel):
    ...
    # Step 3.5 제거
    # schema_hint: Optional[SchemaHint] = None   ← 제거
    ...
```

---

### 3.5 schema_mapper.py — 파일 삭제

`services/vanna-api/src/pipeline/schema_mapper.py` 파일 전체 삭제.

---

### 3.6 seed_chromadb.py — DDL 시딩 제거 + QA tables metadata 추가

#### DDL 상수 및 시딩 호출 제거

```python
# 제거 대상
DDL_AD_COMBINED_LOG = """..."""             # 삭제
DDL_AD_COMBINED_LOG_SUMMARY = """..."""     # 삭제

def train_ddl(vanna) -> None:              # 함수 전체 삭제
    vanna.train(ddl=DDL_AD_COMBINED_LOG)
    vanna.train(ddl=DDL_AD_COMBINED_LOG_SUMMARY)
```

#### `add_question_sql()` 호출에 tables 파라미터 추가

모든 QA 예제에 해당 쿼리가 참조하는 테이블을 명시:

```python
# 예시 — CTR 쿼리 (ad_combined_log)
vanna.add_question_sql(
    question="어제 CTR(클릭률)은 얼마인가요?",
    sql="""SELECT ROUND(SUM(CAST(is_click AS INT)) * 100.0 / NULLIF(COUNT(*), 0), 2) AS ctr_percent
FROM ad_combined_log
WHERE ...""",
    tables=["ad_combined_log"],
)

# 예시 — CVR 쿼리 (ad_combined_log_summary)
vanna.add_question_sql(
    question="지난달 전환율(CVR)은 얼마인가요?",
    sql="""SELECT ROUND(SUM(CAST(is_conversion AS INT)) * 100.0 / NULLIF(SUM(CAST(is_click AS INT)), 0), 2) AS cvr_percent
FROM ad_combined_log_summary
WHERE ...""",
    tables=["ad_combined_log_summary"],
)

# 예시 — 두 테이블 조인이 필요한 경우
vanna.add_question_sql(
    question="...",
    sql="...",
    tables=["ad_combined_log", "ad_combined_log_summary"],
)
```

**테이블 분류 기준**:

| 테이블 | 포함 조건 |
|--------|----------|
| `ad_combined_log` | impression, click, CTR, CPC, 시간대별 분석, hour 파티션 |
| `ad_combined_log_summary` | conversion, CVR, ROAS, CPA, is_conversion, conversion_value |
| 둘 다 | 두 테이블을 JOIN하거나 각각 집계 비교하는 쿼리 |

---

### 3.7 docker-compose.local-e2e.yml 수정

```yaml
# 제거
- SCHEMA_MAPPER_ENABLED=true

# 유지 (이미 설정됨)
- RERANKER_ENABLED=false
- LLM_FILTER_ENABLED=false
```

---

## 4. Phase 3: RAG 시딩 품질 개선

### 4.1 FR-PRO-04: `_TABLE_DDL` dict 인라인 주석 추가

**수정 파일**: `src/pipeline/rag_retriever.py`

```python
_TABLE_DDL: dict[str, str] = {
    "ad_combined_log": """CREATE EXTERNAL TABLE ad_combined_log (
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
    is_click BOOLEAN,                 -- 클릭 발생 여부 (true=클릭, false=노출만, CTR 계산 필수)

    -- Partition 컬럼 (WHERE 절 누락 시 풀스캔 — 반드시 포함)
    year STRING,                      -- 파티션: 연도 (예: '2026')
    month STRING,                     -- 파티션: 월 (예: '03')
    day STRING,                       -- 파티션: 일 (예: '25')
    hour STRING                       -- 파티션: 시간 (예: '09') — ad_combined_log 전용
)
PARTITIONED BY (year STRING, month STRING, day STRING, hour STRING)
STORED AS PARQUET
COMMENT '광고 노출 및 클릭 이벤트 (시간 단위 로그)'""",

    "ad_combined_log_summary": """CREATE EXTERNAL TABLE ad_combined_log_summary (
    -- Impression/Click 컬럼 (ad_combined_log와 동일)
    impression_id STRING,            -- 노출 이벤트 고유 ID
    user_id STRING,                   -- 사용자 ID
    ad_id STRING,                     -- 광고 소재 ID
    campaign_id STRING,               -- 캠페인 ID
    advertiser_id STRING,             -- 광고주 ID
    platform STRING,                  -- 노출 플랫폼
    device_type STRING,               -- 기기 유형
    os STRING,                        -- 운영체제
    delivery_region STRING,           -- 배달 지역
    user_lat DOUBLE,                  -- 사용자 위도
    user_long DOUBLE,                 -- 사용자 경도
    store_id STRING,                  -- 매장 ID
    food_category STRING,             -- 음식 카테고리
    ad_position STRING,               -- 광고 위치
    ad_format STRING,                 -- 광고 포맷
    user_agent STRING,                -- User-Agent
    ip_address STRING,                -- IP 주소
    session_id STRING,                -- 세션 ID
    keyword STRING,                   -- 검색 키워드
    cost_per_impression DOUBLE,       -- 노출 1회당 광고비
    impression_timestamp BIGINT,      -- 노출 시각 (Unix timestamp)
    click_id STRING,                  -- 클릭 이벤트 ID
    click_position_x INT,             -- 클릭 X 좌표
    click_position_y INT,             -- 클릭 Y 좌표
    landing_page_url STRING,          -- 랜딩 페이지 URL
    cost_per_click DOUBLE,            -- 클릭 1회당 광고비
    click_timestamp BIGINT,           -- 클릭 시각
    is_click BOOLEAN,                 -- 클릭 여부

    -- Conversion 관련 컬럼 (이 컬럼들은 ad_combined_log에 없음 — summary 전용)
    conversion_id STRING,             -- 전환 이벤트 ID (전환 미발생 시 NULL)
    conversion_type STRING,           -- 전환 유형 (purchase|signup|download|view_content|add_to_cart)
    conversion_value DOUBLE,          -- 전환 매출액 (1.0~10000.0, ROAS 계산에 사용)
    product_id STRING,                -- 전환 상품 ID (prod_00001~prod_10000)
    quantity INT,                     -- 구매 수량 (1~10)
    attribution_window STRING,        -- 전환 귀속 기간 (1day|7day|30day)
    conversion_timestamp BIGINT,      -- 전환 발생 시각 (Unix timestamp)

    -- Conversion Flag
    is_conversion BOOLEAN,            -- 전환 발생 여부 (true=전환, CVR/ROAS/CPA 계산 필수)

    -- Partition 컬럼 (hour 없음 — 일별 집계 전용, 시간대별 분석 불가)
    year STRING,                      -- 파티션: 연도
    month STRING,                     -- 파티션: 월
    day STRING                        -- 파티션: 일
)
PARTITIONED BY (year STRING, month STRING, day STRING)
STORED AS PARQUET
COMMENT '광고 성과 일일 요약 (노출+클릭+전환 데이터)'""",
}
```

---

### 4.2 FR-PRO-05: Documentation 완전 문장형 변환

**수정 파일**: `scripts/seed_chromadb.py`

변환 원칙:
- 주어+서술어 완성 문장 (어미: "~합니다", "~해야 합니다", "~금지입니다")
- CTR/CVR: **퍼센트 형식** (0~1 비율 아님)
- SQL 코드 예제 유지 (임베딩 대상에 포함)
- `DOCS_SCHEMA_MAPPER` 삭제 (SchemaMapper 제거 후 불필요)

**주요 변환 예시**:

`DOCS_BUSINESS_METRICS` — CTR:
```python
# AS-IS
"""CTR (Click-Through Rate) — 클릭률 (0~1 비율)
정의: (클릭 수) / (노출 수) → 결과는 0~1 비율로 반환
⚠️ SQL 출력 규칙: * 1.0 비율(0~1) 그대로 반환..."""

# TO-BE
"""CTR(클릭률)은 사용자가 광고를 본 후 실제로 클릭할 확률을 나타내는 지표로,
클릭 수를 노출 수로 나눈 후 100을 곱한 퍼센트(%) 값으로 반환합니다.
올바른 Athena 계산식: ROUND(SUM(CAST(is_click AS INT)) * 100.0 / NULLIF(COUNT(*), 0), 2) AS ctr_percent
주의: NULLIF로 노출수 0인 경우 Division by Zero 방지 필수"""
```

`DOCS_BUSINESS_METRICS` — CVR:
```python
# TO-BE
"""CVR(전환율)은 광고를 클릭한 사용자 중 전환까지 이른 비율을 나타내며,
전환 수를 클릭 수로 나눈 후 100을 곱한 퍼센트(%) 값으로 반환합니다.
분모는 반드시 클릭수여야 하며 전체 노출수(COUNT(*))를 분모로 사용하면 안 됩니다.
올바른 Athena 계산식: ROUND(SUM(CAST(is_conversion AS INT)) * 100.0 / NULLIF(SUM(CAST(is_click AS INT)), 0), 2) AS cvr_percent
주의: ad_combined_log_summary 테이블 필수 (is_conversion 컬럼이 여기에만 존재)"""
```

`train_documentation()` 함수 — `DOCS_SCHEMA_MAPPER` 제거:
```python
# AS-IS
all_docs = [
    ...
    ("DOCS_SCHEMA_MAPPER", DOCS_SCHEMA_MAPPER),
]

# TO-BE — DOCS_SCHEMA_MAPPER 제거
all_docs = [
    ("DOCS_BUSINESS_METRICS", DOCS_BUSINESS_METRICS),
    ("DOCS_ATHENA_RULES", DOCS_ATHENA_RULES),
    ("DOCS_POLICIES", DOCS_POLICIES),
    ("DOCS_NONEXISTENT_COLUMNS", DOCS_NONEXISTENT_COLUMNS),
    ("DOCS_CATEGORICAL_VALUES", DOCS_CATEGORICAL_VALUES),
    ("DOCS_GLOSSARY", DOCS_GLOSSARY),
    ("DOCS_NEGATIVE_EXAMPLES", DOCS_NEGATIVE_EXAMPLES),  # 신규
]
```

---

### 4.3 FR-PRO-06: DOCS_NEGATIVE_EXAMPLES 전용 섹션 신설

**수정 파일**: `scripts/seed_chromadb.py`

```python
DOCS_NEGATIVE_EXAMPLES: list[str] = [
    """[오답 패턴 1] CTR/CVR 계산 시 NULLIF 누락 금지
CTR이나 CVR을 계산할 때 분모에 NULLIF를 사용하지 않으면 노출수가 0인 경우 Division by Zero 오류가 발생합니다.
잘못된 쿼리: SUM(CAST(is_click AS INT)) * 100.0 / COUNT(*) AS ctr_percent
올바른 쿼리: ROUND(SUM(CAST(is_click AS INT)) * 100.0 / NULLIF(COUNT(*), 0), 2) AS ctr_percent
CVR도 동일하게 NULLIF(SUM(CAST(is_click AS INT)), 0)을 분모로 사용해야 합니다.""",

    """[오답 패턴 2] 파티션 조건 날짜 하드코딩 금지
Athena 쿼리에서 날짜를 직접 상수로 입력하면 시간이 지나면 틀린 쿼리가 됩니다.
잘못된 쿼리: WHERE year='2026' AND month='03' AND day='25'
올바른 쿼리 (어제): WHERE year=date_format(date_add('day',-1,current_date),'%Y')
  AND month=date_format(date_add('day',-1,current_date),'%m')
  AND day=date_format(date_add('day',-1,current_date),'%d')
파티션 조건은 반드시 current_date 기반의 동적 날짜 표현을 사용해야 합니다.""",

    """[오답 패턴 3] CVR 분모 혼동 (노출수 대신 클릭수 사용)
CVR(전환율)의 분모는 반드시 클릭수여야 하며, 전체 노출수를 분모로 사용하면 안 됩니다.
잘못된 쿼리: ROUND(SUM(CAST(is_conversion AS INT)) * 100.0 / NULLIF(COUNT(*), 0), 2) AS cvr_percent
올바른 쿼리: ROUND(SUM(CAST(is_conversion AS INT)) * 100.0 / NULLIF(SUM(CAST(is_click AS INT)), 0), 2) AS cvr_percent
COUNT(*)는 전체 노출수이므로 CVR이 아닌 CTR의 분모가 됩니다.""",

    """[오답 패턴 4] Athena 미지원 OFFSET 사용 금지
Athena(Presto/Trino)는 OFFSET 구문을 지원하지 않으므로 N번째 순위 조회에 사용하면 안 됩니다.
잘못된 쿼리: ORDER BY click_count DESC LIMIT 1 OFFSET 1
올바른 쿼리: SELECT device_type FROM (
  SELECT device_type, ROW_NUMBER() OVER (ORDER BY click_count DESC) AS rn FROM ...
) WHERE rn = 2
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

## 5. Phase 4: n_results 상향

### 5.1 FR-PRO-07: n_results = 20

**수정 파일**: `src/query_pipeline.py` — `get_similar_question_sql()`

```python
# AS-IS
n_results = self.n_results_sql      # 기본값 10
if PHASE2_RAG_ENABLED:
    n_results = max(n_results, 10)  # PHASE2에서도 10

# TO-BE
n_results = self.n_results_sql      # 기본값 유지
if PHASE2_RAG_ENABLED:
    n_results = max(n_results, 20)  # DDL 역추적 후보 풀 확대 + Few-shot 증가
    # Phase 2에서 top_k 컷 제거 → n_results가 SQL 예제 수 직접 결정
```

환경변수 `N_RESULTS_SQL_PHASE2=20` 추가 (선택, docker-compose.local-e2e.yml):
```yaml
- N_RESULTS_SQL_PHASE2=20
```

---

## 6. 테스트 계획

### 6.1 정적 검증 (코드 리뷰)

| 체크 포인트 | 기준 |
|------------|------|
| `retrieve_v2()` 시그니처 | `schema_hint` 파라미터 없음 |
| `_extract_tables_from_qa_results()` 존재 | 신규 메서드 추가 확인 |
| DDL 벡터 검색 메서드 | 주석처리 상태 (`# def _retrieve_ddl...`) |
| `SchemaHint` 모델 | `models/rag.py`에서 제거 확인 |
| `schema_hint` 필드 | `PipelineContext`에서 제거 확인 |
| `DOCS_SCHEMA_MAPPER` | `seed_chromadb.py`에서 삭제 확인 |
| CTR/CVR Documentation | 퍼센트 형식, 주어+서술어 구조 |
| `DOCS_NEGATIVE_EXAMPLES` | 6개 항목, `train_documentation()`에 등록 |
| `_TABLE_DDL` 인라인 주석 | 주요 컬럼 `--` 주석 포함 |

### 6.2 동적 검증 (재시딩 + 실행)

```bash
# 1. 재시딩
docker exec capa-vanna-api python scripts/seed_chromadb.py

# 예상 로그
# ✓ [DOCS_NEGATIVE_EXAMPLES] 문서 6/6 학습 완료
# ✓ ChromaDB 시딩 완료!

# 2. 컬렉션 메트릭 확인
docker exec capa-vanna-api python -c "
import chromadb
c = chromadb.HttpClient(host='localhost', port=8000)
for name in ['sql-collection', 'documentation-collection']:
    print(name, c.get_collection(name).metadata)
"
# 예상: {'hnsw:space': 'cosine'}

# 3. DDL 역추적 동작 확인 (Docker 로그)
# 예상: RAG 검색 완료: DDL 1건 (tables=['ad_combined_log']), Docs N건, SQL 예제 20건
```

### 6.3 단위 테스트

```bash
docker exec capa-vanna-api pytest tests/unit/ -v
```

`test_multi_turn_recovery.py`의 `SCHEMA_MAPPER_ENABLED` mock 패치 제거 필요.

---

## 7. 구현 순서 (Do 단계)

```
[Phase 1]
  1. seed_chromadb.py — reset_collections() 추가
  2. query_pipeline.py — _ensure_cosine_collections() 추가
  3. query_pipeline.py — score 변환식 2개 메서드 수정
  4. rag_retriever.py — _retrieve_sql_examples_with_score() 주석 업데이트

[Phase 2]
  5. rag_retriever.py — retrieve_v2() 재구현 + _extract_tables_from_qa_results() 추가
  6. rag_retriever.py — DDL/Reranker/LLM필터 관련 메서드 주석처리
  7. rag_retriever.py — 모듈 상단 환경변수 제거
  8. query_pipeline.py — add_question_sql() tables metadata 추가
  9. query_pipeline.py — Reranker 초기화 주석처리, Step 3.5 제거, SCHEMA_MAPPER_ENABLED 제거
  10. models/rag.py — SchemaHint 제거, CandidateDocument 등 주석처리
  11. models/domain.py — SchemaHint import/schema_hint 필드 제거
  12. schema_mapper.py — 파일 삭제
  13. docker-compose.local-e2e.yml — SCHEMA_MAPPER_ENABLED 제거
  14. seed_chromadb.py — DDL 상수/시딩 제거, tables metadata 추가

[Phase 3]
  15. rag_retriever.py — _TABLE_DDL 인라인 주석 추가
  16. seed_chromadb.py — Documentation 문장형 변환 (7개 변수)
  17. seed_chromadb.py — DOCS_NEGATIVE_EXAMPLES 신설

[Phase 4]
  18. query_pipeline.py — n_results 20으로 상향
  19. 재시딩 실행 + 동적 검증
  20. pytest 실행
```

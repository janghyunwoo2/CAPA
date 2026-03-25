# RAG Retrieval Optimization — 설계 문서

- **Feature**: rag-retrieval-optimization
- **Phase**: Design
- **작성일**: 2026-03-24
- **작성자**: t1
- **관련 Plan**: `docs/t1/text-to-sql/07_rag-retrieval-optimization/01-plan/`

---

## 목차

1. [개요](#1-개요)
2. [아키텍처 (TO-BE)](#2-아키텍처-to-be)
3. [데이터 모델 설계](#3-데이터-모델-설계)
4. [모듈별 상세 설계](#4-모듈별-상세-설계)
5. [query_pipeline.py 수정 포인트](#5-query_pipelinepy-수정-포인트)
6. [환경변수 정의](#6-환경변수-정의)
7. [하위 호환성](#7-하위-호환성)
8. [테스트 계획](#8-테스트-계획)

---

## 1. 개요

### 1.1 목적

현재 Step 4 RAG 파이프라인에서 발생하는 4가지 결함(DEFECT-01~05)을 해결하여
SQL 생성 정확도를 개선한다.

| 결함 ID | 현상 | 영향 |
|---------|------|------|
| DEFECT-01 | DDL/Docs initial_score 1.0 고정 (ChromaDB distance 미반영) | Reranker 점수 품질 저하 |
| DEFECT-02 | DDL 벡터 검색이 테이블 무관 DDL을 포함 | LLM에 노이즈 컨텍스트 전달 |
| DEFECT-03 | 테이블 선택 근거 없음 (키워드→테이블 매핑 부재) | 엉뚱한 테이블 DDL이 컨텍스트에 포함 |
| DEFECT-04 | 벡터 검색으로는 ad_combined_log vs summary 구분 불가 | 집계/시간대 쿼리 오류 |
| DEFECT-05 | LLM 선별(Step 4-3) 항상 호출 (불필요한 API 비용) | Claude Haiku 불필요 호출 |

### 1.2 범위

Phase A~D 4단계 개선. 기존 Phase 1/2 인터페이스를 유지하는 점진적 추가.

### 1.3 관련 파일

| 파일 | 역할 | 변경 유형 |
|------|------|----------|
| `services/vanna-api/src/query_pipeline.py` | VannaAthena 클래스, Step 4 실행 | 수정 |
| `services/vanna-api/src/pipeline/rag_retriever.py` | RAGRetriever, retrieve_v2() | 수정 |
| `services/vanna-api/src/pipeline/reranker.py` | CrossEncoderReranker | 변경 없음 |
| `services/vanna-api/src/pipeline/keyword_extractor.py` | 키워드 추출 | 변경 없음 |
| `services/vanna-api/src/pipeline/schema_mapper.py` | 키워드→테이블 룰 매핑 | **신규 생성** |
| `services/vanna-api/src/models/domain.py` | RAGContext, PipelineContext | 수정 (SchemaHint 필드 추가) |
| `services/vanna-api/src/models/rag.py` | CandidateDocument 등 | 수정 (SchemaHint 모델 추가) |

---

## 2. 아키텍처 (TO-BE)

### 2.1 전체 Step 4 데이터 흐름

```
QueryPipeline.run()
  │
  ├─ Step 3: KeywordExtractor → ctx.keywords: list[str]
  │
  ├─ [신규] Step 3.5: SchemaMapper (SCHEMA_MAPPER_ENABLED=true)
  │     │  입력: ctx.keywords
  │     │  출력: schema_hint: SchemaHint
  │     │
  │     ├─ KEYWORD_TO_TABLE_MAP 룰 매핑
  │     │    is_conversion / conversion_value / CVR / ROAS
  │     │    → tables=["ad_combined_log_summary"], confidence=1.0, is_definitive=True
  │     │
  │     ├─ hour / 시간대 / 피크타임
  │     │    → tables=["ad_combined_log"], confidence=1.0, is_definitive=True
  │     │
  │     ├─ 일간 집계 키워드만 (날짜/CTR 등)
  │     │    → tables=["ad_combined_log_summary"], confidence=0.8, is_definitive=False
  │     │
  │     └─ 매핑 불가
  │          → tables=[], confidence=0.5, is_definitive=False
  │
  └─ Step 4: RAGRetriever.retrieve_v2(question, keywords, schema_hint)
        │
        ├─ Step 4-1: _retrieve_candidates(query, schema_hint)
        │     │
        │     ├─ DDL 검색
        │     │    ├─ [Phase C] schema_hint.is_definitive=True
        │     │    │    → _retrieve_ddl_optimized() (직접 주입, 벡터 검색 생략)
        │     │    │    → CandidateDocument(source="ddl", initial_score=1.0)
        │     │    └─ is_definitive=False or schema_hint=None
        │     │         → _retrieve_ddl_with_score() (Phase A: 실제 ChromaDB score)
        │     │         → CandidateDocument(source="ddl", initial_score=score)
        │     │
        │     ├─ Documentation 검색
        │     │    → _retrieve_documentation_with_score() (Phase A)
        │     │    → CandidateDocument(source="documentation", initial_score=score)
        │     │
        │     └─ SQL 예제 검색 (기존 유지)
        │          → _retrieve_sql_examples_with_score()
        │          → CandidateDocument(source="sql_example", initial_score=score)
        │
        ├─ Step 4-2: CrossEncoderReranker.rerank()
        │     top_k = 5 (schema_hint.is_definitive=True) / 7 (기본값)
        │
        └─ Step 4-3: _llm_filter() (Phase D: 조건부 실행)
              ├─ _should_skip_llm_filter(schema_hint)=True
              │    → candidates → RAGContext 직접 변환 (LLM 호출 없음)
              └─ _should_skip_llm_filter(schema_hint)=False
                   → 기존 Claude Haiku LLM 선별 (하위 호환)
```

### 2.2 AS-IS vs TO-BE 비교

| 항목 | AS-IS | TO-BE |
|------|-------|-------|
| DDL initial_score | 항상 1.0 고정 | ChromaDB distance 기반 실제 score |
| Docs initial_score | 항상 1.0 고정 | ChromaDB distance 기반 실제 score |
| 테이블 선택 | 없음 (벡터 검색에 의존) | SchemaMapper 룰 기반 확정 |
| DDL 검색 | 벡터 유사도 (테이블 무관) | 확정 시 직접 주입, 모호 시 벡터 |
| LLM 선별 | 항상 호출 | 테이블 확정 시 스킵 |
| Reranker top_k | 항상 7 | 확정 시 5, 모호 시 7 |

---

## 3. 데이터 모델 설계

### 3.1 SchemaHint (신규 — models/rag.py에 추가)

```python
# services/vanna-api/src/models/rag.py 에 추가

class SchemaHint(BaseModel):
    """Step 3.5 SchemaMapper 출력 — 키워드 기반 테이블/컬럼 힌트"""

    tables: list[str]       # 결정된 테이블 목록 (예: ["ad_combined_log_summary"])
    columns: list[str]      # 관련 컬럼 힌트 목록 (예: ["is_conversion", "conversion_value"])
    confidence: float       # 0.0~1.0 (룰 기반 확정=1.0, 벡터 기반=0.5~0.9)
    is_definitive: bool     # True=테이블 확정 (DDL 직접 주입 가능), False=모호
```

**confidence 기준:**

| 값 | 의미 |
|----|------|
| 1.0 | 룰 기반 확정 (is_conversion 포함, hour 파티션 필요 등) |
| 0.8 | 일간 집계 키워드만 있어 summary 선호 (강한 추론) |
| 0.5 | 키워드가 모호하거나 매핑 불가 |

### 3.2 CandidateDocument (기존 유지)

```python
# services/vanna-api/src/models/rag.py — 변경 없음

class CandidateDocument(BaseModel):
    text: str
    source: Literal["ddl", "documentation", "sql_example"]
    initial_score: float       # Phase A 이후 DDL/Docs도 실제 score 주입
    rerank_score: Optional[float] = None
```

`initial_score` 필드가 이미 존재하므로 모델 변경은 불필요하다.
Phase A 구현으로 DDL/Docs도 1.0 고정이 아닌 실제 ChromaDB score를 받게 된다.

### 3.3 PipelineContext (domain.py — schema_hint 필드 추가)

```python
# services/vanna-api/src/models/domain.py 의 PipelineContext에 추가

# Step 3.5 (신규)
schema_hint: Optional["SchemaHint"] = None
```

`from .rag import SchemaHint` import 추가 필요.

---

## 4. 모듈별 상세 설계

### 4.1 Phase A: VannaAthena score 오버라이드 (query_pipeline.py)

**목표**: DDL과 Documentation에도 ChromaDB distance 기반 실제 score를 반영한다.

#### 4.1.1 get_related_ddl_with_score()

Vanna `ChromaDB_VectorStore`의 DDL 컬렉션명은 내부적으로 `ddl_collection` 속성으로 노출된다
(`self.ddl_collection`). `get_related_ddl()`은 텍스트 리스트만 반환하므로
컬렉션을 직접 쿼리하여 distance를 추출한다.

```python
def get_related_ddl_with_score(
    self,
    question: str,
    n_results: Optional[int] = None,
) -> list[dict]:
    """DDL 후보를 ChromaDB distance 기반 score와 함께 반환.

    Returns:
        list of {"text": str, "score": float}
        score = 1 / (1 + distance)
    """
    try:
        n = n_results or self.n_results_ddl  # Vanna 기본 속성 활용
        results = self.ddl_collection.query(
            query_texts=[question],
            n_results=n,
            include=["documents", "distances"],
        )
        if not results or "documents" not in results:
            return []

        docs = results["documents"][0] if results["documents"] else []
        distances = results.get("distances", [[]])[0]

        return [
            {"text": doc, "score": 1.0 / (1.0 + dist)}
            for doc, dist in zip(docs, distances)
            if doc
        ]
    except Exception as e:
        logger.warning(f"DDL score 검색 실패, fallback: {e}")
        # fallback: 기존 텍스트 전용 메서드 사용, score=1.0 고정
        texts = self.get_related_ddl(question=question)
        return [{"text": t, "score": 1.0} for t in texts]
```

#### 4.1.2 get_related_documentation_with_score()

Documentation 컬렉션은 `self.documentation_collection` 속성으로 접근한다.

```python
def get_related_documentation_with_score(
    self,
    question: str,
    n_results: Optional[int] = None,
) -> list[dict]:
    """Documentation 후보를 ChromaDB distance 기반 score와 함께 반환.

    Returns:
        list of {"text": str, "score": float}
        score = 1 / (1 + distance)
    """
    try:
        n = n_results or self.n_results_documentation  # Vanna 기본 속성 활용
        results = self.documentation_collection.query(
            query_texts=[question],
            n_results=n,
            include=["documents", "distances"],
        )
        if not results or "documents" not in results:
            return []

        docs = results["documents"][0] if results["documents"] else []
        distances = results.get("distances", [[]])[0]

        return [
            {"text": doc, "score": 1.0 / (1.0 + dist)}
            for doc, dist in zip(docs, distances)
            if doc
        ]
    except Exception as e:
        logger.warning(f"Documentation score 검색 실패, fallback: {e}")
        texts = self.get_related_documentation(question=question)
        return [{"text": t, "score": 1.0} for t in texts]
```

**Vanna 내부 컬렉션 속성 확인 포인트:**
- `self.ddl_collection` : `ChromaDB_VectorStore.__init__`에서 `self.chroma_client.get_or_create_collection("ddl")`로 초기화
- `self.documentation_collection` : `self.chroma_client.get_or_create_collection("documentation")`로 초기화
- `self.n_results_ddl` : 기본값 10 (Vanna 설정)
- `self.n_results_documentation` : 기본값 10 (Vanna 설정)

구현 전 `vanna` 라이브러리 소스 (`vanna/chromadb/chromadb_vector.py`)에서
실제 속성명을 grep으로 재확인할 것.

---

### 4.2 Phase B: SchemaMapper 신규 모듈 (pipeline/schema_mapper.py)

**목표**: 추출된 키워드를 룰 기반으로 테이블/컬럼에 매핑하여 SchemaHint를 생성한다.

#### 4.2.1 KEYWORD_TO_TABLE_MAP 딕셔너리

```python
# 키워드 → (테이블 목록, 연관 컬럼 목록, 우선순위 가중치)
# 우선순위: summary_exclusive > log_exclusive > neutral
KEYWORD_TO_TABLE_MAP: dict[str, dict] = {
    # ---- summary 전용 (전환/ROAS/CPA/CVR) ----
    "is_conversion":        {"tables": ["ad_combined_log_summary"], "columns": ["is_conversion"], "weight": "summary_exclusive"},
    "전환":                 {"tables": ["ad_combined_log_summary"], "columns": ["is_conversion", "conversion_value"], "weight": "summary_exclusive"},
    "conversion_value":     {"tables": ["ad_combined_log_summary"], "columns": ["conversion_value"], "weight": "summary_exclusive"},
    "전환가치":             {"tables": ["ad_combined_log_summary"], "columns": ["conversion_value"], "weight": "summary_exclusive"},
    "conversion":           {"tables": ["ad_combined_log_summary"], "columns": ["is_conversion", "conversion_value"], "weight": "summary_exclusive"},
    "cvr":                  {"tables": ["ad_combined_log_summary"], "columns": ["is_conversion"], "weight": "summary_exclusive"},
    "전환율":               {"tables": ["ad_combined_log_summary"], "columns": ["is_conversion"], "weight": "summary_exclusive"},
    "roas":                 {"tables": ["ad_combined_log_summary"], "columns": ["conversion_value", "cost"], "weight": "summary_exclusive"},
    "광고수익률":           {"tables": ["ad_combined_log_summary"], "columns": ["conversion_value", "cost"], "weight": "summary_exclusive"},
    "cpa":                  {"tables": ["ad_combined_log_summary"], "columns": ["is_conversion", "cost"], "weight": "summary_exclusive"},
    "전환당비용":           {"tables": ["ad_combined_log_summary"], "columns": ["is_conversion", "cost"], "weight": "summary_exclusive"},
    "revenue":              {"tables": ["ad_combined_log_summary"], "columns": ["conversion_value"], "weight": "summary_exclusive"},
    "매출":                 {"tables": ["ad_combined_log_summary"], "columns": ["conversion_value"], "weight": "summary_exclusive"},

    # ---- log 전용 (시간대/hour 파티션) ----
    "hour":                 {"tables": ["ad_combined_log"], "columns": ["hour"], "weight": "log_exclusive"},
    "시간대":               {"tables": ["ad_combined_log"], "columns": ["hour"], "weight": "log_exclusive"},
    "시간별":               {"tables": ["ad_combined_log"], "columns": ["hour"], "weight": "log_exclusive"},
    "피크타임":             {"tables": ["ad_combined_log"], "columns": ["hour"], "weight": "log_exclusive"},
    "피크 시간":            {"tables": ["ad_combined_log"], "columns": ["hour"], "weight": "log_exclusive"},
    "hourly":               {"tables": ["ad_combined_log"], "columns": ["hour"], "weight": "log_exclusive"},

    # ---- summary 선호 (일간 집계 지표) ----
    "ctr":                  {"tables": ["ad_combined_log_summary"], "columns": ["click_count", "impression_count"], "weight": "neutral"},
    "클릭률":               {"tables": ["ad_combined_log_summary"], "columns": ["click_count", "impression_count"], "weight": "neutral"},
    "cpc":                  {"tables": ["ad_combined_log_summary"], "columns": ["cost", "click_count"], "weight": "neutral"},
    "클릭당비용":           {"tables": ["ad_combined_log_summary"], "columns": ["cost", "click_count"], "weight": "neutral"},
    "cost":                 {"tables": ["ad_combined_log_summary"], "columns": ["cost"], "weight": "neutral"},
    "광고비":               {"tables": ["ad_combined_log_summary"], "columns": ["cost"], "weight": "neutral"},
    "impression":           {"tables": ["ad_combined_log_summary"], "columns": ["impression_count"], "weight": "neutral"},
    "노출":                 {"tables": ["ad_combined_log_summary"], "columns": ["impression_count"], "weight": "neutral"},
    "노출수":               {"tables": ["ad_combined_log_summary"], "columns": ["impression_count"], "weight": "neutral"},
    "click":                {"tables": ["ad_combined_log_summary"], "columns": ["click_count"], "weight": "neutral"},
    "클릭":                 {"tables": ["ad_combined_log_summary"], "columns": ["click_count"], "weight": "neutral"},
    "클릭수":               {"tables": ["ad_combined_log_summary"], "columns": ["click_count"], "weight": "neutral"},
    "campaign_id":          {"tables": ["ad_combined_log_summary", "ad_combined_log"], "columns": ["campaign_id"], "weight": "neutral"},
    "캠페인":               {"tables": ["ad_combined_log_summary", "ad_combined_log"], "columns": ["campaign_id"], "weight": "neutral"},
    "device_type":          {"tables": ["ad_combined_log_summary", "ad_combined_log"], "columns": ["device_type"], "weight": "neutral"},
    "디바이스":             {"tables": ["ad_combined_log_summary", "ad_combined_log"], "columns": ["device_type"], "weight": "neutral"},
    "food_category":        {"tables": ["ad_combined_log_summary", "ad_combined_log"], "columns": ["food_category"], "weight": "neutral"},
    "카테고리":             {"tables": ["ad_combined_log_summary", "ad_combined_log"], "columns": ["food_category"], "weight": "neutral"},
    "platform":             {"tables": ["ad_combined_log_summary", "ad_combined_log"], "columns": ["platform"], "weight": "neutral"},
    "플랫폼":               {"tables": ["ad_combined_log_summary", "ad_combined_log"], "columns": ["platform"], "weight": "neutral"},
}
```

#### 4.2.2 SchemaMapper 클래스

```python
# services/vanna-api/src/pipeline/schema_mapper.py

import logging
import os
from ..models.rag import SchemaHint

logger = logging.getLogger(__name__)

SCHEMA_MAPPER_ENABLED: bool = os.getenv("SCHEMA_MAPPER_ENABLED", "true").lower() == "true"

# 위 KEYWORD_TO_TABLE_MAP 딕셔너리 정의 (생략)

class SchemaMapper:
    """Step 3.5 — 추출 키워드를 룰 기반으로 테이블/컬럼에 매핑."""

    def map(self, keywords: list[str]) -> SchemaHint:
        """키워드 리스트를 받아 SchemaHint를 반환.

        Args:
            keywords: KeywordExtractor가 추출한 키워드 목록

        Returns:
            SchemaHint
        """
        if not keywords:
            return SchemaHint(
                tables=[], columns=[], confidence=0.5, is_definitive=False
            )

        has_summary_exclusive = False
        has_log_exclusive = False
        collected_tables: set[str] = set()
        collected_columns: set[str] = set()

        keywords_lower = [kw.lower() for kw in keywords]

        for kw in keywords_lower:
            mapping = KEYWORD_TO_TABLE_MAP.get(kw)
            if mapping is None:
                continue
            weight = mapping["weight"]
            if weight == "summary_exclusive":
                has_summary_exclusive = True
            elif weight == "log_exclusive":
                has_log_exclusive = True
            collected_tables.update(mapping["tables"])
            collected_columns.update(mapping["columns"])

        return self._decide(
            has_summary_exclusive=has_summary_exclusive,
            has_log_exclusive=has_log_exclusive,
            collected_tables=collected_tables,
            collected_columns=collected_columns,
        )

    def _decide(
        self,
        has_summary_exclusive: bool,
        has_log_exclusive: bool,
        collected_tables: set[str],
        collected_columns: set[str],
    ) -> SchemaHint:
        """테이블 결정 우선순위 알고리즘."""

        # 규칙 1: 전환/ROAS/CPA 키워드 → summary 확정 (최고 우선순위)
        if has_summary_exclusive and not has_log_exclusive:
            logger.debug("SchemaMapper: summary 확정 (전환/ROAS 키워드)")
            return SchemaHint(
                tables=["ad_combined_log_summary"],
                columns=sorted(
                    c for c in collected_columns
                    if c in self._summary_columns()
                ),
                confidence=1.0,
                is_definitive=True,
            )

        # 규칙 2: hour/시간대 키워드 → log 확정
        if has_log_exclusive and not has_summary_exclusive:
            logger.debug("SchemaMapper: log 확정 (시간대 키워드)")
            return SchemaHint(
                tables=["ad_combined_log"],
                columns=sorted(
                    c for c in collected_columns
                    if c in self._log_columns()
                ),
                confidence=1.0,
                is_definitive=True,
            )

        # 규칙 3: 두 exclusive 모두 없고 neutral 키워드만 → summary 선호
        if collected_tables and "ad_combined_log_summary" in collected_tables:
            logger.debug("SchemaMapper: summary 선호 (일간 지표 키워드)")
            return SchemaHint(
                tables=["ad_combined_log_summary"],
                columns=sorted(collected_columns),
                confidence=0.8,
                is_definitive=False,
            )

        # 규칙 4: 충돌하거나 매핑 불가
        logger.debug("SchemaMapper: 모호 — 벡터 검색 fallback")
        return SchemaHint(
            tables=sorted(collected_tables) if collected_tables else [],
            columns=sorted(collected_columns),
            confidence=0.5,
            is_definitive=False,
        )

    @staticmethod
    def _summary_columns() -> set[str]:
        return {
            "is_conversion", "conversion_value", "cost",
            "click_count", "impression_count",
        }

    @staticmethod
    def _log_columns() -> set[str]:
        return {
            "hour", "campaign_id", "device_type",
            "food_category", "platform",
        }
```

---

### 4.3 Phase C: RAGRetriever DDL 최적화 (rag_retriever.py)

**목표**: Schema Hint가 테이블을 확정했을 때 DDL을 벡터 검색 없이 직접 주입한다.

#### 4.3.1 retrieve_v2() 시그니처 변경

```python
async def retrieve_v2(
    self,
    question: str,
    keywords: list[str],
    schema_hint: Optional["SchemaHint"] = None,   # 신규 파라미터
) -> RAGContext:
```

`from ..models.rag import SchemaHint` import 추가.

#### 4.3.2 _retrieve_candidates() 시그니처 변경

```python
def _retrieve_candidates(
    self,
    query: str,
    schema_hint: Optional["SchemaHint"] = None,   # 신규 파라미터
) -> list[CandidateDocument]:
```

#### 4.3.3 _retrieve_ddl_optimized() 신규 메서드

테이블 이름으로 ChromaDB DDL 컬렉션을 직접 필터링하여 주입한다.

```python
def _retrieve_ddl_optimized(
    self,
    schema_hint: "SchemaHint",
) -> list[CandidateDocument]:
    """Schema Hint 확정 시 DDL을 ChromaDB where 필터로 직접 조회.

    ChromaDB where 필터로 테이블명이 포함된 DDL document를 조회한다.
    조회 실패 시 빈 리스트를 반환하고 상위에서 벡터 검색으로 fallback.

    Args:
        schema_hint: is_definitive=True인 SchemaHint

    Returns:
        list[CandidateDocument] — source="ddl", initial_score=1.0
    """
    results: list[CandidateDocument] = []
    try:
        ddl_collection = self._vanna.ddl_collection
        for table_name in schema_hint.tables:
            # ChromaDB where 필터: document 텍스트에 테이블명 포함 여부 확인
            # ChromaDB 0.4+에서는 $contains 연산자 사용
            query_result = ddl_collection.query(
                query_texts=[table_name],
                n_results=3,            # 테이블당 최대 3개 (중복 DDL 고려)
                include=["documents"],
            )
            docs = query_result.get("documents", [[]])[0] if query_result else []
            for doc in docs:
                if doc and table_name.lower() in doc.lower():
                    results.append(
                        CandidateDocument(
                            text=doc,
                            source="ddl",
                            initial_score=1.0,  # 직접 주입: 최고 신뢰도
                        )
                    )
        if results:
            logger.info(
                f"DDL 직접 주입: {len(results)}건 "
                f"(테이블: {schema_hint.tables})"
            )
        else:
            logger.warning(
                f"DDL 직접 주입 실패 (빈 결과) — 벡터 검색 fallback: {schema_hint.tables}"
            )
    except Exception as e:
        logger.warning(f"DDL 직접 주입 예외 — 벡터 검색 fallback: {e}")
    return results
```

#### 4.3.4 _retrieve_candidates() 내부 로직 (DDL 분기)

```python
def _retrieve_candidates(
    self,
    query: str,
    schema_hint: Optional["SchemaHint"] = None,
) -> list[CandidateDocument]:
    candidates: list[CandidateDocument] = []

    # DDL 검색 — Phase C 분기
    if schema_hint is not None and schema_hint.is_definitive:
        ddl_docs = self._retrieve_ddl_optimized(schema_hint)
        if not ddl_docs:
            # 직접 주입 실패 시 벡터 검색 fallback
            ddl_docs = self._retrieve_ddl_with_score(query)
        candidates.extend(ddl_docs)
    else:
        candidates.extend(self._retrieve_ddl_with_score(query))

    # Documentation 검색 — Phase A score 반영
    for item in self._retrieve_documentation_with_score(query):
        candidates.append(
            CandidateDocument(
                text=item["text"],
                source="documentation",
                initial_score=item["score"],
            )
        )

    # SQL 예제 검색 — 기존 유지
    for item in self._retrieve_sql_examples_with_score(query):
        candidates.append(
            CandidateDocument(
                text=item["text"],
                source="sql_example",
                initial_score=item["score"],
            )
        )

    return candidates
```

#### 4.3.5 _retrieve_ddl_with_score() 신규 헬퍼 (Phase A)

```python
def _retrieve_ddl_with_score(self, query: str) -> list[CandidateDocument]:
    """Phase A: DDL 벡터 검색 — ChromaDB distance 기반 score 반영."""
    try:
        items = self._vanna.get_related_ddl_with_score(question=query)
        return [
            CandidateDocument(
                text=item["text"],
                source="ddl",
                initial_score=item["score"],
            )
            for item in items
        ]
    except Exception as e:
        logger.warning(f"DDL score 검색 실패: {e}")
        return []
```

#### 4.3.6 _retrieve_documentation_with_score() 신규 헬퍼 (Phase A)

```python
def _retrieve_documentation_with_score(self, query: str) -> list[dict]:
    """Phase A: Documentation 벡터 검색 — ChromaDB distance 기반 score 반영."""
    try:
        return self._vanna.get_related_documentation_with_score(question=query)
    except Exception as e:
        logger.warning(f"Documentation score 검색 실패: {e}")
        return []
```

---

### 4.4 Phase D: LLM 선별 조건부 실행 (rag_retriever.py)

**목표**: Schema Mapper가 테이블을 확정했을 때 Claude Haiku LLM 선별 호출을 스킵한다.

#### 4.4.1 _should_skip_llm_filter() 신규 메서드

```python
def _should_skip_llm_filter(
    self,
    schema_hint: Optional["SchemaHint"],
) -> bool:
    """LLM 선별 단계 스킵 여부 결정.

    조건: Schema Mapper가 테이블을 확정(is_definitive=True)한 경우.
    환경변수 LLM_FILTER_ENABLED=false이면 schema_hint 무관하게 항상 스킵.

    Returns:
        True → _llm_filter() 호출 없이 candidates → RAGContext 직접 변환
        False → 기존 LLM 선별 수행
    """
    if not LLM_FILTER_ENABLED:
        return True
    if schema_hint is not None and schema_hint.is_definitive:
        logger.info("LLM 선별 스킵: Schema Mapper 테이블 확정")
        return True
    return False
```

#### 4.4.2 retrieve_v2() top_k 동적 조정

```python
async def retrieve_v2(
    self,
    question: str,
    keywords: list[str],
    schema_hint: Optional["SchemaHint"] = None,
) -> RAGContext:
    search_query = question
    if keywords:
        search_query = f"{question} {' '.join(keywords)}"

    try:
        # Step 4-1: 벡터 유사도 검색 (Phase C 분기 포함)
        candidates = self._retrieve_candidates(search_query, schema_hint)
        if not candidates:
            return RAGContext()

        # Step 4-2: Reranker — top_k 동적 조정
        effective_top_k = (
            RERANKER_TOP_K_DEFINITIVE          # 5 (schema 확정 시)
            if schema_hint is not None and schema_hint.is_definitive
            else RERANKER_TOP_K                # 7 (기본값)
        )
        if self._reranker is not None:
            reranked = await self._reranker.rerank(
                query=search_query,
                candidates=candidates,
                top_k=effective_top_k,
            )
        else:
            logger.warning("Reranker 미설정 — Step 4-2 스킵")
            reranked = candidates[:effective_top_k]

        # Step 4-3: LLM 선별 (Phase D 조건부)
        if self._should_skip_llm_filter(schema_hint):
            return self._candidates_to_rag_context(reranked)
        return self._llm_filter(question=search_query, candidates=reranked)

    except Exception as e:
        logger.error(f"RAG 3단계 검색 실패: {e}, 빈 컨텍스트로 진행")
        return RAGContext()
```

**신규 환경변수 상수 (rag_retriever.py 상단):**

```python
LLM_FILTER_ENABLED: bool = os.getenv("LLM_FILTER_ENABLED", "true").lower() == "true"
RERANKER_TOP_K: int = int(os.getenv("RERANKER_TOP_K", "7"))           # 기존 유지
RERANKER_TOP_K_DEFINITIVE: int = int(os.getenv("RERANKER_TOP_K", "5"))  # Schema 확정 시
```

> 주의: `RERANKER_TOP_K_DEFINITIVE`는 별도 환경변수가 아니라 `RERANKER_TOP_K` 기본값을 5로 하드코딩하여
> Schema 확정 시 오버라이드한다. 운영 중 동적 조정이 필요하면 별도 환경변수(`RERANKER_TOP_K_DEFINITIVE`)로
> 분리할 수 있다.

---

## 5. query_pipeline.py 수정 포인트

### 5.1 환경변수 선언 추가 (라인 59~63 부근)

```python
# 기존
PHASE2_RAG_ENABLED = os.getenv("PHASE2_RAG_ENABLED", "false").lower() == "true"
MULTI_TURN_ENABLED = os.getenv("MULTI_TURN_ENABLED", "false").lower() == "true"
SELF_CORRECTION_ENABLED = os.getenv("SELF_CORRECTION_ENABLED", "false").lower() == "true"
MAX_CORRECTION_ATTEMPTS = int(os.getenv("MAX_CORRECTION_ATTEMPTS", "3"))

# 추가
SCHEMA_MAPPER_ENABLED: bool = os.getenv("SCHEMA_MAPPER_ENABLED", "true").lower() == "true"
```

### 5.2 SchemaMapper import 추가 (QueryPipeline.__init__ 상단)

`QueryPipeline.__init__` 내부에서 조건부 import:

```python
# __init__ 메서드 내부 — 기존 Phase 2 조건부 import 블록 하단에 추가
if SCHEMA_MAPPER_ENABLED:
    from .pipeline.schema_mapper import SchemaMapper
    self._schema_mapper = SchemaMapper()
else:
    self._schema_mapper = None
```

### 5.3 Step 3.5 삽입 (라인 338~351 사이)

현재 Step 3 ~ Step 4 코드:

```python
# 현재 (라인 337~351)
# Step 3: 키워드 추출
ctx.keywords = self._keyword_extractor.extract(ctx.refined_question)
logger.info(f"Step 3 키워드: {ctx.keywords}")

# Step 4: RAG 검색 (Phase 2: PHASE2_RAG_ENABLED=true 시 3단계 RAG 사용)
if PHASE2_RAG_ENABLED:
    ctx.rag_context = await self._rag_retriever.retrieve_v2(
        question=ctx.refined_question,
        keywords=ctx.keywords,
    )
else:
    ctx.rag_context = self._rag_retriever.retrieve(
        question=ctx.refined_question,
        keywords=ctx.keywords,
    )
```

수정 후:

```python
# Step 3: 키워드 추출
ctx.keywords = self._keyword_extractor.extract(ctx.refined_question)
logger.info(f"Step 3 키워드: {ctx.keywords}")

# Step 3.5: Schema Mapper (SCHEMA_MAPPER_ENABLED=true 시)
if SCHEMA_MAPPER_ENABLED and self._schema_mapper is not None:
    ctx.schema_hint = self._schema_mapper.map(ctx.keywords)
    logger.info(
        f"Step 3.5 Schema Hint: tables={ctx.schema_hint.tables}, "
        f"confidence={ctx.schema_hint.confidence}, "
        f"is_definitive={ctx.schema_hint.is_definitive}"
    )
else:
    ctx.schema_hint = None

# Step 4: RAG 검색 (Phase 2: PHASE2_RAG_ENABLED=true 시 3단계 RAG 사용)
if PHASE2_RAG_ENABLED:
    ctx.rag_context = await self._rag_retriever.retrieve_v2(
        question=ctx.refined_question,
        keywords=ctx.keywords,
        schema_hint=ctx.schema_hint,    # Phase B/C/D 연동
    )
else:
    ctx.rag_context = self._rag_retriever.retrieve(
        question=ctx.refined_question,
        keywords=ctx.keywords,
    )
```

---

## 6. 환경변수 정의

| 변수명 | 기본값 | 설명 | 영향 Phase |
|--------|--------|------|-----------|
| `PHASE2_RAG_ENABLED` | `false` | 3단계 RAG 전체 활성화 | 전체 |
| `SCHEMA_MAPPER_ENABLED` | `true` | Step 3.5 Schema Mapper 활성화 | B, C, D |
| `LLM_FILTER_ENABLED` | `true` | Step 4-3 LLM 선별 활성화 | D |
| `RERANKER_TOP_K` | `7` | Reranker 상위 K개 (Schema 확정 시 코드에서 5로 오버라이드) | D |

**주의**: `SCHEMA_MAPPER_ENABLED=true`이더라도 `PHASE2_RAG_ENABLED=false`이면
Phase B/C/D는 동작하지 않는다 (`retrieve_v2`가 호출되지 않으므로).
Schema Hint는 `retrieve_v2` 호출 경로에서만 효과가 있다.

---

## 7. 하위 호환성

### 7.1 PHASE2_RAG_ENABLED=false (Phase 1 경로)

- `retrieve()` 메서드 호출 경로는 변경 없음
- Schema Mapper / DDL 최적화 / LLM 선별 조건부 — 모두 적용 안 됨
- 완전 하위 호환

### 7.2 SCHEMA_MAPPER_ENABLED=false

- `ctx.schema_hint = None` 으로 설정
- `retrieve_v2()` 호출 시 `schema_hint=None` 전달
- `_retrieve_candidates()`에서 기존 벡터 검색 경로 유지
- `_should_skip_llm_filter(None)` → `False` → LLM 선별 유지

### 7.3 DDL 직접 주입 실패 시 Graceful Degradation

`_retrieve_ddl_optimized()` 내부에서 빈 리스트 반환 시
`_retrieve_candidates()`가 `_retrieve_ddl_with_score()` 벡터 검색으로 자동 fallback.

```python
# _retrieve_candidates() 분기
ddl_docs = self._retrieve_ddl_optimized(schema_hint)
if not ddl_docs:
    # 직접 주입 실패 → 벡터 검색 fallback
    ddl_docs = self._retrieve_ddl_with_score(query)
candidates.extend(ddl_docs)
```

### 7.4 SchemaMapper 예외 시 Graceful Degradation

`SchemaMapper.map()`이 예외를 던지면 `ctx.schema_hint = None`으로 처리.
`query_pipeline.py` Step 3.5에 try-except 래핑:

```python
if SCHEMA_MAPPER_ENABLED and self._schema_mapper is not None:
    try:
        ctx.schema_hint = self._schema_mapper.map(ctx.keywords)
    except Exception as e:
        logger.warning(f"Step 3.5 Schema Mapper 실패, 스킵: {e}")
        ctx.schema_hint = None
```

---

## 8. 테스트 계획

### 8.1 Phase A: DDL/Docs score 범위 검증

```python
# test_schema_score_range.py
def test_get_related_ddl_with_score_returns_valid_range():
    """DDL score가 0~1 범위인지 확인."""
    results = vanna.get_related_ddl_with_score(question="CTR 보여줘")
    for item in results:
        assert 0.0 <= item["score"] <= 1.0
        assert isinstance(item["text"], str)
        assert len(item["text"]) > 0

def test_get_related_documentation_with_score_returns_valid_range():
    """Documentation score가 0~1 범위인지 확인."""
    results = vanna.get_related_documentation_with_score(question="CTR 보여줘")
    for item in results:
        assert 0.0 <= item["score"] <= 1.0
```

### 8.2 Phase B: SchemaMapper 단위 테스트 (10개 이상)

```python
# test_schema_mapper.py
mapper = SchemaMapper()

def test_map_conversion_keywords_returns_summary_definitive():
    hint = mapper.map(["is_conversion", "CVR"])
    assert hint.tables == ["ad_combined_log_summary"]
    assert hint.confidence == 1.0
    assert hint.is_definitive is True

def test_map_roas_returns_summary_definitive():
    hint = mapper.map(["ROAS", "광고비"])
    assert hint.tables == ["ad_combined_log_summary"]
    assert hint.is_definitive is True

def test_map_hour_keywords_returns_log_definitive():
    hint = mapper.map(["시간대", "피크타임"])
    assert hint.tables == ["ad_combined_log"]
    assert hint.confidence == 1.0
    assert hint.is_definitive is True

def test_map_hourly_keyword_returns_log_definitive():
    hint = mapper.map(["hourly"])
    assert hint.tables == ["ad_combined_log"]
    assert hint.is_definitive is True

def test_map_ctr_returns_summary_preferred():
    hint = mapper.map(["CTR", "캠페인"])
    assert "ad_combined_log_summary" in hint.tables
    assert hint.confidence == 0.8
    assert hint.is_definitive is False

def test_map_empty_keywords_returns_low_confidence():
    hint = mapper.map([])
    assert hint.confidence == 0.5
    assert hint.is_definitive is False

def test_map_unknown_keywords_returns_low_confidence():
    hint = mapper.map(["알수없는키워드", "xyz"])
    assert hint.confidence == 0.5
    assert hint.is_definitive is False

def test_map_conflict_summary_and_log_exclusive():
    """summary + log 전용 키워드 충돌 시 모호로 처리."""
    # is_conversion(summary_exclusive) + hour(log_exclusive) 동시 존재
    hint = mapper.map(["is_conversion", "hour"])
    # 두 exclusive가 모두 있으면 규칙 1,2 불충족 → 규칙 4(모호)
    assert hint.is_definitive is False

def test_map_cpa_returns_summary_definitive():
    hint = mapper.map(["CPA", "전환당비용"])
    assert hint.tables == ["ad_combined_log_summary"]
    assert hint.is_definitive is True

def test_map_columns_collected_correctly():
    hint = mapper.map(["ROAS"])
    assert "conversion_value" in hint.columns
    assert "cost" in hint.columns
```

### 8.3 Phase C: DDL 직접 주입 검증

```python
def test_retrieve_candidates_with_definitive_hint_uses_direct_ddl():
    """Schema Hint 확정 시 DDL이 1개(직접 주입)만 포함되는지 확인."""
    hint = SchemaHint(
        tables=["ad_combined_log_summary"],
        columns=["is_conversion"],
        confidence=1.0,
        is_definitive=True,
    )
    candidates = retriever._retrieve_candidates(
        query="전환율 보여줘", schema_hint=hint
    )
    ddl_candidates = [c for c in candidates if c.source == "ddl"]
    # 직접 주입된 DDL만 포함 (벡터 검색 결과 없음)
    for ddl in ddl_candidates:
        assert "ad_combined_log_summary" in ddl.text.lower()
```

### 8.4 Phase D: LLM filter 호출 여부 검증

```python
from unittest.mock import MagicMock, AsyncMock

async def test_retrieve_v2_skips_llm_filter_when_definitive():
    """Schema Hint 확정 시 LLM filter가 호출되지 않는지 확인."""
    hint = SchemaHint(
        tables=["ad_combined_log_summary"],
        columns=[],
        confidence=1.0,
        is_definitive=True,
    )
    retriever._llm_filter = MagicMock(
        wraps=retriever._llm_filter
    )
    await retriever.retrieve_v2(
        question="전환율 보여줘",
        keywords=["전환"],
        schema_hint=hint,
    )
    retriever._llm_filter.assert_not_called()

async def test_retrieve_v2_calls_llm_filter_when_not_definitive():
    """Schema Hint 모호 시 LLM filter가 호출되는지 확인."""
    hint = SchemaHint(
        tables=["ad_combined_log_summary"],
        columns=[],
        confidence=0.8,
        is_definitive=False,
    )
    retriever._llm_filter = MagicMock(return_value=RAGContext())
    await retriever.retrieve_v2(
        question="CTR 보여줘",
        keywords=["CTR"],
        schema_hint=hint,
    )
    retriever._llm_filter.assert_called_once()
```

---

*문서 끝*

# [Plan] 동적 DDL 주입 + SchemaMapper 제거

## Executive Summary

| 항목 | 내용 |
|------|------|
| **Feature** | dynamic-ddl-injection |
| **작성일** | 2026-03-25 |
| **담당** | t1 |
| **참고 문서** | `services/vanna-api/src/pipeline/rag_retriever.py`, `schema_mapper.py` |

### Value Delivered (4관점)

| 관점 | 내용 |
|------|------|
| **Problem** | DDL 벡터 검색(`get_related_ddl`)은 NLU 임베딩 모델(`ko-sroberta`)이 SQL DDL 구문을 자연어와 다르게 임베딩하여 잘못된 테이블 DDL이 선택될 위험. SchemaMapper는 키워드 규칙 기반으로 신규 패턴에 취약하고 Dynamic DDL과 역할 중복. DDL 정의가 `seed_chromadb.py`와 `_TABLE_DDL` dict 두 곳에 분산 |
| **Solution** | QA 예제 시딩 시 `metadata.tables`에 참조 테이블 저장 → 검색 시 QA metadata에서 테이블 역추적 → `_TABLE_DDL` dict에서 DDL 직접 주입. SchemaMapper 제거, `seed_chromadb.py` DDL 시딩 제거 |
| **Function UX Effect** | DDL 오선택으로 인한 SQL 오류 감소, 테이블 확장 시 QA 시딩만으로 자동 대응, 파이프라인 인터페이스 단순화 |
| **Core Value** | DDL 단일 소스를 `_TABLE_DDL` dict으로 통일. QA 예제 시딩 품질이 DDL 주입 정확도를 결정하는 단일 구조로 일원화 |

---

## 1. 배경 및 목적

### 1.1 현황

DDL이 두 곳에 중복 존재하고, DDL 결정 경로도 두 갈래로 혼재한다.

**DDL 중복:**

| 위치 | 용도 |
|------|------|
| `seed_chromadb.py` `DDL_AD_COMBINED_LOG` 등 | ChromaDB `ddl_collection`에 저장 → 벡터 검색용 |
| `rag_retriever.py` `_TABLE_DDL` dict | is_definitive=True 시 직접 주입용 |

**DDL 결정 경로:**

```
경로 A (SchemaMapper 확정, is_definitive=True)
  Step 3.5 SchemaMapper → is_definitive=True
  → _TABLE_DDL dict 직접 조회 ✅

경로 B (SchemaMapper 모호, is_definitive=False)
  Step 3.5 SchemaMapper → is_definitive=False
  → get_related_ddl_with_score() → ChromaDB 벡터 검색 ⚠️
```

**경로 B의 문제:**
- `ko-sroberta-multitask`는 한국어 자연어 문장 유사도 모델
- DDL(`CREATE EXTERNAL TABLE ...`)은 SQL 구문 → 자연어 임베딩 공간과 괴리
- 사용자 질문과 DDL의 임베딩 거리 불안정 → 잘못된 테이블 DDL 선택 가능

**SchemaMapper의 한계:**
- 키워드 규칙 hardcoded → 신규 질문 패턴, 오타, 동의어에 취약
- Dynamic DDL Injection이 같은 역할을 더 견고하게 대체 가능

### 1.2 개선 목표

| 항목 | 현재 | 목표 |
|------|------|------|
| DDL 결정 방법 | 키워드 규칙 or 벡터 검색 | QA 예제 메타데이터 역추적 |
| DDL 단일 소스 | seed_chromadb.py + `_TABLE_DDL` dict 중복 | `_TABLE_DDL` dict 단일화 |
| SchemaMapper | 활성화 | 제거 |
| DDL 벡터 검색 | is_definitive=False 시 사용 | 완전 제거 |
| seed_chromadb.py DDL 시딩 | 있음 | 제거 (Phase 1 미사용) |

---

## 2. 아키텍처 설계

### 2.1 3단계 플로우

```
[Step 1 — 시딩]  seed_chromadb.py
  add_question_sql(question, sql, tables=["ad_combined_log"])
    → ChromaDB sql_collection metadata: {"sql": sql, "tables": "['ad_combined_log']"}
  ※ DDL 시딩(train(ddl=...)) 제거 — ddl_collection 더 이상 사용 안 함

[Step 2 — 검색]  retrieve_v2(question, keywords)
  가장 먼저 get_similar_question_sql() 호출 → 유사 QA 예제 Top-K 추출

[Step 3 — DDL 역추적 + 동적 주입]
  Top-K QA 예제 metadata["tables"] 파싱 → set으로 중복 제거
  → _TABLE_DDL[table] (Python 프로세스 메모리 dict) 에서 DDL 원본 조회
  → RAGContext.ddl_context에 적재
  → sql_generator.py가 <ddl>...</ddl> 블록으로 포맷하여 LLM user_content에 주입
  ※ fallback: tables 파싱 불가 시 _TABLE_DDL 전체 주입 (2개 테이블)
```

### 2.2 LLM 주입 경로 (기존 인프라 활용)

`sql_generator.py` 기존 코드가 이미 처리:

```python
# RAGContext.ddl_context → <ddl> 블록 → user_content
if rag_context.ddl_context:
    sections.append("<ddl>\n" + "\n".join(rag_context.ddl_context) + "\n</ddl>")
rag_block = "<rag_context>\n" + "\n".join(sections) + "\n</rag_context>\n"
# user_content에 rag_block 포함 → Anthropic API로 전달
```

`RAGContext.ddl_context`에 DDL 텍스트를 넣는 것만으로 LLM 주입 완료 — 추가 수정 불필요.

### 2.3 환경변수 변경

| 변수 | 변경 | 기본값 |
|------|------|--------|
| `DYNAMIC_DDL_INJECTION_ENABLED` | **신규** | `true` |
| `SCHEMA_MAPPER_ENABLED` | **제거** | — |

---

## 3. 구현 계획

### 3.1 수정/삭제 파일 목록

| # | 파일 | 유형 | 변경 내용 |
|---|------|------|----------|
| ① | `src/query_pipeline.py` | 수정 | `add_question_sql()` tables metadata 추가, Step 3.5 블록 제거, `SCHEMA_MAPPER_ENABLED` 제거, `DYNAMIC_DDL_INJECTION_ENABLED` 추가 |
| ② | `src/pipeline/rag_retriever.py` | 수정 | `retrieve_v2()` schema_hint 파라미터 제거, `_retrieve_candidates()` DDL 역추적 로직 교체, `_extract_tables_from_qa_results()` 신규, `_retrieve_ddl_with_score()` / `_retrieve_ddl()` 제거 |
| ③ | `src/pipeline/schema_mapper.py` | **삭제** | 전체 제거 |
| ④ | `src/models/rag.py` | 수정 | `SchemaHint` 모델 제거 |
| ⑤ | `src/models/domain.py` | 수정 | `from .rag import SchemaHint` import 및 `ctx.schema_hint` 필드 제거 |
| ⑥ | `scripts/seed_chromadb.py` | 수정 | `train(ddl=...)` 호출 및 DDL 상수 제거, `add_question_sql()` 에 `tables` 파라미터 추가 |
| ⑦ | `docker-compose.local-e2e.yml` | 수정 | `SCHEMA_MAPPER_ENABLED` 제거, `DYNAMIC_DDL_INJECTION_ENABLED=true` 추가 |

### 3.2 ① `query_pipeline.py` 핵심 변경

```python
# 환경변수
DYNAMIC_DDL_INJECTION_ENABLED = os.getenv("DYNAMIC_DDL_INJECTION_ENABLED", "true").lower() == "true"
# 제거: SCHEMA_MAPPER_ENABLED

# add_question_sql() 오버라이드 — tables 메타데이터 추가
def add_question_sql(self, question: str, sql: str, tables: list[str] | None = None, **kwargs) -> str:
    id = deterministic_uuid(question + sql) + "-sql"
    metadata: dict = {"sql": sql}
    if tables:
        metadata["tables"] = str(tables)  # ChromaDB는 str 값만 허용
    self.sql_collection.add(documents=question, metadatas=[metadata], ids=[id])
    return id

# __init__(), run() — Step 3.5 SchemaMapper 블록 전체 제거
# retrieve_v2() 호출 — schema_hint 파라미터 제거
ctx.rag_context = await self._rag_retriever.retrieve_v2(
    question=ctx.refined_question,
    keywords=ctx.keywords,
)
```

### 3.3 ② `rag_retriever.py` 핵심 변경

```python
# 환경변수 추가
DYNAMIC_DDL_INJECTION_ENABLED: bool = os.getenv("DYNAMIC_DDL_INJECTION_ENABLED", "true").lower() == "true"

# retrieve_v2() — schema_hint 파라미터 제거
async def retrieve_v2(self, question: str, keywords: list[str]) -> RAGContext: ...

# _retrieve_candidates() — DDL 역추적으로 교체
def _retrieve_candidates(self, query: str) -> list[CandidateDocument]:
    candidates: list[CandidateDocument] = []

    # Step 2: 유사 QA 예제 검색
    qa_results = self._vanna.get_similar_question_sql(question=query)

    # Step 3: DDL 역추적 + 동적 주입
    tables = self._extract_tables_from_qa_results(qa_results)
    if not tables:
        tables = set(_TABLE_DDL.keys())  # fallback: 전체 주입
    for table in tables:
        ddl_text = _TABLE_DDL.get(table)
        if ddl_text:
            candidates.append(CandidateDocument(text=ddl_text, source="ddl", initial_score=1.0))

    # Documentation 벡터 검색 (유지)
    for item in self._retrieve_documentation_with_score(query):
        candidates.append(CandidateDocument(text=item["text"], source="documentation", initial_score=item["score"]))

    # SQL 예제 추가 (유지)
    for item in self._retrieve_sql_examples_with_score(query):
        candidates.append(CandidateDocument(text=item["text"], source="sql_example", initial_score=item["score"]))

    return candidates

# 신규 메서드
def _extract_tables_from_qa_results(self, qa_results: list) -> set[str]:
    """QA 예제 metadata["tables"] 파싱 → 테이블 이름 집합 반환."""
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

# 제거 메서드
# - _retrieve_ddl_with_score()
# - _retrieve_ddl()
# - _should_skip_llm_filter() 내 schema_hint 의존 분기 정리
```

### 3.4 ⑥ `seed_chromadb.py` 핵심 변경

```python
# 제거: DDL 상수 및 시딩 호출
# DDL_AD_COMBINED_LOG = "..." → 삭제
# DDL_AD_COMBINED_LOG_SUMMARY = "..." → 삭제
# vanna.train(ddl=DDL_AD_COMBINED_LOG) → 삭제
# vanna.train(ddl=DDL_AD_COMBINED_LOG_SUMMARY) → 삭제

# 수정: add_question_sql 호출에 tables 파라미터 추가
vanna.add_question_sql(
    question="어제 CTR은 얼마인가요?",
    sql="SELECT ...",
    tables=["ad_combined_log"],
)
vanna.add_question_sql(
    question="지난달 전환율(CVR)을 알려주세요",
    sql="SELECT ...",
    tables=["ad_combined_log_summary"],
)
```

---

## 4. 안전성 분석

| 시나리오 | 동작 |
|---------|------|
| QA metadata에 `tables` 있음 | 역추적 → 해당 DDL만 주입 ✅ |
| QA metadata에 `tables` 없음 (구버전 시딩) | fallback → `_TABLE_DDL` 전체 주입 |
| `_TABLE_DDL`에 없는 테이블명 | 조용히 스킵, 나머지 DDL 주입 |
| `DYNAMIC_DDL_INJECTION_ENABLED=false` | 기존 DDL 벡터 검색 경로 유지 (하위 호환) |
| `PHASE2_RAG_ENABLED=false` | `retrieve_v2()` 미호출 → 영향 없음 |

---

## 5. 성공 기준

| 항목 | 기준 | 검증 방법 |
|------|------|---------|
| DDL 정확도 | 질문 관련 테이블 DDL만 RAGContext에 포함 | Docker 로그 RAGContext 확인 |
| SchemaMapper 제거 | Step 3.5 로그 없음, `schema_mapper.py` 미존재 | 로그 + 파일 확인 |
| DDL 시딩 제거 | `ddl_collection` count = 0 | ChromaDB 컬렉션 확인 |
| fallback 동작 | tables 없는 QA → 전체 DDL 주입 | 단위 테스트 |
| 기존 단위 테스트 PASS | pytest 전체 통과 | pytest 실행 |

---

## 6. 구현 순서

```
1. [⑥] seed_chromadb.py — DDL 시딩 제거, add_question_sql에 tables 추가
2. [①] query_pipeline.py — add_question_sql 오버라이드 tables metadata 저장
3. [②] rag_retriever.py — _extract_tables_from_qa_results() 신규
4. [②] rag_retriever.py — _retrieve_candidates() DDL 역추적 로직 교체
5. [②] rag_retriever.py — retrieve_v2() schema_hint 파라미터 제거
6. [②] rag_retriever.py — _retrieve_ddl_with_score(), _retrieve_ddl() 제거
7. [①] query_pipeline.py — Step 3.5 SchemaMapper 블록 제거
8. [④] models/rag.py — SchemaHint 모델 제거
9. [⑤] models/domain.py — SchemaHint import 및 schema_hint 필드 제거
10. [③] schema_mapper.py 파일 삭제
11. [⑦] docker-compose.local-e2e.yml — 환경변수 업데이트
12. [검증] ChromaDB 재시딩 후 Slack 질문 테스트
```

---

## 7. 연관 문서

| 문서 | 경로 |
|------|------|
| RAG 검색 최적화 설계 | `docs/t1/text-to-sql/07_rag-retrieval-optimization/` |
| Reranker 비활성화 | `docs/t1/text-to-sql/09_reranker-deactivation/` |
| RAG 시딩 품질 | `docs/t1/text-to-sql/10_rag-seeding-quality/` |
| rag_retriever | `services/vanna-api/src/pipeline/rag_retriever.py` |
| query_pipeline | `services/vanna-api/src/query_pipeline.py` |
| schema_mapper | `services/vanna-api/src/pipeline/schema_mapper.py` |

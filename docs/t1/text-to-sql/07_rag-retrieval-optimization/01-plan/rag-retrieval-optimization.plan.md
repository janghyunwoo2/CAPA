# RAG Retrieval Optimization Plan

## Executive Summary

| 관점 | 내용 |
|------|------|
| **Problem** | 현재 RAG 파이프라인이 키워드 기반 테이블/컬럼 매핑 없이 벡터 유사도만으로 후보를 수집하며, DDL/Docs에 `initial_score=1.0` 고정값을 부여하여 Reranker 입력이 편향됨 |
| **Solution** | 키워드→스키마 직접 매핑 도입, DDL/Docs 유사도 점수 실측 반영, 후보 풀 구성 전략 재설계로 RAG 3단계 파이프라인의 검색 정밀도를 근본적으로 개선 |
| **Function UX Effect** | 질문에 언급된 테이블/컬럼만 정확히 RAG 컨텍스트에 포함되어, LLM이 불필요한 DDL 노이즈 없이 정확한 SQL을 생성 |
| **Core Value** | RAG 검색 품질 향상 → SQL 정확도(Exec accuracy) 직접 개선, 프롬프트/시딩에 의존하지 않는 구조적 해결 |

---

## 1. 배경 및 문제 정의

### 1.1 현재 상황

06_sql-accuracy-tuning에서 프롬프트 강화(Phase A), RAG 시딩 재설계(Phase B), Self-Correction(Phase C), 평가 스크립트(Phase D)를 완료했으나, **RAG 검색 자체의 구조적 결함**이 해결되지 않았다.

아무리 프롬프트 엔지니어링과 시딩을 잘 하더라도, RAG가 **무엇을 가져오느냐**에 따라 SQL 정확도가 결정된다.

### 1.2 발견된 5대 구조적 결함

| ID | 결함 | 심각도 | 영향 |
|----|------|--------|------|
| **DEFECT-01** | DDL/Docs `initial_score=1.0` 고정 | Critical | Reranker 입력 편향 — DDL이 실제 관련도와 무관하게 높은 점수 |
| **DEFECT-02** | DDL이 테이블 전체 단위로 검색 | Critical | 30+ 컬럼 DDL 전체가 컨텍스트에 들어가 LLM 토큰 낭비 및 노이즈 |
| **DEFECT-03** | 키워드→테이블/컬럼 매핑 미연동 | Critical | 키워드 추출 후 검색 쿼리 확장에만 사용, 실제 스키마 선택에 미활용 |
| **DEFECT-04** | Vanna 기본 메서드 개수 제어 불가 | Medium | `get_related_ddl/documentation`은 항상 ~5개 고정, 동적 조절 불가 |
| **DEFECT-05** | LLM 선별 단계(Step 4-3) 과잉 | Low | Reranker top_k=7 이후 LLM이 또 필터링 → API 비용 + 지연 시간 증가 |

### 1.3 현재 데이터 흐름 (AS-IS)

```
질문: "어제 CTR 보여줘"
  ↓
Step 3: KeywordExtractor → ["CTR", "어제"]
  ↓
Step 4-1: 벡터 검색 (질문 + 키워드 결합)
  ├─ DDL: get_related_ddl() → ~5개 (score=1.0 고정)     ← DEFECT-01, 04
  ├─ Docs: get_related_documentation() → ~5개 (score=1.0 고정) ← DEFECT-01, 04
  └─ SQL: get_similar_question_sql() → 10개 (실제 score)
  총 ~20개 후보 (DDL 전체 테이블 포함)                      ← DEFECT-02
  ↓
Step 4-2: Reranker (jina-reranker-v2) → top_k=7
  ※ DDL이 score=1.0이라 편향 가능                          ← DEFECT-01
  ↓
Step 4-3: LLM 선별 (Claude Haiku) → 최종 선택              ← DEFECT-05
  ↓
RAGContext → SQLGenerator
  ※ 키워드가 스키마 매핑에 미활용                            ← DEFECT-03
```

### 1.4 목표 데이터 흐름 (TO-BE)

```
질문: "어제 CTR 보여줘"
  ↓
Step 3: KeywordExtractor → ["CTR", "어제"]
  ↓
Step 4-0 (NEW): Schema Mapper
  ├─ 키워드 "CTR" → 필요 컬럼: is_click, COUNT(*)
  ├─ 키워드 "어제" → 파티션: year, month, day (date_add -1)
  └─ 테이블 결정: ad_combined_log_summary (일간 분석, 전환 불필요)
  ↓
Step 4-1: 벡터 검색 (개선)
  ├─ DDL: Schema Mapper가 선택한 테이블 DDL만 (실제 score 반영)
  ├─ Docs: 관련 Documentation만 (실제 score 반영)
  └─ SQL: 유사 QA 예제 (실제 score)
  ↓
Step 4-2: Reranker → top_k=5 (모든 후보가 실제 score 보유)
  ↓
RAGContext → SQLGenerator (LLM 선별 단계 제거 또는 선택적)
```

---

## 2. 개선 범위 및 Phase 구성

### Phase A: DDL/Docs 유사도 점수 실측 반영 (DEFECT-01 해결)

**목표**: DDL과 Documentation 검색 시 ChromaDB 실제 distance를 score로 변환하여 반영

**수정 파일**:

| 파일 | 수정 내용 |
|------|----------|
| `src/query_pipeline.py` | `get_related_ddl()`, `get_related_documentation()` 오버라이드 — ChromaDB `distances` 반환 |
| `src/pipeline/rag_retriever.py` | `_retrieve_ddl()`, `_retrieve_documentation()` — score 포함 dict 반환으로 변경 |

**상세 작업**:
1. `VannaAthena` 클래스에 `get_related_ddl_with_score()` 메서드 추가
   - Vanna 내부 `ddl_collection.query()` 직접 호출
   - `distances`를 `score = 1/(1+distance)`로 변환
   - `[{"text": ddl_text, "score": float}]` 형태 반환
2. `get_related_documentation_with_score()` 동일 패턴 추가
3. `rag_retriever.py`의 `_retrieve_candidates()` 수정
   - `initial_score=1.0` 고정 → 실제 ChromaDB score 사용

**검증 기준**:
- DDL/Docs의 `initial_score`가 0~1 범위의 실제 유사도 값
- Reranker 입력 시 DDL score가 질문과의 관련도에 비례

---

### Phase B: 키워드→스키마 매핑 모듈 신설 (DEFECT-03 해결)

**목표**: 키워드 추출 결과를 활용하여 필요한 테이블/컬럼을 사전에 결정

**신규 파일**:

| 파일 | 역할 |
|------|------|
| `src/pipeline/schema_mapper.py` | 키워드 → 테이블/컬럼 매핑 로직 |

**수정 파일**:

| 파일 | 수정 내용 |
|------|----------|
| `src/query_pipeline.py` | Step 4 전에 Schema Mapper 호출 삽입 |
| `src/pipeline/rag_retriever.py` | `retrieve_v2()`에 `schema_hint` 파라미터 추가 |
| `src/models/domain.py` | `SchemaHint` 데이터 모델 추가 |

**상세 설계**:

```python
# schema_mapper.py 핵심 구조
KEYWORD_TO_TABLE_MAP = {
    # 전환 관련 키워드 → summary 테이블 필수
    "CVR": {"table": "ad_combined_log_summary", "columns": ["is_click", "is_conversion"]},
    "ROAS": {"table": "ad_combined_log_summary", "columns": ["conversion_value", "cost_per_impression", "cost_per_click"]},
    "전환": {"table": "ad_combined_log_summary", "columns": ["is_conversion", "conversion_value"]},
    # 시간대 분석 → log 테이블 필수
    "시간대": {"table": "ad_combined_log", "columns": ["hour"]},
    "피크타임": {"table": "ad_combined_log", "columns": ["hour"]},
    # 범용 키워드 → 둘 다 가능
    "CTR": {"table": None, "columns": ["is_click"]},
    "노출수": {"table": None, "columns": []},
    ...
}
```

**매핑 전략**:
1. **룰 기반 매핑** (1차): `KEYWORD_TO_TABLE_MAP` 딕셔너리로 즉시 매핑
2. **컬럼 존재 확인** (2차): 매핑된 컬럼이 실제 테이블에 존재하는지 DDL 기반 검증
3. **테이블 결정 로직**:
   - `conversion_*` 또는 `is_conversion` 필요 → `ad_combined_log_summary` 강제
   - `hour` 파티션 필요 → `ad_combined_log` 강제
   - 그 외 일간 분석 → `ad_combined_log_summary` 선호

**검증 기준**:
- "어제 CTR 보여줘" → `SchemaHint(tables=["ad_combined_log_summary"], columns=["is_click"])`
- "시간대별 클릭 패턴" → `SchemaHint(tables=["ad_combined_log"], columns=["hour", "is_click"])`
- "지난달 ROAS" → `SchemaHint(tables=["ad_combined_log_summary"], columns=["conversion_value", "cost_per_impression", "cost_per_click"])`

---

### Phase C: DDL 검색 최적화 — 테이블 단위 → 관련 DDL만 (DEFECT-02, 04 해결)

**목표**: Schema Mapper 결과를 활용하여 필요한 테이블 DDL만 RAG 컨텍스트에 포함

**수정 파일**:

| 파일 | 수정 내용 |
|------|----------|
| `src/pipeline/rag_retriever.py` | `_retrieve_ddl()` → Schema Hint 기반 필터링 |
| `src/query_pipeline.py` | DDL 컬렉션 직접 접근으로 `n_results` 제어 |

**상세 작업**:
1. Schema Mapper가 테이블을 결정한 경우:
   - 해당 테이블 DDL만 직접 주입 (벡터 검색 생략)
   - score=1.0 (확정적 선택이므로 최고 점수 정당)
2. Schema Mapper가 테이블을 결정 못한 경우:
   - 기존 벡터 검색 유지 (fallback)
   - 단, 실제 distance score 반영 (Phase A)
3. DDL 컬렉션에 `n_results` 파라미터 전달
   - Vanna 기본 메서드 대신 직접 `ddl_collection.query()` 호출

**검증 기준**:
- "어제 CTR 보여줘" → DDL 1개만 포함 (`ad_combined_log_summary`)
- "시간대별 분석" → DDL 1개만 포함 (`ad_combined_log`)
- 모호한 질문 → DDL 2개 모두 포함 (fallback)

---

### Phase D: 후보 풀 구성 전략 재설계 + LLM 선별 최적화 (DEFECT-05 해결)

**목표**: Reranker 후 LLM 선별 단계를 조건부 실행으로 변경, 후보 풀 비율 최적화

**수정 파일**:

| 파일 | 수정 내용 |
|------|----------|
| `src/pipeline/rag_retriever.py` | `retrieve_v2()` 후보 풀 비율 조정, LLM 선별 조건부 실행 |

**후보 풀 구성 전략**:

| AS-IS | TO-BE | 근거 |
|-------|-------|------|
| DDL ~5개 (score=1.0) | DDL 1~2개 (Schema Mapper 결정) | 필요한 테이블만 |
| Docs ~5개 (score=1.0) | Docs ~3개 (실제 score) | 관련 비즈니스 규칙만 |
| SQL 10개 (실제 score) | SQL 10개 (실제 score) | 유지 |
| 총 ~20개 → Reranker top_k=7 → LLM | 총 ~15개 → Reranker top_k=5 | 노이즈 감소 |

**LLM 선별 조건부 실행**:
- Schema Mapper가 테이블을 확정한 경우: LLM 선별 **생략** (Reranker 결과 직접 사용)
- Schema Mapper가 모호한 경우: LLM 선별 **실행** (기존 로직)
- 환경변수 `LLM_FILTER_ENABLED` (기본값: `true`)로 토글

**검증 기준**:
- Schema Mapper 확정 시: API 호출 1회 감소 (Haiku 호출 제거)
- 전체 Step 4 지연 시간 20% 이상 감소

---

## 3. 구현 일정

| Day | Phase | 작업 내용 | 산출물 |
|-----|-------|----------|--------|
| Day 1 | **Phase A** | DDL/Docs 유사도 점수 실측 반영 | `query_pipeline.py`, `rag_retriever.py` 수정 |
| Day 1~2 | **Phase B** | Schema Mapper 모듈 신설 | `schema_mapper.py` 신규, `domain.py` 수정 |
| Day 2 | **Phase C** | DDL 검색 최적화 (Schema Hint 연동) | `rag_retriever.py`, `query_pipeline.py` 수정 |
| Day 3 | **Phase D** | 후보 풀 재설계 + LLM 선별 최적화 | `rag_retriever.py` 수정 |
| Day 3 | **테스트** | 단위 테스트 + 통합 테스트 | 테스트 코드, 테스트 결과 문서 |
| Day 4 | **평가** | Exec/EM 정답률 측정 (before/after 비교) | 평가 보고서 |

**총 예상 기간**: 4일

---

## 4. 수정 대상 파일 요약

| 파일 | Phase | 변경 유형 | 주요 수정 |
|------|-------|----------|----------|
| `src/pipeline/schema_mapper.py` | B | **신규** | 키워드→테이블/컬럼 매핑 모듈 |
| `src/models/domain.py` | B | 수정 | `SchemaHint` 데이터 모델 추가 |
| `src/query_pipeline.py` | A, B, C | 수정 | DDL/Docs score 오버라이드, Schema Mapper 호출 삽입 |
| `src/pipeline/rag_retriever.py` | A, C, D | 수정 | score 반영, Schema Hint 기반 검색, 후보 풀 재설계 |
| `src/pipeline/keyword_extractor.py` | - | 변경 없음 | 기존 유지 |
| `src/pipeline/reranker.py` | - | 변경 없음 | 기존 유지 |
| `src/pipeline/sql_generator.py` | - | 변경 없음 | 기존 유지 |
| `scripts/seed_chromadb.py` | - | 변경 없음 | 기존 55개 QA + 26개 Docs 유지 |

---

## 5. 위험 요소 및 대응

| 위험 | 가능성 | 영향 | 대응 |
|------|--------|------|------|
| Schema Mapper 룰 누락 (새로운 키워드 패턴) | 높음 | 중간 | fallback으로 기존 벡터 검색 유지, 점진적 룰 추가 |
| DDL 컬렉션 직접 접근 시 Vanna 내부 API 변경 | 낮음 | 높음 | Vanna 버전 고정, 오버라이드 메서드로 격리 |
| Reranker top_k 축소로 관련 문서 누락 | 중간 | 높음 | before/after 평가로 검증, 환경변수로 롤백 가능 |
| LLM 선별 제거 시 노이즈 증가 | 중간 | 중간 | 조건부 실행 (Schema Mapper 확정 시에만 제거) |

---

## 6. 성공 지표

| 지표 | 현재 (AS-IS) | 목표 (TO-BE) | 측정 방법 |
|------|-------------|-------------|----------|
| DDL 정확도 | 불명 (score 미기록) | 질문 관련 테이블만 포함 | RAG 로그 분석 |
| Reranker 입력 품질 | DDL/Docs score=1.0 고정 | 실제 유사도 0.3~0.9 분포 | CandidateDocument 로그 |
| Step 4 지연 시간 | ~10초 (Reranker+LLM) | ~6초 (LLM 선별 조건부 제거) | 타이머 로그 |
| Exec accuracy | 측정 예정 (0%→?) | Phase A~D 적용 후 +10%p 이상 개선 | `run_evaluation.py` |

---

## 7. Phase 간 의존성

```
Phase A (DDL/Docs score 실측)
  ↓ (선행 조건)
Phase B (Schema Mapper)  ←── 독립 개발 가능하나, Phase A의 score가 있으면 fallback 품질 향상
  ↓ (선행 조건)
Phase C (DDL 검색 최적화)  ←── Phase B의 SchemaHint 필수
  ↓ (선행 조건)
Phase D (후보 풀 재설계)  ←── Phase A~C 완료 후 전체 통합
```

**권장 구현 순서**: A → B → C → D (순차적, 각 Phase 완료 후 단위 테스트)

---

## 8. 하위 호환성

- `PHASE2_RAG_ENABLED=false`: 기존 Phase 1 로직 변경 없음
- `PHASE2_RAG_ENABLED=true`: Phase A~D 적용
- Schema Mapper 실패 시: 기존 벡터 검색으로 fallback (graceful degradation)
- 환경변수 `SCHEMA_MAPPER_ENABLED` (기본값: `true`)로 토글 가능

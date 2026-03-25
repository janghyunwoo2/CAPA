# Retrieval Config Optimization Plan

## Executive Summary

| 관점 | 내용 |
|------|------|
| **Problem** | ChromaDB 컬렉션이 기본 L2 거리 지표로 생성되어 코사인 유사도에 최적화된 `ko-sroberta-multitask` 임베딩과 불일치하며, QA 예제 검색 개수(Top-K=10)가 낮아 Few-shot 효과가 제한됨 |
| **Solution** | 컬렉션 생성 시 `{"hnsw:space": "cosine"}` 강제 적용 + score 변환식 L2→cosine 교체 + n_results를 10→20으로 상향하여 검색 품질과 Few-shot 프롬프팅 효과를 동시에 개선 |
| **Function UX Effect** | 임베딩 모델 특성에 맞는 거리 지표로 유사 QA 검색 정확도 향상, 더 많은 관련 예제로 SQL 생성 품질 개선 |
| **Core Value** | 모델-지표 정합성 확보 → 검색 품질 향상 → SQL 정확도(Exec accuracy) 개선, 토큰 최적화(Dynamic DDL injection)의 여유분을 Few-shot 확대에 활용 |

---

## 1. 배경 및 문제 정의

### 1.1 현재 상황

`07_rag-retrieval-optimization`에서 Schema Mapper 기반 DDL 동적 주입과 ChromaDB distance→score 변환을 완료했다. 이후 `11_dynamic-ddl-injection`에서 필요한 DDL만 선택적으로 주입하여 프롬프트 토큰을 최적화했다.

그러나 **ChromaDB 컬렉션 자체의 거리 지표**가 임베딩 모델 특성과 맞지 않는 문제가 여전히 남아 있다.

### 1.2 발견된 2가지 설정 결함

| ID | 결함 | 심각도 | 영향 |
|----|------|--------|------|
| **CFG-01** | ChromaDB 컬렉션 거리 지표 기본값 L2 사용 | Critical | `ko-sroberta-multitask`는 코사인 유사도 최적화 모델 — L2로 검색하면 의미적으로 가까운 벡터를 멀다고 평가할 수 있음 |
| **CFG-02** | QA 예제 Top-K = 10으로 제한 | Medium | Dynamic DDL injection 완료로 토큰 여유가 생겼으나 Few-shot 예제 수는 그대로 — 검색 품질 개선 여지 미활용 |

### 1.3 임베딩 모델과 거리 지표 불일치 (CFG-01 상세)

```
jhgan/ko-sroberta-multitask
  - 학습 방식: Sentence-BERT (코사인 유사도 기반 학습)
  - 출력 벡터: L2-normalized (단위 벡터)
  - 최적 거리 지표: cosine similarity = 내적 = 코사인 거리

ChromaDB 기본값: L2 (유클리드 거리)
  - 정규화된 벡터에서 L2^2 = 2 - 2*cos(θ)
  - 수학적으로 cosine과 단조 관계지만, HNSW 인덱스 구조상
    L2 최적화된 경로 탐색이 cosine 최적 이웃을 놓칠 수 있음
  - score 변환식 1/(1+d)가 L2 기준으로 설계되어 cosine 범위(0~1)와 불일치
```

### 1.4 목표 상태 (TO-BE)

```
ChromaDB 컬렉션 메타데이터
  {"hnsw:space": "cosine"}  ← 3개 컬렉션 모두 적용
  (sql-collection, ddl-collection, documentation-collection)

Score 변환식 (cosine distance 기준)
  cosine distance ∈ [0, 1]  (정규화 벡터 기준)
  score = 1 - distance      (= cosine similarity 직접 반환)

n_results (QA 예제)
  AS-IS: PHASE2=true → max(n_results, 10) = 10개
  TO-BE: PHASE2=true → max(n_results, 20) = 20개
         기본값(n_results_sql): 10 → 15로 상향
```

---

## 2. 개선 범위 및 Phase 구성

### Phase A: ChromaDB 컬렉션 거리 지표 변경 (CFG-01 해결)

**목표**: 3개 ChromaDB 컬렉션 모두 `{"hnsw:space": "cosine"}`으로 재생성

**기술 제약사항**:
- ChromaDB는 컬렉션 생성 시 `hnsw:space`를 지정하며, **생성 후 변경 불가**
- 기존 L2 컬렉션은 **삭제 후 재생성** 필요
- 재생성 후 반드시 `seed_chromadb.py`로 재시딩 수행

**수정 파일**:

| 파일 | 수정 내용 |
|------|----------|
| `src/query_pipeline.py` | `_VannaAthena.__init__` 에서 ChromaDB `VannaConfig`에 cosine 메타데이터 전달 방식 확인 및 오버라이드 |
| `scripts/seed_chromadb.py` | 시딩 시작 전 기존 컬렉션 삭제(`delete_collection`) + cosine 메트릭으로 재생성 로직 추가 |

**상세 작업**:

1. ChromaDB_VectorStore의 컬렉션 초기화 방식 분석
   - Vanna의 `ChromaDB_VectorStore`가 내부적으로 `get_or_create_collection()` 호출 여부 확인
   - cosine 메타데이터를 주입할 수 있는 진입점 파악
2. `_VannaAthena.__init__` 또는 `config` 딕셔너리를 통해 cosine 지표 강제 적용
3. `seed_chromadb.py`에 컬렉션 초기화 단계 추가:
   ```python
   # 기존 컬렉션 삭제 (L2 메트릭 제거)
   for collection_name in ["sql-collection", "ddl-collection", "documentation-collection"]:
       try:
           chroma_client.delete_collection(collection_name)
       except Exception:
           pass
   # 이후 VannaAthena 인스턴스 생성 → cosine 메트릭으로 재생성
   ```

**검증 기준**:
- `chroma_client.get_collection("sql-collection").metadata` → `{"hnsw:space": "cosine"}` 확인
- 재시딩 후 QA 예제 개수 유지 (SQL: ~55개, Docs: ~26개)

---

### Phase B: Score 변환식 업데이트 (CFG-01 연계)

**목표**: L2 기반 `1/(1+distance)` → cosine 기반 `1-distance` 로 교체

**cosine distance 범위**:
- 정규화된 벡터(ko-sroberta 출력): cosine distance ∈ [0, 1]
- distance=0: 동일 벡터 (완전 유사) → score=1.0
- distance=1: 직교 벡터 (무관) → score=0.0

**수정 파일**:

| 파일 | 수정 내용 |
|------|----------|
| `src/query_pipeline.py` | `get_similar_question_sql()`, `get_related_ddl_with_score()`, `get_related_documentation_with_score()` 내 score 계산식 |
| `src/pipeline/rag_retriever.py` | `_retrieve_sql_examples_with_score()` 주석 업데이트 |

**수정 내용**:
```python
# AS-IS (L2 distance 기준)
"score": 1.0 / (1.0 + dist)

# TO-BE (cosine distance 기준)
"score": max(0.0, 1.0 - dist)   # cosine distance = 1 - cosine_similarity
```

**주의**: `max(0.0, ...)` 처리 — 부동소수점 오차로 distance가 1.0을 미세하게 초과할 수 있음

---

### Phase C: n_results 상향 (CFG-02 해결)

**목표**: QA 예제 검색 개수를 10개 → 20개로 상향

**배경**: `11_dynamic-ddl-injection`에서 필요한 DDL만 선택 주입하여 프롬프트 토큰을 절감했다. 확보된 토큰 여유를 Few-shot 예제 확대에 활용한다.

**수정 파일**:

| 파일 | 수정 내용 |
|------|----------|
| `src/query_pipeline.py` | `get_similar_question_sql()` 내 Phase2 n_results 상향 |

**수정 내용**:
```python
# AS-IS
n_results = self.n_results_sql          # 기본값 10
if PHASE2_RAG_ENABLED:
    n_results = max(n_results, 10)      # PHASE2에서도 여전히 10

# TO-BE
n_results = self.n_results_sql          # 기본값 유지
if PHASE2_RAG_ENABLED:
    n_results = max(n_results, 20)      # PHASE2에서 후보 풀 확대
```

**환경변수 추가 (선택)**:
- `N_RESULTS_SQL_PHASE2` (기본값: `20`) — 상향 수치를 환경변수로 관리하여 롤백 용이

---

## 3. 구현 일정

| Day | Phase | 작업 내용 | 산출물 |
|-----|-------|----------|--------|
| Day 1 | **Phase A** | ChromaDB Vanna 내부 구조 분석 + cosine 지표 적용 | `query_pipeline.py` 수정, `seed_chromadb.py` 수정 |
| Day 1 | **Phase B** | Score 변환식 L2→cosine 교체 | `query_pipeline.py` 수정 |
| Day 1 | **Phase C** | n_results 상향 | `query_pipeline.py` 수정 |
| Day 1~2 | **테스트** | 컬렉션 재생성 + 재시딩 + 단위 테스트 | 테스트 코드, 결과 문서 |
| Day 2 | **평가** | before/after 검색 품질 비교 | 평가 로그 |

**총 예상 기간**: 2일

---

## 4. 수정 대상 파일 요약

| 파일 | Phase | 변경 유형 | 주요 수정 |
|------|-------|----------|----------|
| `src/query_pipeline.py` | A, B, C | 수정 | cosine 지표 적용, score 변환식 교체, n_results 상향 |
| `scripts/seed_chromadb.py` | A | 수정 | 컬렉션 삭제 후 재생성 로직 추가 |
| `src/pipeline/rag_retriever.py` | B | 수정 (주석) | cosine score 공식 주석 업데이트 |
| `docker-compose.local-e2e.yml` | C | 수정 (선택) | `N_RESULTS_SQL_PHASE2=20` 환경변수 추가 |

---

## 5. 위험 요소 및 대응

| 위험 | 가능성 | 영향 | 대응 |
|------|--------|------|------|
| Vanna ChromaDB_VectorStore가 `hnsw:space` 주입을 지원하지 않음 | 중간 | 높음 | `__init__` 후 컬렉션 직접 교체 오버라이드로 우회 |
| 기존 컬렉션 삭제 시 운영 환경 데이터 손실 | 낮음 | 높음 | 로컬/E2E 환경에서만 `seed_chromadb.py` 실행, EKS는 PVC 볼륨 백업 후 진행 |
| cosine distance가 1.0 초과 (부동소수점 오차) | 낮음 | 낮음 | `max(0.0, 1.0 - dist)` 방어 처리 |
| n_results=20 증가로 Reranker 처리 시간 증가 | 중간 | 중간 | `RERANKER_ENABLED=false` 환경에서 별도 측정, 필요시 `N_RESULTS_SQL_PHASE2` 환경변수로 롤백 |

---

## 6. 성공 지표

| 지표 | AS-IS | TO-BE | 측정 방법 |
|------|-------|-------|----------|
| 컬렉션 거리 지표 | L2 (기본값) | cosine | `collection.metadata["hnsw:space"] == "cosine"` |
| Score 범위 | 0~0.5 (L2 변환) | 0~1.0 (cosine 직접) | 검색 로그 score 분포 |
| n_results (PHASE2) | 10 | 20 | `get_similar_question_sql()` 반환 개수 |
| 유사 QA top-1 유사도 | 미측정 | cosine 기준 0.7 이상 목표 | 검색 로그 |

---

## 7. 하위 호환성

- `PHASE2_RAG_ENABLED=false`: n_results 변경 무관, Phase 1 로직 그대로
- `PHASE2_RAG_ENABLED=true`: cosine 지표 + n_results=20 적용
- 컬렉션 재생성은 `seed_chromadb.py` 실행 시에만 발생 — 자동 재시작으로 컬렉션이 삭제되지는 않음
- EKS 환경: PVC 마운트된 ChromaDB 볼륨은 별도 마이그레이션 절차 필요 (본 Plan 범위 외)

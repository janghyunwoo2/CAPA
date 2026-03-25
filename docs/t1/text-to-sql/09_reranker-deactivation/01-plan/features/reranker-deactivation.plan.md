# [Plan] Reranker 비활성화

## Executive Summary

| 항목 | 내용 |
|------|------|
| **Feature** | reranker-deactivation |
| **FR ID** | FR-RD-01 |
| **작성일** | 2026-03-25 |
| **담당** | t1 |
| **참고 문서** | `docs/t1/text-to-sql/07_rag-retrieval-optimization/` |

### Value Delivered (4관점)

| 관점 | 내용 |
|------|------|
| **Problem** | `jina-reranker-v2-base-multilingual`이 CPU 환경에서 22건 후보 재평가에 57초 소요 — 전체 파이프라인 71초의 80% 차지. 데이터셋 123개(DDL 2 + Docs 61 + SQL 60) 소규모에서 bi-encoder(ko-sroberta) 평균 유사도 0.88로 이미 충분하며, FAIL 11건 중 Reranker로 개선 가능한 건수 0건 |
| **Solution** | `RERANKER_ENABLED=false` 환경변수 추가, `query_pipeline.py` 조건 분기, `docker-compose.local-e2e.yml` 비활성화 설정 |
| **Function UX Effect** | 파이프라인 응답시간 71초 → 15초 이하 예상, Slack 타임아웃 위험 해소 |
| **Core Value** | 소규모 정제 데이터셋에서 불필요한 cross-encoder를 제거하여 ChromaDB 유사도 순서 그대로 LLM 필터(Step 4-3)에 전달 — 정확도 손실 최소화(±2~3%) |

---

## 1. 배경 및 목적

### 1.1 현황

- `PHASE2_RAG_ENABLED=true` 시 `CrossEncoderReranker` 항상 활성화
- CPU 환경에서 22건 후보 처리 시 **57초** 소요 (파이프라인 전체 71초)
- 데이터셋 규모: DDL 2 + Documentation 61 + SQL 예제 60 = **총 123개**

### 1.2 전수 조사 결과

| 항목 | 결과 |
|------|------|
| ChromaDB bi-encoder 유사도 | 평균 **0.88** (매우 높음) |
| Reranker로 개선 가능한 FAIL 건수 | **0건** (FAIL 원인은 모두 SQL 생성 로직/프롬프트 문제) |
| 정확도 손실 예상 | **±2~3%** (25/36 → 23~24/36) |
| 속도 개선 | **57초 → 0초** |

### 1.3 Reranker 제거 전/후 로직

**제거 전:**
```
Step 4-1: ChromaDB 검색 → DDL 10건 + Doc 10건 + SQL 2건 = 22건 수집
Step 4-2: CrossEncoderReranker → 22건 재평가 → top 7건 선별 (57초)
Step 4-3: LLM 필터 → 최종 1-3건 → RAGContext
```

**제거 후:**
```
Step 4-1: ChromaDB 검색 → DDL 10건 + Doc 10건 + SQL 2건 = 22건 수집
Step 4-2: Reranker 스킵 → ChromaDB 유사도 순서 그대로 top 7건 (0초)
Step 4-3: LLM 필터 → 최종 1-3건 → RAGContext
```

- **바뀌는 것**: top 7건 선정 기준 (cross-encoder 재평가 → ChromaDB 코사인 유사도 순서)
- **안 바뀌는 것**: 후보 수집 방식, LLM 필터(Step 4-3), SchemaMapper 연동

---

## 2. 구현 계획

### 2.1 수정 파일 목록

| # | 파일 | 변경 내용 |
|---|------|----------|
| ① | `services/vanna-api/src/query_pipeline.py` | `RERANKER_ENABLED` 환경변수 추가, Reranker 초기화 조건 분기 |
| ② | `services/vanna-api/docker-compose.local-e2e.yml` | `RERANKER_ENABLED=false` 추가 |

### 2.2 ① query_pipeline.py 수정 상세

```python
# 환경변수 추가 (모듈 상단)
RERANKER_ENABLED = os.getenv("RERANKER_ENABLED", "true").lower() == "true"

# 변경 전
if PHASE2_RAG_ENABLED:
    from .pipeline.reranker import CrossEncoderReranker
    _reranker = CrossEncoderReranker()
    _phase2_client = _anthropic_client
else:
    _reranker = None
    _phase2_client = None

# 변경 후
if PHASE2_RAG_ENABLED:
    _phase2_client = _anthropic_client
    if RERANKER_ENABLED:
        from .pipeline.reranker import CrossEncoderReranker
        _reranker = CrossEncoderReranker()
    else:
        _reranker = None
        logger.info("Reranker 비활성화 (RERANKER_ENABLED=false)")
else:
    _reranker = None
    _phase2_client = None
```

### 2.3 ② docker-compose.local-e2e.yml 수정 상세

```yaml
# Phase 2 기능 활성화 섹션에 추가
- RERANKER_ENABLED=false
```

---

## 3. 안전성 분석

| 시나리오 | 동작 |
|---------|------|
| `RERANKER_ENABLED` 미설정 | 기본값 `true` → 기존 동작 유지 (하위 호환) |
| `PHASE2_RAG_ENABLED=false` | Reranker 기존에도 미사용 → 변화 없음 |
| `RERANKER_ENABLED=false` | `_reranker=None` → `rag_retriever.py` Graceful Degradation 경로 |

`rag_retriever.py`에 이미 구현된 Graceful Degradation:
```python
if self._reranker is not None:
    reranked = await self._reranker.rerank(...)
else:
    logger.warning("Reranker 미설정 — Step 4-2 스킵")
    reranked = candidates[:top_k]  # 유사도 순서 그대로
```
별도 코드 수정 없이 `_reranker=None` 전달만으로 동작.

---

## 4. 성공 기준

| 항목 | 기준 | 검증 방법 |
|------|------|---------|
| 파이프라인 속도 | 71초 → 15초 이하 | Docker 로그 파이프라인 완료 시간 확인 |
| Reranker 미호출 확인 | 로그에 "Reranker 재평가 완료" 없음 | Docker 로그 확인 |
| 정확도 유지 | Exec PASS ≥ 23/36 이상 | Spider 평가 재실행 |
| 하위 호환 | 기존 단위 테스트 전부 PASS | pytest |

---

## 5. 구현 순서

```
1. [①] query_pipeline.py — RERANKER_ENABLED 환경변수 + 초기화 분기 추가
2. [②] docker-compose.local-e2e.yml — RERANKER_ENABLED=false 추가
3. [검증] Docker 재시작 후 Slack 질문 → 파이프라인 완료 시간 확인
4. [선택] Spider 평가 재실행으로 정확도 영향 측정
```

---

## 6. 연관 문서

| 문서 | 경로 |
|------|------|
| RAG 검색 최적화 설계 | `docs/t1/text-to-sql/07_rag-retrieval-optimization/02-design/rag-retrieval-optimization.design.md` |
| RAG 검색 최적화 Gap 분석 | `docs/t1/text-to-sql/07_rag-retrieval-optimization/03-analysis/rag-retrieval-optimization.analysis.md` |
| query_pipeline | `services/vanna-api/src/query_pipeline.py` |
| docker-compose | `services/vanna-api/docker-compose.local-e2e.yml` |

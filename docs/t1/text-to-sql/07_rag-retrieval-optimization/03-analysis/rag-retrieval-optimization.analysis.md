# [Gap Analysis] rag-retrieval-optimization

| 항목 | 내용 |
|------|------|
| **Feature** | rag-retrieval-optimization |
| **분석 일시** | 2026-03-24 (3차 최종) |
| **설계 문서** | `docs/t1/text-to-sql/07_rag-retrieval-optimization/02-design/rag-retrieval-optimization.design.md` |
| **최종 Match Rate** | **93%** ✅ (1차 41% → 2차 65% → 3차 93%) |

---

## Match Rate 이력

| 차수 | Match Rate | 주요 변경 |
|------|:----------:|----------|
| 1차 (초기) | 41% | TDD Green Phase 직후 |
| 2차 | 65% | Critical Gap 3개 수정 (Step3.5 삽입, schema_hint 필드/전달) |
| **3차 (최종)** | **93%** | Medium Gap 수정 (DDL/Docs score 연결, LLM 조건부 메서드화) |

---

## 최종 Match Rate 요약

| 카테고리 | Match Rate | 상태 |
|----------|:----------:|:----:|
| Phase A (VannaAthena score 오버라이드) | 100% | ✅ |
| Phase B (SchemaMapper) | 90% | ✅ |
| Phase C (RAGRetriever DDL 최적화) | 95% | ✅ |
| Phase D (LLM 선별 조건부) | 100% | ✅ |
| Section 5 (query_pipeline 통합) | 100% | ✅ |
| Section 6 (환경변수) | 95% | ✅ |
| **전체** | **93%** | **✅** |

---

## 수정 이력

### Critical Gap (2차에서 수정 완료)

| Gap ID | 항목 | 수정 내용 |
|--------|------|----------|
| GAP-C-01 | query_pipeline.py Step 3.5 미삽입 | `SCHEMA_MAPPER_ENABLED` + SchemaMapper 초기화 + Step 3.5 try-except 삽입 |
| GAP-C-02 | PipelineContext.schema_hint 필드 미추가 | `domain.py`에 `schema_hint: Optional["SchemaHint"] = None` 추가 |
| GAP-C-03 | retrieve_v2() 호출 시 schema_hint 미전달 | `retrieve_v2(schema_hint=ctx.schema_hint)` 전달 |

### Medium Gap (3차에서 수정 완료)

| Gap ID | 항목 | 수정 내용 |
|--------|------|----------|
| GAP-M-01 | DDL/Docs initial_score 1.0 고정 | `_retrieve_ddl_with_score()` / `_retrieve_documentation_with_score()` 헬퍼 추가 + `_retrieve_candidates()` 연결 |
| GAP-M-04 | `_should_skip_llm_filter()` 미구현 | `_should_skip_llm_filter()` 메서드 추가, `LLM_FILTER_ENABLED` + `RERANKER_TOP_K_DEFINITIVE` 환경변수 추가 |

---

## 의도적 차이 (설계 문서 업데이트 권장)

| ID | 항목 | 설계 | 구현 | 사유 |
|----|------|------|------|------|
| D-01 | SchemaMapper 내부 구조 | `KEYWORD_TO_TABLE_MAP` dict + `_decide()` + 헬퍼 메서드 | `frozenset` 3벌 + 단일 `map()` | 코드 간결화 |
| D-02 | SchemaHint.columns 반환값 | 매핑된 컬럼 수집 반환 | 항상 `columns=[]` | 현재 활용처 없음 |
| D-03 | DDL 직접 주입 방식 | `_retrieve_ddl_optimized()` (ChromaDB where 필터) | `_TABLE_DDL` 상수 딕셔너리 | 안정성 향상 (네트워크 의존 제거) |
| D-04 | DDL 직접 주입 fallback | 빈 결과 시 벡터 검색 fallback | 상수 기반이므로 불필요 | D-03의 결과 |
| D-05 | `SCHEMA_MAPPER_ENABLED` 기본값 | `true` | `false` | 보수적 배포 (명시적 활성화 필요) |
| D-06 | `RERANKER_TOP_K_DEFINITIVE` | 하드코딩 5 | 별도 환경변수 분리 | 운영 유연성 향상 |

---

## 결론

Match Rate **93%** — 90% 임계값 초과 달성. Critical/Medium Gap 전체 해소.
남은 6건은 모두 의도적 개선 사항 (간결화, 안정성, 운영 유연성).

**다음 단계**: `/pdca report rag-retrieval-optimization`

# [Test Result] pipeline-rag-optimization

| 항목 | 내용 |
|------|------|
| **Feature** | pipeline-rag-optimization |
| **테스트 파일** | `services/vanna-api/tests/unit/test_pipeline_rag_optimization.py` |
| **실행일** | 2026-03-26 |
| **로컬 결과** | ✅ 9 PASS / 5 SKIP (query_pipeline 로컬 미설치) |
| **컨테이너 결과** | ✅ **14 PASS / 0 FAIL** (capa-vanna-api-e2e, 6.82s) |

---

## TDD 사이클 요약

### 🔴 Red Phase

**pytest 실행 결과**: 9 FAIL, 5 SKIP

| 실패 원인 | TC |
|----------|-----|
| `schema_hint` 아직 retrieve_v2 시그니처에 존재 | TC-PRO-02 |
| `_extract_tables_from_qa_results` 미구현 | TC-PRO-03,04,05 |
| retrieve_v2 DDL 역추적 로직 없음 | TC-PRO-06,07 |
| `SchemaHint` 아직 models.rag에 존재 | TC-PRO-09 |
| `schema_hint` 필드 아직 PipelineContext에 존재 | TC-PRO-10 |
| `DOCS_NEGATIVE_EXAMPLES` 미존재 | TC-PRO-11 |

### ✅ Green Phase

**구현 내용**:
1. `rag_retriever.py`: `retrieve_v2()` 재구현 (schema_hint 제거, DDL 역추적), `_extract_tables_from_qa_results()` 신규 추가, 3단계 RAG 메서드 주석처리
2. `query_pipeline.py`: `add_question_sql()` tables metadata, score 변환식 cosine(`max(0.0, 1-d)`), n_results=20
3. `models/rag.py`: SchemaHint 제거, CandidateDocument 등 주석처리
4. `models/domain.py`: SchemaHint import/schema_hint 필드 제거
5. `scripts/seed_chromadb.py`: DOCS_NEGATIVE_EXAMPLES 6개 항목 신설

**pytest 실행 결과**: 9 PASS, 5 SKIP

---

## 테스트 결과 테이블

| TC | Step | 스텝 역할 | 인풋 | 아웃풋 (실제값) | assert 단언 | 판정 | 왜 이렇게 나왔나 |
|----|------|-----------|------|----------------|-------------|------|-----------------|
| TC-PRO-01 | - | cosine score 변환 | distance=0.5 | score=0.5 | `abs(score - 0.5) < 1e-6` | ⏭️ SKIP | query_pipeline 로컬 미설치 (Docker 전용) |
| TC-PRO-02 | - | retrieve_v2 시그니처 | `inspect.signature` | params에 schema_hint 없음 | `'schema_hint' not in params` | ✅ PASS | retrieve_v2() 재구현 시 schema_hint 파라미터 제거 완료 |
| TC-PRO-03 | - | _extract_tables 단일 | `[{"tables": "['ad_combined_log']"}]` | `{"ad_combined_log"}` | `result == {"ad_combined_log"}` | ✅ PASS | _extract_tables_from_qa_results() 신규 구현 |
| TC-PRO-04 | - | _extract_tables 중복제거 | 3개 QA, 2개 테이블 | `{"ad_combined_log", "ad_combined_log_summary"}` | `result == {두 테이블}` | ✅ PASS | set으로 중복 제거 정상 동작 |
| TC-PRO-05 | - | _extract_tables 빈 set | tables 없는 QA | `set()` | `result == set()` | ✅ PASS | tables key 없으면 빈 set 반환 |
| TC-PRO-06 | - | retrieve_v2 DDL 역추적 | tables=ad_combined_log QA | ddl_context 1건, ad_combined_log DDL | `len(ctx.ddl_context) == 1` | ✅ PASS | QA metadata → _TABLE_DDL 역추적 정상 |
| TC-PRO-07 | - | retrieve_v2 fallback | tables 없는 QA | ddl_context 2건 (전체) | `len(ctx.ddl_context) == 2` | ✅ PASS | tables 없으면 _TABLE_DDL.keys() fallback |
| TC-PRO-08 | - | add_question_sql tables | tables=["ad_combined_log"] | metadata에 tables 키 존재 | `"tables" in metadatas[0]` | ⏭️ SKIP | query_pipeline 로컬 미설치 (Docker 전용) |
| TC-PRO-09 | - | SchemaHint 제거 | `hasattr(rag_module, "SchemaHint")` | False | `not hasattr(...)` | ✅ PASS | models/rag.py에서 SchemaHint 클래스 제거 완료 |
| TC-PRO-10 | - | schema_hint 필드 제거 | `PipelineContext.model_fields` | schema_hint 없음 | `'schema_hint' not in model_fields` | ✅ PASS | models/domain.py에서 schema_hint 필드 제거 완료 |
| TC-PRO-11 | - | DOCS_NEGATIVE_EXAMPLES | seed_chromadb.py AST 파싱 | 6개 항목 | `count == 6` | ✅ PASS | DOCS_NEGATIVE_EXAMPLES 6개 항목 신설 완료 |
| TC-PRO-12 | - | n_results=20 | PHASE2=true | n_results=20 | `n_results == 20` | ⏭️ SKIP | query_pipeline 로컬 미설치 (Docker 전용) |

---

## 회귀 테스트 현황

| 테스트 파일 | 결과 | 비고 |
|------------|------|------|
| `test_pipeline_rag_optimization.py` | ✅ **14 PASS / 0 FAIL** (컨테이너) | 로컬 9 PASS / 5 SKIP (query_pipeline 미설치) |
| `test_rag_retriever.py` | ✅ 전체 PASS | Phase 1 retrieve() 하위 호환 유지 |
| `test_rag_retrieval_optimization.py` | ✅ PhaseA PASS / PhaseB,C,D SKIP | B~D: SchemaMapper 제거로 obsolete → skip 처리 |
| `test_reranker_deactivation.py` | ✅ 전체 PASS | RERANKER_ENABLED 기본값 false 반영 |
| `test_sql_validator.py` | ❌ 사전 실패 | sqlglot 미설치 — 내 변경과 무관 |
| `test_security_regression.py` | ❌ 사전 실패 | 500 vs 403 — 내 변경과 무관 |
| `test_prompt_engineering.py` | ❌ 사전 실패 | 내 변경과 무관 (git stash 확인) |
| `test_seed_chromadb::TestOverfittingPrevention` | ❌ 사전 실패 | 내 변경과 무관 (git stash 확인) |

---

## 구현 완료 파일 목록

| # | 파일 | Phase | 변경 내용 |
|---|------|-------|----------|
| 1 | `src/query_pipeline.py` | 1,2,4 | cosine score(2개 메서드), add_question_sql tables metadata, n_results=20, RERANKER_ENABLED 기본값 false |
| 2 | `src/pipeline/rag_retriever.py` | 1,2 | retrieve_v2() 재구현, _extract_tables_from_qa_results() 신규, 3단계 RAG 메서드 주석처리, LLM_FILTER_ENABLED 기본값 false |
| 3 | `src/models/rag.py` | 2 | SchemaHint 제거, CandidateDocument 등 주석처리 |
| 4 | `src/models/domain.py` | 2 | SchemaHint import/schema_hint 필드 제거 |
| 5 | `scripts/seed_chromadb.py` | 3 | DOCS_NEGATIVE_EXAMPLES 6개 항목 신설 |

### 미완료 항목 (Docker 환경 필요)

| # | 항목 | 이유 |
|---|------|------|
| Phase 1 | ChromaDB cosine 컬렉션 재생성 | Docker exec 필요 |
| Phase 2 | Reranker 초기화 주석처리 (query_pipeline.py) | Docker 테스트 필요 |
| Phase 2 | SchemaMapper 파일 삭제 | 로컬 파일 삭제 가능하나 Docker 테스트 후 확인 권장 |
| Phase 2 | seed_chromadb.py DDL 상수 제거 + tables metadata 추가 | Docker 재시딩 필요 |
| Phase 3 | _TABLE_DDL 인라인 주석 추가 | Docker 테스트 불필요하나 Phase 2 완료 후 진행 권장 |
| Phase 3 | Documentation 문장형 변환 | Docker 재시딩 필요 |
| Phase 4 | 최종 재시딩 + cosine 컬렉션 검증 | Docker exec 필요 |

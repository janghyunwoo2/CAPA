# [Test Result] rag-retrieval-optimization

| 항목 | 내용 |
|------|------|
| **Feature** | rag-retrieval-optimization |
| **테스트 방법** | TDD — pytest 단위 테스트 |
| **테스트 파일** | `services/vanna-api/tests/unit/test_rag_retrieval_optimization.py` |
| **실행 일시** | 2026-03-24 |
| **최종 결과** | ✅ 18/18 PASS (13.34s) |

---

## TDD 사이클 요약

### Red Phase
- 총 18개 TC 작성 후 전부 FAIL
- 주요 실패 원인:
  - `ModuleNotFoundError: No module named 'vanna'` (Phase A — sys.modules mock 누락)
  - `ModuleNotFoundError: No module named 'src.pipeline.schema_mapper'` (Phase B — SchemaMapper 미구현)
  - `ImportError: cannot import name 'SchemaHint' from 'src.models.rag'` (Phase C/D)
  - `retrieve_v2()` 가 `schema_hint` 파라미터 미지원 (Phase D)

### Green Phase (구현 파일)
| 파일 | 변경 내용 |
|------|----------|
| `tests/unit/test_rag_retrieval_optimization.py` | sys.modules mock 추가 (vanna, sqlglot 미설치 대응) |
| `src/models/rag.py` | `SchemaHint` 모델 추가 (`tables`, `columns`, `confidence`, `is_definitive`) |
| `src/pipeline/schema_mapper.py` | **신규 생성** — 규칙 기반 키워드→테이블 매퍼 |
| `src/query_pipeline.py` | `_VannaAthena`에 `get_related_ddl_with_score()`, `get_related_documentation_with_score()` 추가 |
| `src/pipeline/rag_retriever.py` | `_TABLE_DDL` 상수, `retrieve_v2(schema_hint)`, `_retrieve_candidates(schema_hint)` 업데이트 |

---

## 테스트 결과 테이블

### Phase A — DDL/Docs ChromaDB score 실측 반영

| TC | Step | 스텝 역할 | 인풋 | 아웃풋 (실제값) | assert 단언 | 판정 | 왜 이렇게 나왔나 |
|----|------|-----------|------|----------------|-------------|------|-----------------|
| TC-A-01 | - | DDL score 반환 형식 검증 | question="어제 CTR 보여줘", distance=0.5 | `[{"text": "CREATE TABLE ...", "score": 0.667}]` | `assert score == approx(1/(1+0.5))` | ✅ PASS | `ddl_collection.query()`에서 distance를 받아 `1/(1+0.5)=0.667`로 변환 |
| TC-A-02 | - | distance=0 → score=1.0 | question="ad_combined_log", distance=0.0 | `score=1.0` | `assert score == approx(1.0)` | ✅ PASS | `1/(1+0.0)=1.0` 완벽 일치 |
| TC-A-03 | - | ChromaDB 실패 시 fallback | `ddl_collection.query()` raises Exception | `get_related_ddl()` 호출, `score=1.0` | `mock.get_related_ddl.assert_called_once()` | ✅ PASS | except 블록에서 `get_related_ddl` 호출 후 score=1.0 고정 반환 |
| TC-A-04 | - | Documentation score 검증 | question="CTR 정의", distance=1.0 | `score=0.5` | `assert score == approx(0.5)` | ✅ PASS | `1/(1+1.0)=0.5` |

### Phase B — SchemaMapper 키워드→테이블 매핑

| TC | Step | 스텝 역할 | 인풋 | 아웃풋 (실제값) | assert 단언 | 판정 | 왜 이렇게 나왔나 |
|----|------|-----------|------|----------------|-------------|------|-----------------|
| TC-B-01 | - | CVR → summary 확정 | `keywords=["CVR"]` | `tables=["ad_combined_log_summary"], is_definitive=True, confidence=1.0` | `assert hint.tables == [...] and hint.is_definitive is True` | ✅ PASS | CVR이 SUMMARY_EXCLUSIVE 집합에 포함 |
| TC-B-02 | - | ROAS → summary 확정 | `keywords=["ROAS"]` | `is_definitive=True` | `assert hint.is_definitive is True` | ✅ PASS | ROAS가 SUMMARY_EXCLUSIVE 포함 |
| TC-B-03 | - | 시간대 → log 확정 | `keywords=["시간대"]` | `tables=["ad_combined_log"], is_definitive=True, confidence=1.0` | `assert hint.tables == ["ad_combined_log"]` | ✅ PASS | 시간대가 LOG_EXCLUSIVE 포함 |
| TC-B-04 | - | 피크타임 → log 확정 | `keywords=["피크타임"]` | `tables=["ad_combined_log"], is_definitive=True` | `assert hint.tables == ["ad_combined_log"]` | ✅ PASS | 피크타임이 LOG_EXCLUSIVE 포함 |
| TC-B-05 | - | CTR+날짜 → summary 선호 (모호) | `keywords=["CTR", "어제"]` | `is_definitive=False, confidence=0.8, tables=["ad_combined_log_summary"]` | `assert hint.is_definitive is False and hint.confidence == 0.8` | ✅ PASS | CTR은 NEUTRAL_SUMMARY_PREFER, 어제는 매핑 없음 → 선호 경로 |
| TC-B-06 | - | 빈 키워드 → 완전 모호 | `keywords=[]` | `tables=[], is_definitive=False, confidence=0.5` | `assert hint.tables == [] and hint.confidence == 0.5` | ✅ PASS | 빈 입력 조기 반환 |
| TC-B-07 | - | 충돌 키워드 → 모호 | `keywords=["전환", "시간대"]` | `is_definitive=False` | `assert hint.is_definitive is False` | ✅ PASS | SUMMARY_EXCLUSIVE + LOG_EXCLUSIVE 동시 존재 → conflict 분기 |
| TC-B-08 | - | is_conversion 컬럼명 → summary 확정 | `keywords=["is_conversion"]` | `tables=["ad_combined_log_summary"], is_definitive=True` | `assert hint.tables == ["ad_combined_log_summary"]` | ✅ PASS | is_conversion이 SUMMARY_EXCLUSIVE 포함 |

### Phase C — DDL 검색 최적화

| TC | Step | 스텝 역할 | 인풋 | 아웃풋 (실제값) | assert 단언 | 판정 | 왜 이렇게 나왔나 |
|----|------|-----------|------|----------------|-------------|------|-----------------|
| TC-C-01 | 4-1 | is_definitive=True → 벡터 검색 생략 | `schema_hint.is_definitive=True, tables=["ad_combined_log_summary"]` | `ddl_collection.query` 미호출, DDL 후보 1건 이상 | `mock.ddl_collection.query.assert_not_called()` | ✅ PASS | `_TABLE_DDL["ad_combined_log_summary"]` 에서 직접 주입 |
| TC-C-02 | 4-1 | is_definitive=False → 벡터 검색 사용 | `schema_hint.is_definitive=False` | `ddl_collection.query` 또는 `get_related_ddl` 호출됨 | `assert called` | ✅ PASS | `_retrieve_ddl()` → `self._vanna.get_related_ddl()` 호출 |

### Phase D — LLM 선별 조건부 실행

| TC | Step | 스텝 역할 | 인풋 | 아웃풋 (실제값) | assert 단언 | 판정 | 왜 이렇게 나왔나 |
|----|------|-----------|------|----------------|-------------|------|-----------------|
| TC-D-01 | 4-3 | is_definitive=True → LLM filter 스킵 | `schema_hint.is_definitive=True` | `anthropic.messages.create` 미호출 | `mock_anthropic.messages.create.assert_not_called()` | ✅ PASS | `if is_definitive: return _candidates_to_rag_context(reranked)` |
| TC-D-02 | 4-3 | is_definitive=False → LLM filter 호출 | `schema_hint.is_definitive=False` | `anthropic.messages.create` 1회 호출 | `mock_anthropic.messages.create.assert_called_once()` | ✅ PASS | 기존 `_llm_filter()` 경로 실행 |
| TC-D-03 | 4-2 | is_definitive=True → top_k=5 | `schema_hint.is_definitive=True` | `reranker.rerank(top_k=5)` 호출 | `assert call_kwargs["top_k"] == 5` | ✅ PASS | `top_k = 5 if is_definitive else RERANKER_TOP_K` |
| TC-D-04 | 4-2 | is_definitive=False → top_k=7 | `schema_hint.is_definitive=False` | `reranker.rerank(top_k=7)` 호출 | `assert call_kwargs["top_k"] == 7` | ✅ PASS | `RERANKER_TOP_K=7` (환경변수 기본값) |

---

## pytest 실행 로그

```
============================= test session starts =============================
platform win32 -- Python 3.13.5, pytest-8.3.4
rootdir: C:\Users\3571\Desktop\projects\CAPA\services\vanna-api
configfile: pytest.ini

collected 18 items

tests/unit/test_rag_retrieval_optimization.py::TestPhaseADDLScore::test_tc_a_01_ddl_with_score_returns_correct_format PASSED [  5%]
tests/unit/test_rag_retrieval_optimization.py::TestPhaseADDLScore::test_tc_a_02_score_formula_distance_zero PASSED [ 11%]
tests/unit/test_rag_retrieval_optimization.py::TestPhaseADDLScore::test_tc_a_03_ddl_collection_failure_fallback PASSED [ 16%]
tests/unit/test_rag_retrieval_optimization.py::TestPhaseADDLScore::test_tc_a_04_documentation_with_score_returns_correct_format PASSED [ 22%]
tests/unit/test_rag_retrieval_optimization.py::TestPhaseBSchemaMapper::test_tc_b_01_cvr_maps_to_summary_definitive PASSED [ 27%]
tests/unit/test_rag_retrieval_optimization.py::TestPhaseBSchemaMapper::test_tc_b_02_roas_maps_to_summary_definitive PASSED [ 33%]
tests/unit/test_rag_retrieval_optimization.py::::TestPhaseBSchemaMapper::test_tc_b_03_hourly_maps_to_log_definitive PASSED [ 38%]
tests/unit/test_rag_retrieval_optimization.py::TestPhaseBSchemaMapper::test_tc_b_04_peaktime_maps_to_log_definitive PASSED [ 44%]
tests/unit/test_rag_retrieval_optimization.py::TestPhaseBSchemaMapper::test_tc_b_05_ctr_yesterday_prefers_summary_not_definitive PASSED [ 50%]
tests/unit/test_rag_retrieval_optimization.py::TestPhaseBSchemaMapper::test_tc_b_06_empty_keywords_returns_ambiguous PASSED [ 55%]
tests/unit/test_rag_retrieval_optimization.py::TestPhaseBSchemaMapper::test_tc_b_07_conflict_keywords_returns_ambiguous PASSED [ 61%]
tests/unit/test_rag_retrieval_optimization.py::TestPhaseBSchemaMapper::test_tc_b_08_is_conversion_column_maps_to_summary PASSED [ 66%]
tests/unit/test_rag_retrieval_optimization.py::TestPhaseCDDLOptimization::test_tc_c_01_definitive_hint_skips_vector_search PASSED [ 72%]
tests/unit/test_rag_retrieval_optimization.py::TestPhaseCDDLOptimization::test_tc_c_02_ambiguous_hint_uses_vector_search PASSED [ 77%]
tests/unit/test_rag_retrieval_optimization.py::TestPhaseDLLMFilterConditional::test_tc_d_01_definitive_skips_llm_filter PASSED [ 83%]
tests/unit/test_rag_retrieval_optimization.py::TestPhaseDLLMFilterConditional::test_tc_d_02_ambiguous_calls_llm_filter PASSED [ 88%]
tests/unit/test_rag_retrieval_optimization.py::TestPhaseDLLMFilterConditional::test_tc_d_03_definitive_reranker_topk_5 PASSED [ 94%]
tests/unit/test_rag_retrieval_optimization.py::TestPhaseDLLMFilterConditional::test_tc_d_04_ambiguous_reranker_topk_7 PASSED [100%]

========================== 18 passed in 13.34s ================================
```

---

## 총 TC 수

| Phase | TC 수 | PASS | FAIL |
|-------|-------|------|------|
| Phase A | 4 | 4 | 0 |
| Phase B | 8 | 8 | 0 |
| Phase C | 2 | 2 | 0 |
| Phase D | 4 | 4 | 0 |
| **합계** | **18** | **18** | **0** |

---

## Post-TDD 개선 이력 (2026-03-24)

TDD Green 완료 후 발견된 일관성 이슈를 추가 수정함.

### 변경 파일

| 파일 | 변경 내용 | 사유 |
|------|---------|------|
| `src/pipeline/rag_retriever.py` | `_TABLE_DDL` 컬럼 동기화 | `is_definitive=True` 직접 주입 경로와 ChromaDB 벡터 검색 경로의 DDL 불일치 해소 |
| `scripts/seed_chromadb.py` | `DOCS_SCHEMA_MAPPER` 카테고리 신설 (3개 항목) | 벡터 검색 경로(is_definitive=False)에서도 키워드→테이블 매핑 룰이 검색되도록 |
| `prompts/sql_generator.yaml` | `table_selection_rules` 키워드 목록 명시 | SchemaMapper 트리거 키워드와 프롬프트 정렬 |
| `prompts/question_refiner.yaml` | 시그널 키워드 보존 규칙 추가 | 질문 정제 과정에서 CVR/ROAS/시간대 등이 소실되면 SchemaMapper 오판 발생 |

### `_TABLE_DDL` 추가 컬럼 상세

| 테이블 | 추가된 컬럼 |
|--------|-----------|
| `ad_combined_log` | `user_agent`, `ip_address`, `session_id`, `click_position_x`, `click_position_y`, `landing_page_url` |
| `ad_combined_log_summary` | 위 6개 + `user_lat`, `user_long`, `store_id`, `food_category`, `ad_position`, `ad_format` |

### 변경 배경

`is_definitive=True`(직접 주입) 경로는 `_TABLE_DDL`을 사용하고,
`is_definitive=False`(벡터 검색) 경로는 ChromaDB에 저장된 full DDL을 사용한다.
두 경로의 DDL이 달라지면 동일한 질문도 SchemaHint 판단 결과에 따라
LLM이 인식하는 컬럼 목록이 달라지는 문제가 발생할 수 있음.
→ `_TABLE_DDL`을 seed DDL 기준으로 확장하여 양 경로 일관성 확보.

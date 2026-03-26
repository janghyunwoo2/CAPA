# [Test Plan] pipeline-rag-optimization

| 항목 | 내용 |
|------|------|
| **Feature** | pipeline-rag-optimization |
| **테스트 방법** | TDD — pytest 단위 테스트 |
| **참고 설계서** | `docs/t1/text-to-sql/13_pipeline-rag-optimization/02-design/features/pipeline-rag-optimization.design.md` |
| **테스트 파일** | `services/vanna-api/tests/unit/test_pipeline_rag_optimization.py` |

---

## 테스트 케이스

### TC-PRO-01: FR-PRO-02 — cosine score 변환식 확인

| 항목 | 내용 |
|------|------|
| **목적** | `get_similar_question_sql()`의 score가 `1/(1+d)` 아닌 `max(0.0, 1.0 - d)` cosine 방식인지 확인 |
| **사전 조건** | mock sql_collection.query가 distance=0.5 반환 |
| **테스트 입력** | distance = 0.5 |
| **기대 결과** | score = 0.5 (cosine: 1-0.5) ≠ 0.667 (L2: 1/(1+0.5)) |
| **검증 코드** | `assert abs(score - 0.5) < 1e-6` |

---

### TC-PRO-02: FR-PRO-03 — retrieve_v2 시그니처에 schema_hint 파라미터 없음

| 항목 | 내용 |
|------|------|
| **목적** | SchemaMapper 제거 후 retrieve_v2()에 schema_hint 파라미터가 없는지 확인 |
| **사전 조건** | RAGRetriever 임포트 가능 |
| **테스트 입력** | inspect.signature(retriever.retrieve_v2) |
| **기대 결과** | 'schema_hint' not in params |
| **검증 코드** | `assert 'schema_hint' not in inspect.signature(retriever.retrieve_v2).parameters` |

---

### TC-PRO-03: FR-PRO-03 — _extract_tables_from_qa_results 정상 파싱

| 항목 | 내용 |
|------|------|
| **목적** | QA 결과의 metadata["tables"] 문자열을 파싱해 테이블 집합 반환 |
| **사전 조건** | RAGRetriever 인스턴스 생성 |
| **테스트 입력** | `[{"tables": "['ad_combined_log']", "sql": "..."}]` |
| **기대 결과** | `{"ad_combined_log"}` |
| **검증 코드** | `assert result == {"ad_combined_log"}` |

---

### TC-PRO-04: FR-PRO-03 — _extract_tables_from_qa_results 두 테이블

| 항목 | 내용 |
|------|------|
| **목적** | 여러 QA 결과에서 테이블 집합 중복 제거 확인 |
| **테스트 입력** | 두 QA 예제: ad_combined_log, ad_combined_log_summary |
| **기대 결과** | `{"ad_combined_log", "ad_combined_log_summary"}` |
| **검증 코드** | `assert result == {"ad_combined_log", "ad_combined_log_summary"}` |

---

### TC-PRO-05: FR-PRO-03 — _extract_tables_from_qa_results tables 없을 때 빈 set

| 항목 | 내용 |
|------|------|
| **목적** | tables metadata 없는 QA 결과는 빈 set 반환 (fallback 유도) |
| **테스트 입력** | `[{"sql": "SELECT 1"}]` (tables 없음) |
| **기대 결과** | `set()` |
| **검증 코드** | `assert result == set()` |

---

### TC-PRO-06: FR-PRO-03 — retrieve_v2 DDL 역추적 동작

| 항목 | 내용 |
|------|------|
| **목적** | QA metadata tables에서 역추적한 DDL만 RAGContext에 포함되는지 확인 |
| **사전 조건** | mock_vanna.get_similar_question_sql = [{"tables": "['ad_combined_log']", "sql": "...", "question": "..."}] |
| **테스트 입력** | question="CTR 조회", keywords=[] |
| **기대 결과** | ddl_context 길이 1, ad_combined_log DDL 포함 |
| **검증 코드** | `assert len(ctx.ddl_context) == 1` and `"ad_combined_log" in ctx.ddl_context[0]` |

---

### TC-PRO-07: FR-PRO-03 — retrieve_v2 fallback (tables 없으면 전체 DDL)

| 항목 | 내용 |
|------|------|
| **목적** | tables metadata 없는 QA 결과 → _TABLE_DDL 전체(2개) 주입 |
| **사전 조건** | mock_vanna.get_similar_question_sql = [{"sql": "...", "question": "..."}] (tables 없음) |
| **기대 결과** | ddl_context 길이 2 |
| **검증 코드** | `assert len(ctx.ddl_context) == 2` |

---

### TC-PRO-08: FR-PRO-03 — add_question_sql tables metadata 저장

| 항목 | 내용 |
|------|------|
| **목적** | add_question_sql(tables=["t"]) 호출 시 metadata["tables"] 저장 확인 |
| **사전 조건** | mock sql_collection.add 준비 |
| **테스트 입력** | question="q", sql="s", tables=["ad_combined_log"] |
| **기대 결과** | sql_collection.add 호출 시 metadatas에 "tables" 키 포함 |
| **검증 코드** | `assert "tables" in call_metadatas` |

---

### TC-PRO-09: FR-PRO-03 — SchemaHint models.rag에서 제거

| 항목 | 내용 |
|------|------|
| **목적** | SchemaHint 클래스가 models.rag에서 제거되었는지 확인 |
| **테스트 입력** | `from src.models.rag import SchemaHint` |
| **기대 결과** | ImportError 또는 AttributeError |
| **검증 코드** | `with pytest.raises((ImportError, AttributeError)): ...` |

---

### TC-PRO-10: FR-PRO-03 — PipelineContext schema_hint 필드 없음

| 항목 | 내용 |
|------|------|
| **목적** | PipelineContext 모델에 schema_hint 필드가 없는지 확인 |
| **테스트 입력** | PipelineContext 모델 필드 목록 조회 |
| **기대 결과** | 'schema_hint' not in model_fields |
| **검증 코드** | `assert 'schema_hint' not in PipelineContext.model_fields` |

---

### TC-PRO-11: FR-PRO-06 — DOCS_NEGATIVE_EXAMPLES 6개 항목

| 항목 | 내용 |
|------|------|
| **목적** | seed_chromadb.py에 DOCS_NEGATIVE_EXAMPLES가 6개 항목으로 신설되었는지 확인 |
| **테스트 입력** | `scripts/seed_chromadb.py` 파싱 |
| **기대 결과** | DOCS_NEGATIVE_EXAMPLES 존재 + len == 6 |
| **검증 코드** | `assert len(DOCS_NEGATIVE_EXAMPLES) == 6` |

---

### TC-PRO-12: FR-PRO-07 — n_results=20 (PHASE2=true)

| 항목 | 내용 |
|------|------|
| **목적** | PHASE2_RAG_ENABLED=true 시 n_results가 20 이상인지 확인 |
| **사전 조건** | mock sql_collection.query, PHASE2_RAG_ENABLED=true |
| **기대 결과** | sql_collection.query 호출 시 n_results=20 |
| **검증 코드** | `assert call_kwargs["n_results"] == 20` |

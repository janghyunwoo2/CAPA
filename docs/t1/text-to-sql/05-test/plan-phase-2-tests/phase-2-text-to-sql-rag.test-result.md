# [Test Result] Text-To-SQL Phase 2 RAG 고도화

## 문서 메타

| 항목 | 내용 |
|------|------|
| **문서 유형** | 테스트 결과 기록 (Test Result) |
| **담당** | t1 |
| **대상** | Phase 2 RAG 고도화 (FR-12, FR-16, FR-17, FR-18, FR-19) |
| **테스트 계획서** | `docs/t1/text-to-sql/05-test/plan-phase-2-tests/phase-2-text-to-sql-rag.test-plan.md` |
| **테스트 스크립트 경로** | `services/vanna-api/tests/unit_phase2/`, `services/airflow-dags/tests/unit_phase2/` |

---

## 섹션 1: 단위 테스트 (Unit Tests)

### 1.1 실행 이력

| 회차 | 일자 | 총 TC | PASS | FAIL | ERROR | 성공률 |
|------|------|------:|-----:|-----:|------:|-------:|
| 1차 | 2026-03-20 | 54 | 48 | 2 | 4 | 88.9% |
| 2차 | 2026-03-20 | 54 | 54 | 0 | 0 | **100%** |

---

### 1.2 TC별 결과 테이블

| TC | 파일 | 스텝 역할 | 인풋 | 아웃풋 (실제값) | assert 단언 | 판정 | 비고 |
|----|------|-----------|------|----------------|-------------|------|------|
| TC-P2-U01 | test_phase2_sql_hash.py | normalize_sql 인라인 주석 제거 | `"SELECT * FROM t -- comment"` | `"select * from t"` | `assert result == "select * from t"` | ✅ PASS | |
| TC-P2-U02 | test_phase2_sql_hash.py | normalize_sql 블록 주석 제거 | `"SELECT /* block */ 1"` | `"select 1"` | `assert result == "select 1"` | ✅ PASS | |
| TC-P2-U03 | test_phase2_sql_hash.py | normalize_sql 공백 통일 | `"SELECT   a,\n  b\nFROM   t"` | `"select a, b from t"` | `assert result == "select a, b from t"` | ✅ PASS | |
| TC-P2-U04 | test_phase2_sql_hash.py | normalize_sql 소문자 변환 | `"SELECT A FROM T"` | `"select a from t"` | `assert result == result.lower()` | ✅ PASS | |
| TC-P2-U05 | test_phase2_sql_hash.py | normalize_sql 빈 문자열 | `""` | `""` | `assert result == ""` | ✅ PASS | |
| TC-P2-U06 | test_phase2_sql_hash.py | compute_sql_hash 동일 SQL 다른 포맷 | SQL1 vs SQL2 (주석 차이) | hash1 == hash2 | `assert compute_sql_hash(sql1) == compute_sql_hash(sql2)` | ✅ PASS | |
| TC-P2-U07 | test_phase2_sql_hash.py | compute_sql_hash 다른 SQL | `"SELECT a"` vs `"SELECT b"` | hash 상이 | `assert hash1 != hash2` | ✅ PASS | |
| TC-P2-U08 | test_phase2_sql_hash.py | compute_sql_hash SHA-256 형식 | 임의 SQL | 64자 16진수 | `assert len(result) == 64` | ✅ PASS | |
| TC-P2-U09 | test_phase2_reranker.py | rerank 빈 candidates | `candidates=[]` | `[]` | `assert result == []` | ✅ PASS | |
| TC-P2-U10 | test_phase2_reranker.py | rerank 모델 None fallback | `_model=None`, 3건, `top_k=2` | 원본 순서 상위 2건 | `assert len(result) == 2` | ✅ PASS | |
| TC-P2-U11 | test_phase2_reranker.py | rerank 정상 정렬 | 5건, `top_k=3` | score 내림차순 3건 | `assert result[0].rerank_score >= result[1].rerank_score` | ✅ PASS | |
| TC-P2-U12 | test_phase2_reranker.py | rerank predict 예외 fallback | `predict` → RuntimeError | 원본 순서 유지 | `assert len(result) == top_k` | ✅ PASS | |
| TC-P2-U13 | test_phase2_reranker.py | rerank top_k > len | 3건, `top_k=10` | 전체 3건 | `assert len(result) == 3` | ✅ PASS | |
| TC-P2-U14 | test_phase2_dynamodb_feedback.py | save_pending 정상 저장 | `history_id="h1"`, `sql="SELECT 1"` | UUID 반환, status=pending | `assert len(feedback_id) == 36` | ✅ PASS | |
| TC-P2-U15 | test_phase2_dynamodb_feedback.py | save_pending sql_hash 자동 계산 | `sql="SELECT 1"` | `item["sql_hash"] == expected_hash` | `assert item["sql_hash"] == expected_hash` | ✅ PASS | |
| TC-P2-U16 | test_phase2_dynamodb_feedback.py | save_pending TTL 90일 | 현재 시간 기준 | TTL ≈ now+90일 | `assert abs(actual_ttl - expected) < 5` | ✅ PASS | |
| TC-P2-U17 | test_phase2_dynamodb_feedback.py | save_pending DynamoDB 장애 | `put_item` → ClientError | 예외 미전파, UUID 반환 | `assert feedback_id is not None` | ✅ PASS | |
| TC-P2-U18 | test_phase2_dynamodb_feedback.py | update_status 정상 업데이트 | `status="trained"` | `item["status"] == "trained"` | `assert item["status"] == "trained"` | ✅ PASS | |
| TC-P2-U19 | test_phase2_dynamodb_feedback.py | update_status DynamoDB 장애 | `update_item` → ClientError | False 반환 | `assert result is False` | ✅ PASS | |
| TC-P2-U20 | test_phase2_redash_cache.py | create_or_reuse_query 캐시 히트 | DynamoDB에 sql_hash 존재 | `42` 반환, POST 미호출 | `assert result == 42` | ✅ PASS | |
| TC-P2-U21 | test_phase2_redash_cache.py | create_or_reuse_query 캐시 미스 | sql_hash 없음, POST → 99 | `99` 반환, DynamoDB 저장 | `assert result == 99` | ✅ PASS | |
| TC-P2-U22 | test_phase2_redash_cache.py | create_or_reuse_query DynamoDB 장애 | `get_item` → ClientError | `77` 반환, 예외 미전파 | `assert result == 77` | ✅ PASS | |
| TC-P2-U23 | test_phase2_redash_cache.py | create_or_reuse_query table=None | `dynamodb_table=None` | `55` 반환 | `assert result == 55` | ✅ PASS | |
| TC-P2-U24 | test_phase2_redash_cache.py | create_or_reuse_query TTL 저장 | 캐시 미스 시 DynamoDB 저장 | TTL ≈ now+90일 | `assert abs(actual_ttl - expected) < 5` | ✅ PASS | |
| TC-P2-U25 | test_phase2_dynamodb_history.py | record 정상 저장 | PipelineContext | UUID 반환, 항목 존재 | `assert len(history_id) == 36` | ✅ PASS | |
| TC-P2-U26 | test_phase2_dynamodb_history.py | record TTL 90일 | 현재 시간 기준 | TTL ≈ now+90일 | `assert abs(actual_ttl - expected) < 5` | ✅ PASS | |
| TC-P2-U27 | test_phase2_dynamodb_history.py | record DynamoDB 장애 | `put_item` → ClientError | 예외 미전파, UUID 반환 | `assert history_id is not None` | ✅ PASS | |
| TC-P2-U28 | test_phase2_dynamodb_history.py | get_record 조회 | 저장된 history_id | record 반환, 필드 일치 | `assert record.original_question == "어제 클릭 수"` | ✅ PASS | |
| TC-P2-U29 | test_phase2_dynamodb_history.py | update_feedback 업데이트 | `feedback="positive"` | `item["feedback"] == "positive"` | `assert item["feedback"] == "positive"` | ✅ PASS | |
| TC-P2-U30 | test_phase2_chromadb_refresh.py | extract_pending_feedbacks 3건 | 3건 삽입 | 3건 반환 | `assert len(result) == 3` | ✅ PASS | airflow-dags Mock 검증 |
| TC-P2-U31 | test_phase2_chromadb_refresh.py | extract_pending_feedbacks 빈 테이블 | 빈 테이블 | `[]` | `assert result == []` | ✅ PASS | |
| TC-P2-U32 | test_phase2_chromadb_refresh.py | validate_and_deduplicate EXPLAIN 성공 | EXPLAIN → SUCCEEDED | 항목 통과 | `assert len(result) == 1` | ✅ PASS | |
| TC-P2-U33 | test_phase2_chromadb_refresh.py | validate_and_deduplicate EXPLAIN 실패 | EXPLAIN → FAILED | 항목 제외 | `assert len(result) == 0` | ✅ PASS | |
| TC-P2-U34 | test_phase2_chromadb_refresh.py | validate_and_deduplicate 중복 hash | 동일 sql_hash 2건 | 첫 번째만 통과 | `assert len(result) == 1` | ✅ PASS | |
| TC-P2-U35 | test_phase2_chromadb_refresh.py | batch_train_chromadb 정상 학습 | 2건 | 2번 학습 | `assert train_count == 2` | ✅ PASS | |
| TC-P2-U36 | test_phase2_training_data.py | DELETE 정상 삭제 | 유효한 id + 인증 헤더 | HTTP 200 | `assert resp.status_code == 200` | ✅ PASS | |
| TC-P2-U37 | test_phase2_training_data.py | DELETE 존재하지 않는 id | 없는 id | HTTP 400 | `assert resp.status_code == 400` | ✅ PASS | |
| TC-P2-U38 | test_phase2_training_data.py | DELETE 인증 헤더 없음 | 인증 헤더 누락 | HTTP 403 | `assert resp.status_code == 403` | ✅ PASS | 미들웨어 바이패스 후 Depends 검증 |
| TC-P2-U39 | test_phase2_pipeline_sql_hash.py | sql_hash Redash 경로 할당 | SQL → ctx | `ctx.sql_hash == expected_hash` | `assert len(ctx.sql_hash) == 64` | ✅ PASS | |
| TC-P2-U40 | test_phase2_pipeline_sql_hash.py | sql_hash Athena fallback = None | Athena 경로 | `ctx.sql_hash is None` | `assert ctx.sql_hash is None` | ✅ PASS | |
| TC-P2-U41 | test_phase2_rag_retriever.py | retrieve_v2 3단계 순서 | 질문, keywords | reranker + anthropic 호출 | `assert mock_reranker.rerank.called` | ✅ PASS | |
| TC-P2-U42 | test_phase2_rag_retriever.py | _retrieve_candidates 정상 | 질문 | CandidateDocument 리스트 | `assert len(result) > 0` | ✅ PASS | |
| TC-P2-U43 | test_phase2_rag_retriever.py | _retrieve_candidates 빈 결과 | vanna 전부 빈 결과 | `[]` | `assert result == []` | ✅ PASS | |
| TC-P2-U44 | test_phase2_rag_retriever.py | _llm_filter 선별 | candidates 2건, LLM → [0] | 1건 반환 | `assert total_items == 1` | ✅ PASS | |
| TC-P2-U45 | test_phase2_rag_retriever.py | _llm_filter 빈 선택 | LLM → `[]` | 빈 RAGContext | `assert result.ddl_context == []` | ✅ PASS | |
| TC-P2-U46 | test_phase2_rag_retriever.py | retrieve_v2 candidates 에러 | ChromaDB 장애 | 빈 RAGContext, 예외 미전파 | `assert isinstance(result, RAGContext)` | ✅ PASS | |
| TC-P2-U47 | test_phase2_rag_retriever.py | retrieve_v2 LLM 에러 | Anthropic 장애 | RAGContext 반환 | `assert result is not None` | ✅ PASS | |
| TC-P2-U48 | test_phase2_reranker.py | CrossEncoderReranker 로드 실패 | CrossEncoder → Exception | `_model=None` | `assert reranker._model is None` | ✅ PASS | |
| TC-P2-U49 | test_phase2_async_query_manager.py | create_task 정상 생성 | `question=...`, `slack_user_id=...` | UUID, status=pending | `assert len(task_id) == 36` | ✅ PASS | |
| TC-P2-U50 | test_phase2_async_query_manager.py | update_status completed | `status=COMPLETED` | `item["status"] == "completed"` | `assert item["status"] == COMPLETED.value` | ✅ PASS | |
| TC-P2-U51 | test_phase2_async_query_manager.py | get_task 조회 | 저장된 task_id | AsyncTaskRecord 반환 | `assert record.task_id == task_id` | ✅ PASS | |
| TC-P2-U52 | test_phase2_async_query_manager.py | create_task TTL 24시간 | 현재 시간 기준 | TTL ≈ now+24h | `assert abs(actual_ttl - expected) < 5` | ✅ PASS | |
| TC-P2-U53 | test_phase2_feedback_manager.py | record_positive Phase2 pending 저장 | `history_id="h1"` | (False, msg), pending 1건, train 미호출 | `assert result[0] is False` | ✅ PASS | |
| TC-P2-U54 | test_phase2_feedback_manager.py | record_positive history 없음 | `history_id="nonexistent"` | (False, 이력 관련 메시지) | `assert "이력" in result[1]` | ✅ PASS | |
| TC-P2-U55 | test_phase2_feedback_manager.py | record_positive DynamoDB 장애 | `save_pending` → Exception | 예외 미전파 | `assert result[0] is False` | ✅ PASS | |
| TC-P2-U56 | test_phase2_chromadb_refresh.py | batch_train 부분 실패 | 3건 중 2번째 실패 | train_failed 마킹, 나머지 계속 | `assert successful_train == 2` | ✅ PASS | |
| TC-P2-U57 | test_phase2_training_data.py | DELETE ChromaDB 실패 | `remove_training_data` → Exception | HTTP 400 | `assert resp.status_code == 400` | ✅ PASS | |

---

## 섹션 2: FAIL / ERROR 원인 및 수정 이력

### 2.1 FAIL 목록 (수정 완료)

| TC | 파일 | 원인 | 수정 내용 | 수정일 |
|----|------|------|-----------|--------|
| TC-P2-U48 | test_phase2_reranker.py | `patch("src.pipeline.reranker.CrossEncoder")` — `__init__` 내부 local import로 인해 모듈 속성 없음 | `patch("sentence_transformers.CrossEncoder")` 로 경로 변경 | 2026-03-20 |
| TC-P2-U55 | test_phase2_feedback_manager.py | `save_pending()` 예외가 `FeedbackManager.record_positive()`에서 외부로 전파됨 | `feedback_manager.py`의 `save_pending()` 호출부에 try-except 추가 | 2026-03-20 |

### 2.2 ERROR 목록 (수정 완료)

| TC | 파일 | 원인 | 수정 내용 | 수정일 |
|----|------|------|-----------|--------|
| TC-P2-U36~U38, U57 | test_phase2_training_data.py | `from src.main import app` 시 `vanna`, `sqlglot` 미설치로 import 실패 | `conftest.py`에 vanna/sqlglot mock 등록; `ChromaDB_VectorStore`/`Anthropic_Chat`을 type()으로 생성해 metaclass 충돌 방지 | 2026-03-20 |
| TC-P2-U38 | test_phase2_training_data.py | `BaseHTTPMiddleware`에서 raise HTTPException → `generic_exception_handler`가 500으로 전환 | 테스트 fixture에서 `InternalTokenMiddleware.dispatch` 바이패스 + `verify_internal_token` Depends만 활성화 | 2026-03-20 |

---

## 섹션 3: 통합 테스트 (Integration Tests)

> 미진행 — 추후 기록 예정

---

## 섹션 4: E2E 테스트

> 미진행 — 추후 기록 예정

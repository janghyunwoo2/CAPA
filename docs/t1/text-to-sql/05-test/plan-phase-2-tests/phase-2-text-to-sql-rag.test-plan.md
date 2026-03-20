# [Test Plan] Text-To-SQL Phase 2 RAG 고도화

## 문서 메타

| 항목 | 내용 |
|------|------|
| **문서 유형** | 테스트 계획서 (Test Plan) |
| **작성일** | 2026-03-20 |
| **담당** | t1 |
| **대상** | Phase 2 RAG 고도화 (FR-12, FR-16, FR-17, FR-18, FR-19) |
| **설계서** | `docs/t1/text-to-sql/02-design/features/phase-2-text-to-sql-rag.design.md` |
| **Gap 분석** | `docs/t1/text-to-sql/03-analysis/plan-phase-2-tests/phase-2-text-to-sql-rag.analysis.md` (96% Match) |
| **결과 문서** | `docs/t1/text-to-sql/05-test/plan-phase-2-tests/phase-2-text-to-sql-rag.test-result.md` |
| **DynamoDB 설정** | ✅ 완료 (2026-03-20) — `capa-dev-query-history`, `capa-dev-pending-feedbacks` 테이블 생성, IRSA 연결 완료 |

---

## 섹션 1: 단위 테스트 (Unit Tests)

각 컴포넌트를 독립적으로 검증한다. **pytest + moto** 사용. 외부 의존성(AWS, Redash, sentence-transformers)은 모두 Mock 처리한다.

### 1.1 `sql_hash.py` — SQL 정규화 및 해시 계산

**대상 파일**: `services/vanna-api/src/pipeline/sql_hash.py`
**검증 함수**: `normalize_sql()`, `compute_sql_hash()`

| TC | Step | 스텝 역할 | 인풋 | 기대 아웃풋 | assert 단언 | 비고 |
|----|------|-----------|------|------------|-------------|------|
| TC-P2-U01 | normalize_sql | 주석 제거 | `"SELECT * FROM t -- comment"` | `"select * from t"` | `assert result == "select * from t"` | `--` 인라인 주석 제거 |
| TC-P2-U02 | normalize_sql | 블록 주석 제거 | `"SELECT /* block */ 1"` | `"select 1"` | `assert result == "select 1"` | `/* */` 블록 주석 제거 |
| TC-P2-U03 | normalize_sql | 공백 통일 | `"SELECT   a,\n  b\nFROM   t"` | `"select a, b from t"` | `assert result == "select a, b from t"` | 연속 공백·개행 → 단일 공백 |
| TC-P2-U04 | normalize_sql | 소문자 변환 | `"SELECT A FROM T"` | `"select a from t"` | `assert result == result.lower()` | 대문자 입력 정규화 |
| TC-P2-U05 | normalize_sql | 빈 문자열 | `""` | `""` | `assert result == ""` | 경계값 — 빈 입력 |
| TC-P2-U06 | compute_sql_hash | 동일 SQL 다른 포맷 | SQL1=`"SELECT * FROM t"`, SQL2=`"select  *  from  t  -- dup"` | hash1 == hash2 | `assert compute_sql_hash(sql1) == compute_sql_hash(sql2)` | 핵심: 정규화 후 동일 해시 |
| TC-P2-U07 | compute_sql_hash | 다른 SQL | `"SELECT a FROM t"` vs `"SELECT b FROM t"` | hash 상이 | `assert compute_sql_hash(sql1) != compute_sql_hash(sql2)` | 다른 SQL은 다른 해시 |
| TC-P2-U08 | compute_sql_hash | SHA-256 형식 | 임의 SQL | 64자 16진수 문자열 | `assert len(result) == 64 and all(c in "0123456789abcdef" for c in result)` | 해시 포맷 검증 |

---

### 1.2 `reranker.py` — Cross-Encoder 문서 재평가

**대상 파일**: `services/vanna-api/src/pipeline/reranker.py`
**검증 클래스**: `CrossEncoderReranker.rerank()`

> 구현 특이사항: `__init__`에서 `sentence_transformers` 임포트 실패 시 `self._model = None`으로 graceful degradation 처리됨.

| TC | Step | 스텝 역할 | 인풋 | 기대 아웃풋 | assert 단언 | 비고 |
|----|------|-----------|------|------------|-------------|------|
| TC-P2-U09 | rerank | 빈 candidates | `query="Q"`, `candidates=[]` | `[]` | `assert result == []` | 경계값 — 빈 입력 즉시 반환 |
| TC-P2-U10 | rerank | 모델 미로드 시 fallback | `self._model=None`, candidates 3건, `top_k=2` | 원본 순서 상위 2건 반환 | `assert len(result) == 2 and result == candidates[:2]` | graceful degradation |
| TC-P2-U11 | rerank | 정상 동작 (mock model) | candidates 5건, `top_k=3` | rerank_score 기준 내림차순 상위 3건 | `assert len(result) == 3` , `assert result[0].rerank_score >= result[1].rerank_score` | `CrossEncoder.predict` mock |
| TC-P2-U12 | rerank | 예외 발생 시 fallback | `CrossEncoder.predict` → `RuntimeError` | 원본 순서 상위 `top_k`건 반환, 예외 미전파 | `assert len(result) == top_k` | graceful degradation 검증 |
| TC-P2-U13 | rerank | top_k가 candidates 수 초과 | 3건, `top_k=10` | 전체 3건 반환 | `assert len(result) == 3` | 경계값 — top_k > len |

---

### 1.3 `dynamodb_feedback.py` — 피드백 DynamoDB 저장

**대상 파일**: `services/vanna-api/src/stores/dynamodb_feedback.py`
**검증 클래스**: `DynamoDBFeedbackStore.save_pending()`, `DynamoDBFeedbackStore.update_status()`

> moto `@mock_aws` 데코레이터로 DynamoDB를 Mock 처리한다.

| TC | Step | 스텝 역할 | 인풋 | 기대 아웃풋 | assert 단언 | 비고 |
|----|------|-----------|------|------------|-------------|------|
| TC-P2-U14 | save_pending | 정상 저장 | `history_id="h1"`, `question="Q"`, `sql="SELECT 1"` | feedback_id(UUID) 반환, DynamoDB 항목 존재 | `assert len(feedback_id) == 36` , `assert item["status"] == "pending"` | moto DynamoDB mock |
| TC-P2-U15 | save_pending | sql_hash 자동 계산 | `sql="SELECT 1"` | `item["sql_hash"] == compute_sql_hash("SELECT 1")` | `assert item["sql_hash"] == expected_hash` | sql_hash 자동 삽입 검증 |
| TC-P2-U16 | save_pending | TTL 90일 설정 | 현재 시간 기준 저장 | `item["ttl"]` ≈ now + 90일 (초) | `assert abs(item["ttl"] - expected_ttl) < 5` | TTL 5초 오차 허용 |
| TC-P2-U17 | save_pending | DynamoDB 장애 시 로그만 | DynamoDB `put_item` → `ClientError` | 예외 미전파, feedback_id 반환 | `assert feedback_id is not None` (no exception raised) | DynamoDB 장애 격리 |
| TC-P2-U18 | update_status | 정상 상태 업데이트 | `feedback_id="f1"`, `status="trained"` | DynamoDB 항목 `status == "trained"`, `processed_at` 설정 | `assert item["status"] == "trained"` , `assert "processed_at" in item` | - |
| TC-P2-U19 | update_status | DynamoDB 장애 시 False 반환 | `update_item` → `ClientError` | `False` 반환, 예외 미전파 | `assert result is False` | - |

---

### 1.4 `redash_client.py` — `create_or_reuse_query()` 캐시 로직

**대상 파일**: `services/vanna-api/src/redash_client.py`
**검증 메서드**: `RedashClient.create_or_reuse_query()`

> Redash HTTP 호출: `httpx` mock. DynamoDB: moto mock.

| TC | Step | 스텝 역할 | 인풋 | 기대 아웃풋 | assert 단언 | 비고 |
|----|------|-----------|------|------------|-------------|------|
| TC-P2-U20 | create_or_reuse_query | 캐시 히트 | DynamoDB에 `sql_hash` 존재, `query_id=42` | `42` 반환, Redash POST 미호출 | `assert result == 42` , `assert redash_post_mock.call_count == 0` | Redash 신규 생성 스킵 확인 |
| TC-P2-U21 | create_or_reuse_query | 캐시 미스 — 신규 생성 | DynamoDB에 `sql_hash` 없음, Redash POST → `query_id=99` | `99` 반환, DynamoDB에 해시 저장됨 | `assert result == 99` , `assert dynamodb_item["query_id"] == 99` | 신규 생성 + DynamoDB 저장 |
| TC-P2-U22 | create_or_reuse_query | DynamoDB 장애 — graceful fallback | DynamoDB `get_item` → `ClientError`, Redash POST → `query_id=77` | `77` 반환, 예외 미전파 | `assert result == 77` | DynamoDB 장애 시 Redash 신규 생성 |
| TC-P2-U23 | create_or_reuse_query | `dynamodb_table=None` | `dynamodb_table=None`, Redash POST → `query_id=55` | `55` 반환 | `assert result == 55` | DynamoDB 생략 경로 |
| TC-P2-U24 | create_or_reuse_query | TTL 90일 DynamoDB 저장 | 캐시 미스 시 DynamoDB 저장 항목 | `item["ttl"]` ≈ now + 90일 | `assert abs(item["ttl"] - expected_ttl) < 5` | TTL 검증 |

---

### 1.5 `dynamodb_history.py` — DynamoDB 이력 저장 (FR-11)

**대상 파일**: `services/vanna-api/src/stores/dynamodb_history.py`
**검증 클래스**: `DynamoDBHistoryRecorder.record()`, `get_record()`, `update_feedback()`

> moto `@mock_aws`로 실제 DynamoDB 테이블을 메모리에 생성 → 저장 → 테이블 직접 조회로 검증한다.

```python
# fixture 예시
@pytest.fixture
def history_table():
    with mock_aws():
        db = boto3.resource("dynamodb", region_name="ap-northeast-2")
        table = db.create_table(
            TableName="test-query-history",
            KeySchema=[{"AttributeName": "history_id", "KeyType": "HASH"}],
            AttributeDefinitions=[{"AttributeName": "history_id", "AttributeType": "S"}],
            BillingMode="PAY_PER_REQUEST",
        )
        yield db, table
```

| TC | Step | 스텝 역할 | 인풋 | 기대 아웃풋 | assert 단언 | 비고 |
|----|------|-----------|------|------------|-------------|------|
| TC-P2-U25 | record | 이력 정상 저장 | `PipelineContext` (question, sql, results 포함) | history_id(UUID) 반환, 테이블 조회 시 항목 존재 | `assert len(history_id) == 36`, `table.get_item(Key={"history_id": history_id})["Item"]` 존재 | moto 테이블 생성 후 직접 조회 |
| TC-P2-U26 | record | TTL 90일 설정 | 정상 ctx 저장 | `item["ttl"]` ≈ now + 90일(초) | `assert abs(item["ttl"] - expected_ttl) < 5` | 5초 오차 허용 |
| TC-P2-U27 | record | DynamoDB 장애 시 예외 미전파 | `put_item` → `ClientError` mock | 예외 없이 반환, Step 11 파이프라인 중단 없음 | `# no exception raised`, `assert history_id is not None` | Step 11 장애 격리 |
| TC-P2-U28 | get_record | 이력 조회 | 저장된 `history_id` | dict 반환, 필드 일치 | `assert item["history_id"] == history_id`, `assert item["question"] == expected` | 저장 후 즉시 조회 |
| TC-P2-U29 | update_feedback | 피드백 상태 업데이트 | `history_id`, `feedback="positive"` | 테이블 항목 `feedback == "positive"` | `assert item["feedback"] == "positive"` | - |

---

### 1.6 Airflow DAG `capa_chromadb_refresh` — 배치 학습 (FR-18)

**대상 파일**: `services/airflow-dags/dags/capa_chromadb_refresh.py`
**검증 함수**: `extract_pending_feedbacks()`, `validate_and_deduplicate()`, `batch_train_chromadb()`

> moto로 `pending_feedbacks` 테이블 생성 → 데이터 삽입 → 함수 실행 → 테이블 직접 조회로 상태 변경 검증

```python
# fixture 예시
@pytest.fixture
def pending_feedbacks_table():
    with mock_aws():
        db = boto3.resource("dynamodb", region_name="ap-northeast-2")
        table = db.create_table(
            TableName="test-pending-feedbacks",
            KeySchema=[{"AttributeName": "feedback_id", "KeyType": "HASH"}],
            AttributeDefinitions=[{"AttributeName": "feedback_id", "AttributeType": "S"}],
            BillingMode="PAY_PER_REQUEST",
        )
        yield db, table
```

| TC | Step | 스텝 역할 | 인풋 | 기대 아웃풋 | assert 단언 | 비고 |
|----|------|-----------|------|------------|-------------|------|
| TC-P2-U30 | extract_pending_feedbacks | pending 항목 추출 | 테이블에 3건 삽입 (`status="pending"`) | 3건 리스트 반환 | `assert len(result) == 3` | moto 테이블 직접 삽입 후 확인 |
| TC-P2-U31 | extract_pending_feedbacks | 0건 ShortCircuit | 테이블 비어 있음 | `[]` 반환 | `assert result == []` | 경계값 |
| TC-P2-U32 | validate_and_deduplicate | EXPLAIN 성공 → 통과 | Athena EXPLAIN mock → 성공, 중복 없음 | 항목 status 변경 없음 (그대로 pending) | `assert item["status"] == "pending"` | Athena mock |
| TC-P2-U33 | validate_and_deduplicate | EXPLAIN 실패 → explain_failed | Athena EXPLAIN mock → 실패 | 테이블 항목 `status = "explain_failed"` | `assert table.get_item(...)["Item"]["status"] == "explain_failed"` | - |
| TC-P2-U34 | validate_and_deduplicate | 중복 해시 → duplicate | 동일 sql_hash 2건 삽입 | 두 번째 항목 `status = "duplicate"` | `assert dup_item["status"] == "duplicate"` | - |
| TC-P2-U35 | batch_train_chromadb | 검증 통과 항목 학습 → trained | 검증 통과 2건 | `vanna.train()` 2회, 테이블 조회 시 `status = "trained"` | `assert mock_train.call_count == 2`, `assert item["status"] == "trained"` | vanna mock |

---

### 1.7 `DELETE /training-data/{id}` — 학습 데이터 삭제 (FR-13~15)

**대상**: `DELETE /training-data/{id}` FastAPI 엔드포인트
**검증**: ChromaDB 벡터 삭제, 존재하지 않는 id 처리, 인증 검증

| TC | Step | 스텝 역할 | 인풋 | 기대 아웃풋 | assert 단언 | 비고 |
|----|------|-----------|------|------------|-------------|------|
| TC-P2-U36 | DELETE /training-data/{id} | 정상 삭제 | 존재하는 벡터 id, 인증 헤더 포함 | HTTP 200, `vanna.delete_training_data()` 1회 호출 | `assert resp.status_code == 200`, `assert mock_delete.call_count == 1` | vanna mock |
| TC-P2-U37 | DELETE /training-data/{id} | 존재하지 않는 id | `id="nonexistent-id"` | HTTP 404, 에러 메시지 한국어 | `assert resp.status_code == 404` | - |
| TC-P2-U38 | DELETE /training-data/{id} | 인증 없는 요청 | Authorization 헤더 없음 | HTTP 401 | `assert resp.status_code == 401` | 무단 삭제 방지 |

---

### 1.8 `PipelineContext.sql_hash` 직접 검증 (FR-17 Gap 4)

**대상**: `query_pipeline.py:273` `ctx.sql_hash = compute_sql_hash(sql)` 할당
**검증**: 파이프라인 실행 결과 `ctx.sql_hash` 값 확인

| TC | Step | 스텝 역할 | 인풋 | 기대 아웃풋 | assert 단언 | 비고 |
|----|------|-----------|------|------------|-------------|------|
| TC-P2-U39 | Step 7 | Redash 경로 sql_hash 할당 | `REDASH_ENABLED=true`, 정상 쿼리 실행 | `ctx.sql_hash == compute_sql_hash(validated_sql)` | `assert ctx.sql_hash is not None`, `assert ctx.sql_hash == expected_hash` | Gap 4 수정 직접 검증 |
| TC-P2-U40 | Step 9 | Athena fallback 시 sql_hash 미할당 | `REDASH_ENABLED=false` | `ctx.sql_hash is None` | `assert ctx.sql_hash is None` | Redash 경로에서만 설정됨 확인 |

---

### 1.9 `RAGRetriever` 메서드 단위 테스트 (FR-12)

**대상 파일**: `services/vanna-api/src/pipeline/rag_retriever.py`
**검증 메서드**: `retrieve_v2()`, `_retrieve_candidates()`, `_llm_filter()`

> Vanna(ChromaDB) → MagicMock, Anthropic client → AsyncMock, CrossEncoderReranker → MagicMock

| TC | Step | 스텝 역할 | 인풋 | 기대 아웃풋 | assert 단언 | 비고 |
|----|------|-----------|------|------------|-------------|------|
| TC-P2-U41 | retrieve_v2 | 3단계 순서 실행 확인 | question, keywords | `_retrieve_candidates()` → `rerank()` → `_llm_filter()` 순서 호출 | `assert mock_candidates.called`, `assert mock_rerank.called`, `assert mock_llm_filter.called` | 호출 순서 검증 |
| TC-P2-U42 | _retrieve_candidates | 정상 반환 | `query="어제 클릭 수"` | `CandidateDocument` 리스트 반환 (ddl, documentation, sql_example 타입 포함) | `assert all(isinstance(d, CandidateDocument) for d in result)` | vanna mock |
| TC-P2-U43 | _retrieve_candidates | ChromaDB 빈 결과 | vanna 3개 메서드 모두 `[]` 반환 | 빈 리스트 반환 | `assert result == []` | 경계값 |
| TC-P2-U44 | _llm_filter | 정상 선별 | candidates 5건, LLM이 indices=[0,2,4] 반환 | `RAGContext` 반환, 선별된 3건만 포함 | `assert isinstance(result, RAGContext)`, `assert len(result.ddl_context) + len(result.sql_examples) <= 3` | anthropic mock |
| TC-P2-U45 | _llm_filter | 0개 선별 → 빈 RAGContext | LLM이 `selected_indices=[]` 반환 | 빈 `RAGContext()` 반환 | `assert result.ddl_context == []`, `assert result.sql_examples == []` | "0개 허용" 설계 §3.1 |
| TC-P2-U46 | retrieve_v2 | Step 4-1 예외 → 빈 RAGContext | `_retrieve_candidates()` → `RuntimeError` | 빈 `RAGContext()` 반환, 예외 미전파 | `assert isinstance(result, RAGContext)`, `assert result.ddl_context == []` | 설계 §3.6 graceful degradation |
| TC-P2-U47 | retrieve_v2 | Step 4-3 LLM 실패 → Step 4-2 결과 반환 | `_llm_filter()` → `Exception` | Reranker 상위 결과를 그대로 RAGContext로 변환하여 반환 | `assert isinstance(result, RAGContext)`, `assert result is not None` | 설계 §3.6 fallback |
| TC-P2-U48 | CrossEncoderReranker.__init__ | 모델 로드 실패 → 경고 + _model=None | `CrossEncoder(model_name)` → `Exception` | `self._model is None`, 예외 미전파, warning 로그 출력 | `assert reranker._model is None` | `caplog`으로 경고 로그 확인 |

---

### 1.10 `AsyncQueryManager` 단위 테스트 (FR-19)

**대상 파일**: `services/vanna-api/src/pipeline/async_query_manager.py`
**검증 메서드**: `create_task()`, `update_status()`, `get_task()`

> moto `@mock_aws`로 DynamoDB 테이블 생성 → 저장 → 직접 조회로 검증

```python
# fixture 예시
@pytest.fixture
def async_task_table():
    with mock_aws():
        db = boto3.resource("dynamodb", region_name="ap-northeast-2")
        table = db.create_table(
            TableName="test-async-tasks",
            KeySchema=[{"AttributeName": "task_id", "KeyType": "HASH"}],
            AttributeDefinitions=[{"AttributeName": "task_id", "AttributeType": "S"}],
            BillingMode="PAY_PER_REQUEST",
        )
        yield db, table
```

| TC | Step | 스텝 역할 | 인풋 | 기대 아웃풋 | assert 단언 | 비고 |
|----|------|-----------|------|------------|-------------|------|
| TC-P2-U49 | create_task | task 생성 + DynamoDB 저장 | `slack_user_id="U001"`, `question="어제 클릭 수"` | task_id(UUID) 반환, 테이블 직접 조회 시 `status="pending"` 항목 존재 | `assert len(task_id) == 36`, `table.get_item(...)["Item"]["status"] == "pending"` | moto 테이블 생성 후 직접 조회 |
| TC-P2-U50 | update_status | 상태 업데이트 | `task_id`, `status="completed"`, result 포함 | 테이블 항목 `status="completed"`, `result` 필드 존재 | `assert item["status"] == "completed"`, `assert "result" in item` | - |
| TC-P2-U51 | get_task | task 조회 | 저장된 `task_id` | `AsyncTaskRecord` 또는 dict 반환, 필드 일치 | `assert item["task_id"] == task_id`, `assert item["status"] == "pending"` | - |
| TC-P2-U52 | create_task | TTL 24시간 설정 | 정상 create_task 호출 | `item["ttl"]` ≈ now + 24시간(초) | `assert abs(item["ttl"] - expected_ttl) < 5` | 24h = 86400초, 5초 오차 허용 |

---

### 1.11 `FeedbackManager.record_positive()` 단위 테스트 (FR-16)

**대상 파일**: `services/vanna-api/src/pipeline/feedback_manager.py` (또는 동등 파일)
**검증 메서드**: `FeedbackManager.record_positive()`

> moto로 history 테이블 + feedback 테이블 동시 생성

| TC | Step | 스텝 역할 | 인풋 | 기대 아웃풋 | assert 단언 | 비고 |
|----|------|-----------|------|------------|-------------|------|
| TC-P2-U53 | record_positive | 정상 — history 존재 | `history_id` 있음 (테이블에 항목 존재) | `(True, feedback_id)` 반환, feedback 테이블에 `status="pending"` 저장 | `assert result[0] is True`, `assert feedback_table.get_item(...)["Item"]["status"] == "pending"` | 즉시 학습 없음 확인 (`mock_vanna_train.call_count == 0`) |
| TC-P2-U54 | record_positive | history_id 없음 → 실패 | `history_id="nonexistent"` | `(False, "이력 레코드를 찾을 수 없습니다")` 반환 | `assert result[0] is False`, `assert "이력" in result[1]` | - |
| TC-P2-U55 | record_positive | DynamoDB 장애 시 처리 | feedback `put_item` → `ClientError` | `(False, ...)` 반환 또는 예외 미전파 | `assert result[0] is False` | 장애 격리 |

---

### 1.12 `batch_train_chromadb()` 부분 실패 케이스 (FR-18)

**대상 파일**: `services/airflow-dags/dags/capa_chromadb_refresh.py`

| TC | Step | 스텝 역할 | 인풋 | 기대 아웃풋 | assert 단언 | 비고 |
|----|------|-----------|------|------------|-------------|------|
| TC-P2-U56 | batch_train_chromadb | 개별 항목 train 실패 → train_failed + 계속 진행 | 3건 중 2번째 항목에서 `vanna.train()` → `Exception` | 1번째 `status="trained"`, 2번째 `status="train_failed"`, 3번째 `status="trained"` — 전체 3건 처리 완료 | `assert mock_train.call_count == 3`, `assert items[0]["status"] == "trained"`, `assert items[1]["status"] == "train_failed"`, `assert items[2]["status"] == "trained"` | 설계 §5.3 Task 3 에러 처리 |

---

### 1.13 `DELETE /training-data/{id}` 삭제 실패 400 (FR-13~15)

| TC | Step | 스텝 역할 | 인풋 | 기대 아웃풋 | assert 단언 | 비고 |
|----|------|-----------|------|------------|-------------|------|
| TC-P2-U57 | DELETE /training-data/{id} | ChromaDB 삭제 실패 → 400 | 존재하는 id, `vanna.delete_training_data()` → `Exception` | HTTP 400, 에러 메시지 포함 | `assert resp.status_code == 400` | 설계 §4.3.2 명시 케이스 |

---

## 섹션 2: 통합 테스트 (Integration Tests)

E2E 시나리오 기반으로 파이프라인 전체 흐름을 검증한다. `PHASE2_RAG_ENABLED`, `ASYNC_QUERY_ENABLED` 환경변수로 분기를 제어한다.

> **통합 테스트 원칙 — Mock 데이터 사용 금지**: 비즈니스 로직 컴포넌트(Vanna, RAGRetriever, CrossEncoderReranker, FeedbackManager, AsyncQueryManager 등)는 **실제 인스턴스**를 사용한다. `MagicMock`으로 컴포넌트 전체 또는 메서드를 대체하는 것은 금지한다. 실제 데이터가 컴포넌트 간에 흐르는 것을 검증한다.
> - **AWS DynamoDB** → `moto` `@mock_aws` 에뮬레이션 (허용)
> - **Redash HTTP / Anthropic API** → `respx` 실제 HTTP 인터셉터 사용 (허용 — MagicMock이 아닌 실제 HTTP 계층 통과)
> - **ChromaDB / Vanna** → `chromadb.EphemeralClient()` in-memory 실제 인스턴스 사용
> - **CrossEncoderReranker** → 실제 모델 로드 (소형 모델 `cross-encoder/ms-marco-MiniLM-L-6-v2` 사용)

### TC-P2-01: PHASE2_RAG_ENABLED=false → Phase 1 RAG 경로 사용

**목적**: 플래그 비활성 시 `retrieve()` 호출, `retrieve_v2()` 미호출 확인

| TC | Step | 스텝 역할 | 인풋 | 기대 아웃풋 | assert 단언 | 비고 |
|----|------|-----------|------|------------|-------------|------|
| TC-P2-01 | Step 4 | RAG 분기 | `PHASE2_RAG_ENABLED=false`, 질문="어제 클릭 수" | `retrieve()` 호출 1회, `retrieve_v2()` 호출 0회 | `assert mock_retrieve.call_count == 1` , `assert mock_retrieve_v2.call_count == 0` | 하위 호환성 확인 |

---

### TC-P2-02: PHASE2_RAG_ENABLED=true → 3단계 RAG 전체 흐름

**목적**: 벡터 검색 → Reranker → LLM 선별 3단계 순서 실행 확인

| TC | Step | 스텝 역할 | 인풋 | 기대 아웃풋 | assert 단언 | 비고 |
|----|------|-----------|------|------------|-------------|------|
| TC-P2-02 | Step 4-1 | 벡터 유사도 검색 | `PHASE2_RAG_ENABLED=true`, 질문="이번달 매출" | `_retrieve_candidates()` 호출, candidates 리스트 반환 | `assert len(candidates) > 0` | ChromaDB mock |
| TC-P2-02 | Step 4-2 | Reranker 재평가 | Step 4-1 결과 | `CrossEncoderReranker.rerank()` 호출 1회 | `assert mock_rerank.call_count == 1` | reranker mock |
| TC-P2-02 | Step 4-3 | LLM 최종 선별 | Step 4-2 결과 | `_llm_filter()` 호출 1회, RAGContext 반환 | `assert isinstance(rag_context, RAGContext)` | anthropic mock |
| TC-P2-02 | 전체 | retrieve_v2 반환 | 위 3단계 완료 | RAGContext (ddl_context, documentation_context, sql_examples 포함) | `assert ctx.rag_context is not None` | - |

---

### TC-P2-03: FR-17 중복 쿼리 방지 — 동일 SQL 2회 요청

**목적**: 동일 SQL 2회 요청 시 두 번째는 Redash 신규 생성 없이 기존 query_id 반환

| TC | Step | 스텝 역할 | 인풋 | 기대 아웃풋 | assert 단언 | 비고 |
|----|------|-----------|------|------------|-------------|------|
| TC-P2-03 | Step 7 (1회차) | Redash 신규 생성 | SQL="SELECT COUNT(*) FROM ad_clicks WHERE date='2026-03-19'" | Redash POST 호출 1회, `query_id=100` 반환, DynamoDB 저장 | `assert redash_post.call_count == 1` | moto DynamoDB |
| TC-P2-03 | Step 7 (2회차) | 캐시 히트 | 동일 SQL (포맷 무관) | Redash POST 호출 0회, `query_id=100` 반환 | `assert redash_post.call_count == 0` , `assert result == 100` | 중복 방지 핵심 |

---

### TC-P2-04: FR-16 피드백 루프 — 배치 저장 전용 확인

**목적**: 👍 피드백 시 DynamoDB pending 저장, `vanna.train()` 즉시 미호출 확인

| TC | Step | 스텝 역할 | 인풋 | 기대 아웃풋 | assert 단언 | 비고 |
|----|------|-----------|------|------------|-------------|------|
| TC-P2-04 | Step 13 | 피드백 수신 | `POST /feedback {history_id="h1", feedback="positive"}` | HTTP 200, `{"status": "accepted", "trained": false}` | `assert resp.status_code == 200` , `assert resp.json()["trained"] is False` | - |
| TC-P2-04 | Step 13 | DynamoDB pending 저장 | 위 요청 처리 후 | `pending_feedbacks` 테이블에 항목 존재, `status="pending"` | `assert item["status"] == "pending"` | moto DynamoDB |
| TC-P2-04 | Step 13 | vanna.train() 미호출 | 위 요청 처리 후 | `vanna.train()` 호출 0회 | `assert mock_vanna_train.call_count == 0` | Phase 2 핵심 변경 |

---

### TC-P2-05: FR-19 비동기 쿼리 처리 — POST/GET 폴링 흐름

**목적**: `POST /query` → 202 즉시 응답 + `GET /query/{task_id}` 폴링으로 최종 결과 수신

| TC | Step | 스텝 역할 | 인풋 | 기대 아웃풋 | assert 단언 | 비고 |
|----|------|-----------|------|------------|-------------|------|
| TC-P2-05 | POST /query | 비동기 접수 | `ASYNC_QUERY_ENABLED=true`, `{"question": "어제 클릭 수", "slack_user_id": "U001"}` | HTTP 202, `{"task_id": "<uuid>", "status": "pending"}` | `assert resp.status_code == 202` , `assert "task_id" in resp.json()` | - |
| TC-P2-05 | GET /query/{task_id} (처리 중) | 폴링 — pending | task_id로 즉시 조회 | HTTP 202, `status in ("pending", "running")` | `assert resp.status_code == 202` | BackgroundTask 실행 중 |
| TC-P2-05 | GET /query/{task_id} (완료) | 폴링 — completed | 파이프라인 완료 후 조회 | HTTP 200, QueryResponse 포함 | `assert resp.status_code == 200` , `assert "sql" in resp.json()` | 완료 응답 검증 |
| TC-P2-05 | GET /query/{task_id} (없는 task) | 404 처리 | 존재하지 않는 task_id | HTTP 404 | `assert resp.status_code == 404` | 경계값 |

---

### TC-P2-06: EXPLAIN 실패 시 PipelineError 반환

**목적**: Step 6(SQLValidator)에서 EXPLAIN 실패 시 파이프라인이 적절한 에러 응답 반환

| TC | Step | 스텝 역할 | 인풋 | 기대 아웃풋 | assert 단언 | 비고 |
|----|------|-----------|------|------------|-------------|------|
| TC-P2-06 | Step 6 | EXPLAIN 검증 실패 | 의도적 잘못된 SQL (예: `"SELECT invalid syntax"`) → Athena EXPLAIN 실패 | HTTP 200, `error_code="SQL_VALIDATION_FAILED"` 또는 동등 에러 | `assert "error" in resp.json()` | SQLValidator mock |
| TC-P2-06 | Step 6 | 에러 응답 구조 | 위 실패 응답 | 에러 메시지 한국어 포함 | `assert resp.json().get("error") is not None` | PipelineError 구조 확인 |

---

### TC-P2-07: FR-11 파이프라인 완료 후 DynamoDB 이력 저장 확인

**목적**: 파이프라인 Step 11에서 `DynamoDBHistoryRecorder.record()`가 실행되어 이력이 실제 테이블에 저장됨을 확인

| TC | Step | 스텝 역할 | 인풋 | 기대 아웃풋 | assert 단언 | 비고 |
|----|------|-----------|------|------------|-------------|------|
| TC-P2-07 | Step 11 | DynamoDB 이력 저장 | 정상 질문 → 파이프라인 완료 | `ctx.history_id` 존재, moto 테이블 조회 시 항목 존재 | `assert ctx.history_id is not None`, `table.get_item(Key={"history_id": ctx.history_id})["Item"]` 존재 | moto 테이블 생성 후 E2E 실행 |
| TC-P2-07 | Step 11 | DynamoDB 장애 시 응답 정상 | Step 11에서 `ClientError` 발생 | 파이프라인 결과 정상 반환 (ctx.error 없음) | `assert ctx.error is None` | Step 11 장애가 사용자 응답에 영향 없음 |

---

### TC-P2-08: FR-18 Airflow DAG E2E — pending → trained 전체 흐름

**목적**: pending 피드백이 DAG 실행 후 ChromaDB에 학습되고 status가 `trained`로 변경됨을 확인

| TC | Step | 스텝 역할 | 인풋 | 기대 아웃풋 | assert 단언 | 비고 |
|----|------|-----------|------|------------|-------------|------|
| TC-P2-08 | Task 1 | pending 항목 추출 | 테이블에 valid SQL 2건 pending | 2건 추출 | `assert len(pending) == 2` | moto 테이블 |
| TC-P2-08 | Task 2 | EXPLAIN 검증 통과 | Athena EXPLAIN mock → 성공 | 2건 모두 필터 통과 | `assert len(validated) == 2` | Athena mock |
| TC-P2-08 | Task 3 | ChromaDB 학습 + trained 마킹 | 검증된 2건 | `vanna.train()` 2회, 테이블 `status="trained"` | `assert mock_train.call_count == 2`, `assert item["status"] == "trained"` | vanna mock |

---

### TC-P2-09: FR-18 DAG — 0건 ShortCircuit

**목적**: pending 항목이 없을 때 DAG이 조기 종료되고 이후 Task가 실행되지 않음을 확인

| TC | Step | 스텝 역할 | 인풋 | 기대 아웃풋 | assert 단언 | 비고 |
|----|------|-----------|------|------------|-------------|------|
| TC-P2-09 | Task 1 | 0건 ShortCircuit | 빈 테이블 | `extract_pending_feedbacks()` → `[]`, Task 2/3 미실행 | `assert result == []`, `assert mock_train.call_count == 0` | 경계값 |

---

### TC-P2-10: FR-19 비동기 FAILED 상태 처리

**목적**: 파이프라인 내부 예외 발생 시 `GET /query/{task_id}` 폴링에서 FAILED 상태 반환

| TC | Step | 스텝 역할 | 인풋 | 기대 아웃풋 | assert 단언 | 비고 |
|----|------|-----------|------|------------|-------------|------|
| TC-P2-10 | POST /query | 비동기 접수 | `ASYNC_QUERY_ENABLED=true`, 의도적 실패 유발 질문 | HTTP 202, task_id 반환 | `assert resp.status_code == 202` | - |
| TC-P2-10 | GET /query/{task_id} | FAILED 상태 폴링 | 파이프라인 예외 발생 후 조회 | HTTP 200, `status="failed"`, error 메시지 포함 | `assert resp.json()["status"] == "failed"`, `assert "error" in resp.json()` | BackgroundTask 예외 처리 |

---

### TC-P2-11: FR-19 `ASYNC_QUERY_ENABLED=false` — 동기 경로 하위 호환성

**목적**: 플래그 비활성 시 POST /query가 202가 아닌 200으로 직접 결과 반환 (Slack Bot 하위 호환)

| TC | Step | 스텝 역할 | 인풋 | 기대 아웃풋 | assert 단언 | 비고 |
|----|------|-----------|------|------------|-------------|------|
| TC-P2-11 | POST /query | 동기 즉시 응답 | `ASYNC_QUERY_ENABLED=false`, 정상 질문 | HTTP 200, QueryResponse 본문 직접 포함 | `assert resp.status_code == 200`, `assert "sql" in resp.json()` | 202 아님 주의 |
| TC-P2-11 | POST /query | task_id 미포함 | 동기 응답 확인 | 응답 바디에 `task_id` 필드 없음 | `assert "task_id" not in resp.json()` | 비동기 응답과 구분 |

---

### TC-P2-12: RAGRetriever 에러 처리 — 파이프라인 계속 진행 (FR-12)

**목적**: Step 4에서 RAG 실패 시 빈 RAGContext로 SQL 생성을 계속 시도하는지 검증

| TC | Step | 스텝 역할 | 인풋 | 기대 아웃풋 | assert 단언 | 비고 |
|----|------|-----------|------|------------|-------------|------|
| TC-P2-12 | Step 4-1 | 벡터 검색 실패 → 파이프라인 계속 | `_retrieve_candidates()` → `RuntimeError`, 이후 Steps는 정상 | `ctx.error`가 없거나 Step 4 이후 단계에서 에러 (Step 4 자체에서 중단 안 됨), `ctx.rag_context == RAGContext()` | `assert ctx.rag_context is not None`, `assert ctx.rag_context.ddl_context == []` | 설계 §3.6: 빈 RAGContext로 LLM 자체 지식 활용 |
| TC-P2-12 | Step 4-3 | LLM 선별 실패 → Reranker 결과로 계속 | `_llm_filter()` → `Exception` | `ctx.rag_context`가 None이 아님, Reranker 상위 결과 기반 RAGContext 반환 | `assert ctx.rag_context is not None` | graceful degradation E2E |

---

### TC-P2-13: AsyncQueryManager DynamoDB 영속성 E2E (FR-19)

**목적**: POST /query로 생성된 task가 DynamoDB에 저장되고, GET /query/{task_id}가 DynamoDB에서 올바르게 조회하는지 검증

| TC | Step | 스텝 역할 | 인풋 | 기대 아웃풋 | assert 단언 | 비고 |
|----|------|-----------|------|------------|-------------|------|
| TC-P2-13 | POST /query | task 생성 + DynamoDB 저장 확인 | `ASYNC_QUERY_ENABLED=true`, 정상 질문 | HTTP 202, task_id 반환, moto 테이블에 `status="pending"` 항목 존재 | `assert resp.status_code == 202`, `table.get_item(Key={"task_id": task_id})["Item"]["status"] == "pending"` | moto 테이블 직접 조회 |
| TC-P2-13 | GET /query/{task_id} | DynamoDB 조회 → 응답 변환 | 파이프라인 완료 후 task_id 조회 | HTTP 200, DynamoDB `status="completed"`, 응답 본문에 결과 포함 | `assert item["status"] == "completed"`, `assert "sql" in resp.json()` | DynamoDB → API 응답 변환 검증 |

---

### TC-P2-14: POST /feedback E2E — history 조회 → pending 저장 전체 흐름 (FR-16)

**목적**: 피드백 API가 history 테이블 조회 후 feedback 테이블에 pending 저장하는 전체 흐름 검증

| TC | Step | 스텝 역할 | 인풋 | 기대 아웃풋 | assert 단언 | 비고 |
|----|------|-----------|------|------------|-------------|------|
| TC-P2-14 | POST /feedback | history 조회 → pending 저장 | `{history_id: "h1", feedback: "positive"}`, moto history 테이블에 `h1` 존재 | HTTP 200, feedback 테이블에 `status="pending"`, `history_id="h1"` 항목 존재 | `assert resp.status_code == 200`, `assert fb_item["history_id"] == "h1"`, `assert fb_item["status"] == "pending"` | 두 테이블 모두 moto로 생성 |
| TC-P2-14 | POST /feedback | history 없을 때 오류 반환 | `{history_id: "nonexistent", feedback: "positive"}` | HTTP 404 또는 400, 에러 메시지 포함 | `assert resp.status_code in (400, 404)` | history 조회 실패 경로 E2E |

---

### TC-P2-15: DAG 부분 실패 E2E — train_failed 마킹 후 계속 진행 (FR-18)

**목적**: 일부 항목 학습 실패 시 해당 항목만 train_failed로 마킹되고 나머지는 정상 처리되는지 검증

| TC | Step | 스텝 역할 | 인풋 | 기대 아웃풋 | assert 단언 | 비고 |
|----|------|-----------|------|------------|-------------|------|
| TC-P2-15 | Task 3 (부분 실패) | 3건 중 1건 실패 → train_failed, 나머지 trained | 2번째 항목 `vanna.train()` → `Exception` | 1번째 `status="trained"`, 2번째 `status="train_failed"`, 3번째 `status="trained"` | `assert mock_train.call_count == 3`, `assert items[0]["status"] == "trained"`, `assert items[1]["status"] == "train_failed"`, `assert items[2]["status"] == "trained"` | 전체 3건 DynamoDB 조회로 최종 상태 확인 |

---

### TC-P2-16: DELETE /training-data/{id} 실패 E2E (FR-13~15)

**목적**: ChromaDB 삭제 실패 시 HTTP 400이 FastAPI까지 전파되는지 E2E 검증

| TC | Step | 스텝 역할 | 인풋 | 기대 아웃풋 | assert 단언 | 비고 |
|----|------|-----------|------|------------|-------------|------|
| TC-P2-16 | DELETE /training-data/{id} | ChromaDB 삭제 실패 → 400 전파 | 존재하는 id, `vanna.delete_training_data()` → `Exception` | HTTP 400, 에러 메시지 한국어 포함 | `assert resp.status_code == 400`, `assert resp.json().get("detail") is not None` | 에러가 API 레이어까지 올바르게 전파되는지 확인 |

---

## 섹션 3: 배포 후 테스트 (Deployment Tests)

> 본 섹션은 단위/통합 테스트 통과 후 EKS 클러스터(capa-cluster) 배포 시 진행한다. 포트포워딩(`kubectl port-forward -n vanna svc/vanna-api 8080:8000`) 또는 Pod 직접 접근으로 실제 Athena/DynamoDB 연동을 검증한다.

---

## 섹션 4: 테스트 환경 및 사전 조건

### 4.0 인프라 준비 상태

| 항목 | 상태 | 적용일 |
|------|------|-------|
| `capa-dev-query-history` DynamoDB 테이블 | ✅ ACTIVE | 2026-03-20 |
| `capa-dev-pending-feedbacks` DynamoDB 테이블 | ✅ ACTIVE | 2026-03-20 |
| vanna IRSA → DynamoDB IAM 연결 | ✅ 완료 | 2026-03-20 |
| RedashConfig.dynamodb_table 필드 추가 | ✅ 완료 | 2026-03-20 |

**로컬 테스트 준비**: AWS CLI로 `ai-en-6` 자격증명을 통해 DynamoDB 접근 가능
```bash
aws dynamodb list-tables --region ap-northeast-2
```

**EKS 배포**: Pod 자동으로 IRSA를 통해 DynamoDB 접근 가능 (별도 설정 불필요)

---

### 4.1 필수 패키지

```
Python      3.11+
pytest      7.0+
pytest-asyncio  0.23+
moto[dynamodb]  5.0+
httpx       0.27+          (RedashClient httpx mock)
pytest-mock 3.12+          (MagicMock / patch)
```

### 4.2 환경 변수 (단위/통합 테스트용)

| 변수명 | 단위 테스트 값 | 통합 테스트 값 | 설명 |
|--------|--------------|--------------|------|
| `PHASE2_RAG_ENABLED` | `false` / `true` (TC별 지정) | `true` | 3단계 RAG 활성화 여부 |
| `ASYNC_QUERY_ENABLED` | `false` / `true` (TC별 지정) | `true` | 비동기 쿼리 활성화 여부 |
| `ANTHROPIC_API_KEY` | `test-key` (mock) | `test-key` (mock) | LLM 선별용 |
| `REDASH_ENABLED` | `false` | `true` | Redash 연동 여부 |
| `DYNAMODB_HISTORY_TABLE` | `test-query-history` | `test-query-history` | moto DynamoDB 테이블명 |
| `DYNAMODB_FEEDBACK_TABLE` | `test-pending-feedbacks` | `test-pending-feedbacks` | moto DynamoDB 테이블명 |
| `RERANKER_MODEL_NAME` | `cross-encoder/ms-marco-MiniLM-L-6-v2` | 동일 | Reranker 모델명 |

### 4.3 Mock 전략

| 대상 | Mock 방법 | 비고 |
|------|-----------|------|
| AWS DynamoDB | `moto` `@mock_aws` + `boto3.resource("dynamodb", region_name="us-east-1")` | 테이블 사전 생성 필요 |
| Redash API | `pytest.mock.AsyncMock` + `httpx` mock (`respx` 또는 `unittest.mock.patch`) | `create_query()` 응답 mock |
| Vanna (ChromaDB) | `pytest.mock.MagicMock` | `get_related_ddl`, `get_related_documentation`, `get_similar_question_sql` mock |
| sentence-transformers `CrossEncoder` | `pytest.mock.MagicMock` | `predict()` 반환값 지정 |
| Anthropic Claude | `pytest.mock.AsyncMock` | `_llm_filter()` 내부 anthropic 클라이언트 mock |
| AWS Athena | `moto` 또는 `MagicMock` | EXPLAIN 검증 단계 mock |

### 4.4 moto DynamoDB 테이블 초기화 예시

```python
import boto3
from moto import mock_aws

@pytest.fixture
def dynamodb_feedback_table():
    with mock_aws():
        db = boto3.resource("dynamodb", region_name="us-east-1")
        table = db.create_table(
            TableName="test-pending-feedbacks",
            KeySchema=[{"AttributeName": "feedback_id", "KeyType": "HASH"}],
            AttributeDefinitions=[{"AttributeName": "feedback_id", "AttributeType": "S"}],
            BillingMode="PAY_PER_REQUEST",
        )
        yield table
```

### 4.5 TC ID 규칙

| 접두사 | 범위 | 예시 |
|--------|------|------|
| `TC-P2-U` | 단위 테스트 | TC-P2-U01 ~ TC-P2-U24 |
| `TC-P2-` (숫자 2자리) | 통합 테스트 | TC-P2-01 ~ TC-P2-06 |

---

## 요약

| 구분 | TC 수 | 대상 컴포넌트 | 관련 FR |
|------|:-----:|-------------|---------|
| 단위 — sql_hash | 8 | `sql_hash.py` | FR-17 |
| 단위 — reranker | 5 | `reranker.py` | FR-12 |
| 단위 — dynamodb_feedback | 6 | `dynamodb_feedback.py` | FR-16 |
| 단위 — create_or_reuse_query | 5 | `redash_client.py` | FR-17 |
| 단위 — dynamodb_history | 5 | `dynamodb_history.py` | FR-11 |
| 단위 — airflow_dag | 6 | `capa_chromadb_refresh.py` | FR-18 |
| 단위 — DELETE /training-data | 3 | FastAPI endpoint | FR-13~15 |
| 단위 — PipelineContext.sql_hash | 2 | `query_pipeline.py` | FR-17 |
| 단위 — RAGRetriever 메서드 + 에러처리 | 8 | `rag_retriever.py` | FR-12 |
| 단위 — AsyncQueryManager | 4 | `async_query_manager.py` | FR-19 |
| 단위 — FeedbackManager | 3 | `feedback_manager.py` | FR-16 |
| 단위 — batch_train 부분 실패 | 1 | `capa_chromadb_refresh.py` | FR-18 |
| 단위 — DELETE 실패 400 | 1 | FastAPI endpoint | FR-13~15 |
| 통합 — RAG 분기 | 1 | QueryPipeline | FR-12 |
| 통합 — 3단계 RAG | 4 | RAGRetriever | FR-12 |
| 통합 — 중복 쿼리 방지 | 2 | RedashClient + DynamoDB | FR-17 |
| 통합 — 피드백 루프 | 3 | FeedbackManager | FR-16 |
| 통합 — 비동기 쿼리 | 4 | AsyncQueryManager + FastAPI | FR-19 |
| 통합 — EXPLAIN 실패 | 2 | SQLValidator | FR-12 |
| 통합 — DynamoDB 이력 저장 | 2 | DynamoDBHistoryRecorder | FR-11 |
| 통합 — Airflow DAG E2E | 5 | capa_chromadb_refresh | FR-18 |
| 통합 — 비동기 FAILED + 동기 경로 | 4 | AsyncQueryManager + FastAPI | FR-19 |
| 통합 — RAGRetriever 에러 처리 E2E | 2 | RAGRetriever + QueryPipeline | FR-12 |
| 통합 — AsyncQueryManager DynamoDB 영속성 | 2 | AsyncQueryManager + DynamoDB | FR-19 |
| 통합 — POST /feedback E2E | 2 | FeedbackManager + DynamoDB | FR-16 |
| 통합 — DAG 부분 실패 E2E | 1 | capa_chromadb_refresh | FR-18 |
| 통합 — DELETE 실패 E2E | 1 | FastAPI + Vanna | FR-13~15 |
| **합계** | **87** | — | — |

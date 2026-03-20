# [Test Plan] Text-To-SQL Phase 2 RAG 고도화

## 문서 메타

| 항목 | 내용 |
|------|------|
| **문서 유형** | 테스트 계획서 (Test Plan) |
| **작성일** | 2026-03-20 |
| **담당** | t1 |
| **대상** | Phase 2 RAG 고도화 (FR-12, FR-16, FR-18, FR-19) |
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
**요구사항 (FR)**: **FR-17** — SQL 해시 중복 쿼리 방지

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
**요구사항 (FR)**: **FR-12** — 3단계 RAG 고도화 (Step 4-2: Reranker)

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
**요구사항 (FR)**: **FR-16** — 피드백 루프 품질 제어 (pending_feedbacks 테이블)

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

### 1.5 `dynamodb_history.py` — DynamoDB 이력 저장

**대상 파일**: `services/vanna-api/src/stores/dynamodb_history.py`
**검증 클래스**: `DynamoDBHistoryRecorder.record()`, `get_record()`, `update_feedback()`
**요구사항 (FR)**: **FR-11** — History 저장소 전환 (JSON Lines → DynamoDB query_history 테이블)

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

### 1.6 Airflow DAG `capa_chromadb_refresh` — 배치 학습

**대상 파일**: `services/airflow-dags/dags/capa_chromadb_refresh.py`
**검증 함수**: `extract_pending_feedbacks()`, `validate_and_deduplicate()`, `batch_train_chromadb()`
**요구사항 (FR)**: **FR-18** — 피드백 루프 자동 학습 (Airflow DAG: pending_feedbacks → validate → train → ChromaDB)

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

### 1.7 `DELETE /training-data/{id}` — 학습 데이터 삭제

**대상**: `DELETE /training-data/{id}` FastAPI 엔드포인트
**검증**: ChromaDB 벡터 삭제, 존재하지 않는 id 처리, 인증 검증
**요구사항 (FR)**: **FR-13~15** — 학습 데이터 관리 (삭제, 선별, 검증)

| TC | Step | 스텝 역할 | 인풋 | 기대 아웃풋 | assert 단언 | 비고 |
|----|------|-----------|------|------------|-------------|------|
| TC-P2-U36 | DELETE /training-data/{id} | 정상 삭제 | 존재하는 벡터 id, 인증 헤더 포함 | HTTP 200, `vanna.delete_training_data()` 1회 호출 | `assert resp.status_code == 200`, `assert mock_delete.call_count == 1` | vanna mock |
| TC-P2-U37 | DELETE /training-data/{id} | 존재하지 않는 id | `id="nonexistent-id"` | HTTP 404, 에러 메시지 한국어 | `assert resp.status_code == 404` | - |
| TC-P2-U38 | DELETE /training-data/{id} | 인증 없는 요청 | Authorization 헤더 없음 | HTTP 401 | `assert resp.status_code == 401` | 무단 삭제 방지 |

---

### 1.9 `RAGRetriever` 메서드 단위 테스트

**대상 파일**: `services/vanna-api/src/pipeline/rag_retriever.py`
**검증 메서드**: `retrieve_v2()`, `_retrieve_candidates()`, `_llm_filter()`
**요구사항 (FR)**: **FR-12** — 3단계 RAG 고도화 (Step 4: 벡터검색→Reranker→LLM선별)

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

### 1.10 `AsyncQueryManager` 단위 테스트

**대상 파일**: `services/vanna-api/src/pipeline/async_query_manager.py`
**검증 메서드**: `create_task()`, `update_status()`, `get_task()`
**요구사항 (FR)**: **FR-19** — 비동기 쿼리 태스크 관리 (pending_feedbacks 테이블 기반)

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

### 1.11 `FeedbackManager.record_positive()` 단위 테스트

**대상 파일**: `services/vanna-api/src/pipeline/feedback_manager.py` (또는 동등 파일)
**검증 메서드**: `FeedbackManager.record_positive()`
**요구사항 (FR)**: **FR-16** — 피드백 루프 자동화 (positive/negative 기록)

> moto로 history 테이블 + feedback 테이블 동시 생성

| TC | Step | 스텝 역할 | 인풋 | 기대 아웃풋 | assert 단언 | 비고 |
|----|------|-----------|------|------------|-------------|------|
| TC-P2-U53 | record_positive | 정상 — history 존재 | `history_id` 있음 (테이블에 항목 존재) | `(True, feedback_id)` 반환, feedback 테이블에 `status="pending"` 저장 | `assert result[0] is True`, `assert feedback_table.get_item(...)["Item"]["status"] == "pending"` | 즉시 학습 없음 확인 (`mock_vanna_train.call_count == 0`) |
| TC-P2-U54 | record_positive | history_id 없음 → 실패 | `history_id="nonexistent"` | `(False, "이력 레코드를 찾을 수 없습니다")` 반환 | `assert result[0] is False`, `assert "이력" in result[1]` | - |
| TC-P2-U55 | record_positive | DynamoDB 장애 시 처리 | feedback `put_item` → `ClientError` | `(False, ...)` 반환 또는 예외 미전파 | `assert result[0] is False` | 장애 격리 |

---

### 1.12 `batch_train_chromadb()` 부분 실패 케이스

**대상 파일**: `services/airflow-dags/dags/capa_chromadb_refresh.py`
**요구사항 (FR)**: **FR-18** — 피드백 루프 자동 학습 (에러 처리)

| TC | Step | 스텝 역할 | 인풋 | 기대 아웃풋 | assert 단언 | 비고 |
|----|------|-----------|------|------------|-------------|------|
| TC-P2-U56 | batch_train_chromadb | 개별 항목 train 실패 → train_failed + 계속 진행 | 3건 중 2번째 항목에서 `vanna.train()` → `Exception` | 1번째 `status="trained"`, 2번째 `status="train_failed"`, 3번째 `status="trained"` — 전체 3건 처리 완료 | `assert mock_train.call_count == 3`, `assert items[0]["status"] == "trained"`, `assert items[1]["status"] == "train_failed"`, `assert items[2]["status"] == "trained"` | 설계 §5.3 Task 3 에러 처리 |

---

### 1.13 `DELETE /training-data/{id}` 삭제 실패 400

**요구사항 (FR)**: **FR-13~15** — 학습 데이터 관리 (삭제 실패 처리)

| TC | Step | 스텝 역할 | 인풋 | 기대 아웃풋 | assert 단언 | 비고 |
|----|------|-----------|------|------------|-------------|------|
| TC-P2-U57 | DELETE /training-data/{id} | ChromaDB 삭제 실패 → 400 | 존재하는 id, `vanna.delete_training_data()` → `Exception` | HTTP 400, 에러 메시지 포함 | `assert resp.status_code == 400` | 설계 §4.3.2 명시 케이스 |

---

## 섹션 2: 통합 테스트 (Integration Tests)

> **통합 테스트 원칙**: Phase 1 통합 테스트(`plan-phase-1-tests/phase-2-integration-test-plan.md`)에서 검증 완료된 스텝(Step 1~3, 5~6, 9~10)은 본 섹션에서 기본 통과 확인(`assert http_status == 200`)만 수행하며, 상세 assert는 생략하고 "Phase 1 완료" 주석으로 표기한다.
> Phase 2 신규 기능(Step 4 Reranker, Step 7~8 query_id 캐시, Step 11 DynamoDB 이력, 피드백 pending 저장, 비동기 쿼리, Airflow DAG 배치 학습, DELETE /training-data)에 집중하여 검증한다.
>
> **실제 AWS DynamoDB 사용**: 단위 테스트와 달리 통합/배포 후 테스트에서는 moto 에뮬레이션이 아닌 실제 AWS DynamoDB(`capa-dev-query-history`, `capa-dev-pending-feedbacks`) 테이블을 사용한다. 조회 명령은 AWS CLI로 수행한다.
>
> **로컬 환경**: Docker Compose(vanna-api + ChromaDB + Redash) + Airflow 로컬 설치(localhost:8080)
>
> **공통 PowerShell 변수** (모든 TC에서 동일하게 사용):
> ```powershell
> $API_BASE = "http://localhost:8000"
> $TOKEN = "test-token"
> ```

---

### 2.0 파이프라인 스텝별 테스트 범위

#### Phase 1 완료 항목 (기본 통과 확인만)

| Step | 내용 | 테스트 계획서 |
|------|------|--------------|
| Step 1 | 의도 분류 (DATA_QUERY / GENERAL 분기) | `plan-phase-1-tests/phase-2-integration-test-plan.md` TC-A, TC-B |
| Step 2 | 질문 정제 (QuestionRefiner) | 동일 문서 |
| Step 3 | 키워드 추출 (KeywordExtractor) | 동일 문서 |
| Step 5 | SQL 생성 (VannaSQLGenerator) | 동일 문서 |
| Step 6 | SQL 검증 (SQLValidator — EXPLAIN) | 동일 문서 |
| Step 9 | Athena 직접 실행 (Redash 실패 fallback) | 동일 문서 |
| Step 10 | AI 분석 + 차트 추천 | 동일 문서 |
| EX-1~10 | 에러 케이스 (의도 분류 실패, SQL 생성 실패, 타임아웃 등) | 동일 문서 |
| SEC | 보안 검증 (인증 토큰, Rate Limit) | 동일 문서 |

#### Phase 2 신규 검증 항목

| TC ID | Step | Phase 2 신규 기능 | 관련 FR |
|-------|------|-----------------|---------|
| TC-IT-P2-01 | Step 4 | 3단계 RAG (CrossEncoderReranker + LLM filter) | FR-12 |
| TC-IT-P2-02 | Step 11 | DynamoDB 쿼리 이력 저장 | FR-11 |
| TC-IT-P2-04 | Feedback | 피드백 pending 저장 (즉시 학습 제거) | FR-16 |
| TC-IT-P2-05 | Async | 비동기 쿼리 (202 즉시 응답 + 폴링) | FR-19 |
| TC-IT-P2-06 | DELETE | DELETE /training-data/{id} | FR-13~15 |
| TC-IT-P2-07 | Airflow | Airflow DAG 배치 학습 (pending → trained) | FR-18 |
| TC-IT-E2E-01 | 전체 | Phase 1 + Phase 2 전체 흐름 E2E | FR-11~19 |

---

### 2.1 테스트 환경 구성

#### 2.1.1 .env 파일 (Phase 2 추가 설정)

Phase 1 `.env`에 아래 변수를 추가한다. 민감 정보는 `<실제값>` 플레이스홀더로 표기한다.

```dotenv
# === Phase 2 신규 추가 변수 ===

# 3단계 RAG 활성화 (true: CrossEncoderReranker + LLM filter 사용)
PHASE2_RAG_ENABLED=true

# 비동기 쿼리 활성화 (true: POST /query → 202, GET /query/{task_id} 폴링)
ASYNC_QUERY_ENABLED=true

# DynamoDB 연동 활성화
DYNAMODB_ENABLED=true

# DynamoDB 테이블명 (실제 AWS에 생성된 테이블)
DYNAMODB_HISTORY_TABLE=capa-dev-query-history
DYNAMODB_FEEDBACK_TABLE=capa-dev-pending-feedbacks

# Phase 2 피드백 루프 활성화 (true: pending 저장 방식, false: Phase 1 즉시 학습)
PHASE2_FEEDBACK_ENABLED=true

# Reranker 모델명 (sentence-transformers)
RERANKER_MODEL_NAME=cross-encoder/ms-marco-MiniLM-L-6-v2

# AWS 자격증명 (로컬 테스트용 — ai-en-6 계정)
AWS_ACCESS_KEY_ID=<실제값>
AWS_SECRET_ACCESS_KEY=<실제값>
AWS_DEFAULT_REGION=ap-northeast-2
```

#### 2.1.2 환경 적용 후 vanna-api 재시작

```powershell
# Docker Compose 재시작 (환경변수 재적용)
docker compose down
docker compose --env-file .env up -d

# 로그 확인
docker compose logs -f vanna-api
```

#### 2.1.3 Phase 2 환경 스모크 테스트

환경 구성 후 `/health` 엔드포인트에서 DynamoDB 연결 상태를 확인한다.

```powershell
# /health 응답에서 dynamodb: connected 확인
$response = Invoke-RestMethod -Uri "$API_BASE/health" -Method GET
$response | ConvertTo-Json

# 기대 응답 예시:
# {
#   "status": "healthy",
#   "dynamodb": "connected",
#   "chromadb": "connected",
#   "phase2_rag_enabled": true,
#   "async_query_enabled": true
# }
```

| 항목 | 기대값 | assert |
|------|--------|--------|
| `status` | `"healthy"` | `assert response["status"] == "healthy"` |
| `dynamodb` | `"connected"` | `assert response["dynamodb"] == "connected"` |
| `phase2_rag_enabled` | `true` | `assert response["phase2_rag_enabled"] == True` |

---

### 2.2 기능별 통합 테스트

---

#### TC-IT-P2-01: 3단계 RAG 동작 확인 (Step 4, FR-12)

**목적**: `PHASE2_RAG_ENABLED=true` 환경에서 POST /query 실행 시 CrossEncoderReranker와 LLM filter가 실제로 호출되는지 확인.
**사전 조건**: ChromaDB에 DDL/문서/SQL 예제 시딩 완료.

**Phase 1에서 이미 검증된 스텝**:

| Step | 내용 | Phase 1 결과 |
|------|------|-------------|
| Step 1 | 의도 분류 | 완료 — 기본 통과만 확인 |
| Step 2 | 질문 정제 | 완료 — 기본 통과만 확인 |
| Step 3 | 키워드 추출 | 완료 — 기본 통과만 확인 |
| Step 5 | SQL 생성 | 완료 — 기본 통과만 확인 |
| Step 6 | SQL 검증 | 완료 — 기본 통과만 확인 |

**테스트 명령**:

```powershell
# POST /query 실행
$body = @{
    question = "2026-02-01 캠페인별 CTR 알려줘"
    slack_user_id = "test-user"
} | ConvertTo-Json

$response = Invoke-RestMethod `
    -Uri "$API_BASE/query" `
    -Method POST `
    -ContentType "application/json" `
    -Headers @{ Authorization = "Bearer $TOKEN" } `
    -Body $body

$response | ConvertTo-Json -Depth 5

# Reranker 호출 로그 확인
docker compose logs vanna-api | Select-String -Pattern "Reranker|rerank|CrossEncoder"
```

| TC | Step | 스텝 역할 | 인풋 | 아웃풋 (실제값) | assert 단언 | 판정 | 비고 |
|----|------|-----------|------|----------------|-------------|------|------|
| TC-IT-P2-01 | Step 1~3 | 의도 분류·정제·키워드 추출 | 질문 "2026-02-01 캠페인별 CTR 알려줘" | `http_status == 200` | `assert http_status == 200` | | Phase 1 완료 항목 |
| TC-IT-P2-01 | Step 4 | 3단계 RAG 실행 | `PHASE2_RAG_ENABLED=true` | `response["rag_results"]["ddl_count"] >= 1` | `assert response["rag_results"]["ddl_count"] >= 1` | | Phase 2 신규 |
| TC-IT-P2-01 | Step 4-2 | Reranker 호출 확인 | Step 4-1 결과 | `response["rag_results"]["reranked"] == True` (또는 로그에 Reranker 출력 존재) | `assert response["rag_results"]["reranked"] == True` | | `docker compose logs`로 교차 확인 |
| TC-IT-P2-01 | Step 5~6 | SQL 생성·검증 | Phase 2 RAG context | `http_status == 200` | `assert http_status == 200` | | Phase 1 완료 항목 |

**성공 기준**: Step 4 assert 2건 모두 통과 + Reranker 로그 확인

---

#### TC-IT-P2-02: DynamoDB 쿼리 이력 저장 (Step 11, FR-11)

**목적**: 파이프라인 완료 후 `history_id`가 응답에 포함되고, 실제 AWS DynamoDB `capa-dev-query-history` 테이블에 항목이 저장되는지 확인.
**사전 조건**: `DYNAMODB_ENABLED=true`, `capa-dev-query-history` 테이블 ACTIVE 상태.

**Phase 1에서 이미 검증된 스텝**:

| Step | 내용 | Phase 1 결과 |
|------|------|-------------|
| Step 1~6 | 의도 분류 ~ SQL 검증 | 완료 — 기본 통과만 확인 |
| Step 9~10 | Athena 실행 / AI 분석 | 완료 — 기본 통과만 확인 |

**테스트 명령**:

```powershell
# Step 1: POST /query 실행
$body = @{
    question = "어제 광고 클릭 수 알려줘"
    slack_user_id = "test-user"
} | ConvertTo-Json

$response = Invoke-RestMethod `
    -Uri "$API_BASE/query" `
    -Method POST `
    -ContentType "application/json" `
    -Headers @{ Authorization = "Bearer $TOKEN" } `
    -Body $body

$historyId = $response.history_id
Write-Host "history_id: $historyId"

# Step 2: AWS CLI로 DynamoDB 직접 조회 (실제 AWS 테이블)
aws dynamodb get-item `
    --table-name capa-dev-query-history `
    --key "{`"history_id`": {`"S`": `"$historyId`"}}" `
    --region ap-northeast-2
```

| TC | Step | 스텝 역할 | 인풋 | 아웃풋 (실제값) | assert 단언 | 판정 | 비고 |
|----|------|-----------|------|----------------|-------------|------|------|
| TC-IT-P2-02 | Step 11 | history_id 응답 포함 | POST /query 응답 | `response["history_id"] is not None` | `assert response["history_id"] is not None` | | Phase 2 신규 |
| TC-IT-P2-02 | Step 11 | DynamoDB 항목 존재 | AWS CLI get-item 결과 | `Item` 키 존재 | `assert "Item" in dynamodb_result` | | 실제 AWS DynamoDB 조회 |
| TC-IT-P2-02 | Step 11 | 저장 필드 확인 | DynamoDB Item 내용 | `item["question"]`, `item["sql"]`, `item["ttl"]` 필드 존재 | `assert all(f in item for f in ["question", "sql", "ttl"])` | | TTL 90일 설정 검증 포함 |

**성공 기준**: assert 3건 모두 통과

---

#### TC-IT-P2-04: Phase 2 피드백 루프 — pending 저장 (FR-16)

**목적**: 긍정 피드백 시 `trained=false`(즉시 학습 없음)로 응답하고, AWS DynamoDB `capa-dev-pending-feedbacks` 테이블에 `status=pending`으로 저장되는지 확인. Phase 1과의 동작 차이(Phase 1: `trained=true`) 교차 검증.
**사전 조건**: TC-IT-P2-02 완료로 `history_id` 확보, `PHASE2_FEEDBACK_ENABLED=true`.

**테스트 명령**:

```powershell
# Step 1: POST /query로 history_id 획득
$qBody = @{ question = "어제 클릭 수 알려줘"; slack_user_id = "test-user" } | ConvertTo-Json
$qResp = Invoke-RestMethod -Uri "$API_BASE/query" -Method POST `
    -ContentType "application/json" `
    -Headers @{ Authorization = "Bearer $TOKEN" } -Body $qBody
$historyId = $qResp.history_id

# Step 2: POST /feedback
$fbBody = @{
    history_id = $historyId
    feedback   = "positive"
    slack_user_id = "test-user"
} | ConvertTo-Json

$fbResp = Invoke-RestMethod `
    -Uri "$API_BASE/feedback" -Method POST `
    -ContentType "application/json" `
    -Headers @{ Authorization = "Bearer $TOKEN" } `
    -Body $fbBody

Write-Host "trained: $($fbResp.trained)"

# Step 3: AWS CLI로 pending_feedbacks 테이블 스캔
aws dynamodb scan `
    --table-name capa-dev-pending-feedbacks `
    --region ap-northeast-2
```

| TC | Step | 스텝 역할 | 인풋 | 아웃풋 (실제값) | assert 단언 | 판정 | 비고 |
|----|------|-----------|------|----------------|-------------|------|------|
| TC-IT-P2-04 | POST /feedback | 즉시 응답 확인 | `{history_id, feedback: "positive"}` | HTTP 200, `trained == false` | `assert fbResp.trained == False` | | Phase 1(`trained=true`)과 다름 — Phase 2 핵심 |
| TC-IT-P2-04 | DynamoDB 저장 | pending 항목 존재 | AWS CLI scan 결과 | `Count >= 1`, `item["status"] == "pending"` | `assert scan_result["Count"] >= 1` | | 실제 AWS DynamoDB 스캔 |
| TC-IT-P2-04 | DynamoDB 저장 | history_id 연결 확인 | scan 결과 Item 내용 | `item["history_id"] == historyId` | `assert item["history_id"] == historyId` | | 피드백-이력 연결 검증 |

**성공 기준**: assert 3건 모두 통과

---

#### TC-IT-P2-05: 비동기 쿼리 — 202 즉시 응답 + 폴링 (FR-19)

**목적**: `ASYNC_QUERY_ENABLED=true` 환경에서 POST /query가 202를 즉시 반환하고, GET /query/{task_id} 폴링으로 최종 결과를 수신하는 전체 흐름 확인.
**사전 조건**: `ASYNC_QUERY_ENABLED=true`.

**테스트 명령**:

```powershell
# Step 1: POST /query → 202
$body = @{ question = "어제 캠페인별 클릭 수"; slack_user_id = "test-user" } | ConvertTo-Json
$resp202 = Invoke-WebRequest `
    -Uri "$API_BASE/query" -Method POST `
    -ContentType "application/json" `
    -Headers @{ Authorization = "Bearer $TOKEN" } -Body $body

Write-Host "HTTP Status: $($resp202.StatusCode)"
$taskId = ($resp202.Content | ConvertFrom-Json).task_id
Write-Host "task_id: $taskId"

# Step 2: GET /query/{task_id} 폴링 (1초 간격, 3회)
for ($i = 1; $i -le 3; $i++) {
    Start-Sleep -Seconds 1
    $pollResp = Invoke-RestMethod `
        -Uri "$API_BASE/query/$taskId" -Method GET `
        -Headers @{ Authorization = "Bearer $TOKEN" }
    Write-Host "폴링 $i 회차: status=$($pollResp.status)"
    if ($pollResp.status -eq "completed") { break }
}

# Step 3: 없는 task_id 조회 → 404 확인
try {
    Invoke-RestMethod -Uri "$API_BASE/query/nonexistent-task-id" `
        -Method GET -Headers @{ Authorization = "Bearer $TOKEN" }
} catch {
    Write-Host "404 응답 확인: $($_.Exception.Response.StatusCode)"
}
```

| TC | Step | 스텝 역할 | 인풋 | 아웃풋 (실제값) | assert 단언 | 판정 | 비고 |
|----|------|-----------|------|----------------|-------------|------|------|
| TC-IT-P2-05 | POST /query | 202 즉시 응답 | `ASYNC_QUERY_ENABLED=true`, 질문 | HTTP 202, `task_id` 포함 | `assert resp202.StatusCode == 202` | | 동기 200이면 실패 |
| TC-IT-P2-05 | GET 폴링 (처리 중) | pending/running 상태 | task_id 즉시 조회 | `status in ("pending", "running")` | `assert pollResp.status in ("pending", "running")` | | BackgroundTask 실행 확인 |
| TC-IT-P2-05 | GET 폴링 (완료) | completed + 결과 포함 | 파이프라인 완료 후 조회 | HTTP 200, `sql` 필드 포함 | `assert pollResp.status == "completed"` , `assert "sql" in pollResp` | | 최종 결과 구조 검증 |
| TC-IT-P2-05 | GET 없는 task_id | 404 반환 | `task_id="nonexistent-task-id"` | HTTP 404 | `assert exception.StatusCode == 404` | | 경계값 |

**성공 기준**: assert 4건 모두 통과

---

#### TC-IT-P2-06: DELETE /training-data/{id} (FR-13~15)

**목적**: 내부 인증 토큰으로 ChromaDB 학습 데이터를 삭제하고, 재조회 시 해당 id가 사라지는지 확인. 인증 없는 요청은 403으로 차단됨을 검증.
**사전 조건**: GET /training-data로 학습 데이터 목록 조회 가능한 상태.

**Phase 1에서 이미 검증된 스텝**:

| Step | 내용 | Phase 1 결과 |
|------|------|-------------|
| GET /training-data | 학습 데이터 목록 조회 | 완료 |

**테스트 명령**:

```powershell
# Step 1: 학습 데이터 목록 조회 — 임의 id 선택
$listResp = Invoke-RestMethod `
    -Uri "$API_BASE/training-data" -Method GET `
    -Headers @{ Authorization = "Bearer $TOKEN" }
$targetId = $listResp.data[0].id
Write-Host "삭제 대상 id: $targetId"

# Step 2: DELETE /training-data/{id} (X-Internal-Token 헤더 포함)
$deleteResp = Invoke-RestMethod `
    -Uri "$API_BASE/training-data/$targetId" -Method DELETE `
    -Headers @{
        Authorization      = "Bearer $TOKEN"
        "X-Internal-Token" = "<internal-token>"
    }
Write-Host "삭제 응답: $($deleteResp | ConvertTo-Json)"

# Step 3: 삭제 후 재조회 — id 미존재 확인
$listAfter = Invoke-RestMethod `
    -Uri "$API_BASE/training-data" -Method GET `
    -Headers @{ Authorization = "Bearer $TOKEN" }
$ids = $listAfter.data | ForEach-Object { $_.id }
Write-Host "삭제 후 id 목록에 포함 여부: $($ids -contains $targetId)"

# Step 4: 인증 없이 요청 → 403 확인
try {
    Invoke-RestMethod -Uri "$API_BASE/training-data/$targetId" -Method DELETE
} catch {
    Write-Host "인증 없는 요청 응답: $($_.Exception.Response.StatusCode)"
}
```

| TC | Step | 스텝 역할 | 인풋 | 아웃풋 (실제값) | assert 단언 | 판정 | 비고 |
|----|------|-----------|------|----------------|-------------|------|------|
| TC-IT-P2-06 | DELETE 요청 | 정상 삭제 | 존재하는 id, `X-Internal-Token` 포함 | HTTP 200 | `assert deleteResp.StatusCode == 200` | | Phase 2 신규 엔드포인트 |
| TC-IT-P2-06 | GET 재조회 | 삭제 후 미존재 확인 | 삭제된 id로 목록 검색 | `ids`에 `targetId` 미포함 | `assert targetId not in ids` | | ChromaDB 실제 삭제 검증 |
| TC-IT-P2-06 | 인증 없는 요청 | 403 차단 | Authorization 헤더 없음 | HTTP 403 | `assert exception.StatusCode == 403` | | 무단 삭제 방지 |

**성공 기준**: assert 3건 모두 통과

---

#### TC-IT-P2-07: Airflow DAG — pending → trained 배치 학습 (FR-18)

**목적**: TC-IT-P2-04에서 저장된 pending 항목을 Airflow DAG `capa_chromadb_refresh`가 처리하여 ChromaDB에 재학습하고 DynamoDB 상태가 `trained`로 변경되는지 확인.
**사전 조건**: TC-IT-P2-04 완료 후 `capa-dev-pending-feedbacks`에 `status=pending` 항목 1건 이상 존재. Airflow 로컬 환경 기동 완료(localhost:8080).

**Phase 1에서 이미 검증된 스텝**:

| 항목 | 내용 | Phase 1 결과 |
|------|------|-------------|
| Airflow DAG 존재 | `capa_chromadb_refresh` DAG 목록 확인 | 미검증 (Phase 2 신규) |

**테스트 명령**:

```powershell
# Step 1: DAG 수동 트리거 (Airflow REST API — localhost:8080)
$dagResp = Invoke-RestMethod `
    -Uri "http://localhost:8080/api/v1/dags/capa_chromadb_refresh/dagRuns" `
    -Method POST `
    -ContentType "application/json" `
    -Headers @{ Authorization = "Basic " + [Convert]::ToBase64String([Text.Encoding]::ASCII.GetBytes("admin:admin")) } `
    -Body '{"conf": {}}'

$dagRunId = $dagResp.dag_run_id
Write-Host "DAG run_id: $dagRunId"

# Step 2: DAG 실행 완료 대기 (30초 ~ 2분 소요 예상)
Start-Sleep -Seconds 60

# Step 3: DAG 실행 상태 확인
$dagStatus = Invoke-RestMethod `
    -Uri "http://localhost:8080/api/v1/dags/capa_chromadb_refresh/dagRuns/$dagRunId" `
    -Method GET `
    -Headers @{ Authorization = "Basic " + [Convert]::ToBase64String([Text.Encoding]::ASCII.GetBytes("admin:admin")) }
Write-Host "DAG 상태: $($dagStatus.state)"

# Step 4: DynamoDB status=trained 항목 확인 (실제 AWS)
aws dynamodb scan `
    --table-name capa-dev-pending-feedbacks `
    --filter-expression "#s = :trained" `
    --expression-attribute-names '{\"#s\": \"status\"}' `
    --expression-attribute-values '{\":trained\": {\"S\": \"trained\"}}' `
    --region ap-northeast-2
```

| TC | Step | 스텝 역할 | 인풋 | 아웃풋 (실제값) | assert 단언 | 판정 | 비고 |
|----|------|-----------|------|----------------|-------------|------|------|
| TC-IT-P2-07 | DAG 트리거 | DAG 실행 시작 | Airflow REST API trigger | `dag_run_id` 반환, HTTP 200 | `assert dagResp.state in ("queued", "running")` | | Airflow localhost:8080 |
| TC-IT-P2-07 | DAG 완료 대기 | DAG 성공 종료 | DAG run 상태 조회 | `state == "success"` | `assert dagStatus.state == "success"` | | 실패 시 Airflow 로그 확인 필요 |
| TC-IT-P2-07 | DynamoDB 상태 변경 | pending → trained | AWS CLI scan (status=trained 필터) | `Count >= 1` | `assert trained_scan["Count"] >= 1` | | 실제 AWS DynamoDB 조회 |

**성공 기준**: assert 3건 모두 통과

---

### 2.3 E2E 통합 시나리오 (Phase 1 + Phase 2 전체 흐름)

---

#### TC-IT-E2E-01: 전체 파이프라인 E2E — 비동기 질문 → 이력 저장 → 피드백 → DAG 재학습 확인

**목적**: Phase 1(Step 1~10) + Phase 2 신규 기능(비동기, DynamoDB 이력, Redash 캐시, 피드백 pending, Airflow 재학습)을 하나의 연속 시나리오로 검증.
**환경 설정**: `PHASE2_RAG_ENABLED=true`, `ASYNC_QUERY_ENABLED=true`, `DYNAMODB_ENABLED=true`, `PHASE2_FEEDBACK_ENABLED=true`

**전체 흐름**:

```
[Step 1] POST /query → 202 (ASYNC)
    │
[Step 2] GET /query/{task_id} 폴링 → 200 완료, history_id 획득
    │
[Step 3] AWS CLI: capa-dev-query-history 저장 확인
    │
[Step 4] POST /feedback positive → trained=false, DynamoDB pending 확인
    │
[Step 5] Airflow DAG trigger → DynamoDB status=trained 확인
    │
[Step 6] 동일 SQL 재요청 → Redash 캐시 히트 (로그 확인)
```

**테스트 명령**:

```powershell
# === Step 1: 비동기 질문 접수 ===
$body = @{ question = "2026-02-01 캠페인별 CTR 알려줘"; slack_user_id = "test-user" } | ConvertTo-Json
$resp202 = Invoke-WebRequest `
    -Uri "$API_BASE/query" -Method POST `
    -ContentType "application/json" `
    -Headers @{ Authorization = "Bearer $TOKEN" } -Body $body
$taskId = ($resp202.Content | ConvertFrom-Json).task_id
Write-Host "[Step 1] HTTP: $($resp202.StatusCode) / task_id: $taskId"

# === Step 2: GET 폴링 — 완료까지 대기 ===
$maxRetry = 10; $completed = $false
for ($i = 1; $i -le $maxRetry; $i++) {
    Start-Sleep -Seconds 3
    $pollResp = Invoke-RestMethod `
        -Uri "$API_BASE/query/$taskId" -Method GET `
        -Headers @{ Authorization = "Bearer $TOKEN" }
    Write-Host "[Step 2] 폴링 $i 회: status=$($pollResp.status)"
    if ($pollResp.status -eq "completed") { $completed = $true; break }
}
$historyId = $pollResp.history_id
Write-Host "[Step 2] 완료: history_id=$historyId"

# === Step 3: DynamoDB query-history 저장 확인 ===
$dynResult = aws dynamodb get-item `
    --table-name capa-dev-query-history `
    --key "{`"history_id`": {`"S`": `"$historyId`"}}" `
    --region ap-northeast-2 | ConvertFrom-Json
Write-Host "[Step 3] DynamoDB Item 존재: $($dynResult.Item -ne $null)"

# === Step 4: POST /feedback positive ===
$fbBody = @{ history_id = $historyId; feedback = "positive"; slack_user_id = "test-user" } | ConvertTo-Json
$fbResp = Invoke-RestMethod `
    -Uri "$API_BASE/feedback" -Method POST `
    -ContentType "application/json" `
    -Headers @{ Authorization = "Bearer $TOKEN" } -Body $fbBody
Write-Host "[Step 4] trained: $($fbResp.trained)"

$pendingScan = aws dynamodb scan `
    --table-name capa-dev-pending-feedbacks `
    --region ap-northeast-2 | ConvertFrom-Json
Write-Host "[Step 4] pending 항목 수: $($pendingScan.Count)"

# === Step 5: Airflow DAG trigger ===
$dagResp = Invoke-RestMethod `
    -Uri "http://localhost:8080/api/v1/dags/capa_chromadb_refresh/dagRuns" `
    -Method POST -ContentType "application/json" `
    -Headers @{ Authorization = "Basic " + [Convert]::ToBase64String([Text.Encoding]::ASCII.GetBytes("admin:admin")) } `
    -Body '{"conf": {}}'
$dagRunId = $dagResp.dag_run_id
Start-Sleep -Seconds 60
$dagStatus = Invoke-RestMethod `
    -Uri "http://localhost:8080/api/v1/dags/capa_chromadb_refresh/dagRuns/$dagRunId" `
    -Method GET `
    -Headers @{ Authorization = "Basic " + [Convert]::ToBase64String([Text.Encoding]::ASCII.GetBytes("admin:admin")) }
Write-Host "[Step 5] DAG 상태: $($dagStatus.state)"

$trainedScan = aws dynamodb scan `
    --table-name capa-dev-pending-feedbacks `
    --filter-expression "#s = :trained" `
    --expression-attribute-names '{\"#s\": \"status\"}' `
    --expression-attribute-values '{\":trained\": {\"S\": \"trained\"}}' `
    --region ap-northeast-2 | ConvertFrom-Json
Write-Host "[Step 5] trained 항목 수: $($trainedScan.Count)"

# === Step 6: 동일 SQL 재요청 → Redash 캐시 히트 ===
Invoke-RestMethod -Uri "$API_BASE/query" -Method POST `
    -ContentType "application/json" `
    -Headers @{ Authorization = "Bearer $TOKEN" } -Body $body | Out-Null
docker compose logs vanna-api | Select-String -Pattern "캐시|cache_hit|sql_hash"
```

| TC | 단계 | 스텝 역할 | 인풋 | 아웃풋 (실제값) | assert 단언 | 판정 | 비고 |
|----|------|-----------|------|----------------|-------------|------|------|
| TC-IT-E2E-01 | Step 1 | 비동기 질문 접수 | POST /query (ASYNC=true) | HTTP 202, `task_id` 존재 | `assert resp202.StatusCode == 202` , `assert task_id is not None` | | FR-19 |
| TC-IT-E2E-01 | Step 2 | 폴링 완료 + 결과 | GET /query/{task_id} 반복 | `status == "completed"`, `history_id` 존재, `sql` 포함 | `assert completed == True` , `assert history_id is not None` | | FR-19 + FR-11 |
| TC-IT-E2E-01 | Step 3 | DynamoDB 이력 저장 확인 | AWS CLI get-item | `Item` 키 존재 | `assert dynResult.Item is not None` | | FR-11 — 실제 AWS |
| TC-IT-E2E-01 | Step 4-a | 피드백 — 즉시 학습 없음 | POST /feedback positive | `trained == false` | `assert fbResp.trained == False` | | FR-16 Phase 2 핵심 |
| TC-IT-E2E-01 | Step 4-b | DynamoDB pending 저장 | AWS CLI scan | `Count >= 1` | `assert pendingScan.Count >= 1` | | FR-16 — 실제 AWS |
| TC-IT-E2E-01 | Step 5-a | Airflow DAG 성공 | DAG run 상태 조회 | `state == "success"` | `assert dagStatus.state == "success"` | | FR-18 |
| TC-IT-E2E-01 | Step 5-b | DynamoDB status=trained | AWS CLI scan (trained 필터) | `Count >= 1` | `assert trainedScan.Count >= 1` | | FR-18 — 실제 AWS |
| TC-IT-E2E-01 | Step 6 | Redash 캐시 히트 | 동일 질문 2회차 | 로그에 "캐시" 또는 "cache_hit" 출력 | `assert log_contains("캐시" or "cache_hit")` | | FR-17 — 로그 확인 |

**성공 기준**: assert 8건 모두 통과

**결과 기록 파일**: `docs/t1/text-to-sql/05-test/plan-phase-2-tests/phase-2-text-to-sql-rag.test-result.md` 섹션 3에 위 테이블 형식으로 기록한다.

---

### 2.4 TC 전체 요약

| TC ID | 분류 | 대상 기능 | 관련 FR | assert 수 | 통과 기준 |
|-------|------|----------|---------|:---------:|----------|
| TC-IT-P2-01 | 기능 통합 | 3단계 RAG (Reranker + LLM filter) | FR-12 | 4 | 4/4 |
| TC-IT-P2-02 | 기능 통합 | DynamoDB 쿼리 이력 저장 | FR-11 | 3 | 3/3 |
| TC-IT-P2-03 | 기능 통합 | Redash query_id DynamoDB 캐시 | FR-17 | 3 | 3/3 |
| TC-IT-P2-04 | 기능 통합 | 피드백 pending 저장 (즉시 학습 제거) | FR-16 | 3 | 3/3 |
| TC-IT-P2-05 | 기능 통합 | 비동기 쿼리 (202 + 폴링) | FR-19 | 4 | 4/4 |
| TC-IT-P2-06 | 기능 통합 | DELETE /training-data/{id} | FR-13~15 | 3 | 3/3 |
| TC-IT-P2-07 | 기능 통합 | Airflow DAG 배치 학습 | FR-18 | 3 | 3/3 |
| TC-IT-E2E-01 | E2E | 전체 파이프라인 (Phase 1 + Phase 2) | FR-11~19 | 8 | 8/8 |
| **합계** | | | | **31** | **31/31** |

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
| `TC-P2-U` | 단위 테스트 | TC-P2-U01 ~ TC-P2-U57 |
| `TC-P2-` (숫자 2자리) | 통합 테스트 (2.1 기능별) | TC-P2-01 ~ TC-P2-16 |
| `TC-P2-E2E-` | E2E 시나리오 (2.2 전체 흐름) | TC-P2-E2E-01 ~ TC-P2-E2E-02 |

---

## 요약

| 구분 | TC 수 | 대상 컴포넌트 | 관련 FR |
|------|:-----:|-------------|---------|
| 단위 — sql_hash | 8 | `sql_hash.py` | FR-16/FR-18 (피드백 중복 제거) |
| 단위 — reranker | 5 | `reranker.py` | FR-12 |
| 단위 — dynamodb_feedback | 6 | `dynamodb_feedback.py` | FR-16 |
| 단위 — dynamodb_history | 5 | `dynamodb_history.py` | FR-11 |
| 단위 — airflow_dag | 6 | `capa_chromadb_refresh.py` | FR-18 |
| 단위 — DELETE /training-data | 3 | FastAPI endpoint | FR-13~15 |
| 단위 — RAGRetriever 메서드 + 에러처리 | 8 | `rag_retriever.py` | FR-12 |
| 단위 — AsyncQueryManager | 4 | `async_query_manager.py` | FR-19 |
| 단위 — FeedbackManager | 3 | `feedback_manager.py` | FR-16 |
| 단위 — batch_train 부분 실패 | 1 | `capa_chromadb_refresh.py` | FR-18 |
| 단위 — DELETE 실패 400 | 1 | FastAPI endpoint | FR-13~15 |
| 통합 — RAG 분기 | 1 | QueryPipeline | FR-12 |
| 통합 — 3단계 RAG | 4 | RAGRetriever | FR-12 |
| 통합 — 피드백 루프 | 3 | FeedbackManager | FR-16 |
| 통합 — 비동기 쿼리 | 4 | AsyncQueryManager + FastAPI | FR-19 |
| 통합 — EXPLAIN 실패 | 2 | SQLValidator | FR-12 |
| 통합 — DynamoDB 이력 저장 | 2 | DynamoDBHistoryRecorder | FR-11 |
| 통합 — Airflow DAG E2E | 4 | capa_chromadb_refresh | FR-18 |
| 통합 — 비동기 FAILED + 동기 경로 | 4 | AsyncQueryManager + FastAPI | FR-19 |
| 통합 — RAGRetriever 에러 처리 E2E | 2 | RAGRetriever + QueryPipeline | FR-12 |
| 통합 — AsyncQueryManager DynamoDB 영속성 | 2 | AsyncQueryManager + DynamoDB | FR-19 |
| 통합 — POST /feedback E2E | 2 | FeedbackManager + DynamoDB | FR-16 |
| 통합 — DAG 부분 실패 E2E | 1 | capa_chromadb_refresh | FR-18 |
| 통합 — DELETE 실패 E2E | 1 | FastAPI + Vanna | FR-13~15 |
| E2E — Phase 2 전체 기능 통합 | 12 | 전체 파이프라인 | FR-11~19 (FR-17 제외) |
| E2E — 피드백 루프 중복 제거 | 4 | FeedbackManager + DAG | FR-16~18 |
| **합계** | **99** | — | — |

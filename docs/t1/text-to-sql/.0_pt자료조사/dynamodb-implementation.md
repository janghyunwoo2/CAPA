# Text-to-SQL DynamoDB 구현 현황 및 가이드

이 문서는 CAPA 프로젝트의 Text-to-SQL 서비스에서 사용되는 DynamoDB의 구현 단계, 테이블 구조, 사용 목적 및 관련 코드를 정리한 자료입니다.

## 1. 구현 단계 (When)
- **도입 시점**: Phase 2 고도화 단계 중 **#01 Multi-turn Conversation (2026-03-21)** 과제에서 최초 도입되었습니다.
- **배경**: 기존 Phase 1에서는 로컬 JSON Lines 파일에 이력을 저장했으나, EKS 환경의 Pod 재시작 시 데이터 휘발 문제 및 멀티턴 대화 문맥 유지를 위해 영구 저장소인 DynamoDB로 전환했습니다.

---

## 2. DynamoDB 테이블 현황 (What)

현재 프로젝트에는 총 3개의 주요 테이블이 정의되어 운영 중입니다. (Terraform 기준)

| 테이블 구분 | 실제 테이블명 (dev 기준) | Hash Key | 사용 목적 |
|:---|:---|:---|:---|
| **Query History** | `capa-dev-query-history` | `history_id` (S) | 전체 질의 이력, 실행 결과, 멀티턴 세션 저장 |
| **Pending Feedbacks** | `capa-dev-pending-feedbacks` | `feedback_id` (S) | 사용자 긍정 피드백 데이터 임시 저장 (검증 대기) |
| **Async Tasks** | `capa-dev-async-tasks` | `task_id` (S) | Athena 비동기 쿼리 실행 상태 및 결과 폴링용 |

### 2.1 상세 저장 항목
- **Query History**: 질문(original/refined), 생성 SQL, SQL 검증 결과, Redash URL, 행 수, AI 답변, **session_id(Slack thread_ts)**, **turn_number**, Slack User/Channel ID, TTL 등.
- **Pending Feedbacks**: 질문-SQL 쌍, SQL 해시값, 상태(`pending`/`trained`), 생성 시각.
- **Async Tasks**: Task 상태(`PENDING`/`RUNNING`/`COMPLETED`/`FAILED`), 질문, 최종 결과 JSON, 오류 메시지.

---

## 3. 사용 이유 (Why)

1.  **멀티턴 세션 유지 (State Management)**:
    - Slack 스레드 내에서 "그 다음은?", "기기별로 보여줘"와 같은 대화를 처리하기 위해, 이전 질문과 답변의 맥락을 `session_id`와 `turn_number` 기반으로 조회하여 LLM에게 주입합니다.
2.  **비동기 쿼리 처리 (Async Polling)**:
    - Athena 쿼리 실행이 수십 초 이상 걸릴 경우, API 타임아웃을 방지하기 위해 즉시 `task_id`를 반환하고 DynamoDB에서 상태를 조회(Polling)하는 구조를 지원합니다.
3.  **데이터 정제 및 학습 (Feedback Loop)**:
    - 사용자가 누른 '좋아요' 데이터를 즉시 학습(ChromaDB)에 넣지 않고, `pending` 상태로 보관하여 데이터 품질 검사(Airflow)를 거친 후 안전하게 학습 데이터로 전환합니다.
4.  **보안 및 규정 준수 (PII & Retention)**:
    - `slack_user_id`를 SHA-256 해싱 처리하여 개인정보를 보호하며, 90일 TTL 설정을 통해 오래된 데이터를 자동으로 삭제하여 저장 비용을 최적화합니다.

---

## 4. 관련 코드 위치 (Where)

### 4.1 인프라 정의 (Terraform)
- **파일**: `infrastructure/terraform/13-dynamodb.tf`
- **주요 내용**: `aws_dynamodb_table` 리소스 정의, GSI(`session_id-turn_number-index`) 설계, vanna-api 전용 IAM Role 권한 부여.

### 4.2 어플리케이션 구현 (Python)
- **저장 로직 (Recorder)**: `services/vanna-api/src/stores/dynamodb_history.py`
    - `DynamoDBHistoryRecorder.record()` 메서드에서 파이프라인 컨텍스트를 DynamoDB Item으로 변환하여 저장합니다.
- **조회 로직 (Retriever)**: `services/vanna-api/src/pipeline/conversation_history_retriever.py`
    - `session_id`와 `turn_number`로 GSI를 쿼리하여 이전 대화 5건을 가져옵니다.
- **비동기 관리 (Manager)**: `services/vanna-api/src/async_query_manager.py`
    - `AsyncQueryManager.update_status()`를 통해 작업 상태를 동기화합니다.
- **초기화 및 연동**: `services/vanna-api/src/main.py`
    - 환경변수(`DYNAMODB_ENABLED`)에 따라 `lifespan` 시점에 Boto3 리소스를 초기화하고 인스턴스를 주입합니다.

### 4.3 주요 코드 스니펫 (예시: History 저장)
```python
# services/vanna-api/src/stores/dynamodb_history.py
def record(self, ctx: PipelineContext) -> str:
    item = {
        "history_id": str(uuid.uuid4()),
        "session_id": ctx.session_id,  # Slack thread_ts
        "turn_number": ctx.turn_number,
        "original_question": ctx.original_question,
        "generated_sql": ctx.generated_sql,
        "ttl": int((datetime.utcnow() + timedelta(days=90)).timestamp())
    }
    self._table.put_item(Item=item)
```

---
*작성일: 2026-03-26*
*작성자: Antigravity (Advanced Agentic Coding)*

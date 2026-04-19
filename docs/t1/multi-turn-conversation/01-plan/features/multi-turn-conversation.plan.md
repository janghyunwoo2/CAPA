# [Plan] Multi-Turn Conversation (FR-20)

## Executive Summary

| 항목 | 내용 |
|------|------|
| **Feature** | multi-turn-conversation |
| **FR ID** | FR-20 |
| **작성일** | 2026-03-21 |
| **담당** | t1 |
| **참고 문서** | `docs/t1/text-to-sql/01-plan/features/text-to-sql.plan.md` (FR-20 원출처), `docs/t1/text-to-sql/02_txt-to-sql-slack/01-plan/features/txt-to-sql-slack-thread.plan.md` (FR-24 연계) |

### Value Delivered (4관점)

| 관점 | 내용 |
|------|------|
| **Problem** | 현재 파이프라인은 단일 턴(stateless)으로 동작하여 "연령대별로 나눠줘"와 같은 후속 질문이 이전 맥락 없이 처리되어 SQL 생성이 불가능하거나 무관한 쿼리가 생성됨 |
| **Solution** | 기존 `capa-dev-query-history` 테이블에 `session_id`, `turn_number`, `answer` 필드 3개를 추가하고 GSI 1개를 생성. 파이프라인 앞에 Step 0을 추가해 이전 맥락을 조회한 뒤 QuestionRefiner/SQLGenerator에 주입 |
| **Function UX Effect** | 사용자는 Slack에서 자연스러운 연속 대화가 가능해지며, 첫 질문의 결과를 기반으로 "연령대별", "일별로 나눠줘" 같은 후속 질문을 반복할 수 있음 |
| **Core Value** | 별도 테이블 없이 기존 이력 테이블을 재활용해 중복 저장을 제거하고, FR-24(Slack 스레드)의 `thread_ts`를 `session_id`로 활용하여 "스레드 = 하나의 대화 세션" 개념을 자연스럽게 구현 |

---

## 1. 배경 및 목적

### 1.1 문제 정의 (현재 Phase 1/2)

```
[AS-IS — Stateless 파이프라인]

Turn 1: "지난달 신규 가입자 수 알려줘"
  → SQL: SELECT COUNT(*) FROM users WHERE created_at >= '...'
  → 결과: 12,345명

Turn 2: "연령대별로 나눠줘"
  → 맥락 없음 → "연령대별로" 무엇을? → SQL 생성 불가 또는 오답
```

**구조적 문제:**
- `PipelineContext`는 요청당 새로 생성되고 즉시 소멸 (stateless)
- `conversation_id` 필드가 `QueryRequest`에 이미 존재하지만 Phase 1/2에서 미사용
- 후속 질문의 의미는 이전 대화 맥락 없이 해석 불가

### 1.2 목표 (TO-BE)

```
[TO-BE — Session-aware 파이프라인]

Step 0: ConversationHistoryRetriever
  session_id(= thread_ts)로 기존 DynamoDB 테이블 GSI 조회
  → 최근 N턴 대화 이력 반환
                         ↓
Step 2: QuestionRefiner (이력 주입)
  "연령대별로 나눠줘" + [이전: 지난달 신규 가입자 수]
  → "지난달 신규 가입자 수를 연령대별로 나눠서 조회해줘"
                         ↓
Step 5: SQLGenerator (이력 주입)
  정제된 질문 + 이전 SQL 참고 → 정확한 후속 SQL 생성
```

---

## 2. 기능 요구사항

### 2.1 FR-20 세부 요구사항

| ID | 요구사항 | 우선순위 |
|----|---------|---------|
| FR-20-01 | 동일 세션 내 이전 대화 이력을 DynamoDB에서 조회하는 Step 0 추가 | Must |
| FR-20-02 | `session_id` = `thread_ts` (FR-24 연계): Slack Bot이 thread_ts를 conversation_id로 전달 | Must |
| FR-20-03 | 이전 대화 맥락을 QuestionRefiner(Step 2)에 주입하여 질문 정제 개선 | Must |
| FR-20-04 | 이전 SQL을 SQLGenerator(Step 5)에 참고 자료로 주입 | Must |
| FR-20-05 | Step 11 HistoryRecorder에서 `session_id`, `turn_number`, `answer` 저장 | Must |
| FR-20-06 | 맥락 창 크기 제한: 최근 5턴만 사용 (토큰 비용 제어) | Should |
| FR-20-07 | `conversation_id` 미전달 시 기존 파이프라인 정상 동작 유지 (하위 호환) | Must |

### 2.2 제외 범위 (Out of Scope)

- 크로스 세션 맥락 유지 (세션 만료 후 기억)
- 별도 conversation 전용 DynamoDB 테이블 생성 (기존 테이블 재활용)
- 대화 이력 기반 ChromaDB 재학습 (→ Phase 4 FR-22)
- 웹 UI 기반 대화 인터페이스 (Slack 전용)

---

## 3. 아키텍처

### 3.1 핵심 설계 결정: 기존 테이블 재활용

```
[기존 Plan — 별도 테이블]            [최적화 방안 — 기존 테이블 재활용]
capa-dev-query-history               capa-dev-query-history
  history_id (PK)                      history_id (PK)
  original_question                    session_id        ← 추가 (GSI PK)
  generated_sql                        turn_number       ← 추가 (GSI SK)
  ...                                  answer            ← 추가 (LLM 답변)
                                       original_question  기존 재활용
capa-conversation-sessions (신규)      generated_sql      기존 재활용
  session_id (PK)                      refined_question   기존 재활용
  turn_number (SK)
  question         ← 중복!
  generated_sql    ← 중복!
  ...

→ 테이블 1개 절약, 중복 데이터 없음, 피드백 루프(FR-16)와 자연 연동
```

### 3.2 파이프라인 변경

```
[변경 전 — Phase 1/2 파이프라인]
Step 1  IntentClassifier
Step 2  QuestionRefiner
...
Step 11 HistoryRecorder

[변경 후 — FR-20 파이프라인]
Step 0   ConversationHistoryRetriever  ← 신규 (DynamoDB GSI 조회)
Step 1   IntentClassifier
Step 2   QuestionRefiner               ← 맥락 주입 (conversation_history)
Step 3   KeywordExtractor
Step 4   RAGRetriever
Step 5   SQLGenerator                  ← 이전 SQL 주입
Step 6   SQLValidator
Step 7   RedashQueryCreator
Step 8   RedashExecutor
Step 9   ResultCollector
Step 10  AIAnalyzer
Step 10.5 ChartRenderer
Step 11  HistoryRecorder               ← session_id, turn_number, answer 추가 저장
```

### 3.3 session_id 전략 (FR-24 연계)

```
FR-24(Slack 스레드) 구현 후:
  Slack Bot → thread_ts 생성 → conversation_id로 QueryRequest에 포함
  → vanna-api session_id = thread_ts

FR-24 미구현 / conversation_id 없는 경우:
  → session_id = None → 기존 파이프라인 그대로 (하위 호환)

결론: "Slack 스레드 1개 = 대화 세션 1개"
```

### 3.4 맥락 주입 위치

| 주입 대상 | 주입 내용 |
|----------|---------|
| QuestionRefiner (Step 2) | 최근 N턴 질문 + LLM 답변 요약 |
| SQLGenerator (Step 5) | 최근 N턴 생성 SQL |

---

## 4. 데이터 모델

### 4.1 DynamoDB 스키마 변경 (기존 테이블)

```
테이블명: capa-dev-query-history (기존)

추가 필드:
  - session_id:    String  (Slack thread_ts 값, 없으면 저장 생략)
  - turn_number:   Number  (세션 내 순번, session_id 없으면 저장 생략)
  - answer:        String  (AIAnalyzer 생성 답변, 최대 500자)

추가 GSI:
  이름: session_id-turn_number-index
  PK:   session_id (String)
  SK:   turn_number (Number)
  → 특정 세션의 모든 턴을 turn_number 순으로 조회 가능
```

### 4.2 저장되는 것 vs 이미 있는 것

| 필드 | 상태 | 설명 |
|------|------|------|
| `original_question` | ✅ 기존 | 사용자 원본 질문 |
| `refined_question` | ✅ 기존 | LLM 정제 질문 |
| `generated_sql` | ✅ 기존 | LLM 생성 SQL |
| `answer` | ❌ 신규 추가 | AIAnalyzer LLM 답변 텍스트 |
| `session_id` | ❌ 신규 추가 | Slack thread_ts |
| `turn_number` | ❌ 신규 추가 | 세션 내 순번 |

### 4.3 PipelineContext 변경

```python
class ConversationTurn(BaseModel):
    """이전 대화 턴 — Step 0에서 조회, Step 2/5에서 참조"""
    turn_number: int
    question: str
    refined_question: Optional[str] = None
    generated_sql: Optional[str] = None
    answer: Optional[str] = None  # LLM 답변


class PipelineContext(BaseModel):
    # ... 기존 필드 유지 ...

    # FR-20 추가
    session_id: Optional[str] = None
    turn_number: Optional[int] = None
    conversation_history: list[ConversationTurn] = Field(default_factory=list)
```

---

## 5. API 변경사항

### 5.1 QueryRequest (변경 없음)

```python
# models/api.py:31 — 기존 필드 그대로 사용
conversation_id: Optional[str] = Field(None, description="세션 ID = Slack thread_ts (FR-20)")
```

### 5.2 QueryResponse 변경

```python
class QueryResponse(BaseModel):
    # ... 기존 필드 유지 ...
    session_id: Optional[str] = Field(None, description="세션 ID (FR-20, 클라이언트 재전송용)")
```

---

## 6. 신규 추가 ENV

| ENV 이름 | 값 | 추가 위치 |
|---------|---|----------|
| `CONVERSATION_MAX_TURNS` | `5` | `infrastructure/terraform/11-k8s-apps.tf` |
| `MULTI_TURN_ENABLED` | `false` → `true` (Feature Flag) | `infrastructure/terraform/11-k8s-apps.tf` |

> DynamoDB 테이블 신규 생성 없음. GSI 추가는 Terraform `aws_dynamodb_table` 리소스 수정으로 처리.
> DynamoDB IAM: 기존 IRSA 역할에 `dynamodb:Query` (GSI 조회) 권한 추가 필요.

---

## 7. 구현 파일 목록

| 파일 | 변경 종류 | 설명 |
|------|---------|------|
| `src/pipeline/conversation_history_retriever.py` | 신규 | Step 0 구현 (GSI Query) |
| `src/models/domain.py` | 수정 | `ConversationTurn`, `PipelineContext` 필드 추가 |
| `src/models/api.py` | 수정 | `QueryResponse.session_id` 추가 |
| `src/pipeline/question_refiner.py` | 수정 | `conversation_history` 맥락 주입 |
| `src/pipeline/sql_generator.py` | 수정 | 이전 SQL 맥락 주입 |
| `src/stores/dynamodb_history.py` | 수정 | `session_id`, `turn_number`, `answer` 저장 추가 |
| `src/query_pipeline.py` | 수정 | Step 0 통합 |
| `infrastructure/terraform/11-k8s-apps.tf` | 수정 | ENV 추가, DynamoDB GSI 추가 |

---

## 8. 성공 기준

| 항목 | 기준 |
|------|------|
| 후속 질문 정확도 | "연령대별로 나눠줘" → 이전 맥락 기반 올바른 SQL 생성 |
| 하위 호환 | `conversation_id` 미전달 시 기존 파이프라인 동작 동일 |
| 응답 지연 | Step 0 DynamoDB GSI 조회 추가 지연 < 50ms |
| 맥락 창 | 최근 5턴 초과 시 가장 오래된 턴 제외 |
| 데이터 무결성 | 동일 session_id 내 turn_number 연속성 보장 |

---

## 9. 구현 순서

```
전제: FR-24(Slack 스레드) 구현 완료 후 진행 권장
      (thread_ts → conversation_id 전달 경로 확보 필요)

1. DynamoDB GSI 추가 (session_id-turn_number-index) — Terraform 수정
2. ConversationTurn / PipelineContext 모델 추가 (domain.py)
3. ConversationHistoryRetriever 구현 (Step 0, GSI Query)
4. DynamoDBHistoryRecorder 수정 (session_id, turn_number, answer 저장)
5. QuestionRefiner 맥락 주입 수정
6. SQLGenerator 이전 SQL 주입 수정
7. QueryPipeline 통합 (Step 0 연결)
8. API 모델 변경 (session_id 응답 추가)
9. Terraform ENV 추가 (MULTI_TURN_ENABLED=false 로 Feature Flag)
10. 단위 테스트 작성
```

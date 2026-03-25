# [Plan] Multi-Turn Conversation (FR-20)

## Executive Summary

| 항목 | 내용 |
|------|------|
| **Feature** | multi-turn-conversation |
| **FR ID** | FR-20 |
| **작성일** | 2026-03-21 |
| **담당** | t1 |
| **참고 문서** | `docs/t1/text-to-sql/00_mvp_develop/01-plan/features/text-to-sql.plan.md` (FR-20 원출처), `docs/t1/text-to-sql/02_txt-to-sql-slack/01-plan/features/txt-to-sql-slack-thread.plan.md` (FR-24 연계) |

### Value Delivered (4관점)

| 관점 | 내용 |
|------|------|
| **Problem** | 현재 파이프라인은 단일 턴(stateless)으로 동작하여 "연령대별로 나눠줘"와 같은 후속 질문이 이전 맥락 없이 처리되어 SQL 생성이 불가능하거나 무관한 쿼리가 생성됨 |
| **Solution** | 기존 `capa-dev-query-history` 테이블에 `session_id`, `turn_number`, `answer` 3개 필드와 GSI 1개를 추가하고, 파이프라인 앞에 Step 0을 추가해 이전 맥락을 조회한 뒤 QuestionRefiner/SQLGenerator에 주입 |
| **Function UX Effect** | 사용자는 Slack 스레드 안에서 자연스러운 연속 대화가 가능해지며, "연령대별", "일별로 나눠줘" 같은 후속 질문을 반복할 수 있음 |
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
- `conversation_id` 필드가 `QueryRequest`에 이미 존재하지만 미사용
- 후속 질문의 의미는 이전 대화 맥락 없이 해석 불가

### 1.2 목표 (TO-BE)

```
[TO-BE — Session-aware 파이프라인]

Slack Bot:
  thread_ts → conversation_id 로 QueryRequest에 포함 (FR-24 연계)

Step 0: ConversationHistoryRetriever
  session_id(= thread_ts)로 기존 DynamoDB 테이블 GSI 조회
  → 최근 N턴 이력 반환 / turn_number = 기존 턴 수 + 1 계산
                         ↓
Step 2: QuestionRefiner (이력 주입)
  "연령대별로 나눠줘" + [Turn 1: 지난달 신규 가입자 수 / answer: 12,345명]
  → "지난달 신규 가입자 수를 연령대별로 나눠서 조회해줘"
                         ↓
Step 5: SQLGenerator (이전 SQL 주입)
  정제된 질문 + 이전 SQL 참고 → 정확한 후속 SQL 생성
                         ↓
Step 11: HistoryRecorder (기존)
  session_id, turn_number, answer 추가 저장 (기존 record() 확장)
```

---

## 2. 기능 요구사항

### 2.1 FR-20 세부 요구사항

| ID | 요구사항 | 우선순위 |
|----|---------|---------|
| FR-20-01 | 동일 세션 내 이전 대화 이력을 DynamoDB GSI로 조회하는 Step 0 추가 | Must |
| FR-20-02 | `session_id` = `thread_ts` (FR-24 연계): Slack Bot이 thread_ts를 conversation_id로 전달 | Must |
| FR-20-03 | Step 0에서 현재 turn_number 계산 (기존 턴 수 조회 후 +1) | Must |
| FR-20-04 | 이전 대화 맥락(질문 + answer)을 QuestionRefiner(Step 2)에 주입 | Must |
| FR-20-05 | 이전 SQL을 SQLGenerator(Step 5)에 참고 자료로 주입 | Must |
| FR-20-06 | Step 11 HistoryRecorder에서 `session_id`, `turn_number`, `answer` 추가 저장 | Must |
| FR-20-07 | 맥락 창 크기 제한: 최근 5턴만 사용 (토큰 비용 제어) | Should |
| FR-20-08 | `conversation_id` 미전달 시 기존 파이프라인 정상 동작 유지 (하위 호환) | Must |

### 2.2 제외 범위 (Out of Scope)

- 크로스 세션 맥락 유지 (세션 만료 후 기억)
- 별도 conversation 전용 DynamoDB 테이블 생성 (기존 테이블 재활용)
- Step 0.5 ConversationTurnSaver 별도 구현 (Step 11에서 함께 처리)
- 대화 이력 기반 ChromaDB 재학습 (→ Phase 4 FR-22)

---

## 3. 아키텍처

### 3.1 핵심 설계 결정: 기존 테이블 재활용

```
[기존 — 별도 테이블 방식]        [채택 — 기존 테이블 재활용]
capa-dev-query-history            capa-dev-query-history
  history_id (PK)                   history_id (PK)
  original_question                 session_id   ← 추가 (GSI PK)
  generated_sql                     turn_number  ← 추가 (GSI SK)
  ...                               answer       ← 추가 (LLM 답변)
                                    기존 필드 재활용
capa-conversation-sessions (신규)
  → 불필요, 중복 저장 제거

장점: 테이블 1개 절약, 피드백 루프(FR-16)와 자연 연동
```

### 3.2 파이프라인 변경

```
[변경 전]
Step 1  IntentClassifier
Step 2  QuestionRefiner
Step 3  KeywordExtractor
Step 4  RAGRetriever
Step 5  SQLGenerator
Step 6  SQLValidator
Step 7  RedashQueryCreator
Step 8  RedashExecutor
Step 9  ResultCollector
Step 10 AIAnalyzer
Step 10.5 ChartRenderer
Step 11 HistoryRecorder

[변경 후]
Step 0   ConversationHistoryRetriever  ← 신규 (GSI 조회, turn_number 계산)
Step 1   IntentClassifier
Step 2   QuestionRefiner               ← 맥락 주입 (질문 + answer 이력)
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

### 3.3 session_id 전략

```
FR-24 구현 후 (권장):
  Slack Bot → thread_ts를 conversation_id로 QueryRequest에 포함
  → vanna-api: session_id = conversation_id = thread_ts

스레드 답글 감지 (멀티턴 핵심):
  event['thread_ts'] 있음 → 기존 스레드 = 기존 세션 (Turn 2+)
  event['thread_ts'] 없음 → 신규 스레드 생성 = 새 세션 (Turn 1)
  → 동일 thread_ts = 동일 session_id = 이전 이력 조회 가능

FR-24 미구현 / conversation_id 없는 경우:
  → session_id = None → Step 0 건너뜀 → 기존 파이프라인 그대로

결론: "Slack 스레드 1개 = 대화 세션 1개"
      동일 사용자라도 스레드가 다르면 다른 세션 (정확한 맥락 분리)
```

### 3.4 turn_number 계산

```python
# Step 0: ConversationHistoryRetriever
existing_turns = dynamodb.query(
    IndexName="session_id-turn_number-index",
    KeyConditionExpression="session_id = :sid",
)
current_turn_number = len(existing_turns) + 1  # 새 턴 번호
ctx.turn_number = current_turn_number
ctx.conversation_history = existing_turns[-MAX_TURNS:]  # 최근 5턴만
```

### 3.5 맥락 주입 위치

| 주입 대상 | 주입 내용 |
|----------|---------|
| QuestionRefiner (Step 2) | 최근 N턴 질문 + answer |
| SQLGenerator (Step 5) | 최근 N턴 generated_sql |

---

## 4. 데이터 모델

### 4.1 DynamoDB 스키마 변경 (기존 테이블)

```
테이블명: capa-dev-query-history (기존, 변경 없음)

추가 필드:
  - session_id:    String  (Slack thread_ts, 없으면 저장 생략)
  - turn_number:   Number  (세션 내 순번, session_id 없으면 저장 생략)
  - answer:        String  (ctx.analysis.answer, 최대 500자 트림)

추가 GSI:
  이름: session_id-turn_number-index
  PK:   session_id (String)
  SK:   turn_number (Number)
  투영: ALL (기존 필드 포함)
```

### 4.2 저장 필드 현황

| 필드 | 상태 | 출처 |
|------|------|------|
| `original_question` | ✅ 기존 | ctx.original_question |
| `refined_question` | ✅ 기존 | ctx.refined_question |
| `generated_sql` | ✅ 기존 | ctx.validation_result.normalized_sql |
| `answer` | ❌ **신규 추가** | ctx.analysis.answer |
| `session_id` | ❌ **신규 추가** | ctx.session_id (= thread_ts) |
| `turn_number` | ❌ **신규 추가** | ctx.turn_number |
| `slack_thread_ts` | ❌ **신규 추가** | ctx.slack_thread_ts (FR-24 연계) |

### 4.3 PipelineContext 변경

```python
class ConversationTurn(BaseModel):
    """이전 대화 턴 — Step 0에서 조회, Step 2/5에서 참조"""
    turn_number: int
    question: str
    refined_question: Optional[str] = None
    generated_sql: Optional[str] = None
    answer: Optional[str] = None  # LLM 답변 (FR-24와 필드명 통일)


class PipelineContext(BaseModel):
    # ... 기존 필드 유지 ...

    # FR-20 추가
    session_id: Optional[str] = None         # thread_ts 값
    turn_number: Optional[int] = None        # 현재 턴 번호
    slack_thread_ts: Optional[str] = None    # FR-24 연계
    conversation_history: list[ConversationTurn] = Field(default_factory=list)
```

---

## 5. API 변경사항

### 5.1 QueryRequest (변경 없음)

```python
# models/api.py:31 — 기존 필드 그대로 사용
conversation_id: Optional[str] = Field(None, description="세션 ID = Slack thread_ts (FR-20/FR-24 연계)")
```

### 5.2 QueryResponse 변경

```python
class QueryResponse(BaseModel):
    # ... 기존 필드 유지 ...
    session_id: Optional[str] = Field(None, description="세션 ID (클라이언트 재전송용, FR-20)")
```

---

## 6. 신규 추가 ENV

| ENV 이름 | 값 | 추가 위치 |
|---------|---|----------|
| `CONVERSATION_MAX_TURNS` | `5` | `infrastructure/terraform/11-k8s-apps.tf` |
| `MULTI_TURN_ENABLED` | `false` → `true` (Feature Flag) | `infrastructure/terraform/11-k8s-apps.tf` |
| `HISTORY_TABLE_NAME` | `capa-dev-query-history` (기본값) | `src/pipeline/conversation_history_retriever.py` |

> DynamoDB 테이블 신규 생성 없음.
> GSI 추가: Terraform `aws_dynamodb_table` 리소스에 `global_secondary_index` 블록 추가.
> IAM: 기존 IRSA 역할에 `dynamodb:Query` (GSI 조회) 권한 추가.

---

## 7. 구현 파일 목록

| 파일 | 변경 종류 | 설명 |
|------|---------|------|
| `services/slack-bot/app.py` | 수정 | 스레드 답글 감지 + `conversation_id=thread_ts` 전달 (멀티턴 인터페이스) |
| `src/pipeline/conversation_history_retriever.py` | **신규** | Step 0 구현 (GSI Query, turn_number 계산) |
| `src/models/domain.py` | 수정 | `ConversationTurn`, `PipelineContext` 필드 추가 |
| `src/models/api.py` | 수정 | `QueryResponse.session_id` 추가 |
| `src/pipeline/question_refiner.py` | 수정 | `conversation_history` 맥락 주입 |
| `src/pipeline/sql_generator.py` | 수정 | 이전 SQL 맥락 주입 |
| `src/stores/dynamodb_history.py` | 수정 | `session_id`, `turn_number`, `answer`, `slack_thread_ts` 저장 추가 |
| `src/query_pipeline.py` | 수정 | Step 0 통합 (run() 메서드 앞에 추가) |
| `src/main.py` | 수정 | `conversation_id` → `run()` 전달, `session_id` 응답 추가 |
| `infrastructure/terraform/11-k8s-apps.tf` | 수정 | ENV 추가, DynamoDB GSI 추가 |

---

## 8. 성공 기준

| 항목 | 기준 |
|------|------|
| 후속 질문 정확도 | "연령대별로 나눠줘" → 이전 맥락 기반 올바른 SQL 생성 |
| 하위 호환 | `conversation_id` 미전달 시 기존 파이프라인 동작 동일 |
| 응답 지연 | Step 0 DynamoDB GSI 조회 추가 지연 < 50ms |
| turn_number | 동일 session_id 내 연속적으로 증가 (1, 2, 3...) |
| answer 저장 | Step 11 이후 DynamoDB에 answer 필드 확인 가능 |

---

## 9. 구현 순서

```
전제: FR-24(Slack 스레드) 구현 완료 후 진행 권장
      (thread_ts → conversation_id 전달 경로 확보 필요)

1. domain.py — ConversationTurn 모델, PipelineContext 필드 추가
2. dynamodb_history.py — session_id, turn_number, answer, slack_thread_ts 저장
3. conversation_history_retriever.py — Step 0 신규 구현 (GSI Query)
4. question_refiner.py — conversation_history 파라미터, 프롬프트 주입
5. sql_generator.py — conversation_history 파라미터, 이전 SQL 주입
6. query_pipeline.py — __init__에 _conversation_retriever 초기화, run() 파라미터 추가
7. main.py — conversation_id → run() 전달, session_id 응답 추가
8. slack-bot/app.py — 스레드 답글 감지 + conversation_id=thread_ts 전달
9. 11-k8s-apps.tf — GSI 추가, ENV 추가 (MULTI_TURN_ENABLED=false)
10. IAM — vanna-api IRSA 역할에 dynamodb:Query 권한 추가 (GSI 조회용)
11. 단위 테스트 작성
```

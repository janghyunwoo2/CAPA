# [Design] Multi-Turn Conversation (FR-20)

## Executive Summary

| 항목 | 내용 |
|------|------|
| **Feature** | multi-turn-conversation |
| **FR ID** | FR-20 |
| **작성일** | 2026-03-21 |
| **담당** | t1 |
| **참고 문서** | `docs/t1/text-to-sql/01_multi-turn-conversation/01-plan/features/multi-turn-conversation.plan.md` |

### Value Delivered (4관점)

| 관점 | 내용 |
|------|------|
| **Problem** | Stateless 파이프라인으로 후속 질문("연령대별로 나눠줘") 처리 불가 |
| **Solution** | Step 0 추가 + Step 11 확장으로 기존 파이프라인 최소 변경 |
| **Function UX Effect** | Slack 스레드 = 하나의 대화 세션, 자연스러운 연속 질의 가능 |
| **Core Value** | 기존 테이블 재활용, 별도 테이블·저장 단계 없이 구현 |

---

## 1. 설계 개요

### 1.1 설계 원칙

1. **최소 변경**: 기존 11-Step 파이프라인 앞뒤에만 추가, 중간 단계 구조 유지
2. **하위 호환**: `conversation_id` 없으면 기존 동작과 100% 동일
3. **단일 저장**: 기존 Step 11 한 곳에서만 저장, 별도 저장 단계 없음
4. **FR-24 의존**: `session_id = thread_ts` 전략, FR-24 구현 후 활성화

### 1.2 변경 범위

| 구분 | 파일 | 변경 종류 |
|------|------|---------|
| 수정 | `services/slack-bot/app.py` | 스레드 답글 감지 + conversation_id=thread_ts 전달 |
| 신규 | `src/pipeline/conversation_history_retriever.py` | Step 0 구현 |
| 수정 | `src/models/domain.py` | ConversationTurn 모델, PipelineContext 필드 추가 |
| 수정 | `src/models/api.py` | QueryResponse.session_id 추가 |
| 수정 | `src/pipeline/question_refiner.py` | 대화 이력 맥락 주입 |
| 수정 | `src/pipeline/sql_generator.py` | 이전 SQL 맥락 주입 |
| 수정 | `src/stores/dynamodb_history.py` | session_id, turn_number, answer 저장 추가 |
| 수정 | `src/query_pipeline.py` | Step 0 연결 |
| 수정 | `src/main.py` | conversation_id → run() 전달, session_id 응답 추가 |
| 수정 | `infrastructure/terraform/11-k8s-apps.tf` | GSI, ENV 추가 |

---

## 2. 시스템 아키텍처

### 2.1 파이프라인 전체 흐름

```
Slack Bot
  │  thread_ts → conversation_id (FR-24)
  ▼
POST /query { question, conversation_id: "thread_ts값" }
  │
  ▼
QueryPipeline.run()
  │
  ├─ [MULTI_TURN_ENABLED=true 이고 conversation_id 있을 때만]
  │
  ▼
Step 0: ConversationHistoryRetriever
  DynamoDB GSI 조회: session_id = conversation_id
  → conversation_history (최근 5턴)
  → current turn_number = 기존 턴 수 + 1
  │
  ▼
Step 1: IntentClassifier (변경 없음)
  │
  ▼
Step 2: QuestionRefiner  ← conversation_history 주입
  이전 대화 맥락 + 현재 질문 → 정제된 질문
  │
  ▼
Step 3~4: KeywordExtractor, RAGRetriever (변경 없음)
  │
  ▼
Step 5: SQLGenerator  ← 이전 SQL 목록 주입
  이전 SQL 참고 + 현재 정제된 질문 → SQL 생성
  │
  ▼
Step 6~10.5: 검증, 실행, 분석, 차트 (변경 없음)
  │
  ▼
Step 11: HistoryRecorder  ← session_id, turn_number, answer 추가 저장
  DynamoDB PutItem (기존 + 신규 3개 필드)
```

---

### 2.2 Slack Bot 연계 인터페이스 (FR-24)

FR-20은 Slack Bot이 `thread_ts`를 `conversation_id`로 전달한다는 전제로 동작한다.
이 섹션은 Slack Bot(FR-24)과의 인터페이스 및 멀티턴 동작 방식을 명시한다.

#### 2.2.1 thread_ts 처리 전략

```
신규 채널 메시지 (Turn 1 시작):
  event['thread_ts'] 없음
  → say("🔄 처리 중...") 로 스레드 루트 생성
  → thread_ts = response['ts']
  → conversation_id = thread_ts  (새 세션 시작)

스레드 답글 (Turn 2+, 같은 스레드):
  event['thread_ts'] 존재  ← Slack이 자동 포함
  → thread_ts = event['thread_ts']  (기존 루트 재사용)
  → conversation_id = thread_ts  (기존 세션 계속)
  → 새 루트 메시지 생성 안 함
```

> **핵심**: Turn 2에서 `event['thread_ts']`를 재사용해야 기존 session_id로 이력이 조회됨.
> 새 루트를 만들면 새 thread_ts = 새 session_id = 이력 없음 (멀티턴 단절).

#### 2.2.2 Slack Bot 코드 (services/slack-bot/app.py)

```python
@app.event("app_mention")
def handle_mention(event, say, client):
    text = event["text"]
    user = event["user"]
    channel_id = event.get("channel", "")

    # [FR-20 핵심] 스레드 답글이면 기존 thread_ts 재사용, 신규이면 루트 생성
    existing_thread_ts = event.get("thread_ts")  # 스레드 답글 시 Slack이 자동 포함

    if existing_thread_ts:
        # Turn 2+ : 기존 스레드에 "처리 중" 추가 (새 루트 생성 안 함)
        thread_ts = existing_thread_ts
        say(text="🔄 처리 중...", thread_ts=thread_ts)
    else:
        # Turn 1 : 신규 스레드 루트 생성 (FR-24-01)
        thread_response = say(text="🔄 처리 중...")
        thread_ts = thread_response['ts']

    try:
        # [FR-20 연계] thread_ts → conversation_id 로 vanna-api에 전달
        response = requests.post(
            f"{VANNA_API_URL}/query",
            json={
                "question": text,
                "slack_user_id": user,
                "slack_channel_id": channel_id,
                "conversation_id": thread_ts,   # ← session_id = thread_ts (FR-20)
            },
            timeout=VANNA_API_TIMEOUT
        )
        result = response.json()

        # 스레드 답글로 결과 전송
        say(blocks=_build_header_blocks(result), thread_ts=thread_ts)
        say(blocks=_upload_chart(...), thread_ts=thread_ts)
        say(blocks=_build_footer_blocks(result), thread_ts=thread_ts)

        # Turn 1에서만 루트 메시지 완료 업데이트 (선택, FR-24-04)
        if not existing_thread_ts:
            question_summary = text[:30] + "..." if len(text) > 30 else text
            client.chat_update(
                channel=channel_id,
                ts=thread_ts,
                text=f"✅ 완료: {question_summary}"
            )

    except Exception as e:
        logger.error(f"쿼리 실패: {e}")
        say(
            blocks=[{"type": "section", "text": {"type": "mrkdwn", "text": f"❌ 오류: {str(e)[:100]}"}}],
            thread_ts=thread_ts
        )
```

#### 2.2.3 멀티턴 대화 전체 시퀀스

```
[Turn 1 — 신규 채널 메시지]

사용자: "@capa-bot 지난달 신규 가입자 수 알려줘"

Slack Bot:
  - event['thread_ts'] 없음 → 신규 스레드 루트 생성
  - say("🔄 처리 중...") → thread_ts = "1711234567.111"
  - POST /query { question: "...", conversation_id: "1711234567.111" }

vanna-api:
  - Step 0: session_id="1711234567.111", DynamoDB 이력 없음 → turn_number=1
  - Step 2: 이력 없음 → 질문 그대로 정제
  - Step 5: SQL 생성
  - Step 11: DynamoDB 저장 { session_id: "1711234567.111", turn_number: 1, answer: "..." }

Slack Bot:
  - 결과를 thread_ts="1711234567.111" 스레드 답글로 전송
  - 루트 메시지 → "✅ 완료: 지난달 신규 가입자 수..."

─────────────────────────────────────────────────

[Turn 2 — 같은 스레드 답글]

사용자: "@capa-bot 연령대별로 나눠줘" (thread_ts="1711234567.111" 스레드에 답글)

Slack Bot:
  - event['thread_ts'] = "1711234567.111" → 기존 스레드 재사용
  - say("🔄 처리 중...", thread_ts="1711234567.111")
  - POST /query { question: "연령대별로 나눠줘", conversation_id: "1711234567.111" }  ← 동일 session_id

vanna-api:
  - Step 0: session_id="1711234567.111" → DynamoDB GSI 조회
            → Turn 1 이력 반환 (question, answer, generated_sql)
            → turn_number = 2
  - Step 2: "연령대별로 나눠줘" + Turn 1 맥락
            → "2026-02 신규 가입자를 연령대별로 분류하여 조회"
  - Step 5: Turn 1 SQL 참고 → GROUP BY age_group 포함 SQL 생성
  - Step 11: DynamoDB 저장 { session_id: "1711234567.111", turn_number: 2 }

Slack Bot:
  - 결과를 동일 스레드 답글로 전송 (채널은 깔끔하게 유지)
```

---

## 3. 상세 설계

### 3.1 Step 0: ConversationHistoryRetriever (신규)

**파일**: `src/pipeline/conversation_history_retriever.py`

```python
"""
Step 0: ConversationHistoryRetriever
session_id(= thread_ts)로 DynamoDB GSI를 조회하여
이전 대화 이력과 현재 turn_number를 계산한다.
MULTI_TURN_ENABLED=false 이거나 session_id 없으면 건너뜀.
"""

import logging
import os
from typing import Optional
import boto3
from botocore.exceptions import ClientError
from boto3.dynamodb.conditions import Key
from ..models.domain import PipelineContext, ConversationTurn

logger = logging.getLogger(__name__)

_TABLE_NAME = os.getenv("HISTORY_TABLE_NAME", "capa-dev-query-history")
_GSI_NAME = "session_id-turn_number-index"
_MAX_TURNS = int(os.getenv("CONVERSATION_MAX_TURNS", "5"))


class ConversationHistoryRetriever:
    """Step 0 — DynamoDB GSI로 이전 대화 조회"""

    def __init__(self, dynamodb_resource) -> None:
        self._table = dynamodb_resource.Table(_TABLE_NAME)

    def retrieve(self, ctx: PipelineContext) -> PipelineContext:
        """
        session_id가 있으면 GSI 조회 후 ctx에 이력과 turn_number 세팅.
        없거나 실패하면 ctx 그대로 반환 (하위 호환).
        """
        if not ctx.session_id:
            return ctx

        try:
            resp = self._table.query(
                IndexName=_GSI_NAME,
                KeyConditionExpression=Key("session_id").eq(ctx.session_id),
                ScanIndexForward=True,  # turn_number 오름차순
            )
            items = resp.get("Items", [])

            # turn_number 계산: 기존 턴 수 + 1
            ctx.turn_number = len(items) + 1

            # 최근 N턴만 맥락으로 사용
            recent = items[-_MAX_TURNS:] if len(items) > _MAX_TURNS else items
            ctx.conversation_history = [
                ConversationTurn(
                    turn_number=int(item["turn_number"]),
                    question=item.get("original_question", ""),
                    refined_question=item.get("refined_question"),
                    generated_sql=item.get("generated_sql"),
                    answer=item.get("answer"),
                )
                for item in recent
            ]
            logger.info(
                f"Step 0 대화 이력 조회: session_id={ctx.session_id}, "
                f"총 {len(items)}턴, 현재 turn_number={ctx.turn_number}"
            )
        except ClientError as e:
            logger.error(f"Step 0 DynamoDB GSI 조회 실패 (건너뜀): {e}")

        return ctx
```

---

### 3.2 domain.py 변경

**파일**: `src/models/domain.py`

```python
# 신규 추가
class ConversationTurn(BaseModel):
    """이전 대화 턴 — Step 0에서 채워짐, Step 2/5에서 참조"""
    turn_number: int
    question: str
    refined_question: Optional[str] = None
    generated_sql: Optional[str] = None
    answer: Optional[str] = None


# PipelineContext에 아래 필드 추가
class PipelineContext(BaseModel):
    # ... 기존 필드 유지 ...

    # FR-20 추가
    session_id: Optional[str] = None
    turn_number: Optional[int] = None
    slack_thread_ts: Optional[str] = None
    conversation_history: list[ConversationTurn] = Field(default_factory=list)
```

---

### 3.3 Step 2: QuestionRefiner 변경

**파일**: `src/pipeline/question_refiner.py`

`refine()` 메서드에 `conversation_history` 파라미터를 추가하고,
이력이 있으면 시스템 프롬프트에 이전 대화를 포함한다.

```python
def refine(self, question: str, conversation_history: Optional[list] = None) -> str:
    conversation_history = conversation_history or []  # mutable default 방지
    # 이전 대화 이력을 프롬프트에 포함
    history_text = ""
    if conversation_history:
        lines = []
        for turn in conversation_history:
            lines.append(f"[Turn {turn.turn_number}] 질문: {turn.question}")
            if turn.answer:
                lines.append(f"[Turn {turn.turn_number}] 답변: {turn.answer}")
        history_text = "\n[이전 대화 맥락]\n" + "\n".join(lines) + "\n\n"

    messages = [{"role": "user", "content": f"{history_text}현재 질문: {question}"}]

    # 이하 기존 LLM 호출 로직 동일
    ...
```

**동작 예시:**
```
이전 대화 맥락:
  [Turn 1] 질문: 지난달 신규 가입자 수 알려줘
  [Turn 1] 답변: 지난달(2026-02) 신규 가입자는 12,345명입니다.

현재 질문: 연령대별로 나눠줘

→ 정제 결과: "2026년 2월 신규 가입자 수를 연령대별로 분류하여 조회"
```

---

### 3.4 Step 5: SQLGenerator 변경

**파일**: `src/pipeline/sql_generator.py`

`generate()` 메서드에 `conversation_history` 파라미터를 추가하고,
이전 SQL을 참고 자료로 프롬프트에 포함한다.

```python
def generate(
    self,
    question: str,
    rag_context: Optional[RAGContext] = None,
    conversation_history: Optional[list] = None,
) -> str:
    conversation_history = conversation_history or []  # mutable default 방지
    # 이전 SQL을 참고 자료로 추가
    prev_sql_text = ""
    if conversation_history:
        sqls = [t.generated_sql for t in conversation_history if t.generated_sql]
        if sqls:
            prev_sql_text = "\n[이전 대화에서 생성된 SQL 참고]\n"
            for i, sql in enumerate(sqls[-3:], 1):  # 최근 3개만
                prev_sql_text += f"-- 참고 SQL {i}\n{sql}\n\n"

    prompt = f"{date_context}{prev_sql_text}{question}"
    # 이하 기존 Vanna 호출 로직 동일
    ...
```

---

### 3.5 Step 11: DynamoDBHistoryRecorder 변경

**파일**: `src/stores/dynamodb_history.py`

`record()` 메서드에서 `ctx`에 session_id가 있으면 신규 필드를 추가 저장한다.

```python
def record(self, ctx: PipelineContext) -> str:
    # ... 기존 item 구성 ...

    # FR-20: 멀티턴 필드 추가 (session_id 있을 때만)
    if ctx.session_id:
        item["session_id"] = ctx.session_id
        item["turn_number"] = ctx.turn_number or 1

    # FR-24: slack_thread_ts 저장
    if ctx.slack_thread_ts:
        item["slack_thread_ts"] = ctx.slack_thread_ts

    # FR-20: LLM 답변 저장 (answer)
    if ctx.analysis and ctx.analysis.answer:
        item["answer"] = ctx.analysis.answer[:500]  # 최대 500자 트림

    # 이하 기존 PutItem 로직 동일
    ...
```

---

### 3.6 QueryPipeline.__init__() 변경 (Gap 1 수정)

**파일**: `src/query_pipeline.py`

`_conversation_retriever` 초기화를 `__init__`에 추가한다.
`MULTI_TURN_ENABLED=false`이면 None으로 유지하여 Step 0을 건너뜀.

```python
def __init__(self, ...) -> None:
    # ... 기존 초기화 로직 유지 ...

    # FR-20: 멀티턴 대화 이력 조회기 초기화
    multi_turn_enabled = os.getenv("MULTI_TURN_ENABLED", "false").lower() == "true"
    if multi_turn_enabled:
        _dynamodb = boto3.resource("dynamodb", region_name=aws_region)
        self._conversation_retriever = ConversationHistoryRetriever(_dynamodb)
    else:
        self._conversation_retriever = None
```

### 3.7 QueryPipeline.run() 변경

**파일**: `src/query_pipeline.py`

```python
async def run(
    self,
    question: str,
    slack_user_id: str = "",
    slack_channel_id: str = "",
    conversation_id: Optional[str] = None,   # ← 파라미터 추가
) -> PipelineContext:
    # conversation_id = thread_ts (FR-24에서 전달)
    # slack_thread_ts도 동일한 값이므로 conversation_id로 통일
    ctx = PipelineContext(
        original_question=question,
        slack_user_id=slack_user_id,
        slack_channel_id=slack_channel_id,
        session_id=conversation_id,          # ← 추가
        slack_thread_ts=conversation_id,     # ← thread_ts = conversation_id (동일값)
    )

    # Step 0: 대화 이력 조회 (MULTI_TURN_ENABLED=true 이고 session_id 있을 때만)
    if self._conversation_retriever and ctx.session_id:
        ctx = self._conversation_retriever.retrieve(ctx)

    # Step 1~11: 기존 로직 동일
    # (Step 2, 5 호출 시 conversation_history 전달 추가)
    ctx.refined_question = self._question_refiner.refine(
        question,
        conversation_history=ctx.conversation_history,  # ← 추가
    )
    ...
    ctx.generated_sql = self._sql_generator.generate(
        question=ctx.refined_question,
        rag_context=ctx.rag_context,
        conversation_history=ctx.conversation_history,  # ← 추가
    )
```

---

### 3.8 main.py: QueryRequest → run() 연결 (Gap 2 수정)

**파일**: `src/main.py`

`conversation_id` 하나만 전달한다. `slack_thread_ts`는 run() 내부에서 동일하게 처리.

```python
@app.post("/query")
async def query(req: QueryRequest) -> QueryResponse:
    ctx = await pipeline.run(
        question=req.question,
        slack_user_id=req.slack_user_id,
        slack_channel_id=req.slack_channel_id,
        conversation_id=req.conversation_id,    # ← thread_ts 값이 들어옴 (FR-24)
    )
    return QueryResponse(
        ...
        session_id=ctx.session_id,              # ← 클라이언트에 반환 (다음 턴에 재전송)
    )
```

---

## 4. 데이터 모델

### 4.1 DynamoDB GSI

```
기존 테이블: capa-dev-query-history

신규 GSI:
  이름: session_id-turn_number-index
  PK:   session_id  (String)
  SK:   turn_number (Number)
  투영: ALL

Terraform 추가:
  global_secondary_index {
    name            = "session_id-turn_number-index"
    hash_key        = "session_id"
    range_key       = "turn_number"
    projection_type = "ALL"
  }
  attribute {
    name = "session_id"
    type = "S"
  }
  attribute {
    name = "turn_number"
    type = "N"
  }
```

### 4.2 저장 레코드 예시 (Turn 2)

```json
{
  "history_id":       "uuid-bbb-222",
  "session_id":       "1711234567.123456",
  "turn_number":      2,
  "slack_thread_ts":  "1711234567.123456",
  "slack_user_id":    "a1b2c3d4e5f6g7h8",
  "slack_channel_id": "C987654321",
  "original_question": "연령대별로 나눠줘",
  "refined_question":  "2026년 2월 신규 가입자 수를 연령대별로 분류하여 조회",
  "generated_sql":     "SELECT age_group, COUNT(*) ...",
  "answer":            "2026년 2월 신규 가입자를 연령대별로 집계한 결과...",
  "ttl":               1234567890
}
```

---

## 5. API 변경사항

### 5.1 QueryRequest (변경 없음)

```python
conversation_id: Optional[str] = Field(None, description="세션 ID = Slack thread_ts")
```

### 5.2 QueryResponse (session_id 추가)

```python
session_id: Optional[str] = Field(None, description="세션 ID (클라이언트 재전송용)")
```

---

## 6. 환경변수

| ENV | 기본값 | 설명 |
|-----|--------|------|
| `MULTI_TURN_ENABLED` | `false` | Feature Flag (true로 변경 시 활성화) |
| `CONVERSATION_MAX_TURNS` | `5` | 맥락으로 사용할 최근 턴 수 |
| `HISTORY_TABLE_NAME` | `capa-dev-query-history` | DynamoDB 테이블명 (기존과 동일) |

---

## 7. 예외 처리

| 상황 | 처리 방식 |
|------|---------|
| `conversation_id` 없음 | Step 0 건너뜀, 기존 파이프라인 동작 |
| `MULTI_TURN_ENABLED=false` | Step 0 건너뜀, 기존 파이프라인 동작 |
| GSI 조회 실패 (ClientError) | 로그 남기고 이력 없이 진행 (graceful degradation) |
| 첫 번째 턴 (이력 없음) | conversation_history=[], turn_number=1 |
| answer 500자 초과 | 500자로 트림 후 저장 |

---

## 8. 구현 순서

```
1. domain.py — ConversationTurn 모델, PipelineContext 필드 추가
2. dynamodb_history.py — session_id, turn_number, answer, slack_thread_ts 저장
3. conversation_history_retriever.py — Step 0 신규 구현
4. question_refiner.py — conversation_history 파라미터 (Optional[list]), 프롬프트 주입
5. sql_generator.py — conversation_history 파라미터 (Optional[list]), 이전 SQL 주입
6. query_pipeline.py — __init__에 _conversation_retriever 초기화, run() 파라미터 추가
7. main.py — conversation_id → run() 전달, session_id 응답 추가
8. 11-k8s-apps.tf — GSI 추가, ENV 추가 (MULTI_TURN_ENABLED=false)
9. IAM — vanna-api IRSA 역할에 dynamodb:Query 권한 추가 (GSI 조회용)
10. 단위 테스트 작성
```

# [Plan] Slack 스레드 기반 응답 출력 (FR-24)

## Executive Summary

| 항목 | 내용 |
|------|------|
| **Feature** | txt-to-sql-slack-thread |
| **FR ID** | FR-24 |
| **작성일** | 2026-03-21 |
| **담당** | t1 |
| **참고 문서** | `docs/t1/text-to-sql/00_mvp_develop/02-design/features/phase-1-text-to-sql.design.md` (Phase 1), `docs/t1/text-to-sql/01_multi-turn-conversation/01-plan/features/multi-turn-conversation.plan.md` (FR-20) |

### Value Delivered (4관점)

| 관점 | 내용 |
|------|------|
| **Problem** | 현재 파이프라인은 각 쿼리 결과를 별도 메시지로 Slack에 출력하여 여러 질문이 채널을 오염시키고, 사용자가 대화 흐름을 추적하기 어려움. Phase 2 FR-20(다중 턴 대화)를 구현하려면 사전에 스레드 구조로 응답을 정리해야 함 |
| **Solution** | Slack Bot의 응답 포맷팅을 **스레드 기반으로 변경**: 사용자 질문에 대한 초기 응답 메시지(스레드 루트)를 생성한 후, 쿼리 결과 및 AI 분석을 동일 스레드 내 답글로 구성. `thread_ts` 파라미터를 통해 모든 응답을 단일 스레드로 통합 |
| **Function UX Effect** | 사용자는 Slack 채널을 깔끔하게 유지하면서도 각 질문에 대한 완전한 대화 맥락(질문 → 실행 → 결과 → 분석)을 스레드 내에서 한눈에 볼 수 있음. 후속 질문도 동일 스레드 내에서 진행 가능 |
| **Core Value** | 스레드 기반 구조를 기초로 하면, Phase 2 FR-20(세션/대화 이력 관리)을 구현할 때 `session_id` ↔ `thread_ts` 매핑만으로 대화 이력을 자동 조회·저장 가능. 즉, Phase 1과 Phase 2 간 기술 부채 없이 자연스러운 확장 가능 |

---

## 1. 배경 및 목적

### 1.1 문제 정의 (현재 Phase 1)

```
[AS-IS — 메시지 기반 출력]

사용자: "지난달 신규 가입자 수 알려줘"
  → Bot 응답1: ① 헤더 + 질문 + SQL + 테이블 (메시지1)
  → Bot 응답2: ② 차트 이미지 (메시지2)
  → Bot 응답3: ③ AI 분석 + Redash 링크 + 피드백 (메시지3)

[채널 상태]
  메시지1 | 메시지2 | 메시지3 | (다른 사용자 질문) | 메시지4 | 메시지5 | ...
  ├─────────────────────────┤
  └ 채널이 복잡해지고 대화 추적 어려움
```

**구조적 문제:**
- 각 쿼리 결과가 3개 메시지로 분산되어 채널 오염
- 사용자가 "이전 결과가 뭐였더라?" 찾기 어려움
- Phase 2 FR-20(다중 턴 대화)에서 `conversation_id` 기반 대화 이력 관리 시 메시지 ID로는 연결 불가

### 1.2 목표 (TO-BE)

```
[TO-BE — 스레드 기반 출력]

사용자: "지난달 신규 가입자 수 알려줘"
  → Bot 응답: 스레드 루트 메시지 (thread_ts 생성)
    └─ 스레드 답글1: ① 헤더 + 질문 + SQL + 테이블
    └─ 스레드 답글2: ② 차트 이미지
    └─ 스레드 답글3: ③ AI 분석 + Redash 링크 + 피드백

[채널 상태]
  스레드 루트 메시지 (접힌 상태, 스레드 내용 요약)
  ├─ 스레드 답글1
  ├─ 스레드 답글2
  ├─ 스레드 답글3
  └─ (채널은 깔끔하게 유지)

[추후 연계]
  FR-20: session_id ↔ thread_ts 매핑으로
  "스레드=세션" 개념 적용 가능 ✅
```

---

## 2. 기능 요구사항

### 2.1 FR-24 세부 요구사항

| ID | 요구사항 | 우선순위 |
|----|---------|---------|
| FR-24-01 | Slack Bot이 사용자 질문에 응답할 때 **스레드 루트 메시지** 생성 (간단한 "처리 중..." 텍스트) | Must |
| FR-24-02 | 생성된 스레드의 `thread_ts`를 캡처하고 이후 모든 응답을 해당 스레드로 전송 (`thread_ts` 파라미터 사용) | Must |
| FR-24-03 | 기존 3단계 응답(헤더 + 차트 + 푸터)을 순차적으로 스레드 답글로 전송 (구조 동일, 전송 대상만 변경) | Must |
| FR-24-04 | 스레드 루트 메시지에 결과 요약 정보 업데이트 (선택): 실행 완료 후 루트 메시지를 편집하여 "✅ 완료: {질문 요약}" 표시 | Should |
| FR-24-05 | 오류 발생 시에도 스레드 구조 유지: 에러 메시지를 스레드 답글로 전송 | Must |
| FR-24-06 | 기존 기능과의 호환성: `SLACK_THREAD_ENABLED` Feature Flag로 스레드 모드 ON/OFF 가능 (기본값: `true`) | Should |
| FR-24-07 | 대화 이력 저장 시 `thread_ts`도 함께 저장 (Phase 2 FR-20 연계 준비) | Must |

### 2.2 제외 범위 (Out of Scope)

- 기존 메시지 기반 응답 방식의 완전한 제거 (Feature Flag로 호환성 유지)
- Slack Threaded Replies 이외의 고급 Slack 기능 (예: Slack Canvas, Workflow)
- 스레드 내 메시지 삭제 및 편집 기능 (Slack 정책 준수)

---

## 3. 아키텍처

### 3.1 Slack API 변경

```
[변경 전 — say() 호출]
say(blocks=[...])  # 기본적으로 채널에 메시지 전송

[변경 후 — thread_ts 기반 응답]
1. 스레드 루트 메시지 생성
   response = say(text="🔄 처리 중...")  # thread_ts 자동 생성
   thread_ts = response['ts']

2. 스레드 답글 전송
   say(blocks=[...], thread_ts=thread_ts)
   say(blocks=[...], thread_ts=thread_ts)
   ...

3. (선택) 루트 메시지 업데이트
   client.chat_update(
       channel=channel_id,
       ts=thread_ts,
       text="✅ 완료: 신규 가입자 수 조회"
   )
```

### 3.2 코드 구조 변경

#### 3.2.1 Slack Bot (services/slack-bot/app.py)

현재 구조:
```python
@app.event("app_mention")
def handle_mention(event, say, client):
    # 1. API 호출
    response = requests.post(...)

    # 2. 응답 포맷팅
    say(blocks=_build_header_blocks(result))  # 메시지1
    say(blocks=...)  # 메시지2 (차트)
    say(blocks=_build_footer_blocks(result))  # 메시지3
```

변경 후:
```python
@app.event("app_mention")
def handle_mention(event, say, client):
    channel_id = event.get("channel", "")
    question = event.get("text", "").strip()

    # 1. 스레드 루트 생성
    thread_response = say(text="🔄 처리 중...")
    thread_ts = thread_response['ts']

    # 2. API 호출 (thread_ts → conversation_id로 전달, FR-20 연계)
    response = requests.post(url, json={
        "question": question,
        "slack_user_id": event.get("user", ""),
        "slack_channel_id": channel_id,
        "conversation_id": thread_ts,  # ← session_id = thread_ts (FR-20)
    })

    # 3. 스레드 응답 포맷팅
    say(blocks=_build_header_blocks(result), thread_ts=thread_ts)
    say(blocks=..., thread_ts=thread_ts)  # 차트
    say(blocks=_build_footer_blocks(result), thread_ts=thread_ts)

    # 4. (선택) 루트 업데이트
    client.chat_update(
        channel=channel_id,
        ts=thread_ts,
        text=f"✅ 완료: {question_summary}"
    )
```

#### 3.2.2 thread_ts 저장 (PipelineContext ↔ History)

```python
# models/domain.py - PipelineContext 추가
class PipelineContext(BaseModel):
    # ... 기존 필드 ...
    slack_thread_ts: Optional[str] = None  # FR-24-07: 스레드 ID
```

```python
# src/pipeline/history_recorder.py (Step 11)
# 기존 저장 로직에서 slack_thread_ts도 함께 저장
history_record = {
    "query_id": ...,
    "question": ...,
    "slack_thread_ts": context.slack_thread_ts,  # ← 신규
    ...
}
```

### 3.3 데이터 흐름 (시퀀스)

```
User (Slack)
  │
  ├─ "@capa-bot 지난달 신규 가입자 수?"
  │
  ▼
Slack Bot (app.py)
  │
  ├─ 1️⃣ 스레드 루트 메시지 생성
  │     say(text="🔄 처리 중...")
  │     ▼ thread_ts = "1234567890.1234567"
  │
  ├─ 2️⃣ vanna-api 호출 (동기 또는 비동기)
  │     POST /query → QueryResponse
  │
  ├─ 3️⃣ 스레드 답글1: 헤더 블록
  │     say(blocks=header, thread_ts="1234567890.1234567")
  │
  ├─ 4️⃣ 스레드 답글2: 차트
  │     files.upload_v2(..., thread_ts="1234567890.1234567")
  │
  ├─ 5️⃣ 스레드 답글3: 푸터 블록
  │     say(blocks=footer, thread_ts="1234567890.1234567")
  │
  ├─ 6️⃣ (선택) 루트 메시지 업데이트
  │     client.chat_update(ts="1234567890.1234567", text="✅ 완료")
  │
  └─ vanna-api (내부)
       │
       └─ Step 11: HistoryRecorder
            └─ DynamoDB/파일에 slack_thread_ts 저장
```

---

## 4. API 변경사항

### 4.1 QueryRequest (변경 없음)

```python
# models/api.py:31
conversation_id: Optional[str] = Field(None, description="세션 ID (FR-20)")
```

> 변경 없음. Slack Bot에서 전달 시점에서 처리.

### 4.2 QueryResponse 추가

```python
class QueryResponse(BaseModel):
    # ... 기존 필드 ...
    slack_thread_ts: Optional[str] = Field(None, description="Slack 스레드 ID (FR-24)")
```

> Slack Bot이 thread_ts를 응답에 포함시켜 저장 시 참고 가능.

---

## 5. 신규 추가 ENV

| ENV 이름 | 값 | 설명 |
|---------|---|------|
| `SLACK_THREAD_ENABLED` | `true` (기본값) | Slack 스레드 모드 활성화 Feature Flag |

> DynamoDB, IAM, 네트워크 변경 없음 (Slack API만 변경).

---

## 6. 데이터 모델

### 6.1 DynamoDB History (Phase 1)

기존 JSON Lines 기반 History에 `slack_thread_ts` 필드 추가:

```json
{
  "query_id": "q_20260321_001",
  "session_id": null,
  "slack_user_id": "U123456789",
  "slack_channel_id": "C987654321",
  "slack_thread_ts": "1234567890.1234567",
  "original_question": "지난달 신규 가입자 수 알려줘",
  "refined_question": "2026-02-01 ~ 2026-02-28 기간 신규 사용자 수",
  "sql": "SELECT COUNT(*) FROM users WHERE created_at >= '2026-02-01'...",
  "results": [...],
  "answer": "...",
  "created_at": "2026-03-21T10:00:00Z"
}
```

### 6.2 DynamoDB (Phase 2 FR-20 연계)

별도 테이블 신규 생성 없음. 기존 `capa-dev-query-history` 테이블에 아래 필드가 추가됨 (FR-20).

| 필드 | 설명 |
|------|------|
| `session_id` | = `slack_thread_ts` (thread_ts를 세션 ID로 사용) |
| `turn_number` | 세션 내 순번 |
| `answer` | LLM 답변 텍스트 |
| `slack_thread_ts` | Slack 스레드 ID (FR-24-07) |

> FR-24에서 `thread_ts`를 `conversation_id`로 vanna-api에 전달하면,
> FR-20의 Step 11에서 `session_id = thread_ts`로 저장됨. 중복 저장 없음.

---

## 7. 구현 파일 목록

| 파일 | 변경 종류 | 설명 |
|------|---------|------|
| `services/slack-bot/app.py` | 수정 | 스레드 루트 생성 + 답글 전송 로직 추가 |

> **주의**: vanna-api 내부 로직(models, pipeline, history 등)은 Phase 2 FR-20에서 다룬다.
> FR-24에서는 Slack Bot이 `conversation_id=thread_ts`로 vanna-api에 전달하기만 함.

---

## 8. 성공 기준

| 항목 | 기준 |
|------|------|
| 스레드 생성 | 모든 쿼리 응답이 Slack 스레드 내에서 전달됨 |
| 채널 정결성 | 루트 메시지만 채널에 노출, 응답 답글은 스레드로 숨김 |
| 호환성 | `SLACK_THREAD_ENABLED=false`일 때 기존 메시지 방식으로 동작 |
| FR-20 연계 준비 | Slack Bot이 `conversation_id=thread_ts`로 vanna-api에 전달 (저장은 FR-20에서 처리) |
| 에러 처리 | 오류 발생 시에도 스레드 구조 유지 (실패 메시지가 스레드 답글로 전송) |
| Phase 2 준비 | `session_id` ↔ `thread_ts` 매핑 가능한 구조 확보 |

---

## 9. 구현 순서

```
1. Slack Bot 스레드 생성 로직 구현 (say → thread_ts 캡처)
2. 기존 응답 블록을 스레드로 전송하도록 수정
3. conversation_id=thread_ts 를 vanna-api 요청에 포함
4. Feature Flag (SLACK_THREAD_ENABLED) 처리
5. 단위 테스트 작성 (스레드 생성 확인, thread_ts 전달 확인)
6. E2E 테스트 (실제 Slack 채널에서 스레드 출력 확인)
```

---

## 10. 참고: Phase 2 연계 (FR-20)

### 현재 구조 (Phase 1 + FR-24)

```
History 레코드:
{
  "query_id": "q_001",
  "slack_thread_ts": "1234567890.111",  ← FR-24로 추가
  "question": "신규 가입자 수?",
  ...
}

DynamoDB Conversation Sessions (준비 중):
{
  "session_id": "{channel_id}:{user_id}",
  "turn_number": 1,
  "slack_thread_ts": "1234567890.111",  ← FR-24로 이미 저장
  "question": "신규 가입자 수?",
  ...
}
```

### Phase 2 활용 시나리오 (FR-20 구현)

```
Turn 1:
  User: "신규 가입자 수 알려줘"
  Thread: 1234567890.111
  History: session_id + turn_number로 저장

Turn 2 (같은 스레드):
  User: "연령대별로 나눠줘"
  Thread: 1234567890.111 (동일)
  Step 0: DynamoDB에서 session_id 기반 Turn 1 조회
         → thread_ts도 함께 확인하여 대화 연속성 검증
  → FR-20 구현 완료! 🎉
```

**결론**: FR-24(스레드)는 FR-20(다중 턴)의 **필수 기반 구조** 역할 수행

---

## 11. 위험 및 완화책

| 위험 | 영향도 | 완화책 |
|------|--------|--------|
| Slack API `say()` 호출 오류 (thread_ts 미반환) | 높음 | try-except로 thread_ts 캡처, 실패 시 채널 메시지로 폴백 |
| 기존 통합 테스트 깨짐 | 중간 | Feature Flag로 레거시 모드 유지, 점진적 마이그레이션 |
| 대량 쿼리 시 스레드 폭증 | 낮음 | 각 질문별 스레드 독립 (사용자가 정리 가능) |

---

## 12. 마이그레이션 계획

### 마이그레이션 타입: **Feature Flag 점진식**

```
Phase 1 (배포):
  - SLACK_THREAD_ENABLED = true (기본값)
  - 모든 새 응답은 스레드로
  - 기존 코드 경로는 `if not SLACK_THREAD_ENABLED` 로 유지

Phase 1.5 (모니터링):
  - 2주간 실제 운영 환경에서 스레드 동작 확인
  - Slack 채널 피드백 수집

Phase 2 (레거시 제거):
  - SLACK_THREAD_ENABLED = false 경로 제거 (정책 변경 후)
  - 코드 정리
```

---


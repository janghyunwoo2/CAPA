# [Plan] Multi-Turn Session Fix (FR-20 세션 연속성 복구)

## Executive Summary

| 관점 | 내용 |
|------|------|
| **Problem** | Slack Bot이 `event["ts"]`(현재 메시지 ts)를 `conversation_id`로 사용하여, 2번째 질문의 session_id가 1번째와 달라져 DynamoDB 이력 조회가 항상 빈 결과를 반환함 |
| **Solution** | `event.get("thread_ts") or event.get("ts")` 방식으로 변경 — 스레드 답글이면 부모 ts를 session_id로 사용, 신규 메시지면 현재 ts로 신규 세션 시작 |
| **Function UX Effect** | Slack 스레드 내 연속 질문 시 이전 SQL·맥락이 LLM 프롬프트에 자동 주입되어 "지난 결과 기준으로 필터해줘" 같은 연속 질문이 정확히 작동함 |
| **Core Value** | 이미 완성된 DynamoDB 저장/조회 인프라를 Slack Bot 1줄 수정으로 즉시 활성화 — 코드 변경 최소화, 위험도 극히 낮음 |

---

## 1. 배경 및 문제 정의

### 1.1 멀티턴 인프라 현황 (이미 완성됨)

`08_multi-turn-recovery` 작업으로 아래 인프라가 완성 상태임:

| 컴포넌트 | 구현 상태 | 파일 |
|---------|---------|------|
| `DynamoDBHistoryRecorder` | ✅ 완성 | `src/stores/dynamodb_history.py` |
| `ConversationHistoryRetriever` | ✅ 완성 | `src/pipeline/conversation_history_retriever.py` |
| Terraform GSI `session_id-turn_number-index` | ✅ 완성 | `infrastructure/terraform/13-dynamodb.tf` |
| `DYNAMODB_ENABLED=true` | ✅ 설정됨 | `docker-compose.local-e2e.yml:198` |
| `MULTI_TURN_ENABLED=true` | ✅ 설정됨 | `docker-compose.local-e2e.yml:182` |
| `session_id`, `turn_number`, `answer` 저장 | ✅ 완성 | `dynamodb_history.py:71~78` |
| QuestionRefiner / SQLGenerator 이력 주입 | ✅ 완성 | `question_refiner.py`, `sql_generator.py` |

### 1.2 실제 버그 위치

```
services/slack-bot/app.py:279
```

```python
# AS-IS (버그)
thread_ts = None
if SLACK_THREAD_ENABLED:
    thread_ts = event.get("ts")          # ← 현재 메시지의 ts
    # "conversation_id": thread_ts       # 매 메시지마다 다른 값

# TO-BE (수정)
if SLACK_THREAD_ENABLED:
    thread_ts = event.get("thread_ts") or event.get("ts")
    # thread 답글: event["thread_ts"] = 부모 메시지 ts → 동일 session_id 유지
    # 신규 메시지: event["thread_ts"] = None  → event["ts"]로 신규 세션 시작
```

### 1.3 버그 재현 흐름

```
1번째 질문 (신규 메시지)
  event["ts"]        = "1711234567.123456"
  event["thread_ts"] = None
  conversation_id    = "1711234567.123456"  ← session_id로 DynamoDB 저장

2번째 질문 (스레드 답글)   ← 여기서 버그 발생
  event["ts"]        = "1711234568.234567"  ← 새 메시지 ts (다름!)
  event["thread_ts"] = "1711234567.123456"  ← 부모 ts (무시됨)
  conversation_id    = "1711234568.234567"  ← session_id가 달라짐!

ConversationHistoryRetriever.retrieve():
  GSI query: session_id = "1711234568.234567"
  → DynamoDB 조회 결과: [] (빈 배열)  ← 이전 이력 없음
  → conversation_history = []
  → QuestionRefiner, SQLGenerator에 이전 맥락 없이 SQL 생성
```

### 1.4 수정 후 흐름 (TO-BE)

```
1번째 질문 (신규 메시지)
  conversation_id = event.get("thread_ts") or event.get("ts")
                  = None or "1711234567.123456"
                  = "1711234567.123456"  ← session_id로 DynamoDB 저장

2번째 질문 (스레드 답글)
  conversation_id = event.get("thread_ts") or event.get("ts")
                  = "1711234567.123456"  ← 부모 ts 우선 사용!
                  = "1711234567.123456"  ← 동일 session_id!

ConversationHistoryRetriever.retrieve():
  GSI query: session_id = "1711234567.123456"
  → DynamoDB 조회 결과: [turn_1 이력]  ✅
  → conversation_history = [ConversationTurn(turn=1, sql=..., answer=...)]
  → QuestionRefiner, SQLGenerator에 이전 SQL·답변 주입 → 정확한 SQL 생성
```

---

## 2. 수정 범위

### 2.1 수정 파일 (최소 변경)

| 파일 | 변경 내용 | 변경량 |
|------|----------|--------|
| `services/slack-bot/app.py` | `thread_ts = event.get("ts")` → `event.get("thread_ts") or event.get("ts")` | 1줄 변경 |

### 2.2 변경 없는 파일 (검증용 확인)

| 파일 | 현황 | 이유 |
|------|------|------|
| `src/pipeline/conversation_history_retriever.py` | 변경 없음 | GSI 조회 로직 정상 |
| `src/stores/dynamodb_history.py` | 변경 없음 | session_id/turn_number 저장 정상 |
| `infrastructure/terraform/13-dynamodb.tf` | 변경 없음 | GSI 이미 배포됨 |
| `src/query_pipeline.py` | 변경 없음 | conversation_id 전달 정상 |

---

## 3. 검증 계획

### 3.1 단위 테스트 (신규 작성)

```
tests/unit/test_slack_bot_session_id.py
```

| TC ID | 케이스 | 입력 | 기대 결과 |
|-------|-------|------|---------|
| TC-SS-01 | 신규 메시지 | `thread_ts=None, ts="A"` | `conversation_id = "A"` |
| TC-SS-02 | 스레드 답글 | `thread_ts="A", ts="B"` | `conversation_id = "A"` (부모 우선) |
| TC-SS-03 | SLACK_THREAD_ENABLED=false | 어떤 경우든 | `conversation_id = None` |

### 3.2 통합 테스트 (기존 활용)

```
tests/integration/test_multi_turn_dynamodb.py
```

TC-IT-01~04 기존 테스트 + 스레드 연속 질문 시나리오 추가:

| TC ID | 케이스 | 검증 방법 |
|-------|-------|---------|
| TC-IT-05 | 2번 질문 시 DynamoDB 이력 조회 성공 | `conversation_history` 길이 >= 1 |
| TC-IT-06 | `QuestionRefiner`에 이전 SQL 주입됨 | 로그 확인 |

### 3.3 수동 E2E 테스트 (Slack)

1. Slack 채널에 첫 번째 질문: "어제 CTR이 가장 높은 캠페인은?"
2. 응답 스레드에 두 번째 질문: "그 캠페인의 시간대별 추이도 보여줘"
3. 기대: 두 번째 SQL에 캠페인 ID 또는 이전 필터 조건이 반영됨

---

## 4. 구현 일정

| Day | 작업 | 산출물 |
|-----|------|--------|
| Day 1 (오전) | `slack-bot/app.py` 1줄 수정 | 코드 변경 |
| Day 1 (오후) | 단위 테스트 `test_slack_bot_session_id.py` 작성 | 테스트 코드 |
| Day 1 (오후) | Docker E2E로 통합 테스트 실행 | 테스트 결과 |
| Day 2 | Slack 수동 E2E 테스트 | 테스트 결과 문서 |

**총 예상 기간**: 2일

---

## 5. 위험 요소 및 대응

| 위험 | 가능성 | 영향 | 대응 |
|------|--------|------|------|
| DynamoDB 테이블이 실 환경에 미배포 | 낮음 | 높음 | terraform apply 상태 먼저 확인 |
| `turn_number` Decimal 타입 문제 (DynamoDB) | 중간 | 중간 | `int(item["turn_number"])` 이미 처리됨 (retriever:46) |
| `SLACK_THREAD_ENABLED=false`인 경우 | 낮음 | 없음 | thread_ts=None → conversation_id=None → Step 0 스킵 (기존 동작 유지) |
| `event["thread_ts"]`가 없는 Slack 이벤트 유형 | 낮음 | 낮음 | `or event.get("ts")` fallback으로 처리 |

---

## 6. 성공 기준

| 항목 | 기준 | 검증 방법 |
|------|------|---------|
| 단위 테스트 | TC-SS-01~03 PASS | `pytest tests/unit/test_slack_bot_session_id.py` |
| 통합 테스트 | TC-IT-05~06 PASS | Docker E2E 환경 |
| 수동 E2E | 2번째 질문에 이전 SQL 맥락 반영 | Slack 채널 실제 확인 |
| 기존 테스트 회귀 없음 | 기존 pytest 전체 PASS | `pytest tests/unit/` |

---

## 7. 연관 문서

| 문서 | 경로 |
|------|------|
| 08_multi-turn-recovery Plan | `docs/t1/text-to-sql/08_multi-turn-recovery/01-plan/features/multi-turn-recovery.plan.md` |
| ConversationHistoryRetriever | `services/vanna-api/src/pipeline/conversation_history_retriever.py` |
| DynamoDBHistoryRecorder | `services/vanna-api/src/stores/dynamodb_history.py` |
| Slack Bot | `services/slack-bot/app.py` |
| DynamoDB Terraform | `infrastructure/terraform/13-dynamodb.tf` |

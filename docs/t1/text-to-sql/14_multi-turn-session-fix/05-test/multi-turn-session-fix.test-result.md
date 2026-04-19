# [Test Result] Multi-Turn Session Fix

## 테스트 실행 정보

| 항목 | 내용 |
|------|------|
| 실행일 | 2026-03-26 |
| 환경 | Docker 컨테이너 (`capa-slack-bot-e2e`, `capa-vanna-api-e2e`) |
| 수정 파일 | `services/slack-bot/app.py`, `services/vanna-api/src/stores/dynamodb_history.py` |

---

## 근본 원인 분석

멀티턴이 작동하지 않은 원인은 **2개의 독립 버그**가 겹쳐 있었음.

### BUG-A: DynamoDB 이력 저장 항상 실패 (진짜 근본 원인)

| 항목 | 내용 |
|------|------|
| **파일** | `services/vanna-api/src/stores/dynamodb_history.py:47` |
| **증상** | `ValidationException: The AttributeValue for a key attribute cannot contain an empty string value. IndexName: channel-index, IndexKey: slack_channel_id` |
| **원인** | `slack_channel_id=""` (빈 문자열)을 DynamoDB에 저장 시도 → `channel-index` GSI 해시키는 빈 문자열 불허 → **PutItem 항상 실패** → 이력 0건 저장 |
| **영향** | 1번째 질문 이력이 DynamoDB에 저장되지 않음 → 2번째 질문에서 조회해도 항상 빈 결과 |
| **수정** | `ctx.slack_channel_id` → `ctx.slack_channel_id or None` (빈 문자열 → None → 기존 None 필터에 의해 제거) |

### BUG-B: Slack 스레드 session_id 불연속

| 항목 | 내용 |
|------|------|
| **파일** | `services/slack-bot/app.py:279` |
| **증상** | 2번째 질문의 `conversation_id`가 1번째와 달라 DynamoDB 조회 결과 항상 빈 배열 |
| **원인** | `event.get("ts")` 사용 → 스레드 답글도 자신의 ts로 session_id 설정 → 매 메시지 다른 session_id |
| **수정** | `event.get("thread_ts") or event.get("ts")` → 답글은 부모 ts 사용, 신규 메시지는 자신의 ts |

> **주의**: BUG-A가 있는 한 BUG-B만 수정해도 멀티턴 동작 불가. BUG-A 수정이 선행 조건.

---

## TC-SS: slack-bot session_id 세션 연속성 테스트

| TC | Step | 스텝 역할 | 인풋 | 아웃풋 (실제값) | assert 단언 | 판정 | 왜 이렇게 나왔나 |
|----|------|-----------|------|----------------|-------------|------|-----------------|
| TC-SS-01 | Step 1 | 신규 메시지 → session_id 결정 | `ts="A"`, `thread_ts=None` | `conversation_id = "A"` | `result == "A"` | ✅ PASS | `thread_ts` → None, fallback `ts` = "A" |
| TC-SS-02 | Step 1 | 스레드 답글 → 부모 ts 우선 사용 | `ts="B"`, `thread_ts="A"` | `conversation_id = "A"` | `result == "A"` | ✅ PASS | `thread_ts` = "A" (truthy) → 부모 ts 반환 |
| TC-SS-03 | Step 1 | SLACK_THREAD_ENABLED=false | `ts="A"`, `thread_ts="A"` | `conversation_id = None` | `result is None` | ✅ PASS | 플래그 off → thread_ts=None → Step 0 스킵 |
| TC-SS-04 | Step 1 | `thread_ts` 키 없는 이벤트 | `ts="A"` (thread_ts 키 없음) | `conversation_id = "A"` | `result == "A"` | ✅ PASS | `get("thread_ts")` = None → fallback `ts` |

**결과**: 4/4 PASS (`capa-slack-bot-e2e` 컨테이너)

---

## TC-MR: multi-turn-recovery 기존 테스트 회귀 확인

| TC | Step | 스텝 역할 | 인풋 | 아웃풋 (실제값) | assert 단언 | 판정 | 왜 이렇게 나왔나 |
|----|------|-----------|------|----------------|-------------|------|-----------------|
| TC-MR-01 | Step 1 | QuestionRefiner llm_client 수락 | `llm_client=MagicMock()` | `refiner._client is mock` | `assert refiner._client is mock_client` | ✅ PASS | llm_client 정상 저장 |
| TC-MR-01b | Step 1 | api_key 방식 차단 | `api_key="test-key"` | `TypeError` | `pytest.raises(TypeError)` | ✅ PASS | 구 방식 완전 차단 |
| TC-MR-02 | Step 2 | PHASE2=false → QuestionRefiner에 llm_client 전달 | `phase2_enabled=False` | `llm_client=mock_anthropic` | `assert "llm_client" in call_kwargs` | ✅ PASS | 항상 anthropic_client 생성 후 전달 |
| TC-MR-03 | Step 2 | PHASE2=false → RAGRetriever.anthropic_client=None | `phase2_enabled=False` | `anthropic_client=None` | `assert ... is None` | ✅ PASS | Phase1 Vanna 경로 유지 |
| TC-MR-04 | Step 2 | PHASE2=true → RAGRetriever.anthropic_client 주입 | `phase2_enabled=True` | `anthropic_client=mock_anthropic` | `assert ... is mock_anthropic` | ✅ PASS | Phase2 정상 전달 |

**결과**: 5/5 PASS (`capa-vanna-api-e2e` 컨테이너) — 회귀 없음

---

## TC-IT: Docker E2E 통합 테스트 (API 직접 호출)

| TC | Step | 스텝 역할 | 인풋 | 아웃풋 (실제값) | assert 단언 | 판정 | 왜 이렇게 나왔나 |
|----|------|-----------|------|----------------|-------------|------|-----------------|
| TC-IT-05 | Step 0 | 1번째 질문 DynamoDB 저장 | `session_id="test-session-001"`, `question="오늘 캠페인별 노출수"` | `DynamoDB 이력 저장 완료: 89adc0ab-...` (에러 없음) | `ERROR` 로그 없음 | ✅ PASS | `slack_channel_id or None` 수정으로 PutItem 성공 |
| TC-IT-06 | Step 0 | 2번째 질문 이력 조회 성공 | `session_id="test-session-001"`, `question="그 중에서 campaign_01만"` | `Step 0 대화 이력: turn=2, history=1건` | `history >= 1` | ✅ PASS | DynamoDB GSI 조회로 1번 이력 정상 반환 |
| TC-IT-07 | Step 2 | 이력 주입 → 질문 정제에 맥락 반영 | 2번째 질문 + conversation_history=[turn1] | `정제된 질문: "campaign_01 오늘 노출수"` | 이전 맥락(오늘/노출수) 포함 | ✅ PASS | QuestionRefiner가 이전 대화 맥락으로 "그 중에서" 해석 |

**결과**: 3/3 PASS

---

## TC-E2E: Slack 실제 멀티턴 E2E 테스트 (2026-03-26 12:30)

**테스트 환경**: Slack 실제 채널 → `capa-slack-bot-e2e` → `capa-vanna-api-e2e` → DynamoDB (`capa-dev-query-history`)

| TC | Step | 스텝 역할 | 인풋 | 아웃풋 (실제값) | assert 단언 | 판정 | 왜 이렇게 나왔나 |
|----|------|-----------|------|----------------|-------------|------|-----------------|
| TC-E2E-01 | Step 0 | 1번째 질문 — 신규 세션 시작 | `질문="어제 기기별 클릭수 알려줘"`, 채널 신규 메시지 | `session_id=1774495802.070619, turn=1, history=0건` | `turn==1`, `history==0` | ✅ PASS | 신규 메시지 → `event["ts"]`가 session_id |
| TC-E2E-02 | Step 2~9 | 1번째 SQL 생성·실행 | `어제 기기별 클릭수` | `Redash query_id=1279, 4건 반환` | `row_count==4` | ✅ PASS | 4개 기기(desktop/others/mobile/tablet) 정상 조회 |
| TC-E2E-03 | Step 11 | 1번째 이력 DynamoDB 저장 | `session_id=1774495802.070619, turn=1` | `DynamoDB 이력 저장 완료: 5c3cb4fe-a36f-...` | ERROR 로그 없음 | ✅ PASS | `slack_channel_id or None` 수정으로 PutItem 성공 |
| TC-E2E-04 | Step 0 | 2번째 질문 — 동일 세션 연속 | `질문="두번째 순위 기기 이름 알려줘"`, 스레드 답글 | `session_id=1774495802.070619, turn=2, history=1건` | `session_id 동일`, `history==1` | ✅ PASS | `event.get("thread_ts")` = 부모 ts → 1번 이력 조회 성공 |
| TC-E2E-05 | Step 2 | 이전 AI 분석 맥락으로 질문 정제 | `"두번째 순위 기기 이름 알려줘"` + `answer="...others 2위..."` | `정제된 질문: "기타(3,084클릭) — 이전 대화에서 desktop 1위, others 2위"` | 이전 answer에서 2위 기기 추출 | ✅ PASS | QuestionRefiner가 `t.answer`에서 순위 직접 읽어 답변 생성 |
| TC-E2E-06 | Step 7~9 | 2번째 SQL 생성·실행 (others 단독 조회) | `WHERE device_type='others'` 조건 | `Redash query_id=1280, 1건 반환` | `row_count==1` | ✅ PASS | "기타" 단독 필터 SQL 정확히 생성 |
| TC-E2E-07 | Step 11 | 2번째 이력 DynamoDB 저장 | `session_id=1774495802.070619, turn=2` | `DynamoDB 이력 저장 완료: f5ea611f-bd97-...` | ERROR 로그 없음 | ✅ PASS | 멀티턴 필드(session_id, turn_number, answer) 정상 저장 |

**결과**: 7/7 PASS — Slack 실제 멀티턴 E2E 완전 검증 ✅

---

## 변경 사항 요약

| 파일 | 변경 내용 | 구분 |
|------|---------|------|
| `services/slack-bot/app.py:279` | `event.get("ts")` → `event.get("thread_ts") or event.get("ts")` | BUG-B 수정 |
| `services/vanna-api/src/stores/dynamodb_history.py:47` | `ctx.slack_channel_id` → `ctx.slack_channel_id or None` | BUG-A 수정 (근본 원인) |
| `services/vanna-api/src/stores/dynamodb_history.py:46` | `_hash_user_id(ctx.slack_user_id)` → `... or None` | 동일 패턴 선제 수정 |
| `services/slack-bot/tests/unit/test_slack_bot_session_id.py` | 신규 생성 (TC-SS-01~04) | 테스트 |

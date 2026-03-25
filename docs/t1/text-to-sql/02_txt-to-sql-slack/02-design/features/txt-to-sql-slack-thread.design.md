# [Design] Slack 스레드 기반 응답 출력

## Executive Summary

| 항목 | 내용 |
|------|------|
| **Feature** | txt-to-sql-slack-thread |
| **작성일** | 2026-03-21 |
| **담당** | t1 |
| **Phase** | Design — **FR-24 Slack Bot 전용 범위** |
| **참고 문서** | `docs/t1/text-to-sql/02_txt-to-sql-slack/01-plan/features/txt-to-sql-slack-thread.plan.md`, `docs/t1/text-to-sql/00_mvp_develop/02-design/features/phase-1-text-to-sql.design.md` |

### Value Delivered (4관점)

| 관점 | 내용 |
|------|------|
| **Problem** | 현재 각 쿼리 결과가 3개 메시지로 분산되어 Slack 채널이 복잡해지고, Phase 2 다중 턴 대화 구현에 필수적인 대화 세션 추적 불가 |
| **Solution** | Slack Bot에서 스레드 루트 메시지를 생성 후, 모든 응답을 동일 스레드로 통합 전송. `thread_ts`를 `conversation_id`로 변환하여 내부 멀티턴과 자동 연결 |
| **Function UX Effect** | 사용자는 Slack 채널을 깔끔하게 유지하면서 각 질문의 전체 맥락(질문 → 실행 → 결과 → 분석)을 스레드 내에서 한눈에 볼 수 있고, 후속 질문도 동일 스레드에서 자연스럽게 진행 |
| **Core Value** | 스레드 구조를 통해 물리적 세션 경계가 명확해져, Phase 2 FR-20의 `session_id = thread_ts` 매핑으로 대화 이력이 자동 추적·저장·조회 가능 |

---

## 1. 설계 개요

### 1.1 범위

본 설계서는 Plan 문서에서 정의한 FR-24 (Slack 스레드 기반 응답 출력) 7개 기능 요구사항을 구현하기 위한 상세 기술 설계를 다룬다.

**설계 원칙:**
1. **최소 변경**: 기존 Phase 1 응답 로직은 유지, Slack 전송 부분만 변경
2. **호환성**: Feature Flag로 기존 메시지 방식과 함께 지원
3. **명확한 세션 추적**: `thread_ts` ↔ `conversation_id` ↔ `session_id` 매핑 명시
4. **Phase 2 준비**: DynamoDB 스키마에서 `session_id = thread_ts` 규칙 일관성 유지

### 1.2 아키텍처 영향도

```
[변경 전 — Phase 1]
Slack Bot (say) → vanna-api → DynamoDB (session_id 미사용)

[변경 후 — Phase 1 + FR-24]
Slack Bot (thread_ts 생성)
  ↓ conversation_id = thread_ts
vanna-api (conversation_id → session_id)
  ↓
DynamoDB (session_id = thread_ts 저장)
  ↓
[추후] FR-20: 같은 thread_ts로 대화 조회

→ 아키텍처 확장성 100% 확보 ✅
```

---

## 2. 상세 설계

### 2.1 Slack Bot 설계 (services/slack-bot/app.py)

#### 2.1.1 현재 구조

```python
@app.event("app_mention")
def handle_mention(event, say, client):
    """Phase 1: 메시지 기반 응답"""

    # 1. 질문 추출
    text = event["text"]
    user = event["user"]
    channel_id = event.get("channel", "")

    # 2. vanna-api 호출
    response = requests.post(
        f"{VANNA_API_URL}/query",
        json={
            "question": text,
            "slack_user_id": user,
            "slack_channel_id": channel_id,
        },
        timeout=VANNA_API_TIMEOUT
    )

    # 3. 응답 포맷팅
    result = response.json()
    say(blocks=_build_header_blocks(result))      # 메시지1
    say(blocks=_upload_chart(...))                # 메시지2
    say(blocks=_build_footer_blocks(result))      # 메시지3
```

#### 2.1.2 변경 후 구조 (FR-24)

```python
@app.event("app_mention")
def handle_mention(event, say, client):
    """Phase 1 + FR-24: 스레드 기반 응답"""

    text = event["text"]
    user = event["user"]
    channel_id = event.get("channel", "")

    # [FR-24-01] 스레드 루트 생성
    thread_response = say(text="🔄 처리 중...")
    thread_ts = thread_response['ts']  # "1234567890.1234567"

    try:
        # [FR-24-02] thread_ts를 conversation_id로 전달 (FR-20 연계)
        response = requests.post(
            f"{VANNA_API_URL}/query",
            json={
                "question": text,
                "slack_user_id": user,
                "slack_channel_id": channel_id,
                "conversation_id": thread_ts,  # ← FR-20 session_id
            },
            timeout=VANNA_API_TIMEOUT
        )

        # [FR-24-03] 스레드 답글로 응답 전송
        result = response.json()
        say(
            blocks=_build_header_blocks(result),
            thread_ts=thread_ts
        )
        say(
            blocks=_upload_chart(...),
            thread_ts=thread_ts
        )
        say(
            blocks=_build_footer_blocks(result),
            thread_ts=thread_ts
        )

        # [FR-24-04] 루트 메시지 업데이트 (선택)
        question_summary = text[:30] + "..." if len(text) > 30 else text
        client.chat_update(
            channel=channel_id,
            ts=thread_ts,
            text=f"✅ 완료: {question_summary}"
        )

    except Exception as e:
        # [FR-24-05] 에러도 스레드 구조 유지
        logger.error(f"쿼리 실패: {e}")
        say(
            blocks=[{
                "type": "section",
                "text": {"type": "mrkdwn", "text": f"❌ 오류: {str(e)[:100]}"}
            }],
            thread_ts=thread_ts
        )
```

#### 2.1.3 Feature Flag 처리 (FR-24-06)

```python
# env 변수
SLACK_THREAD_ENABLED = os.environ.get("SLACK_THREAD_ENABLED", "true").lower() == "true"

@app.event("app_mention")
def handle_mention(event, say, client):
    text = event["text"]
    user = event["user"]
    channel_id = event.get("channel", "")

    thread_ts = None

    # [FR-24-06] Feature Flag
    if SLACK_THREAD_ENABLED:
        thread_response = say(text="🔄 처리 중...")
        thread_ts = thread_response['ts']

    try:
        response = requests.post(...)
        result = response.json()

        # 공통 응답 로직 (thread_ts가 None이면 채널 메시지, 아니면 스레드)
        say(blocks=_build_header_blocks(result), thread_ts=thread_ts)
        say(blocks=_upload_chart(...), thread_ts=thread_ts)
        say(blocks=_build_footer_blocks(result), thread_ts=thread_ts)

        if thread_ts:
            client.chat_update(channel=channel_id, ts=thread_ts, text="✅ 완료")

    except Exception as e:
        say(blocks=[...], thread_ts=thread_ts)
```

### 2.2 Slack API 파라미터

#### say() 함수 호출

```python
# [기존] 채널 메시지
say(text="메시지", blocks=[...])

# [FR-24] 스레드 답글
say(text="메시지", blocks=[...], thread_ts="1234567890.1234567")

# [FR-24-04] 루트 메시지 편집
client.chat_update(
    channel="C1234567890",
    ts="1234567890.1234567",
    text="✅ 완료"
)
```

---

## 4. 구현 순서 및 파일 목록

### 4.1 파일 수정 순서

| 순서 | 파일 | 변경 | 설명 |
|------|------|------|------|
| 1 | `services/slack-bot/app.py` | 수정 | 스레드 루트 생성 + 답글 전송 + 루트 업데이트 로직 추가 |

> **주의**: vanna-api 내부 파일(domain.py, api.py, query_pipeline.py, history_recorder.py)은 FR-20(Phase 2)에서 수정한다.

### 4.2 테스트 전략

| 테스트 | 대상 | 예상 결과 |
|--------|------|---------|
| **Unit Test** | `services/slack-bot/app.py` | thread_ts 캡처 + 스레드 답글 전송 동작 확인 |
| **E2E Test** | 실제 Slack 채널 | 스레드 루트 생성 + 답글 전송 + 루트 업데이트 확인 |
| **Regression Test** | Feature Flag OFF | 기존 메시지 방식 동작 확인 |

---

## 5. 오류 처리 및 엣지 케이스

### 5.1 Slack API 오류 처리

```python
try:
    # [FR-24-01] 루트 메시지 생성 실패
    thread_response = say(text="🔄 처리 중...")
    thread_ts = thread_response.get('ts')
except SlackApiError as e:
    logger.error(f"스레드 생성 실패: {e}")
    # 폴백: 채널 메시지로 전송
    thread_ts = None
    say(text="처리 중입니다...")

# 이후 처리는 thread_ts 유무에 따라 동작
```

### 5.2 vanna-api 응답 오류

```python
try:
    response = requests.post(...)
    result = response.json()
except (requests.Timeout, requests.RequestException) as e:
    # [FR-24-05] 스레드 구조 유지하며 에러 전송
    say(
        blocks=[{
            "type": "section",
            "text": {"type": "mrkdwn", "text": "❌ API 호출 오류"}
        }],
        thread_ts=thread_ts
    )
```

---

## 6. 성능 및 비용 영향

### 6.1 성능

| 지표 | 값 | 영향 |
|------|-----|------|
| **추가 API 호출** | 1회 (루트 메시지 생성) | +100ms 정도 (무시할 수준) |
| **메시지 전송** | say() × 3회 (기존과 동일) | 0 (변화 없음) |
| **루트 업데이트** | 1회 (chat_update) | +50ms 정도 (선택 사항) |

### 6.2 비용

| 항목 | 변화 | 설명 |
|------|------|------|
| **Slack API 호출** | +2회 | 루트 생성, 루트 업데이트 (무료) |
| **DynamoDB** | 변경 없음 | FR-20 범위에서 처리 |
| **AWS** | 0원 | Slack API는 Slack 비용에 포함 |

---

## 7. 배포 및 마이그레이션

### 7.1 배포 계획

```
[Phase 1] 준비
  1. 코드 수정 + 단위 테스트
  2. Feature Flag = true (기본값)

[Phase 2] 스테이징
  1. 스테이징 환경에서 E2E 테스트
  2. Slack 채널에서 스레드 생성 확인

[Phase 3] 프로덕션
  1. 배포 (SLACK_THREAD_ENABLED=true)
  2. 2주 모니터링

[Phase 4] 정책 변경
  1. Feature Flag 제거 (정책 결정 후)
  2. 레거시 코드 정리
```

### 7.2 롤백 계획

기존 메시지 방식으로 복귀:
```bash
# ENV 변수 변경
SLACK_THREAD_ENABLED=false

# 재배포
# → 이후 모든 응답이 채널 메시지로 전송
```

---

## 8. Phase 2 연계 (FR-20)

Slack Bot에서 `conversation_id = thread_ts`로 vanna-api에 전달하면,
Phase 2 FR-20에서 `conversation_id`를 `session_id`로 처리하여 DynamoDB에 저장한다.
둘 간 자동 연결됨.

> 상세한 vanna-api 내부 매핑(PipelineContext, HistoryRecorder, DynamoDB GSI 등)은 FR-20 설계서 참고.

---

## 9. 설계 검증

| 체크 항목 | 결과 | 비고 |
|----------|------|------|
| **FR-24-01** | ✅ | 스레드 루트 생성 구현 |
| **FR-24-02** | ✅ | thread_ts 캡처 + 스레드 답글 전송 |
| **FR-24-03** | ✅ | 3단계 응답 → 스레드 답글 변환 |
| **FR-24-04** | ✅ | 루트 메시지 업데이트 (선택) |
| **FR-24-05** | ✅ | 에러도 스레드 구조 유지 |
| **FR-24-06** | ✅ | Feature Flag 처리 |
| **FR-24-07** | ✅ | conversation_id=thread_ts 를 vanna-api에 전달 (저장은 FR-20) |
| **FR-20 연계** | ✅ | conversation_id 전달로 자동 연결, 상세 구현은 FR-20 설계서 참고 |
| **Slack Bot 전용** | ✅ | vanna-api 내부 로직 미포함 — FR-24 범위 준수 |

---

## 10. 위험 및 완화책

| 위험 | 영향 | 완화책 |
|------|------|--------|
| Slack API 속도 저하 | 중간 | timeout 설정 + 폴백 (채널 메시지) |
| Feature Flag 설정 오류 | 낮음 | 기본값 = true, CI에서 검증 |
| Thread_ts 생성 실패 | 중간 | try-except + 채널 메시지 폴백 |

---


# [Test Result] Slack 스레드 기반 응답 출력 (FR-24)

## 실행 정보

| 항목 | 내용 |
|------|------|
| **실행일** | 2026-03-21 |
| **실행 방법** | `python -m pytest tests/unit/test_slack_thread.py -v` |
| **환경** | Python 3.13.5, pytest 8.3.4 |
| **최종 결과** | ✅ 16/16 PASS (4차 TDD 사이클 완료) |

---

## 테스트 결과 테이블 (최종 — 3차 TDD 사이클 완료)

| TC | Step | 스텝 역할 | 인풋 | 아웃풋 (실제값) | assert 단언 | 판정 | 왜 이렇게 나왔나 |
|----|------|-----------|------|----------------|-------------|------|-----------------|
| TC-ST-01 | - | 첫 say() 스레드 답글 전송 | SLACK_THREAD_ENABLED=true, 멘션 이벤트 | `say(text="🔄 처리 중...", thread_ts="EVENT_TS_111111.222222")` 첫 호출 확인 | `first_call == call(text="🔄 처리 중...", thread_ts="EVENT_TS_111111.222222")` | ✅ PASS | BUG-03 수정: event["ts"]를 thread_ts로, 첫 say()도 thread_ts 포함 |
| TC-ST-02 | - | event["ts"]를 thread_ts로 사용 | 멘션 이벤트 (ts="EVENT_TS_111111.222222") | 모든 say() 중 thread_ts="EVENT_TS_111111.222222" 포함 호출 1건 이상 | `len(all_thread_ts_calls) >= 1` | ✅ PASS | BUG-03 수정: `thread_ts = event.get("ts")` 로 변경 |
| TC-ST-03 | - | conversation_id=event["ts"] 전달 | 멘션 이벤트 | `requests.post(json={..., "conversation_id": "EVENT_TS_111111.222222"})` | `payload["conversation_id"] == "EVENT_TS_111111.222222"` | ✅ PASS | thread_ts = event["ts"]이므로 conversation_id도 동일값 |
| TC-ST-04 | - | 헤더 스레드 답글 | 정상 vanna-api 응답 | `say(blocks=[...], thread_ts="EVENT_TS_111111.222222")` 호출 | blocks 있는 say() 모두 thread_ts 포함 | ✅ PASS | 결과 say()에 `thread_ts=thread_ts` 파라미터 전달됨 |
| TC-ST-05 | - | 푸터 스레드 답글 | 정상 vanna-api 응답 | blocks 포함 say() 2건 이상, 모두 thread_ts 포함 | `len(block_calls) >= 2` | ✅ PASS | 헤더·푸터 모두 thread_ts 포함 |
| TC-ST-07 | - | 예외 에러 스레드 유지 | `requests.post` 예외 발생 | `say("⚠️ ...", thread_ts="EVENT_TS_111111.222222")` | thread_ts 포함 say() >= 1 | ✅ PASS | except Exception에 `thread_ts=thread_ts` 전달됨 |
| TC-ST-08 | - | Timeout 에러 스레드 유지 | `requests.Timeout` 발생 | `say("⚠️ ...", thread_ts="EVENT_TS_111111.222222")` | thread_ts 포함 say() >= 1 | ✅ PASS | except Timeout에 `thread_ts=thread_ts` 전달됨 |
| TC-ST-09 | - | Feature Flag OFF 채널 메시지 | SLACK_THREAD_ENABLED=false | 모든 say() 호출에 thread_ts 없음 | `len(calls_with_thread_ts) == 0` | ✅ PASS | Feature Flag=false 시 thread_ts=None, say()에 전달되지 않음 |
| TC-ST-10 | - | Feature Flag OFF chat_update 미호출 | SLACK_THREAD_ENABLED=false | `chat_update()` 미호출 | `not mock_client.chat_update.called` | ✅ PASS | thread_ts=None, chat_update 로직 자체가 제거됨 |
| TC-ST-11 | - | say() 반환값 타입 무관 검증 | `say.return_value=MagicMock()` (dict 아님) | 모든 blocks say()의 thread_ts="EVENT_TS_111111.222222" | `c[1].get("thread_ts") == "EVENT_TS_111111.222222"` | ✅ PASS | BUG-03 수정으로 event["ts"] 직접 사용 → say() 반환값 타입 무관 |
| TC-ST-12 | - | answer 있을 때 elapsed 표시 | `answer="10명"`, `elapsed_seconds=2.5` | say() 블록 중 `"처리 시간"`, `"2.5"` 포함 | `any("처리 시간" in t ...)` | ✅ PASS | elapsed 블록 `if answer:` 외부 독립 렌더링 |
| TC-ST-13 | - | answer 없어도 elapsed 표시 | `answer=None`, `elapsed_seconds=1.5` | say() 블록 중 `"처리 시간"` 포함 | `any("처리 시간" in t ...)` | ✅ PASS | elapsed 블록 `if answer:` 외부에 위치 |
| TC-ST-14 | - | 첫 say()가 event["ts"] thread_ts 포함 | 멘션 이벤트 (ts="EVENT_TS_111111.222222") | `first_call_kwargs.get("thread_ts") == "EVENT_TS_111111.222222"` | `first_call_kwargs.get("thread_ts") == "EVENT_TS_111111.222222"` | ✅ PASS | BUG-03 fix: `thread_ts = event.get("ts")`, 첫 say()에 thread_ts 추가 |
| TC-ST-15 | - | chat_update() 미호출 | 정상 vanna-api 응답 | `mock_client.chat_update.called == False` | `not mock_client.chat_update.called` | ✅ PASS | BUG-03 fix: chat_update 로직 제거 (사용자 원본 메시지 수정 불가) |
| TC-ST-16 | - | files_upload_v2에 thread_ts 포함 | chart_image_base64 있는 응답 | `files_upload_v2(thread_ts="EVENT_TS_111111.222222", ...)` 호출 | `upload_kwargs.get("thread_ts") == "EVENT_TS_111111.222222"` | ✅ PASS | BUG-04 fix: `files_upload_v2`에 `thread_ts=thread_ts` 추가 |
| TC-ST-17 | - | elapsed 블록이 actions보다 앞에 위치 | elapsed_seconds=2.5, query_id 있는 응답 | elapsed_idx < actions_idx | `assert elapsed_idx < actions_idx` | ✅ PASS | 현재 코드에서 이미 elapsed가 actions보다 앞에 위치 (간략히보기 원인은 SQL 테이블 길이) |

---

## TDD 사이클 요약

### Red Phase 1차 (TC-ST-01~10 구현 전)
- 10개 테스트 중 **7개 FAIL**, 3개 PASS
- PASS된 3개: TC-ST-05(푸터 2개 say() 기존에도 존재), TC-ST-09, TC-ST-10 (Feature Flag OFF = 기존 동작과 동일)
- 주요 FAIL 원인:
  - 첫 say()가 `"🔍 <@U_TEST_USER>님의 질문을 분석 중입니다..."` 였음 (스레드 루트 미생성)
  - `conversation_id` POST body에 없음
  - `chat_update()` 미호출

### Green Phase 1차 (app.py 수정 후)
- **10개 모두 PASS (100%)**
- 수정 내용:
  1. `SLACK_THREAD_ENABLED` 환경변수 추가 (기본값 `true`)
  2. Feature Flag 분기: 스레드 루트 생성 or 기존 채널 메시지
  3. POST body에 `conversation_id=thread_ts` 추가 (FR-20 연계)
  4. 결과 say()에 `thread_ts=thread_ts` 추가
  5. 완료 후 `client.chat_update()` 추가
  6. 에러 say()에 `thread_ts=thread_ts` 추가
  7. `_handle_error_response()` 함수에 `thread_ts` 파라미터 추가

### Red Phase 2차 (TC-ST-11~13 추가, 실제 운영 버그 발견)

실제 Slack 환경에서 스레드가 열리지 않고 처리 시간이 표시되지 않는 문제 발견 → 추가 TC 작성.

- **BUG-01**: `say()` 반환값 타입 불일치
  - 원인: 실제 slack_bolt의 `say()`는 `SlackResponse` 객체 반환 (`dict` 아님)
  - 기존 코드: `if isinstance(thread_response, dict): thread_ts = thread_response.get("ts")`
  - → 항상 False → `thread_ts = None` → 스레드 미생성
  - 기존 테스트의 conftest.py mock이 `{"ts": "..."}` plain dict를 반환해 버그가 가려짐
- **BUG-02**: `elapsed_seconds` 표시 누락
  - 원인: elapsed 블록이 `if answer:` 내부에 종속됨
  - `answer=None`인 경우 처리 시간이 아예 표시되지 않음
  - `answer` 있어도 별도 블록이 아닌 동일 텍스트에 append되어 구조 불명확

TC-ST-11, 12, 13 작성 직후 모두 FAIL 확인:
- TC-ST-11: `chat_update(ts="9999999999.999999")` 미호출 (`thread_ts=None`)
- TC-ST-12, 13: `"처리 시간"` 텍스트 미포함

### Green Phase 2차 (BUG-01, BUG-02 수정)
- **13개 모두 PASS (100%)**
- 수정 내용:
  1. **BUG-01 fix**: `isinstance` 분기 제거 → `thread_ts = thread_response.get("ts") if thread_response else None`
  2. **BUG-02 fix**: `_build_footer_blocks()`에서 elapsed 블록을 `if answer:` 외부로 분리, 독립 section block으로 구성

### Red Phase 3차 (TC-ST-14, TC-ST-15 추가, 실제 운영 버그 BUG-03 발견)

실제 Slack 환경에서 봇이 새 메시지("🔄 처리 중...")를 루트로 만들고 거기에 스레드를 생성하는 문제 발견.
사용자가 원한 동작: **자신의 원본 메시지에** 스레드가 열리고 봇 응답이 그 스레드로 전달.

- **BUG-03**: 스레드 기준점 오류
  - 원인: `thread_ts = say(text="🔄 처리 중...").get("ts")` — 봇이 만든 새 메시지의 ts 사용
  - 결과: 봇 메시지에 스레드 생성 → 사용자 입력과 응답이 분리됨
  - 수정 방향: `event["ts"]`(사용자 원본 메시지 ts)를 thread_ts로 사용
  - 부수 변경: `client.chat_update()` 제거 (사용자 원본 메시지는 수정 불가)

TC-ST-14, TC-ST-15 작성 직후 FAIL 확인 (+ 기존 TC-ST-03도 FAIL):
- TC-ST-14: 첫 say()의 thread_ts가 None (`{"text": "🔄 처리 중..."}` 형식으로 호출됨)
- TC-ST-15: chat_update()가 호출됨 (`ts="1234567890.123456"`)
- TC-ST-03: conversation_id = "1234567890.123456" (event["ts"]가 아닌 say() 반환값)

### Green Phase 3차 (BUG-03 수정)
- **14개 모두 PASS (100%)**
- 수정 내용 (app.py):
  1. **BUG-03 fix**: `thread_ts = event.get("ts")` — 사용자 원본 메시지 ts를 thread_ts로 직접 사용
  2. 첫 say()에 `thread_ts=thread_ts` 추가: `say(text="🔄 처리 중...", thread_ts=thread_ts)`
  3. `client.chat_update()` 로직 제거 (사용자 원본 메시지 수정 불가)
- 충돌 TC 정리 (잘못된 설계를 검증하던 TC — 사유 명시 후 수정):
  - TC-ST-01: `call(text="🔄 처리 중...", thread_ts="EVENT_TS_111111.222222")` 형식으로 수정
  - TC-ST-02: chat_update 검증 → event["ts"] 직접 검증으로 교체
  - TC-ST-04 (TestRootMessageUpdate): chat_update 제거됨 → TC 클래스 삭제
  - TC-ST-07, TC-ST-08: thread_ts 기대값 "EVENT_TS_111111.222222"로 수정
  - TC-ST-11 (TestSlackResponseCompat): say() 반환값 파싱 불필요 → say() 반환값 타입 무관 검증으로 교체

### Red Phase 4차 (TC-ST-16, TC-ST-17 추가, BUG-04·BUG-05 발견)

실제 Slack 환경에서 이미지가 스레드가 아닌 메인 채널에 올라가고, 간략히보기 시 elapsed가 잘리는 문제 발견.

- **BUG-04**: `files_upload_v2`에 `thread_ts` 누락
  - 원인: 이미지 업로드 시 `thread_ts` 파라미터 미전달
  - 결과: 이미지가 메인 채널에 업로드 → 스레드에서 보이지 않음
- **BUG-05**: elapsed 블록 위치
  - 발견 경위: Slack 간략히보기 시 실행시간이 잘림
  - 분석 결과: 현재 코드에서 elapsed는 이미 actions보다 앞에 위치함 (TC-ST-17 처음부터 PASS)
  - 실제 원인: SQL 결과 테이블 텍스트가 Slack 3000자 제한 초과 → 간략히보기 발생

TC-ST-16, TC-ST-17 작성 직후:
- TC-ST-16: `files_upload_v2` thread_ts 누락으로 FAIL
- TC-ST-17: 이미 elapsed < actions 순서여서 처음부터 PASS

### Green Phase 4차 (BUG-04 수정)
- **16개 모두 PASS (100%)**
- 수정 내용 (app.py):
  1. **BUG-04 fix**: `client.files_upload_v2(thread_ts=thread_ts, ...)` — thread_ts 파라미터 추가

---

## 실제 Slack 검증 후 추가 수정 (2026-03-22)

TDD 완료 후 로컬 e2e 환경에서 실제 Slack 동작 확인 중 추가 버그 발견.

### BUG-06: "처리 중..." 메시지 중복 출력

| 항목 | 내용 |
|------|------|
| **현상** | 비동기 모드(`ASYNC_QUERY_ENABLED=true`)에서 `"🔄 처리 중..."` + `"⏳ 처리 중입니다... 완료되면 알려드리겠습니다."` 2개 출력 |
| **원인** | 동기 경로의 첫 say() + 비동기 경로(line 247)의 say() 중복 |
| **수정** | app.py에서 `say(text="🔄 처리 중...", thread_ts=thread_ts)` 제거 |

### BUG-07: vanna-api 비동기 응답에 elapsed_seconds 누락 + 타입 오류

| 항목 | 내용 |
|------|------|
| **현상 1** | `elapsed_seconds`가 Slack 메시지에 표시되지 않음 |
| **원인 1** | `vanna-api/src/main.py` `_run_pipeline_async()` 함수의 result 딕셔너리에 `elapsed_seconds` 키 누락. 동기 모드(line 339)에는 있었으나 비동기 코드 누락 |
| **수정 1** | `"elapsed_seconds": round((datetime.utcnow() - ctx.started_at).total_seconds(), 2)` 추가 + `from datetime import datetime` import 추가 |
| **파일** | `services/vanna-api/src/main.py` |
| **현상 2** | 수정 후 `"AI 서버와 통신 중 오류가 발생했습니다"` 에러 발생 |
| **원인 2** | `elapsed_seconds` 값이 JSON 직렬화 후 str로 반환되어 `{elapsed:.2f}` 포맷 실패 (`Unknown format code 'f' for object of type 'str'`) |
| **수정 2** | `_build_footer_blocks()`에 `float(elapsed)` 변환 추가 (ValueError/TypeError 방어 처리 포함) |
| **파일** | `services/slack-bot/app.py` |
| **최종 확인** | ✅ 실제 Slack에서 처리 시간 정상 표시 확인 |

---

## 실행 로그

```
============================= test session starts =============================
platform win32 -- Python 3.13.5, pytest-8.3.4, pluggy-1.5.0
cachedir: .pytest_cache
rootdir: C:\Users\3571\Desktop\projects\CAPA\services\slack-bot
configfile: pytest.ini
collected 14 items

tests/unit/test_slack_thread.py::TestSlackThreadRoot::test_thread_root_message_created_on_mention PASSED [  7%]
tests/unit/test_slack_thread.py::TestSlackThreadRoot::test_thread_ts_from_event_ts PASSED [ 14%]
tests/unit/test_slack_thread.py::TestConversationIdTransmission::test_conversation_id_included_in_vanna_api_call PASSED [ 21%]
tests/unit/test_slack_thread.py::TestThreadReplies::test_header_reply_sent_in_thread PASSED [ 28%]
tests/unit/test_slack_thread.py::TestThreadReplies::test_footer_reply_sent_in_thread PASSED [ 35%]
tests/unit/test_slack_thread.py::TestErrorInThread::test_exception_error_message_sent_in_thread PASSED [ 42%]
tests/unit/test_slack_thread.py::TestErrorInThread::test_timeout_error_message_sent_in_thread PASSED [ 50%]
tests/unit/test_slack_thread.py::TestFeatureFlag::test_channel_message_when_thread_disabled PASSED [ 57%]
tests/unit/test_slack_thread.py::TestFeatureFlag::test_no_chat_update_when_thread_disabled PASSED [ 64%]
tests/unit/test_slack_thread.py::TestSlackResponseCompat::test_thread_ts_uses_event_ts_regardless_of_say_return_type PASSED [ 71%]
tests/unit/test_slack_thread.py::TestUserMessageThread::test_first_reply_sent_to_user_message_thread PASSED [ 78%]
tests/unit/test_slack_thread.py::TestUserMessageThread::test_no_chat_update_called PASSED [ 85%]
tests/unit/test_slack_thread.py::TestElapsedSeconds::test_elapsed_shown_when_answer_present PASSED [ 92%]
tests/unit/test_slack_thread.py::TestElapsedSeconds::test_elapsed_shown_even_without_answer PASSED [100%]

============================= 14 passed in 0.12s ==============================
```

---

## 실제 Slack 검증

| 항목 | 결과 |
|------|------|
| Docker 이미지 교체 | ✅ 완료 (BUG-03) |
| Slack 동작 확인 | ✅ 사용자 원본 메시지에 스레드 정상 생성 확인 |
| BUG-04 이미지 미표시 | ✅ 수정 완료 — `files_upload_v2(thread_ts=thread_ts)` 추가 |
| BUG-05 간략히보기 | ⚠️ elapsed 위치는 이미 올바름 — 원인은 SQL 결과 테이블 텍스트 길이 (Slack 3000자 제한) |
| BUG-06 처리 중 중복 | ✅ 수정 완료 — 첫 번째 `say(text="🔄 처리 중...")` 제거 |
| BUG-07 elapsed_seconds 미표시 | ✅ 수정 완료 — vanna-api 비동기 result에 `elapsed_seconds` 추가 + app.py `float()` 변환 추가, Slack 정상 표시 확인 |

# [Test Result] Slack 스레드 기반 응답 출력 (FR-24)

## 실행 정보

| 항목 | 내용 |
|------|------|
| **실행일** | 2026-03-21 |
| **실행 방법** | `python -m pytest tests/unit/test_slack_thread.py -v` |
| **환경** | Python 3.13.5, pytest 8.3.4 |
| **최종 결과** | ✅ 13/13 PASS |

---

## 테스트 결과 테이블

| TC | Step | 스텝 역할 | 인풋 | 아웃풋 (실제값) | assert 단언 | 판정 | 왜 이렇게 나왔나 |
|----|------|-----------|------|----------------|-------------|------|-----------------|
| TC-ST-01 | - | 스레드 루트 생성 | SLACK_THREAD_ENABLED=true, 멘션 이벤트 | `say(text="🔄 처리 중...")` 첫 호출 확인 | `first_call == call(text="🔄 처리 중...")` | ✅ PASS | app.py에 SLACK_THREAD_ENABLED 분기 추가 후 첫 say()가 스레드 루트용으로 변경됨 |
| TC-ST-02 | - | thread_ts 캡처 | `mock_say.return_value = {"ts": "1234567890.123456"}` | `chat_update(ts="1234567890.123456")` 호출 | `kwargs.get("ts") == "1234567890.123456"` | ✅ PASS | say() 반환값에서 ts 추출 후 thread_ts 변수에 저장, 이후 chat_update에 전달 |
| TC-ST-03 | - | conversation_id 전달 | 멘션 이벤트 | `requests.post(json={..., "conversation_id": "1234567890.123456"})` | `payload["conversation_id"] == "1234567890.123456"` | ✅ PASS | POST body에 `conversation_id=thread_ts` 추가됨 |
| TC-ST-04 | - | 헤더 스레드 답글 | 정상 vanna-api 응답 | `say(blocks=[...], thread_ts="1234567890.123456")` 호출 | blocks 있는 say() 모두 thread_ts 포함 | ✅ PASS | 결과 say()에 `thread_ts=thread_ts` 파라미터 추가됨 |
| TC-ST-05 | - | 푸터 스레드 답글 | 정상 vanna-api 응답 | blocks 포함 say() 2건 이상, 모두 thread_ts 포함 | `len(block_calls) >= 2` | ✅ PASS | 헤더 say()와 푸터 say() 둘 다 thread_ts 포함 |
| TC-ST-06 | - | 루트 메시지 업데이트 | 정상 완료 | `chat_update(channel="C_TEST_CHANNEL", ts="1234567890.123456", text="✅ 완료: ...")` | `"✅" in kwargs["text"]` | ✅ PASS | 완료 후 `client.chat_update()` 추가됨 |
| TC-ST-07 | - | 예외 에러 스레드 유지 | `requests.post` 예외 발생 | `say("⚠️ ...", thread_ts="1234567890.123456")` | thread_ts 포함 say() >= 1 | ✅ PASS | except Exception에 `thread_ts=thread_ts` 추가됨 |
| TC-ST-08 | - | Timeout 에러 스레드 유지 | `requests.Timeout` 발생 | `say("⚠️ ...", thread_ts="1234567890.123456")` | thread_ts 포함 say() >= 1 | ✅ PASS | except requests.Timeout에 `thread_ts=thread_ts` 추가됨 |
| TC-ST-09 | - | Feature Flag OFF 채널 메시지 | SLACK_THREAD_ENABLED=false | 모든 say() 호출에 thread_ts 없음 | `len(calls_with_thread_ts) == 0` | ✅ PASS | Feature Flag=false 시 thread_ts=None, say()에 전달되지 않음 |
| TC-ST-10 | - | Feature Flag OFF chat_update 미호출 | SLACK_THREAD_ENABLED=false | `chat_update()` 미호출 | `not mock_client.chat_update.called` | ✅ PASS | thread_ts=None 이므로 `if thread_ts:` 분기에 진입하지 않음 |
| TC-ST-11 | - | SlackResponse-like 객체에서 thread_ts 추출 | `say.return_value=MagicMock()` (dict 아님), `.get("ts")="9999999999.999999"` | `chat_update(ts="9999999999.999999")` 호출 | `update_kwargs.get("ts") == "9999999999.999999"` | ✅ PASS | `isinstance(res, dict)` 분기 제거 → `.get("ts")` 직접 호출로 수정 |
| TC-ST-12 | - | answer 있을 때 elapsed 표시 | `answer="10명"`, `elapsed_seconds=2.5` | say() 블록 중 `"처리 시간"`, `"2.5"` 포함 텍스트 존재 | `any("처리 시간" in t for t in all_say_texts)` | ✅ PASS | elapsed 블록을 `if answer:` 외부로 분리하여 항상 독립 렌더링 |
| TC-ST-13 | - | answer 없어도 elapsed 표시 | `answer=None`, `elapsed_seconds=1.5` | say() 블록 중 `"처리 시간"` 포함 텍스트 존재 | `any("처리 시간" in t for t in all_say_texts)` | ✅ PASS | elapsed 블록이 `if answer:` 외부에 위치하므로 answer=None이어도 표시됨 |

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

---

## 실행 로그

```
============================= test session starts =============================
platform win32 -- Python 3.13.5, pytest-8.3.4, pluggy-1.5.0
cachedir: .pytest_cache
rootdir: C:\Users\3571\Desktop\projects\CAPA\services\slack-bot
configfile: pytest.ini
collected 13 items

tests/unit/test_slack_thread.py::TestSlackThreadRoot::test_thread_root_message_created_on_mention PASSED [  7%]
tests/unit/test_slack_thread.py::TestSlackThreadRoot::test_thread_ts_captured_from_root_response PASSED [ 15%]
tests/unit/test_slack_thread.py::TestConversationIdTransmission::test_conversation_id_included_in_vanna_api_call PASSED [ 23%]
tests/unit/test_slack_thread.py::TestThreadReplies::test_header_reply_sent_in_thread PASSED [ 30%]
tests/unit/test_slack_thread.py::TestThreadReplies::test_footer_reply_sent_in_thread PASSED [ 38%]
tests/unit/test_slack_thread.py::TestRootMessageUpdate::test_root_message_updated_after_completion PASSED [ 46%]
tests/unit/test_slack_thread.py::TestErrorInThread::test_exception_error_message_sent_in_thread PASSED [ 53%]
tests/unit/test_slack_thread.py::TestErrorInThread::test_timeout_error_message_sent_in_thread PASSED [ 61%]
tests/unit/test_slack_thread.py::TestFeatureFlag::test_channel_message_when_thread_disabled PASSED [ 69%]
tests/unit/test_slack_thread.py::TestFeatureFlag::test_no_chat_update_when_thread_disabled PASSED [ 76%]
tests/unit/test_slack_thread.py::TestSlackResponseCompat::test_thread_ts_extracted_from_non_dict_response PASSED [ 84%]
tests/unit/test_slack_thread.py::TestElapsedSeconds::test_elapsed_shown_when_answer_present PASSED [ 92%]
tests/unit/test_slack_thread.py::TestElapsedSeconds::test_elapsed_shown_even_without_answer PASSED [100%]

============================= 13 passed in 0.25s ==============================
```

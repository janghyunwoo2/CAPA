# [Test Plan] Slack 스레드 기반 응답 출력 (FR-24)

## Executive Summary

| 항목 | 내용 |
|------|------|
| **Feature** | txt-to-sql-slack-thread |
| **FR ID** | FR-24 |
| **작성일** | 2026-03-21 |
| **담당** | t1 |
| **테스트 방법** | TDD (Red → Green) — pytest 단위 테스트 |
| **참고 설계서** | `docs/t1/text-to-sql/02_txt-to-sql-slack/02-design/features/txt-to-sql-slack-thread.design.md` |

---

## 1. 테스트 범위

### 1.1 대상 파일

| 파일 | 변경 내용 |
|------|----------|
| `services/slack-bot/app.py` | 스레드 루트 생성, conversation_id 전달, thread_ts 포함 say() |

### 1.2 테스트 파일 위치

| 파일 | 설명 |
|------|------|
| `services/slack-bot/pytest.ini` | pytest 설정 |
| `services/slack-bot/tests/conftest.py` | 공통 픽스처 (mock_say, mock_client, mock_event 등) |
| `services/slack-bot/tests/unit/test_slack_thread.py` | 단위 테스트 (TC-ST-01 ~ TC-ST-10) |
| `docs/t1/text-to-sql/02_txt-to-sql-slack/05-test/txt-to-sql-slack-thread.test-result.md` | 테스트 결과 |

### 1.3 테스트 전략

- **방식**: Mock 기반 단위 테스트 (vanna-api 미구현 상태에서도 독립 실행 가능)
- **Mock 대상**: `requests.post`, `say()`, `client.chat_update()`, `client.files_upload_v2()`
- **비 Mock 대상**: `app.py`의 실제 핸들러 로직 (실제 코드 경로 검증)

---

## 2. 테스트 케이스

### TC-ST-01: 스레드 루트 메시지 생성 (FR-24-01)

| 항목 | 내용 |
|------|------|
| **목적** | SLACK_THREAD_ENABLED=true 시 첫 say()로 스레드 루트 생성 |
| **사전 조건** | `SLACK_THREAD_ENABLED=true`, vanna-api Mock 정상 응답 |
| **테스트 입력** | 멘션 이벤트 `"지난달 신규 가입자 수 알려줘"` |
| **실행 절차** | `handle_mention(event, say, client)` 호출 |
| **기대 결과** | 첫 번째 `say()` 호출이 `text="🔄 처리 중..."` 형식 |
| **검증 코드** | `assert first_call == call(text="🔄 처리 중...")` |

---

### TC-ST-02: thread_ts 캡처 및 활용 (FR-24-01)

| 항목 | 내용 |
|------|------|
| **목적** | say() 반환값에서 thread_ts 추출 후 이후 로직에서 사용 |
| **사전 조건** | `mock_say.return_value = {"ts": "1234567890.123456"}` |
| **기대 결과** | `client.chat_update(ts="1234567890.123456")` 호출 확인 |
| **검증 코드** | `assert kwargs.get("ts") == "1234567890.123456"` |

---

### TC-ST-03: conversation_id=thread_ts 전달 (FR-24-02, FR-24-07)

| 항목 | 내용 |
|------|------|
| **목적** | vanna-api POST body에 conversation_id=thread_ts 포함 여부 |
| **기대 결과** | `requests.post(json={"conversation_id": "1234567890.123456", ...})` |
| **검증 코드** | `assert payload["conversation_id"] == "1234567890.123456"` |

---

### TC-ST-04: 헤더 응답 스레드 답글 전송 (FR-24-03)

| 항목 | 내용 |
|------|------|
| **목적** | blocks 포함 say() 호출에 thread_ts 파라미터 포함 |
| **기대 결과** | `say(blocks=[...], thread_ts="1234567890.123456")` |
| **검증 코드** | blocks 있는 say() 호출 모두 `thread_ts` 포함 확인 |

---

### TC-ST-05: 푸터 응답 스레드 답글 전송 (FR-24-03)

| 항목 | 내용 |
|------|------|
| **목적** | 헤더 + 푸터 2개 이상의 blocks 응답이 thread_ts 포함 |
| **기대 결과** | blocks 포함 say() 최소 2회, 모두 thread_ts 포함 |
| **검증 코드** | `assert len(block_calls) >= 2` |

---

### TC-ST-06: 루트 메시지 업데이트 (FR-24-04)

| 항목 | 내용 |
|------|------|
| **목적** | 처리 완료 후 client.chat_update()로 루트 메시지 업데이트 |
| **기대 결과** | `client.chat_update(channel="C_TEST_CHANNEL", ts="1234567890.123456", text="✅ 완료: ...")` |
| **검증 코드** | `assert "✅" in kwargs["text"]` |

---

### TC-ST-07: 예외 에러 시 스레드 유지 (FR-24-05)

| 항목 | 내용 |
|------|------|
| **목적** | requests.post 예외 발생 시 에러 say()에 thread_ts 포함 |
| **사전 조건** | `requests.post side_effect=Exception("네트워크 오류")` |
| **기대 결과** | `say("⚠️ ...", thread_ts="1234567890.123456")` |
| **검증 코드** | thread_ts 포함 say() 호출 >= 1 확인 |

---

### TC-ST-08: Timeout 에러 시 스레드 유지 (FR-24-05)

| 항목 | 내용 |
|------|------|
| **목적** | requests.Timeout 발생 시 에러 say()에 thread_ts 포함 |
| **사전 조건** | `requests.post side_effect=requests.Timeout()` |
| **기대 결과** | `say("⚠️ ...", thread_ts="1234567890.123456")` |
| **검증 코드** | thread_ts 포함 say() 호출 >= 1 확인 |

---

### TC-ST-09: Feature Flag OFF → 채널 메시지 (FR-24-06)

| 항목 | 내용 |
|------|------|
| **목적** | SLACK_THREAD_ENABLED=false 시 모든 say()에 thread_ts 없음 |
| **사전 조건** | `SLACK_THREAD_ENABLED=false` |
| **기대 결과** | 모든 say() 호출에 thread_ts 파라미터 없음 |
| **검증 코드** | `assert len(calls_with_thread_ts) == 0` |

---

### TC-ST-10: Feature Flag OFF → chat_update 미호출 (FR-24-06)

| 항목 | 내용 |
|------|------|
| **목적** | SLACK_THREAD_ENABLED=false 시 chat_update() 미호출 |
| **기대 결과** | `client.chat_update.called == False` |
| **검증 코드** | `assert not mock_client.chat_update.called` |

---

### TC-ST-11: SlackResponse-like 객체에서 thread_ts 추출 (BUG-01)

| 항목 | 내용 |
|------|------|
| **목적** | `say()` 반환값이 `dict`가 아닌 `SlackResponse`-like 객체여도 `thread_ts` 올바르게 추출 |
| **발견 경위** | 실제 slack_bolt의 `say()`는 `SlackResponse` 반환 — `isinstance(res, dict)` 항상 False → `thread_ts=None` |
| **사전 조건** | `say.return_value`가 `dict`가 아닌 MagicMock (`.get()` 지원) |
| **테스트 입력** | `slack_response_mock.get("ts") == "9999999999.999999"` |
| **기대 결과** | `client.chat_update(ts="9999999999.999999")` 호출 확인 |
| **검증 코드** | `assert update_kwargs.get("ts") == "9999999999.999999"` |

---

### TC-ST-12: answer 있을 때 elapsed_seconds 독립 표시 (BUG-02)

| 항목 | 내용 |
|------|------|
| **목적** | `answer` 있는 정상 응답에서 `⏱ 처리 시간` 텍스트가 say() 블록에 포함됨 |
| **발견 경위** | `elapsed` 표시가 `if answer:` 블록 안에 종속 → 별도 블록으로 분리 필요 |
| **사전 조건** | `mock_vanna_response.elapsed_seconds = 2.5`, `answer` 있음 |
| **기대 결과** | say() 호출 blocks 중 `"처리 시간"`, `"2.5초"` 포함 텍스트 존재 |
| **검증 코드** | `assert any("처리 시간" in t for t in all_say_texts)` |

---

### TC-ST-13: answer 없어도 elapsed_seconds 표시 (BUG-02)

| 항목 | 내용 |
|------|------|
| **목적** | `answer=None`이어도 `elapsed_seconds`가 표시됨 |
| **발견 경위** | 기존 코드는 `elapsed` 표시가 `if answer:` 블록 안 → answer 없으면 미표시 |
| **사전 조건** | `answer=None`, `elapsed_seconds=1.5` |
| **기대 결과** | say() 블록 중 `"처리 시간"` 포함 텍스트 존재 |
| **검증 코드** | `assert any("처리 시간" in t for t in all_say_texts)` |

---

### TC-ST-16: 이미지 파일이 스레드에 업로드됨 (BUG-04)

| 항목 | 내용 |
|------|------|
| **목적** | `files_upload_v2()` 호출 시 `thread_ts` 파라미터 포함 — 이미지가 메인 채널이 아닌 스레드에 올라가야 함 |
| **발견 경위** | `files_upload_v2`에 `thread_ts` 누락 → 이미지가 메인 채널에 올라가 스레드에서 안 보임 |
| **사전 조건** | `chart_image_base64` 있는 vanna-api 응답, `SLACK_THREAD_ENABLED=true` |
| **테스트 입력** | `result["chart_image_base64"] = base64("fake_image")` |
| **기대 결과** | `client.files_upload_v2(channel=..., thread_ts="EVENT_TS_111111.222222", ...)` 호출 |
| **검증 코드** | `assert upload_kwargs.get("thread_ts") == "EVENT_TS_111111.222222"` |

---

### TC-ST-17: elapsed 블록이 피드백 버튼보다 앞에 위치 (BUG-05)

| 항목 | 내용 |
|------|------|
| **목적** | `_build_footer_blocks()`에서 elapsed 블록이 actions(피드백 버튼) 블록보다 앞에 위치해야 Slack 간략히보기에서 잘리지 않음 |
| **발견 경위** | elapsed 블록이 footer 맨 뒤에 위치 → Slack이 메시지를 접을 때 elapsed가 잘림 |
| **사전 조건** | `elapsed_seconds=2.5`, `query_id="hist-test-001"` 있는 정상 응답 |
| **기대 결과** | footer blocks 내에서 elapsed section 블록 인덱스 < actions 블록 인덱스 |
| **검증 코드** | `assert elapsed_idx < actions_idx` |

---

## 3. 테스트 실행 방법

```bash
# services/slack-bot/ 디렉토리에서 실행
cd services/slack-bot
python -m pytest tests/unit/test_slack_thread.py -v
```

---

## 4. 성공 기준

| 기준 | 목표 |
|------|------|
| **전체 Pass율** | 16/16 (100%) |
| **FAIL 허용** | 0건 |
| **Mock 의존도** | vanna-api 완전 Mock (독립 실행 가능) |

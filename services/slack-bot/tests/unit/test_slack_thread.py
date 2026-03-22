"""
FR-24 Slack 스레드 기반 응답 출력 단위 테스트

TC 목록:
  TC-ST-01: 스레드 루트 메시지 생성 (FR-24-01)
  TC-ST-02: conversation_id=thread_ts 전달 (FR-24-02, FR-24-07)
  TC-ST-03: 응답 say() 에 thread_ts 포함 (FR-24-03)
  TC-ST-04: 완료 후 루트 메시지 업데이트 (FR-24-04)
  TC-ST-05: 에러 시 thread_ts 포함 say() (FR-24-05)
  TC-ST-06: Feature Flag OFF → thread_ts 없음 (FR-24-06)
  TC-ST-11: SlackResponse-like 객체에서 thread_ts 추출 (BUG-01)
  TC-ST-12: answer 있을 때 elapsed_seconds 독립 표시 (BUG-02)
  TC-ST-13: answer 없어도 elapsed_seconds 표시 (BUG-02)
  TC-ST-14: event["ts"]를 thread_ts로 사용하여 첫 say()가 스레드 답글로 전송 (BUG-03)
  TC-ST-15: chat_update() 미호출 — 사용자 원본 메시지 수정 불가 (BUG-03)
  TC-ST-16: files_upload_v2 호출 시 thread_ts 포함 — 이미지가 스레드에 업로드 (BUG-04)
  TC-ST-17: footer blocks에서 elapsed 블록이 actions 블록보다 앞에 위치 (BUG-05)
"""

import sys
import os
import importlib
from unittest.mock import MagicMock, patch, call

import pytest


def _reload_app(monkeypatch, thread_enabled: bool = True):
    """SLACK_THREAD_ENABLED 값을 변경한 후 app 모듈 reload"""
    monkeypatch.setenv("SLACK_THREAD_ENABLED", "true" if thread_enabled else "false")
    # 캐시된 모듈 제거 후 재import
    if "app" in sys.modules:
        del sys.modules["app"]
    slack_app = importlib.import_module("app")
    return slack_app


class TestSlackThreadRoot:
    """TC-ST-01, TC-ST-02: 스레드 답글 전송 (FR-24-01)
    [BUG-03 수정] 새 루트 메시지 생성 방식 → event["ts"]를 thread_ts로 사용하는 방식으로 변경
    """

    def test_thread_root_message_created_on_mention(
        self, mock_say, mock_client, mock_event, mock_vanna_response, monkeypatch
    ):
        """TC-ST-01: SLACK_THREAD_ENABLED=true 시, 첫 번째 say()가 event["ts"]를 thread_ts로 포함하여 스레드 답글로 전송됨
        [BUG-03 수정 사유] 기존 TC는 '새 루트 메시지 생성(say(text="🔄 처리 중..."))' 방식을 검증했으나,
        BUG-03 수정으로 event["ts"]를 thread_ts로 사용하는 방식으로 변경됨.
        """
        slack_app = _reload_app(monkeypatch, thread_enabled=True)

        with patch("requests.post", return_value=mock_vanna_response):
            slack_app.handle_mention(event=mock_event, say=mock_say, client=mock_client)

        # 첫 번째 say() 호출이 event["ts"]를 thread_ts로 포함해야 함
        assert mock_say.call_count >= 1, "say()가 한 번도 호출되지 않음"
        first_call_kwargs = mock_say.call_args_list[0]
        assert first_call_kwargs == call(text="🔄 처리 중...", thread_ts="EVENT_TS_111111.222222"), (
            f"첫 번째 say() 호출 형식 불일치: {first_call_kwargs}"
        )

    def test_thread_ts_from_event_ts(
        self, mock_say, mock_client, mock_event, mock_vanna_response, monkeypatch
    ):
        """TC-ST-02: event["ts"]가 thread_ts로 사용되어 모든 응답 say()에 전달됨
        [BUG-03 수정 사유] 기존 TC는 say() 반환값에서 ts를 추출해 chat_update로 검증했으나,
        BUG-03 수정으로 event["ts"]를 직접 thread_ts로 사용하는 방식으로 변경됨.
        """
        slack_app = _reload_app(monkeypatch, thread_enabled=True)

        with patch("requests.post", return_value=mock_vanna_response):
            slack_app.handle_mention(event=mock_event, say=mock_say, client=mock_client)

        # 모든 say() 호출에 thread_ts="EVENT_TS_111111.222222" 포함 여부 확인
        all_thread_ts_calls = [
            c for c in mock_say.call_args_list
            if c[1].get("thread_ts") == "EVENT_TS_111111.222222"
        ]
        assert len(all_thread_ts_calls) >= 1, (
            f"thread_ts='EVENT_TS_111111.222222' 포함 say() 없음: {mock_say.call_args_list}"
        )


class TestConversationIdTransmission:
    """TC-ST-03: conversation_id=event["ts"] 전달 (FR-24-02, FR-24-07)"""

    def test_conversation_id_included_in_vanna_api_call(
        self, mock_say, mock_client, mock_event, mock_vanna_response, monkeypatch
    ):
        """vanna-api POST body에 conversation_id=event["ts"] 포함 여부 검증"""
        slack_app = _reload_app(monkeypatch, thread_enabled=True)

        with patch("requests.post", return_value=mock_vanna_response) as mock_post:
            slack_app.handle_mention(event=mock_event, say=mock_say, client=mock_client)

        assert mock_post.called, "requests.post()가 호출되지 않음"
        payload = mock_post.call_args[1].get("json", {})

        assert "conversation_id" in payload, (
            f"vanna-api POST body에 conversation_id가 없음: {payload}"
        )
        # event["ts"] 값이 conversation_id로 전달되어야 함
        assert payload["conversation_id"] == "EVENT_TS_111111.222222", (
            f"conversation_id 값이 event['ts']와 다름: {payload.get('conversation_id')}"
        )


class TestThreadReplies:
    """TC-ST-03: 응답 say()에 thread_ts 포함 (FR-24-03)"""

    def test_header_reply_sent_in_thread(
        self, mock_say, mock_client, mock_event, mock_vanna_response, monkeypatch
    ):
        """헤더 블록 say()가 thread_ts 파라미터 포함하여 호출됨"""
        slack_app = _reload_app(monkeypatch, thread_enabled=True)

        with patch("requests.post", return_value=mock_vanna_response):
            slack_app.handle_mention(event=mock_event, say=mock_say, client=mock_client)

        # 스레드 루트 이후의 say() 호출들을 검증
        # blocks가 있는 호출은 모두 thread_ts를 포함해야 함
        block_calls = [c for c in mock_say.call_args_list if c[1].get("blocks")]
        assert len(block_calls) >= 1, "blocks 포함 say() 호출이 없음"

        for block_call in block_calls:
            kwargs = block_call[1]
            assert "thread_ts" in kwargs, (
                f"blocks 포함 say() 호출에 thread_ts 없음: {block_call}"
            )
            # [BUG-03 수정] thread_ts는 event["ts"] = "EVENT_TS_111111.222222"
            assert kwargs["thread_ts"] == "EVENT_TS_111111.222222", (
                f"thread_ts 값 불일치: {kwargs.get('thread_ts')}"
            )

    def test_footer_reply_sent_in_thread(
        self, mock_say, mock_client, mock_event, mock_vanna_response, monkeypatch
    ):
        """푸터 블록 say()도 thread_ts 포함하여 호출됨"""
        slack_app = _reload_app(monkeypatch, thread_enabled=True)

        with patch("requests.post", return_value=mock_vanna_response):
            slack_app.handle_mention(event=mock_event, say=mock_say, client=mock_client)

        # 최소 2개의 blocks 응답(헤더 + 푸터)이 thread_ts 포함해야 함
        block_calls = [c for c in mock_say.call_args_list if c[1].get("blocks")]
        assert len(block_calls) >= 2, (
            f"헤더+푸터 2개 blocks 응답 예상, 실제: {len(block_calls)}개"
        )


class TestErrorInThread:
    """TC-ST-05: 에러 시 thread_ts 포함 say() (FR-24-05)"""

    def test_exception_error_message_sent_in_thread(
        self, mock_say, mock_client, mock_event, monkeypatch
    ):
        """requests.post 예외 발생 시 에러 say()에 thread_ts 포함"""
        slack_app = _reload_app(monkeypatch, thread_enabled=True)

        with patch("requests.post", side_effect=Exception("네트워크 오류")):
            slack_app.handle_mention(event=mock_event, say=mock_say, client=mock_client)

        # 에러 응답 say() 호출 확인 (blocks 포함 또는 text 포함)
        # [BUG-03 수정] 에러 say()는 event["ts"] = "EVENT_TS_111111.222222"를 thread_ts로 포함해야 함
        calls_with_thread_ts = [
            c for c in mock_say.call_args_list
            if c[1].get("thread_ts") == "EVENT_TS_111111.222222"
        ]
        assert len(calls_with_thread_ts) >= 1, (
            f"에러 시 thread_ts 포함 say() 호출 없음. 전체 호출: {mock_say.call_args_list}"
        )

    def test_timeout_error_message_sent_in_thread(
        self, mock_say, mock_client, mock_event, monkeypatch
    ):
        """requests.Timeout 발생 시 에러 say()에 thread_ts 포함"""
        import requests as req_module
        slack_app = _reload_app(monkeypatch, thread_enabled=True)

        with patch("requests.post", side_effect=req_module.Timeout()):
            slack_app.handle_mention(event=mock_event, say=mock_say, client=mock_client)

        # [BUG-03 수정] thread_ts = event["ts"] = "EVENT_TS_111111.222222"
        calls_with_thread_ts = [
            c for c in mock_say.call_args_list
            if c[1].get("thread_ts") == "EVENT_TS_111111.222222"
        ]
        assert len(calls_with_thread_ts) >= 1, (
            f"Timeout 시 thread_ts 포함 say() 호출 없음. 전체 호출: {mock_say.call_args_list}"
        )


class TestFeatureFlag:
    """TC-ST-06: Feature Flag OFF → thread_ts 없음 (FR-24-06)"""

    def test_channel_message_when_thread_disabled(
        self, mock_say, mock_client, mock_event, mock_vanna_response, monkeypatch
    ):
        """SLACK_THREAD_ENABLED=false 시 모든 say()에 thread_ts 없음 (채널 메시지)"""
        slack_app = _reload_app(monkeypatch, thread_enabled=False)

        with patch("requests.post", return_value=mock_vanna_response):
            slack_app.handle_mention(event=mock_event, say=mock_say, client=mock_client)

        # 모든 say() 호출에 thread_ts가 없어야 함
        calls_with_thread_ts = [
            c for c in mock_say.call_args_list
            if c[1].get("thread_ts") is not None
        ]
        assert len(calls_with_thread_ts) == 0, (
            f"SLACK_THREAD_ENABLED=false 인데 thread_ts 포함 say() 발견: {calls_with_thread_ts}"
        )

    def test_no_chat_update_when_thread_disabled(
        self, mock_say, mock_client, mock_event, mock_vanna_response, monkeypatch
    ):
        """SLACK_THREAD_ENABLED=false 시 chat_update() 미호출"""
        slack_app = _reload_app(monkeypatch, thread_enabled=False)

        with patch("requests.post", return_value=mock_vanna_response):
            slack_app.handle_mention(event=mock_event, say=mock_say, client=mock_client)

        assert not mock_client.chat_update.called, (
            "SLACK_THREAD_ENABLED=false 인데 chat_update() 호출됨"
        )


class TestSlackResponseCompat:
    """TC-ST-11: say() 반환값 타입에 무관하게 event["ts"]가 thread_ts로 사용됨 (BUG-03)
    [BUG-03 수정 사유] 기존 TC는 say() 반환값(SlackResponse-like 객체)에서 ts를 추출하는
    BUG-01을 검증했으나, BUG-03 수정으로 event["ts"]를 직접 thread_ts로 사용하므로
    say() 반환값 타입이 무관해짐.
    """

    def test_thread_ts_uses_event_ts_regardless_of_say_return_type(
        self, mock_client, mock_event, mock_vanna_response, monkeypatch
    ):
        """TC-ST-11: say()가 SlackResponse-like 객체를 반환해도 thread_ts는 event["ts"]에서 올바르게 추출됨"""
        slack_app = _reload_app(monkeypatch, thread_enabled=True)

        # say()가 SlackResponse-like 객체를 반환 (dict 아님, .get() 지원 안 함 수준도 포함)
        slack_response_mock = MagicMock()
        say = MagicMock(return_value=slack_response_mock)

        with patch("requests.post", return_value=mock_vanna_response):
            slack_app.handle_mention(event=mock_event, say=say, client=mock_client)

        # say() 반환값 타입과 무관하게 thread_ts = event["ts"] = "EVENT_TS_111111.222222"
        block_calls = [c for c in say.call_args_list if c[1].get("blocks")]
        assert len(block_calls) >= 1, "blocks 포함 say() 없음"
        for c in block_calls:
            assert c[1].get("thread_ts") == "EVENT_TS_111111.222222", (
                f"say() 반환값 타입에 따라 thread_ts가 달라짐: {c[1]}"
            )


class TestUserMessageThread:
    """TC-ST-14, TC-ST-15: BUG-03 — 사용자 원본 메시지에 스레드 열기

    실제 운영 버그: 봇이 새 루트 메시지("🔄 처리 중...")를 만들고 거기에 스레드를 생성.
    사용자가 원한 동작: 자신의 원본 메시지에 스레드가 열리고 봇 응답이 그 스레드로 오는 것.
    수정 방향: event["ts"] 를 thread_ts로 사용, 첫 say()도 thread_ts 포함.
    """

    def test_first_reply_sent_to_user_message_thread(
        self, mock_say, mock_client, mock_event, mock_vanna_response, monkeypatch
    ):
        """TC-ST-14: 첫 번째 say()가 event['ts']를 thread_ts로 포함하여 스레드 답글로 전송됨"""
        slack_app = _reload_app(monkeypatch, thread_enabled=True)

        with patch("requests.post", return_value=mock_vanna_response):
            slack_app.handle_mention(event=mock_event, say=mock_say, client=mock_client)

        # 첫 번째 say() 호출이 event["ts"] 를 thread_ts로 포함해야 함
        assert mock_say.call_count >= 1, "say()가 한 번도 호출되지 않음"
        first_call_kwargs = mock_say.call_args_list[0][1]
        assert first_call_kwargs.get("thread_ts") == "EVENT_TS_111111.222222", (
            f"첫 say()의 thread_ts가 event['ts']와 다름: {first_call_kwargs}"
        )

    def test_no_chat_update_called(
        self, mock_say, mock_client, mock_event, mock_vanna_response, monkeypatch
    ):
        """TC-ST-15: chat_update() 미호출 — 사용자 원본 메시지는 수정 불가"""
        slack_app = _reload_app(monkeypatch, thread_enabled=True)

        with patch("requests.post", return_value=mock_vanna_response):
            slack_app.handle_mention(event=mock_event, say=mock_say, client=mock_client)

        assert not mock_client.chat_update.called, (
            f"chat_update()가 호출됨 — 사용자 원본 메시지 수정은 금지: {mock_client.chat_update.call_args}"
        )


class TestElapsedSeconds:
    """TC-ST-12, TC-ST-13: elapsed_seconds 독립 표시 (BUG-02)"""

    def _collect_say_texts(self, say_mock: MagicMock) -> list[str]:
        """say() 호출에서 blocks 내 모든 텍스트를 수집"""
        texts = []
        for c in say_mock.call_args_list:
            for block in c[1].get("blocks", []):
                text = block.get("text", {}).get("text", "")
                if text:
                    texts.append(text)
        return texts

    def test_elapsed_shown_when_answer_present(
        self, mock_say, mock_client, mock_event, mock_vanna_response, monkeypatch
    ):
        """answer가 있는 정상 응답에서 ⏱ 처리 시간이 say() 블록에 포함됨 (TC-ST-12)"""
        slack_app = _reload_app(monkeypatch, thread_enabled=True)

        with patch("requests.post", return_value=mock_vanna_response):
            slack_app.handle_mention(event=mock_event, say=mock_say, client=mock_client)

        all_texts = self._collect_say_texts(mock_say)
        elapsed_texts = [t for t in all_texts if "처리 시간" in t]

        assert len(elapsed_texts) >= 1, (
            f"처리 시간 표시 없음. 전체 say() 텍스트: {all_texts}"
        )
        assert "2.5" in elapsed_texts[0], (
            f"처리 시간 값(2.5초) 불일치: {elapsed_texts[0]}"
        )

    def test_elapsed_shown_even_without_answer(
        self, mock_client, mock_event, monkeypatch
    ):
        """answer=None이어도 elapsed_seconds가 표시됨 (TC-ST-13)

        기존 버그: elapsed 표시가 if answer: 블록 안에 종속되어 answer 없으면 미표시.
        """
        slack_app = _reload_app(monkeypatch, thread_enabled=True)

        import requests as req_module
        no_answer_response = MagicMock(spec=req_module.Response)
        no_answer_response.status_code = 200
        no_answer_response.json.return_value = {
            "original_question": "지난달 신규 가입자 수 알려줘",
            "sql": "SELECT COUNT(*) FROM users",
            "results": [{"count": 12345}],
            "answer": None,
            "query_id": "hist-test-no-answer",
            "elapsed_seconds": 1.5,
        }

        say = MagicMock(return_value={"ts": "1234567890.123456"})

        with patch("requests.post", return_value=no_answer_response):
            slack_app.handle_mention(event=mock_event, say=say, client=mock_client)

        all_texts = self._collect_say_texts(say)
        elapsed_texts = [t for t in all_texts if "처리 시간" in t]

        assert len(elapsed_texts) >= 1, (
            f"answer=None 일 때도 처리 시간이 표시되어야 함. 전체 텍스트: {all_texts}"
        )


class TestImageUpload:
    """TC-ST-16: 이미지가 스레드에 업로드됨 (BUG-04)"""

    def test_files_upload_v2_includes_thread_ts(
        self, mock_say, mock_client, mock_event, monkeypatch
    ):
        """TC-ST-16: chart_image_base64 있을 때 files_upload_v2에 thread_ts 포함"""
        import base64 as b64_mod
        import requests as req_module

        slack_app = _reload_app(monkeypatch, thread_enabled=True)

        chart_response = MagicMock(spec=req_module.Response)
        chart_response.status_code = 200
        chart_response.json.return_value = {
            "original_question": "지난달 신규 가입자 수 알려줘",
            "sql": "SELECT COUNT(*) FROM users",
            "results": [{"count": 1}],
            "answer": "1명입니다.",
            "query_id": "hist-chart-001",
            "elapsed_seconds": 1.0,
            "chart_image_base64": b64_mod.b64encode(b"fake_png_data").decode(),
        }

        with patch("requests.post", return_value=chart_response):
            slack_app.handle_mention(event=mock_event, say=mock_say, client=mock_client)

        assert mock_client.files_upload_v2.called, "files_upload_v2()가 호출되지 않음"
        upload_kwargs = mock_client.files_upload_v2.call_args[1]
        assert upload_kwargs.get("thread_ts") == "EVENT_TS_111111.222222", (
            f"files_upload_v2에 thread_ts 없음 — 이미지가 메인 채널에 올라감: {upload_kwargs}"
        )


class TestFooterBlockOrder:
    """TC-ST-17: footer blocks에서 elapsed 블록이 actions 블록보다 앞에 위치 (BUG-05)"""

    def test_elapsed_block_between_redash_and_actions(
        self, mock_say, mock_client, mock_event, mock_vanna_response, monkeypatch
    ):
        """TC-ST-17: footer blocks 내 순서 — redash → elapsed → actions (피드백버튼)
        elapsed가 Redash 링크와 피드백 버튼 사이에 위치해야 Slack에서 잘리지 않음.
        """
        slack_app = _reload_app(monkeypatch, thread_enabled=True)

        with patch("requests.post", return_value=mock_vanna_response):
            slack_app.handle_mention(event=mock_event, say=mock_say, client=mock_client)

        # footer blocks: actions 타입 블록이 있는 say() 찾기
        footer_call = None
        for c in mock_say.call_args_list:
            blocks = c[1].get("blocks", [])
            if any(b.get("type") == "actions" for b in blocks):
                footer_call = c
                break

        assert footer_call is not None, "actions 블록 포함 say() 호출 없음"
        blocks = footer_call[1]["blocks"]

        redash_idx = next(
            (i for i, b in enumerate(blocks)
             if b.get("type") == "section" and "Redash" in b.get("text", {}).get("text", "")),
            None,
        )
        elapsed_idx = next(
            (i for i, b in enumerate(blocks)
             if b.get("type") == "section" and "처리 시간" in b.get("text", {}).get("text", "")),
            None,
        )
        actions_idx = next(
            (i for i, b in enumerate(blocks) if b.get("type") == "actions"),
            None,
        )

        assert redash_idx is not None, f"Redash 블록 없음: {blocks}"
        assert elapsed_idx is not None, f"elapsed 블록 없음: {blocks}"
        assert actions_idx is not None, f"actions 블록 없음: {blocks}"
        assert redash_idx < elapsed_idx < actions_idx, (
            f"블록 순서 불일치 — redash({redash_idx}), elapsed({elapsed_idx}), actions({actions_idx})"
        )

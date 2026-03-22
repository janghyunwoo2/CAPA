"""
Multi-Turn Thread Wiring 단위 테스트 (Slack Bot)

TC 목록:
  TC-WI-07: 스레드 답글 → event["thread_ts"]를 conversation_id로 사용
  TC-WI-08: 새 채널 메시지 → event["ts"]를 conversation_id로 사용
"""

import importlib
import sys
from unittest.mock import MagicMock, patch

import pytest


def _reload_app(monkeypatch, thread_enabled: bool = True, async_enabled: bool = False):
    """환경변수 변경 후 app 모듈 reload"""
    monkeypatch.setenv("SLACK_THREAD_ENABLED", "true" if thread_enabled else "false")
    monkeypatch.setenv("ASYNC_QUERY_ENABLED", "true" if async_enabled else "false")
    if "app" in sys.modules:
        del sys.modules["app"]
    return importlib.import_module("app")


class TestMultiTurnThreadWiring:
    def test_thread_reply_uses_thread_ts_as_conversation_id(
        self, mock_say, mock_client, mock_vanna_response, monkeypatch
    ):
        """TC-WI-07: 스레드 답글(event['thread_ts'] 존재) → conversation_id == event['thread_ts']

        Turn 2+ 에서는 event["thread_ts"](스레드 루트 ts)를 conversation_id로 전달해야 한다.
        현재 버그: event.get("ts") 를 사용해 답글 자체의 ts가 conversation_id로 들어감.
        """
        slack_app = _reload_app(monkeypatch, thread_enabled=True, async_enabled=False)

        # Turn 2: 스레드 답글 이벤트 (thread_ts != ts)
        thread_reply_event = {
            "text": "기기별로 나눠줘",
            "user": "U_TEST_USER",
            "channel": "C_TEST_CHANNEL",
            "ts": "REPLY_TS_222222.333333",          # 답글 자체 ts
            "thread_ts": "ROOT_TS_111111.222222",    # 스레드 루트 ts → 이게 conversation_id여야 함
        }

        captured_payload = {}

        def _mock_post(url, json=None, headers=None, timeout=None):
            if json:
                captured_payload.update(json)
            return mock_vanna_response

        with patch("requests.post", side_effect=_mock_post):
            slack_app.handle_mention(
                event=thread_reply_event, say=mock_say, client=mock_client
            )

        assert captured_payload.get("conversation_id") == "ROOT_TS_111111.222222"

    def test_new_message_uses_ts_as_conversation_id(
        self, mock_say, mock_client, mock_vanna_response, monkeypatch
    ):
        """TC-WI-08: 새 채널 메시지(thread_ts 없음) → conversation_id == event['ts']

        Turn 1 (새 메시지)에서는 event["ts"]가 conversation_id로 올바르게 전달돼야 한다.
        이 동작은 현재 코드에서도 올바르게 동작 중 (BUG-03 fix 유지 확인).
        """
        slack_app = _reload_app(monkeypatch, thread_enabled=True, async_enabled=False)

        # Turn 1: 새 채널 메시지 (thread_ts 없음)
        new_message_event = {
            "text": "어제 전체 광고 클릭수 알려줘",
            "user": "U_TEST_USER",
            "channel": "C_TEST_CHANNEL",
            "ts": "MSG_TS_111111.222222",
            # thread_ts 키 없음
        }

        captured_payload = {}

        def _mock_post(url, json=None, headers=None, timeout=None):
            if json:
                captured_payload.update(json)
            return mock_vanna_response

        with patch("requests.post", side_effect=_mock_post):
            slack_app.handle_mention(
                event=new_message_event, say=mock_say, client=mock_client
            )

        assert captured_payload.get("conversation_id") == "MSG_TS_111111.222222"

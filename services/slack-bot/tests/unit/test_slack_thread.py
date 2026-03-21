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
    """TC-ST-01: 스레드 루트 생성 (FR-24-01)"""

    def test_thread_root_message_created_on_mention(
        self, mock_say, mock_client, mock_event, mock_vanna_response, monkeypatch
    ):
        """SLACK_THREAD_ENABLED=true 시, 첫 번째 say()가 스레드 루트 생성용으로 호출됨"""
        slack_app = _reload_app(monkeypatch, thread_enabled=True)

        with patch("requests.post", return_value=mock_vanna_response):
            slack_app.handle_mention(event=mock_event, say=mock_say, client=mock_client)

        # 첫 번째 say() 호출이 스레드 루트용이어야 함
        assert mock_say.call_count >= 1, "say()가 한 번도 호출되지 않음"
        first_call_kwargs = mock_say.call_args_list[0]
        # 스레드 루트는 text="🔄 처리 중..." 으로 호출되어야 함
        assert first_call_kwargs == call(text="🔄 처리 중..."), (
            f"첫 번째 say() 호출이 스레드 루트 생성 형식이 아님: {first_call_kwargs}"
        )

    def test_thread_ts_captured_from_root_response(
        self, mock_say, mock_client, mock_event, mock_vanna_response, monkeypatch
    ):
        """say() 반환값에서 thread_ts를 올바르게 추출함"""
        slack_app = _reload_app(monkeypatch, thread_enabled=True)
        # say()가 {"ts": "1234567890.123456"} 반환 (conftest 설정)

        with patch("requests.post", return_value=mock_vanna_response):
            slack_app.handle_mention(event=mock_event, say=mock_say, client=mock_client)

        # thread_ts = "1234567890.123456" 이 이후 호출에 사용되어야 함
        # client.chat_update가 ts="1234567890.123456" 로 호출됨으로 검증
        assert mock_client.chat_update.called, "chat_update()가 호출되지 않음 → thread_ts 미사용 의심"
        update_kwargs = mock_client.chat_update.call_args[1]
        assert update_kwargs.get("ts") == "1234567890.123456", (
            f"chat_update ts가 thread_ts와 다름: {update_kwargs}"
        )


class TestConversationIdTransmission:
    """TC-ST-02: conversation_id=thread_ts 전달 (FR-24-02, FR-24-07)"""

    def test_conversation_id_included_in_vanna_api_call(
        self, mock_say, mock_client, mock_event, mock_vanna_response, monkeypatch
    ):
        """vanna-api POST body에 conversation_id=thread_ts 포함 여부 검증"""
        slack_app = _reload_app(monkeypatch, thread_enabled=True)

        with patch("requests.post", return_value=mock_vanna_response) as mock_post:
            slack_app.handle_mention(event=mock_event, say=mock_say, client=mock_client)

        # requests.post 호출 확인
        assert mock_post.called, "requests.post()가 호출되지 않음"
        call_kwargs = mock_post.call_args[1]  # keyword args
        payload = call_kwargs.get("json", {})

        assert "conversation_id" in payload, (
            f"vanna-api POST body에 conversation_id가 없음: {payload}"
        )
        assert payload["conversation_id"] == "1234567890.123456", (
            f"conversation_id 값이 thread_ts와 다름: {payload.get('conversation_id')}"
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
            assert kwargs["thread_ts"] == "1234567890.123456", (
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


class TestRootMessageUpdate:
    """TC-ST-04: 완료 후 루트 메시지 업데이트 (FR-24-04)"""

    def test_root_message_updated_after_completion(
        self, mock_say, mock_client, mock_event, mock_vanna_response, monkeypatch
    ):
        """처리 완료 후 client.chat_update()로 루트 메시지 업데이트"""
        slack_app = _reload_app(monkeypatch, thread_enabled=True)

        with patch("requests.post", return_value=mock_vanna_response):
            slack_app.handle_mention(event=mock_event, say=mock_say, client=mock_client)

        assert mock_client.chat_update.called, "chat_update()가 호출되지 않음"
        kwargs = mock_client.chat_update.call_args[1]

        # 필수 파라미터 검증
        assert kwargs.get("channel") == "C_TEST_CHANNEL", f"channel 불일치: {kwargs.get('channel')}"
        assert kwargs.get("ts") == "1234567890.123456", f"ts(thread_ts) 불일치: {kwargs.get('ts')}"
        assert "text" in kwargs, "업데이트 text 없음"
        assert "✅" in kwargs["text"], f"완료 표시(✅) 없음: {kwargs['text']}"


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
        # 에러 say()는 thread_ts를 포함해야 함
        calls_with_thread_ts = [
            c for c in mock_say.call_args_list
            if c[1].get("thread_ts") == "1234567890.123456"
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

        calls_with_thread_ts = [
            c for c in mock_say.call_args_list
            if c[1].get("thread_ts") == "1234567890.123456"
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
    """TC-ST-11: SlackResponse-like 객체에서 thread_ts 추출 (BUG-01)"""

    def test_thread_ts_extracted_from_non_dict_response(
        self, mock_client, mock_event, mock_vanna_response, monkeypatch
    ):
        """say()가 dict가 아닌 SlackResponse-like 객체를 반환해도 thread_ts를 올바르게 추출함.

        실제 slack_bolt의 say()는 SlackResponse 객체를 반환한다.
        isinstance(res, dict) 체크는 항상 False → thread_ts=None 버그를 재현.
        """
        slack_app = _reload_app(monkeypatch, thread_enabled=True)

        # SlackResponse처럼 dict가 아니지만 .get()은 지원하는 객체
        slack_response_mock = MagicMock()
        slack_response_mock.get.return_value = "9999999999.999999"
        assert not isinstance(slack_response_mock, dict), "SlackResponse mock이 dict여서는 안 됨"

        say = MagicMock(return_value=slack_response_mock)

        with patch("requests.post", return_value=mock_vanna_response):
            slack_app.handle_mention(event=mock_event, say=say, client=mock_client)

        assert mock_client.chat_update.called, (
            "chat_update()가 호출되지 않음 → SlackResponse-like 객체에서 thread_ts 추출 실패"
        )
        update_kwargs = mock_client.chat_update.call_args[1]
        assert update_kwargs.get("ts") == "9999999999.999999", (
            f"SlackResponse-like 객체에서 thread_ts 추출 실패: {update_kwargs}"
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

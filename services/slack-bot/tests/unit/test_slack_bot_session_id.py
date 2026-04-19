"""
TC-SS-01~03: Slack Bot session_id(conversation_id) 세션 연속성 단위 테스트
Plan: docs/t1/text-to-sql/14_multi-turn-session-fix/01-plan/features/multi-turn-session-fix.plan.md
"""

import pytest
from unittest.mock import MagicMock, patch


def _extract_conversation_id(event: dict, slack_thread_enabled: bool) -> str | None:
    """slack-bot/app.py의 thread_ts 결정 로직 추출 (테스트용 함수)"""
    thread_ts = None
    if slack_thread_enabled:
        thread_ts = event.get("thread_ts") or event.get("ts")
    return thread_ts


class TestSlackBotSessionId:
    """TC-SS-01~03: thread_ts → conversation_id 매핑 검증"""

    def test_new_message_uses_own_ts_as_session(self):
        """TC-SS-01: 신규 메시지 — thread_ts=None → event['ts']로 신규 세션 시작"""
        event = {"ts": "1711234567.123456", "thread_ts": None}
        result = _extract_conversation_id(event, slack_thread_enabled=True)
        assert result == "1711234567.123456", (
            f"신규 메시지는 자신의 ts를 session_id로 써야 함, got: {result}"
        )

    def test_thread_reply_uses_parent_ts_for_session_continuity(self):
        """TC-SS-02: 스레드 답글 — thread_ts 우선 사용 → session_id 연속성 보장"""
        event = {
            "ts": "1711234568.234567",       # 현재 답글 ts (다름)
            "thread_ts": "1711234567.123456", # 부모 메시지 ts
        }
        result = _extract_conversation_id(event, slack_thread_enabled=True)
        assert result == "1711234567.123456", (
            f"스레드 답글은 부모 ts를 session_id로 써야 함, got: {result}"
        )

    def test_slack_thread_disabled_returns_none(self):
        """TC-SS-03: SLACK_THREAD_ENABLED=false → conversation_id=None → Step 0 스킵"""
        event = {"ts": "1711234567.123456", "thread_ts": "1711234567.123456"}
        result = _extract_conversation_id(event, slack_thread_enabled=False)
        assert result is None, (
            f"SLACK_THREAD_ENABLED=false면 None이어야 함, got: {result}"
        )

    def test_reply_without_thread_ts_field_falls_back_to_ts(self):
        """TC-SS-04: thread_ts 키 자체가 없는 이벤트 → ts fallback"""
        event = {"ts": "1711234567.123456"}  # thread_ts 키 없음
        result = _extract_conversation_id(event, slack_thread_enabled=True)
        assert result == "1711234567.123456", (
            f"thread_ts 키 없으면 ts로 fallback해야 함, got: {result}"
        )

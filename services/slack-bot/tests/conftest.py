"""
Slack Bot 테스트 공통 픽스처
IMPORTANT: slack_bolt Mock을 sys.modules에 등록 후 app 모듈 import 가능
"""

import os
import sys
from unittest.mock import MagicMock

# --- slack_bolt / flask Mock (테스트 환경에 미설치) ---
# app.py 의 module-level import 전에 sys.modules에 등록해야 함

def _make_bolt_mock():
    """slack_bolt.App을 흉내내는 Mock - 데코레이터는 함수를 그대로 반환"""
    mock_app_instance = MagicMock()
    mock_app_instance.event = lambda event_type: (lambda f: f)   # @app.event 데코레이터 pass-through
    mock_app_instance.action = lambda action_id: (lambda f: f)   # @app.action 데코레이터 pass-through

    mock_bolt = MagicMock()
    mock_bolt.App.return_value = mock_app_instance
    return mock_bolt


if "slack_bolt" not in sys.modules:
    sys.modules["slack_bolt"] = _make_bolt_mock()
    sys.modules["slack_bolt.adapter"] = MagicMock()
    sys.modules["slack_bolt.adapter.socket_mode"] = MagicMock()

if "flask" not in sys.modules:
    mock_flask = MagicMock()
    mock_flask_app = MagicMock()
    mock_flask.Flask.return_value = mock_flask_app
    sys.modules["flask"] = mock_flask

# --- 환경 변수 기본값 (app.py 모듈 초기화 전) ---
os.environ.setdefault("SLACK_BOT_TOKEN", "xoxb-test-fake-token")
os.environ.setdefault("SLACK_APP_TOKEN", "xapp-test-fake-token")
os.environ.setdefault("VANNA_API_URL", "http://mock-vanna-api:8000")
os.environ.setdefault("INTERNAL_API_TOKEN", "test-internal-token")

import pytest


@pytest.fixture
def mock_say():
    """Slack say() Mock - 스레드 루트 메시지 ts 반환"""
    say = MagicMock()
    say.return_value = {"ts": "1234567890.123456"}
    return say


@pytest.fixture
def mock_client():
    """Slack client Mock"""
    client = MagicMock()
    client.chat_update.return_value = {"ok": True}
    client.files_upload_v2.return_value = {"files": [{"id": "F_TEST_FILE_ID"}]}
    client.conversations_history.return_value = {"messages": []}
    return client


@pytest.fixture
def mock_event():
    """기본 Slack app_mention 이벤트"""
    return {
        "text": "지난달 신규 가입자 수 알려줘",
        "user": "U_TEST_USER",
        "channel": "C_TEST_CHANNEL",
        "ts": "EVENT_TS_111111.222222",  # BUG-03: 사용자 원본 메시지 ts (스레드 기준점)
    }


@pytest.fixture
def mock_vanna_response():
    """vanna-api 정상 응답 Mock"""
    import requests
    response = MagicMock(spec=requests.Response)
    response.status_code = 200
    response.json.return_value = {
        "original_question": "지난달 신규 가입자 수 알려줘",
        "refined_question": "지난달 신규 가입자 수를 조회해줘",
        "sql": "SELECT COUNT(*) FROM users WHERE created_at >= '2026-02-01'",
        "results": [{"count": 12345}],
        "answer": "지난달 신규 가입자 수는 12,345명입니다.",
        "query_id": "hist-test-001",
        "redash_url": "http://redash.test/queries/1",
        "elapsed_seconds": 2.5,
    }
    return response


@pytest.fixture
def mock_vanna_error_response():
    """vanna-api 오류 응답 Mock"""
    import requests
    response = MagicMock(spec=requests.Response)
    response.status_code = 500
    response.json.return_value = {
        "detail": {
            "error_code": "SQL_GENERATION_FAILED",
            "message": "SQL 생성에 실패했습니다.",
        }
    }
    return response

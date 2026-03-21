"""
Phase 2 단위 테스트 — DELETE /training-data/{id} 엔드포인트
커버 TC: TC-P2-U36 ~ TC-P2-U38, TC-P2-U57
대상: services/vanna-api/src/main.py (FastAPI DELETE 엔드포인트)
요구사항: FR-13~15 — 학습 데이터 관리 (삭제, 선별, 검증)

주의: DELETE /training-data/{id}는 X-Internal-Token 헤더로 인증 (403 반환).
"""

import sys
import pytest
from unittest.mock import MagicMock, patch

# vanna 모듈 mock — 테스트 환경에 설치되지 않은 경우 대비
for _mod_name in [
    "vanna", "vanna.chromadb", "vanna.anthropic", "vanna.base", "vanna.base.base",
    "chromadb", "sentence_transformers",
]:
    if _mod_name not in sys.modules:
        sys.modules[_mod_name] = MagicMock()

from fastapi.testclient import TestClient


# ---------------------------------------------------------------------------
# App 설정 (lifespan 비활성화 + state 직접 주입)
# ---------------------------------------------------------------------------


@pytest.fixture()
def test_client():
    """FastAPI TestClient — Vanna/DynamoDB 의존성 Mock 처리

    BaseHTTPMiddleware에서 raise HTTPException은 generic_exception_handler(500)로 전달되므로
    미들웨어를 바이패스하고 verify_internal_token Depends만 활성화해 403 동작을 검증.
    """
    from src.main import app
    from src.security.auth import InternalTokenMiddleware

    mock_vanna = MagicMock()
    mock_vanna.remove_training_data.return_value = None  # 정상 삭제

    async def _middleware_passthrough(self, request, call_next):
        return await call_next(request)

    with patch.object(InternalTokenMiddleware, "dispatch", _middleware_passthrough):
        with patch("src.security.auth.INTERNAL_SERVICE_TOKEN", "test-internal-token"):
            with patch("src.main.DYNAMODB_ENABLED", False):
                with patch("src.main.ASYNC_QUERY_ENABLED", False):
                    client = TestClient(app, raise_server_exceptions=False)
                    app.state.vanna = mock_vanna
                    app.state.pipeline = MagicMock()
                    app.state.recorder = MagicMock()
                    app.state.feedback_manager = MagicMock()
                    app.state.async_manager = None
                    yield client, mock_vanna


# ---------------------------------------------------------------------------
# TC-P2-U36: 정상 삭제
# ---------------------------------------------------------------------------


class TestDeleteTrainingData:
    """DELETE /training-data/{id} 단위 테스트"""

    def test_delete_training_data_success(self, test_client):
        """TC-P2-U36: 존재하는 id + 인증 헤더 → HTTP 200, remove_training_data 1회 호출"""
        client, mock_vanna = test_client

        resp = client.delete(
            "/training-data/test-vector-id-001",
            headers={"X-Internal-Token": "test-internal-token"},
        )

        assert resp.status_code == 200
        mock_vanna.remove_training_data.assert_called_once_with(id="test-vector-id-001")

    def test_delete_training_data_not_found_returns_400(self, test_client):
        """TC-P2-U37: 존재하지 않는 id → remove_training_data 예외 → HTTP 400"""
        client, mock_vanna = test_client
        mock_vanna.remove_training_data.side_effect = Exception("id not found in ChromaDB")

        resp = client.delete(
            "/training-data/nonexistent-id",
            headers={"X-Internal-Token": "test-internal-token"},
        )

        assert resp.status_code == 400

    def test_delete_training_data_no_auth_header_returns_403(self, test_client):
        """TC-P2-U38: Authorization 헤더 없음 → HTTP 403"""
        client, mock_vanna = test_client

        resp = client.delete("/training-data/some-id")  # 인증 헤더 없음

        assert resp.status_code == 403

    def test_delete_training_data_chromadb_exception_returns_400(self, test_client):
        """TC-P2-U57: ChromaDB 삭제 실패 → HTTP 400"""
        client, mock_vanna = test_client
        mock_vanna.remove_training_data.side_effect = Exception("ChromaDB write error")

        resp = client.delete(
            "/training-data/existing-id",
            headers={"X-Internal-Token": "test-internal-token"},
        )

        assert resp.status_code == 400

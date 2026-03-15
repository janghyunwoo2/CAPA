"""
§3.6 SEC-17: /train 엔드포인트 인증 및 학습 기능 테스트
SEC-05: 학습 엔드포인트 접근 제어
SEC-09: AI 분석 프롬프트 시스템/데이터 영역 분리 검증
"""

import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def _set_token(monkeypatch):
    """INTERNAL_API_TOKEN 환경변수 설정"""
    monkeypatch.setenv("INTERNAL_API_TOKEN", "test-secret-token")


@pytest.fixture()
def _unset_token(monkeypatch):
    """INTERNAL_API_TOKEN 환경변수 제거 (개발 환경 시뮬레이션)"""
    monkeypatch.delenv("INTERNAL_API_TOKEN", raising=False)


@pytest.fixture()
def mock_vanna():
    """Vanna 인스턴스 Mock"""
    vanna = MagicMock()
    vanna.train = MagicMock()
    vanna.get_training_data = MagicMock(return_value=[{"id": "1"}])
    return vanna


@pytest.fixture()
def app_with_state(mock_vanna):
    """app.state에 필요한 의존성을 주입한 TestClient"""
    # auth 모듈이 로드되기 전에 환경변수 설정
    os.environ["INTERNAL_API_TOKEN"] = "test-secret-token"

    # main 모듈을 새로 임포트하지 않고 auth 패치로 우회
    with patch("src.security.auth.INTERNAL_SERVICE_TOKEN", "test-secret-token"):
        from src.main import app

        app.state.vanna = mock_vanna
        app.state.pipeline = MagicMock()
        app.state.recorder = MagicMock()
        app.state.feedback_manager = MagicMock()

        client = TestClient(app, raise_server_exceptions=False)
        yield client


@pytest.fixture()
def auth_headers():
    """유효한 인증 헤더"""
    return {"X-Internal-Token": "test-secret-token"}


# ---------------------------------------------------------------------------
# SEC-17: 인증 필수 테스트
# ---------------------------------------------------------------------------


class TestTrainEndpointAuth:
    """SEC-17: /train 엔드포인트 인증 검증"""

    def test_train_without_token_returns_403(self, app_with_state):
        """/train 토큰 없이 호출 → 403 (SEC-17)"""
        response = app_with_state.post("/train", json={
            "data_type": "ddl",
            "ddl": "CREATE TABLE test (id INT)",
        })
        assert response.status_code == 403

    def test_train_invalid_token_returns_403(self, app_with_state):
        """/train 잘못된 토큰 → 403 (SEC-17)"""
        response = app_with_state.post(
            "/train",
            json={"data_type": "ddl", "ddl": "CREATE TABLE test (id INT)"},
            headers={"X-Internal-Token": "wrong-token"},
        )
        assert response.status_code == 403


# ---------------------------------------------------------------------------
# /train 기능 테스트 (SEC-05, §11.5.2)
# ---------------------------------------------------------------------------


class TestTrainEndpointFunctionality:
    """/train 엔드포인트 학습 기능 검증"""

    def test_train_ddl_valid_auth_returns_200(self, app_with_state, auth_headers, mock_vanna):
        """DDL 학습 요청 + 유효한 토큰 → 200 (SEC-05)"""
        response = app_with_state.post(
            "/train",
            json={"data_type": "ddl", "ddl": "CREATE TABLE ad_combined_log (id INT)"},
            headers=auth_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        assert data["data_type"] == "ddl"
        mock_vanna.train.assert_called_once()

    def test_train_documentation_valid_auth_returns_200(self, app_with_state, auth_headers, mock_vanna):
        """Documentation 학습 요청 → 200"""
        response = app_with_state.post(
            "/train",
            json={"data_type": "documentation", "documentation": "ROAS = 전환매출 / 광고비"},
            headers=auth_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert data["data_type"] == "documentation"

    def test_train_sql_valid_auth_returns_200(self, app_with_state, auth_headers, mock_vanna):
        """SQL 학습 요청 → 200"""
        response = app_with_state.post(
            "/train",
            json={"data_type": "sql", "sql": "SELECT device_type, COUNT(*) FROM ad_combined_log GROUP BY 1"},
            headers=auth_headers,
        )
        assert response.status_code == 200

    def test_train_qa_pair_valid_returns_200(self, app_with_state, auth_headers, mock_vanna):
        """QA pair 학습 요청 → 200"""
        response = app_with_state.post(
            "/train",
            json={
                "data_type": "qa_pair",
                "question": "어제 캠페인별 CTR은?",
                "sql": "SELECT campaign_id, ctr FROM ad_combined_log_summary",
            },
            headers=auth_headers,
        )
        assert response.status_code == 200

    def test_train_qa_pair_missing_sql_returns_400(self, app_with_state, auth_headers):
        """QA pair에서 sql 누락 → 400"""
        response = app_with_state.post(
            "/train",
            json={"data_type": "qa_pair", "question": "어제 CTR"},
            headers=auth_headers,
        )
        assert response.status_code == 400

    def test_train_invalid_data_type_returns_422(self, app_with_state, auth_headers):
        """유효하지 않은 data_type → 422"""
        response = app_with_state.post(
            "/train",
            json={"data_type": "invalid_type"},
            headers=auth_headers,
        )
        assert response.status_code == 422


# ---------------------------------------------------------------------------
# SEC-09: 프롬프트 시스템/데이터 영역 분리 검증
# ---------------------------------------------------------------------------


class TestSEC09PromptSeparation:
    """SEC-09: AI 분석 프롬프트 영역 분리 검증"""

    def test_ai_analyzer_prompt_separates_system_and_data(self):
        """AIAnalyzer 프롬프트가 <instructions>와 <data>로 영역 분리 (SEC-09)"""
        from src.pipeline.ai_analyzer import AIAnalyzer

        analyzer = AIAnalyzer(api_key="test-key")

        # analyze 메서드 내부에서 사용하는 프롬프트 구조를 확인하기 위해
        # _client.messages.create 호출 시 전달되는 content를 캡처
        with patch.object(analyzer._client.messages, "create") as mock_create:
            mock_response = MagicMock()
            mock_response.content = [MagicMock(text='{"answer": "테스트", "chart_type": "none", "insight_points": []}')]
            mock_create.return_value = mock_response

            from src.models.domain import QueryResults
            analyzer.analyze(
                question="어제 CTR",
                sql="SELECT campaign_id, ctr FROM summary",
                query_results=QueryResults(
                    rows=[{"campaign_id": "C-001", "ctr": 5.0}],
                    columns=["campaign_id", "ctr"],
                    row_count=1,
                ),
            )

            # messages.create 호출 인자에서 프롬프트 구조 확인
            call_args = mock_create.call_args
            messages = call_args.kwargs.get("messages") or call_args[1].get("messages")
            content_blocks = messages[0]["content"]

            # 최소 2개의 content block (시스템 지시 + 데이터)
            assert len(content_blocks) >= 2

            instructions_block = content_blocks[0]["text"]
            data_block = content_blocks[1]["text"]

            # 시스템 지시 영역
            assert "<instructions>" in instructions_block
            assert "</instructions>" in instructions_block

            # 데이터 영역
            assert "<data>" in data_block
            assert "</data>" in data_block

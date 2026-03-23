"""
§3.14: AIAnalyzer (Step 10) 단위 테스트
AI 인사이트 생성, PII 마스킹, 실패 시 폴백 검증
"""

import json
from unittest.mock import MagicMock, patch

import pytest

from src.models.domain import AnalysisResult, ChartType, QueryResults
from src.pipeline.ai_analyzer import AIAnalyzer, mask_sensitive_data, PII_COLUMNS


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def analyzer() -> AIAnalyzer:
    """AIAnalyzer 인스턴스 (API 키는 테스트용)"""
    return AIAnalyzer(api_key="test-api-key")


@pytest.fixture()
def sample_query_results() -> QueryResults:
    """테스트용 쿼리 결과"""
    return QueryResults(
        rows=[
            {"device_type": "Android", "revenue": 50000, "ctr": 3.2},
            {"device_type": "iOS", "revenue": 40000, "ctr": 4.1},
        ],
        columns=["device_type", "revenue", "ctr"],
        row_count=2,
    )


# ---------------------------------------------------------------------------
# PII 마스킹 (SEC-15)
# ---------------------------------------------------------------------------


class TestMaskSensitiveData:
    """SEC-15: PII 마스킹 함수 테스트"""

    def test_user_id_masked_to_last_4(self):
        """user_id → ****XXXX 형식 마스킹"""
        rows = [{"user_id": "U0123ABCDE1234", "revenue": 50000}]
        result = mask_sensitive_data(rows)
        assert result[0]["user_id"].startswith("****")
        assert result[0]["user_id"].endswith("1234")
        assert result[0]["revenue"] == 50000

    def test_ip_address_masked_last_octet(self):
        """ip_address → 마지막 옥텟 마스킹"""
        rows = [{"ip_address": "192.168.1.100"}]
        result = mask_sensitive_data(rows)
        assert result[0]["ip_address"] == "192.168.1.*"

    def test_advertiser_id_redacted(self):
        """advertiser_id → [REDACTED]"""
        rows = [{"advertiser_id": "ADV-001", "campaign_id": "C-001"}]
        result = mask_sensitive_data(rows)
        assert result[0]["advertiser_id"] == "[REDACTED]"
        assert result[0]["campaign_id"] == "C-001"

    def test_device_id_hashed(self):
        """device_id → SHA-256 해시 (12자)"""
        rows = [{"device_id": "DEV-ABCDEF"}]
        result = mask_sensitive_data(rows)
        assert len(result[0]["device_id"]) == 12
        assert result[0]["device_id"] != "DEV-ABCDEF"

    def test_non_pii_columns_unchanged(self):
        """비PII 컬럼은 변경 없음"""
        rows = [{"campaign_id": "C-001", "impressions": 10000, "clicks": 500}]
        result = mask_sensitive_data(rows)
        assert result[0] == {"campaign_id": "C-001", "impressions": 10000, "clicks": 500}

    def test_empty_rows_returns_empty(self):
        """빈 리스트 입력 → 빈 리스트 반환"""
        assert mask_sensitive_data([]) == []

    def test_null_pii_values_handled(self):
        """PII 컬럼이 None이면 마스킹 스킵"""
        rows = [{"user_id": None, "ip_address": None, "advertiser_id": None}]
        result = mask_sensitive_data(rows)
        # advertiser_id는 값과 무관하게 [REDACTED]
        assert result[0]["advertiser_id"] == "[REDACTED]"


# ---------------------------------------------------------------------------
# AIAnalyzer.analyze 성공 케이스
# ---------------------------------------------------------------------------


class TestAIAnalyzerSuccess:
    """AIAnalyzer 정상 동작 테스트"""

    def test_analyze_returns_analysis_result(self, analyzer, sample_query_results):
        """정상 응답 → AnalysisResult 반환"""
        mock_response = MagicMock()
        mock_response.content = [MagicMock(text=json.dumps({
            "answer": "Android 매출이 iOS보다 25% 높습니다",
            "chart_type": "bar",
            "insight_points": ["Android 매출 우위", "iOS CTR 우위"],
        }))]

        with patch.object(analyzer._client.messages, "create", return_value=mock_response):
            result = analyzer.analyze(
                question="기기별 매출 비교",
                sql="SELECT device_type, revenue FROM summary",
                query_results=sample_query_results,
            )

        assert isinstance(result, AnalysisResult)
        assert "Android" in result.answer
        assert result.chart_type == ChartType.BAR
        assert len(result.insight_points) == 2

    def test_analyze_unknown_chart_type_defaults_to_none(self, analyzer, sample_query_results):
        """알 수 없는 chart_type → ChartType.NONE"""
        mock_response = MagicMock()
        mock_response.content = [MagicMock(text=json.dumps({
            "answer": "결과",
            "chart_type": "unknown_type",
            "insight_points": [],
        }))]

        with patch.object(analyzer._client.messages, "create", return_value=mock_response):
            result = analyzer.analyze(
                question="테스트",
                sql="SELECT 1",
                query_results=sample_query_results,
            )

        assert result.chart_type == ChartType.NONE


# ---------------------------------------------------------------------------
# AIAnalyzer.analyze 실패 시 폴백
# ---------------------------------------------------------------------------


class TestAIAnalyzerFallback:
    """AI 분석 실패 시 기본 AnalysisResult 반환 검증"""

    def test_analyze_api_error_returns_fallback(self, analyzer, sample_query_results):
        """Anthropic API 오류 → 폴백 AnalysisResult"""
        import anthropic

        with patch.object(
            analyzer._client.messages, "create",
            side_effect=anthropic.APIError(
                message="API Error",
                request=MagicMock(),
                body=None,
            ),
        ):
            result = analyzer.analyze(
                question="테스트",
                sql="SELECT 1",
                query_results=sample_query_results,
            )

        assert "2건" in result.answer
        assert result.chart_type == ChartType.NONE

    def test_analyze_json_decode_error_returns_fallback(self, analyzer, sample_query_results):
        """JSON 파싱 실패 → 폴백 AnalysisResult"""
        mock_response = MagicMock()
        mock_response.content = [MagicMock(text="This is not JSON")]

        with patch.object(analyzer._client.messages, "create", return_value=mock_response):
            result = analyzer.analyze(
                question="테스트",
                sql="SELECT 1",
                query_results=sample_query_results,
            )

        assert "2건" in result.answer
        assert result.chart_type == ChartType.NONE

    def test_analyze_unexpected_exception_returns_fallback(self, analyzer, sample_query_results):
        """예상치 못한 예외 → 폴백 AnalysisResult"""
        with patch.object(
            analyzer._client.messages, "create",
            side_effect=RuntimeError("Unexpected"),
        ):
            result = analyzer.analyze(
                question="테스트",
                sql="SELECT 1",
                query_results=sample_query_results,
            )

        assert result.chart_type == ChartType.NONE


# ---------------------------------------------------------------------------
# SEC-16: 최대 10행 제한
# ---------------------------------------------------------------------------


class TestSEC16RowLimit:
    """SEC-16: AI 분석 시 최대 10행만 전달"""

    def test_analyze_passes_max_10_rows_to_llm(self, analyzer):
        """20행 데이터 → LLM에 최대 10행만 전달"""
        rows = [{"id": i, "value": i * 100} for i in range(20)]
        qr = QueryResults(rows=rows, columns=["id", "value"], row_count=20)

        mock_response = MagicMock()
        mock_response.content = [MagicMock(text=json.dumps({
            "answer": "결과", "chart_type": "none", "insight_points": [],
        }))]

        with patch.object(analyzer._client.messages, "create", return_value=mock_response) as mock_create:
            analyzer.analyze(question="테스트", sql="SELECT 1", query_results=qr)

            # LLM에 전달된 데이터 블록에서 행 수 확인
            call_args = mock_create.call_args
            messages = call_args.kwargs.get("messages") or call_args[1].get("messages")
            data_text = messages[0]["content"][1]["text"]
            # JSON 파싱으로 실제 전달된 행 수 확인
            # "Results (up to 10 rows): [...]" 형태
            assert "up to 10 rows" in data_text

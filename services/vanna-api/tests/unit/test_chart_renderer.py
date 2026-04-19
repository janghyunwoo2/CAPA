"""
§3.15: ChartRenderer (Step 10.5) 단위 테스트
matplotlib Agg 백엔드 Base64 PNG 렌더링 검증
"""

import base64
import os
from unittest.mock import patch

import pytest

from src.models.domain import ChartType, QueryResults
from src.pipeline.chart_renderer import ChartRenderer


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def renderer() -> ChartRenderer:
    """ChartRenderer 인스턴스"""
    return ChartRenderer()


@pytest.fixture()
def bar_chart_data() -> QueryResults:
    """바 차트용 쿼리 결과"""
    return QueryResults(
        rows=[
            {"device_type": "Android", "revenue": 50000},
            {"device_type": "iOS", "revenue": 40000},
            {"device_type": "Web", "revenue": 30000},
        ],
        columns=["device_type", "revenue"],
        row_count=3,
    )


@pytest.fixture()
def line_chart_data() -> QueryResults:
    """라인 차트용 시계열 결과"""
    return QueryResults(
        rows=[
            {"date": "2026-03-10", "impressions": 1000},
            {"date": "2026-03-11", "impressions": 1200},
            {"date": "2026-03-12", "impressions": 1100},
        ],
        columns=["date", "impressions"],
        row_count=3,
    )


@pytest.fixture()
def pie_chart_data() -> QueryResults:
    """파이 차트용 비율 데이터"""
    return QueryResults(
        rows=[
            {"device_type": "Android", "share": 45},
            {"device_type": "iOS", "share": 35},
            {"device_type": "Web", "share": 20},
        ],
        columns=["device_type", "share"],
        row_count=3,
    )


# ---------------------------------------------------------------------------
# 기본 동작
# ---------------------------------------------------------------------------


class TestChartRendererBasic:
    """ChartRenderer 기본 동작 테스트"""

    def test_render_chart_type_none_returns_none(self, renderer, bar_chart_data):
        """chart_type=NONE → None 반환"""
        result = renderer.render(bar_chart_data, ChartType.NONE)
        assert result is None

    def test_render_empty_rows_returns_none(self, renderer):
        """빈 결과 → None 반환"""
        qr = QueryResults(rows=[], columns=[], row_count=0)
        result = renderer.render(qr, ChartType.BAR)
        assert result is None

    def test_render_no_columns_returns_none(self, renderer):
        """컬럼 없는 결과 → None 반환"""
        qr = QueryResults(rows=[{"a": 1}], columns=[], row_count=1)
        result = renderer.render(qr, ChartType.BAR)
        assert result is None


# ---------------------------------------------------------------------------
# 차트 유형별 렌더링 (Base64 PNG)
# ---------------------------------------------------------------------------


class TestChartRendering:
    """차트 유형별 렌더링 결과 검증"""

    def test_render_bar_chart_returns_base64(self, renderer, bar_chart_data):
        """바 차트 → 유효한 Base64 문자열"""
        result = renderer.render(bar_chart_data, ChartType.BAR)
        assert result is not None
        # Base64 디코딩 가능 확인
        decoded = base64.b64decode(result)
        # PNG 매직 바이트 확인
        assert decoded[:4] == b"\x89PNG"

    def test_render_line_chart_returns_base64(self, renderer, line_chart_data):
        """라인 차트 → 유효한 Base64 PNG"""
        result = renderer.render(line_chart_data, ChartType.LINE)
        assert result is not None
        decoded = base64.b64decode(result)
        assert decoded[:4] == b"\x89PNG"

    def test_render_pie_chart_returns_base64(self, renderer, pie_chart_data):
        """파이 차트 → 유효한 Base64 PNG"""
        result = renderer.render(pie_chart_data, ChartType.PIE)
        assert result is not None
        decoded = base64.b64decode(result)
        assert decoded[:4] == b"\x89PNG"

    def test_render_scatter_chart_returns_base64(self, renderer):
        """산점도 → 유효한 Base64 PNG"""
        qr = QueryResults(
            rows=[
                {"impressions": 1000, "clicks": 50},
                {"impressions": 2000, "clicks": 120},
                {"impressions": 1500, "clicks": 80},
            ],
            columns=["impressions", "clicks"],
            row_count=3,
        )
        result = renderer.render(qr, ChartType.SCATTER)
        assert result is not None
        decoded = base64.b64decode(result)
        assert decoded[:4] == b"\x89PNG"


# ---------------------------------------------------------------------------
# NFR-08: MPLBACKEND=Agg 강제
# ---------------------------------------------------------------------------


class TestMplBackend:
    """NFR-08: matplotlib Agg 백엔드 설정 확인"""

    def test_mplbackend_set_to_agg(self):
        """MPLBACKEND 환경변수가 Agg로 설정됨"""
        import matplotlib
        assert matplotlib.get_backend().lower() == "agg"


# ---------------------------------------------------------------------------
# SEC-24: 차트 데이터 PII 마스킹
# ---------------------------------------------------------------------------


class TestChartPIIMasking:
    """SEC-24: 차트 렌더링 시 PII 마스킹 적용"""

    def test_render_applies_pii_masking(self, renderer):
        """PII 컬럼(user_id)이 차트 데이터에서 마스킹됨"""
        qr = QueryResults(
            rows=[
                {"user_id": "U12345678", "revenue": 50000},
                {"user_id": "U87654321", "revenue": 30000},
            ],
            columns=["user_id", "revenue"],
            row_count=2,
        )

        with patch("src.pipeline.chart_renderer.mask_sensitive_data", wraps=__import__("src.pipeline.ai_analyzer", fromlist=["mask_sensitive_data"]).mask_sensitive_data) as mock_mask:
            result = renderer.render(qr, ChartType.BAR)
            # mask_sensitive_data가 호출되었는지 확인
            mock_mask.assert_called_once()

    def test_render_exception_returns_none(self, renderer, bar_chart_data):
        """렌더링 중 예외 → None 반환 (서비스 중단 방지)"""
        with patch("src.pipeline.chart_renderer.pd.DataFrame", side_effect=RuntimeError("mock error")):
            result = renderer.render(bar_chart_data, ChartType.BAR)
        assert result is None

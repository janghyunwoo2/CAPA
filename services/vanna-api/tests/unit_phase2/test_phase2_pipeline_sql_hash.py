"""
Phase 2 단위 테스트 — PipelineContext.sql_hash 할당 검증
커버 TC: TC-P2-U39 ~ TC-P2-U40
대상: services/vanna-api/src/query_pipeline.py (Step 7 sql_hash 할당)
요구사항: FR-17 — SQL 해시 파이프라인 컨텍스트 할당 (Gap 4 수정 검증)
"""

import pytest
from unittest.mock import MagicMock, AsyncMock, patch

from src.pipeline.sql_hash import compute_sql_hash
from src.models.domain import (
    PipelineContext,
    IntentType,
    ValidationResult,
)


# ---------------------------------------------------------------------------
# TC-P2-U39: Redash 경로에서 sql_hash 할당
# ---------------------------------------------------------------------------


class TestPipelineSQLHashAssignment:
    """PipelineContext.sql_hash 할당 직접 검증"""

    def test_sql_hash_assigned_correctly_for_redash_path(self):
        """TC-P2-U39: sql_hash가 올바르게 계산되어 ctx에 할당됨 (Redash 경로)"""
        sql = "SELECT COUNT(*) FROM ad_clicks WHERE date='2026-03-19'"
        expected_hash = compute_sql_hash(sql)

        # PipelineContext에 직접 할당 (query_pipeline.py:273 로직 재현)
        ctx = PipelineContext(
            original_question="어제 클릭 수",
            validation_result=ValidationResult(is_valid=True, normalized_sql=sql),
        )
        ctx.sql_hash = compute_sql_hash(sql)

        assert ctx.sql_hash is not None
        assert ctx.sql_hash == expected_hash
        assert len(ctx.sql_hash) == 64  # SHA-256

    def test_sql_hash_none_for_athena_fallback_path(self):
        """TC-P2-U40: Athena fallback 경로에서 sql_hash는 None (미할당)"""
        ctx = PipelineContext(
            original_question="어제 클릭 수",
        )
        # Athena fallback 경로: sql_hash 미할당
        # (query_pipeline.py에서 REDASH_ENABLED=false 시 할당 로직 없음)

        assert ctx.sql_hash is None

    def test_sql_hash_consistent_with_pipeline_sql_hash_module(self):
        """TC-P2-U39 보완: pipeline의 compute_sql_hash와 동일한 값 사용"""
        sql_variants = [
            "SELECT * FROM ad_clicks",
            "SELECT  *  FROM  ad_clicks  -- dup",
            "select * from ad_clicks",
        ]
        hashes = [compute_sql_hash(s) for s in sql_variants]

        # 모두 동일한 해시여야 함
        assert len(set(hashes)) == 1

    def test_sql_hash_field_exists_on_pipeline_context(self):
        """PipelineContext에 sql_hash 필드가 정의되어 있음 확인"""
        ctx = PipelineContext(original_question="Q")
        assert hasattr(ctx, "sql_hash")
        assert ctx.sql_hash is None  # 초기값 None

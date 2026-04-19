"""
§3.16: HistoryRecorder (Step 11) 단위 테스트
FR-10: 질문-SQL-결과 이력 JSON Lines 저장 검증
"""

import json
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.history_recorder import HistoryRecorder, _hash_user_id
from src.models.domain import (
    IntentType,
    PipelineContext,
    QueryResults,
    ValidationResult,
)
from src.models.feedback import QueryHistoryRecord


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def tmp_history_file(tmp_path) -> Path:
    """임시 이력 파일 경로"""
    return tmp_path / "query_history.jsonl"


@pytest.fixture()
def recorder(tmp_history_file) -> HistoryRecorder:
    """임시 파일 기반 HistoryRecorder"""
    return HistoryRecorder(history_file=tmp_history_file)


@pytest.fixture()
def sample_context() -> PipelineContext:
    """테스트용 PipelineContext"""
    return PipelineContext(
        original_question="어제 캠페인별 CTR 알려줘",
        slack_user_id="U12345678",
        slack_channel_id="C-general",
        intent=IntentType.DATA_QUERY,
        refined_question="어제 캠페인별 CTR 조회",
        keywords=["CTR", "campaign_id", "어제"],
        generated_sql="SELECT campaign_id, ctr FROM ad_combined_log_summary",
        validation_result=ValidationResult(
            is_valid=True,
            normalized_sql="SELECT campaign_id, ctr FROM ad_combined_log_summary",
        ),
        query_results=QueryResults(
            rows=[{"campaign_id": "C-001", "ctr": 5.0}],
            columns=["campaign_id", "ctr"],
            row_count=1,
        ),
        redash_query_id=42,
        redash_url="https://redash.example.com/queries/42",
    )


# ---------------------------------------------------------------------------
# _hash_user_id (PII 보호)
# ---------------------------------------------------------------------------


class TestHashUserId:
    """PII 보호를 위한 user_id 해싱 테스트"""

    def test_hash_user_id_returns_16_chars(self):
        """user_id 해시는 16자"""
        result = _hash_user_id("U12345678")
        assert len(result) == 16

    def test_hash_user_id_deterministic(self):
        """동일 입력 → 동일 해시"""
        hash1 = _hash_user_id("U12345678")
        hash2 = _hash_user_id("U12345678")
        assert hash1 == hash2

    def test_hash_user_id_different_inputs(self):
        """다른 입력 → 다른 해시"""
        hash1 = _hash_user_id("U12345678")
        hash2 = _hash_user_id("U87654321")
        assert hash1 != hash2

    def test_hash_user_id_empty_returns_empty(self):
        """빈 문자열 → 빈 문자열 반환"""
        assert _hash_user_id("") == ""


# ---------------------------------------------------------------------------
# HistoryRecorder.record (FR-10)
# ---------------------------------------------------------------------------


class TestHistoryRecorderRecord:
    """FR-10: 이력 저장 테스트"""

    def test_record_creates_jsonl_entry(self, recorder, sample_context, tmp_history_file):
        """record() → JSONL 파일에 1건 저장"""
        history_id = recorder.record(sample_context)

        assert history_id  # UUID 문자열
        assert tmp_history_file.exists()

        lines = tmp_history_file.read_text(encoding="utf-8").strip().splitlines()
        assert len(lines) == 1

        data = json.loads(lines[0])
        assert data["history_id"] == history_id
        assert data["original_question"] == "어제 캠페인별 CTR 알려줘"
        assert data["intent"] == "data_query"

    def test_record_hashes_slack_user_id(self, recorder, sample_context, tmp_history_file):
        """저장된 slack_user_id는 해시 처리됨 (PII 보호)"""
        recorder.record(sample_context)
        data = json.loads(tmp_history_file.read_text(encoding="utf-8").strip())
        # 원본 user_id가 아닌 해시값
        assert data["slack_user_id"] != "U12345678"
        assert len(data["slack_user_id"]) == 16

    def test_record_includes_sql_and_results(self, recorder, sample_context, tmp_history_file):
        """SQL, row_count, redash 정보가 저장됨"""
        recorder.record(sample_context)
        data = json.loads(tmp_history_file.read_text(encoding="utf-8").strip())
        assert data["generated_sql"] is not None
        assert data["sql_validated"] is True
        assert data["row_count"] == 1
        assert data["redash_query_id"] == 42

    def test_record_multiple_entries_appended(self, recorder, sample_context, tmp_history_file):
        """여러 번 호출 시 JSONL에 append"""
        recorder.record(sample_context)
        recorder.record(sample_context)
        lines = tmp_history_file.read_text(encoding="utf-8").strip().splitlines()
        assert len(lines) == 2

    def test_record_failure_does_not_raise(self, recorder, sample_context):
        """저장 실패 시 예외를 발생시키지 않음 (사용자 영향 없음)"""
        with patch.object(recorder, "_append_record", side_effect=IOError("disk full")):
            history_id = recorder.record(sample_context)
        # 예외 없이 history_id 반환
        assert history_id is not None


# ---------------------------------------------------------------------------
# HistoryRecorder.update_feedback
# ---------------------------------------------------------------------------


class TestHistoryRecorderFeedback:
    """피드백 업데이트 테스트"""

    def test_update_feedback_positive(self, recorder, sample_context, tmp_history_file):
        """긍정 피드백 업데이트"""
        history_id = recorder.record(sample_context)
        result = recorder.update_feedback(history_id, feedback="positive", trained=True)
        assert result is True

        data = json.loads(tmp_history_file.read_text(encoding="utf-8").strip())
        assert data["feedback"] == "positive"
        assert data["trained"] is True
        assert data["feedback_at"] is not None

    def test_update_feedback_nonexistent_id_returns_false(self, recorder, sample_context):
        """존재하지 않는 history_id → False"""
        recorder.record(sample_context)
        result = recorder.update_feedback("nonexistent-id", feedback="negative")
        assert result is False

    def test_update_feedback_no_file_returns_false(self, recorder):
        """파일 없음 → False"""
        result = recorder.update_feedback("any-id", feedback="positive")
        assert result is False


# ---------------------------------------------------------------------------
# HistoryRecorder.get_record
# ---------------------------------------------------------------------------


class TestHistoryRecorderGetRecord:
    """이력 조회 테스트"""

    def test_get_record_found(self, recorder, sample_context):
        """존재하는 history_id → QueryHistoryRecord 반환"""
        history_id = recorder.record(sample_context)
        record = recorder.get_record(history_id)
        assert record is not None
        assert record.history_id == history_id
        assert record.original_question == "어제 캠페인별 CTR 알려줘"

    def test_get_record_not_found_returns_none(self, recorder, sample_context):
        """존재하지 않는 ID → None"""
        recorder.record(sample_context)
        assert recorder.get_record("nonexistent") is None

    def test_get_record_no_file_returns_none(self, recorder):
        """파일 미존재 → None"""
        assert recorder.get_record("any-id") is None

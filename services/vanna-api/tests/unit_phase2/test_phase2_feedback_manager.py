"""
Phase 2 단위 테스트 — FeedbackManager.record_positive()
커버 TC: TC-P2-U53 ~ TC-P2-U55
대상 파일: services/vanna-api/src/feedback_manager.py
요구사항: FR-16 — 피드백 루프 자동화 (Phase 2: pending 저장, 즉시 학습 없음)
"""

import pytest
import boto3
import os
from moto import mock_aws
from unittest.mock import MagicMock, patch
from datetime import datetime

from src.feedback_manager import FeedbackManager
from src.models.feedback import QueryHistoryRecord
from src.models.domain import FeedbackType

HISTORY_TABLE = "test-query-history"
FEEDBACK_TABLE = "test-pending-feedbacks"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def aws_credentials(monkeypatch):
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "testing")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "testing")
    monkeypatch.setenv("AWS_SECURITY_TOKEN", "testing")
    monkeypatch.setenv("AWS_SESSION_TOKEN", "testing")
    monkeypatch.setenv("AWS_DEFAULT_REGION", "us-east-1")


@pytest.fixture()
def feedback_setup_phase2(aws_credentials):
    """Phase 2 모드 FeedbackManager 설정 (PHASE2_FEEDBACK_ENABLED=true)"""
    with mock_aws():
        db = boto3.resource("dynamodb", region_name="us-east-1")
        feedback_table = db.create_table(
            TableName=FEEDBACK_TABLE,
            KeySchema=[{"AttributeName": "feedback_id", "KeyType": "HASH"}],
            AttributeDefinitions=[{"AttributeName": "feedback_id", "AttributeType": "S"}],
            BillingMode="PAY_PER_REQUEST",
        )

        # Mock history recorder
        mock_recorder = MagicMock()
        mock_recorder.get_record.return_value = QueryHistoryRecord(
            history_id="h1",
            timestamp=datetime.utcnow(),
            slack_user_id="U001",
            slack_channel_id="C001",
            original_question="어제 클릭 수",
            refined_question="어제 기준 광고 클릭 수를 알려주세요",
            intent="data_query",
            keywords=["클릭"],
            generated_sql="SELECT COUNT(*) FROM ad_clicks",
        )
        mock_recorder.update_feedback.return_value = True

        # Mock vanna
        mock_vanna = MagicMock()

        # DynamoDBFeedbackStore
        from src.stores.dynamodb_feedback import DynamoDBFeedbackStore
        feedback_store = DynamoDBFeedbackStore(dynamodb_resource=db, table_name=FEEDBACK_TABLE)

        with patch.dict(os.environ, {"PHASE2_FEEDBACK_ENABLED": "true"}):
            # 모듈 레벨 변수 패치
            with patch("src.feedback_manager.PHASE2_FEEDBACK_ENABLED", True):
                fm = FeedbackManager(
                    vanna_instance=mock_vanna,
                    history_recorder=mock_recorder,
                    feedback_store=feedback_store,
                )
                yield fm, mock_vanna, mock_recorder, feedback_table


# ---------------------------------------------------------------------------
# TC-P2-U53: 정상 — history 존재, pending 저장, 즉시 학습 없음
# ---------------------------------------------------------------------------


class TestRecordPositivePhase2:
    """record_positive() Phase 2 모드 단위 테스트"""

    def test_record_positive_phase2_stores_pending_no_train(self, feedback_setup_phase2):
        """TC-P2-U53: history 존재 → (False, msg) 반환, feedback 테이블 pending 저장, vanna.train 미호출"""
        fm, mock_vanna, mock_recorder, feedback_table = feedback_setup_phase2

        result = fm.record_positive(history_id="h1", slack_user_id="U001")

        # Phase 2: trained=False 반환
        assert result[0] is False

        # vanna.train 미호출 (즉시 학습 없음)
        mock_vanna.train.assert_not_called()

        # feedback 테이블에 pending 항목 존재
        resp = feedback_table.scan()
        items = resp["Items"]
        assert len(items) == 1
        assert items[0]["status"] == "pending"


# ---------------------------------------------------------------------------
# TC-P2-U54: history_id 없음 → 실패
# ---------------------------------------------------------------------------


class TestRecordPositiveNotFound:
    """record_positive() history 미존재 케이스"""

    def test_record_positive_history_not_found_returns_false(self, aws_credentials):
        """TC-P2-U54: history_id 없음 → (False, 이력 관련 메시지) 반환"""
        with mock_aws():
            mock_recorder = MagicMock()
            mock_recorder.get_record.return_value = None  # 이력 없음

            mock_vanna = MagicMock()

            fm = FeedbackManager(
                vanna_instance=mock_vanna,
                history_recorder=mock_recorder,
                feedback_store=None,
            )

            result = fm.record_positive(history_id="nonexistent", slack_user_id="U001")

            assert result[0] is False
            assert "이력" in result[1]


# ---------------------------------------------------------------------------
# TC-P2-U55: DynamoDB 장애 시 처리
# ---------------------------------------------------------------------------


class TestRecordPositiveDynamoDBError:
    """record_positive() DynamoDB 장애 케이스"""

    def test_record_positive_feedback_store_error_handled(self, aws_credentials):
        """TC-P2-U55: feedback_store.save_pending 실패 → (False, ...) 반환 또는 예외 미전파"""
        with mock_aws():
            mock_recorder = MagicMock()
            mock_recorder.get_record.return_value = QueryHistoryRecord(
                history_id="h1",
                timestamp=datetime.utcnow(),
                slack_user_id="U001",
                slack_channel_id="C001",
                original_question="Q",
                refined_question="Q refined",
                intent="data_query",
                generated_sql="SELECT 1",
            )

            # feedback_store에서 에러 유발
            mock_feedback_store = MagicMock()
            mock_feedback_store.save_pending.side_effect = Exception("DynamoDB 장애")

            mock_vanna = MagicMock()

            with patch("src.feedback_manager.PHASE2_FEEDBACK_ENABLED", True):
                fm = FeedbackManager(
                    vanna_instance=mock_vanna,
                    history_recorder=mock_recorder,
                    feedback_store=mock_feedback_store,
                )

                # 예외가 전파되지 않아야 함 (또는 False 반환)
                try:
                    result = fm.record_positive(history_id="h1", slack_user_id="U001")
                    # 정상 완료 시 False 반환 가능 (save_pending 실패 후 계속 진행)
                    assert result[0] is False
                except Exception:
                    pytest.fail("record_positive()가 예외를 전파하면 안 됩니다")

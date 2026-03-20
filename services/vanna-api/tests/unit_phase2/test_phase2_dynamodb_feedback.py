"""
Phase 2 단위 테스트 — DynamoDBFeedbackStore
커버 TC: TC-P2-U14 ~ TC-P2-U19
대상 파일: services/vanna-api/src/stores/dynamodb_feedback.py
요구사항: FR-16 — 피드백 루프 품질 제어 (pending_feedbacks 테이블)
"""

import time
import pytest
import boto3
from moto import mock_aws
from unittest.mock import patch, MagicMock
from botocore.exceptions import ClientError
from datetime import datetime, timedelta

from src.pipeline.sql_hash import compute_sql_hash
from src.stores.dynamodb_feedback import DynamoDBFeedbackStore

TABLE_NAME = "test-pending-feedbacks"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def aws_credentials(monkeypatch):
    """moto용 가짜 AWS 자격증명"""
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "testing")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "testing")
    monkeypatch.setenv("AWS_SECURITY_TOKEN", "testing")
    monkeypatch.setenv("AWS_SESSION_TOKEN", "testing")
    monkeypatch.setenv("AWS_DEFAULT_REGION", "us-east-1")


@pytest.fixture()
def feedback_table(aws_credentials):
    """moto DynamoDB pending_feedbacks 테이블 생성"""
    with mock_aws():
        db = boto3.resource("dynamodb", region_name="us-east-1")
        table = db.create_table(
            TableName=TABLE_NAME,
            KeySchema=[{"AttributeName": "feedback_id", "KeyType": "HASH"}],
            AttributeDefinitions=[{"AttributeName": "feedback_id", "AttributeType": "S"}],
            BillingMode="PAY_PER_REQUEST",
        )
        store = DynamoDBFeedbackStore(dynamodb_resource=db, table_name=TABLE_NAME)
        yield store, table


# ---------------------------------------------------------------------------
# TC-P2-U14: 정상 저장
# ---------------------------------------------------------------------------


class TestSavePending:
    """save_pending() 단위 테스트"""

    def test_save_pending_returns_uuid_and_stores_item(self, feedback_table):
        """TC-P2-U14: 정상 저장 — feedback_id(UUID) 반환, 테이블 항목 존재, status=pending"""
        store, table = feedback_table
        feedback_id = store.save_pending(
            history_id="h1",
            question="어제 클릭 수",
            sql="SELECT 1",
        )

        assert len(feedback_id) == 36  # UUID 형식

        item = table.get_item(Key={"feedback_id": feedback_id})["Item"]
        assert item["status"] == "pending"
        assert item["history_id"] == "h1"

    def test_save_pending_stores_sql_hash(self, feedback_table):
        """TC-P2-U15: sql_hash 자동 계산 및 저장"""
        store, table = feedback_table
        sql = "SELECT 1"
        expected_hash = compute_sql_hash(sql)

        feedback_id = store.save_pending(
            history_id="h1",
            question="Q",
            sql=sql,
        )

        item = table.get_item(Key={"feedback_id": feedback_id})["Item"]
        assert item["sql_hash"] == expected_hash

    def test_save_pending_sets_ttl_90_days(self, feedback_table):
        """TC-P2-U16: TTL 90일 설정 (5초 오차 허용)"""
        store, table = feedback_table
        before_ts = int((datetime.utcnow() + timedelta(days=90)).timestamp())

        feedback_id = store.save_pending(
            history_id="h1",
            question="Q",
            sql="SELECT 1",
        )

        after_ts = int((datetime.utcnow() + timedelta(days=90)).timestamp())
        item = table.get_item(Key={"feedback_id": feedback_id})["Item"]
        actual_ttl = int(item["ttl"])

        assert before_ts - 5 <= actual_ttl <= after_ts + 5

    def test_save_pending_dynamodb_error_does_not_raise(self):
        """TC-P2-U17: DynamoDB put_item 장애 시 예외 미전파, feedback_id 반환"""
        with mock_aws():
            db = boto3.resource("dynamodb", region_name="us-east-1")
            # 테이블을 생성하지 않아 ClientError 유발
            store = DynamoDBFeedbackStore(dynamodb_resource=db, table_name="nonexistent-table")

            # 예외가 전파되지 않아야 함
            feedback_id = store.save_pending(
                history_id="h1",
                question="Q",
                sql="SELECT 1",
            )

            assert feedback_id is not None
            assert len(feedback_id) == 36


# ---------------------------------------------------------------------------
# TC-P2-U18 ~ U19: update_status()
# ---------------------------------------------------------------------------


class TestUpdateStatus:
    """update_status() 단위 테스트"""

    def test_update_status_changes_to_trained(self, feedback_table):
        """TC-P2-U18: 정상 상태 업데이트 — trained, processed_at 설정"""
        store, table = feedback_table

        # 먼저 항목 저장
        feedback_id = store.save_pending(
            history_id="h1",
            question="Q",
            sql="SELECT 1",
        )

        result = store.update_status(feedback_id, "trained")

        assert result is True
        item = table.get_item(Key={"feedback_id": feedback_id})["Item"]
        assert item["status"] == "trained"
        assert "processed_at" in item

    def test_update_status_dynamodb_error_returns_false(self):
        """TC-P2-U19: DynamoDB update_item 장애 시 False 반환, 예외 미전파"""
        with mock_aws():
            db = boto3.resource("dynamodb", region_name="us-east-1")
            store = DynamoDBFeedbackStore(dynamodb_resource=db, table_name="nonexistent-table")

            result = store.update_status("fake-id", "trained")

            assert result is False

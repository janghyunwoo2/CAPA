"""
Phase 2 단위 테스트 — DynamoDBHistoryRecorder
커버 TC: TC-P2-U25 ~ TC-P2-U29
대상 파일: services/vanna-api/src/stores/dynamodb_history.py
요구사항: FR-11 — History 저장소 전환 (JSON Lines → DynamoDB query_history 테이블)
"""

import pytest
import boto3
from moto import mock_aws
from datetime import datetime, timedelta
from unittest.mock import patch

from src.stores.dynamodb_history import DynamoDBHistoryRecorder
from src.models.domain import PipelineContext, IntentType, ValidationResult, QueryResults

TABLE_NAME = "test-query-history"


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
def history_table(aws_credentials):
    """moto DynamoDB query_history 테이블"""
    with mock_aws():
        db = boto3.resource("dynamodb", region_name="us-east-1")
        table = db.create_table(
            TableName=TABLE_NAME,
            KeySchema=[{"AttributeName": "history_id", "KeyType": "HASH"}],
            AttributeDefinitions=[{"AttributeName": "history_id", "AttributeType": "S"}],
            BillingMode="PAY_PER_REQUEST",
        )
        recorder = DynamoDBHistoryRecorder(dynamodb_resource=db, table_name=TABLE_NAME)
        yield recorder, table


@pytest.fixture()
def sample_pipeline_context() -> PipelineContext:
    """테스트용 PipelineContext"""
    return PipelineContext(
        original_question="어제 클릭 수",
        slack_user_id="U001",
        slack_channel_id="C001",
        intent=IntentType.DATA_QUERY,
        refined_question="어제 기준 광고 클릭 수를 알려주세요",
        keywords=["클릭", "어제"],
        generated_sql="SELECT COUNT(*) FROM ad_clicks WHERE date='2026-03-19'",
        validation_result=ValidationResult(
            is_valid=True,
            normalized_sql="SELECT COUNT(*) FROM ad_clicks WHERE date='2026-03-19'",
        ),
        query_results=QueryResults(rows=[{"count": 100}], columns=["count"], row_count=1),
        redash_query_id=42,
        redash_url="http://redash.test/queries/42",
    )


# ---------------------------------------------------------------------------
# TC-P2-U25: 이력 정상 저장
# ---------------------------------------------------------------------------


class TestRecord:
    """record() 단위 테스트"""

    def test_record_returns_uuid_and_stores_item(self, history_table, sample_pipeline_context):
        """TC-P2-U25: 이력 정상 저장 — history_id(UUID) 반환, 테이블 항목 존재"""
        recorder, table = history_table
        history_id = recorder.record(sample_pipeline_context)

        assert len(history_id) == 36

        resp = table.get_item(Key={"history_id": history_id})
        assert "Item" in resp
        assert resp["Item"]["history_id"] == history_id

    def test_record_sets_ttl_90_days(self, history_table, sample_pipeline_context):
        """TC-P2-U26: TTL 90일 설정 (5초 오차 허용)"""
        recorder, table = history_table
        before_ts = int((datetime.utcnow() + timedelta(days=90)).timestamp())

        history_id = recorder.record(sample_pipeline_context)

        after_ts = int((datetime.utcnow() + timedelta(days=90)).timestamp())
        item = table.get_item(Key={"history_id": history_id})["Item"]
        actual_ttl = int(item["ttl"])

        assert before_ts - 5 <= actual_ttl <= after_ts + 5

    def test_record_dynamodb_error_does_not_raise(self, aws_credentials, sample_pipeline_context):
        """TC-P2-U27: DynamoDB put_item 장애 시 예외 미전파, history_id 반환"""
        with mock_aws():
            db = boto3.resource("dynamodb", region_name="us-east-1")
            # 테이블 미생성으로 ClientError 유발
            recorder = DynamoDBHistoryRecorder(dynamodb_resource=db, table_name="nonexistent")

            history_id = recorder.record(sample_pipeline_context)

            assert history_id is not None
            assert len(history_id) == 36


# ---------------------------------------------------------------------------
# TC-P2-U28: get_record()
# ---------------------------------------------------------------------------


class TestGetRecord:
    """get_record() 단위 테스트"""

    def test_get_record_returns_matching_item(self, history_table, sample_pipeline_context):
        """TC-P2-U28: 저장 후 조회 — 필드 일치 확인"""
        recorder, table = history_table
        history_id = recorder.record(sample_pipeline_context)

        record = recorder.get_record(history_id)

        assert record is not None
        assert record.history_id == history_id
        assert record.original_question == "어제 클릭 수"


# ---------------------------------------------------------------------------
# TC-P2-U29: update_feedback()
# ---------------------------------------------------------------------------


class TestUpdateFeedback:
    """update_feedback() 단위 테스트"""

    def test_update_feedback_sets_feedback_positive(self, history_table, sample_pipeline_context):
        """TC-P2-U29: 피드백 업데이트 → feedback='positive'"""
        recorder, table = history_table
        history_id = recorder.record(sample_pipeline_context)

        result = recorder.update_feedback(history_id=history_id, feedback="positive")

        assert result is True
        item = table.get_item(Key={"history_id": history_id})["Item"]
        assert item["feedback"] == "positive"

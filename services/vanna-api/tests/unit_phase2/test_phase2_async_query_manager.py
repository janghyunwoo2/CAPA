"""
Phase 2 단위 테스트 — AsyncQueryManager
커버 TC: TC-P2-U49 ~ TC-P2-U52
대상 파일: services/vanna-api/src/async_query_manager.py
요구사항: FR-19 — 비동기 쿼리 태스크 관리
"""

import pytest
import boto3
from moto import mock_aws
from datetime import datetime, timedelta

from src.async_query_manager import AsyncQueryManager
from src.models.async_task import AsyncTaskStatus

TABLE_NAME = "test-async-tasks"


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
def async_task_setup(aws_credentials):
    """moto DynamoDB async-tasks 테이블 + AsyncQueryManager"""
    with mock_aws():
        db = boto3.resource("dynamodb", region_name="us-east-1")
        table = db.create_table(
            TableName=TABLE_NAME,
            KeySchema=[{"AttributeName": "task_id", "KeyType": "HASH"}],
            AttributeDefinitions=[{"AttributeName": "task_id", "AttributeType": "S"}],
            BillingMode="PAY_PER_REQUEST",
        )
        manager = AsyncQueryManager(dynamodb_resource=db, table_name=TABLE_NAME)
        yield manager, table


# ---------------------------------------------------------------------------
# TC-P2-U49: create_task
# ---------------------------------------------------------------------------


class TestCreateTask:
    """create_task() 단위 테스트"""

    def test_create_task_returns_uuid_and_stores_pending(self, async_task_setup):
        """TC-P2-U49: task 생성 → task_id(UUID) 반환, DynamoDB에 status=pending 항목 존재"""
        manager, table = async_task_setup
        task_id = manager.create_task(question="어제 클릭 수", slack_user_id="U001")

        assert len(task_id) == 36  # UUID

        item = table.get_item(Key={"task_id": task_id})["Item"]
        assert item["status"] == AsyncTaskStatus.PENDING.value
        assert item["question"] == "어제 클릭 수"
        assert item["slack_user_id"] == "U001"

    def test_create_task_sets_ttl_24_hours(self, async_task_setup):
        """TC-P2-U52: TTL 24시간(86400초) 설정 (5초 오차 허용)"""
        manager, table = async_task_setup
        before_ts = int((datetime.utcnow() + timedelta(hours=24)).timestamp())

        task_id = manager.create_task(question="Q")

        after_ts = int((datetime.utcnow() + timedelta(hours=24)).timestamp())
        item = table.get_item(Key={"task_id": task_id})["Item"]
        actual_ttl = int(item["ttl"])

        assert before_ts - 5 <= actual_ttl <= after_ts + 5


# ---------------------------------------------------------------------------
# TC-P2-U50: update_status
# ---------------------------------------------------------------------------


class TestUpdateStatus:
    """update_status() 단위 테스트"""

    def test_update_status_to_completed_with_result(self, async_task_setup):
        """TC-P2-U50: 상태 completed로 업데이트 + result 필드 저장"""
        manager, table = async_task_setup
        task_id = manager.create_task(question="Q")

        result_payload = {"sql": "SELECT 1", "answer": "1건"}
        manager.update_status(task_id, AsyncTaskStatus.COMPLETED, result=result_payload)

        item = table.get_item(Key={"task_id": task_id})["Item"]
        assert item["status"] == AsyncTaskStatus.COMPLETED.value
        assert "result" in item
        assert item["result"]["sql"] == "SELECT 1"


# ---------------------------------------------------------------------------
# TC-P2-U51: get_task
# ---------------------------------------------------------------------------


class TestGetTask:
    """get_task() 단위 테스트"""

    def test_get_task_returns_matching_record(self, async_task_setup):
        """TC-P2-U51: 저장된 task_id로 조회 → AsyncTaskRecord 반환, 필드 일치"""
        manager, table = async_task_setup
        task_id = manager.create_task(question="어제 클릭 수", slack_user_id="U001")

        record = manager.get_task(task_id)

        assert record is not None
        assert record.task_id == task_id
        assert record.status == AsyncTaskStatus.PENDING
        assert record.question == "어제 클릭 수"

    def test_get_task_nonexistent_returns_none(self, async_task_setup):
        """get_task 존재하지 않는 task_id → None 반환"""
        manager, table = async_task_setup

        record = manager.get_task("nonexistent-task-id")

        assert record is None

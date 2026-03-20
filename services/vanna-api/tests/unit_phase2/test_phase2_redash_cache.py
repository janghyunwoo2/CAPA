"""
Phase 2 단위 테스트 — RedashClient.create_or_reuse_query() 캐시 로직
커버 TC: TC-P2-U20 ~ TC-P2-U24
대상 파일: services/vanna-api/src/redash_client.py
요구사항: FR-17 — SQL 해시 → Redash query_id 캐시 (DynamoDB 기반)
"""

import pytest
import boto3
from moto import mock_aws
from unittest.mock import AsyncMock, patch, MagicMock
from datetime import datetime, timedelta

from src.redash_client import RedashClient
from src.models.redash import RedashConfig

TABLE_NAME = "test-sql-hash-cache"

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
def hash_cache_table(aws_credentials):
    """moto DynamoDB SQL 해시 캐시 테이블"""
    with mock_aws():
        db = boto3.resource("dynamodb", region_name="us-east-1")
        table = db.create_table(
            TableName=TABLE_NAME,
            KeySchema=[{"AttributeName": "sql_hash", "KeyType": "HASH"}],
            AttributeDefinitions=[{"AttributeName": "sql_hash", "AttributeType": "S"}],
            BillingMode="PAY_PER_REQUEST",
        )
        yield db, table


@pytest.fixture()
def redash_client() -> RedashClient:
    config = RedashConfig(
        base_url="http://redash.test",
        api_key="test-key",
        data_source_id=1,
        query_timeout_sec=30,
        poll_interval_sec=1,
        public_url="http://redash.test",
        enabled=True,
    )
    return RedashClient(config=config)


# ---------------------------------------------------------------------------
# TC-P2-U20: 캐시 히트
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_or_reuse_query_cache_hit(hash_cache_table, redash_client):
    """TC-P2-U20: DynamoDB에 sql_hash 존재 → 기존 query_id 반환, Redash POST 미호출"""
    from src.pipeline.sql_hash import compute_sql_hash
    db, table = hash_cache_table

    sql = "SELECT * FROM ad_clicks"
    sql_hash = compute_sql_hash(sql)

    # 사전에 캐시 항목 삽입
    table.put_item(Item={"sql_hash": sql_hash, "query_id": 42})

    with patch.object(redash_client, "create_query", new_callable=AsyncMock) as mock_create:
        result = await redash_client.create_or_reuse_query(sql=sql, dynamodb_table=table)

    assert result == 42
    mock_create.assert_not_called()


# ---------------------------------------------------------------------------
# TC-P2-U21: 캐시 미스 → 신규 생성 + DynamoDB 저장
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_or_reuse_query_cache_miss_creates_and_stores(hash_cache_table, redash_client):
    """TC-P2-U21: DynamoDB에 sql_hash 없음 → Redash 신규 생성 후 DynamoDB 저장"""
    from src.pipeline.sql_hash import compute_sql_hash
    db, table = hash_cache_table

    sql = "SELECT COUNT(*) FROM ad_clicks"
    sql_hash = compute_sql_hash(sql)

    with patch.object(redash_client, "create_query", new_callable=AsyncMock, return_value=99):
        result = await redash_client.create_or_reuse_query(sql=sql, dynamodb_table=table)

    assert result == 99

    # DynamoDB에 해시 저장 확인
    item = table.get_item(Key={"sql_hash": sql_hash}).get("Item")
    assert item is not None
    assert int(item["query_id"]) == 99


# ---------------------------------------------------------------------------
# TC-P2-U22: DynamoDB 장애 → graceful fallback (Redash 신규 생성)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_or_reuse_query_dynamodb_error_falls_back_to_create(
    hash_cache_table, redash_client
):
    """TC-P2-U22: DynamoDB get_item 장애 시 Redash 신규 생성, 예외 미전파"""
    db, table = hash_cache_table

    # get_item 호출 시 ClientError 유발을 위해 테이블을 강제 삭제
    table.delete()

    with patch.object(redash_client, "create_query", new_callable=AsyncMock, return_value=77):
        result = await redash_client.create_or_reuse_query(sql="SELECT 1", dynamodb_table=table)

    assert result == 77


# ---------------------------------------------------------------------------
# TC-P2-U23: dynamodb_table=None → Redash 직접 생성
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_or_reuse_query_no_dynamodb_creates_directly(redash_client):
    """TC-P2-U23: dynamodb_table=None → DynamoDB 조회 없이 Redash 신규 생성"""
    with patch.object(redash_client, "create_query", new_callable=AsyncMock, return_value=55):
        result = await redash_client.create_or_reuse_query(sql="SELECT 1", dynamodb_table=None)

    assert result == 55


# ---------------------------------------------------------------------------
# TC-P2-U24: 캐시 미스 시 DynamoDB TTL 90일 저장
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_or_reuse_query_stores_ttl_90_days(hash_cache_table, redash_client):
    """TC-P2-U24: 캐시 미스 후 DynamoDB 저장 항목의 TTL이 약 90일"""
    from src.pipeline.sql_hash import compute_sql_hash
    db, table = hash_cache_table

    sql = "SELECT user_id FROM ad_combined_log"
    sql_hash = compute_sql_hash(sql)
    before_ts = int((datetime.utcnow() + timedelta(days=90)).timestamp())

    with patch.object(redash_client, "create_query", new_callable=AsyncMock, return_value=88):
        await redash_client.create_or_reuse_query(sql=sql, dynamodb_table=table)

    after_ts = int((datetime.utcnow() + timedelta(days=90)).timestamp())

    item = table.get_item(Key={"sql_hash": sql_hash}).get("Item")
    assert item is not None
    actual_ttl = int(item["ttl"])
    assert before_ts - 5 <= actual_ttl <= after_ts + 5

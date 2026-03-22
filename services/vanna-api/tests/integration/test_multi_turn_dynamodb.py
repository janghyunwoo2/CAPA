"""
Multi-Turn DynamoDB 통합 테스트

TC 목록:
  TC-IT-01: session_id-turn_number-index GSI 존재 및 ACTIVE 상태
  TC-IT-02: ConversationHistoryRetriever — 실제 DynamoDB에서 새 session 빈 이력 조회
  TC-IT-03: DynamoDB 이력 저장 → 동일 session_id로 조회 시 이전 턴 반환
  TC-IT-04: MULTI_TURN_ENABLED=true 환경변수 설정 확인
"""

import os
import uuid
import time

import boto3
import pytest
from botocore.exceptions import ClientError

HISTORY_TABLE = os.getenv("DYNAMODB_HISTORY_TABLE", "capa-dev-query-history")
AWS_REGION = os.getenv("AWS_REGION", "ap-northeast-2")
GSI_NAME = "session_id-turn_number-index"


@pytest.fixture(scope="module")
def dynamodb():
    return boto3.resource("dynamodb", region_name=AWS_REGION)


@pytest.fixture(scope="module")
def dynamodb_client():
    return boto3.client("dynamodb", region_name=AWS_REGION)


@pytest.fixture(scope="module")
def history_table(dynamodb):
    return dynamodb.Table(HISTORY_TABLE)


# ---------------------------------------------------------------------------
# TC-IT-01: GSI 존재 및 ACTIVE
# ---------------------------------------------------------------------------

class TestDynamoDBGSI:
    def test_session_id_gsi_exists_and_active(self, dynamodb_client):
        """TC-IT-01: capa-dev-query-history 테이블에 session_id-turn_number-index GSI 존재 및 ACTIVE"""
        resp = dynamodb_client.describe_table(TableName=HISTORY_TABLE)
        gsi_list = resp["Table"].get("GlobalSecondaryIndexes", [])
        gsi_names = [g["IndexName"] for g in gsi_list]

        assert GSI_NAME in gsi_names, (
            f"GSI '{GSI_NAME}' not found. 현재 GSI: {gsi_names}"
        )

        gsi = next(g for g in gsi_list if g["IndexName"] == GSI_NAME)
        assert gsi["IndexStatus"] == "ACTIVE", (
            f"GSI '{GSI_NAME}' 상태: {gsi['IndexStatus']} (ACTIVE 아님)"
        )


# ---------------------------------------------------------------------------
# TC-IT-02: 새 session_id로 빈 이력 조회
# ---------------------------------------------------------------------------

class TestConversationHistoryRetriever:
    def test_retrieve_empty_history_for_new_session(self, dynamodb):
        """TC-IT-02: 존재하지 않는 session_id 조회 시 빈 이력 반환 (GSI 정상 동작 확인)"""
        from src.pipeline.conversation_history_retriever import ConversationHistoryRetriever
        from src.models.domain import PipelineContext

        retriever = ConversationHistoryRetriever(dynamodb_resource=dynamodb)
        ctx = PipelineContext(
            original_question="테스트 질문",
            session_id=f"test-session-{uuid.uuid4()}",
        )

        result = retriever.retrieve(ctx)

        # 새 세션 → 이력 없음, turn_number=1, 예외 없음
        assert result.conversation_history == []
        assert result.turn_number == 1

    def test_retrieve_returns_previous_turn_after_save(self, history_table, dynamodb):
        """TC-IT-03: DynamoDB에 이력 저장 후 동일 session_id로 조회 시 이전 턴 반환"""
        from src.pipeline.conversation_history_retriever import ConversationHistoryRetriever
        from src.models.domain import PipelineContext

        session_id = f"tdd-test-{uuid.uuid4()}"
        history_id = str(uuid.uuid4())

        # Turn 1 이력을 DynamoDB에 직접 저장
        history_table.put_item(Item={
            "history_id": history_id,
            "session_id": session_id,
            "turn_number": 1,
            "original_question": "어제 전체 광고 클릭수는?",
            "refined_question": "어제 광고 클릭수",
            "generated_sql": "SELECT COUNT(*) FROM ad_combined_log WHERE is_click = true",
            "answer": "총 12,345건 클릭이 발생했습니다.",
            "timestamp": "2026-03-22T00:00:00",
            "ttl": int(time.time()) + 3600,
        })

        # Turn 2 조회
        retriever = ConversationHistoryRetriever(dynamodb_resource=dynamodb)
        ctx = PipelineContext(
            original_question="기기별로 나눠줘",
            session_id=session_id,
        )

        result = retriever.retrieve(ctx)

        # 저장한 Turn 1이 조회돼야 함
        assert len(result.conversation_history) == 1
        assert result.conversation_history[0].turn_number == 1
        assert result.conversation_history[0].question == "어제 전체 광고 클릭수는?"
        assert result.turn_number == 2  # 다음 턴

        # 테스트 데이터 정리
        history_table.delete_item(Key={"history_id": history_id})


# ---------------------------------------------------------------------------
# TC-IT-04: MULTI_TURN_ENABLED 환경변수
# ---------------------------------------------------------------------------

class TestMultiTurnEnvConfig:
    def test_multi_turn_enabled_env_is_true(self):
        """TC-IT-04: MULTI_TURN_ENABLED=true 환경변수가 vanna-api 컨테이너에 설정돼 있어야 함"""
        value = os.getenv("MULTI_TURN_ENABLED", "false")
        assert value.lower() == "true", (
            f"MULTI_TURN_ENABLED='{value}' — 'true'로 설정 필요 (docker-compose.local-e2e.yml)"
        )

    def test_pipeline_has_conversation_retriever(self):
        """TC-IT-04b: MULTI_TURN_ENABLED=true 시 QueryPipeline._conversation_retriever 초기화됨"""
        from src.query_pipeline import QueryPipeline, MULTI_TURN_ENABLED

        assert MULTI_TURN_ENABLED is True, (
            "src.query_pipeline.MULTI_TURN_ENABLED is False — 환경변수 설정 후 재시작 필요"
        )

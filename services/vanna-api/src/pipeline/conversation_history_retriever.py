"""
Step 0: ConversationHistoryRetriever — DynamoDB GSI로 대화 이력 조회 (FR-20-01)
session_id로 기존 대화 이력을 조회하고 turn_number를 계산한다.
"""

import logging
import os
from typing import Any

from botocore.exceptions import ClientError

from ..models.domain import ConversationTurn, PipelineContext

logger = logging.getLogger(__name__)


class ConversationHistoryRetriever:
    """Step 0 — DynamoDB GSI 기반 대화 이력 조회 (FR-20-01)"""

    def __init__(self, dynamodb_resource: Any) -> None:
        self._resource = dynamodb_resource
        self._table_name = os.getenv("HISTORY_TABLE_NAME", "capa-dev-query-history")
        self._max_turns = int(os.getenv("CONVERSATION_MAX_TURNS", "5"))

    def retrieve(self, ctx: PipelineContext) -> PipelineContext:
        """session_id로 GSI 조회, conversation_history 채우고 turn_number 계산.

        session_id 없으면 건너뜀 (하위 호환).
        ClientError 발생 시 graceful degradation — 빈 이력으로 진행.
        """
        if not ctx.session_id:
            return ctx

        try:
            table = self._resource.Table(self._table_name)
            resp = table.query(
                IndexName="session_id-turn_number-index",
                KeyConditionExpression="session_id = :sid",
                ExpressionAttributeValues={":sid": ctx.session_id},
                ScanIndexForward=True,
            )
            all_items = resp.get("Items", [])

            # turn_number = 전체 이력의 최대값 + 1
            if all_items:
                max_turn = max(int(item["turn_number"]) for item in all_items)
                ctx.turn_number = max_turn + 1
            else:
                ctx.turn_number = 1

            # 최근 max_turns 개만 conversation_history에 포함
            items_to_use = (
                all_items[-self._max_turns:]
                if len(all_items) > self._max_turns
                else all_items
            )
            ctx.conversation_history = [
                ConversationTurn(
                    turn_number=int(item["turn_number"]),
                    question=item.get("original_question", ""),
                    refined_question=item.get("refined_question"),
                    generated_sql=item.get("generated_sql"),
                    answer=item.get("answer"),
                )
                for item in items_to_use
            ]

        except ClientError as e:
            logger.error(f"대화 이력 조회 실패 (graceful degradation): {e}")

        return ctx

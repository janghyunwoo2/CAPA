"""
DynamoDBHistoryRecorder — DynamoDB 기반 쿼리 이력 저장 (Phase 2)
설계 문서 §7.2 기준
HistoryRecorder 서브클래스로 구현, Phase 1 하위 호환 유지
"""

import hashlib
import logging
import uuid
from datetime import datetime, timedelta
from typing import Any, Optional

from botocore.exceptions import ClientError

from ..history_recorder import HistoryRecorder
from ..models.domain import PipelineContext
from ..models.feedback import QueryHistoryRecord

logger = logging.getLogger(__name__)

_TTL_DAYS = 90


def _hash_user_id(user_id: str) -> str:
    """PII 보호: SHA-256 앞 16자"""
    if not user_id:
        return ""
    return hashlib.sha256(user_id.encode()).hexdigest()[:16]


class DynamoDBHistoryRecorder(HistoryRecorder):
    """Step 11 — DynamoDB 기반 이력 저장 (Phase 2, FR-11)"""

    def __init__(self, dynamodb_resource: Any, table_name: str) -> None:
        # 부모 클래스 __init__을 호출하지 않음 (파일 기반 초기화 불필요)
        self._table = dynamodb_resource.Table(table_name)

    def record(self, ctx: PipelineContext) -> str:
        """DynamoDB에 파이프라인 컨텍스트 이력 저장"""
        history_id = str(uuid.uuid4())
        now = datetime.utcnow()
        ttl = int((now + timedelta(days=_TTL_DAYS)).timestamp())
        item: dict[str, Any] = {
            "history_id": history_id,
            "timestamp": now.isoformat(),
            "slack_user_id": _hash_user_id(ctx.slack_user_id),
            "slack_channel_id": ctx.slack_channel_id,
            "original_question": ctx.original_question,
            "refined_question": ctx.refined_question or "",
            "intent": ctx.intent.value if ctx.intent else "unknown",
            "keywords": ctx.keywords,
            "generated_sql": (
                ctx.validation_result.normalized_sql
                if ctx.validation_result and ctx.validation_result.normalized_sql
                else ctx.generated_sql or ""
            ),
            "sql_validated": (
                ctx.validation_result.is_valid if ctx.validation_result else False
            ),
            "row_count": (
                ctx.query_results.row_count if ctx.query_results else None
            ),
            "redash_query_id": ctx.redash_query_id,
            "redash_url": ctx.redash_url or "",
            "feedback": None,
            "feedback_at": None,
            "trained": False,
            "ttl": ttl,
        }
        # 멀티턴 필드 (FR-20): session_id 있을 때만 저장
        if ctx.session_id:
            answer_text = ctx.analysis.answer if ctx.analysis else None
            item["session_id"] = ctx.session_id
            item["turn_number"] = ctx.turn_number
            if answer_text:
                item["answer"] = answer_text[:500]
            if ctx.slack_thread_ts:
                item["slack_thread_ts"] = ctx.slack_thread_ts
        # None 값 제거 (DynamoDB PutItem 허용 불가)
        item = {k: v for k, v in item.items() if v is not None}
        try:
            self._table.put_item(Item=item)
            logger.info(f"DynamoDB 이력 저장 완료: {history_id}")
        except ClientError as e:
            logger.error(f"DynamoDB 이력 저장 실패: {e}")
        return history_id

    def get_record(self, history_id: str) -> Optional[QueryHistoryRecord]:
        """history_id로 DynamoDB에서 이력 조회"""
        try:
            resp = self._table.get_item(Key={"history_id": history_id})
            item = resp.get("Item")
            if not item:
                return None
            return QueryHistoryRecord(
                history_id=item["history_id"],
                timestamp=datetime.fromisoformat(item["timestamp"]),
                slack_user_id=item.get("slack_user_id", ""),
                slack_channel_id=item.get("slack_channel_id", ""),
                original_question=item.get("original_question", ""),
                refined_question=item.get("refined_question"),
                intent=item.get("intent", "unknown"),
                keywords=item.get("keywords", []),
                generated_sql=item.get("generated_sql"),
                sql_validated=item.get("sql_validated"),
                row_count=item.get("row_count"),
                redash_query_id=item.get("redash_query_id"),
                redash_url=item.get("redash_url"),
                feedback=item.get("feedback"),
                feedback_at=(
                    datetime.fromisoformat(item["feedback_at"])
                    if item.get("feedback_at")
                    else None
                ),
                trained=item.get("trained", False),
            )
        except ClientError as e:
            logger.error(f"DynamoDB 이력 조회 실패: {e}")
            return None

    def update_feedback(
        self,
        history_id: str,
        feedback: str,
        trained: bool = False,
    ) -> bool:
        """DynamoDB 이력 레코드 피드백 업데이트"""
        try:
            self._table.update_item(
                Key={"history_id": history_id},
                UpdateExpression=(
                    "SET feedback = :fb, feedback_at = :fa, trained = :tr"
                ),
                ExpressionAttributeValues={
                    ":fb": feedback,
                    ":fa": datetime.utcnow().isoformat(),
                    ":tr": trained,
                },
            )
            logger.info(f"DynamoDB 피드백 업데이트 완료: {history_id} → {feedback}")
            return True
        except ClientError as e:
            logger.error(f"DynamoDB 피드백 업데이트 실패: {e}")
            return False

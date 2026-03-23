"""
DynamoDBFeedbackStore — DynamoDB 기반 피드백 저장 (Phase 2)
설계 문서 §4.1.3 기준
긍정 피드백을 pending 상태로 저장 → Airflow DAG 배치 검증 후 학습
"""

import logging
import uuid
from datetime import datetime, timedelta
from typing import Any

from botocore.exceptions import ClientError

from ..pipeline.sql_hash import compute_sql_hash

logger = logging.getLogger(__name__)

_TTL_DAYS = 90


class DynamoDBFeedbackStore:
    """피드백 DynamoDB 저장소 (Phase 2, FR-16)"""

    def __init__(self, dynamodb_resource: Any, table_name: str) -> None:
        self._table = dynamodb_resource.Table(table_name)

    def save_pending(
        self,
        history_id: str,
        question: str,
        sql: str,
    ) -> str:
        """피드백을 pending 상태로 DynamoDB 저장 → feedback_id 반환"""
        feedback_id = str(uuid.uuid4())
        now = datetime.utcnow()
        ttl = int((now + timedelta(days=_TTL_DAYS)).timestamp())
        item = {
            "feedback_id": feedback_id,
            "history_id": history_id,
            "question": question,
            "sql": sql,
            "sql_hash": compute_sql_hash(sql),
            "status": "pending",
            "created_at": now.isoformat(),
            "ttl": ttl,
        }
        try:
            self._table.put_item(Item=item)
            logger.info(f"피드백 pending 저장 완료: feedback_id={feedback_id}")
        except ClientError as e:
            logger.error(f"피드백 DynamoDB 저장 실패: {e}")
        return feedback_id

    def update_status(self, feedback_id: str, status: str) -> bool:
        """피드백 상태 업데이트 (pending → trained / explain_failed / duplicate / train_failed)"""
        try:
            self._table.update_item(
                Key={"feedback_id": feedback_id},
                UpdateExpression=(
                    "SET #s = :s, processed_at = :pa"
                ),
                ExpressionAttributeNames={"#s": "status"},
                ExpressionAttributeValues={
                    ":s": status,
                    ":pa": datetime.utcnow().isoformat(),
                },
            )
            logger.info(f"피드백 상태 업데이트: {feedback_id} → {status}")
            return True
        except ClientError as e:
            logger.error(f"피드백 상태 업데이트 실패: {e}")
            return False

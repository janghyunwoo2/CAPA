"""
AsyncQueryManager — DynamoDB 기반 비동기 쿼리 Task 상태 관리 (Phase 2)
설계 문서 §6.2 기준
"""

import logging
import uuid
from datetime import datetime, timedelta
from typing import Any, Optional

from botocore.exceptions import ClientError

from .models.async_task import AsyncTaskRecord, AsyncTaskStatus

logger = logging.getLogger(__name__)

_TTL_HOURS = 24


class AsyncQueryManager:
    """비동기 쿼리 실행 Task 상태 관리자 (DynamoDB 기반)"""

    def __init__(self, dynamodb_resource: Any, table_name: str) -> None:
        self._table = dynamodb_resource.Table(table_name)

    def create_task(self, question: str, slack_user_id: str = "") -> str:
        """신규 비동기 Task 생성 → task_id 반환"""
        task_id = str(uuid.uuid4())
        now = datetime.utcnow()
        ttl = int((now + timedelta(hours=_TTL_HOURS)).timestamp())
        item = {
            "task_id": task_id,
            "status": AsyncTaskStatus.PENDING.value,
            "question": question,
            "slack_user_id": slack_user_id,
            "created_at": now.isoformat(),
            "ttl": ttl,
        }
        try:
            self._table.put_item(Item=item)
            logger.info(f"비동기 Task 생성: task_id={task_id}")
        except ClientError as e:
            logger.error(f"비동기 Task DynamoDB 저장 실패: {e}")
        return task_id

    def update_status(
        self,
        task_id: str,
        status: AsyncTaskStatus,
        result: Optional[dict] = None,
        error: Optional[dict] = None,
    ) -> None:
        """Task 상태 업데이트"""
        update_expr = "SET #s = :s, completed_at = :ca"
        expr_names = {"#s": "status"}
        expr_values: dict[str, Any] = {
            ":s": status.value,
            ":ca": datetime.utcnow().isoformat(),
        }
        if result is not None:
            update_expr += ", #r = :r"
            expr_names["#r"] = "result"
            expr_values[":r"] = result
        if error is not None:
            update_expr += ", #e = :e"
            expr_names["#e"] = "error"
            expr_values[":e"] = error
        try:
            self._table.update_item(
                Key={"task_id": task_id},
                UpdateExpression=update_expr,
                ExpressionAttributeNames=expr_names,
                ExpressionAttributeValues=expr_values,
            )
            logger.info(f"비동기 Task 상태 업데이트: task_id={task_id}, status={status.value}")
        except ClientError as e:
            logger.error(f"비동기 Task 상태 업데이트 실패: {e}")

    def get_task(self, task_id: str) -> Optional[AsyncTaskRecord]:
        """Task 조회"""
        try:
            resp = self._table.get_item(Key={"task_id": task_id})
            item = resp.get("Item")
            if not item:
                return None
            return AsyncTaskRecord(
                task_id=item["task_id"],
                status=AsyncTaskStatus(item["status"]),
                question=item.get("question", ""),
                slack_user_id=item.get("slack_user_id", ""),
                created_at=datetime.fromisoformat(item["created_at"]),
                completed_at=(
                    datetime.fromisoformat(item["completed_at"])
                    if item.get("completed_at")
                    else None
                ),
                result=item.get("result"),
                error=item.get("error"),
                ttl=item.get("ttl"),
            )
        except ClientError as e:
            logger.error(f"비동기 Task 조회 실패: {e}")
            return None

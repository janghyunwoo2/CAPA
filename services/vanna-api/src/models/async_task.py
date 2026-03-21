"""
비동기 쿼리 Task 상태 모델 (Phase 2)
설계 문서 §6.4 기준
"""

from datetime import datetime
from enum import Enum
from typing import Optional
from pydantic import BaseModel


class AsyncTaskStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class AsyncTaskRecord(BaseModel):
    task_id: str
    status: AsyncTaskStatus
    question: str
    slack_user_id: str = ""
    created_at: datetime
    completed_at: Optional[datetime] = None
    result: Optional[dict] = None
    error: Optional[dict] = None
    ttl: Optional[int] = None

"""
피드백 & 학습 이력 모델 — 설계 문서 §4.1.3 기준
"""

from datetime import datetime
from typing import Optional
from pydantic import BaseModel
from .domain import FeedbackType


class QueryHistoryRecord(BaseModel):
    """FR-10 쿼리 이력 — 성공한 쿼리만 저장 (피드백 루프 데이터 축적 목적)
    실패 쿼리 분석은 Phase 3(FR-22)에서 별도 구현
    """
    history_id: str
    timestamp: datetime
    slack_user_id: str          # 저장 시 해시 처리 (PII)
    slack_channel_id: str
    original_question: str
    refined_question: Optional[str] = None
    intent: str
    keywords: list[str] = []
    generated_sql: Optional[str] = None
    sql_validated: Optional[bool] = None
    row_count: Optional[int] = None
    redash_query_id: Optional[int] = None
    redash_url: Optional[str] = None
    feedback: Optional[FeedbackType] = None
    feedback_at: Optional[datetime] = None
    trained: bool = False


class TrainingDataRecord(BaseModel):
    """ChromaDB 학습 데이터 출처 추적"""
    training_id: str
    data_type: str          # ddl / documentation / qa_example
    source: str             # manual_seed / feedback_loop / airflow_sync
    created_at: datetime
    ddl: Optional[str] = None
    documentation: Optional[str] = None
    question: Optional[str] = None
    sql: Optional[str] = None
    sql_hash: Optional[str] = None  # SHA-256, 중복 방지

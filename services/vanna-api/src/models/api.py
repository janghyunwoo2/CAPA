"""
API 요청/응답 모델 — 설계 문서 §3.2 기준
main.py에서 이 모듈을 임포트하여 사용한다.
"""

from typing import Optional
from pydantic import BaseModel, Field
from .domain import IntentType, FeedbackType, TrainDataType


# ---------------------------------------------------------------------------
# 공통 에러 응답 (§3.2, SEC-07)
# ---------------------------------------------------------------------------

class ErrorResponse(BaseModel):
    error_code: str = Field(..., description="에러 코드")
    message: str = Field(..., description="사용자 친화적 메시지 (한국어)")
    detail: Optional[str] = Field(None, description="디버깅 힌트 (DEBUG=true 시만 노출)")
    prompt_used: Optional[str] = Field(None, description="실패 시 사용 프롬프트 (FR-09)")


# ---------------------------------------------------------------------------
# POST /query
# ---------------------------------------------------------------------------

class QueryRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=500, description="자연어 질의 (SEC-08)")
    execute: bool = Field(default=True, description="Redash/Athena 실행 여부")
    slack_user_id: str = Field(default="", description="Slack 사용자 ID")
    slack_channel_id: str = Field(default="", description="Slack 채널 ID")
    conversation_id: Optional[str] = Field(None, description="대화 ID (Phase 3 FR-20)")


class QueryResponse(BaseModel):
    query_id: str = Field(..., description="history_id (FR-10)")
    intent: Optional[IntentType] = None
    refined_question: Optional[str] = None
    sql: Optional[str] = None
    sql_validated: bool = False
    results: Optional[list[dict]] = Field(None, description="최대 10행 (SEC-16)")
    answer: Optional[str] = None
    chart_image_base64: Optional[str] = Field(None, description="matplotlib Base64 PNG (FR-08b)")
    redash_url: Optional[str] = Field(None, description="Redash 쿼리 링크 (FR-08)")
    redash_query_id: Optional[int] = None
    execution_path: str = Field(default="redash")
    error: Optional[ErrorResponse] = None
    elapsed_seconds: float = 0.0


# ---------------------------------------------------------------------------
# POST /feedback
# ---------------------------------------------------------------------------

class FeedbackRequest(BaseModel):
    history_id: str = Field(..., description="QueryHistoryRecord의 고유 ID")
    feedback: FeedbackType
    slack_user_id: str = Field(..., description="피드백 제공 사용자 (Slack Block Kit 콜백)")
    comment: Optional[str] = Field(None, max_length=500)


class FeedbackResponse(BaseModel):
    status: str = "accepted"
    trained: bool = False
    message: str


# ---------------------------------------------------------------------------
# POST /train
# ---------------------------------------------------------------------------

class TrainRequest(BaseModel):
    data_type: TrainDataType
    ddl: Optional[str] = None
    documentation: Optional[str] = None
    sql: Optional[str] = None
    question: Optional[str] = Field(None, description="qa_pair 시 필수")


class TrainResponse(BaseModel):
    status: str = "success"
    data_type: TrainDataType
    message: str
    training_data_count: int = 0


# ---------------------------------------------------------------------------
# GET /health
# ---------------------------------------------------------------------------

class HealthResponse(BaseModel):
    status: str = "ok"
    service: str = "vanna-api"
    version: str = "0.2.0"
    checks: dict[str, str] = Field(default_factory=dict)

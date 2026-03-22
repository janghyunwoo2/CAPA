"""
도메인 모델 — PipelineContext, QueryResults, AnalysisResult, PipelineError, RAGContext
설계 문서 §2.3.1, §4.1.1 기준
"""

from datetime import datetime
from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# 공통 Enum
# ---------------------------------------------------------------------------

class IntentType(str, Enum):
    DATA_QUERY = "data_query"
    GENERAL = "general"
    OUT_OF_SCOPE = "out_of_scope"


class FeedbackType(str, Enum):
    POSITIVE = "positive"
    NEGATIVE = "negative"


class TrainDataType(str, Enum):
    DDL = "ddl"
    DOCUMENTATION = "documentation"
    SQL = "sql"
    QA_PAIR = "qa_pair"


class ChartType(str, Enum):
    BAR = "bar"
    LINE = "line"
    PIE = "pie"
    SCATTER = "scatter"
    NONE = "none"


# ---------------------------------------------------------------------------
# 파이프라인 내부 데이터 모델
# ---------------------------------------------------------------------------

class PipelineError(BaseModel):
    """실패 투명성 (FR-09) — 파이프라인 어느 단계에서 실패했는지 기록"""
    failed_step: int
    step_name: str
    error_code: str
    error_message: str
    generated_sql: Optional[str] = None
    used_prompt: Optional[str] = None


class RAGContext(BaseModel):
    """Step 4 RAGRetriever 출력 — ChromaDB 검색 결과"""
    ddl_context: list[str] = Field(default_factory=list)
    documentation_context: list[str] = Field(default_factory=list)
    sql_examples: list[str] = Field(default_factory=list)


class ValidationResult(BaseModel):
    """Step 6 SQLValidator 출력"""
    is_valid: bool
    normalized_sql: Optional[str] = None
    error_message: Optional[str] = None
    explain_result: Optional[str] = None


class QueryResults(BaseModel):
    """Step 9 ResultCollector 출력 — 쿼리 실행 결과"""
    rows: list[dict] = Field(default_factory=list)
    columns: list[str] = Field(default_factory=list)
    row_count: int = 0
    execution_path: str = "redash"  # "redash" | "athena_fallback"


class AnalysisResult(BaseModel):
    """Step 10 AIAnalyzer 출력 — AI 인사이트"""
    answer: str
    chart_type: ChartType = ChartType.NONE
    insight_points: list[str] = Field(default_factory=list)


class ConversationTurn(BaseModel):
    """멀티턴 대화 한 턴의 이력 (FR-20)"""
    turn_number: int
    question: str
    refined_question: Optional[str] = None
    generated_sql: Optional[str] = None
    answer: Optional[str] = None


class PipelineContext(BaseModel):
    """파이프라인 공유 컨텍스트 — 전 단계에 걸쳐 상태를 전달 (설계 §2.3.1)"""
    # 입력
    original_question: str
    slack_user_id: str = ""
    slack_channel_id: str = ""

    # Step 0: 멀티턴 (FR-20)
    session_id: Optional[str] = None
    turn_number: Optional[int] = None
    conversation_history: list["ConversationTurn"] = Field(default_factory=list)

    # Step 1
    intent: Optional[IntentType] = None

    # Step 2
    refined_question: Optional[str] = None

    # Step 3
    keywords: list[str] = Field(default_factory=list)

    # Step 4
    rag_context: Optional[RAGContext] = None

    # Step 5
    generated_sql: Optional[str] = None

    # Step 6
    validation_result: Optional[ValidationResult] = None

    # Step 7~8
    redash_query_id: Optional[int] = None
    redash_job_id: Optional[str] = None
    redash_query_result_id: Optional[int] = None
    redash_url: Optional[str] = None

    # Step 9
    query_results: Optional[QueryResults] = None

    # Step 10
    analysis: Optional[AnalysisResult] = None

    # Step 10.5
    chart_base64: Optional[str] = None

    # Step 11
    history_id: Optional[str] = None

    # 실패 정보 (FR-09)
    error: Optional[PipelineError] = None

    # 메타
    started_at: datetime = Field(default_factory=datetime.utcnow)

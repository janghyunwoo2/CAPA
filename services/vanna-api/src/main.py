"""
Vanna AI API - Text-to-SQL Service (v2)
11-Step QueryPipeline 위임 방식 (T3)
설계 문서 §3, §5, §6.5 기준

Phase 2 추가:
- ASYNC_QUERY_ENABLED=true 시 POST /query → 202 + task_id
- GET /query/{task_id} 폴링 엔드포인트
- DELETE /training-data/{training_id}
- DYNAMODB_ENABLED=true 시 DynamoDB History/Feedback 초기화
"""

import json
import logging
import os
import time
from datetime import datetime
from contextlib import asynccontextmanager
from typing import AsyncGenerator, Optional

import boto3
import chromadb
from fastapi import BackgroundTasks, Depends, FastAPI, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from vanna.anthropic import Anthropic_Chat
from vanna.chromadb import ChromaDB_VectorStore

from .feedback_manager import FeedbackManager
from .history_recorder import HistoryRecorder
from .models.api import (
    ErrorResponse,
    FeedbackRequest,
    FeedbackResponse,
    HealthResponse,
    QueryRequest,
    QueryResponse as NewQueryResponse,
    TrainRequest,
    TrainResponse,
)
from .models.async_task import AsyncTaskStatus
from .models.domain import FeedbackType, TrainDataType
from .models.redash import RedashConfig
from .query_pipeline import QueryPipeline
from .security.auth import InternalTokenMiddleware, verify_internal_token
from .security.error_handler import generic_exception_handler

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

CHROMA_HOST = os.getenv("CHROMA_HOST", "chromadb.chromadb.svc.cluster.local")
CHROMA_PORT = int(os.getenv("CHROMA_PORT", "8000"))
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
ATHENA_DATABASE = os.getenv("ATHENA_DATABASE", "capa_db")
AWS_REGION = os.getenv("AWS_REGION", "ap-northeast-2")
S3_STAGING_DIR = os.getenv("S3_STAGING_DIR", "")
ATHENA_WORKGROUP = os.getenv("ATHENA_WORKGROUP", "capa-workgroup")
REDASH_ENABLED = os.getenv("REDASH_ENABLED", "true").lower() == "true"
REDASH_BASE_URL = os.getenv("REDASH_BASE_URL", "http://redash.redash.svc.cluster.local:5000")
REDASH_API_KEY = os.getenv("REDASH_API_KEY", "")
REDASH_DATA_SOURCE_ID = int(os.getenv("REDASH_DATA_SOURCE_ID", "1"))
REDASH_QUERY_TIMEOUT_SEC = int(os.getenv("REDASH_QUERY_TIMEOUT_SEC", "300"))
REDASH_POLL_INTERVAL_SEC = int(os.getenv("REDASH_POLL_INTERVAL_SEC", "3"))
REDASH_PUBLIC_URL = os.getenv("REDASH_PUBLIC_URL", "https://redash.capa.internal")
DEBUG = os.getenv("DEBUG", "false").lower() == "true"

# Phase 2 Feature Flags
DYNAMODB_ENABLED = os.getenv("DYNAMODB_ENABLED", "false").lower() == "true"
ASYNC_QUERY_ENABLED = os.getenv("ASYNC_QUERY_ENABLED", "false").lower() == "true"
DYNAMODB_HISTORY_TABLE = os.getenv("DYNAMODB_HISTORY_TABLE", "capa-dev-query-history")
DYNAMODB_FEEDBACK_TABLE = os.getenv("DYNAMODB_FEEDBACK_TABLE", "capa-dev-pending-feedbacks")
DYNAMODB_ASYNC_TABLE = os.getenv("DYNAMODB_ASYNC_TABLE", "capa-dev-async-tasks")


class VannaAthena(ChromaDB_VectorStore, Anthropic_Chat):
    def __init__(self, config=None):
        ChromaDB_VectorStore.__init__(self, config=config)
        Anthropic_Chat.__init__(self, config=config)


def _init_vanna() -> VannaAthena:
    logger.info(f"Vanna 초기화 중: ChromaDB {CHROMA_HOST}:{CHROMA_PORT}")
    chroma_client = chromadb.HttpClient(host=CHROMA_HOST, port=CHROMA_PORT)
    instance = VannaAthena(config={
        "api_key": ANTHROPIC_API_KEY,
        "model": "claude-haiku-4-5-20251001",
        "client": chroma_client,
    })
    logger.info("Vanna 초기화 완료")
    return instance


def _init_pipeline(
    vanna: VannaAthena,
    history_recorder: Optional[HistoryRecorder] = None,
) -> QueryPipeline:
    athena_client = boto3.client("athena", region_name=AWS_REGION)
    redash_config: Optional[RedashConfig] = None
    if REDASH_ENABLED and REDASH_API_KEY:
        redash_config = RedashConfig(
            base_url=REDASH_BASE_URL,
            api_key=REDASH_API_KEY,
            data_source_id=REDASH_DATA_SOURCE_ID,
            query_timeout_sec=REDASH_QUERY_TIMEOUT_SEC,
            poll_interval_sec=REDASH_POLL_INTERVAL_SEC,
            public_url=REDASH_PUBLIC_URL,
            enabled=True,
        )
    return QueryPipeline(
        vanna_instance=vanna,
        anthropic_api_key=ANTHROPIC_API_KEY,
        athena_client=athena_client,
        database=ATHENA_DATABASE,
        workgroup=ATHENA_WORKGROUP,
        s3_staging_dir=S3_STAGING_DIR,
        redash_config=redash_config,
        history_recorder=history_recorder,
    )


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    logger.info("Vanna API 시작 중...")
    vanna = _init_vanna()
    app.state.vanna = vanna

    # Phase 2: DynamoDB 기반 History/Feedback 초기화
    if DYNAMODB_ENABLED:
        try:
            from .stores.dynamodb_history import DynamoDBHistoryRecorder
            from .stores.dynamodb_feedback import DynamoDBFeedbackStore
            dynamodb = boto3.resource("dynamodb", region_name=AWS_REGION)
            recorder = DynamoDBHistoryRecorder(
                dynamodb_resource=dynamodb,
                table_name=DYNAMODB_HISTORY_TABLE,
            )
            feedback_store = DynamoDBFeedbackStore(
                dynamodb_resource=dynamodb,
                table_name=DYNAMODB_FEEDBACK_TABLE,
            )
            logger.info("DynamoDB History/Feedback 초기화 완료")
        except Exception as e:
            logger.error(f"DynamoDB 초기화 실패, JSON Lines 폴백: {e}")
            recorder = HistoryRecorder()
            feedback_store = None
    else:
        recorder = HistoryRecorder()
        feedback_store = None

    app.state.recorder = recorder
    app.state.pipeline = _init_pipeline(vanna, recorder)
    app.state.feedback_manager = FeedbackManager(
        vanna_instance=vanna,
        history_recorder=recorder,
        feedback_store=feedback_store,
    )

    # Phase 2: 비동기 Task 관리자 초기화
    if ASYNC_QUERY_ENABLED and DYNAMODB_ENABLED:
        try:
            from .async_query_manager import AsyncQueryManager
            dynamodb = boto3.resource("dynamodb", region_name=AWS_REGION)
            app.state.async_manager = AsyncQueryManager(
                dynamodb_resource=dynamodb,
                table_name=DYNAMODB_ASYNC_TABLE,
            )
            logger.info("AsyncQueryManager 초기화 완료")
        except Exception as e:
            logger.error(f"AsyncQueryManager 초기화 실패: {e}")
            app.state.async_manager = None
    else:
        app.state.async_manager = None

    yield
    logger.info("Vanna API 종료 중...")


app = FastAPI(
    title="Vanna AI API",
    description="Text-to-SQL 자연어 질의 처리 서비스 (11-Step 파이프라인)",
    version="0.2.0",
    lifespan=lifespan,
)
app.add_middleware(InternalTokenMiddleware)
app.add_exception_handler(Exception, generic_exception_handler)


@app.get("/health", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    """헬스 체크 (인증 없음)"""
    return HealthResponse(
        status="ok",
        service="vanna-api",
        version="0.2.0",
        checks={
            "chromadb": f"{CHROMA_HOST}:{CHROMA_PORT}",
            "athena": ATHENA_DATABASE,
            "redash": "enabled" if REDASH_ENABLED else "disabled",
            "dynamodb": "enabled" if DYNAMODB_ENABLED else "disabled",
            "async_query": "enabled" if ASYNC_QUERY_ENABLED else "disabled",
        },
    )


async def _run_pipeline_async(
    task_id: str,
    request: "QueryRequest",
    pipeline: QueryPipeline,
    async_manager: "AsyncQueryManager",
) -> None:
    """BackgroundTasks에서 실행되는 파이프라인 비동기 래퍼"""
    from .async_query_manager import AsyncQueryManager as _AM
    try:
        async_manager.update_status(task_id, AsyncTaskStatus.RUNNING)
        ctx = await pipeline.run(
            question=request.question,
            slack_user_id=request.slack_user_id,
            slack_channel_id=request.slack_channel_id,
            conversation_id=request.conversation_id or "",
        )
        if ctx.error:
            async_manager.update_status(
                task_id,
                AsyncTaskStatus.FAILED,
                error={
                    "error_code": ctx.error.error_code,
                    "message": ctx.error.error_message,
                },
            )
        else:
            validated_sql = (
                ctx.validation_result.normalized_sql
                if ctx.validation_result and ctx.validation_result.normalized_sql
                else ctx.generated_sql
            )
            result = {
                "query_id": ctx.history_id or "",
                "intent": ctx.intent.value if ctx.intent else None,
                "refined_question": ctx.refined_question,
                "sql": validated_sql,
                "sql_validated": ctx.validation_result.is_valid if ctx.validation_result else False,
                "results": ctx.query_results.rows[:10] if ctx.query_results else None,
                "answer": ctx.analysis.answer if ctx.analysis else None,
                "chart_image_base64": ctx.chart_base64,
                "redash_url": ctx.redash_url,
                "redash_query_id": ctx.redash_query_id,
                "execution_path": ctx.query_results.execution_path if ctx.query_results else "unknown",
                "elapsed_seconds": round((datetime.utcnow() - ctx.started_at).total_seconds(), 2),
            }
            async_manager.update_status(task_id, AsyncTaskStatus.COMPLETED, result=result)
    except Exception as e:
        logger.error(f"비동기 파이프라인 실패: task_id={task_id}, {e}", exc_info=True)
        async_manager.update_status(
            task_id,
            AsyncTaskStatus.FAILED,
            error={"error_code": "INTERNAL_ERROR", "message": "요청 처리 중 오류가 발생했습니다."},
        )


@app.post("/query")
async def query_natural_language(
    request: QueryRequest,
    background_tasks: BackgroundTasks,
) -> dict:
    """자연어 질의 → 파이프라인 실행.

    ASYNC_QUERY_ENABLED=true: 202 Accepted + task_id 즉시 반환 (BackgroundTasks)
    ASYNC_QUERY_ENABLED=false: 기존 동기 응답 유지 (Phase 1 하위 호환)
    """
    pipeline: QueryPipeline = app.state.pipeline

    # Phase 2: 비동기 모드
    if ASYNC_QUERY_ENABLED and app.state.async_manager is not None:
        manager = app.state.async_manager
        task_id = manager.create_task(
            question=request.question,
            slack_user_id=request.slack_user_id,
        )
        background_tasks.add_task(
            _run_pipeline_async, task_id, request, pipeline, manager
        )
        return JSONResponse(
            status_code=202,
            content={"task_id": task_id, "status": "pending"},
        )

    # Phase 1: 동기 모드 (하위 호환)
    start_time = time.time()
    logger.info(f"질의 처리 시작: {request.question[:100]}")
    try:
        ctx = await pipeline.run(
            question=request.question,
            slack_user_id=request.slack_user_id,
            slack_channel_id=request.slack_channel_id,
            conversation_id=request.conversation_id or "",
        )
    except Exception as e:
        logger.error(f"파이프라인 예외: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={"error_code": "INTERNAL_ERROR", "message": "요청 처리 중 오류가 발생했습니다."},
        )
    elapsed = time.time() - start_time
    if ctx.error:
        error_resp = ErrorResponse(
            error_code=ctx.error.error_code,
            message=ctx.error.error_message,
            detail=ctx.error.generated_sql if DEBUG else None,
            prompt_used=ctx.error.used_prompt if DEBUG else None,
        )
        status_map = {
            "INTENT_OUT_OF_SCOPE": 422,
            "INTENT_GENERAL": 422,
            "SQL_GENERATION_FAILED": 422,
            "SQL_VALIDATION_FAILED": 422,
            "SQL_NOT_SELECT": 422,
            "QUERY_TIMEOUT": 504,
            "REDASH_ERROR": 500,
            "ATHENA_EXECUTION_FAILED": 500,
        }
        raise HTTPException(
            status_code=status_map.get(ctx.error.error_code, 500),
            detail=error_resp.model_dump(exclude_none=True),
        )
    results_preview = ctx.query_results.rows[:10] if ctx.query_results else None
    validated_sql = (
        ctx.validation_result.normalized_sql
        if ctx.validation_result and ctx.validation_result.normalized_sql
        else ctx.generated_sql
    )
    return NewQueryResponse(
        query_id=ctx.history_id or "",
        intent=ctx.intent,
        refined_question=ctx.refined_question,
        sql=validated_sql,
        sql_validated=ctx.validation_result.is_valid if ctx.validation_result else False,
        results=results_preview,
        answer=ctx.analysis.answer if ctx.analysis else None,
        chart_image_base64=ctx.chart_base64,
        redash_url=ctx.redash_url,
        redash_query_id=ctx.redash_query_id,
        execution_path=ctx.query_results.execution_path if ctx.query_results else "unknown",
        elapsed_seconds=round(elapsed, 2),
        session_id=ctx.session_id,
    )


@app.get("/query/{task_id}")
async def get_query_result(task_id: str) -> dict:
    """비동기 쿼리 결과 조회 (Phase 2, §6.5).
    ASYNC_QUERY_ENABLED=false 시 404 반환.
    """
    if not ASYNC_QUERY_ENABLED or app.state.async_manager is None:
        raise HTTPException(status_code=404, detail="비동기 쿼리 모드가 비활성화되어 있습니다.")

    manager = app.state.async_manager
    task = manager.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task를 찾을 수 없습니다.")

    if task.status in (AsyncTaskStatus.PENDING, AsyncTaskStatus.RUNNING):
        return JSONResponse(
            status_code=202,
            content={"task_id": task_id, "status": task.status.value},
        )
    if task.status == AsyncTaskStatus.COMPLETED:
        return task.result or {}
    # FAILED
    raise HTTPException(
        status_code=500,
        detail=task.error or {"error_code": "UNKNOWN_ERROR", "message": "알 수 없는 오류가 발생했습니다."},
    )


@app.post("/feedback", response_model=FeedbackResponse)
async def post_feedback(request: FeedbackRequest) -> FeedbackResponse:
    """피드백 수집 (FR-21)"""
    fm: FeedbackManager = app.state.feedback_manager
    logger.info(f"피드백 수신: history_id={request.history_id}, feedback={request.feedback}")
    if request.feedback == FeedbackType.POSITIVE:
        trained, msg = fm.record_positive(history_id=request.history_id, slack_user_id=request.slack_user_id)
        return FeedbackResponse(status="accepted", trained=trained, message=msg)
    msg = fm.record_negative(history_id=request.history_id, slack_user_id=request.slack_user_id, comment=request.comment)
    return FeedbackResponse(status="accepted", trained=False, message=msg)


@app.post("/train", response_model=TrainResponse)
async def train_model(request: TrainRequest) -> TrainResponse:
    """Vanna 모델 학습"""
    vanna: VannaAthena = app.state.vanna
    try:
        if request.data_type == TrainDataType.DDL and request.ddl:
            vanna.train(ddl=request.ddl)
            logger.info("DDL 학습 완료")
        elif request.data_type == TrainDataType.DOCUMENTATION and request.documentation:
            vanna.train(documentation=request.documentation)
            logger.info("Documentation 학습 완료")
        elif request.data_type == TrainDataType.SQL and request.sql:
            vanna.train(sql=request.sql)
            logger.info("SQL 학습 완료")
        elif request.data_type == TrainDataType.QA_PAIR:
            if not request.question or not request.sql:
                raise HTTPException(status_code=400, detail={"error_code": "INVALID_INPUT", "message": "qa_pair 유형은 question과 sql이 필요합니다."})
            vanna.train(question=request.question, sql=request.sql)
            logger.info("QA pair 학습 완료")
        else:
            raise HTTPException(status_code=400, detail={"error_code": "INVALID_INPUT", "message": "유효하지 않은 학습 데이터입니다."})
        training_data = vanna.get_training_data()
        count = len(training_data) if training_data is not None else 0
        return TrainResponse(status="success", data_type=request.data_type, message="학습 데이터가 성공적으로 추가되었습니다.", training_data_count=count)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"학습 오류: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail={"error_code": "INTERNAL_ERROR", "message": "학습 처리 중 오류가 발생했습니다."})


@app.get("/history")
async def get_history(limit: int = 50) -> dict:
    """쿼리 이력 조회 (FR-10)
    DYNAMODB_ENABLED=true 시 DynamoDB 조회, false 시 JSON Lines 파일 조회.
    """
    recorder = app.state.recorder
    try:
        if DYNAMODB_ENABLED:
            # DynamoDB 모드: scan으로 최근 limit건 반환
            from .stores.dynamodb_history import DynamoDBHistoryRecorder
            if isinstance(recorder, DynamoDBHistoryRecorder):
                from boto3.dynamodb.conditions import Key
                try:
                    resp = recorder._table.scan(Limit=limit)
                    items = resp.get("Items", [])
                    items.sort(key=lambda x: x.get("timestamp", ""), reverse=True)
                    return {"data": items[:limit], "total": len(items)}
                except Exception as e:
                    logger.error(f"DynamoDB 이력 조회 오류: {e}", exc_info=True)
                    raise HTTPException(status_code=500, detail={"error_code": "INTERNAL_ERROR", "message": "이력 조회 중 오류가 발생했습니다."})

        # JSON Lines 모드 (Phase 1 하위 호환)
        if not recorder._file.exists():
            return {"data": [], "total": 0}
        lines = recorder._file.read_text(encoding="utf-8").splitlines()
        records = []
        for line in reversed(lines):
            if not line.strip():
                continue
            try:
                records.append(json.loads(line))
            except Exception:
                continue
            if len(records) >= limit:
                break
        return {"data": records, "total": len(records)}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"이력 조회 오류: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail={"error_code": "INTERNAL_ERROR", "message": "이력 조회 중 오류가 발생했습니다."})


@app.get("/training-data")
async def get_training_data() -> dict:
    """저장된 학습 데이터 조회"""
    vanna: VannaAthena = app.state.vanna
    try:
        training_data = vanna.get_training_data()
        records = training_data.to_dict(orient="records") if training_data is not None else []
        return {"data": records, "count": len(records)}
    except Exception as e:
        logger.error(f"학습 데이터 조회 오류: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail={"error_code": "INTERNAL_ERROR", "message": "학습 데이터 조회 중 오류가 발생했습니다."})


@app.delete("/training-data/{training_id}")
async def delete_training_data(
    training_id: str,
    _: None = Depends(verify_internal_token),
) -> dict:
    """학습 데이터 삭제 (Phase 2, FR-13~15, §4.3.3).
    training_id: GET /training-data 응답의 id 필드값.
    """
    vanna: VannaAthena = app.state.vanna
    try:
        vanna.remove_training_data(id=training_id)
        logger.info(f"학습 데이터 삭제 완료: {training_id}")
        return {"status": "deleted", "training_id": training_id}
    except Exception as e:
        logger.error(f"학습 데이터 삭제 실패: {training_id}: {e}")
        raise HTTPException(status_code=400, detail={"error_code": "DELETE_FAILED", "message": "학습 데이터 삭제에 실패했습니다."})


class _LegacyRequest(BaseModel):
    question: str


class _SummarizeRequest(BaseModel):
    text: str


@app.post("/generate-sql")
async def generate_sql_only(request: _LegacyRequest) -> dict:
    """SQL 생성만 (하위 호환성)"""
    from .pipeline.sql_generator import SQLGenerator, SQLGenerationError
    vanna: VannaAthena = app.state.vanna
    try:
        sql = SQLGenerator(vanna_instance=vanna).generate(question=request.question)
        return {"sql": sql}
    except SQLGenerationError as e:
        raise HTTPException(status_code=422, detail={"error_code": "SQL_GENERATION_FAILED", "message": str(e)})
    except Exception as e:
        logger.error(f"SQL 생성 오류: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail={"error_code": "INTERNAL_ERROR", "message": "SQL 생성 중 오류가 발생했습니다."})


@app.post("/summarize")
async def summarize_text(request: _SummarizeRequest) -> dict:
    """텍스트 요약 (하위 호환성)"""
    import anthropic as _anthropic
    try:
        client = _anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
        response = client.messages.create(model="claude-haiku-4-5-20251001", max_tokens=1024, messages=[{"role": "user", "content": request.text}])
        return {"answer": response.content[0].text}
    except Exception as e:
        logger.error(f"요약 오류: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail={"error_code": "INTERNAL_ERROR", "message": "요약 처리 중 오류가 발생했습니다."})

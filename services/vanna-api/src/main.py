"""
Vanna AI API - Text-to-SQL Service
자연어 질의를 SQL로 변환하고 Athena에서 실행하는 FastAPI 애플리케이션
"""

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Dict, List, Optional
import logging
import os
from vanna.chromadb import ChromaDB_VectorStore
from vanna.anthropic import Anthropic_Chat

# 로깅 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# FastAPI 앱 초기화
app = FastAPI(
    title="Vanna AI API",
    description="Text-to-SQL 자연어 질의 처리 서비스",
    version="0.1.0",
)

# 환경 변수
CHROMA_HOST = os.getenv("CHROMA_HOST", "chromadb-service.chromadb.svc.cluster.local")
CHROMA_PORT = int(os.getenv("CHROMA_PORT", "8000"))
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
ATHENA_DATABASE = os.getenv("ATHENA_DATABASE", "capa_db")
AWS_REGION = os.getenv("AWS_REGION", "ap-northeast-2")


# Vanna 클래스 정의 (ChromaDB + Anthropic)
class VannaAthena(ChromaDB_VectorStore, Anthropic_Chat):
    def __init__(self, config=None):
        ChromaDB_VectorStore.__init__(self, config=config)
        Anthropic_Chat.__init__(self, config=config)


# Vanna 인스턴스 (전역)
vanna_instance: Optional[VannaAthena] = None


def get_vanna() -> VannaAthena:
    """Vanna 인스턴스 반환 (Lazy Initialization)"""
    global vanna_instance
    if vanna_instance is None:
        logger.info("Initializing Vanna instance...")
        vanna_instance = VannaAthena(
            config={
                "api_key": ANTHROPIC_API_KEY,
                "model": "claude-3-5-sonnet-20241022",
                "chroma_host": CHROMA_HOST,
                "chroma_port": CHROMA_PORT,
            }
        )
        # Athena 연결 설정 (IRSA 자동 인증)
        vanna_instance.connect_to_athena(
            database=ATHENA_DATABASE, region_name=AWS_REGION
        )
        logger.info("Vanna initialization complete")
    return vanna_instance


# Request/Response 모델
class QueryRequest(BaseModel):
    question: str


class QueryResponse(BaseModel):
    sql: str
    results: Optional[List[Dict]] = None
    error: Optional[str] = None


class TrainRequest(BaseModel):
    ddl: Optional[str] = None
    documentation: Optional[str] = None
    sql: Optional[str] = None


# =====================================================
# API Endpoints
# =====================================================


@app.get("/health")
async def health_check() -> Dict[str, str]:
    """헬스 체크"""
    logger.info("Health check requested")
    return {"status": "ok", "service": "vanna-api"}


@app.post("/query", response_model=QueryResponse)
async def query_natural_language(request: QueryRequest):
    """
    자연어 질의를 SQL로 변환하고 실행

    Example:
        POST /query
        {
            "question": "지난 7일간 CTR이 가장 높은 캠페인 5개를 보여줘"
        }
    """
    try:
        vanna = get_vanna()
        logger.info(f"Processing question: {request.question}")

        # SQL 생성
        sql = vanna.generate_sql(request.question)
        logger.info(f"Generated SQL: {sql}")

        # Athena 실행
        results = vanna.run_sql(sql)

        return QueryResponse(
            sql=sql,
            results=results.to_dict(orient="records") if results is not None else [],
        )

    except Exception as e:
        logger.error(f"Query error: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/generate-sql")
async def generate_sql_only(request: QueryRequest):
    """
    자연어 질의를 SQL로만 변환 (실행하지 않음)
    """
    try:
        vanna = get_vanna()
        sql = vanna.generate_sql(request.question)
        return {"sql": sql}

    except Exception as e:
        logger.error(f"SQL generation error: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/train")
async def train_model(request: TrainRequest):
    """
    Vanna 모델 학습 (DDL, 문서, SQL 예제 추가)

    Example:
        POST /train
        {
            "ddl": "CREATE TABLE ad_events (campaign_id STRING, ctr DOUBLE, ...)",
            "documentation": "CTR은 클릭률을 의미합니다",
            "sql": "SELECT campaign_id, AVG(ctr) FROM ad_events GROUP BY campaign_id"
        }
    """
    try:
        vanna = get_vanna()

        if request.ddl:
            vanna.train(ddl=request.ddl)
            logger.info(f"Trained with DDL: {request.ddl[:100]}...")

        if request.documentation:
            vanna.train(documentation=request.documentation)
            logger.info(f"Trained with documentation: {request.documentation[:100]}...")

        if request.sql:
            vanna.train(sql=request.sql)
            logger.info(f"Trained with SQL: {request.sql[:100]}...")

        return {"status": "success", "message": "Training completed"}

    except Exception as e:
        logger.error(f"Training error: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/training-data")
async def get_training_data():
    """저장된 학습 데이터 조회"""
    try:
        vanna = get_vanna()
        training_data = vanna.get_training_data()
        return {"data": training_data}

    except Exception as e:
        logger.error(f"Error fetching training data: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.on_event("startup")
async def startup_event():
    """애플리케이션 시작 시 실행"""
    logger.info("Vanna API starting up...")
    logger.info(f"ChromaDB: {CHROMA_HOST}:{CHROMA_PORT}")
    logger.info(f"Athena Database: {ATHENA_DATABASE}")
    logger.info(f"AWS Region: {AWS_REGION}")


@app.on_event("shutdown")
async def shutdown_event():
    """애플리케이션 종료 시 실행"""
    logger.info("Vanna API shutting down...")

"""
Vanna AI API - Text-to-SQL Service
자연어 질의를 SQL로 변환하고 Athena에서 실행하는 FastAPI 애플리케이션
"""

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Dict, List, Optional
import logging
import os
import time
import boto3
import pandas as pd
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
S3_STAGING_DIR = os.getenv("S3_STAGING_DIR", "")  # Athena 쿼리 결과 저장 경로


# Vanna 클래스 정의 (ChromaDB + Anthropic + Custom Athena)
class VannaAthena(ChromaDB_VectorStore, Anthropic_Chat):
    def __init__(self, config=None):
        ChromaDB_VectorStore.__init__(self, config=config)
        Anthropic_Chat.__init__(self, config=config)
        self.athena_client = None
        self.athena_database = None
        self.s3_staging_dir = None

    def connect_to_athena(self, database, region_name, s3_staging_dir):
        """Athena 연결 설정"""
        self.athena_database = database
        self.s3_staging_dir = s3_staging_dir
        self.athena_client = boto3.client("athena", region_name=region_name)
        logger.info(f"Connected to Athena: {database}, storage: {s3_staging_dir}")

    def generate_explanation(self, question: str, sql: str, df: pd.DataFrame) -> str:
        """결과에 대한 자연어 설명 생성 (Anthropic SDK 직접 사용)"""
        try:
            import anthropic

            client = anthropic.Anthropic(api_key=self.config.get("api_key"))
            model = self.config.get("model", "claude-haiku-4-5")

            prompt = f"User Question: {question}\nSQL: {sql}\nResults:\n{df.to_string()}\n\nPlease summarize the results and answer the user's question in a friendly tone in Korean."

            response = client.messages.create(
                model=model,
                max_tokens=1024,
                messages=[{"role": "user", "content": prompt}],
            )
            return response.content[0].text
        except Exception as e:
            logger.error(f"Error in generate_explanation: {e}", exc_info=True)
            return f"결과를 요약하는 중 오류가 발생했습니다. (에러: {str(e)})"

    def run_sql(self, sql: str) -> pd.DataFrame:
        """Athena에서 SQL 실행 및 결과 반환 (Custom Implementation)"""
        if not self.athena_client:
            raise Exception(
                "Athena client not initialized. Call connect_to_athena() first."
            )

        logger.info(f"Executing Athena SQL: {sql}")

        # 쿼리 실행 시작
        response = self.athena_client.start_query_execution(
            QueryString=sql,
            QueryExecutionContext={"Database": self.athena_database},
            ResultConfiguration={"OutputLocation": self.s3_staging_dir},
        )
        query_execution_id = response["QueryExecutionId"]

        # 완료 대기 (최대 60초)
        max_attempts = 60
        attempts = 0
        while attempts < max_attempts:
            execution = self.athena_client.get_query_execution(
                QueryExecutionId=query_execution_id
            )
            state = execution["QueryExecution"]["Status"]["State"]

            if state == "SUCCEEDED":
                break
            elif state in ["FAILED", "CANCELLED"]:
                reason = execution["QueryExecution"]["Status"].get(
                    "StateChangeReason", "Unknown"
                )
                raise Exception(f"Athena query {state}: {reason}")

            time.sleep(1)
            attempts += 1
        else:
            raise Exception("Athena query timed out")

        # 결과 가져오기
        paginator = self.athena_client.get_paginator("get_query_results")
        results_iter = paginator.paginate(QueryExecutionId=query_execution_id)

        rows = []
        columns = []

        for results in results_iter:
            if not columns:
                columns = [
                    col["Name"]
                    for col in results["ResultSet"]["ResultSetMetadata"]["ColumnInfo"]
                ]

            for row in results["ResultSet"]["Rows"]:
                data = [val.get("VarCharValue", None) for val in row["Data"]]
                rows.append(data)

        if not rows:
            return pd.DataFrame(columns=columns)

        # 데이터프레임 생성 (첫 줄이 컬럼명과 겹치면 제거)
        df = pd.DataFrame(rows, columns=columns)
        if len(df) > 0 and list(df.iloc[0]) == columns:
            df = df.iloc[1:].reset_index(drop=True)

        return df


# Vanna 인스턴스 (전역)
vanna_instance: Optional[VannaAthena] = None


def get_vanna() -> VannaAthena:
    """Vanna 인스턴스 반환 (Lazy Initialization)"""
    global vanna_instance
    if vanna_instance is None:
        logger.info(f"Initializing Vanna instance with key: {ANTHROPIC_API_KEY[:5]}...")
        import chromadb

        # Instantiate external ChromaDB client properly
        chroma_client = chromadb.HttpClient(host=CHROMA_HOST, port=CHROMA_PORT)

        vanna_instance = VannaAthena(
            config={
                "api_key": ANTHROPIC_API_KEY,
                "model": "claude-haiku-4-5",
                "client": chroma_client,
            }
        )
        # Athena 연결 설정 (IRSA 자동 인증)
        vanna_instance.connect_to_athena(
            database=ATHENA_DATABASE,
            region_name=AWS_REGION,
            s3_staging_dir=S3_STAGING_DIR,
        )
        logger.info("Vanna initialization complete")
    return vanna_instance


# Request/Response 모델
class QueryRequest(BaseModel):
    question: str


class QueryResponse(BaseModel):
    sql: str
    results: Optional[List[Dict]] = None
    answer: Optional[str] = None
    error: Optional[str] = None


class TrainRequest(BaseModel):
    ddl: Optional[str] = None
    documentation: Optional[str] = None
    sql: Optional[str] = None


class SummarizeRequest(BaseModel):
    text: str


class SummarizeResponse(BaseModel):
    answer: str


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

        # AI 요약/설명 생성
        answer = "답변을 생성하지 못했습니다."
        if results is not None:
            try:
                answer = vanna.generate_explanation(request.question, sql, results)
            except Exception as ae:
                logger.error(f"Explanation generation error: {ae}")
                answer = f"쿼리 실행은 성공했으나 요약 생성 중 오류가 발생했습니다. (결과: {len(results)}건)"

        return QueryResponse(
            sql=sql,
            results=results.to_dict(orient="records") if results is not None else [],
            answer=answer,
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


@app.post("/summarize", response_model=SummarizeResponse)
async def summarize_text(request: SummarizeRequest):
    """
    집계된 데이터 텍스트를 AI로 요약 분석
    """
    try:
        import anthropic

        vanna = get_vanna()
        client = anthropic.Anthropic(api_key=vanna.config.get("api_key"))
        model = vanna.config.get("model", "claude-haiku-4-5")

        logger.info(f"Summarizing text: {request.text[:100]}...")

        response = client.messages.create(
            model=model,
            max_tokens=1024,
            messages=[{"role": "user", "content": request.text}],
        )
        return SummarizeResponse(answer=response.content[0].text)

    except Exception as e:
        logger.error(f"Summarization error: {str(e)}", exc_info=True)
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

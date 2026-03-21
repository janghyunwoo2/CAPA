"""
capa_chromadb_refresh — Phase 2 주간 ChromaDB 학습 데이터 검증 + 자동 학습

스케줄: 매주 월요일 00:00 UTC (= 09:00 KST)
FR-18: Airflow DAG 연동 — pending_feedbacks 배치 처리
"""
from __future__ import annotations

import hashlib
import logging
import os
import re
import time
from datetime import datetime, timedelta

from airflow import DAG
from airflow.operators.python import PythonOperator, ShortCircuitOperator

logger = logging.getLogger(__name__)

# ------------------------------------------------------------------------------
# 환경변수
# ------------------------------------------------------------------------------
DYNAMODB_FEEDBACK_TABLE = os.getenv(
    "DYNAMODB_FEEDBACK_TABLE", "capa-dev-pending-feedbacks"
)
CHROMA_HOST = os.getenv("CHROMA_HOST", "chromadb.chromadb.svc.cluster.local")
CHROMA_PORT = int(os.getenv("CHROMA_PORT", "8000"))
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
ATHENA_DATABASE = os.getenv("ATHENA_DATABASE", "capa_db")
ATHENA_WORKGROUP = os.getenv("ATHENA_WORKGROUP", "capa-workgroup")
S3_STAGING_DIR = os.getenv("S3_STAGING_DIR", "")
AWS_REGION = os.getenv("AWS_REGION", "ap-northeast-2")

# Athena EXPLAIN 폴링 최대 대기 횟수 (3초 간격 × 30 = 90초)
_EXPLAIN_POLL_MAX = 30
_EXPLAIN_POLL_INTERVAL = 3


# ------------------------------------------------------------------------------
# 유틸
# ------------------------------------------------------------------------------
def _normalize_sql(sql: str) -> str:
    """SQL 정규화: 주석 제거 + 공백 통일 + 소문자 변환"""
    sql = re.sub(r"--[^\n]*", "", sql)
    sql = re.sub(r"/\*.*?\*/", "", sql, flags=re.DOTALL)
    sql = re.sub(r"\s+", " ", sql).strip()
    return sql.lower()


def _compute_sql_hash(sql: str) -> str:
    return hashlib.sha256(_normalize_sql(sql).encode("utf-8")).hexdigest()


# ------------------------------------------------------------------------------
# Task 1: pending 항목 추출
# ------------------------------------------------------------------------------
def extract_pending_feedbacks(**kwargs) -> list[dict]:
    """DynamoDB pending_feedbacks에서 status='pending' 항목 전체 추출"""
    import boto3
    from boto3.dynamodb.conditions import Attr
    from botocore.exceptions import ClientError

    try:
        dynamodb = boto3.resource("dynamodb", region_name=AWS_REGION)
        table = dynamodb.Table(DYNAMODB_FEEDBACK_TABLE)

        response = table.scan(FilterExpression=Attr("status").eq("pending"))
        items: list[dict] = response.get("Items", [])

        # 페이지네이션 처리
        while "LastEvaluatedKey" in response:
            response = table.scan(
                FilterExpression=Attr("status").eq("pending"),
                ExclusiveStartKey=response["LastEvaluatedKey"],
            )
            items.extend(response.get("Items", []))

        logger.info("pending 항목 추출 완료: %d건", len(items))
        return items
    except ClientError as e:
        logger.error("DynamoDB Scan 실패: %s", e)
        raise


# ------------------------------------------------------------------------------
# ShortCircuit: pending 항목이 없으면 후속 Task 스킵
# ------------------------------------------------------------------------------
def has_pending_items(**kwargs) -> bool:
    ti = kwargs["ti"]
    items = ti.xcom_pull(task_ids="extract_pending_feedbacks")
    count = len(items) if items else 0
    logger.info("pending 항목 수: %d — %s", count, "계속 진행" if count else "ShortCircuit")
    return bool(count)


# ------------------------------------------------------------------------------
# Task 2: SQL EXPLAIN 검증 + 해시 중복 제거
# ------------------------------------------------------------------------------
def validate_and_deduplicate(**kwargs) -> list[dict]:
    """EXPLAIN 재검증 후 SQL 해시 기준 중복 제거, 실패 항목은 상태 업데이트"""
    import boto3
    from botocore.exceptions import ClientError

    ti = kwargs["ti"]
    pending: list[dict] = ti.xcom_pull(task_ids="extract_pending_feedbacks") or []

    dynamodb = boto3.resource("dynamodb", region_name=AWS_REGION)
    table = dynamodb.Table(DYNAMODB_FEEDBACK_TABLE)
    athena_client = boto3.client("athena", region_name=AWS_REGION)

    validated: list[dict] = []
    seen_hashes: set[str] = set()

    def _update_status(feedback_id: str, status: str) -> None:
        try:
            table.update_item(
                Key={"feedback_id": feedback_id},
                UpdateExpression="SET #s = :s",
                ExpressionAttributeNames={"#s": "status"},
                ExpressionAttributeValues={":s": status},
            )
        except ClientError as ce:
            logger.error("상태 업데이트 실패 (%s → %s): %s", feedback_id, status, ce)

    for item in pending:
        feedback_id = item.get("feedback_id", "")
        sql = item.get("sql", "")
        sql_hash = item.get("sql_hash") or _compute_sql_hash(sql)

        # 1. Athena EXPLAIN 검증
        try:
            resp = athena_client.start_query_execution(
                QueryString=f"EXPLAIN {sql}",
                QueryExecutionContext={"Database": ATHENA_DATABASE},
                ResultConfiguration={"OutputLocation": S3_STAGING_DIR},
                WorkGroup=ATHENA_WORKGROUP,
            )
            execution_id = resp["QueryExecutionId"]

            for _ in range(_EXPLAIN_POLL_MAX):
                state_resp = athena_client.get_query_execution(
                    QueryExecutionId=execution_id
                )
                state = state_resp["QueryExecution"]["Status"]["State"]
                if state == "SUCCEEDED":
                    break
                if state in ("FAILED", "CANCELLED"):
                    raise RuntimeError(f"EXPLAIN 쿼리 상태: {state}")
                time.sleep(_EXPLAIN_POLL_INTERVAL)
            else:
                raise TimeoutError("EXPLAIN 폴링 타임아웃")

        except Exception as e:
            logger.warning("EXPLAIN 검증 실패 (%s): %s", feedback_id, e)
            _update_status(feedback_id, "explain_failed")
            continue

        # 2. SQL 해시 중복 체크
        if sql_hash in seen_hashes:
            logger.info("해시 중복 스킵 (%s): %s...", feedback_id, sql_hash[:16])
            _update_status(feedback_id, "duplicate")
            continue

        seen_hashes.add(sql_hash)
        validated.append(item)

    logger.info(
        "검증 완료: %d건 통과 / %d건 중", len(validated), len(pending)
    )
    return validated


# ------------------------------------------------------------------------------
# Task 3: ChromaDB 배치 학습
# ------------------------------------------------------------------------------
def batch_train_chromadb(**kwargs) -> dict[str, int]:
    """검증된 질문-SQL 쌍을 ChromaDB에 배치 학습, DynamoDB 상태 업데이트"""
    import boto3
    import chromadb
    from botocore.exceptions import ClientError
    from vanna.anthropic import Anthropic_Chat
    from vanna.chromadb import ChromaDB_VectorStore

    class _VannaAthena(ChromaDB_VectorStore, Anthropic_Chat):
        def __init__(self, config: dict | None = None) -> None:
            ChromaDB_VectorStore.__init__(self, config=config)
            Anthropic_Chat.__init__(self, config=config)

    ti = kwargs["ti"]
    validated: list[dict] = ti.xcom_pull(task_ids="validate_and_deduplicate") or []

    if not validated:
        logger.info("학습할 항목 없음 — 스킵")
        return {"trained": 0, "total": 0}

    # Vanna 초기화
    chroma_client = chromadb.HttpClient(host=CHROMA_HOST, port=CHROMA_PORT)
    vanna = _VannaAthena(
        config={
            "api_key": ANTHROPIC_API_KEY,
            "model": "claude-haiku-4-5-20251001",
            "client": chroma_client,
        }
    )

    dynamodb = boto3.resource("dynamodb", region_name=AWS_REGION)
    table = dynamodb.Table(DYNAMODB_FEEDBACK_TABLE)

    trained_count = 0
    for item in validated:
        feedback_id = item.get("feedback_id", "")
        question = item.get("question", "")
        sql = item.get("sql", "")

        try:
            vanna.train(question=question, sql=sql)
            table.update_item(
                Key={"feedback_id": feedback_id},
                UpdateExpression="SET #s = :s, processed_at = :pa",
                ExpressionAttributeNames={"#s": "status"},
                ExpressionAttributeValues={
                    ":s": "trained",
                    ":pa": datetime.utcnow().isoformat(),
                },
            )
            trained_count += 1
            logger.info("학습 완료: %s", feedback_id)
        except Exception as e:
            logger.error("학습 실패 (%s): %s", feedback_id, e)
            try:
                table.update_item(
                    Key={"feedback_id": feedback_id},
                    UpdateExpression="SET #s = :s",
                    ExpressionAttributeNames={"#s": "status"},
                    ExpressionAttributeValues={":s": "train_failed"},
                )
            except ClientError as ce:
                logger.error("상태 업데이트 실패: %s", ce)

    result: dict[str, int] = {"trained": trained_count, "total": len(validated)}
    logger.info("배치 학습 완료: %s", result)
    return result


# ------------------------------------------------------------------------------
# DAG 정의
# ------------------------------------------------------------------------------
default_args = {
    "owner": "capa-team",
    "retries": 2,
    "retry_delay": timedelta(minutes=5),
    "email_on_failure": True,
    "execution_timeout": timedelta(minutes=30),
}

with DAG(
    dag_id="capa_chromadb_refresh",
    default_args=default_args,
    description="Phase 2 — 주간 ChromaDB 학습 데이터 검증 + 자동 학습 (FR-18)",
    schedule_interval="0 0 * * 1",  # 매주 월요일 00:00 UTC = 09:00 KST
    start_date=datetime(2026, 3, 24),
    catchup=False,
    tags=["capa", "text-to-sql", "chromadb", "phase2"],
    max_active_runs=1,
) as dag:

    t1_extract = PythonOperator(
        task_id="extract_pending_feedbacks",
        python_callable=extract_pending_feedbacks,
    )

    t_check = ShortCircuitOperator(
        task_id="check_has_items",
        python_callable=has_pending_items,
    )

    t2_validate = PythonOperator(
        task_id="validate_and_deduplicate",
        python_callable=validate_and_deduplicate,
    )

    t3_train = PythonOperator(
        task_id="batch_train_chromadb",
        python_callable=batch_train_chromadb,
    )

    t1_extract >> t_check >> t2_validate >> t3_train

"""AWS Athena 쿼리 클라이언트 모듈.

boto3 기반으로 Athena에 쿼리를 실행하고 결과를 DataFrame으로 반환합니다.
Glue 테이블: capa_db.ad_events_raw
"""

import os
import time
import logging

import boto3
import pandas as pd
from dotenv import load_dotenv

load_dotenv()

logger: logging.Logger = logging.getLogger(__name__)

# Athena 설정
ATHENA_S3_OUTPUT: str = os.environ.get(
    "ATHENA_S3_OUTPUT", "s3://capa-logs-dev-ap-northeast-2/athena-results/"
)
GLUE_DATABASE: str = os.environ.get("GLUE_DATABASE", "capa_db")
GLUE_TABLE: str = os.environ.get("GLUE_TABLE", "ad_events_raw")

# 쿼리 폴링 설정
POLL_INTERVAL_SEC: float = 1.0
MAX_POLL_COUNT: int = 120


def _get_client() -> "boto3.client":
    """Athena boto3 클라이언트를 반환합니다."""
    return boto3.client(
        "athena",
        region_name=os.environ.get("AWS_REGION", "ap-northeast-2"),
    )


def execute_query(sql: str) -> pd.DataFrame:
    """Athena 쿼리를 실행하고 결과를 DataFrame으로 반환합니다.

    Args:
        sql: 실행할 SQL 쿼리 문자열

    Returns:
        쿼리 결과가 담긴 pandas DataFrame

    Raises:
        RuntimeError: 쿼리 실행 실패 시
        TimeoutError: 쿼리 폴링 제한 시간 초과 시
    """
    client = _get_client()

    # 쿼리 실행 시작
    response: dict = client.start_query_execution(
        QueryString=sql,
        QueryExecutionContext={"Database": GLUE_DATABASE},
        ResultConfiguration={"OutputLocation": ATHENA_S3_OUTPUT},
    )
    query_id: str = response["QueryExecutionId"]
    logger.info(f"Athena 쿼리 시작: {query_id}")

    # 폴링으로 쿼리 완료 대기
    state: str = _wait_for_query(client, query_id)

    if state != "SUCCEEDED":
        # 실패 사유 조회
        exec_info = client.get_query_execution(QueryExecutionId=query_id)
        reason: str = (
            exec_info["QueryExecution"]
            .get("Status", {})
            .get("StateChangeReason", "알 수 없는 오류")
        )
        raise RuntimeError(f"Athena 쿼리 실패 (id={query_id}): {reason}")

    # 결과 조회 및 DataFrame 변환
    return _fetch_results(client, query_id)


def _wait_for_query(client: "boto3.client", query_id: str) -> str:
    """쿼리 완료까지 폴링합니다.

    Args:
        client: Athena boto3 클라이언트
        query_id: 쿼리 실행 ID

    Returns:
        최종 쿼리 상태 문자열 (SUCCEEDED, FAILED, CANCELLED)

    Raises:
        TimeoutError: 폴링 횟수 초과 시
    """
    for _ in range(MAX_POLL_COUNT):
        response = client.get_query_execution(QueryExecutionId=query_id)
        state: str = response["QueryExecution"]["Status"]["State"]

        if state in ("SUCCEEDED", "FAILED", "CANCELLED"):
            logger.info(f"Athena 쿼리 완료: {query_id} -> {state}")
            return state

        time.sleep(POLL_INTERVAL_SEC)

    raise TimeoutError(f"Athena 쿼리 시간 초과 (id={query_id}, {MAX_POLL_COUNT}회 폴링)")


def _fetch_results(client: "boto3.client", query_id: str) -> pd.DataFrame:
    """Athena 쿼리 결과를 DataFrame으로 변환합니다.

    Args:
        client: Athena boto3 클라이언트
        query_id: 쿼리 실행 ID

    Returns:
        쿼리 결과 DataFrame
    """
    rows: list[list[str]] = []
    next_token: str | None = None

    while True:
        kwargs: dict = {"QueryExecutionId": query_id, "MaxResults": 1000}
        if next_token:
            kwargs["NextToken"] = next_token

        result = client.get_query_results(**kwargs)
        result_rows = result["ResultSet"]["Rows"]

        for row in result_rows:
            rows.append([col.get("VarCharValue", "") for col in row["Data"]])

        next_token = result.get("NextToken")
        if not next_token:
            break

    if not rows:
        return pd.DataFrame()

    # 첫 번째 행은 헤더
    header: list[str] = rows[0]
    data: list[list[str]] = rows[1:]

    return pd.DataFrame(data, columns=header)


# --- 사전 정의 쿼리 함수들 ---


def query_daily_summary(start_date: str, end_date: str) -> pd.DataFrame:
    """일별 노출/클릭/전환 집계를 조회합니다.

    Args:
        start_date: 시작 날짜 (YYYY-MM-DD)
        end_date: 종료 날짜 (YYYY-MM-DD)

    Returns:
        일별 집계 DataFrame (date, impressions, clicks, conversions, cost)
    """
    sql: str = f"""
    SELECT
        CAST(from_unixtime(timestamp / 1000) AS date) AS date,
        COUNT(CASE WHEN event_type = 'impression' THEN 1 END) AS impressions,
        COUNT(CASE WHEN event_type = 'click' THEN 1 END) AS clicks,
        COUNT(CASE WHEN event_type = 'conversion' THEN 1 END) AS conversions,
        SUM(CASE WHEN event_type = 'impression' THEN bid_price ELSE 0 END) AS cost
    FROM {GLUE_DATABASE}.{GLUE_TABLE}
    WHERE CAST(from_unixtime(timestamp / 1000) AS date)
          BETWEEN CAST('{start_date}' AS date) AND CAST('{end_date}' AS date)
    GROUP BY CAST(from_unixtime(timestamp / 1000) AS date)
    ORDER BY date
    """
    return execute_query(sql)


def query_kpi_summary(start_date: str, end_date: str) -> pd.DataFrame:
    """CTR, CVR, ROAS 등 KPI를 계산합니다.

    Args:
        start_date: 시작 날짜 (YYYY-MM-DD)
        end_date: 종료 날짜 (YYYY-MM-DD)

    Returns:
        KPI 요약 DataFrame (impressions, clicks, conversions, cost, ctr, cvr, roas)
    """
    sql: str = f"""
    SELECT
        COUNT(CASE WHEN event_type = 'impression' THEN 1 END) AS impressions,
        COUNT(CASE WHEN event_type = 'click' THEN 1 END) AS clicks,
        COUNT(CASE WHEN event_type = 'conversion' THEN 1 END) AS conversions,
        SUM(CASE WHEN event_type = 'impression' THEN bid_price ELSE 0 END) AS cost,
        ROUND(
            CAST(COUNT(CASE WHEN event_type = 'click' THEN 1 END) AS DOUBLE)
            / NULLIF(COUNT(CASE WHEN event_type = 'impression' THEN 1 END), 0) * 100,
            2
        ) AS ctr,
        ROUND(
            CAST(COUNT(CASE WHEN event_type = 'conversion' THEN 1 END) AS DOUBLE)
            / NULLIF(COUNT(CASE WHEN event_type = 'click' THEN 1 END), 0) * 100,
            2
        ) AS cvr
    FROM {GLUE_DATABASE}.{GLUE_TABLE}
    WHERE CAST(from_unixtime(timestamp / 1000) AS date)
          BETWEEN CAST('{start_date}' AS date) AND CAST('{end_date}' AS date)
    """
    return execute_query(sql)


def query_category_performance(start_date: str, end_date: str) -> pd.DataFrame:
    """카테고리별 성과를 분석합니다.

    Args:
        start_date: 시작 날짜 (YYYY-MM-DD)
        end_date: 종료 날짜 (YYYY-MM-DD)

    Returns:
        카테고리별 성과 DataFrame
    """
    sql: str = f"""
    SELECT
        campaign_id,
        COUNT(CASE WHEN event_type = 'impression' THEN 1 END) AS impressions,
        COUNT(CASE WHEN event_type = 'click' THEN 1 END) AS clicks,
        COUNT(CASE WHEN event_type = 'conversion' THEN 1 END) AS conversions,
        SUM(CASE WHEN event_type = 'impression' THEN bid_price ELSE 0 END) AS cost,
        ROUND(
            CAST(COUNT(CASE WHEN event_type = 'click' THEN 1 END) AS DOUBLE)
            / NULLIF(COUNT(CASE WHEN event_type = 'impression' THEN 1 END), 0) * 100,
            2
        ) AS ctr
    FROM {GLUE_DATABASE}.{GLUE_TABLE}
    WHERE CAST(from_unixtime(timestamp / 1000) AS date)
          BETWEEN CAST('{start_date}' AS date) AND CAST('{end_date}' AS date)
    GROUP BY campaign_id
    ORDER BY impressions DESC
    """
    return execute_query(sql)


def query_shop_performance(start_date: str, end_date: str) -> pd.DataFrame:
    """shop별 성과를 분석합니다.

    Args:
        start_date: 시작 날짜 (YYYY-MM-DD)
        end_date: 종료 날짜 (YYYY-MM-DD)

    Returns:
        shop별 성과 DataFrame
    """
    sql: str = f"""
    SELECT
        user_id,
        COUNT(CASE WHEN event_type = 'impression' THEN 1 END) AS impressions,
        COUNT(CASE WHEN event_type = 'click' THEN 1 END) AS clicks,
        COUNT(CASE WHEN event_type = 'conversion' THEN 1 END) AS conversions,
        SUM(CASE WHEN event_type = 'impression' THEN bid_price ELSE 0 END) AS cost,
        ROUND(
            CAST(COUNT(CASE WHEN event_type = 'click' THEN 1 END) AS DOUBLE)
            / NULLIF(COUNT(CASE WHEN event_type = 'impression' THEN 1 END), 0) * 100,
            2
        ) AS ctr
    FROM {GLUE_DATABASE}.{GLUE_TABLE}
    WHERE CAST(from_unixtime(timestamp / 1000) AS date)
          BETWEEN CAST('{start_date}' AS date) AND CAST('{end_date}' AS date)
    GROUP BY user_id
    ORDER BY impressions DESC
    """
    return execute_query(sql)

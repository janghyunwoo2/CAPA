"""AWS Athena 쿼리 클라이언트 모듈.

문서 스펙에 맞는 일간/주간/월간 보고서 데이터를 Athena에서 조회합니다.
Glue 테이블: capa_ad_logs.ad_combined_log_summary

구조:
- get_daily_kpi(start_date, end_date): 누적 KPI 조회
- get_weekly_list(month_start, end_date): 주차별 범위 리스트 반환
- get_monthly_kpi(year, month): 월간 KPI 조회
- get_category_performance(start_date, end_date): 카테고리별 성과
- get_shop_top5(start_date, end_date): Top 10 상점
- get_shop_bottom5(start_date, end_date): Bottom 10 상점 (ROAS 기준)
- get_funnel_data(start_date, end_date): 전환 퍼널 데이터
"""

import os
import time
import logging
# import calendar  # 미사용 (비교 쿼리 제거 후 불필요)
from datetime import datetime, timedelta
from typing import Any

import boto3
import pandas as pd
from dotenv import load_dotenv

load_dotenv()

logger: logging.Logger = logging.getLogger(__name__)

# Athena 설정
ATHENA_S3_OUTPUT: str = os.environ.get(
    "ATHENA_S3_OUTPUT", "s3://capa-data-lake-827913617635/athena-results/"
)
GLUE_DATABASE: str = os.environ.get("GLUE_DATABASE", "capa_ad_logs")
GLUE_TABLE: str = os.environ.get("GLUE_TABLE", "ad_combined_log_summary")

# 쿼리 폴링 설정
POLL_INTERVAL_SEC: float = 1.0
MAX_POLL_COUNT: int = 120


def _get_client() -> "boto3.client":
    """Athena boto3 클라이언트를 반환합니다."""
    return boto3.client(
        "athena",
        region_name=os.environ.get("AWS_REGION", "ap-northeast-2"),
    )


def _build_partition_filter(start_date: str, end_date: str) -> str:
    """날짜 범위에 대한 파티션 키(year/month/day) 필터 조건을 생성합니다.

    파티션 프루닝을 통해 Athena 스캔 비용을 절감합니다.
    단순 범위: 같은 월 내의 경우 간단한 조건으로 처리합니다.

    Args:
        start_date: 시작 날짜 (YYYY-MM-DD)
        end_date: 종료 날짜 (YYYY-MM-DD)

    Returns:
        WHERE 절에 추가할 파티션 조건 문자열
    """
    start = datetime.strptime(start_date, "%Y-%m-%d")
    end = datetime.strptime(end_date, "%Y-%m-%d")

    # 단일 날짜
    if start == end:
        return (
            f"year = '{start.strftime('%Y')}' "
            f"AND month = '{start.strftime('%m')}' "
            f"AND day = '{start.strftime('%d')}'"
        )

    # 같은 연월 내
    if start.year == end.year and start.month == end.month:
        return (
            f"year = '{start.strftime('%Y')}' "
            f"AND month = '{start.strftime('%m')}' "
            f"AND day BETWEEN '{start.strftime('%d')}' AND '{end.strftime('%d')}'"
        )

    # 여러 달에 걸치는 경우: impression_timestamp 기반만 사용 (범위가 넓으면 파티션 조건이 복잡해짐)
    return (
        f"(year > '{start.strftime('%Y')}' OR "
        f"(year = '{start.strftime('%Y')}' AND month > '{start.strftime('%m')}') OR "
        f"(year = '{start.strftime('%Y')}' AND month = '{start.strftime('%m')}' AND day >= '{start.strftime('%d')}')) "
        f"AND (year < '{end.strftime('%Y')}' OR "
        f"(year = '{end.strftime('%Y')}' AND month < '{end.strftime('%m')}') OR "
        f"(year = '{end.strftime('%Y')}' AND month = '{end.strftime('%m')}' AND day <= '{end.strftime('%d')}'))"
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
    """쿼리 완료까지 폴링합니다."""
    for _ in range(MAX_POLL_COUNT):
        response = client.get_query_execution(QueryExecutionId=query_id)
        state: str = response["QueryExecution"]["Status"]["State"]

        if state in ("SUCCEEDED", "FAILED", "CANCELLED"):
            logger.info(f"Athena 쿼리 완료: {query_id} -> {state}")
            return state

        time.sleep(POLL_INTERVAL_SEC)

    raise TimeoutError(f"Athena 쿼리 시간 초과 (id={query_id}, {MAX_POLL_COUNT}회 폴링)")


def _fetch_results(client: "boto3.client", query_id: str) -> pd.DataFrame:
    """Athena 쿼리 결과를 DataFrame으로 변환합니다."""
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


# ============================================================================
# 일간 섹션: Executive Summary & KPI 상세 & 일별 트렌드
# ============================================================================


def get_daily_kpi(start_date: str, end_date: str) -> dict[str, Any]:
    """일간 누적 KPI를 조회합니다.

    start_date부터 end_date까지의 누적 데이터를 반환합니다.
    월별 누적(1일부터 시작) 또는 데이터 조회에 사용됩니다.

    Args:
        start_date: 시작 날짜 (YYYY-MM-DD), 보통 월초(1일)
        end_date: 종료 날짜 (YYYY-MM-DD), 보통 전날

    Returns:
        {
            "summary": {...},  # 누적 KPI
            "daily_breakdown": [...]  # 일별 분해 테이블
        }
    """
    # 1. 누적 KPI 조회
    start = datetime.strptime(start_date, "%Y-%m-%d")
    end = datetime.strptime(end_date, "%Y-%m-%d")

    _part = _build_partition_filter(start_date, end_date)

    sql_kpi = f"""
    SELECT
        COUNT(DISTINCT impression_id) AS impressions,
        SUM(CAST(is_click AS INT)) AS clicks,
        COUNT(CASE WHEN conversion_type = 'purchase' AND is_click = TRUE THEN 1 END) AS conversions,
        SUM(COALESCE(cost_per_click, 0)) AS cost,
        SUM(CASE WHEN conversion_type = 'purchase' AND is_click = TRUE THEN conversion_value ELSE 0 END) AS revenue,
        ROUND(
            CAST(SUM(CAST(is_click AS INT)) AS DOUBLE)
            / NULLIF(COUNT(DISTINCT impression_id), 0) * 100,
            2
        ) AS ctr,
        ROUND(
            CAST(COUNT(CASE WHEN conversion_type = 'purchase' AND is_click = TRUE THEN 1 END) AS DOUBLE)
            / NULLIF(SUM(CAST(is_click AS INT)), 0) * 100,
            2
        ) AS cvr,
        ROUND(
            SUM(CAST(cost_per_click AS DOUBLE))
            / NULLIF(SUM(CAST(is_click AS INT)), 0),
            2
        ) AS cpc,
        ROUND(
            SUM(CASE WHEN conversion_type = 'purchase' AND is_click = TRUE THEN conversion_value ELSE 0 END) / NULLIF(SUM(COALESCE(cost_per_click, 0)), 0) * 100,
            2
        ) AS roas
    FROM {GLUE_DATABASE}.{GLUE_TABLE}
    WHERE {_part}
      AND CAST(CONCAT(year, '-', LPAD(month, 2, '0'), '-', LPAD(day, 2, '0')) AS date)
          BETWEEN CAST('{start_date}' AS date) AND CAST('{end_date}' AS date)
    """

    df_kpi = execute_query(sql_kpi)

    # 2. 일별 분해 조회
    sql_daily = f"""
    SELECT
        CAST(CONCAT(year, '-', LPAD(month, 2, '0'), '-', LPAD(day, 2, '0')) AS date) AS date,
        COUNT(DISTINCT impression_id) AS impressions,
        SUM(CAST(is_click AS INT)) AS clicks,
        COUNT(CASE WHEN conversion_type = 'purchase' AND is_click = TRUE THEN 1 END) AS conversions,
        SUM(CASE WHEN conversion_type = 'purchase' AND is_click = TRUE THEN conversion_value ELSE 0 END) AS revenue,
        SUM(COALESCE(cost_per_click, 0)) AS cost,
        ROUND(
            CAST(SUM(CAST(is_click AS INT)) AS DOUBLE)
            / NULLIF(COUNT(DISTINCT impression_id), 0) * 100,
            2
        ) AS ctr,
        ROUND(
            SUM(CASE WHEN conversion_type = 'purchase' AND is_click = TRUE THEN conversion_value ELSE 0 END) / NULLIF(SUM(COALESCE(cost_per_click, 0)), 0) * 100,
            2
        ) AS roas
    FROM {GLUE_DATABASE}.{GLUE_TABLE}
    WHERE {_part}
      AND CAST(CONCAT(year, '-', LPAD(month, 2, '0'), '-', LPAD(day, 2, '0')) AS date)
          BETWEEN CAST('{start_date}' AS date) AND CAST('{end_date}' AS date)
    GROUP BY CAST(CONCAT(year, '-', LPAD(month, 2, '0'), '-', LPAD(day, 2, '0')) AS date)
    ORDER BY date ASC
    """

    df_daily = execute_query(sql_daily)

    return {
        "summary": df_kpi.to_dict(orient="records")[0] if len(df_kpi) > 0 else {},
        "daily_breakdown": df_daily.to_dict(orient="records"),
    }


# ============================================================================
# 주간 섹션: 주차별 범위 생성 및 데이터 조회
# ============================================================================


def get_weekly_list(month_start: str, end_date: str) -> list[dict[str, Any]]:
    """월초부터 end_date까지의 모든 주차를 반환합니다.

    월요일 기준으로 주차를 구분하고, 월초 부분주차, 완성 주차, 월말 부분주차를 포함합니다.

    Args:
        month_start: 월의 시작 날짜 (YYYY-MM-DD), 보통 1일
        end_date: 종료 날짜 (YYYY-MM-DD)

    Returns:
        [
            {
                "start_date": "YYYY-MM-DD",
                "end_date": "YYYY-MM-DD",
                "summary": {...},
                "daily_breakdown": [...]
            },
            ...
        ]

    예시 (3월):
        - 3/1(일)~3/1(일) = 월초 부분주차
        - 3/2(월)~3/8(일) = 완성 주차
        - 3/9(월)~3/15(일) = 완성 주차
        - ...
        - 3/30(월)~3/31(화) = 월말 부분주차
    """
    start = datetime.strptime(month_start, "%Y-%m-%d")
    end = datetime.strptime(end_date, "%Y-%m-%d")

    weeks = []
    current = start

    # 월초 부분주차: 현재 날짜가 월요일이 아니면, 그 주의 월요일부터 시작
    if current.weekday() != 0:  # 월초가 월요일이 아니면
        # 현재 날짜의 월요일 찾기 (역으로 거슬러 올라감)
        week_start = current - timedelta(days=current.weekday())
        # 첫 번째 일요일 찾기
        days_until_sunday = 6 - current.weekday()
        first_sunday = current + timedelta(days=days_until_sunday)

        if first_sunday <= end:
            week_end = min(first_sunday, end)
            weeks.append(
                {
                    "start_date": week_start.strftime("%Y-%m-%d"),  # 월요일부터 시작
                    "end_date": week_end.strftime("%Y-%m-%d"),
                }
            )
            current = week_end + timedelta(days=1)

    # 완성된 주차: 월요일부터 일요일까지
    while current <= end:
        if current.weekday() != 0:  # 월요일이 아니면 스킵
            current += timedelta(days=1)
            continue

        # 이번 주의 일요일 계산
        week_end = current + timedelta(days=6)

        # end_date를 넘지 않도록
        actual_end = min(week_end, end)

        weeks.append(
            {
                "start_date": current.strftime("%Y-%m-%d"),
                "end_date": actual_end.strftime("%Y-%m-%d"),
            }
        )

        current = actual_end + timedelta(days=1)

    # 각 주차별 데이터 조회
    result = []
    for i, week in enumerate(weeks):
        week_kpi = get_daily_kpi(week["start_date"], week["end_date"])

        result.append(
            {
                "start_date": week["start_date"],
                "end_date": week["end_date"],
                "summary": week_kpi["summary"],
                "daily_breakdown": week_kpi["daily_breakdown"],
            }
        )

    return result


# ============================================================================
# 월간 섹션: 카테고리별, 상점별, 퍼널
# ============================================================================


def get_category_performance(start_date: str, end_date: str) -> list[dict[str, Any]]:
    """카테고리별 성과를 조회합니다 (매출 내림차순)."""
    # 현재 기간 데이터
    _part = _build_partition_filter(start_date, end_date)
    sql_current = f"""
    SELECT
        food_category AS category,
        COUNT(DISTINCT impression_id) AS impressions,
        SUM(CAST(is_click AS INT)) AS clicks,
        COUNT(CASE WHEN conversion_type = 'purchase' AND is_click = TRUE THEN 1 END) AS conversions,
        SUM(CASE WHEN conversion_type = 'purchase' AND is_click = TRUE THEN conversion_value ELSE 0 END) AS revenue,
        SUM(COALESCE(cost_per_click, 0)) AS cost,
        ROUND(
            CAST(SUM(CAST(is_click AS INT)) AS DOUBLE)
            / NULLIF(COUNT(DISTINCT impression_id), 0) * 100,
            2
        ) AS ctr,
        ROUND(
            CAST(COUNT(CASE WHEN conversion_type = 'purchase' AND is_click = TRUE THEN 1 END) AS DOUBLE)
            / NULLIF(SUM(CAST(is_click AS INT)), 0) * 100,
            2
        ) AS cvr,
        ROUND(
            SUM(CASE WHEN conversion_type = 'purchase' AND is_click = TRUE THEN conversion_value ELSE 0 END) / NULLIF(SUM(COALESCE(cost_per_click, 0)), 0) * 100,
            2
        ) AS roas
    FROM {GLUE_DATABASE}.{GLUE_TABLE}
    WHERE {_part}
      AND CAST(CONCAT(year, '-', LPAD(month, 2, '0'), '-', LPAD(day, 2, '0')) AS date)
          BETWEEN CAST('{start_date}' AS date) AND CAST('{end_date}' AS date)
    GROUP BY food_category
    ORDER BY revenue DESC
    """

    df_current = execute_query(sql_current)
    return df_current.to_dict(orient="records")


def get_shop_top5(start_date: str, end_date: str) -> list[dict[str, Any]]:
    """Top 5 상점을 조회합니다 (매출 기준)."""
    # 현재 기간 데이터
    _part = _build_partition_filter(start_date, end_date)
    sql_current = f"""
    SELECT
        store_id AS shop_id,
        food_category AS category,
        COUNT(DISTINCT impression_id) AS impressions,
        SUM(CAST(is_click AS INT)) AS clicks,
        COUNT(CASE WHEN conversion_type = 'purchase' AND is_click = TRUE THEN 1 END) AS conversions,
        SUM(CASE WHEN conversion_type = 'purchase' AND is_click = TRUE THEN conversion_value ELSE 0 END) AS revenue,
        ROUND(
            CAST(SUM(CAST(is_click AS INT)) AS DOUBLE)
            / NULLIF(COUNT(DISTINCT impression_id), 0) * 100,
            2
        ) AS ctr,
        ROUND(
            SUM(CASE WHEN conversion_type = 'purchase' AND is_click = TRUE THEN conversion_value ELSE 0 END) / NULLIF(SUM(COALESCE(cost_per_click, 0)), 0) * 100,
            2
        ) AS roas
    FROM {GLUE_DATABASE}.{GLUE_TABLE}
    WHERE {_part}
      AND CAST(CONCAT(year, '-', LPAD(month, 2, '0'), '-', LPAD(day, 2, '0')) AS date)
          BETWEEN CAST('{start_date}' AS date) AND CAST('{end_date}' AS date)
    GROUP BY store_id, food_category
    ORDER BY revenue DESC
    LIMIT 5
    """

    df_current = execute_query(sql_current)
    return df_current.to_dict(orient="records")


def get_shop_bottom5(start_date: str, end_date: str) -> list[dict[str, Any]]:
    """Bottom 5 상점을 조회합니다 (ROAS 기준, 최소 노출 100건)."""
    _part = _build_partition_filter(start_date, end_date)
    sql = f"""
    SELECT
        store_id AS shop_id,
        food_category AS category,
        COUNT(DISTINCT impression_id) AS impressions,
        SUM(CAST(is_click AS INT)) AS clicks,
        COUNT(CASE WHEN conversion_type = 'purchase' AND is_click = TRUE THEN 1 END) AS conversions,
        SUM(CASE WHEN conversion_type = 'purchase' AND is_click = TRUE THEN conversion_value ELSE 0 END) AS revenue,
        ROUND(
            CAST(SUM(CAST(is_click AS INT)) AS DOUBLE)
            / NULLIF(COUNT(DISTINCT impression_id), 0) * 100,
            2
        ) AS ctr,
        ROUND(
            SUM(CASE WHEN conversion_type = 'purchase' AND is_click = TRUE THEN conversion_value ELSE 0 END) / NULLIF(SUM(COALESCE(cost_per_click, 0)), 0) * 100,
            2
        ) AS roas
    FROM {GLUE_DATABASE}.{GLUE_TABLE}
    WHERE {_part}
      AND CAST(CONCAT(year, '-', LPAD(month, 2, '0'), '-', LPAD(day, 2, '0')) AS date)
          BETWEEN CAST('{start_date}' AS date) AND CAST('{end_date}' AS date)
    GROUP BY store_id, food_category
    HAVING COUNT(DISTINCT impression_id) >= 100
    ORDER BY roas ASC
    LIMIT 5
    """
    df = execute_query(sql)
    return df.to_dict(orient="records")


def get_funnel_data(start_date: str, end_date: str) -> list[dict[str, Any]]:
    """전환 퍼널 데이터를 조회합니다."""
    # 현재 기간 데이터
    _part = _build_partition_filter(start_date, end_date)
    sql_current = f"""
    SELECT
        conversion_type,
        SUM(CAST(is_conversion AS INT)) AS count
    FROM {GLUE_DATABASE}.{GLUE_TABLE}
    WHERE {_part}
      AND CAST(CONCAT(year, '-', LPAD(month, 2, '0'), '-', LPAD(day, 2, '0')) AS date)
          BETWEEN CAST('{start_date}' AS date) AND CAST('{end_date}' AS date)
    GROUP BY conversion_type
    ORDER BY conversion_type
    """

    df_current = execute_query(sql_current)
    return df_current.to_dict(orient="records")

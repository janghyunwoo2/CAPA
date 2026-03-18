"""
RedashClient — Redash API CRUD (httpx AsyncClient)
설계 문서 §2.2.2, §4.4 기준 (T2)
REDASH_ENABLED=false 시 Athena 직접 실행 폴백
"""

import asyncio
import logging
import time
from datetime import datetime
from typing import Optional, Any

import httpx

from .models.domain import QueryResults
from .models.redash import RedashConfig, RedashJobStatus

logger = logging.getLogger(__name__)

# Redash Job 상태 코드
_JOB_STATUS_PENDING = 1
_JOB_STATUS_STARTED = 2
_JOB_STATUS_SUCCESS = 3
_JOB_STATUS_FAILURE = 4
_JOB_STATUS_CANCELLED = 5


class RedashAPIError(Exception):
    """Redash API 호출 실패 예외"""
    pass


class RedashTimeoutError(RedashAPIError):
    """Redash 폴링 타임아웃 예외"""
    pass


class RedashClient:
    """Redash API 클라이언트 (httpx AsyncClient 기반)"""

    def __init__(self, config: RedashConfig) -> None:
        self._config = config
        self._base_headers = {
            "Authorization": f"Key {config.api_key}",
            "Content-Type": "application/json",
        }

    def _make_client(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(
            base_url=self._config.base_url,
            headers=self._base_headers,
            timeout=30.0,
        )

    async def create_query(self, sql: str, name: Optional[str] = None) -> int:
        """Redash에 쿼리를 생성하고 query_id를 반환.

        Args:
            sql: 실행할 SQL 문자열
            name: 쿼리 이름 (없으면 타임스탬프 기반 자동 생성)

        Returns:
            query_id (int)

        Raises:
            RedashAPIError: API 호출 실패 시
        """
        query_name = name or f"CAPA: Query [{datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')}]"
        payload = {
            "name": query_name,
            "query": sql,
            "data_source_id": self._config.data_source_id,
            "description": "CAPA Text-to-SQL 자동 생성 쿼리",
            "schedule": None,
        }

        try:
            async with self._make_client() as client:
                response = await client.post("/api/queries", json=payload)
                response.raise_for_status()
                data = response.json()
                query_id = int(data["id"])
                logger.info(f"Redash 쿼리 생성 완료: query_id={query_id}, name={query_name}")
                return query_id

        except httpx.HTTPStatusError as e:
            logger.error(f"Redash 쿼리 생성 실패 (HTTP {e.response.status_code}): {e.response.text}")
            raise RedashAPIError(f"Redash 쿼리 생성 실패: HTTP {e.response.status_code}")
        except httpx.RequestError as e:
            logger.error(f"Redash 쿼리 생성 네트워크 오류: {e}")
            raise RedashAPIError(f"Redash 연결 오류: {str(e)}")
        except (KeyError, ValueError) as e:
            logger.error(f"Redash 응답 파싱 실패: {e}")
            raise RedashAPIError(f"Redash 응답 파싱 오류: {str(e)}")

    async def execute_query(self, query_id: int) -> str:
        """쿼리를 실행하고 job_id를 반환.

        Args:
            query_id: 실행할 쿼리 ID

        Returns:
            job_id (str)

        Raises:
            RedashAPIError: API 호출 실패 시
        """
        try:
            async with self._make_client() as client:
                response = await client.post(
                    f"/api/queries/{query_id}/results",
                    json={"parameters": {}, "max_age": 0},  # BUG-4: 캐시 무효화 — 항상 신규 job 생성
                )
                response.raise_for_status()
                data = response.json()
                job_id = str(data["job"]["id"])
                logger.info(f"Redash 쿼리 실행 시작: query_id={query_id}, job_id={job_id}")
                return job_id

        except httpx.HTTPStatusError as e:
            logger.error(f"Redash 쿼리 실행 실패 (HTTP {e.response.status_code}): {e.response.text}")
            raise RedashAPIError(f"Redash 쿼리 실행 실패: HTTP {e.response.status_code}")
        except httpx.RequestError as e:
            logger.error(f"Redash 쿼리 실행 네트워크 오류: {e}")
            raise RedashAPIError(f"Redash 연결 오류: {str(e)}")
        except (KeyError, ValueError) as e:
            logger.error(f"Redash 실행 응답 파싱 실패: {e}")
            raise RedashAPIError(f"Redash 응답 파싱 오류: {str(e)}")

    async def poll_job(
        self,
        job_id: str,
        timeout: Optional[int] = None,
        interval: Optional[int] = None,
    ) -> int:
        """job이 완료될 때까지 폴링하고 query_result_id를 반환.

        Args:
            job_id: 폴링할 job ID
            timeout: 최대 대기 시간 (초, 기본값: RedashConfig.query_timeout_sec)
            interval: 폴링 간격 (초, 기본값: RedashConfig.poll_interval_sec)

        Returns:
            query_result_id (int)

        Raises:
            RedashTimeoutError: 타임아웃 시
            RedashAPIError: API 실패 또는 Job 실패 시
        """
        max_wait = timeout or self._config.query_timeout_sec
        poll_interval = interval or self._config.poll_interval_sec
        elapsed = 0

        logger.info(f"Redash job 폴링 시작: job_id={job_id}, timeout={max_wait}초")

        while elapsed < max_wait:
            try:
                status = await self._get_job_status(job_id)

                if status.status == _JOB_STATUS_SUCCESS:
                    if status.query_result_id is None:
                        raise RedashAPIError("job 성공이나 query_result_id가 없습니다")
                    logger.info(f"Redash job 완료: job_id={job_id}, result_id={status.query_result_id}")
                    return status.query_result_id

                elif status.status in (_JOB_STATUS_FAILURE, _JOB_STATUS_CANCELLED):
                    error_msg = status.error or "알 수 없는 오류"
                    logger.error(f"Redash job 실패: {error_msg}")
                    raise RedashAPIError(f"Redash 실행 실패: {error_msg}")

                # 대기 중 또는 실행 중
                await asyncio.sleep(poll_interval)
                elapsed += poll_interval

            except (RedashAPIError, RedashTimeoutError):
                raise
            except Exception as e:
                logger.error(f"Redash 폴링 중 예외: {e}")
                raise RedashAPIError(f"Redash 폴링 오류: {str(e)}")

        logger.error(f"Redash job 타임아웃: job_id={job_id}, {max_wait}초 초과")
        raise RedashTimeoutError(f"Redash 쿼리 타임아웃 ({max_wait}초 초과)")

    async def _get_job_status(self, job_id: str) -> RedashJobStatus:
        try:
            async with self._make_client() as client:
                response = await client.get(f"/api/jobs/{job_id}")
                response.raise_for_status()
                data = response.json()["job"]
                return RedashJobStatus(
                    id=str(data["id"]),
                    status=int(data["status"]),
                    error=data.get("error"),
                    query_result_id=data.get("query_result_id"),
                )
        except httpx.HTTPStatusError as e:
            raise RedashAPIError(f"job 상태 조회 실패: HTTP {e.response.status_code}")
        except httpx.RequestError as e:
            raise RedashAPIError(f"job 상태 조회 네트워크 오류: {str(e)}")

    async def get_results(self, query_id: int) -> QueryResults:
        """저장된 쿼리 결과를 가져와 QueryResults로 반환.

        Args:
            query_id: 결과를 가져올 쿼리 ID

        Returns:
            QueryResults

        Raises:
            RedashAPIError: API 호출 실패 시
        """
        try:
            async with self._make_client() as client:
                response = await client.get(f"/api/queries/{query_id}/results")
                response.raise_for_status()
                data = response.json()

            result_data = data.get("query_result", {}).get("data", {})
            columns_meta = result_data.get("columns", [])
            rows_raw = result_data.get("rows", [])

            columns = [col.get("name", col.get("friendly_name", "")) for col in columns_meta]
            rows = rows_raw if isinstance(rows_raw, list) else []

            logger.info(f"Redash 결과 수집 완료: query_id={query_id}, {len(rows)}건")
            return QueryResults(
                rows=rows,
                columns=columns,
                row_count=len(rows),
                execution_path="redash",
            )

        except httpx.HTTPStatusError as e:
            logger.error(f"Redash 결과 조회 실패 (HTTP {e.response.status_code}): {e.response.text}")
            raise RedashAPIError(f"Redash 결과 조회 실패: HTTP {e.response.status_code}")
        except httpx.RequestError as e:
            logger.error(f"Redash 결과 조회 네트워크 오류: {e}")
            raise RedashAPIError(f"Redash 연결 오류: {str(e)}")

    def build_public_url(self, query_id: int) -> str:
        """사용자 전달용 Redash 공개 URL 생성"""
        return f"{self._config.public_url}/queries/{query_id}"


# ---------------------------------------------------------------------------
# Athena 폴백 실행 (REDASH_ENABLED=false 시)
# ---------------------------------------------------------------------------

async def run_athena_fallback(
    sql: str,
    athena_client: Any,
    database: str,
    s3_staging_dir: str,
    workgroup: str,
) -> QueryResults:
    """REDASH_ENABLED=false 시 boto3 Athena 직접 실행 폴백.

    Args:
        sql: 실행할 SQL
        athena_client: boto3 Athena 클라이언트
        database: Athena 데이터베이스명
        s3_staging_dir: 결과 저장 S3 경로
        workgroup: Athena Workgroup 이름

    Returns:
        QueryResults

    Raises:
        RedashAPIError: Athena 실행 실패 시
    """
    from botocore.exceptions import ClientError

    logger.info(f"Athena 직접 실행 폴백: {sql[:100]}...")

    try:
        response = athena_client.start_query_execution(
            QueryString=sql,
            QueryExecutionContext={"Database": database},
            ResultConfiguration={"OutputLocation": s3_staging_dir},
            WorkGroup=workgroup,
        )
        query_execution_id = response["QueryExecutionId"]

    except ClientError as e:
        logger.error(f"Athena 쿼리 시작 실패: {e}")
        raise RedashAPIError(f"Athena 실행 실패: {str(e)}")

    # 완료 대기 (최대 300초)
    max_attempts = 100
    for attempt in range(max_attempts):
        try:
            execution = athena_client.get_query_execution(
                QueryExecutionId=query_execution_id
            )
            state = execution["QueryExecution"]["Status"]["State"]

            if state == "SUCCEEDED":
                break
            elif state in ("FAILED", "CANCELLED"):
                reason = execution["QueryExecution"]["Status"].get(
                    "StateChangeReason", "알 수 없는 오류"
                )
                logger.error(f"Athena 쿼리 {state}: {reason}")
                raise RedashAPIError(f"Athena 쿼리 실패: {reason}")

            await asyncio.sleep(3)

        except ClientError as e:
            logger.error(f"Athena 쿼리 상태 확인 실패: {e}")
            raise RedashAPIError(f"Athena 상태 확인 실패: {str(e)}")
    else:
        raise RedashTimeoutError("Athena 쿼리 타임아웃 (300초 초과)")

    # 결과 수집
    try:
        paginator = athena_client.get_paginator("get_query_results")
        results_iter = paginator.paginate(QueryExecutionId=query_execution_id)

        rows: list[dict] = []
        columns: list[str] = []

        for page in results_iter:
            if not columns:
                columns = [
                    col["Name"]
                    for col in page["ResultSet"]["ResultSetMetadata"]["ColumnInfo"]
                ]
            for row in page["ResultSet"]["Rows"]:
                data = [val.get("VarCharValue", None) for val in row["Data"]]
                rows.append(dict(zip(columns, data)))

        # 첫 행이 헤더와 중복되면 제거
        if rows and list(rows[0].values()) == columns:
            rows = rows[1:]

        logger.info(f"Athena 폴백 결과 수집 완료: {len(rows)}건")
        return QueryResults(
            rows=rows,
            columns=columns,
            row_count=len(rows),
            execution_path="athena_fallback",
        )

    except ClientError as e:
        logger.error(f"Athena 결과 수집 실패: {e}")
        raise RedashAPIError(f"Athena 결과 수집 실패: {str(e)}")

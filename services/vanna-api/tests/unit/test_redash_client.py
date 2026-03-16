"""
§3.11~§3.13: RedashClient 단위 테스트
Step 7 (QueryCreator), Step 8 (Executor), Step 9 (ResultCollector) 기능 검증
httpx Mock에 respx 라이브러리 사용
"""

import pytest
import respx
import httpx

from src.models.redash import RedashConfig
from src.redash_client import (
    RedashClient,
    RedashAPIError,
    RedashTimeoutError,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def redash_config() -> RedashConfig:
    """테스트용 Redash 설정"""
    return RedashConfig(
        base_url="http://redash-test:5000",
        api_key="test-api-key-12345",
        data_source_id=1,
        query_timeout_sec=10,
        poll_interval_sec=1,
        public_url="https://redash.example.com",
        enabled=True,
    )


@pytest.fixture()
def client(redash_config: RedashConfig) -> RedashClient:
    """RedashClient 인스턴스"""
    return RedashClient(config=redash_config)


# ---------------------------------------------------------------------------
# §3.11 Step 7: create_query (RedashQueryCreator)
# ---------------------------------------------------------------------------


class TestCreateQuery:
    """Step 7: Redash 쿼리 생성 테스트"""

    @pytest.mark.asyncio
    @respx.mock
    async def test_create_query_success_returns_query_id(self, client):
        """정상 쿼리 생성 → query_id 반환"""
        respx.post("http://redash-test:5000/api/queries").mock(
            return_value=httpx.Response(200, json={"id": 42, "name": "test"})
        )
        query_id = await client.create_query(sql="SELECT 1")
        assert query_id == 42

    @pytest.mark.asyncio
    @respx.mock
    async def test_create_query_with_custom_name(self, client):
        """사용자 정의 이름으로 쿼리 생성"""
        route = respx.post("http://redash-test:5000/api/queries").mock(
            return_value=httpx.Response(200, json={"id": 100})
        )
        query_id = await client.create_query(sql="SELECT 1", name="CAPA: 커스텀 쿼리")
        assert query_id == 100
        # 요청 본문에 name 포함 확인
        request_body = route.calls[0].request.content
        assert b"CAPA" in request_body

    @pytest.mark.asyncio
    @respx.mock
    async def test_create_query_http_error_raises_redash_api_error(self, client):
        """HTTP 500 응답 → RedashAPIError"""
        respx.post("http://redash-test:5000/api/queries").mock(
            return_value=httpx.Response(500, text="Internal Server Error")
        )
        with pytest.raises(RedashAPIError, match="HTTP 500"):
            await client.create_query(sql="SELECT 1")

    @pytest.mark.asyncio
    @respx.mock
    async def test_create_query_network_error_raises_redash_api_error(self, client):
        """네트워크 오류 → RedashAPIError"""
        respx.post("http://redash-test:5000/api/queries").mock(
            side_effect=httpx.ConnectError("Connection refused")
        )
        with pytest.raises(RedashAPIError, match="연결 오류"):
            await client.create_query(sql="SELECT 1")

    @pytest.mark.asyncio
    @respx.mock
    async def test_create_query_missing_id_raises_error(self, client):
        """응답에 id 필드 없음 → RedashAPIError"""
        respx.post("http://redash-test:5000/api/queries").mock(
            return_value=httpx.Response(200, json={"name": "no-id"})
        )
        with pytest.raises(RedashAPIError, match="파싱"):
            await client.create_query(sql="SELECT 1")


# ---------------------------------------------------------------------------
# §3.12 Step 8: execute_query (RedashExecutor)
# ---------------------------------------------------------------------------


class TestExecuteQuery:
    """Step 8: Redash 쿼리 실행 테스트"""

    @pytest.mark.asyncio
    @respx.mock
    async def test_execute_query_success_returns_job_id(self, client):
        """정상 실행 → job_id 반환"""
        respx.post("http://redash-test:5000/api/queries/42/results").mock(
            return_value=httpx.Response(200, json={"job": {"id": "job-abc-123"}})
        )
        job_id = await client.execute_query(query_id=42)
        assert job_id == "job-abc-123"

    @pytest.mark.asyncio
    @respx.mock
    async def test_execute_query_http_error_raises(self, client):
        """HTTP 404 → RedashAPIError"""
        respx.post("http://redash-test:5000/api/queries/999/results").mock(
            return_value=httpx.Response(404, text="Not Found")
        )
        with pytest.raises(RedashAPIError, match="HTTP 404"):
            await client.execute_query(query_id=999)

    @pytest.mark.asyncio
    @respx.mock
    async def test_execute_query_missing_job_raises(self, client):
        """응답에 job 필드 없음 → RedashAPIError"""
        respx.post("http://redash-test:5000/api/queries/42/results").mock(
            return_value=httpx.Response(200, json={"data": "no-job"})
        )
        with pytest.raises(RedashAPIError, match="파싱"):
            await client.execute_query(query_id=42)


# ---------------------------------------------------------------------------
# §3.12 Step 8: poll_job
# ---------------------------------------------------------------------------


class TestPollJob:
    """Step 8: Redash job 폴링 테스트"""

    @pytest.mark.asyncio
    @respx.mock
    async def test_poll_job_success_returns_result_id(self, client):
        """job 성공 → query_result_id 반환"""
        respx.get("http://redash-test:5000/api/jobs/job-123").mock(
            return_value=httpx.Response(200, json={
                "job": {"id": "job-123", "status": 3, "query_result_id": 777}
            })
        )
        result_id = await client.poll_job(job_id="job-123")
        assert result_id == 777

    @pytest.mark.asyncio
    @respx.mock
    async def test_poll_job_failure_raises_error(self, client):
        """job 실패 → RedashAPIError"""
        respx.get("http://redash-test:5000/api/jobs/job-fail").mock(
            return_value=httpx.Response(200, json={
                "job": {"id": "job-fail", "status": 4, "error": "Query failed"}
            })
        )
        with pytest.raises(RedashAPIError, match="실행 실패"):
            await client.poll_job(job_id="job-fail")

    @pytest.mark.asyncio
    @respx.mock
    async def test_poll_job_timeout_raises_timeout_error(self, client):
        """폴링 타임아웃 → RedashTimeoutError"""
        respx.get("http://redash-test:5000/api/jobs/job-slow").mock(
            return_value=httpx.Response(200, json={
                "job": {"id": "job-slow", "status": 2}
            })
        )
        with pytest.raises(RedashTimeoutError, match="타임아웃"):
            await client.poll_job(job_id="job-slow", timeout=1, interval=1)

    @pytest.mark.asyncio
    @respx.mock
    async def test_poll_job_cancelled_raises_error(self, client):
        """job 취소 → RedashAPIError"""
        respx.get("http://redash-test:5000/api/jobs/job-cancel").mock(
            return_value=httpx.Response(200, json={
                "job": {"id": "job-cancel", "status": 5, "error": None}
            })
        )
        with pytest.raises(RedashAPIError, match="실행 실패"):
            await client.poll_job(job_id="job-cancel")


# ---------------------------------------------------------------------------
# §3.13 Step 9: get_results (ResultCollector)
# ---------------------------------------------------------------------------


class TestGetResults:
    """Step 9: Redash 결과 수집 테스트"""

    @pytest.mark.asyncio
    @respx.mock
    async def test_get_results_success_returns_query_results(self, client):
        """정상 결과 → QueryResults 반환"""
        respx.get("http://redash-test:5000/api/queries/42/results").mock(
            return_value=httpx.Response(200, json={
                "query_result": {
                    "data": {
                        "columns": [
                            {"name": "device_type"},
                            {"name": "revenue"},
                        ],
                        "rows": [
                            {"device_type": "Android", "revenue": 50000},
                            {"device_type": "iOS", "revenue": 40000},
                        ],
                    }
                }
            })
        )
        results = await client.get_results(query_id=42)
        assert results.row_count == 2
        assert results.columns == ["device_type", "revenue"]
        assert results.rows[0]["device_type"] == "Android"
        assert results.execution_path == "redash"

    @pytest.mark.asyncio
    @respx.mock
    async def test_get_results_empty_rows_returns_zero_count(self, client):
        """빈 결과 → row_count=0"""
        respx.get("http://redash-test:5000/api/queries/42/results").mock(
            return_value=httpx.Response(200, json={
                "query_result": {
                    "data": {"columns": [{"name": "id"}], "rows": []}
                }
            })
        )
        results = await client.get_results(query_id=42)
        assert results.row_count == 0

    @pytest.mark.asyncio
    @respx.mock
    async def test_get_results_http_error_raises(self, client):
        """HTTP 오류 → RedashAPIError"""
        respx.get("http://redash-test:5000/api/queries/999/results").mock(
            return_value=httpx.Response(404, text="Not Found")
        )
        with pytest.raises(RedashAPIError, match="HTTP 404"):
            await client.get_results(query_id=999)


# ---------------------------------------------------------------------------
# build_public_url
# ---------------------------------------------------------------------------


class TestBuildPublicUrl:
    """Redash 공개 URL 생성 테스트"""

    def test_build_public_url_format(self, client):
        """query_id로 공개 URL 생성"""
        url = client.build_public_url(query_id=42)
        assert url == "https://redash.example.com/queries/42"

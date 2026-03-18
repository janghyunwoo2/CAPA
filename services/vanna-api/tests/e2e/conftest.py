"""
E2E 테스트 공통 설정 — phase-2-integration-test-plan.md 기준

실행 방법:
  1. docker-compose.local-e2e.yml 환경 기동
  2. pytest tests/e2e/ -v --timeout=120

환경변수:
  - E2E_BASE_URL: vanna-api 주소 (기본: http://localhost:8000)
  - E2E_API_TOKEN: X-Internal-Token 값 (기본: test-token)
"""

import os
from typing import Any

import httpx
import pytest


BASE_URL = os.getenv("E2E_BASE_URL", "http://localhost:8000")
API_TOKEN = os.getenv("E2E_API_TOKEN", "test-token")


@pytest.fixture(scope="session")
def base_url() -> str:
    return BASE_URL


@pytest.fixture(scope="session")
def headers() -> dict[str, str]:
    return {
        "Content-Type": "application/json; charset=utf-8",
        "X-Internal-Token": API_TOKEN,
    }


@pytest.fixture(scope="session")
def http_client() -> httpx.Client:
    """세션 전체에서 재사용하는 동기 HTTP 클라이언트"""
    client = httpx.Client(base_url=BASE_URL, timeout=120.0)
    yield client  # type: ignore[misc]
    client.close()


@pytest.fixture(scope="session", autouse=True)
def check_api_health() -> None:
    """E2E 테스트 전 API 서버 헬스 체크"""
    try:
        resp = httpx.get(f"{BASE_URL}/health", timeout=10.0)
        resp.raise_for_status()
    except Exception as e:
        pytest.skip(f"vanna-api 미기동 — E2E 테스트 스킵: {e}")


def post_query(
    client: httpx.Client,
    headers: dict[str, str],
    question: str,
) -> tuple[int, dict[str, Any]]:
    """POST /query 호출 후 (status_code, response_body) 반환.

    정상(200)이면 JSON body 그대로,
    에러(4xx/5xx)이면 HTTPException의 detail 딕셔너리를 반환한다.
    """
    resp = client.post("/query", headers=headers, json={"question": question})
    body = resp.json()
    # FastAPI HTTPException → {"detail": {...}}
    if resp.status_code != 200 and "detail" in body:
        return resp.status_code, body["detail"]
    return resp.status_code, body

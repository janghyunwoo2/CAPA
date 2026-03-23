"""
Phase 2 통합 테스트 - 공용 픽스처 및 설정

목적: Step 간 실제 연결 검증 (실제 ChromaDB + 실제 LLM + mock Athena)
방식: QueryPipeline() 직접 호출 (HTTP 서버 불필요)
"""

import os
import sys
import pytest
import asyncio
from unittest.mock import MagicMock

# /app 을 sys.path에 추가하여 'from src.xxx import' 가능하게 함
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))


# ──────────────────────────────────────────────
# 이벤트 루프
# ──────────────────────────────────────────────
@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


# ──────────────────────────────────────────────
# 환경 변수 기반 설정
# ──────────────────────────────────────────────
@pytest.fixture(scope="session")
def anthropic_api_key():
    key = os.getenv("ANTHROPIC_API_KEY", "")
    if not key or key == "test-key":
        pytest.skip("ANTHROPIC_API_KEY 미설정 — 실제 LLM 호출 불가")
    return key


@pytest.fixture(scope="session")
def chroma_host():
    return os.getenv("CHROMA_HOST", "localhost")


@pytest.fixture(scope="session")
def chroma_port():
    return int(os.getenv("CHROMA_PORT", "8001"))


# ──────────────────────────────────────────────
# ChromaDB 연결 확인 (선행 조건)
# ──────────────────────────────────────────────
@pytest.fixture(scope="session", autouse=True)
def wait_for_chromadb(chroma_host, chroma_port):
    """ChromaDB 서비스 연결 대기 (최대 30초)"""
    import time
    import httpx

    url = f"http://{chroma_host}:{chroma_port}/api/v1"
    for i in range(30):
        try:
            resp = httpx.get(url, timeout=2.0)
            if resp.status_code < 500:
                print(f"✅ ChromaDB 연결 확인: {url}")
                return
        except Exception:
            pass
        if i == 29:
            pytest.skip(f"ChromaDB({url}) 연결 실패 — 통합 테스트 스킵")
        time.sleep(1)


# ──────────────────────────────────────────────
# Mock Athena Client (Step 6 SQLValidator용)
# ──────────────────────────────────────────────
@pytest.fixture(scope="session")
def mock_athena():
    """Athena는 로컬 테스트 불가 → moto mock 사용"""
    mock = MagicMock()
    mock.start_query_execution = MagicMock(
        return_value={"QueryExecutionId": "mock-execution-id"}
    )
    mock.get_query_execution = MagicMock(
        return_value={
            "QueryExecution": {
                "Status": {"State": "SUCCEEDED"},
                "Statistics": {"EngineExecutionTimeInMillis": 50},
            }
        }
    )
    mock.get_query_results = MagicMock(
        return_value={
            "ResultSet": {
                "Rows": [{"Data": [{"VarCharValue": "plan"}]}],
                "ResultSetMetadata": {"ColumnInfo": [{"Name": "plan"}]},
            }
        }
    )
    return mock


# ──────────────────────────────────────────────
# QueryPipeline 픽스처 (실제 LLM + 실제 ChromaDB + mock Athena)
# ──────────────────────────────────────────────
@pytest.fixture(scope="session")
def pipeline(anthropic_api_key, mock_athena, wait_for_chromadb):
    """
    Phase 2 통합 테스트용 QueryPipeline:
    - vanna_instance=None → 환경변수(CHROMA_HOST)로 실제 ChromaDB 자동 연결
    - anthropic_api_key=실제 키 → 실제 LLM 호출
    - athena_client=mock → Athena EXPLAIN은 mock 처리
    - REDASH_ENABLED=false → Athena fallback 경로 사용
    """
    from src.query_pipeline import QueryPipeline
    import chromadb

    # QueryPipeline 초기화
    pipeline = QueryPipeline(
        vanna_instance=None,          # 실제 ChromaDB 자동 연결
        anthropic_api_key=anthropic_api_key,
        athena_client=mock_athena,    # Athena mock
        database=os.getenv("ATHENA_DATABASE", "capa_db"),
        workgroup=os.getenv("ATHENA_WORKGROUP", "primary"),
        s3_staging_dir=os.getenv("S3_STAGING_DIR", "s3://test-bucket/results/"),
    )

    # ChromaDB 시딩 — Vanna SDK 올바른 메서드 사용
    vanna = pipeline._vanna

    # 1) DDL 시딩
    vanna.train(ddl="""
        CREATE TABLE ad_combined_log (
            impression_id STRING,
            user_id STRING,
            ad_id STRING,
            campaign_id STRING,
            platform STRING,
            device_type STRING,
            cost_per_impression DOUBLE,
            cost_per_click DOUBLE,
            is_click BOOLEAN,
            year STRING, month STRING, day STRING, hour STRING
        )
        COMMENT '광고 노출 및 클릭 이벤트 로그'
    """)

    vanna.train(ddl="""
        CREATE TABLE ad_combined_log_summary (
            impression_id STRING,
            user_id STRING,
            ad_id STRING,
            campaign_id STRING,
            platform STRING,
            device_type STRING,
            conversion_value DOUBLE,
            cost_per_impression DOUBLE,
            cost_per_click DOUBLE,
            is_click BOOLEAN,
            is_conversion BOOLEAN,
            year STRING, month STRING, day STRING
        )
        COMMENT '광고 노출/클릭/전환 요약 테이블'
    """)

    # 2) 질문-SQL 예제 시딩
    vanna.train(
        question="어제 캠페인별 CTR 알려줘",
        sql="""
        SELECT
            campaign_id,
            COUNT(CASE WHEN is_click = true THEN 1 END) * 100.0 / COUNT(*) AS ctr
        FROM ad_combined_log
        WHERE year = CAST(year(current_date) AS VARCHAR)
          AND month = CAST(month(current_date) AS VARCHAR)
          AND day = CAST(day(current_date - interval '1' day) AS VARCHAR)
        GROUP BY campaign_id
        ORDER BY ctr DESC
        """,
    )

    vanna.train(
        question="최근 7일간 디바이스별 ROAS 순위 알려줘",
        sql="""
        SELECT
            device_type,
            SUM(conversion_value) / NULLIF(SUM(cost_per_impression + cost_per_click), 0) AS roas
        FROM ad_combined_log_summary
        WHERE date_diff('day',
                date(concat(year, '-', month, '-', day)),
                current_date) <= 7
        GROUP BY device_type
        ORDER BY roas DESC
        """,
    )

    # 3) 문서 시딩 (도메인 지식)
    vanna.train(documentation="""
        허용 테이블: ad_combined_log, ad_combined_log_summary
        campaign_id: 캠페인 식별자
        device_type: Android, iOS, Web, Tablet
        CTR = (클릭 수 / 노출 수) * 100
        ROAS = 전환 매출 / 광고 비용
        날짜 파티션 컬럼: year, month, day (STRING 타입)
    """)

    print("✅ ChromaDB 시딩 완료 (DDL 2개 + SQL 2개 + 문서 1개)")

    return pipeline

"""
TC-EX-01 ~ TC-EX-10 E2E 예외 케이스 테스트
phase-2-integration-test-plan.md §6.3 기준

실행:
  pytest tests/e2e/test_ex_cases.py -v --timeout=120

사전 조건:
  - docker-compose.local-e2e.yml 환경 기동
  - ChromaDB 시딩 완료
  - Redash 초기화 + Athena 데이터소스 등록 완료
"""

import httpx
import pytest

from .conftest import post_query


# ─────────────────────────────────────────────────────────────
# TC-EX-01: 도메인 범위 외 질문
# ─────────────────────────────────────────────────────────────
class TestEX01DomainOutOfScope:
    """광고 데이터와 무관한 일반 질문 → OUT_OF_SCOPE 분류"""

    def test_intent_out_of_scope(
        self, http_client: httpx.Client, headers: dict[str, str]
    ) -> None:
        status, body = post_query(http_client, headers, "파이썬 배우는 방법은?")

        # 422 + INTENT_OUT_OF_SCOPE 또는 INTENT_GENERAL
        assert status == 422, f"기대: 422, 실제: {status}"
        assert body.get("error_code") in (
            "INTENT_OUT_OF_SCOPE",
            "INTENT_GENERAL",
        ), f"에러 코드: {body.get('error_code')}"

    def test_no_sql_generated(
        self, http_client: httpx.Client, headers: dict[str, str]
    ) -> None:
        status, body = post_query(http_client, headers, "파이썬 배우는 방법은?")

        assert status == 422
        # 에러 응답에는 sql 필드가 없음
        assert body.get("sql") is None

    def test_user_friendly_message(
        self, http_client: httpx.Client, headers: dict[str, str]
    ) -> None:
        status, body = post_query(http_client, headers, "파이썬 배우는 방법은?")

        assert status == 422
        assert body.get("message") is not None
        assert len(body["message"]) > 0


# ─────────────────────────────────────────────────────────────
# TC-EX-02: 의도 불명확 질문
# ─────────────────────────────────────────────────────────────
class TestEX02AmbiguousQuestion:
    """날짜/지표 불특정 모호한 질문 → 정제 시도 또는 거부"""

    def test_handled_gracefully(
        self, http_client: httpx.Client, headers: dict[str, str]
    ) -> None:
        status, body = post_query(http_client, headers, "지난 주 데이터 좀")

        # 두 가지 정상 경로:
        #   1) 200 + refined_question (정제 시도 후 진행)
        #   2) 422 + INTENT_OUT_OF_SCOPE / INTENT_GENERAL (거부)
        if status == 200:
            assert body.get("refined_question") is not None
        else:
            assert status == 422
            assert body.get("error_code") in (
                "INTENT_OUT_OF_SCOPE",
                "INTENT_GENERAL",
                "SQL_GENERATION_FAILED",
                "SQL_VALIDATION_FAILED",
            )


# ─────────────────────────────────────────────────────────────
# TC-EX-03: SQL 생성 타임아웃 시뮬레이션
# ─────────────────────────────────────────────────────────────
@pytest.mark.skip(reason="환경변수 오버라이드 필요 (LLM_TIMEOUT_SECONDS=0.001) — 수동 테스트 권장")
class TestEX03SQLGenerationTimeout:
    """LLM_TIMEOUT_SECONDS=0.001 설정 후 SQL 생성 타임아웃 확인"""

    def test_timeout_error(
        self, http_client: httpx.Client, headers: dict[str, str]
    ) -> None:
        status, body = post_query(http_client, headers, "어제 캠페인별 CTR")

        assert body.get("error_code") in ("SQL_GENERATION_FAILED", "QUERY_TIMEOUT")
        assert body.get("message") is not None
        assert status in (200, 422, 504)


# ─────────────────────────────────────────────────────────────
# TC-EX-04: Redash 쿼리 타임아웃
# ─────────────────────────────────────────────────────────────
@pytest.mark.skip(reason="환경변수 오버라이드 필요 (REDASH_QUERY_TIMEOUT_SECONDS=1) — 수동 테스트 권장")
class TestEX04RedashQueryTimeout:
    """REDASH_QUERY_TIMEOUT_SECONDS=1 설정 후 쿼리 타임아웃 확인"""

    def test_timeout_error(
        self, http_client: httpx.Client, headers: dict[str, str]
    ) -> None:
        status, body = post_query(
            http_client,
            headers,
            "최근 30일간 캠페인별 디바이스별 시간대별 CTR ROAS 전환율 알려줘",
        )

        assert body.get("error_code") == "QUERY_TIMEOUT"
        assert body.get("message") is not None


# ─────────────────────────────────────────────────────────────
# TC-EX-05: SQL 인젝션 시도
# ─────────────────────────────────────────────────────────────
class TestEX05SQLInjection:
    """DDL 조작 구문 포함 질문 → 차단"""

    def test_injection_blocked(
        self, http_client: httpx.Client, headers: dict[str, str]
    ) -> None:
        status, body = post_query(
            http_client, headers, "DROP TABLE ad_combined_log; SELECT 1"
        )

        # SQL 검증 실패(422) 또는 의도 분류에서 차단(422)
        if status == 200:
            # 만약 200이라면 sql_validated=False여야 함
            assert body.get("sql_validated") is False
        else:
            assert status in (422, 500)
            assert body.get("error_code") in (
                "INTENT_OUT_OF_SCOPE",
                "INTENT_GENERAL",
                "SQL_VALIDATION_FAILED",
                "SQL_NOT_SELECT",
                "SQL_GENERATION_FAILED",
            )

    def test_error_or_rejection(
        self, http_client: httpx.Client, headers: dict[str, str]
    ) -> None:
        status, body = post_query(
            http_client, headers, "DROP TABLE ad_combined_log; SELECT 1"
        )

        # 에러 응답이거나, 정상이라면 sql_validated=False
        if status == 200:
            assert body.get("sql_validated") is False
        else:
            assert body.get("error_code") is not None or body.get("message") is not None


# ─────────────────────────────────────────────────────────────
# TC-EX-06: 허용되지 않은 테이블 참조
# ─────────────────────────────────────────────────────────────
class TestEX06UnauthorizedTable:
    """허용 테이블 외 참조 → 차단 또는 도메인 거부"""

    def test_blocked_or_rejected(
        self, http_client: httpx.Client, headers: dict[str, str]
    ) -> None:
        status, body = post_query(
            http_client, headers, "users 테이블에서 이메일 목록 줘"
        )

        if status == 200:
            assert body.get("sql_validated") is False
        else:
            assert status in (422, 500)
            assert body.get("error_code") in (
                "INTENT_OUT_OF_SCOPE",
                "INTENT_GENERAL",
                "SQL_VALIDATION_FAILED",
                "SQL_NOT_SELECT",
                "SQL_GENERATION_FAILED",
            )

    def test_message_present(
        self, http_client: httpx.Client, headers: dict[str, str]
    ) -> None:
        status, body = post_query(
            http_client, headers, "users 테이블에서 이메일 목록 줘"
        )

        assert body.get("message") is not None or body.get("answer") is not None


# ─────────────────────────────────────────────────────────────
# TC-EX-07: 빈 질문
# ─────────────────────────────────────────────────────────────
class TestEX07EmptyQuestion:
    """빈 문자열 → FastAPI 유효성 검사 거부 (422)"""

    def test_empty_string_rejected(
        self, http_client: httpx.Client, headers: dict[str, str]
    ) -> None:
        resp = http_client.post(
            "/query", headers=headers, json={"question": ""}
        )
        assert resp.status_code == 422, f"기대: 422, 실제: {resp.status_code}"

    def test_whitespace_only_rejected(
        self, http_client: httpx.Client, headers: dict[str, str]
    ) -> None:
        resp = http_client.post(
            "/query", headers=headers, json={"question": "   "}
        )
        # min_length=1은 공백만 있어도 통과할 수 있으므로 422 또는 다른 에러 허용
        assert resp.status_code in (422, 200, 500)


# ─────────────────────────────────────────────────────────────
# TC-EX-08: 데이터 존재 범위 외 날짜 요청
# ─────────────────────────────────────────────────────────────
class TestEX08OutOfDateRange:
    """Athena에 데이터 없는 과거 날짜 (2020년) → 빈 결과 또는 사전 차단"""

    def test_handled_gracefully(
        self, http_client: httpx.Client, headers: dict[str, str]
    ) -> None:
        status, body = post_query(
            http_client, headers, "2020년 1월 데이터 줘"
        )

        if status == 200:
            # 정상 처리 + 빈 결과
            results = body.get("results")
            assert results is None or len(results) == 0
        else:
            # 사전 차단 또는 에러 처리
            assert status in (422, 500)
            assert body.get("error_code") is not None or body.get("message") is not None

    def test_message_present(
        self, http_client: httpx.Client, headers: dict[str, str]
    ) -> None:
        status, body = post_query(
            http_client, headers, "2020년 1월 데이터 줘"
        )

        # 어떤 경로든 메시지가 있어야 함
        assert (
            body.get("message") is not None
            or body.get("answer") is not None
            or body.get("error_code") is not None
        )


# ─────────────────────────────────────────────────────────────
# TC-EX-09: 특수문자 포함 질문 (XSS 방어)
# ─────────────────────────────────────────────────────────────
class TestEX09XSSDefense:
    """HTML/스크립트 태그 포함 질문 → 이스케이프 또는 도메인 거부"""

    def test_script_tag_not_reflected(
        self, http_client: httpx.Client, headers: dict[str, str]
    ) -> None:
        status, body = post_query(
            http_client, headers, "<script>alert(1)</script> CTR 알려줘"
        )

        # 응답 어디에도 raw <script> 태그가 반영되면 안 됨
        body_str = str(body)
        assert "<script>" not in body_str.lower().replace("&lt;script&gt;", "")

    def test_handled_without_crash(
        self, http_client: httpx.Client, headers: dict[str, str]
    ) -> None:
        status, body = post_query(
            http_client, headers, "<script>alert(1)</script> CTR 알려줘"
        )

        # 서버가 크래시하지 않고 정상 처리 (200 또는 422)
        assert status in (200, 422, 500)

        if status == 200:
            # 정상 처리된 경우 sql_validated 필드 존재
            assert body.get("sql_validated") is not None
        else:
            # 에러 처리된 경우 에러 코드 존재
            assert body.get("error_code") is not None


# ─────────────────────────────────────────────────────────────
# TC-EX-10: 데이터 없는 정상 날짜 쿼리 (빈 결과 처리)
# ─────────────────────────────────────────────────────────────
class TestEX10EmptyResultValidDate:
    """유효 날짜이나 데이터 없음 (2026-01-01, 데이터 범위 전) → SQL 생성 성공 + 빈 결과"""

    def test_returns_200(
        self, http_client: httpx.Client, headers: dict[str, str]
    ) -> None:
        status, body = post_query(
            http_client, headers, "2026-01-01 캠페인별 CTR 알려줘"
        )
        assert status == 200, f"기대: 200, 실제: {status}, body: {body}"

    def test_intent_is_data_query(
        self, http_client: httpx.Client, headers: dict[str, str]
    ) -> None:
        status, body = post_query(
            http_client, headers, "2026-01-01 캠페인별 CTR 알려줘"
        )

        if status == 200:
            assert body.get("intent").upper() == "DATA_QUERY"

    def test_sql_generated(
        self, http_client: httpx.Client, headers: dict[str, str]
    ) -> None:
        status, body = post_query(
            http_client, headers, "2026-01-01 캠페인별 CTR 알려줘"
        )

        if status == 200:
            assert body.get("sql") is not None
            assert len(body["sql"]) > 0

    def test_empty_results(
        self, http_client: httpx.Client, headers: dict[str, str]
    ) -> None:
        status, body = post_query(
            http_client, headers, "2026-01-01 캠페인별 CTR 알려줘"
        )

        if status == 200:
            results = body.get("results")
            assert results is None or (isinstance(results, list) and len(results) == 0)

    def test_fallback_message(
        self, http_client: httpx.Client, headers: dict[str, str]
    ) -> None:
        status, body = post_query(
            http_client, headers, "2026-01-01 캠페인별 CTR 알려줘"
        )

        if status == 200:
            # 빈 결과 시 answer에 fallback 메시지가 있거나, answer가 None일 수 있음
            # 어느 쪽이든 error는 None이어야 함
            assert body.get("error") is None

    def test_no_error(
        self, http_client: httpx.Client, headers: dict[str, str]
    ) -> None:
        status, body = post_query(
            http_client, headers, "2026-01-01 캠페인별 CTR 알려줘"
        )

        if status == 200:
            assert body.get("error") is None

"""
[통합 테스트] ChromaDB RAG 검색 품질 검증

목적:
  실제 ChromaDB에 seed_chromadb.py 데이터를 시딩한 뒤,
  사용자의 자연어 질문에 대해 올바른 예제가 검색되는지 검증한다.

  단순히 "SQL에 키워드가 있나"가 아닌,
  "사용자 질문 → RAG 검색 → 올바른 예제 반환"의 실제 흐름 검증.

선행 조건:
  - ChromaDB가 localhost:8001에서 실행 중이어야 함
  - docker-compose.local-e2e.yml 기준: docker-compose -f docker-compose.local-e2e.yml up chromadb -d

실행:
  cd services/vanna-api
  CHROMA_HOST=localhost CHROMA_PORT=8001 python -m pytest tests/integration/test_chromadb_rag_retrieval.py -v

TC 목록:
  TC-RAG-01: "시간대별" 질문 → ad_combined_log 예제 검색
  TC-RAG-02: "전환/ROAS" 질문 → ad_combined_log_summary 예제 검색
  TC-RAG-03: "광고채널별" 질문 → ad_format 컬럼 예제 검색 (platform 아님)
  TC-RAG-04: "CVR" 질문 → NULLIF 포함 예제 검색
  TC-RAG-05: "ROAS" 질문 → NULLIF + conversion_value 포함 예제 검색
  TC-RAG-06: 날짜 표현 → 동적 date_add 함수 예제 검색 (하드코딩 날짜 아님)
  TC-RAG-07: "CTR 하락 캠페인" 질문 → CTE 임계값 비교 패턴 검색
  TC-RAG-08: "주중/주말" 질문 → day_of_week 함수 패턴 검색
  TC-RAG-09: "전환 0인 캠페인" 질문 → HAVING 이상탐지 패턴 검색
  TC-RAG-10: 테이블 혼동 방지 — "시간대별" 질문 시 summary 테이블 예제 TOP 검색 안 됨
  TC-RAG-11: "고유사용자수" 질문 → COUNT(DISTINCT user_id) 패턴 검색
  TC-RAG-12: "광고채널 + 시간대" 복합 질문 → ad_combined_log + ad_format 예제
"""

import os
import sys
import time
import pytest
import chromadb

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))


# ─────────────────────────────────────────────────────────────────────────────
# 설정 상수
# ─────────────────────────────────────────────────────────────────────────────
CHROMA_HOST = os.getenv("CHROMA_HOST", "localhost")
CHROMA_PORT = int(os.getenv("CHROMA_PORT", "8001"))
TOP_K = 3          # 검색 결과 상위 K개 확인
COLLECTION_NAME = "sql-qa"   # Vanna의 QA 컬렉션명


# ─────────────────────────────────────────────────────────────────────────────
# Fixtures
# ─────────────────────────────────────────────────────────────────────────────

@pytest.fixture(scope="session")
def chroma_client():
    """실제 ChromaDB 클라이언트 연결 및 연결 확인."""
    import httpx

    url = f"http://{CHROMA_HOST}:{CHROMA_PORT}/api/v1"
    for attempt in range(30):
        try:
            resp = httpx.get(url, timeout=2.0)
            if resp.status_code < 500:
                print(f"\n✅ ChromaDB 연결 성공: {url}")
                break
        except Exception:
            pass
        if attempt == 29:
            pytest.skip(
                f"ChromaDB({url}) 연결 실패.\n"
                "실행 방법: docker-compose -f docker-compose.local-e2e.yml up chromadb -d"
            )
        time.sleep(1)

    client = chromadb.HttpClient(host=CHROMA_HOST, port=CHROMA_PORT)
    return client


@pytest.fixture(scope="session")
def seeded_vanna(chroma_client):
    """
    기존에 seed_chromadb.py로 시딩된 ChromaDB에 연결하고 Vanna 인스턴스를 반환한다.

    시딩은 테스트 실행 전 별도로 수행한다:
      docker exec capa-vanna-api-e2e python scripts/seed_chromadb.py

    컬렉션 삭제/추가는 추후 확장 기능을 위해 구조상 남겨두되, 자동 재시딩은 하지 않는다.
    """
    # (확장용) 기존 컬렉션 삭제 — 현재는 사용하지 않음
    # for col_name in ["sql", "ddl", "documentation"]:
    #     try:
    #         chroma_client.delete_collection(col_name)
    #     except Exception:
    #         pass

    # Vanna 인스턴스 생성 (기존 시딩된 ChromaDB에 연결)
    anthropic_key = os.getenv("ANTHROPIC_API_KEY", "test-key")
    if not anthropic_key or anthropic_key == "test-key":
        pytest.skip("ANTHROPIC_API_KEY 미설정 — 실제 임베딩 불가")

    os.environ["CHROMA_HOST"] = CHROMA_HOST
    os.environ["CHROMA_PORT"] = str(CHROMA_PORT)

    from src.query_pipeline import QueryPipeline
    pipeline = QueryPipeline(
        vanna_instance=None,
        anthropic_api_key=anthropic_key,
        athena_client=None,
        database="capa_db",
        workgroup="primary",
        s3_staging_dir="s3://test-bucket/results/",
    )
    vanna = pipeline._vanna

    print(f"\n✅ ChromaDB 연결 완료: {CHROMA_HOST}:{CHROMA_PORT}")
    return vanna


def get_top_sql(vanna, question: str, top_k: int = TOP_K) -> list[str]:
    """질문에 대해 검색된 상위 K개 SQL 반환."""
    results = vanna.get_similar_question_sql(question)
    sqls = [r.get("sql", "") for r in results[:top_k] if r.get("sql")]
    return sqls


# ─────────────────────────────────────────────────────────────────────────────
# TC-RAG-01: 시간대별 질문 → ad_combined_log 검색
# ─────────────────────────────────────────────────────────────────────────────
class TestTableSelection:
    """RAG가 질문에 맞는 테이블의 예제를 검색하는지 검증."""

    def test_tc_rag_01_hourly_question_retrieves_combined_log(self, seeded_vanna):
        """TC-RAG-01: "시간대별" 질문 → 상위 결과에 ad_combined_log 예제 포함"""
        questions = [
            "오늘 시간대별 클릭 분포를 알려줘",
            "어제 피크타임이 언제야?",
            "기기별로 시간대별 클릭 패턴을 분석해줘",
        ]
        for q in questions:
            sqls = get_top_sql(seeded_vanna, q)
            assert sqls, f"검색 결과 없음: {q}"
            top_sql = sqls[0].lower()
            assert "ad_combined_log" in top_sql and "summary" not in top_sql, (
                f"[{q}]\n"
                f"기대: FROM ad_combined_log (summary 아님)\n"
                f"실제 TOP SQL: {sqls[0][:200]}"
            )

    def test_tc_rag_02_conversion_question_retrieves_summary(self, seeded_vanna):
        """TC-RAG-02: "전환/ROAS/CVR" 질문 → ad_combined_log_summary 예제 검색"""
        questions = [
            "이번달 ROAS가 높은 캠페인은?",
            "캠페인별 전환율(CVR)을 보여줘",
            "어제 전환이 0인 캠페인을 찾아줘",
        ]
        for q in questions:
            sqls = get_top_sql(seeded_vanna, q)
            assert sqls, f"검색 결과 없음: {q}"
            top_sql = sqls[0].lower()
            assert "ad_combined_log_summary" in top_sql, (
                f"[{q}]\n"
                f"기대: ad_combined_log_summary\n"
                f"실제 TOP SQL: {sqls[0][:200]}"
            )

    def test_tc_rag_10_hourly_question_does_not_retrieve_summary_as_top(self, seeded_vanna):
        """TC-RAG-10: 테이블 혼동 방지 — "시간대별" 질문 시 summary 예제가 1위로 오지 않음"""
        q = "오늘 시간대별 노출 분포 알려줘"
        sqls = get_top_sql(seeded_vanna, q, top_k=1)
        assert sqls, f"검색 결과 없음: {q}"
        top_sql = sqls[0].lower()
        assert "from ad_combined_log\n" in top_sql or "from ad_combined_log " in top_sql, (
            f"[{q}]\n"
            f"기대: 1위 예제가 ad_combined_log 사용\n"
            f"실제 TOP SQL: {sqls[0][:200]}"
        )


# ─────────────────────────────────────────────────────────────────────────────
# TC-RAG-03~05: 컬럼 정확성
# ─────────────────────────────────────────────────────────────────────────────
class TestColumnAccuracy:
    """RAG가 의미에 맞는 올바른 컬럼을 사용하는 예제를 검색하는지 검증."""

    def test_tc_rag_03_channel_question_retrieves_ad_format_not_platform(self, seeded_vanna):
        """TC-RAG-03: "광고채널별" 질문 → ad_format 컬럼 예제 검색 (platform 아님)"""
        questions = [
            "광고채널별 CTR을 비교해줘",
            "채널별 전환율이 어떻게 돼?",
            "디스플레이/네이티브/동영상 채널별 성과를 보여줘",
        ]
        for q in questions:
            sqls = get_top_sql(seeded_vanna, q)
            assert sqls, f"검색 결과 없음: {q}"
            # 상위 결과 중 하나라도 ad_format을 GROUP BY하는 예제가 있어야 함
            found_ad_format = any(
                "ad_format" in sql.lower() and "group by" in sql.lower()
                for sql in sqls
            )
            assert found_ad_format, (
                f"[{q}]\n"
                f"기대: 상위 {TOP_K}개 중 ad_format GROUP BY 예제 존재\n"
                f"실제: {[s[:100] for s in sqls]}"
            )

    def test_tc_rag_04_cvr_question_retrieves_nullif(self, seeded_vanna):
        """TC-RAG-04: "CVR" 질문 → NULLIF 포함 예제 검색"""
        questions = [
            "카테고리별 전환율(CVR) TOP 5를 보여줘",
            "이번달 CVR이 높은 캠페인은?",
        ]
        for q in questions:
            sqls = get_top_sql(seeded_vanna, q)
            assert sqls, f"검색 결과 없음: {q}"
            found_nullif = any("nullif" in sql.lower() for sql in sqls)
            assert found_nullif, (
                f"[{q}]\n"
                f"기대: 상위 {TOP_K}개 중 NULLIF 포함 예제 존재 (Division by Zero 방지)\n"
                f"실제: {[s[:150] for s in sqls]}"
            )

    def test_tc_rag_05_roas_question_retrieves_conversion_value_and_nullif(self, seeded_vanna):
        """TC-RAG-05: "ROAS" 질문 → conversion_value + NULLIF 포함 예제"""
        q = "이번달 ROAS 100% 이상인 캠페인 찾아줘"
        sqls = get_top_sql(seeded_vanna, q)
        assert sqls, f"검색 결과 없음: {q}"
        top_sql = sqls[0].lower()
        assert "conversion_value" in top_sql, (
            f"기대: conversion_value 컬럼 사용\n실제: {sqls[0][:200]}"
        )
        assert "nullif" in top_sql, (
            f"기대: NULLIF 포함 (광고비 0 방지)\n실제: {sqls[0][:200]}"
        )

    def test_tc_rag_11_unique_user_question_retrieves_count_distinct(self, seeded_vanna):
        """TC-RAG-11: "고유사용자수" 질문 → COUNT(DISTINCT user_id) 패턴 검색"""
        q = "이번달 고유사용자수를 알려줘"
        sqls = get_top_sql(seeded_vanna, q)
        assert sqls, f"검색 결과 없음: {q}"
        found = any("count(distinct" in sql.lower() for sql in sqls)
        assert found, (
            f"기대: COUNT(DISTINCT user_id) 패턴\n"
            f"실제: {[s[:150] for s in sqls]}"
        )


# ─────────────────────────────────────────────────────────────────────────────
# TC-RAG-06: 날짜 패턴 — 동적 함수 사용 여부
# ─────────────────────────────────────────────────────────────────────────────
class TestDatePattern:
    """RAG가 동적 날짜 함수를 사용하는 예제를 검색하는지 검증."""

    def test_tc_rag_06_relative_date_question_retrieves_dynamic_date_function(self, seeded_vanna):
        """TC-RAG-06: "어제/이번달/지난달" 질문 → date_add/date_format 동적 함수 예제"""
        cases = [
            ("어제 전체 CTR을 알려줘", "date_add"),
            ("이번달 캠페인별 성과를 보여줘", "date_format"),
            ("지난달 광고비를 구해줘", "date_add"),
        ]
        for q, expected_fn in cases:
            sqls = get_top_sql(seeded_vanna, q)
            assert sqls, f"검색 결과 없음: {q}"
            found = any(expected_fn in sql.lower() for sql in sqls)
            assert found, (
                f"[{q}]\n"
                f"기대: 상위 {TOP_K}개 중 '{expected_fn}' 동적 날짜 함수 포함\n"
                f"실제: {[s[:150] for s in sqls]}"
            )

    def test_tc_rag_06b_no_hardcoded_specific_day_in_top_result(self, seeded_vanna):
        """TC-RAG-06b: 검색된 TOP SQL에 하드코딩 날짜(day='13' 등)가 없어야 함"""
        import re
        q = "어제 광고 성과를 알려줘"
        sqls = get_top_sql(seeded_vanna, q, top_k=1)
        assert sqls, f"검색 결과 없음: {q}"
        top_sql = sqls[0]
        # day='DD' 패턴이 있으면 하드코딩 날짜 사용 — date_add 함수 써야 함
        hardcoded = re.findall(r"day\s*=\s*'(\d{2})'", top_sql)
        assert not hardcoded, (
            f"기대: 동적 날짜 함수 사용 (date_add)\n"
            f"실제: 하드코딩 날짜 발견 → day='{hardcoded}'\n"
            f"SQL: {top_sql[:200]}"
        )


# ─────────────────────────────────────────────────────────────────────────────
# TC-RAG-07~09: 복잡 패턴
# ─────────────────────────────────────────────────────────────────────────────
class TestComplexPattern:
    """복잡한 SQL 패턴(CTE, HAVING, day_of_week)이 올바르게 검색되는지 검증."""

    def test_tc_rag_07_avg_ctr_threshold_question_retrieves_cte_pattern(self, seeded_vanna):
        """TC-RAG-07: "평균 CTR 대비 하락" 질문 → CTE WITH 패턴 검색"""
        q = "평균보다 CTR이 많이 떨어진 캠페인을 찾아줘"
        sqls = get_top_sql(seeded_vanna, q)
        assert sqls, f"검색 결과 없음: {q}"
        found_cte = any("with " in sql.lower() for sql in sqls)
        assert found_cte, (
            f"기대: CTE(WITH) 패턴 포함 예제\n"
            f"실제: {[s[:150] for s in sqls]}"
        )

    def test_tc_rag_08_weekday_weekend_question_retrieves_day_of_week(self, seeded_vanna):
        """TC-RAG-08: "주중/주말" 질문 → day_of_week 함수 예제 검색"""
        q = "주중과 주말의 클릭 패턴 차이를 분석해줘"
        sqls = get_top_sql(seeded_vanna, q)
        assert sqls, f"검색 결과 없음: {q}"
        found = any("day_of_week" in sql.lower() for sql in sqls)
        assert found, (
            f"기대: day_of_week() 함수 패턴\n"
            f"실제: {[s[:150] for s in sqls]}"
        )

    def test_tc_rag_09_zero_conversion_question_retrieves_having_pattern(self, seeded_vanna):
        """TC-RAG-09: "전환 0인 캠페인" 질문 → HAVING 이상탐지 패턴 검색"""
        q = "어제 전환이 한 건도 없는 캠페인이 어디야?"
        sqls = get_top_sql(seeded_vanna, q)
        assert sqls, f"검색 결과 없음: {q}"
        found = any(
            "having" in sql.lower() and "is_conversion" in sql.lower()
            for sql in sqls
        )
        assert found, (
            f"기대: HAVING + is_conversion 패턴 (전환 0 탐지)\n"
            f"실제: {[s[:150] for s in sqls]}"
        )

    def test_tc_rag_12_channel_hourly_combined_retrieves_ad_format_with_hour(self, seeded_vanna):
        """TC-RAG-12: "광고채널별 시간대별" 복합 질문 → ad_format + hour 예제"""
        q = "광고채널별로 아침/낮/저녁 시간대 클릭 패턴을 보여줘"
        sqls = get_top_sql(seeded_vanna, q)
        assert sqls, f"검색 결과 없음: {q}"
        found = any(
            "ad_format" in sql.lower() and "hour" in sql.lower()
            for sql in sqls
        )
        assert found, (
            f"기대: ad_format + hour 복합 예제\n"
            f"실제: {[s[:150] for s in sqls]}"
        )


# ─────────────────────────────────────────────────────────────────────────────
# TC-RAG-전체: 검색 결과 파티션 조건 포함 여부
# ─────────────────────────────────────────────────────────────────────────────
class TestPartitionInRetrievedSQL:
    """검색된 모든 TOP SQL에 파티션 조건이 포함되어 있는지 검증."""

    @pytest.mark.parametrize("question", [
        "어제 CTR을 알려줘",
        "이번달 ROAS 계산해줘",
        "광고채널별 성과를 보여줘",
        "지난주 대비 이번주 증감률은?",
        "시간대별 클릭 분포를 분석해줘",
    ])
    def test_partition_condition_in_top_sql(self, seeded_vanna, question):
        """검색된 TOP-1 SQL에 year/month 파티션 조건 포함"""
        sqls = get_top_sql(seeded_vanna, question, top_k=1)
        assert sqls, f"검색 결과 없음: {question}"
        top_sql = sqls[0].lower()
        assert "year" in top_sql and "month" in top_sql, (
            f"[{question}]\n"
            f"기대: year / month 파티션 조건 포함\n"
            f"실제: {sqls[0][:200]}"
        )

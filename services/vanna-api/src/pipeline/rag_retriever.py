"""
Step 4: RAGRetriever — ChromaDB 벡터 검색 (Phase 1) + Dynamic DDL Injection (Phase 2)
설계 문서 13_pipeline-rag-optimization §3 기준
Phase 1 retrieve() 하위 호환 유지, PHASE2_RAG_ENABLED=true 시 retrieve_v2() 사용
retrieve_v2: QA metadata 역추적 DDL 주입, Reranker/LLM필터 제거
실패 시 빈 RAGContext 반환 → LLM 자체 지식으로 SQL 생성
"""

import ast as _ast
import json
import logging
import os
from typing import Any, Optional

from ..models.domain import RAGContext
# from ..models.rag import CandidateDocument, SchemaHint  # Phase 2 이후 미사용 — 주석처리

logger = logging.getLogger(__name__)

# 제거: Reranker/LLM필터 환경변수 (Design §3.1 — retrieve_v2 단순화)
# RERANKER_TOP_K: int = int(os.getenv("RERANKER_TOP_K", "7"))
# RERANKER_TOP_K_DEFINITIVE: int = int(os.getenv("RERANKER_TOP_K_DEFINITIVE", "5"))
# LLM_FILTER_ENABLED: bool = os.getenv("LLM_FILTER_ENABLED", "false").lower() == "true"

# DDL 단일 소스 — QA metadata 역추적으로 직접 주입 (Design §3.2 FR-PRO-03)
_TABLE_DDL: dict[str, str] = {
    "ad_combined_log": """CREATE EXTERNAL TABLE ad_combined_log (
    -- Impression 관련 컬럼
    impression_id STRING,            -- 노출 이벤트 고유 ID (UUID 형식)
    user_id STRING,                   -- 광고를 본 사용자 ID (user_000001~user_100000)
    ad_id STRING,                     -- 광고 소재 ID (ad_0001~ad_1000)
    campaign_id STRING,               -- 캠페인 ID (campaign_01~campaign_05)
    advertiser_id STRING,             -- 광고주 ID (advertiser_01~advertiser_30)
    platform STRING,                  -- 노출 플랫폼 (web|app_ios|app_android|tablet_ios|tablet_android)
    device_type STRING,               -- 기기 유형 (mobile|tablet|desktop|others)
    os STRING,                        -- 운영체제 (ios|android|macos|windows)
    delivery_region STRING,           -- 배달 지역 (강남구|서초구 등 서울 25개 자치구)
    user_lat DOUBLE,                  -- 사용자 위도 (서울 범위: 37.4~37.7)
    user_long DOUBLE,                 -- 사용자 경도 (서울 범위: 126.8~127.1)
    store_id STRING,                  -- 매장 ID (store_0001~store_5000)
    food_category STRING,             -- 음식 카테고리 (chicken|pizza|korean|chinese|dessert 외 10개)
    ad_position STRING,               -- 광고 위치 (home_top_rolling|list_top_fixed|search_ai_recommend|checkout_bottom)
    ad_format STRING,                 -- 광고 포맷 (display|native|video|discount_coupon)
    user_agent STRING,                -- 브라우저/앱 User-Agent 문자열
    ip_address STRING,                -- 사용자 IP 주소
    session_id STRING,                -- 세션 ID
    keyword STRING,                   -- 검색 키워드 (검색 연동 광고용)
    cost_per_impression DOUBLE,       -- 노출 1회당 광고비 (0.005~0.10)
    impression_timestamp BIGINT,      -- 노출 발생 시각 (Unix timestamp, from_unixtime()로 변환)
    -- Click 관련 컬럼
    click_id STRING,                  -- 클릭 이벤트 ID (클릭 미발생 시 NULL)
    click_position_x INT,             -- 클릭 X 좌표 (픽셀)
    click_position_y INT,             -- 클릭 Y 좌표 (픽셀)
    landing_page_url STRING,          -- 클릭 후 이동한 랜딩 페이지 URL
    cost_per_click DOUBLE,            -- 클릭 1회당 광고비 (0.1~5.0)
    click_timestamp BIGINT,           -- 클릭 발생 시각 (Unix timestamp)
    -- Flag
    is_click BOOLEAN,                 -- 클릭 발생 여부 (true=클릭, false=노출만, CTR 계산 필수)
    -- Partition 컬럼 (WHERE 절 누락 시 풀스캔 — 반드시 포함)
    year STRING,                      -- 파티션: 연도 (예: '2026')
    month STRING,                     -- 파티션: 월 (예: '03')
    day STRING,                       -- 파티션: 일 (예: '25')
    hour STRING                       -- 파티션: 시간 (예: '09') — ad_combined_log 전용
)
PARTITIONED BY (year STRING, month STRING, day STRING, hour STRING)
STORED AS PARQUET
COMMENT '광고 노출 및 클릭 이벤트 (시간 단위 로그)'""",
    "ad_combined_log_summary": """CREATE EXTERNAL TABLE ad_combined_log_summary (
    -- Impression/Click 컬럼 (ad_combined_log와 동일)
    impression_id STRING,            -- 노출 이벤트 고유 ID
    user_id STRING,                   -- 사용자 ID
    ad_id STRING,                     -- 광고 소재 ID
    campaign_id STRING,               -- 캠페인 ID
    advertiser_id STRING,             -- 광고주 ID
    platform STRING,                  -- 노출 플랫폼
    device_type STRING,               -- 기기 유형 (mobile|tablet|desktop|others)
    os STRING,                        -- 운영체제
    delivery_region STRING,           -- 배달 지역
    user_lat DOUBLE,                  -- 사용자 위도
    user_long DOUBLE,                 -- 사용자 경도
    store_id STRING,                  -- 매장 ID
    food_category STRING,             -- 음식 카테고리
    ad_position STRING,               -- 광고 위치
    ad_format STRING,                 -- 광고 포맷
    user_agent STRING,                -- User-Agent
    ip_address STRING,                -- IP 주소
    session_id STRING,                -- 세션 ID
    keyword STRING,                   -- 검색 키워드
    cost_per_impression DOUBLE,       -- 노출 1회당 광고비
    impression_timestamp BIGINT,      -- 노출 시각 (Unix timestamp)
    click_id STRING,                  -- 클릭 이벤트 ID
    click_position_x INT,             -- 클릭 X 좌표
    click_position_y INT,             -- 클릭 Y 좌표
    landing_page_url STRING,          -- 랜딩 페이지 URL
    cost_per_click DOUBLE,            -- 클릭 1회당 광고비
    click_timestamp BIGINT,           -- 클릭 시각
    is_click BOOLEAN,                 -- 클릭 여부
    -- Conversion 관련 컬럼 (이 컬럼들은 ad_combined_log에 없음 — summary 전용)
    conversion_id STRING,             -- 전환 이벤트 ID (전환 미발생 시 NULL)
    conversion_type STRING,           -- 전환 유형 (purchase|signup|download|view_content|add_to_cart)
    conversion_value DOUBLE,          -- 전환 매출액 (1.0~10000.0, ROAS 계산에 사용)
    product_id STRING,                -- 전환 상품 ID (prod_00001~prod_10000)
    quantity INT,                     -- 구매 수량 (1~10)
    attribution_window STRING,        -- 전환 귀속 기간 (1day|7day|30day)
    conversion_timestamp BIGINT,      -- 전환 발생 시각 (Unix timestamp)
    -- Conversion Flag
    is_conversion BOOLEAN,            -- 전환 발생 여부 (true=전환, CVR/ROAS/CPA 계산 필수)
    -- Partition 컬럼 (hour 없음 — 일별 집계 전용, 시간대별 분석 불가)
    year STRING,                      -- 파티션: 연도
    month STRING,                     -- 파티션: 월
    day STRING                        -- 파티션: 일
)
PARTITIONED BY (year STRING, month STRING, day STRING)
STORED AS PARQUET
COMMENT '광고 성과 일일 요약 (노출+클릭+전환 데이터)'""",
}


class RAGRetriever:
    """Step 4 — ChromaDB 기반 RAG 컨텍스트 조회"""

    def __init__(
        self,
        vanna_instance: Any,
        reranker: Optional[Any] = None,
        anthropic_client: Optional[Any] = None,
    ) -> None:
        """
        Args:
            vanna_instance: 초기화된 VannaAthena 인스턴스 (ChromaDB + Anthropic)
            reranker: CrossEncoderReranker 인스턴스 (Phase 2 신규, None이면 Step 4-2 스킵)
            anthropic_client: Anthropic 클라이언트 (Phase 2 LLM 선별용, None이면 Step 4-3 스킵)
        """
        self._vanna = vanna_instance
        self._reranker = reranker
        self._anthropic = anthropic_client

    def retrieve(self, question: str, keywords: list[str]) -> RAGContext:
        """Phase 1 인터페이스 — PHASE2_RAG_ENABLED=false 시 사용 (하위 호환)"""
        search_query = question
        if keywords:
            search_query = f"{question} {' '.join(keywords)}"

        try:
            ddl_context = self._retrieve_ddl(search_query)
            doc_context = self._retrieve_documentation(search_query)
            sql_examples = self._retrieve_sql_examples(search_query)

            logger.info(
                f"RAG 검색 완료: DDL {len(ddl_context)}건, "
                f"Docs {len(doc_context)}건, "
                f"SQL 예제 {len(sql_examples)}건"
            )
            return RAGContext(
                ddl_context=ddl_context,
                documentation_context=doc_context,
                sql_examples=sql_examples,
            )

        except Exception as e:
            logger.error(f"RAG 검색 실패: {e}, 빈 컨텍스트로 진행")
            return RAGContext()

    async def retrieve_v2(
        self,
        question: str,
        keywords: list[str],
    ) -> RAGContext:
        """Phase 2 단순 RAG + Dynamic DDL Injection — PHASE2_RAG_ENABLED=true 시 사용.

        Reranker/LLM필터 제거, Phase 1 스타일 직접 구성.
        DDL은 QA metadata["tables"]에서 역추적 → _TABLE_DDL dict 직접 주입.
        설계 문서 §3.1 기준.
        """
        search_query = question
        if keywords:
            search_query = f"{question} {' '.join(keywords)}"

        try:
            # 1. QA 예제 검색 (n_results는 get_similar_question_sql 내부에서 결정)
            qa_results = self._vanna.get_similar_question_sql(question=search_query)

            # 2. DDL 역추적: QA metadata["tables"] → _TABLE_DDL dict
            tables = self._extract_tables_from_qa_results(qa_results)
            if not tables:
                tables = set(_TABLE_DDL.keys())  # fallback: 전체 주입
            ddl_context = [_TABLE_DDL[t] for t in sorted(tables) if t in _TABLE_DDL]

            # 3. SQL 예제 텍스트 추출
            sql_examples = [
                f"Q: {item['question']}\nSQL: {item['sql']}"
                for item in qa_results
                if isinstance(item, dict) and item.get("sql") and item.get("question")
            ]

            # 4. Documentation 검색
            doc_context = self._retrieve_documentation(search_query)

            logger.info(
                f"RAG 검색 완료: DDL {len(ddl_context)}건 "
                f"(tables={sorted(tables)}), "
                f"Docs {len(doc_context)}건, "
                f"SQL 예제 {len(sql_examples)}건"
            )
            return RAGContext(
                ddl_context=ddl_context,
                documentation_context=doc_context,
                sql_examples=sql_examples,
            )
        except Exception as e:
            logger.error(f"RAG 검색 실패: {e}, 빈 컨텍스트로 진행")
            return RAGContext()

    def _extract_tables_from_qa_results(self, qa_results: list) -> set[str]:
        """QA 예제 metadata["tables"] 파싱 → 테이블 이름 집합 반환.

        ChromaDB metadata 값은 str 타입 → ast.literal_eval로 list 복원.
        예: "['ad_combined_log']" → {'ad_combined_log'}
        tables metadata 없는 항목은 무시 (fallback은 호출자가 처리).
        """
        tables: set[str] = set()
        for item in qa_results:
            if not isinstance(item, dict):
                continue
            raw = item.get("tables", "")
            if not raw:
                continue
            try:
                parsed = _ast.literal_eval(raw)
                if isinstance(parsed, list):
                    tables.update(t for t in parsed if isinstance(t, str))
            except Exception:
                pass
        return tables

    # -------------------------------------------------------------------------
    # 주석처리: 3단계 RAG 전용 메서드 (Phase 2 이후 미사용 — 코드 참조용 보존)
    # Design §3.1 기준: Reranker/LLM필터/CandidateDocument 경로 비활성화
    # -------------------------------------------------------------------------

    # def _retrieve_candidates(self, query, schema_hint=None):
    #     """Step 4-1: CandidateDocument 기반 후보 수집 (3단계 RAG용)."""
    #     ...

    # def _should_skip_llm_filter(self, schema_hint):
    #     ...

    # def _retrieve_ddl_with_score(self, query):
    #     """DDL ChromaDB 벡터 검색 (Phase 2 이후 미사용)."""
    #     ...

    # def _retrieve_documentation_with_score(self, query):
    #     """Documentation ChromaDB 벡터 검색 with score."""
    #     ...

    # def _llm_filter(self, question, candidates):
    #     """Step 4-3: LLM 최종 선별 (Phase 2 이후 미사용)."""
    #     ...

    # def _candidates_to_rag_context(self, candidates):
    #     """CandidateDocument → RAGContext 변환."""
    #     ...

    def _retrieve_ddl(self, query: str) -> list[str]:
        """Phase 1 DDL 벡터 검색 — retrieve() 하위 호환 유지."""
        try:
            results = self._vanna.get_related_ddl(question=query)
            return results if isinstance(results, list) else []
        except Exception as e:
            logger.warning(f"DDL RAG 검색 실패: {e}")
            return []

    def _retrieve_documentation(self, query: str) -> list[str]:
        try:
            results = self._vanna.get_related_documentation(question=query)
            return results if isinstance(results, list) else []
        except Exception as e:
            logger.warning(f"Documentation RAG 검색 실패: {e}")
            return []

    def _retrieve_sql_examples(self, query: str) -> list[str]:
        """Phase 1 한정: SQL 텍스트만 리스트로 반환 (하위 호환 유지)."""
        return [item["text"] for item in self._retrieve_sql_examples_with_score(query)]

    def _retrieve_sql_examples_with_score(self, query: str) -> list[dict]:
        """SQL 예제를 ChromaDB distance 기반 score와 함께 반환.

        Returns:
            list of {"text": str, "score": float}
            score = 1 / (1 + distance) → 클수록 유사 (0~1)
        """
        try:
            results = self._vanna.get_similar_question_sql(question=query)
            if not isinstance(results, list):
                return []
            converted: list[dict] = []
            for item in results:
                if isinstance(item, str):
                    converted.append({"text": item, "score": 1.0})
                elif isinstance(item, dict):
                    sql = item.get("sql") or item.get("SQL") or ""
                    if sql:
                        score = item.get("score", 1.0)  # query_pipeline이 주입한 score
                        question = item.get("question", "")
                        text = f"Q: {question}\nSQL: {sql}" if question else str(sql)
                        converted.append({"text": text, "score": float(score)})
            return converted
        except Exception as e:
            logger.warning(f"SQL 예제 RAG 검색 실패: {e}")
            return []

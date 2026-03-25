"""
Step 4: RAGRetriever — ChromaDB 벡터 검색 (Phase 1) + 3단계 RAG (Phase 2)
설계 문서 §2.3.2, §3.4 기준
Phase 1 retrieve() 하위 호환 유지, PHASE2_RAG_ENABLED=true 시 retrieve_v2() 사용
실패 시 빈 RAGContext 반환 → LLM 자체 지식으로 SQL 생성
"""

import json
import logging
import os
from typing import Any, Optional

from ..models.domain import RAGContext
from ..models.rag import CandidateDocument, SchemaHint

logger = logging.getLogger(__name__)

# GAP-D-01: Config 튜닝 실험용 환경변수 (설계서 §5.1.3 / §6)
# RERANKER_TOP_K: 모호한 경우(is_definitive=False) Reranker top_k (기본값 7)
# RERANKER_TOP_K_DEFINITIVE: 확정된 경우(is_definitive=True) Reranker top_k (기본값 5)
# LLM_FILTER_ENABLED: LLM 선별 단계 전체 활성화 여부 (기본값 true)
RERANKER_TOP_K: int = int(os.getenv("RERANKER_TOP_K", "7"))
RERANKER_TOP_K_DEFINITIVE: int = int(os.getenv("RERANKER_TOP_K_DEFINITIVE", "5"))
LLM_FILTER_ENABLED: bool = os.getenv("LLM_FILTER_ENABLED", "false").lower() == "true"

# is_definitive=True 시 ChromaDB 벡터 검색 없이 직접 주입할 DDL 상수
_TABLE_DDL: dict[str, str] = {
    "ad_combined_log": """CREATE EXTERNAL TABLE ad_combined_log (
    impression_id STRING, user_id STRING, ad_id STRING,
    campaign_id STRING, advertiser_id STRING, platform STRING,
    device_type STRING, os STRING, delivery_region STRING,
    user_lat DOUBLE, user_long DOUBLE, store_id STRING,
    food_category STRING, ad_position STRING, ad_format STRING,
    user_agent STRING, ip_address STRING, session_id STRING,
    keyword STRING, cost_per_impression DOUBLE, impression_timestamp BIGINT,
    click_id STRING, click_position_x INT, click_position_y INT,
    landing_page_url STRING, cost_per_click DOUBLE, click_timestamp BIGINT,
    is_click BOOLEAN,
    year STRING, month STRING, day STRING, hour STRING
)
PARTITIONED BY (year STRING, month STRING, day STRING, hour STRING)
STORED AS PARQUET
COMMENT '광고 노출 및 클릭 이벤트 (시간 단위 로그)'""",
    "ad_combined_log_summary": """CREATE EXTERNAL TABLE ad_combined_log_summary (
    impression_id STRING, user_id STRING, ad_id STRING,
    campaign_id STRING, advertiser_id STRING, platform STRING,
    device_type STRING, os STRING, delivery_region STRING,
    user_lat DOUBLE, user_long DOUBLE, store_id STRING,
    food_category STRING, ad_position STRING, ad_format STRING,
    user_agent STRING, ip_address STRING, session_id STRING,
    keyword STRING, cost_per_impression DOUBLE, impression_timestamp BIGINT,
    click_id STRING, click_position_x INT, click_position_y INT,
    landing_page_url STRING, cost_per_click DOUBLE, click_timestamp BIGINT,
    is_click BOOLEAN,
    conversion_id STRING, conversion_type STRING, conversion_value DOUBLE,
    product_id STRING, quantity INT, attribution_window STRING,
    conversion_timestamp BIGINT, is_conversion BOOLEAN,
    year STRING, month STRING, day STRING
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
        schema_hint: Optional[SchemaHint] = None,
    ) -> RAGContext:
        """Phase 2 3단계 RAG — PHASE2_RAG_ENABLED=true 시 사용
        Step 4-1: 벡터 유사도 검색 (is_definitive=True 시 DDL 직접 주입)
        Step 4-2: Reranker (is_definitive=True 시 top_k=5)
        Step 4-3: LLM 선별 (is_definitive=True 시 스킵)
        """
        search_query = question
        if keywords:
            search_query = f"{question} {' '.join(keywords)}"

        is_definitive = schema_hint is not None and schema_hint.is_definitive

        try:
            # Step 4-1: 벡터 유사도 검색 (또는 DDL 직접 주입)
            candidates = self._retrieve_candidates(search_query, schema_hint=schema_hint)
            if not candidates:
                logger.info("RAG 3단계: 후보 문서 없음, 빈 컨텍스트 반환")
                return RAGContext()

            # Step 4-2: Reranker 재평가
            # is_definitive=True → RERANKER_TOP_K_DEFINITIVE(기본 5), 그 외 → RERANKER_TOP_K(기본 7)
            top_k = RERANKER_TOP_K_DEFINITIVE if is_definitive else RERANKER_TOP_K
            if self._reranker is not None:
                reranked = await self._reranker.rerank(
                    query=search_query, candidates=candidates, top_k=top_k
                )
            else:
                logger.warning("Reranker 미설정 — Step 4-2 스킵")
                reranked = candidates[:top_k]

            # Step 4-3: LLM 최종 선별 (is_definitive=True 또는 LLM_FILTER_ENABLED=false 시 스킵)
            if self._should_skip_llm_filter(schema_hint):
                logger.info("LLM 선별 스킵 — 컨텍스트 직접 반환")
                return self._candidates_to_rag_context(reranked)
            return self._llm_filter(question=search_query, candidates=reranked)

        except Exception as e:
            logger.error(f"RAG 3단계 검색 실패: {e}, 빈 컨텍스트로 진행")
            return RAGContext()

    def _retrieve_candidates(
        self, query: str, schema_hint: Optional[SchemaHint] = None
    ) -> list[CandidateDocument]:
        """Step 4-1: 기존 vanna 검색을 CandidateDocument 리스트로 변환.

        schema_hint.is_definitive=True 시:
          - DDL: _TABLE_DDL 상수에서 직접 주입 (벡터 검색 생략)
          - Documentation: 생략
        schema_hint.is_definitive=False 또는 None 시:
          - DDL/Documentation: 기존 벡터 검색 경로
        SQL 예제는 항상 get_similar_question_sql 기반 score 주입.
        """
        candidates: list[CandidateDocument] = []
        is_definitive = schema_hint is not None and schema_hint.is_definitive

        if is_definitive:
            # DDL 직접 주입 — ChromaDB 벡터 검색 불필요
            for table in schema_hint.tables:  # type: ignore[union-attr]
                ddl_text = _TABLE_DDL.get(table)
                if ddl_text:
                    candidates.append(
                        CandidateDocument(text=ddl_text, source="ddl", initial_score=1.0)
                    )
        else:
            # 벡터 검색 경로 — ChromaDB distance 기반 score 주입 (DEFECT-01 해결)
            for item in self._retrieve_ddl_with_score(query):
                candidates.append(
                    CandidateDocument(
                        text=item["text"], source="ddl", initial_score=item["score"]
                    )
                )
            for item in self._retrieve_documentation_with_score(query):
                candidates.append(
                    CandidateDocument(
                        text=item["text"],
                        source="documentation",
                        initial_score=item["score"],
                    )
                )

        for item in self._retrieve_sql_examples_with_score(query):
            candidates.append(
                CandidateDocument(
                    text=item["text"],
                    source="sql_example",
                    initial_score=item["score"],  # ChromaDB distance 기반 실제 점수
                )
            )
        return candidates

    def _should_skip_llm_filter(self, schema_hint: Optional[SchemaHint]) -> bool:
        """LLM 선별 스킵 여부 결정.
        - LLM_FILTER_ENABLED=false 시 항상 스킵
        - schema_hint.is_definitive=True 시 스킵
        """
        if not LLM_FILTER_ENABLED:
            return True
        return schema_hint is not None and schema_hint.is_definitive

    def _retrieve_ddl_with_score(self, query: str) -> list[dict]:
        """DDL을 ChromaDB distance 기반 score와 함께 조회.
        VannaAthena.get_related_ddl_with_score() 위임, 실패 시 score=1.0 fallback.

        Returns:
            list of {"text": str, "score": float}
        """
        try:
            results = self._vanna.get_related_ddl_with_score(question=query)
            if isinstance(results, list):
                return results
        except Exception:
            pass
        return [{"text": t, "score": 1.0} for t in self._retrieve_ddl(query)]

    def _retrieve_documentation_with_score(self, query: str) -> list[dict]:
        """Documentation을 ChromaDB distance 기반 score와 함께 조회.
        VannaAthena.get_related_documentation_with_score() 위임, 실패 시 score=1.0 fallback.

        Returns:
            list of {"text": str, "score": float}
        """
        try:
            results = self._vanna.get_related_documentation_with_score(question=query)
            if isinstance(results, list):
                return results
        except Exception:
            pass
        return [{"text": t, "score": 1.0} for t in self._retrieve_documentation(query)]

    def _llm_filter(
        self, question: str, candidates: list[CandidateDocument]
    ) -> RAGContext:
        """Step 4-3: Claude를 이용해 SQL 생성에 유용한 문서만 선별.
        실패 시 candidates 전체를 RAGContext로 변환.
        """
        if self._anthropic is None or not candidates:
            return self._candidates_to_rag_context(candidates)

        doc_list = "\n".join(
            f"[{i}] ({doc.source}) {doc.text[:300]}" for i, doc in enumerate(candidates)
        )
        prompt = (
            f"You are a SQL expert. Given the following documents and a user question, "
            f"select only the documents that are truly helpful for generating correct SQL. "
            f"0 selections are allowed if none are helpful.\n\n"
            f"User question: {question}\n\n"
            f"Documents:\n{doc_list}\n\n"
            f"Respond in JSON format only: "
            f'{{"selected_indices": [<list of int indices>], "reason": "<brief reason>"}}'
        )
        try:
            response = self._anthropic.messages.create(
                model="claude-haiku-4-5-20251001",
                max_tokens=256,
                messages=[{"role": "user", "content": prompt}],
            )
            raw = response.content[0].text.strip()
            # 마크다운 코드블록 제거 (```json ... ``` 형태 대응)
            if raw.startswith("```"):
                lines = raw.splitlines()
                raw = "\n".join(
                    line for line in lines if not line.strip().startswith("```")
                ).strip()
            parsed = json.loads(raw)
            selected_indices: list[int] = parsed.get("selected_indices", [])
            reason: str = parsed.get("reason", "")
            logger.info(
                f"LLM 선별 완료: {len(selected_indices)}건 선택, 이유: {reason[:80]}"
            )

            selected = [
                candidates[i] for i in selected_indices if 0 <= i < len(candidates)
            ]
            return self._candidates_to_rag_context(selected)

        except Exception as e:
            logger.error(f"LLM 선별 실패: {e}, candidates 전체 사용")
            return self._candidates_to_rag_context(candidates)

    def _candidates_to_rag_context(
        self, candidates: list[CandidateDocument]
    ) -> RAGContext:
        """CandidateDocument 리스트를 RAGContext로 변환"""
        ddl: list[str] = []
        docs: list[str] = []
        sqls: list[str] = []
        for doc in candidates:
            if doc.source == "ddl":
                ddl.append(doc.text)
            elif doc.source == "documentation":
                docs.append(doc.text)
            else:
                sqls.append(doc.text)
        return RAGContext(
            ddl_context=ddl,
            documentation_context=docs,
            sql_examples=sqls,
        )

    def _retrieve_ddl(self, query: str) -> list[str]:
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

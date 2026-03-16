"""
Step 4: RAGRetriever — ChromaDB 벡터 검색 (3단계 RAG)
설계 문서 §2.3.2 기준
실패 시 빈 RAGContext 반환 → LLM 자체 지식으로 SQL 생성
"""

import logging
from typing import Any
from ..models.domain import RAGContext

logger = logging.getLogger(__name__)


class RAGRetriever:
    """Step 4 — ChromaDB 기반 RAG 컨텍스트 조회"""

    def __init__(self, vanna_instance: Any) -> None:
        """
        Args:
            vanna_instance: 초기화된 VannaAthena 인스턴스 (ChromaDB + Anthropic)
        """
        self._vanna = vanna_instance

    def retrieve(self, question: str, keywords: list[str]) -> RAGContext:
        """ChromaDB에서 DDL, Documentation, SQL 예제를 검색하여 반환.
        검색 실패 시 빈 RAGContext 반환.
        """
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
        try:
            results = self._vanna.get_similar_question_sql(question=query)
            if not isinstance(results, list):
                return []
            # Vanna SDK 반환값이 dict 배열인 경우 SQL 문자열로 변환
            converted: list[str] = []
            for item in results:
                if isinstance(item, str):
                    converted.append(item)
                elif isinstance(item, dict):
                    sql = item.get("sql") or item.get("SQL") or ""
                    if sql:
                        converted.append(str(sql))
            return converted
        except Exception as e:
            logger.warning(f"SQL 예제 RAG 검색 실패: {e}")
            return []

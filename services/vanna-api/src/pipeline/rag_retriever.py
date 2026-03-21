"""
Step 4: RAGRetriever — ChromaDB 벡터 검색 (Phase 1) + 3단계 RAG (Phase 2)
설계 문서 §2.3.2, §3.4 기준
Phase 1 retrieve() 하위 호환 유지, PHASE2_RAG_ENABLED=true 시 retrieve_v2() 사용
실패 시 빈 RAGContext 반환 → LLM 자체 지식으로 SQL 생성
"""

import json
import logging
from typing import Any, Optional

from ..models.domain import RAGContext
from ..models.rag import CandidateDocument

logger = logging.getLogger(__name__)


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

    def retrieve_v2(self, question: str, keywords: list[str]) -> RAGContext:
        """Phase 2 3단계 RAG — PHASE2_RAG_ENABLED=true 시 사용
        Step 4-1: 벡터 유사도 검색 → Step 4-2: Reranker → Step 4-3: LLM 선별
        """
        search_query = question
        if keywords:
            search_query = f"{question} {' '.join(keywords)}"

        try:
            # Step 4-1: 벡터 유사도 검색
            candidates = self._retrieve_candidates(search_query)
            if not candidates:
                logger.info("RAG 3단계: 후보 문서 없음, 빈 컨텍스트 반환")
                return RAGContext()

            # Step 4-2: Reranker 재평가 (top_k=7)
            if self._reranker is not None:
                reranked = self._reranker.rerank(
                    query=search_query, candidates=candidates, top_k=7
                )
            else:
                logger.warning("Reranker 미설정 — Step 4-2 스킵")
                reranked = candidates[:7]

            # Step 4-3: LLM 최종 선별
            return self._llm_filter(question=search_query, candidates=reranked)

        except Exception as e:
            logger.error(f"RAG 3단계 검색 실패: {e}, 빈 컨텍스트로 진행")
            return RAGContext()

    def _retrieve_candidates(self, query: str) -> list[CandidateDocument]:
        """Step 4-1: 기존 vanna 검색을 CandidateDocument 리스트로 변환"""
        candidates: list[CandidateDocument] = []

        for text in self._retrieve_ddl(query):
            candidates.append(
                CandidateDocument(text=text, source="ddl", initial_score=1.0)
            )
        for text in self._retrieve_documentation(query):
            candidates.append(
                CandidateDocument(text=text, source="documentation", initial_score=1.0)
            )
        for text in self._retrieve_sql_examples(query):
            candidates.append(
                CandidateDocument(text=text, source="sql_example", initial_score=1.0)
            )
        return candidates

    def _llm_filter(
        self, question: str, candidates: list[CandidateDocument]
    ) -> RAGContext:
        """Step 4-3: Claude를 이용해 SQL 생성에 유용한 문서만 선별.
        실패 시 candidates 전체를 RAGContext로 변환.
        """
        if self._anthropic is None or not candidates:
            return self._candidates_to_rag_context(candidates)

        doc_list = "\n".join(
            f"[{i}] ({doc.source}) {doc.text[:300]}"
            for i, doc in enumerate(candidates)
        )
        prompt = (
            f"You are a SQL expert. Given the following documents and a user question, "
            f"select only the documents that are truly helpful for generating correct SQL. "
            f"0 selections are allowed if none are helpful.\n\n"
            f"User question: {question}\n\n"
            f"Documents:\n{doc_list}\n\n"
            f"Respond in JSON format only: "
            f'{{\"selected_indices\": [<list of int indices>], \"reason\": \"<brief reason>\"}}'
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
                    line for line in lines
                    if not line.strip().startswith("```")
                ).strip()
            parsed = json.loads(raw)
            selected_indices: list[int] = parsed.get("selected_indices", [])
            reason: str = parsed.get("reason", "")
            logger.info(f"LLM 선별 완료: {len(selected_indices)}건 선택, 이유: {reason[:80]}")

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
        try:
            results = self._vanna.get_similar_question_sql(question=query)
            if not isinstance(results, list):
                return []
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

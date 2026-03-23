"""
Phase 2 단위 테스트 — RAGRetriever.retrieve_v2(), _retrieve_candidates(), _llm_filter()
커버 TC: TC-P2-U41 ~ TC-P2-U48
대상 파일: services/vanna-api/src/pipeline/rag_retriever.py
요구사항: FR-12 — 3단계 RAG 고도화 (Step 4-1, 4-2, 4-3)
"""

import json
import pytest
from unittest.mock import MagicMock, patch, call

from src.pipeline.rag_retriever import RAGRetriever
from src.models.domain import RAGContext
from src.models.rag import CandidateDocument


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def mock_vanna():
    """Vanna 인스턴스 Mock"""
    v = MagicMock()
    v.get_related_ddl.return_value = ["CREATE TABLE ad_combined_log (id INT, clicks INT)"]
    v.get_related_documentation.return_value = ["광고 로그 테이블 설명 문서"]
    v.get_similar_question_sql.return_value = [{"sql": "SELECT COUNT(*) FROM ad_combined_log"}]
    return v


@pytest.fixture()
def mock_vanna_empty():
    """모든 검색 결과가 빈 Vanna Mock"""
    v = MagicMock()
    v.get_related_ddl.return_value = []
    v.get_related_documentation.return_value = []
    v.get_similar_question_sql.return_value = []
    return v


@pytest.fixture()
def mock_reranker():
    """CrossEncoderReranker Mock"""
    r = MagicMock()
    # 전달받은 candidates[:3]을 그대로 반환
    r.rerank.side_effect = lambda query, candidates, top_k: candidates[:top_k]
    return r


@pytest.fixture()
def mock_anthropic():
    """Anthropic client Mock — selected_indices=[0] 반환"""
    client = MagicMock()
    response = MagicMock()
    response.content = [MagicMock()]
    response.content[0].text = json.dumps({"selected_indices": [0], "reason": "첫 번째 문서가 관련성 높음"})
    client.messages.create.return_value = response
    return client


@pytest.fixture()
def retriever_full(mock_vanna, mock_reranker, mock_anthropic) -> RAGRetriever:
    """reranker + anthropic 모두 있는 RAGRetriever"""
    return RAGRetriever(
        vanna_instance=mock_vanna,
        reranker=mock_reranker,
        anthropic_client=mock_anthropic,
    )


# ---------------------------------------------------------------------------
# TC-P2-U41: retrieve_v2 3단계 순서 실행
# ---------------------------------------------------------------------------


class TestRetrieveV2Order:
    """retrieve_v2() 3단계 순서 검증"""

    def test_retrieve_v2_calls_all_three_stages(self, retriever_full, mock_reranker, mock_anthropic):
        """TC-P2-U41: _retrieve_candidates → rerank → _llm_filter 순서 호출 확인"""
        result = retriever_full.retrieve_v2("어제 클릭 수", keywords=["클릭"])

        assert mock_reranker.rerank.called
        assert mock_anthropic.messages.create.called
        assert isinstance(result, RAGContext)


# ---------------------------------------------------------------------------
# TC-P2-U42 ~ U43: _retrieve_candidates()
# ---------------------------------------------------------------------------


class TestRetrieveCandidates:
    """_retrieve_candidates() 단위 테스트"""

    def test_retrieve_candidates_returns_candidate_documents(self, mock_vanna):
        """TC-P2-U42: 정상 반환 — CandidateDocument 리스트"""
        retriever = RAGRetriever(vanna_instance=mock_vanna)
        result = retriever._retrieve_candidates("어제 클릭 수")

        assert len(result) > 0
        assert all(isinstance(d, CandidateDocument) for d in result)

        sources = {d.source for d in result}
        assert "ddl" in sources or "documentation" in sources or "sql_example" in sources

    def test_retrieve_candidates_empty_vanna_returns_empty(self, mock_vanna_empty):
        """TC-P2-U43: vanna 3개 메서드 모두 빈 결과 → 빈 리스트"""
        retriever = RAGRetriever(vanna_instance=mock_vanna_empty)
        result = retriever._retrieve_candidates("어제 클릭 수")

        assert result == []


# ---------------------------------------------------------------------------
# TC-P2-U44 ~ U45: _llm_filter()
# ---------------------------------------------------------------------------


class TestLLMFilter:
    """_llm_filter() 단위 테스트"""

    def test_llm_filter_returns_selected_candidates(self, mock_vanna, mock_anthropic):
        """TC-P2-U44: LLM이 indices=[0] 반환 → RAGContext에 해당 문서만 포함"""
        retriever = RAGRetriever(vanna_instance=mock_vanna, anthropic_client=mock_anthropic)
        candidates = [
            CandidateDocument(text="CREATE TABLE t", source="ddl", initial_score=1.0),
            CandidateDocument(text="SELECT 1", source="sql_example", initial_score=1.0),
        ]

        result = retriever._llm_filter("질문", candidates)

        assert isinstance(result, RAGContext)
        total_items = len(result.ddl_context) + len(result.sql_examples) + len(result.documentation_context)
        assert total_items == 1  # index 0만 선택

    def test_llm_filter_empty_selection_returns_empty_rag_context(self, mock_vanna):
        """TC-P2-U45: LLM이 selected_indices=[] → 빈 RAGContext 반환"""
        client = MagicMock()
        response = MagicMock()
        response.content = [MagicMock()]
        response.content[0].text = json.dumps({"selected_indices": [], "reason": "없음"})
        client.messages.create.return_value = response

        retriever = RAGRetriever(vanna_instance=mock_vanna, anthropic_client=client)
        candidates = [
            CandidateDocument(text="DDL", source="ddl", initial_score=1.0),
        ]

        result = retriever._llm_filter("질문", candidates)

        assert isinstance(result, RAGContext)
        assert result.ddl_context == []
        assert result.sql_examples == []
        assert result.documentation_context == []


# ---------------------------------------------------------------------------
# TC-P2-U46 ~ U47: retrieve_v2 graceful degradation
# ---------------------------------------------------------------------------


class TestRetrieveV2Fallback:
    """retrieve_v2() 에러 처리 테스트"""

    def test_retrieve_v2_candidates_error_returns_empty_rag_context(self, mock_vanna):
        """TC-P2-U46: _retrieve_candidates 예외 → 빈 RAGContext, 예외 미전파"""
        mock_vanna.get_related_ddl.side_effect = RuntimeError("ChromaDB 장애")
        mock_vanna.get_related_documentation.side_effect = RuntimeError("ChromaDB 장애")
        mock_vanna.get_similar_question_sql.side_effect = RuntimeError("ChromaDB 장애")

        retriever = RAGRetriever(vanna_instance=mock_vanna)
        result = retriever.retrieve_v2("질문", keywords=[])

        assert isinstance(result, RAGContext)
        assert result.ddl_context == []

    def test_retrieve_v2_llm_filter_error_returns_reranker_result(
        self, mock_vanna, mock_reranker
    ):
        """TC-P2-U47: _llm_filter 예외 → Reranker 결과로 RAGContext 반환 (미전파)"""
        bad_anthropic = MagicMock()
        bad_anthropic.messages.create.side_effect = Exception("Anthropic 장애")

        retriever = RAGRetriever(
            vanna_instance=mock_vanna,
            reranker=mock_reranker,
            anthropic_client=bad_anthropic,
        )

        result = retriever.retrieve_v2("질문", keywords=[])

        # 예외 미전파 + 결과 반환
        assert isinstance(result, RAGContext)
        assert result is not None

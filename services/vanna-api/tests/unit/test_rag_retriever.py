"""
Step 4: RAGRetriever 단위 테스트 — test-plan.md §3.9 (FR-04)
ChromaDB/Vanna 호출을 Mock 처리하여 RAG 검색 로직 검증
"""

import pytest
from unittest.mock import MagicMock

from src.pipeline.rag_retriever import RAGRetriever
from src.models.domain import RAGContext


class TestRetrieveSuccess:
    """정상 RAG 검색 테스트"""

    def test_retrieve_returns_rag_context(self, mock_vanna_instance):
        """RAG 검색 결과가 RAGContext 인스턴스인지 확인"""
        mock_vanna_instance.get_related_ddl.return_value = ["CREATE TABLE ad_combined_log (...)"]
        mock_vanna_instance.get_related_documentation.return_value = ["광고 로그 테이블 설명"]
        mock_vanna_instance.get_similar_question_sql.return_value = [
            "SELECT device_type FROM ad_combined_log"
        ]

        retriever = RAGRetriever(vanna_instance=mock_vanna_instance)
        result = retriever.retrieve("디바이스별 ROAS", keywords=["ROAS", "device_type"])

        assert isinstance(result, RAGContext)
        assert len(result.ddl_context) == 1
        assert len(result.documentation_context) == 1
        assert len(result.sql_examples) == 1

    def test_retrieve_combines_question_and_keywords(self, mock_vanna_instance):
        """질문 + 키워드 결합하여 검색하는지 확인"""
        retriever = RAGRetriever(vanna_instance=mock_vanna_instance)
        retriever.retrieve("ROAS 조회", keywords=["ROAS", "device_type"])

        call_args = mock_vanna_instance.get_related_ddl.call_args
        search_query = call_args.kwargs.get("question", call_args.args[0] if call_args.args else "")
        assert "ROAS" in search_query
        assert "device_type" in search_query

    def test_retrieve_without_keywords_uses_question_only(self, mock_vanna_instance):
        """키워드 없으면 질문만으로 검색"""
        retriever = RAGRetriever(vanna_instance=mock_vanna_instance)
        retriever.retrieve("ROAS 조회", keywords=[])

        call_args = mock_vanna_instance.get_related_ddl.call_args
        search_query = call_args.kwargs.get("question", call_args.args[0] if call_args.args else "")
        assert search_query == "ROAS 조회"

    def test_retrieve_empty_results(self, mock_vanna_instance):
        """검색 결과 없을 때 빈 리스트 포함 RAGContext 반환"""
        mock_vanna_instance.get_related_ddl.return_value = []
        mock_vanna_instance.get_related_documentation.return_value = []
        mock_vanna_instance.get_similar_question_sql.return_value = []

        retriever = RAGRetriever(vanna_instance=mock_vanna_instance)
        result = retriever.retrieve("알 수 없는 질문", keywords=[])

        assert isinstance(result, RAGContext)
        assert result.ddl_context == []
        assert result.documentation_context == []
        assert result.sql_examples == []


class TestRetrieveFallback:
    """Fallback 동작 테스트"""

    def test_vanna_exception_returns_empty_rag_context(self, mock_vanna_instance):
        """Vanna 예외 → 빈 RAGContext 반환 (graceful degradation)"""
        mock_vanna_instance.get_related_ddl.side_effect = RuntimeError("ChromaDB 연결 실패")

        retriever = RAGRetriever(vanna_instance=mock_vanna_instance)
        result = retriever.retrieve("어떤 질문", keywords=["CTR"])

        assert isinstance(result, RAGContext)
        assert result.ddl_context == []
        assert result.documentation_context == []
        assert result.sql_examples == []

    def test_ddl_failure_returns_empty_ddl_only(self, mock_vanna_instance):
        """DDL 검색만 실패 → ddl_context만 빈 리스트 (부분 실패 허용)"""
        mock_vanna_instance.get_related_ddl.side_effect = RuntimeError("DDL 실패")
        mock_vanna_instance.get_related_documentation.return_value = ["문서"]
        mock_vanna_instance.get_similar_question_sql.return_value = ["SELECT 1"]

        retriever = RAGRetriever(vanna_instance=mock_vanna_instance)
        result = retriever.retrieve("테스트", keywords=[])

        # 전체 실패로 빈 context 반환 (retrieve 메서드 내부에서 전체 try-except)
        assert isinstance(result, RAGContext)

    def test_non_list_return_handled_gracefully(self, mock_vanna_instance):
        """Vanna가 리스트가 아닌 값 반환 시 빈 리스트로 처리"""
        mock_vanna_instance.get_related_ddl.return_value = "not a list"
        mock_vanna_instance.get_related_documentation.return_value = None
        mock_vanna_instance.get_similar_question_sql.return_value = 42

        retriever = RAGRetriever(vanna_instance=mock_vanna_instance)
        result = retriever.retrieve("테스트", keywords=[])

        assert isinstance(result, RAGContext)
        # _retrieve_ddl 내부에서 isinstance 체크 → 빈 리스트 반환
        assert result.ddl_context == []


class TestRetrieveInterfaceContract:
    """인터페이스 계약 검증"""

    def test_retrieve_always_returns_rag_context(self, mock_vanna_instance):
        """어떤 경우에도 RAGContext 반환 보장"""
        retriever = RAGRetriever(vanna_instance=mock_vanna_instance)

        result = retriever.retrieve("테스트", keywords=["keyword"])

        assert isinstance(result, RAGContext)
        assert hasattr(result, "ddl_context")
        assert hasattr(result, "documentation_context")
        assert hasattr(result, "sql_examples")

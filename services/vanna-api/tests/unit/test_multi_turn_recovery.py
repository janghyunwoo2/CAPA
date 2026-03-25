"""
Multi-Turn Recovery 단위 테스트

TC 목록:
  TC-MR-01: QuestionRefiner llm_client 생성자 수락 확인 (api_key 방식 차단)
  TC-MR-02: QueryPipeline PHASE2=false → QuestionRefiner에 llm_client 전달
  TC-MR-03: QueryPipeline PHASE2=false → RAGRetriever.anthropic_client=None
  TC-MR-04: QueryPipeline PHASE2=true  → RAGRetriever.anthropic_client is not None
"""

import sys
import pytest
from unittest.mock import MagicMock, patch, call

from src.pipeline.question_refiner import QuestionRefiner

# QueryPipeline 임포트 가능 여부 확인 (vanna, sqlglot 등 필요)
try:
    import src.query_pipeline as qp_module
    _QP_AVAILABLE = True
except Exception:
    _QP_AVAILABLE = False

_skip_qp = pytest.mark.skipif(
    not _QP_AVAILABLE,
    reason="vanna/sqlglot 등 미설치 환경 — Docker 환경의 test_multi_turn_wiring.py에서 검증"
)


# ---------------------------------------------------------------------------
# TC-MR-01: QuestionRefiner 생성자 검증
# ---------------------------------------------------------------------------

class TestQuestionRefinerConstructor:
    """TC-MR-01: llm_client 파라미터 수락, api_key 방식 차단"""

    def test_accepts_llm_client_stores_as_client(self):
        """llm_client 파라미터로 생성 성공, _client에 저장됨"""
        mock_client = MagicMock()
        refiner = QuestionRefiner(llm_client=mock_client)
        assert refiner._client is mock_client

    def test_api_key_parameter_raises_type_error(self):
        """api_key 파라미터 전달 시 TypeError — 구 방식 완전 차단"""
        with pytest.raises(TypeError):
            QuestionRefiner(api_key="test-key")


# ---------------------------------------------------------------------------
# TC-MR-02~04: QueryPipeline 초기화 배선 검증
# ---------------------------------------------------------------------------

def _build_pipeline(phase2_enabled: bool):
    """QueryPipeline을 mock 의존성으로 초기화하는 헬퍼.

    Returns:
        (mock_qr_cls, mock_rag_cls, mock_sql_cls, mock_anthropic_instance)
    """
    mock_vanna = MagicMock()
    mock_athena = MagicMock()
    mock_anthropic_instance = MagicMock()

    with patch.object(qp_module, "PHASE2_RAG_ENABLED", phase2_enabled), \
         patch.object(qp_module, "MULTI_TURN_ENABLED", False), \
         patch.object(qp_module, "SCHEMA_MAPPER_ENABLED", False), \
         patch("anthropic.Anthropic", return_value=mock_anthropic_instance), \
         patch.object(qp_module, "IntentClassifier", MagicMock()), \
         patch.object(qp_module, "QuestionRefiner", MagicMock()) as mock_qr_cls, \
         patch.object(qp_module, "KeywordExtractor", MagicMock()), \
         patch.object(qp_module, "RAGRetriever", MagicMock()) as mock_rag_cls, \
         patch.object(qp_module, "SQLGenerator", MagicMock()) as mock_sql_cls, \
         patch.object(qp_module, "SQLValidator", MagicMock()), \
         patch.object(qp_module, "AIAnalyzer", MagicMock()), \
         patch.object(qp_module, "ChartRenderer", MagicMock()), \
         patch.object(qp_module, "ConversationHistoryRetriever", MagicMock()), \
         patch.object(qp_module, "HistoryRecorder", MagicMock()):

        qp_module.QueryPipeline(
            anthropic_api_key="test-key",
            vanna_instance=mock_vanna,
            athena_client=mock_athena,
        )

        return mock_qr_cls, mock_rag_cls, mock_sql_cls, mock_anthropic_instance


class TestQueryPipelineClientWiring:
    """TC-MR-02~04: QueryPipeline 초기화 시 anthropic_client 배선 검증

    vanna/sqlglot 등 미설치 환경에서는 skip.
    Docker 환경에서 test_multi_turn_wiring.py로 검증.
    """

    @_skip_qp
    def test_question_refiner_receives_llm_client_when_phase2_disabled(self):
        """TC-MR-02: PHASE2=false → QuestionRefiner에 llm_client 전달"""
        mock_qr_cls, _, _, mock_anthropic_instance = _build_pipeline(phase2_enabled=False)

        assert mock_qr_cls.called, "QuestionRefiner가 초기화되지 않음"
        call_kwargs = mock_qr_cls.call_args.kwargs
        assert "llm_client" in call_kwargs, "llm_client 파라미터가 전달되지 않음"
        assert call_kwargs["llm_client"] is mock_anthropic_instance

    @_skip_qp
    def test_rag_retriever_receives_none_when_phase2_disabled(self):
        """TC-MR-03: PHASE2=false → RAGRetriever.anthropic_client=None (Vanna 경로 유지)"""
        _, mock_rag_cls, _, _ = _build_pipeline(phase2_enabled=False)

        assert mock_rag_cls.called, "RAGRetriever가 초기화되지 않음"
        call_kwargs = mock_rag_cls.call_args.kwargs
        assert call_kwargs.get("anthropic_client") is None

    @_skip_qp
    def test_rag_retriever_receives_client_when_phase2_enabled(self):
        """TC-MR-04: PHASE2=true → RAGRetriever.anthropic_client is not None"""
        _, mock_rag_cls, _, mock_anthropic_instance = _build_pipeline(phase2_enabled=True)

        assert mock_rag_cls.called, "RAGRetriever가 초기화되지 않음"
        call_kwargs = mock_rag_cls.call_args.kwargs
        assert call_kwargs.get("anthropic_client") is mock_anthropic_instance

"""
Multi-Turn Wiring 단위 테스트 (TC-WI-01 ~ TC-WI-06)

TC 목록:
  TC-WI-01: QueryResponse.session_id 필드 존재 확인
  TC-WI-02: run(conversation_id=...) → ctx.session_id 설정
  TC-WI-03: MULTI_TURN_ENABLED=true → retriever.retrieve() 1회 호출
  TC-WI-04: MULTI_TURN_ENABLED=false → retriever 미호출
  TC-WI-05: run() Step 2 refine() 호출에 conversation_history 파라미터 전달
  TC-WI-06: run() Step 5 generate() 호출에 conversation_history 파라미터 전달
"""

import asyncio
from unittest.mock import MagicMock, patch

import pytest

from src.models.api import QueryResponse
from src.models.domain import ConversationTurn, IntentType, PipelineContext
from src.query_pipeline import QueryPipeline


# ---------------------------------------------------------------------------
# 헬퍼: mock 컴포넌트 주입된 파이프라인 생성
# ---------------------------------------------------------------------------

def _make_pipeline(history=None):
    """QueryPipeline.__new__()로 mock 컴포넌트 주입된 파이프라인 반환.

    Returns:
        (pipeline, mock_retriever, mock_refiner, mock_sql_gen)
    """
    pipeline = QueryPipeline.__new__(QueryPipeline)

    # Step 0: 대화 이력 retriever mock
    mock_retriever = MagicMock()

    def _retriever_side_effect(ctx):
        ctx.turn_number = 2
        if history:
            ctx.conversation_history = list(history)
        return ctx

    mock_retriever.retrieve.side_effect = _retriever_side_effect

    # Step 1: 의도 분류 (기본: OUT_OF_SCOPE → 빠른 return)
    mock_intent = MagicMock()
    mock_intent.classify.return_value = IntentType.OUT_OF_SCOPE

    # Step 2: 질문 정제
    mock_refiner = MagicMock()
    mock_refiner.refine.return_value = "기기별 클릭수"

    # Step 3: 키워드 추출
    mock_keyword = MagicMock()
    mock_keyword.extract.return_value = ["클릭수", "기기"]

    # Step 4: RAG 검색
    mock_rag = MagicMock()
    mock_rag.retrieve.return_value = MagicMock()

    # Step 5: SQL 생성
    mock_sql_gen = MagicMock()
    mock_sql_gen.generate.return_value = (
        "SELECT COUNT(*) FROM ad_combined_log WHERE is_click = true"
    )

    # Step 6: SQL 검증
    mock_validator = MagicMock()
    val_result = MagicMock()
    val_result.is_valid = True
    val_result.normalized_sql = (
        "SELECT COUNT(*) FROM ad_combined_log WHERE is_click = true"
    )
    mock_validator.validate.return_value = val_result

    # Step 10: AI 분석
    mock_ai = MagicMock()
    analysis = MagicMock()
    analysis.chart_type.value = "none"
    mock_ai.analyze.return_value = analysis

    # Step 10.5: 차트 렌더링
    mock_chart = MagicMock()

    # Step 11: 이력 저장
    mock_recorder = MagicMock()
    mock_recorder.record.return_value = "hist-test-001"

    pipeline._intent_classifier = mock_intent
    pipeline._question_refiner = mock_refiner
    pipeline._keyword_extractor = mock_keyword
    pipeline._rag_retriever = mock_rag
    pipeline._sql_generator = mock_sql_gen
    pipeline._sql_validator = mock_validator
    pipeline._ai_analyzer = mock_ai
    pipeline._chart_renderer = mock_chart
    pipeline._recorder = mock_recorder
    pipeline._redash_config = None
    pipeline._conversation_retriever = mock_retriever

    return pipeline, mock_retriever, mock_refiner, mock_sql_gen


# ---------------------------------------------------------------------------
# TC-WI-01: QueryResponse.session_id 필드 존재
# ---------------------------------------------------------------------------

class TestQueryResponseSessionIdField:
    def test_session_id_field_exists(self):
        """TC-WI-01: QueryResponse에 session_id Optional[str] 필드가 존재해야 한다"""
        assert "session_id" in QueryResponse.model_fields
        assert QueryResponse.model_fields["session_id"].default is None


# ---------------------------------------------------------------------------
# TC-WI-02 ~ TC-WI-04: run() conversation_id 파라미터 및 Feature Flag
# ---------------------------------------------------------------------------

class TestPipelineRunConversationId:
    def test_conversation_id_sets_session_id_on_ctx(self):
        """TC-WI-02: run(conversation_id=...) → 반환된 ctx.session_id == 입력값"""
        pipeline, _, _, _ = _make_pipeline()

        ctx = asyncio.run(
            pipeline.run(
                question="기기별 클릭수 알려줘",
                conversation_id="1711111.111",
            )
        )

        assert ctx.session_id == "1711111.111"

    def test_multi_turn_enabled_calls_retriever(self):
        """TC-WI-03: MULTI_TURN_ENABLED=true + session_id 있을 때 retriever.retrieve() 1회 호출"""
        pipeline, mock_retriever, _, _ = _make_pipeline()

        with patch("src.query_pipeline.MULTI_TURN_ENABLED", True):
            asyncio.run(
                pipeline.run(
                    question="기기별 클릭수",
                    conversation_id="1711111.111",
                )
            )

        mock_retriever.retrieve.assert_called_once()

    def test_multi_turn_disabled_skips_retriever(self):
        """TC-WI-04: MULTI_TURN_ENABLED=false → retriever.retrieve() 미호출"""
        pipeline, mock_retriever, _, _ = _make_pipeline()

        with patch("src.query_pipeline.MULTI_TURN_ENABLED", False):
            asyncio.run(
                pipeline.run(
                    question="기기별 클릭수",
                    conversation_id="1711111.111",
                )
            )

        mock_retriever.retrieve.assert_not_called()


# ---------------------------------------------------------------------------
# TC-WI-05 ~ TC-WI-06: conversation_history 파라미터 전파
# ---------------------------------------------------------------------------

class TestConversationHistoryPropagation:
    def _make_full_pipeline(self, history=None):
        """Step 2/5 도달을 위한 파이프라인.

        intent=SQL_QUERY, _run_athena_fallback=AsyncMock(noop).
        """
        pipeline, mock_retriever, mock_refiner, mock_sql_gen = _make_pipeline(
            history=history
        )
        # DATA_QUERY로 변경 → Step 2, 5까지 실행
        pipeline._intent_classifier.classify.return_value = IntentType.DATA_QUERY

        # _run_athena_fallback async noop (ctx 그대로 반환)
        async def _noop_fallback(ctx, sql):
            return ctx

        pipeline._run_athena_fallback = _noop_fallback

        return pipeline, mock_retriever, mock_refiner, mock_sql_gen

    def test_conversation_history_passed_to_refiner(self):
        """TC-WI-05: run() 실행 시 Step 2 refine()에 conversation_history kwarg 전달"""
        history = [
            ConversationTurn(
                turn_number=1,
                question="어제 전체 광고 클릭수는?",
                answer="총 12,345건 클릭이 발생했습니다.",
            )
        ]
        pipeline, _, mock_refiner, _ = self._make_full_pipeline(history=history)

        with patch("src.query_pipeline.MULTI_TURN_ENABLED", True):
            asyncio.run(
                pipeline.run(
                    question="기기별로 나눠줘",
                    conversation_id="1711111.111",
                )
            )

        call_kwargs = mock_refiner.refine.call_args
        assert "conversation_history" in call_kwargs.kwargs

    def test_conversation_history_passed_to_sql_generator(self):
        """TC-WI-06: run() 실행 시 Step 5 generate()에 conversation_history kwarg 전달"""
        history = [
            ConversationTurn(
                turn_number=1,
                question="어제 전체 광고 클릭수는?",
                generated_sql=(
                    "SELECT COUNT(*) FROM ad_combined_log WHERE is_click = true"
                ),
            )
        ]
        pipeline, _, _, mock_sql_gen = self._make_full_pipeline(history=history)

        with patch("src.query_pipeline.MULTI_TURN_ENABLED", True):
            asyncio.run(
                pipeline.run(
                    question="기기별로 나눠줘",
                    conversation_id="1711111.111",
                )
            )

        call_kwargs = mock_sql_gen.generate.call_args
        assert "conversation_history" in call_kwargs.kwargs

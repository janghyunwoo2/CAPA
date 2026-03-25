"""
Multi-Turn Conversation (FR-20) 단위 테스트

TC 목록:
  TC-MT-01: ConversationTurn 모델 생성 및 필드 검증
  TC-MT-02: PipelineContext FR-20 신규 필드 검증
  TC-MT-03: Step 0 — 이력 있을 때 조회 및 turn_number 계산
  TC-MT-04: Step 0 — 첫 번째 턴 (이력 없음)
  TC-MT-05: Step 0 — session_id 없으면 건너뜀
  TC-MT-06: Step 0 — DynamoDB 오류 시 graceful degradation
  TC-MT-07: Step 0 — 최근 5턴 초과 시 잘라냄
  TC-MT-08: Step 11 — session_id 있을 때 멀티턴 필드 저장
  TC-MT-09: Step 11 — session_id 없으면 멀티턴 필드 미저장
  TC-MT-10: QuestionRefiner — conversation_history 주입
  TC-MT-11: QuestionRefiner — conversation_history=None 기존 동작
  TC-MT-12: SQLGenerator — conversation_history 이전 SQL 주입
  TC-MT-13: SQLGenerator — conversation_history=None 기존 동작
"""

from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest
from botocore.exceptions import ClientError

from src.models.domain import (
    AnalysisResult,
    ConversationTurn,
    IntentType,
    PipelineContext,
)
from src.pipeline.conversation_history_retriever import ConversationHistoryRetriever
from src.stores.dynamodb_history import DynamoDBHistoryRecorder


# ---------------------------------------------------------------------------
# 공통 픽스처
# ---------------------------------------------------------------------------


def _make_dynamo_item(turn_number: int, question: str = "테스트 질문", sql: str = "SELECT 1", answer: str = "결과입니다") -> dict:
    """DynamoDB GSI 반환 형식의 더미 아이템"""
    return {
        "history_id": f"uuid-{turn_number}",
        "session_id": "1711234567.111",
        "turn_number": Decimal(str(turn_number)),
        "original_question": question,
        "refined_question": f"정제된 {question}",
        "generated_sql": sql,
        "answer": answer,
    }


@pytest.fixture
def mock_dynamo_table():
    """DynamoDB Table Mock"""
    table = MagicMock()
    table.query.return_value = {"Items": []}
    return table


@pytest.fixture
def mock_dynamo_resource(mock_dynamo_table):
    """DynamoDB Resource Mock"""
    resource = MagicMock()
    resource.Table.return_value = mock_dynamo_table
    return resource


@pytest.fixture
def retriever(mock_dynamo_resource):
    """ConversationHistoryRetriever 인스턴스"""
    return ConversationHistoryRetriever(mock_dynamo_resource)


@pytest.fixture
def base_ctx():
    """기본 PipelineContext (session_id 없음)"""
    return PipelineContext(original_question="신규 가입자 수?")


@pytest.fixture
def session_ctx():
    """session_id 있는 PipelineContext"""
    return PipelineContext(
        original_question="연령대별로 나눠줘",
        session_id="1711234567.111",
    )


# ---------------------------------------------------------------------------
# TC-MT-01 / TC-MT-02: 도메인 모델
# ---------------------------------------------------------------------------


class TestDomainModels:
    """FR-20 도메인 모델 검증"""

    def test_conversation_turn_creation(self):
        """TC-MT-01: ConversationTurn 모델 — 필수/선택 필드"""
        turn = ConversationTurn(turn_number=1, question="어제 전체 광고 클릭수는?")
        assert turn.turn_number == 1
        assert turn.question == "어제 전체 광고 클릭수는?"
        assert turn.refined_question is None
        assert turn.generated_sql is None
        assert turn.answer is None

    def test_conversation_turn_with_all_fields(self):
        """TC-MT-01: ConversationTurn 모델 — 전체 필드 설정"""
        turn = ConversationTurn(
            turn_number=1,
            question="어제 전체 광고 클릭수는?",
            refined_question="2026-02 전체 광고 클릭수 조회",
            generated_sql="SELECT COUNT(*) FROM ad_combined_log WHERE is_click = true",
            answer="총 12,345건 클릭이 발생했습니다.",
        )
        assert turn.generated_sql == "SELECT COUNT(*) FROM ad_combined_log WHERE is_click = true"
        assert turn.answer == "총 12,345건 클릭이 발생했습니다."

    def test_pipeline_context_fr20_fields(self):
        """TC-MT-02: PipelineContext — FR-20 신규 필드"""
        ctx = PipelineContext(
            original_question="테스트",
            session_id="1711234567.111",
            turn_number=2,
            slack_thread_ts="1711234567.111",
        )
        assert ctx.session_id == "1711234567.111"
        assert ctx.turn_number == 2
        assert ctx.slack_thread_ts == "1711234567.111"
        assert ctx.conversation_history == []  # 기본값 빈 리스트

    def test_pipeline_context_fr20_fields_default_none(self):
        """TC-MT-02: PipelineContext — FR-20 필드 기본값 None"""
        ctx = PipelineContext(original_question="테스트")
        assert ctx.session_id is None
        assert ctx.turn_number is None
        assert ctx.slack_thread_ts is None
        assert ctx.conversation_history == []


# ---------------------------------------------------------------------------
# TC-MT-03 ~ TC-MT-07: ConversationHistoryRetriever (Step 0)
# ---------------------------------------------------------------------------


class TestConversationHistoryRetriever:
    """FR-20-01, FR-20-03, FR-20-07, FR-20-08: Step 0 대화 이력 조회"""

    def test_retrieve_with_existing_history(self, retriever, mock_dynamo_table, session_ctx):
        """TC-MT-03: 이력 1건 있을 때 — conversation_history 1건, turn_number=2"""
        mock_dynamo_table.query.return_value = {
            "Items": [_make_dynamo_item(1)]
        }
        ctx = retriever.retrieve(session_ctx)
        assert len(ctx.conversation_history) == 1
        assert ctx.turn_number == 2
        assert ctx.conversation_history[0].turn_number == 1
        assert ctx.conversation_history[0].question == "테스트 질문"

    def test_retrieve_first_turn_empty_history(self, retriever, mock_dynamo_table, session_ctx):
        """TC-MT-04: 이력 없을 때 — turn_number=1, conversation_history=[]"""
        mock_dynamo_table.query.return_value = {"Items": []}
        ctx = retriever.retrieve(session_ctx)
        assert ctx.turn_number == 1
        assert ctx.conversation_history == []

    def test_retrieve_skips_when_no_session_id(self, retriever, mock_dynamo_table, base_ctx):
        """TC-MT-05: session_id 없으면 DynamoDB 조회 안 함 (하위 호환)"""
        ctx = retriever.retrieve(base_ctx)
        mock_dynamo_table.query.assert_not_called()
        assert ctx.conversation_history == []

    def test_retrieve_graceful_on_dynamodb_error(self, retriever, mock_dynamo_table, session_ctx):
        """TC-MT-06: DynamoDB ClientError → 예외 없이 빈 이력으로 진행"""
        mock_dynamo_table.query.side_effect = ClientError(
            {"Error": {"Code": "ResourceNotFoundException", "Message": "Table not found"}},
            "Query",
        )
        ctx = retriever.retrieve(session_ctx)
        assert ctx.conversation_history == []

    def test_retrieve_limits_to_max_turns(self, retriever, mock_dynamo_table, session_ctx):
        """TC-MT-07: 7턴 있어도 최근 5턴만, turn_number=8"""
        items = [_make_dynamo_item(i) for i in range(1, 8)]  # 7건
        mock_dynamo_table.query.return_value = {"Items": items}
        with patch.dict("os.environ", {"CONVERSATION_MAX_TURNS": "5"}):
            # 모듈 상수는 import 시 결정되므로 retriever의 _max_turns 직접 패치
            retriever._max_turns = 5
            ctx = retriever.retrieve(session_ctx)
        assert len(ctx.conversation_history) == 5
        assert ctx.turn_number == 8
        # 최근 5턴 = turn 3~7
        assert ctx.conversation_history[0].turn_number == 3


# ---------------------------------------------------------------------------
# TC-MT-08 / TC-MT-09: DynamoDBHistoryRecorder (Step 11)
# ---------------------------------------------------------------------------


class TestDynamoDBHistoryRecorderMultiTurn:
    """FR-20-06: Step 11 멀티턴 필드 저장"""

    @pytest.fixture
    def recorder(self, mock_dynamo_resource):
        return DynamoDBHistoryRecorder(mock_dynamo_resource, "capa-dev-query-history")

    @pytest.fixture
    def ctx_with_session(self):
        """session_id 있는 컨텍스트"""
        ctx = PipelineContext(
            original_question="기기별로 나눠줘",
            session_id="1711234567.111",
            turn_number=2,
            slack_thread_ts="1711234567.111",
            intent=IntentType.DATA_QUERY,
        )
        ctx.analysis = AnalysisResult(answer="기기별 클릭수 집계 결과입니다.")
        return ctx

    @pytest.fixture
    def ctx_without_session(self):
        """session_id 없는 컨텍스트 (기존 동작)"""
        return PipelineContext(
            original_question="어제 전체 광고 클릭수는?",
            intent=IntentType.DATA_QUERY,
        )

    def test_record_saves_multi_turn_fields(self, recorder, mock_dynamo_table, ctx_with_session):
        """TC-MT-08: session_id 있으면 session_id/turn_number/answer/slack_thread_ts 저장"""
        recorder.record(ctx_with_session)
        assert mock_dynamo_table.put_item.called
        item = mock_dynamo_table.put_item.call_args[1]["Item"]
        assert item["session_id"] == "1711234567.111"
        assert item["turn_number"] == 2
        assert item["answer"] == "기기별 클릭수 집계 결과입니다."
        assert item["slack_thread_ts"] == "1711234567.111"

    def test_record_omits_multi_turn_fields_without_session(
        self, recorder, mock_dynamo_table, ctx_without_session
    ):
        """TC-MT-09: session_id 없으면 멀티턴 필드 저장 안 함"""
        recorder.record(ctx_without_session)
        item = mock_dynamo_table.put_item.call_args[1]["Item"]
        assert "session_id" not in item
        assert "turn_number" not in item
        assert "answer" not in item

    def test_record_trims_answer_to_500_chars(self, recorder, mock_dynamo_table):
        """TC-MT-08: answer 500자 초과 시 트림"""
        ctx = PipelineContext(
            original_question="질문",
            session_id="1711234567.111",
            turn_number=1,
            intent=IntentType.DATA_QUERY,
        )
        ctx.analysis = AnalysisResult(answer="A" * 600)
        recorder.record(ctx)
        item = mock_dynamo_table.put_item.call_args[1]["Item"]
        assert len(item["answer"]) == 500


# ---------------------------------------------------------------------------
# TC-MT-10 / TC-MT-11: QuestionRefiner
# ---------------------------------------------------------------------------


class TestQuestionRefinerMultiTurn:
    """FR-20-04: QuestionRefiner conversation_history 주입"""

    @pytest.fixture
    def mock_llm(self):
        """Anthropic LLM Mock"""
        llm = MagicMock()
        msg = MagicMock()
        msg.content = [MagicMock(text="정제된 질문입니다.")]
        llm.messages.create.return_value = msg
        return llm

    @pytest.fixture
    def refiner(self, mock_llm):
        from src.pipeline.question_refiner import QuestionRefiner
        return QuestionRefiner(mock_llm)

    def test_refine_includes_history_in_prompt(self, refiner, mock_llm):
        """TC-MT-10: conversation_history 있으면 LLM 프롬프트에 이전 대화 맥락 포함"""
        history = [
            ConversationTurn(
                turn_number=1,
                question="어제 전체 광고 클릭수는?",
                answer="총 12,345건 클릭이 발생했습니다.",
            )
        ]
        refiner.refine("기기별로 나눠줘", conversation_history=history)
        call_args = mock_llm.messages.create.call_args
        messages = call_args[1]["messages"]
        prompt_text = " ".join(str(m) for m in messages)
        assert "이전 대화 맥락" in prompt_text

    def test_refine_without_history_no_error(self, refiner):
        """TC-MT-11: conversation_history=None 전달 시 예외 없이 정상 동작"""
        result = refiner.refine("어제 전체 광고 클릭수는?", conversation_history=None)
        assert result is not None

    def test_refine_without_history_param_no_error(self, refiner):
        """TC-MT-11: conversation_history 파라미터 생략 시도 기존 동작"""
        result = refiner.refine("어제 전체 광고 클릭수는?")
        assert result is not None


# ---------------------------------------------------------------------------
# TC-MT-12 / TC-MT-13: SQLGenerator
# ---------------------------------------------------------------------------


class TestSQLGeneratorMultiTurn:
    """FR-20-05: SQLGenerator conversation_history 이전 SQL 주입"""

    @pytest.fixture
    def mock_vanna(self):
        vanna = MagicMock()
        vanna.generate_sql.return_value = "SELECT COUNT(*) FROM ad_combined_log WHERE is_click = true"
        return vanna

    @pytest.fixture
    def generator(self, mock_vanna):
        from src.pipeline.sql_generator import SQLGenerator
        return SQLGenerator(mock_vanna)

    def test_generate_includes_prev_sql_in_prompt(self, generator, mock_vanna):
        """TC-MT-12: conversation_history 있으면 이전 SQL이 Vanna 프롬프트에 포함"""
        history = [
            ConversationTurn(
                turn_number=1,
                question="어제 전체 광고 클릭수는?",
                generated_sql="SELECT COUNT(*) FROM ad_combined_log WHERE is_click = true AND month='02'",
            )
        ]
        generator.generate("기기별로 나눠줘", conversation_history=history)
        vanna_call_args = mock_vanna.generate_sql.call_args
        prompt = vanna_call_args[1]["question"]
        assert "이전 대화에서 생성된 SQL" in prompt

    def test_generate_without_history_returns_sql(self, generator):
        """TC-MT-13: conversation_history=None 전달 시 기존 SQL 생성 동작"""
        result = generator.generate("어제 전체 광고 클릭수는?", conversation_history=None)
        assert result == "SELECT COUNT(*) FROM ad_combined_log WHERE is_click = true"

    def test_generate_without_history_param_returns_sql(self, generator):
        """TC-MT-13: conversation_history 파라미터 생략 — 기존 동작 유지"""
        result = generator.generate("어제 전체 광고 클릭수는?")
        assert result == "SELECT COUNT(*) FROM ad_combined_log WHERE is_click = true"

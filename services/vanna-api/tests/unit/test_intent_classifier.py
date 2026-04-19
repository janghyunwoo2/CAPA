"""
Step 1: IntentClassifier 단위 테스트 — test-plan.md §3.1 (FR-01)
LLM 호출을 Mock 처리하여 분류 로직만 검증
"""

import pytest
from unittest.mock import patch, MagicMock

from src.pipeline.intent_classifier import IntentClassifier
from src.models.domain import IntentType


@pytest.fixture
def classifier(fake_api_key):
    """IntentClassifier 인스턴스 (API 호출은 Mock 처리)"""
    with patch("src.pipeline.intent_classifier.anthropic.Anthropic") as mock_cls:
        instance = IntentClassifier(api_key=fake_api_key)
        yield instance, mock_cls.return_value


def _make_response(text: str) -> MagicMock:
    """Anthropic API 응답 Mock 생성 헬퍼"""
    response = MagicMock()
    content_block = MagicMock()
    content_block.text = text
    response.content = [content_block]
    return response


class TestClassifyDataQuery:
    """데이터 조회 질문 분류 테스트"""

    def test_classify_sql_query_intent_returns_data_query(self, classifier):
        """데이터 조회 질문 → DATA_QUERY 분류 (FR-01)"""
        instance, mock_client = classifier
        mock_client.messages.create.return_value = _make_response("DATA_QUERY")

        result = instance.classify("어제 캠페인별 CTR 알려줘")

        assert result == IntentType.DATA_QUERY

    def test_classify_roas_question_returns_data_query(self, classifier):
        """ROAS 관련 질문 → DATA_QUERY 분류 (FR-01)"""
        instance, mock_client = classifier
        mock_client.messages.create.return_value = _make_response("DATA_QUERY")

        result = instance.classify("최근 7일간 디바이스별 ROAS 순위")

        assert result == IntentType.DATA_QUERY


class TestClassifyOutOfScope:
    """도메인 외 질문 분류 테스트"""

    def test_classify_out_of_domain_intent(self, classifier):
        """광고 외 질문 → OUT_OF_SCOPE 분류 (FR-01, EX-1)"""
        instance, mock_client = classifier
        mock_client.messages.create.return_value = _make_response("OUT_OF_SCOPE")

        result = instance.classify("요즘 날씨 어때?")

        assert result == IntentType.OUT_OF_SCOPE


class TestClassifyGeneral:
    """일반 질문 분류 테스트"""

    def test_classify_general_knowledge_question(self, classifier):
        """일반 지식 질문 → GENERAL 분류 (FR-01)"""
        instance, mock_client = classifier
        mock_client.messages.create.return_value = _make_response("GENERAL")

        result = instance.classify("CTR이 뭐야?")

        assert result == IntentType.GENERAL


class TestClassifyFallback:
    """Fallback 동작 테스트"""

    def test_unexpected_response_falls_back_to_data_query(self, classifier):
        """예상치 못한 응답 → DATA_QUERY fallback (graceful degradation)"""
        instance, mock_client = classifier
        mock_client.messages.create.return_value = _make_response("UNKNOWN_TYPE")

        result = instance.classify("이상한 질문")

        assert result == IntentType.DATA_QUERY

    def test_api_error_falls_back_to_data_query(self, classifier):
        """API 호출 실패 → DATA_QUERY fallback (graceful degradation)"""
        import anthropic

        instance, mock_client = classifier
        mock_client.messages.create.side_effect = anthropic.APIError(
            message="API Error",
            request=MagicMock(),
            body=None,
        )

        result = instance.classify("어떤 질문이든")

        assert result == IntentType.DATA_QUERY

    def test_generic_exception_falls_back_to_data_query(self, classifier):
        """일반 예외 발생 → DATA_QUERY fallback (graceful degradation)"""
        instance, mock_client = classifier
        mock_client.messages.create.side_effect = RuntimeError("연결 실패")

        result = instance.classify("어떤 질문이든")

        assert result == IntentType.DATA_QUERY


class TestClassifyInterfaceContract:
    """인터페이스 계약 검증"""

    def test_classify_returns_intent_type_enum(self, classifier):
        """반환값이 IntentType enum 인스턴스인지 확인"""
        instance, mock_client = classifier
        mock_client.messages.create.return_value = _make_response("DATA_QUERY")

        result = instance.classify("테스트 질문")

        assert isinstance(result, IntentType)

    def test_classify_calls_anthropic_with_correct_params(self, classifier):
        """Anthropic API를 올바른 파라미터로 호출하는지 확인"""
        instance, mock_client = classifier
        mock_client.messages.create.return_value = _make_response("DATA_QUERY")

        instance.classify("테스트 질문")

        mock_client.messages.create.assert_called_once()
        call_kwargs = mock_client.messages.create.call_args.kwargs
        assert call_kwargs["max_tokens"] == 20
        assert call_kwargs["messages"][0]["content"] == "테스트 질문"

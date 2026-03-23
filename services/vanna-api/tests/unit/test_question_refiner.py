"""
Step 2: QuestionRefiner 단위 테스트 — test-plan.md §3.2 (FR-02)
LLM 호출을 Mock 처리하여 질문 정제 로직만 검증
"""

import pytest
from unittest.mock import patch, MagicMock

from src.pipeline.question_refiner import QuestionRefiner


@pytest.fixture
def refiner(fake_api_key):
    """QuestionRefiner 인스턴스 (API 호출은 Mock 처리)"""
    with patch("src.pipeline.question_refiner.anthropic.Anthropic") as mock_cls:
        instance = QuestionRefiner(api_key=fake_api_key)
        yield instance, mock_cls.return_value


def _make_response(text: str) -> MagicMock:
    """Anthropic API 응답 Mock 생성 헬퍼"""
    response = MagicMock()
    content_block = MagicMock()
    content_block.text = text
    response.content = [content_block]
    return response


class TestRefineSuccess:
    """정상 정제 동작 테스트"""

    def test_refine_removes_filler_keeps_core(self, refiner):
        """불필요한 수식어 제거, 핵심 의미 보존 (FR-02)"""
        instance, mock_client = refiner
        mock_client.messages.create.return_value = _make_response(
            "최근 7일간 기기별 전환액"
        )

        result = instance.refine("음... 혹시 최근 7일간 기기별 전환액 좀 알 수 있을까요?")

        assert "전환액" in result
        assert isinstance(result, str)

    def test_refine_pipeline_flow_example_case(self, refiner):
        """pipeline-flow-example.md 기준 케이스 (FR-02)"""
        instance, mock_client = refiner
        mock_client.messages.create.return_value = _make_response(
            "최근 7일간 디바이스별 구매 전환액과 ROAS 순위"
        )

        result = instance.refine("최근 7일간 디바이스별 구매 전환액과 ROAS 순위 알려줘")

        assert any(kw in result for kw in ["ROAS", "전환액", "디바이스"])

    def test_refine_preserves_time_expression(self, refiner):
        """시간 표현 보존 확인 (FR-02)"""
        instance, mock_client = refiner
        mock_client.messages.create.return_value = _make_response(
            "어제 캠페인별 CTR 상위 5개"
        )

        result = instance.refine("안녕하세요, 어제 캠페인별 CTR 상위 5개 보여주세요~")

        assert "어제" in result
        assert "CTR" in result


class TestRefineFallback:
    """Fallback 동작 테스트 (graceful degradation)"""

    def test_api_error_returns_original_question(self, refiner):
        """API 호출 실패 → 원본 질문 그대로 반환 (graceful degradation)"""
        import anthropic

        instance, mock_client = refiner
        mock_client.messages.create.side_effect = anthropic.APIError(
            message="API Error",
            request=MagicMock(),
            body=None,
        )

        original = "원본 질문입니다"
        result = instance.refine(original)

        assert result == original

    def test_generic_exception_returns_original_question(self, refiner):
        """일반 예외 발생 → 원본 질문 그대로 반환 (graceful degradation)"""
        instance, mock_client = refiner
        mock_client.messages.create.side_effect = RuntimeError("연결 실패")

        original = "원본 질문입니다"
        result = instance.refine(original)

        assert result == original

    def test_empty_response_returns_original_question(self, refiner):
        """빈 응답 → 원본 질문 그대로 반환 (graceful degradation)"""
        instance, mock_client = refiner
        mock_client.messages.create.return_value = _make_response("")

        original = "원본 질문입니다"
        result = instance.refine(original)

        assert result == original


class TestRefineInterfaceContract:
    """인터페이스 계약 검증"""

    def test_refine_returns_string(self, refiner):
        """반환값이 문자열인지 확인"""
        instance, mock_client = refiner
        mock_client.messages.create.return_value = _make_response("정제된 질문")

        result = instance.refine("테스트")

        assert isinstance(result, str)

    def test_refine_calls_anthropic_with_correct_params(self, refiner):
        """Anthropic API를 올바른 파라미터로 호출하는지 확인"""
        instance, mock_client = refiner
        mock_client.messages.create.return_value = _make_response("정제된 질문")

        instance.refine("테스트 질문")

        mock_client.messages.create.assert_called_once()
        call_kwargs = mock_client.messages.create.call_args.kwargs
        assert call_kwargs["max_tokens"] == 200
        assert call_kwargs["messages"][0]["content"] == "테스트 질문"

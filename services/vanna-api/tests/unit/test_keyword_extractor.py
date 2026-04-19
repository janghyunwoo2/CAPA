"""
Step 3: KeywordExtractor 단위 테스트 — test-plan.md §3.3 (FR-03)
LLM 호출을 Mock 처리하여 키워드 추출 로직만 검증
"""

import pytest
from unittest.mock import patch, MagicMock

from src.pipeline.keyword_extractor import KeywordExtractor


@pytest.fixture
def extractor(fake_api_key):
    """KeywordExtractor 인스턴스 (API 호출은 Mock 처리)"""
    with patch("src.pipeline.keyword_extractor.anthropic.Anthropic") as mock_cls:
        instance = KeywordExtractor(api_key=fake_api_key)
        yield instance, mock_cls.return_value


def _make_response(text: str) -> MagicMock:
    """Anthropic API 응답 Mock 생성 헬퍼"""
    response = MagicMock()
    content_block = MagicMock()
    content_block.text = text
    response.content = [content_block]
    return response


class TestExtractSuccess:
    """정상 키워드 추출 테스트"""

    def test_extract_keywords_returns_list(self, extractor):
        """키워드 추출 결과는 리스트 (FR-03)"""
        instance, mock_client = extractor
        mock_client.messages.create.return_value = _make_response(
            '["ROAS", "device_type", "전환액"]'
        )

        result = instance.extract("디바이스별 ROAS 순위")

        assert isinstance(result, list)
        assert len(result) > 0

    def test_extract_includes_domain_terms(self, extractor):
        """ROAS, device_type 등 도메인 용어 포함 (FR-03)"""
        instance, mock_client = extractor
        mock_client.messages.create.return_value = _make_response(
            '["ROAS", "device_type", "conversion_value", "최근 7일"]'
        )

        result = instance.extract("최근 7일간 디바이스별 전환액과 ROAS")

        keywords_lower = [k.lower() for k in result]
        assert any(kw in keywords_lower for kw in ["roas", "device_type", "conversion_value"])

    def test_extract_preserves_time_expression(self, extractor):
        """시간 표현 키워드 추출 확인 (FR-03)"""
        instance, mock_client = extractor
        mock_client.messages.create.return_value = _make_response(
            '["CTR", "캠페인", "어제"]'
        )

        result = instance.extract("어제 캠페인별 CTR")

        assert "어제" in result or "CTR" in result

    def test_extract_empty_question_returns_empty_list(self, extractor):
        """빈 배열 응답 시 빈 리스트 반환 (FR-03)"""
        instance, mock_client = extractor
        mock_client.messages.create.return_value = _make_response("[]")

        result = instance.extract("키워드 없는 질문")

        assert result == []


class TestExtractFallback:
    """Fallback 동작 테스트"""

    def test_api_error_returns_empty_list(self, extractor):
        """API 호출 실패 → 빈 리스트 반환 (graceful degradation)"""
        import anthropic

        instance, mock_client = extractor
        mock_client.messages.create.side_effect = anthropic.APIError(
            message="API Error",
            request=MagicMock(),
            body=None,
        )

        result = instance.extract("어떤 질문이든")

        assert result == []

    def test_json_parse_error_returns_empty_list(self, extractor):
        """JSON 파싱 실패 → 빈 리스트 반환 (graceful degradation)"""
        instance, mock_client = extractor
        mock_client.messages.create.return_value = _make_response(
            "이것은 JSON이 아닙니다"
        )

        result = instance.extract("어떤 질문이든")

        assert result == []

    def test_generic_exception_returns_empty_list(self, extractor):
        """일반 예외 발생 → 빈 리스트 반환 (graceful degradation)"""
        instance, mock_client = extractor
        mock_client.messages.create.side_effect = RuntimeError("연결 실패")

        result = instance.extract("어떤 질문이든")

        assert result == []

    def test_non_list_json_returns_empty_list(self, extractor):
        """JSON이지만 리스트가 아닌 응답 → 빈 리스트 반환"""
        instance, mock_client = extractor
        mock_client.messages.create.return_value = _make_response(
            '{"key": "value"}'
        )

        result = instance.extract("어떤 질문이든")

        assert result == []


class TestExtractInterfaceContract:
    """인터페이스 계약 검증"""

    def test_extract_returns_list_of_strings(self, extractor):
        """반환값이 문자열 리스트인지 확인"""
        instance, mock_client = extractor
        mock_client.messages.create.return_value = _make_response('["CTR", "ROAS"]')

        result = instance.extract("테스트")

        assert isinstance(result, list)
        assert all(isinstance(k, str) for k in result)

    def test_extract_calls_anthropic_with_correct_params(self, extractor):
        """Anthropic API를 올바른 파라미터로 호출하는지 확인"""
        instance, mock_client = extractor
        mock_client.messages.create.return_value = _make_response('["CTR"]')

        instance.extract("테스트 질문")

        mock_client.messages.create.assert_called_once()
        call_kwargs = mock_client.messages.create.call_args.kwargs
        assert call_kwargs["max_tokens"] == 200
        assert call_kwargs["messages"][0]["content"] == "테스트 질문"

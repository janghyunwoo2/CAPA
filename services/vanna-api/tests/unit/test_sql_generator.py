"""
Step 5: SQLGenerator 단위 테스트 — test-plan.md §3.10 (FR-05)
Vanna 호출을 Mock 처리하여 SQL 생성 로직 검증
"""

import pytest
from unittest.mock import MagicMock

from src.pipeline.sql_generator import SQLGenerator, SQLGenerationError
from src.models.domain import RAGContext


class TestGenerateSuccess:
    """정상 SQL 생성 테스트"""

    def test_generate_returns_sql_string(self, mock_vanna_instance):
        """SQL 생성 결과가 문자열인지 확인 (FR-05)"""
        mock_vanna_instance.generate_sql.return_value = (
            "SELECT device_type, SUM(conversion_value) FROM ad_combined_log_summary "
            "GROUP BY device_type ORDER BY 2 DESC"
        )

        generator = SQLGenerator(vanna_instance=mock_vanna_instance)
        result = generator.generate("디바이스별 전환액 순위")

        assert isinstance(result, str)
        assert "SELECT" in result.upper()

    def test_generate_strips_whitespace(self, mock_vanna_instance):
        """생성된 SQL 양쪽 공백 제거 확인"""
        mock_vanna_instance.generate_sql.return_value = "  SELECT 1 FROM ad_combined_log  "

        generator = SQLGenerator(vanna_instance=mock_vanna_instance)
        result = generator.generate("테스트 질문")

        assert not result.startswith(" ")
        assert not result.endswith(" ")

    def test_generate_with_rag_context(self, mock_vanna_instance):
        """RAGContext 전달 시 정상 동작 확인"""
        mock_vanna_instance.generate_sql.return_value = "SELECT * FROM ad_combined_log"
        rag = RAGContext(
            ddl_context=["CREATE TABLE ad_combined_log (...)"],
            documentation_context=["광고 로그 테이블"],
            sql_examples=["SELECT device_type FROM ad_combined_log"],
        )

        generator = SQLGenerator(vanna_instance=mock_vanna_instance)
        result = generator.generate("디바이스별 조회", rag_context=rag)

        assert isinstance(result, str)
        assert len(result) > 0

    def test_generate_calls_vanna_with_question(self, mock_vanna_instance):
        """Vanna에 질문을 올바르게 전달하는지 확인"""
        mock_vanna_instance.generate_sql.return_value = "SELECT 1 FROM ad_combined_log"

        generator = SQLGenerator(vanna_instance=mock_vanna_instance)
        generator.generate("테스트 질문")

        mock_vanna_instance.generate_sql.assert_called_once_with(question="테스트 질문")


class TestGenerateFailure:
    """SQL 생성 실패 테스트"""

    def test_generate_empty_sql_raises_error(self, mock_vanna_instance):
        """빈 SQL 생성 → SQLGenerationError 발생"""
        mock_vanna_instance.generate_sql.return_value = ""

        generator = SQLGenerator(vanna_instance=mock_vanna_instance)

        with pytest.raises(SQLGenerationError) as exc_info:
            generator.generate("테스트 질문")
        assert "빈 SQL" in str(exc_info.value)

    def test_generate_none_sql_raises_error(self, mock_vanna_instance):
        """None 반환 → SQLGenerationError 발생"""
        mock_vanna_instance.generate_sql.return_value = None

        generator = SQLGenerator(vanna_instance=mock_vanna_instance)

        with pytest.raises(SQLGenerationError):
            generator.generate("테스트 질문")

    def test_generate_whitespace_only_raises_error(self, mock_vanna_instance):
        """공백만 있는 SQL → SQLGenerationError 발생"""
        mock_vanna_instance.generate_sql.return_value = "   "

        generator = SQLGenerator(vanna_instance=mock_vanna_instance)

        with pytest.raises(SQLGenerationError):
            generator.generate("테스트 질문")

    def test_generate_vanna_exception_raises_sql_generation_error(self, mock_vanna_instance):
        """Vanna 내부 예외 → SQLGenerationError 래핑 (파이프라인 중단)"""
        mock_vanna_instance.generate_sql.side_effect = RuntimeError("Vanna 내부 오류")

        generator = SQLGenerator(vanna_instance=mock_vanna_instance)

        with pytest.raises(SQLGenerationError) as exc_info:
            generator.generate("테스트 질문")
        assert "오류" in str(exc_info.value)

    def test_generate_connection_error_raises_sql_generation_error(self, mock_vanna_instance):
        """연결 오류 → SQLGenerationError 래핑"""
        mock_vanna_instance.generate_sql.side_effect = ConnectionError("ChromaDB 연결 실패")

        generator = SQLGenerator(vanna_instance=mock_vanna_instance)

        with pytest.raises(SQLGenerationError):
            generator.generate("테스트 질문")


class TestGenerateInterfaceContract:
    """인터페이스 계약 검증"""

    def test_generate_returns_non_empty_string_on_success(self, mock_vanna_instance):
        """성공 시 비어있지 않은 문자열 반환 보장"""
        mock_vanna_instance.generate_sql.return_value = "SELECT 1 FROM ad_combined_log"

        generator = SQLGenerator(vanna_instance=mock_vanna_instance)
        result = generator.generate("테스트")

        assert isinstance(result, str)
        assert len(result.strip()) > 0

    def test_sql_generation_error_is_exception(self):
        """SQLGenerationError가 Exception 하위 클래스인지 확인"""
        assert issubclass(SQLGenerationError, Exception)

        error = SQLGenerationError("테스트 에러")
        assert str(error) == "테스트 에러"

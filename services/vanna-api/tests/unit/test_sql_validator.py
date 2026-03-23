"""
Step 6: SQLValidator 단위 테스트 — test-plan.md §3.4 (FR-04, SEC-04)
3계층 SQL 검증 (키워드 차단 → AST 파싱 → SELECT 전용 + 테이블 화이트리스트)
validate_sql() 함수와 SQLValidator 클래스 모두 검증
"""

import pytest
from unittest.mock import MagicMock

from src.pipeline.sql_validator import (
    validate_sql,
    SQLValidationError,
    SQLValidator,
    ALLOWED_TABLES,
    BLOCKED_KEYWORDS,
    DEFAULT_LIMIT,
)
from src.models.domain import ValidationResult


# ---------------------------------------------------------------------------
# validate_sql() 함수 테스트 — 순수 로직, Mock 불필요
# ---------------------------------------------------------------------------


class TestValidateSqlNormalSelect:
    """정상 SELECT 통과 테스트"""

    def test_validate_normal_select_passes(self):
        """정상 SELECT 통과 (FR-04, SEC-04)"""
        sql = """SELECT device_type, SUM(conversion_value) as revenue
                 FROM ad_combined_log_summary
                 WHERE year='2026' AND month='03' AND day='14'
                 GROUP BY device_type ORDER BY revenue DESC"""
        result = validate_sql(sql)
        assert "SELECT" in result.upper()
        assert "ad_combined_log_summary" in result.lower()

    def test_validate_select_with_existing_limit(self):
        """LIMIT 있는 SELECT는 그대로 통과"""
        sql = "SELECT * FROM ad_combined_log LIMIT 10"
        result = validate_sql(sql)
        assert "LIMIT 10" in result

    def test_validate_auto_adds_limit(self):
        """LIMIT 없는 SELECT에 자동 LIMIT 추가"""
        sql = "SELECT * FROM ad_combined_log"
        result = validate_sql(sql)
        assert f"LIMIT {DEFAULT_LIMIT}" in result


class TestValidateSqlKeywordBlocking:
    """1계층: 키워드 차단 테스트"""

    def test_validate_drop_table_blocked(self):
        """EX-3A: DROP TABLE 차단 (SEC-04, 1계층)"""
        with pytest.raises(SQLValidationError) as exc_info:
            validate_sql("DROP TABLE ad_combined_log_summary")
        assert "DROP" in exc_info.value.message

    def test_validate_delete_blocked(self):
        """DELETE 차단 (SEC-04, 1계층)"""
        with pytest.raises(SQLValidationError):
            validate_sql("DELETE FROM ad_combined_log_summary")

    def test_validate_insert_blocked(self):
        """INSERT 차단 (SEC-04, 1계층)"""
        with pytest.raises(SQLValidationError):
            validate_sql("INSERT INTO ad_combined_log_summary VALUES (1,2,3)")

    def test_validate_update_blocked(self):
        """UPDATE 차단 (SEC-04, 1계층)"""
        with pytest.raises(SQLValidationError):
            validate_sql("UPDATE ad_combined_log_summary SET col=1")

    def test_validate_truncate_blocked(self):
        """TRUNCATE 차단 (SEC-04, 1계층)"""
        with pytest.raises(SQLValidationError):
            validate_sql("TRUNCATE TABLE ad_combined_log_summary")

    @pytest.mark.parametrize("keyword", list(BLOCKED_KEYWORDS))
    def test_validate_all_blocked_keywords(self, keyword):
        """모든 차단 키워드 검증 (SEC-04, 1계층)"""
        with pytest.raises(SQLValidationError):
            validate_sql(f"{keyword} something ad_combined_log_summary")


class TestValidateSqlAstParsing:
    """2계층: AST 파싱 테스트"""

    def test_validate_insert_blocked_by_ast(self):
        """EX-3B: INSERT 차단 — AST 파싱 (SEC-04, 2계층)"""
        with pytest.raises(SQLValidationError):
            validate_sql("INSERT INTO ad_combined_log_summary VALUES (1,2,3)")

    def test_validate_select_into_blocked(self):
        """SELECT INTO 차단 (SEC-04)"""
        with pytest.raises(SQLValidationError):
            validate_sql("SELECT * INTO backup_table FROM ad_combined_log_summary")


class TestValidateSqlTableWhitelist:
    """3계층: 테이블 화이트리스트 테스트"""

    def test_validate_disallowed_table_blocked(self):
        """EX-3 변형: 허용 외 테이블 차단 (SEC-04, 3계층)"""
        with pytest.raises(SQLValidationError) as exc_info:
            validate_sql("SELECT * FROM secret_internal_table")
        assert "secret_internal_table" in exc_info.value.message

    def test_validate_allowed_table_ad_combined_log(self):
        """허용 테이블 ad_combined_log 통과"""
        result = validate_sql("SELECT * FROM ad_combined_log")
        assert "ad_combined_log" in result.lower()

    def test_validate_allowed_table_ad_combined_log_summary(self):
        """허용 테이블 ad_combined_log_summary 통과"""
        result = validate_sql("SELECT * FROM ad_combined_log_summary")
        assert "ad_combined_log_summary" in result.lower()


class TestValidateSqlEdgeCases:
    """경계값 및 복합 구문 테스트"""

    def test_validate_semicolon_multi_statement_blocked(self):
        """SELECT 1; DROP TABLE 복합 구문 차단 (SEC-04)"""
        with pytest.raises(SQLValidationError):
            validate_sql("SELECT 1; DROP TABLE ad_combined_log_summary")

    def test_validate_empty_string_blocked(self):
        """빈 문자열 차단 (SEC-04)"""
        with pytest.raises(SQLValidationError) as exc_info:
            validate_sql("")
        assert exc_info.value.error_code == "SQL_EMPTY"

    def test_validate_whitespace_only_blocked(self):
        """공백 문자열 차단"""
        with pytest.raises(SQLValidationError) as exc_info:
            validate_sql("   ")
        assert exc_info.value.error_code == "SQL_EMPTY"

    def test_validate_custom_allowed_tables(self):
        """커스텀 허용 테이블 세트 적용"""
        custom_tables = frozenset({"custom_table"})
        result = validate_sql("SELECT * FROM custom_table", allowed_tables=custom_tables)
        assert "custom_table" in result.lower()


# ---------------------------------------------------------------------------
# SQLValidator 클래스 테스트 — Athena EXPLAIN Mock 포함
# ---------------------------------------------------------------------------


class TestSQLValidatorClass:
    """SQLValidator 클래스 (파이프라인 Step 6 통합) 테스트"""

    @pytest.fixture
    def validator(self, mock_athena_client):
        """SQLValidator 인스턴스"""
        return SQLValidator(
            athena_client=mock_athena_client,
            database="test_db",
            workgroup="test-workgroup",
            s3_staging_dir="s3://test-bucket/staging/",
        )

    def test_validate_normal_select_returns_valid(self, validator):
        """정상 SELECT → is_valid=True (FR-04)"""
        sql = """SELECT device_type, SUM(conversion_value) as revenue
                 FROM ad_combined_log_summary
                 GROUP BY device_type"""
        result = validator.validate(sql)

        assert isinstance(result, ValidationResult)
        assert result.is_valid is True
        assert result.normalized_sql is not None

    def test_validate_drop_returns_invalid(self, validator):
        """DROP TABLE → is_valid=False (SEC-04)"""
        result = validator.validate("DROP TABLE ad_combined_log_summary")

        assert result.is_valid is False
        assert result.error_message is not None

    def test_validate_disallowed_table_returns_invalid(self, validator):
        """허용 외 테이블 → is_valid=False (SEC-04)"""
        result = validator.validate("SELECT * FROM secret_table")

        assert result.is_valid is False
        assert result.error_message is not None

    def test_validate_empty_sql_returns_invalid(self, validator):
        """빈 SQL → is_valid=False"""
        result = validator.validate("")

        assert result.is_valid is False

    def test_validate_athena_explain_failure_still_valid(self, validator, mock_athena_client):
        """Athena EXPLAIN 실패 시에도 정적 검증 통과하면 is_valid=True (진행 허용)"""
        mock_athena_client.get_query_execution.return_value = {
            "QueryExecution": {
                "Status": {
                    "State": "FAILED",
                    "StateChangeReason": "테이블을 찾을 수 없음",
                }
            }
        }

        sql = "SELECT * FROM ad_combined_log"
        result = validator.validate(sql)

        assert result.is_valid is True
        assert "EXPLAIN 경고" in (result.error_message or "")

    def test_validate_athena_client_error_still_valid(self, validator, mock_athena_client):
        """Athena ClientError 발생 시에도 is_valid=True (진행 허용)"""
        mock_athena_client.start_query_execution.side_effect = Exception("Athena 연결 실패")

        sql = "SELECT * FROM ad_combined_log"
        result = validator.validate(sql)

        assert result.is_valid is True

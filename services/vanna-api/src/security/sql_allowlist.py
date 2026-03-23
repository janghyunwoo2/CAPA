"""
SQL Allowlist — SEC-04 SQL Injection 방지 3계층 검증
sqlglot AST 파싱, SELECT만 허용, 허용 테이블 화이트리스트 검증
"""

import logging
from typing import Optional

import sqlglot
from sqlglot import exp
from sqlglot.errors import ParseError

logger = logging.getLogger(__name__)

# 허용 테이블 화이트리스트 (Design §5.2)
ALLOWED_TABLES: frozenset[str] = frozenset({
    "ad_combined_log",
    "ad_combined_log_summary",
})

# 차단 키워드 (DML/DDL 방지)
BLOCKED_KEYWORDS: frozenset[str] = frozenset({
    "DROP", "DELETE", "INSERT", "UPDATE", "TRUNCATE",
    "CREATE", "ALTER", "GRANT", "REVOKE", "EXEC",
})

# 기본 LIMIT 값 (결과 제한)
DEFAULT_LIMIT: int = 1000


class SQLValidationError(Exception):
    """SQL 검증 실패 시 발생하는 예외"""

    def __init__(self, message: str, error_code: str = "SQL_VALIDATION_FAILED") -> None:
        self.message = message
        self.error_code = error_code
        super().__init__(self.message)


def validate_sql(sql: str, allowed_tables: Optional[frozenset[str]] = None) -> str:
    """3계층 검증: 키워드 차단 -> sqlglot AST 파싱 -> SELECT 전용 + 테이블 화이트리스트

    Args:
        sql: 검증할 SQL 문자열
        allowed_tables: 허용 테이블 집합 (None이면 기본값 사용)

    Returns:
        검증 완료된 SQL (LIMIT 자동 추가 포함)

    Raises:
        SQLValidationError: 검증 실패 시
    """
    if allowed_tables is None:
        allowed_tables = ALLOWED_TABLES

    sql = sql.strip()
    if not sql:
        raise SQLValidationError("SQL이 비어있습니다", "SQL_EMPTY")

    # 1계층: 키워드 차단
    sql_upper = sql.upper()
    tokens = sql_upper.split()
    for blocked in BLOCKED_KEYWORDS:
        if blocked in tokens:
            logger.warning(f"차단된 SQL 키워드 감지: {blocked}")
            raise SQLValidationError(
                f"허용되지 않는 SQL 키워드: {blocked}",
                "SQL_BLOCKED_KEYWORD",
            )

    # 2계층: sqlglot AST 파싱
    try:
        parsed = sqlglot.parse(sql, dialect="presto")
    except ParseError as e:
        logger.warning(f"SQL 파싱 실패: {e}")
        raise SQLValidationError(
            "SQL 구문 분석에 실패했습니다",
            "SQL_PARSE_ERROR",
        )

    if not parsed or parsed[0] is None:
        raise SQLValidationError("SQL 파싱 결과가 비어있습니다", "SQL_PARSE_ERROR")

    statement = parsed[0]

    # 3계층-a: SELECT 문만 허용
    if not isinstance(statement, exp.Select):
        raise SQLValidationError(
            "SELECT 문만 허용됩니다",
            "SQL_NOT_SELECT",
        )

    # 3계층-b: 서브쿼리 포함 모든 테이블 참조를 화이트리스트 검증
    referenced_tables: set[str] = set()
    for table in statement.find_all(exp.Table):
        table_name = table.name.lower()
        if table_name:
            referenced_tables.add(table_name)

    if not referenced_tables:
        logger.warning("SQL에서 테이블 참조를 찾을 수 없습니다")
        raise SQLValidationError(
            "SQL에서 유효한 테이블 참조를 찾을 수 없습니다",
            "SQL_NO_TABLE",
        )

    disallowed = referenced_tables - {t.lower() for t in allowed_tables}
    if disallowed:
        logger.warning(f"허용되지 않은 테이블 참조: {disallowed}")
        raise SQLValidationError(
            f"허용되지 않는 테이블: {', '.join(sorted(disallowed))}",
            "SQL_DISALLOWED_TABLE",
        )

    # LIMIT 자동 추가 (없는 경우)
    if not statement.find(exp.Limit):
        sql = sql.rstrip(";") + f" LIMIT {DEFAULT_LIMIT}"
        logger.info(f"LIMIT {DEFAULT_LIMIT} 자동 추가")

    return sql

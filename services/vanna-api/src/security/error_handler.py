"""
Error Handler — SEC-07 에러 메시지 추상화
내부 스택트레이스/파일 경로 노출을 방지하고,
사용자에게는 일반적 에러 메시지만 반환
"""

import logging
from typing import Optional

from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)

# 에러 코드별 사용자 노출 메시지 매핑
_ERROR_MESSAGES: dict[str, str] = {
    "SQL_VALIDATION_FAILED": "SQL 검증에 실패했습니다",
    "SQL_EMPTY": "SQL이 비어있습니다",
    "SQL_BLOCKED_KEYWORD": "허용되지 않는 SQL 키워드가 포함되어 있습니다",
    "SQL_PARSE_ERROR": "SQL 구문 분석에 실패했습니다",
    "SQL_NOT_SELECT": "SELECT 문만 허용됩니다",
    "SQL_NO_TABLE": "유효한 테이블 참조를 찾을 수 없습니다",
    "SQL_DISALLOWED_TABLE": "허용되지 않는 테이블이 참조되었습니다",
    "QUESTION_EMPTY": "질문이 비어있습니다",
    "QUESTION_TOO_LONG": "질문이 너무 깁니다",
    "PROMPT_INJECTION_DETECTED": "허용되지 않는 입력 패턴이 감지되었습니다",
    "INTENT_OUT_OF_SCOPE": "범위 외 질문입니다",
    "SQL_GENERATION_FAILED": "SQL 생성에 실패했습니다",
    "QUERY_TIMEOUT": "쿼리 실행 시간이 초과되었습니다",
    "SERVICE_UNAVAILABLE": "서비스를 일시적으로 사용할 수 없습니다",
}

# 기본 에러 메시지 (매핑되지 않은 에러)
_DEFAULT_ERROR_MESSAGE: str = "요청 처리 중 오류가 발생했습니다"


def sanitize_error_response(
    error: Exception,
    status_code: int = 500,
    error_code: Optional[str] = None,
) -> HTTPException:
    """내부 오류를 사용자 안전한 HTTPException으로 변환

    상세 오류 정보는 logger.error()로만 기록하고,
    사용자에게는 일반화된 메시지만 반환한다.

    Args:
        error: 원본 예외
        status_code: HTTP 상태 코드
        error_code: 에러 코드 (매핑 메시지 조회용)

    Returns:
        사용자 노출 가능한 HTTPException
    """
    # 상세 오류는 서버 로그에만 기록
    logger.error(f"내부 오류 [{error_code or 'UNKNOWN'}]: {str(error)}", exc_info=True)

    # 사용자에게는 일반화된 메시지만 반환
    user_message = _ERROR_MESSAGES.get(error_code or "", _DEFAULT_ERROR_MESSAGE)

    return HTTPException(
        status_code=status_code,
        detail={
            "error_code": error_code or "INTERNAL_ERROR",
            "message": user_message,
        },
    )


async def generic_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """FastAPI 글로벌 예외 핸들러 — 처리되지 않은 예외를 안전하게 변환

    app.add_exception_handler(Exception, generic_exception_handler) 로 등록
    """
    logger.error(
        f"처리되지 않은 예외: {request.method} {request.url.path} — {str(exc)}",
        exc_info=True,
    )

    return JSONResponse(
        status_code=500,
        content={
            "error_code": "INTERNAL_ERROR",
            "message": _DEFAULT_ERROR_MESSAGE,
        },
    )

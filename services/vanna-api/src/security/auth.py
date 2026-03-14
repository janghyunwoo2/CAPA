"""
Internal Service Token 인증 미들웨어 — SEC-17
slack-bot -> vanna-api 간 내부 서비스 인증
"""

import logging
import os
import secrets

from fastapi import HTTPException, Request
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import Response

logger = logging.getLogger(__name__)

# 환경변수에서 내부 서비스 토큰 로드 (Design §5.4)
INTERNAL_SERVICE_TOKEN: str = os.getenv("INTERNAL_API_TOKEN", "")

# 인증 제외 경로 (헬스 체크 등)
_EXEMPT_PATHS: frozenset[str] = frozenset({
    "/health",
    "/docs",
    "/openapi.json",
    "/redoc",
})


class InternalTokenMiddleware(BaseHTTPMiddleware):
    """X-Internal-Token 헤더 검증 미들웨어

    모든 요청에 대해 X-Internal-Token 헤더를 검증한다.
    INTERNAL_API_TOKEN 환경변수가 비어있으면 인증을 건너뛴다 (개발 환경).
    """

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        # 인증 제외 경로 확인
        if request.url.path in _EXEMPT_PATHS:
            return await call_next(request)

        # 토큰 미설정 시 인증 건너뜀 (개발 환경 호환)
        if not INTERNAL_SERVICE_TOKEN:
            logger.warning("INTERNAL_API_TOKEN 미설정 — 인증 건너뜀 (개발 환경만 허용)")
            return await call_next(request)

        # X-Internal-Token 헤더 검증
        token = request.headers.get("X-Internal-Token", "")
        if not token:
            logger.warning(f"인증 헤더 누락: {request.method} {request.url.path}")
            raise HTTPException(
                status_code=403,
                detail="접근이 거부되었습니다",
            )

        if not secrets.compare_digest(token, INTERNAL_SERVICE_TOKEN):
            logger.warning(f"인증 토큰 불일치: {request.method} {request.url.path}")
            raise HTTPException(
                status_code=403,
                detail="접근이 거부되었습니다",
            )

        return await call_next(request)

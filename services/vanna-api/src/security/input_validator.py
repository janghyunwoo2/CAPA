"""
Input Validator — SEC-08 Prompt Injection 방지
자연어 질문 입력에 대한 길이 제한 및 위험 패턴 차단
"""

import logging
import re
from typing import Optional

logger = logging.getLogger(__name__)

# 최대 질문 길이 (Design §3.2 SEC-08)
MAX_QUESTION_LENGTH: int = 500

# Prompt Injection 위험 패턴
_INJECTION_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"ignore\s+(all\s+)?(previous\s+)?instructions", re.IGNORECASE),
    re.compile(r"ignore\s+above", re.IGNORECASE),
    re.compile(r"disregard\s+(all\s+)?(previous\s+)?instructions", re.IGNORECASE),
    re.compile(r"forget\s+(all\s+)?(previous\s+)?instructions", re.IGNORECASE),
    re.compile(r"you\s+are\s+now\s+", re.IGNORECASE),
    re.compile(r"act\s+as\s+(a\s+)?", re.IGNORECASE),
    re.compile(r"new\s+instructions?\s*:", re.IGNORECASE),
    re.compile(r"system\s*prompt", re.IGNORECASE),
    re.compile(r"<\s*/?system\s*>", re.IGNORECASE),
    re.compile(r"<\s*/?instructions?\s*>", re.IGNORECASE),
    re.compile(r"override\s+(previous\s+)?instructions", re.IGNORECASE),
    re.compile(r"reveal\s+(your\s+)?(system\s+)?prompt", re.IGNORECASE),
    re.compile(r"show\s+(me\s+)?(your\s+)?(system\s+)?prompt", re.IGNORECASE),
    re.compile(r"print\s+(your\s+)?(system\s+)?prompt", re.IGNORECASE),
    re.compile(r"what\s+(are\s+)?(your\s+)?instructions", re.IGNORECASE),
]


class InputValidationError(Exception):
    """입력 검증 실패 시 발생하는 예외"""

    def __init__(self, message: str, error_code: str = "INPUT_VALIDATION_FAILED") -> None:
        self.message = message
        self.error_code = error_code
        super().__init__(self.message)


def validate_question(question: str) -> str:
    """자연어 질문 입력 검증

    Args:
        question: 사용자 질문 문자열

    Returns:
        검증 완료된 질문 (앞뒤 공백 제거)

    Raises:
        InputValidationError: 검증 실패 시
    """
    if not question or not question.strip():
        raise InputValidationError("질문이 비어있습니다", "QUESTION_EMPTY")

    question = question.strip()

    # 길이 제한 (SEC-08)
    if len(question) > MAX_QUESTION_LENGTH:
        logger.warning(f"질문 길이 초과: {len(question)}자 (최대 {MAX_QUESTION_LENGTH}자)")
        raise InputValidationError(
            f"질문은 {MAX_QUESTION_LENGTH}자 이내로 입력해 주세요",
            "QUESTION_TOO_LONG",
        )

    # Prompt Injection 패턴 차단
    detected: Optional[str] = _detect_injection(question)
    if detected is not None:
        logger.warning(f"Prompt Injection 패턴 감지: {detected}")
        raise InputValidationError(
            "허용되지 않는 입력 패턴이 감지되었습니다",
            "PROMPT_INJECTION_DETECTED",
        )

    return question


def _detect_injection(text: str) -> Optional[str]:
    """Prompt Injection 패턴 감지

    Returns:
        감지된 패턴 문자열 (없으면 None)
    """
    for pattern in _INJECTION_PATTERNS:
        match = pattern.search(text)
        if match:
            return match.group(0)
    return None

"""
Step 1: IntentClassifier — LLM 기반 의도 분류
설계 문서 §2.3.2 기준
출력: IntentType (DATA_QUERY / GENERAL / OUT_OF_SCOPE)
"""

import logging
from typing import Optional
import anthropic
from ..models.domain import IntentType

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = """당신은 광고 데이터 분석 서비스의 질의 의도 분류기입니다.
사용자의 질문을 다음 세 가지 중 하나로 분류하세요:

- DATA_QUERY: 광고 로그 데이터에 대한 SQL 조회가 필요한 질문
  (예: CTR, CVR, ROAS, 클릭수, 전환율, 캠페인 성과, 광고비 등)
- GENERAL: SQL 조회 없이 답할 수 있는 일반 질문
  (예: "CTR이 뭐야?", "광고 플랫폼 종류 알려줘")
- OUT_OF_SCOPE: 광고 도메인과 무관한 질문
  (예: 날씨, 요리, 스포츠 등)

반드시 DATA_QUERY, GENERAL, OUT_OF_SCOPE 중 하나만 응답하세요. 다른 텍스트는 포함하지 마세요."""


class IntentClassifier:
    """Step 1 — 자연어 질의 의도 분류"""

    def __init__(self, api_key: str, model: str = "claude-haiku-4-5-20251001") -> None:
        self._client = anthropic.Anthropic(api_key=api_key)
        self._model = model

    def classify(self, question: str) -> IntentType:
        """질문을 분류하여 IntentType 반환.
        LLM 호출 실패 시 DATA_QUERY로 fallback (graceful degradation).
        """
        try:
            response = self._client.messages.create(
                model=self._model,
                max_tokens=20,
                system=_SYSTEM_PROMPT,
                messages=[{"role": "user", "content": question}],
            )
            raw = response.content[0].text.strip().upper()
            logger.info(f"의도 분류 결과: {raw} (질문: {question[:50]}...)")

            if raw == "DATA_QUERY":
                return IntentType.DATA_QUERY
            elif raw == "GENERAL":
                return IntentType.GENERAL
            elif raw == "OUT_OF_SCOPE":
                return IntentType.OUT_OF_SCOPE
            else:
                logger.warning(f"예상치 못한 의도 분류 응답: {raw}, DATA_QUERY로 fallback")
                return IntentType.DATA_QUERY

        except anthropic.APIError as e:
            logger.error(f"의도 분류 LLM 호출 실패: {e}")
            return IntentType.DATA_QUERY
        except Exception as e:
            logger.error(f"의도 분류 중 예외 발생: {e}")
            return IntentType.DATA_QUERY

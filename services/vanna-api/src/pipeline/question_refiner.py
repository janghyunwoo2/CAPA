"""
Step 2: QuestionRefiner — 인사말/부연설명 제거, 핵심 질문 추출
설계 문서 §2.3.2 기준
실패 시 원본 질문 그대로 사용 (graceful degradation)
"""

import logging
from typing import Optional
import anthropic
from ..prompt_loader import load_prompt

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = """당신은 광고 데이터 분석 질의 정제기입니다.
사용자의 질문에서 인사말, 부연설명, 중복 표현을 제거하고
데이터 조회에 필요한 핵심 질문만 추출하세요.

규칙:
- 핵심 질문만 반환 (한국어)
- 불필요한 설명 없이 질문 텍스트만 출력
- 원본 의도를 유지하면서 간결하게 정제

예시:
입력: "안녕하세요! 혹시 지난주 CTR이 제일 높은 캠페인 5개 좀 알 수 있을까요? 부탁드립니다"
출력: "지난주 CTR이 가장 높은 캠페인 5개"
"""


class QuestionRefiner:
    """Step 2 — 질문 정제"""

    def __init__(self, api_key: str, model: str = "claude-haiku-4-5-20251001") -> None:
        self._client = anthropic.Anthropic(api_key=api_key)
        self._model = model

    def refine(self, question: str, conversation_history: Optional[list] = None) -> str:
        """질문을 정제하여 반환.
        LLM 호출 실패 시 원본 질문 그대로 반환 (graceful degradation).
        conversation_history: 멀티턴 대화 이력 (현재 미사용, 시그니처 호환 용도).
        """
        try:
            prompts = load_prompt("question_refiner")
            system = prompts.get("system", _SYSTEM_PROMPT)
            response = self._client.messages.create(
                model=self._model,
                max_tokens=200,
                system=system,
                messages=[{"role": "user", "content": question}],
            )
            refined = response.content[0].text.strip()
            logger.info(f"질문 정제: '{question[:50]}' → '{refined[:50]}'")
            return refined if refined else question

        except anthropic.APIError as e:
            logger.error(f"질문 정제 LLM 호출 실패: {e}, 원본 질문 사용")
            return question
        except Exception as e:
            logger.error(f"질문 정제 중 예외 발생: {e}, 원본 질문 사용")
            return question

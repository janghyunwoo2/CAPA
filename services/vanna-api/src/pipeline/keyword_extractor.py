"""
Step 3: KeywordExtractor — 광고 도메인 핵심 명사/지표 추출
설계 문서 §2.3.2 기준
실패 시 빈 리스트 반환 → 전체 질문으로 RAG 검색
"""

import json
import logging
import anthropic

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = """당신은 광고 도메인 키워드 추출기입니다.
사용자의 질문에서 광고 분석에 관련된 핵심 명사와 지표를 추출하세요.

추출 대상:
- 광고 지표: CTR, CVR, ROAS, CPA, CPC, 클릭률, 전환율, 광고비 등
- 도메인 객체: 캠페인, 광고, 광고주, 디바이스, 플랫폼 등
- 시간 표현: 어제, 지난주, 지난달, 최근 7일 등
- 테이블 관련 컬럼명: campaign_id, device_type, food_category 등

JSON 배열 형식으로만 응답하세요:
["키워드1", "키워드2", ...]

키워드가 없으면 빈 배열 []을 반환하세요."""


class KeywordExtractor:
    """Step 3 — 도메인 키워드 추출"""

    def __init__(self, api_key: str, model: str = "claude-haiku-4-5-20251001") -> None:
        self._client = anthropic.Anthropic(api_key=api_key)
        self._model = model

    def extract(self, question: str) -> list[str]:
        """질문에서 키워드를 추출하여 반환.
        LLM 호출 실패 시 빈 리스트 반환 → RAG 전체 질문 검색으로 fallback.
        """
        try:
            response = self._client.messages.create(
                model=self._model,
                max_tokens=200,
                system=_SYSTEM_PROMPT,
                messages=[{"role": "user", "content": question}],
            )
            raw = response.content[0].text.strip()
            keywords: list[str] = json.loads(raw)
            logger.info(f"키워드 추출 결과: {keywords}")
            return keywords if isinstance(keywords, list) else []

        except (anthropic.APIError, json.JSONDecodeError, ValueError) as e:
            logger.error(f"키워드 추출 실패: {e}, 빈 리스트 반환")
            return []
        except Exception as e:
            logger.error(f"키워드 추출 중 예외 발생: {e}, 빈 리스트 반환")
            return []

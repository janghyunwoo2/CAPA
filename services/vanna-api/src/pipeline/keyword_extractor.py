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

[중요] 반드시 질문에 직접 언급된 단어/표현만 추출하세요.
질문에 없는 관련 지표나 컬럼명을 절대 추가하지 마세요.
예시:
  - "어제 CTR 보여줘" → ["CTR", "어제"]  ← 올바름
  - "어제 CTR 보여줘" → ["CTR", "ROAS", "cost"]  ← 잘못됨 (ROAS, cost는 질문에 없음)

추출 대상 (질문에 언급된 것만):
- 광고 지표: CTR, CVR, ROAS, CPA, CPC, 클릭률, 전환율, 광고비 등
- 도메인 객체: 캠페인, 광고, 광고주, 디바이스, 플랫폼 등
- 시간 표현: 어제, 지난주, 지난달, 최근 7일 등
- 컬럼명: campaign_id, device_type, food_category 등

JSON 배열 형식으로만 응답하세요:
["키워드1", "키워드2", ...]

키워드가 없으면 빈 배열 []을 반환하세요."""

# 스키마 기반 허용 키워드 화이트리스트 — RAG 검색 오염 방지
_ALLOWED_KEYWORDS: frozenset[str] = frozenset({
    # 실제 컬럼명 (ad_combined_log + ad_combined_log_summary)
    "impression_id", "user_id", "ad_id", "campaign_id", "advertiser_id",
    "platform", "device_type", "os", "delivery_region", "store_id",
    "food_category", "ad_position", "ad_format", "keyword",
    "cost_per_impression", "cost_per_click", "is_click", "click_id",
    "is_conversion", "conversion_id", "conversion_type", "conversion_value",
    "product_id", "quantity", "attribution_window",
    "year", "month", "day", "hour",
    # 표준 지표 (영문 대문자)
    "CTR", "CVR", "ROAS", "CPA", "CPC",
    # 표준 지표 (한국어)
    "클릭률", "전환율", "노출수", "클릭수", "전환수", "노출", "클릭", "전환", "비용", "광고비",
    # 도메인 객체
    "캠페인", "광고", "광고주", "디바이스", "플랫폼", "지역", "카테고리", "시간대", "기기",
    # 컬럼 범주값
    "web", "app_ios", "app_android", "tablet_ios", "tablet_android",
    "mobile", "tablet", "desktop", "others",
    "ios", "android", "macos", "windows",
    "purchase", "signup", "download", "view_content", "add_to_cart",
    "display", "native", "video", "discount_coupon",
    "home_top_rolling", "list_top_fixed", "search_ai_recommend", "checkout_bottom",
    "1day", "7day", "30day",
    # 시간 표현
    "어제", "오늘", "이번달", "지난달", "지난주", "이번주", "최근7일",
})


def _filter_keywords(keywords: list[str]) -> list[str]:
    """추출된 키워드를 화이트리스트와 교차 검증 — 없는 컬럼명/지표 자동 제거.

    대소문자 무관 비교 (CTR, ctr, Ctr 모두 허용).
    질문에서 추출했으나 실제 스키마/지표에 없는 hallucination 키워드를 제거하여
    RAG 검색 쿼리 오염을 방지한다.
    """
    allowed_lower = {k.lower() for k in _ALLOWED_KEYWORDS}
    return [kw for kw in keywords if kw.strip().lower() in allowed_lower]


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
            # markdown 코드블록 제거 (```json ... ``` 형식 처리)
            if raw.startswith("```"):
                lines = raw.split("\n")
                raw = "\n".join(lines[1:-1]) if len(lines) > 2 else ""
            keywords: list[str] = json.loads(raw) if raw else []
            if not isinstance(keywords, list):
                keywords = []
            # 화이트리스트 필터: hallucination 키워드 제거
            keywords = _filter_keywords(keywords)
            logger.info(f"키워드 추출 결과 (필터 후): {keywords}")
            return keywords

        except (anthropic.APIError, json.JSONDecodeError, ValueError) as e:
            logger.error(f"키워드 추출 실패: {e}, 빈 리스트 반환")
            return []
        except Exception as e:
            logger.error(f"키워드 추출 중 예외 발생: {e}, 빈 리스트 반환")
            return []

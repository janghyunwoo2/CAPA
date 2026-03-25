"""
Step 3.5: SchemaMapper — 키워드 → 테이블/컬럼 매핑
설계 문서 §3.3 기준

SUMMARY_EXCLUSIVE 키워드 → ad_combined_log_summary (확정)
LOG_EXCLUSIVE 키워드    → ad_combined_log (확정)
충돌 또는 NEUTRAL       → 모호 처리 (벡터 검색 위임)
"""

from ..models.rag import SchemaHint

# ad_combined_log_summary에서만 조회 가능한 지표 (전환 관련)
SUMMARY_EXCLUSIVE: frozenset[str] = frozenset({
    "cvr", "roas", "전환", "전환율", "전환수", "is_conversion",
    "conversion", "수익률", "전환매출", "전환금액",
})

# ad_combined_log에서만 조회 가능한 분석 (시간대 파티션 필요)
LOG_EXCLUSIVE: frozenset[str] = frozenset({
    "시간대", "피크타임", "hour", "시간별", "hourly",
})

# 어느 테이블이든 가능하지만 summary를 선호하는 지표
NEUTRAL_SUMMARY_PREFER: frozenset[str] = frozenset({
    "ctr", "클릭률", "클릭수", "노출수", "cpc", "cpm",
    "impression", "click", "노출", "클릭",
})


class SchemaMapper:
    """키워드 리스트로부터 SchemaHint를 생성하는 규칙 기반 매퍼"""

    def map(self, keywords: list[str]) -> SchemaHint:
        """
        Args:
            keywords: Step 3 KeywordExtractor 출력 키워드 리스트

        Returns:
            SchemaHint — tables, columns, confidence, is_definitive 포함
        """
        if not keywords:
            return SchemaHint(
                tables=[], columns=[], confidence=0.5, is_definitive=False
            )

        kw_lower = {kw.lower() for kw in keywords}

        has_summary = bool(kw_lower & SUMMARY_EXCLUSIVE)
        has_log = bool(kw_lower & LOG_EXCLUSIVE)
        has_neutral = bool(kw_lower & NEUTRAL_SUMMARY_PREFER)

        # 충돌: summary 확정 키워드 + log 확정 키워드 동시 존재
        if has_summary and has_log:
            return SchemaHint(
                tables=[], columns=[], confidence=0.5, is_definitive=False
            )

        # 확정: summary 테이블
        if has_summary:
            return SchemaHint(
                tables=["ad_combined_log_summary"],
                columns=[],
                confidence=1.0,
                is_definitive=True,
            )

        # 확정: log 테이블 (시간대 파티션 필요)
        if has_log:
            return SchemaHint(
                tables=["ad_combined_log"],
                columns=[],
                confidence=1.0,
                is_definitive=True,
            )

        # 선호: summary 쪽이지만 확정 불가
        if has_neutral:
            return SchemaHint(
                tables=["ad_combined_log_summary"],
                columns=[],
                confidence=0.8,
                is_definitive=False,
            )

        # 완전 모호: 매핑 가능한 키워드 없음
        return SchemaHint(
            tables=[], columns=[], confidence=0.5, is_definitive=False
        )

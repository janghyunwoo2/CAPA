"""Claude API 기반 광고 성과 보고서 작성 모듈.

Athena에서 조회한 DataFrame 데이터를 Claude API에 전달하여
마크다운 형식의 분석 보고서를 생성합니다.
"""

import logging
import os

import pandas as pd
from anthropic import Anthropic
from dotenv import load_dotenv

load_dotenv()

logger: logging.Logger = logging.getLogger(__name__)


class ReportWriter:
    """Claude API를 사용하여 광고 성과 보고서를 작성합니다."""

    def __init__(self) -> None:
        api_key: str | None = os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            raise ValueError("ANTHROPIC_API_KEY 환경 변수가 설정되지 않았습니다.")

        self.client: Anthropic = Anthropic(api_key=api_key)
        self.model: str = os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-4-5-20250929")

    def generate_report(
        self,
        daily_df: pd.DataFrame,
        kpi_df: pd.DataFrame,
        category_df: pd.DataFrame,
        shop_df: pd.DataFrame,
        start_date: str,
        end_date: str,
    ) -> str:
        """광고 성과 데이터를 분석하여 마크다운 보고서를 생성합니다.

        Args:
            daily_df: 일별 성과 DataFrame
            kpi_df: KPI 요약 DataFrame
            category_df: 카테고리별 성과 DataFrame
            shop_df: Shop별 성과 DataFrame
            start_date: 리포트 시작 날짜
            end_date: 리포트 종료 날짜

        Returns:
            마크다운 형식의 보고서 텍스트
        """
        data_summary: str = self._format_data(
            daily_df, kpi_df, category_df, shop_df
        )
        prompt: str = self._build_prompt(data_summary, start_date, end_date)

        logger.info("Claude API로 보고서 생성 요청 중...")

        message = self.client.messages.create(
            model=self.model,
            max_tokens=4000,
            messages=[{"role": "user", "content": prompt}],
        )

        report_text: str = message.content[0].text
        logger.info("보고서 생성 완료")
        return report_text

    def _format_data(
        self,
        daily_df: pd.DataFrame,
        kpi_df: pd.DataFrame,
        category_df: pd.DataFrame,
        shop_df: pd.DataFrame,
    ) -> str:
        """DataFrame들을 LLM이 읽기 쉬운 텍스트로 변환합니다."""
        sections: list[str] = []

        if not daily_df.empty:
            sections.append(f"[일별 성과 데이터]\n{daily_df.to_markdown(index=False)}")

        if not kpi_df.empty:
            sections.append(f"[KPI 요약]\n{kpi_df.to_markdown(index=False)}")

        if not category_df.empty:
            sections.append(f"[카테고리별 성과]\n{category_df.to_markdown(index=False)}")

        if not shop_df.empty:
            sections.append(f"[Shop별 성과]\n{shop_df.to_markdown(index=False)}")

        return "\n\n".join(sections)

    def _build_prompt(
        self, data_summary: str, start_date: str, end_date: str
    ) -> str:
        """LLM 프롬프트를 구성합니다."""
        return f"""당신은 온라인 광고 성과 분석 전문가입니다.
아래의 광고 성과 데이터를 분석하여 한국어로 리포트를 작성해주세요.

기간: {start_date} ~ {end_date}

{data_summary}

다음 구조로 마크다운 리포트를 작성해주세요:

## Executive Summary
- 전체 성과를 3~4문장으로 요약

## 주요 지표 분석
- 노출(impressions), 클릭(clicks), 전환(conversions) 분석
- CTR, CVR, ROAS 해석
- 비용 효율성 평가

## 일별 트렌드 분석
- 기간 내 성과 변동 추이
- 특이 사항 (급증, 급감 등)

## 카테고리별 성과
- 카테고리별 비교 분석
- 상위/하위 카테고리 식별

## Shop별 성과
- Shop별 비교 분석
- 성과 우수/부진 Shop 식별

## 인사이트 및 추천 사항
- 데이터 기반 핵심 인사이트 3~5개
- 구체적인 개선 추천 사항

주의사항:
- 숫자는 천 단위 구분자를 사용해주세요 (예: 1,234)
- 비율은 소수점 둘째 자리까지 표시해주세요
- 마크다운 제목은 ##(h2)부터 시작해주세요 (h1은 PDF 제목에 사용)
- 데이터가 비어있는 섹션은 "데이터 없음"으로 표시해주세요"""

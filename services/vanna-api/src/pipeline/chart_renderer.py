"""
Step 10.5: ChartRenderer — matplotlib Agg PNG → Base64
설계 문서 §2.3.2, §5.8 (SEC-24 차트 PII 마스킹) 기준
NFR-08: MPLBACKEND=Agg 강제 설정
실패 시 None 반환 (텍스트만 반환)
"""

import base64
import io
import logging
import os
from typing import Optional

# NFR-08: 서버 환경에서 GUI 없이 렌더링하기 위해 Agg 백엔드 강제 설정
os.environ.setdefault("MPLBACKEND", "Agg")

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm
import pandas as pd

from .ai_analyzer import mask_sensitive_data
from ..models.domain import ChartType, QueryResults

logger = logging.getLogger(__name__)


class ChartRenderer:
    """Step 10.5 — matplotlib 차트 렌더링 (Agg 백엔드, Base64 PNG)"""

    def render(
        self,
        query_results: QueryResults,
        chart_type: ChartType,
    ) -> Optional[str]:
        """쿼리 결과를 차트로 렌더링하여 Base64 문자열로 반환.
        실패하거나 chart_type=NONE 이면 None 반환.
        """
        if chart_type == ChartType.NONE:
            return None
        if not query_results.rows or not query_results.columns:
            logger.info("차트 렌더링 스킵: 결과 없음")
            return None

        try:
            # SEC-24: PII 마스킹 적용
            masked_rows = mask_sensitive_data(query_results.rows)
            df = pd.DataFrame(masked_rows, columns=query_results.columns)

            fig = self._create_chart(df, chart_type)
            if fig is None:
                return None

            buf = io.BytesIO()
            fig.savefig(buf, format="png", bbox_inches="tight", dpi=100)
            plt.close(fig)
            buf.seek(0)
            encoded = base64.b64encode(buf.read()).decode("utf-8")
            logger.info(f"차트 렌더링 완료: {chart_type.value}, {len(encoded)} bytes")
            return encoded

        except Exception as e:
            logger.error(f"차트 렌더링 실패: {e}")
            return None

    def _create_chart(
        self, df: pd.DataFrame, chart_type: ChartType
    ) -> Optional[plt.Figure]:
        """차트 유형에 따라 Figure를 생성하여 반환"""
        if df.empty or len(df.columns) < 1:
            return None

        fig, ax = plt.subplots(figsize=(10, 6))

        try:
            x_col = df.columns[0]
            y_col = df.columns[1] if len(df.columns) > 1 else df.columns[0]

            # 숫자형 변환 시도
            try:
                df[y_col] = pd.to_numeric(df[y_col], errors="coerce")
            except Exception:
                pass

            if chart_type == ChartType.BAR:
                ax.bar(df[x_col].astype(str), df[y_col])
                ax.set_xlabel(x_col)
                ax.set_ylabel(y_col)
                plt.xticks(rotation=45, ha="right")

            elif chart_type == ChartType.LINE:
                ax.plot(df[x_col].astype(str), df[y_col], marker="o")
                ax.set_xlabel(x_col)
                ax.set_ylabel(y_col)
                plt.xticks(rotation=45, ha="right")

            elif chart_type == ChartType.PIE:
                # PIE는 최대 6개 카테고리
                pie_df = df.head(6)
                ax.pie(
                    pie_df[y_col].fillna(0),
                    labels=pie_df[x_col].astype(str),
                    autopct="%1.1f%%",
                )

            elif chart_type == ChartType.SCATTER:
                if len(df.columns) >= 2:
                    ax.scatter(df[x_col], df[y_col])
                    ax.set_xlabel(x_col)
                    ax.set_ylabel(y_col)

            else:
                plt.close(fig)
                return None

            ax.set_title(f"{y_col} by {x_col}", fontsize=12)
            fig.tight_layout()
            return fig

        except Exception as e:
            logger.error(f"차트 Figure 생성 실패: {e}")
            plt.close(fig)
            return None

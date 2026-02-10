"""분석기: 집계 메트릭을 로드해 리포트(CSV)를 생성한다."""
from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Optional

import pandas as pd


@dataclass
class AdAnalytics:
    """간단한 분석 리포트 생성기"""

    metrics_path: str = "data/processed/metrics.parquet"
    out_csv: str = "data/analysis/report_top_ads.csv"

    def generate_report(self, top_n: int = 20) -> None:
        df = pd.read_parquet(self.metrics_path)

        # 캠페인/광고별 주요 지표 상위 추출
        # CTR로 상위 광고 추출 (충분한 노출이 있는 광고만 고려)
        df['impressions'] = df['impressions'].astype(int)
        df['clicks'] = df['clicks'].astype(int)
        df['conversions'] = df['conversions'].astype(int)

        threshold = 10
        filtered = df[df.impressions >= threshold].copy()

        top_by_ctr = filtered.sort_values('ctr', ascending=False).head(top_n)

        os.makedirs(os.path.dirname(self.out_csv), exist_ok=True)
        top_by_ctr.to_csv(self.out_csv, index=False)

        print(f"분석 리포트 생성 완료 -> {self.out_csv}")


if __name__ == "__main__":
    a = AdAnalytics()
    a.generate_report()

"""시각화 유틸리티: 집계 메트릭을 플롯으로 저장한다."""
from __future__ import annotations

import os
from typing import Optional

import matplotlib.pyplot as plt
import pandas as pd
import seaborn as sns


def plot_ctr_over_time(metrics_path: str = "data/processed/metrics.parquet", out_dir: str = "data/outputs") -> None:
    """광고별 일별 CTR 추이를 시각화하고 PNG로 저장한다."""
    os.makedirs(out_dir, exist_ok=True)
    df = pd.read_parquet(metrics_path)

    # 날짜 처리
    df['date'] = pd.to_datetime(df['date'])

    # 전체 CTR 추이 (일별 평균)
    daily = df.groupby('date')['ctr'].mean().reset_index()

    sns.set(style='whitegrid')
    plt.figure(figsize=(10, 5))
    sns.lineplot(data=daily, x='date', y='ctr')
    plt.title('Daily Average CTR')
    plt.tight_layout()
    out_path = os.path.join(out_dir, 'daily_ctr.png')
    plt.savefig(out_path)
    plt.close()

    # 상위 광고별 CTR (상위 5)
    latest = df.sort_values('date').groupby('ad_id').tail(1)
    top_ads = latest.sort_values('ctr', ascending=False).head(5)['ad_id'].tolist()

    plt.figure(figsize=(10, 6))
    subset = df[df.ad_id.isin(top_ads)]
    sns.lineplot(data=subset, x='date', y='ctr', hue='ad_id')
    plt.title('Top 5 Ads CTR Over Time')
    plt.tight_layout()
    out_path2 = os.path.join(out_dir, 'top5_ads_ctr.png')
    plt.savefig(out_path2)
    plt.close()

    print(f"시각화 결과 저장: {out_path}, {out_path2}")


if __name__ == "__main__":
    plot_ctr_over_time()

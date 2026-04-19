"""시각화 유틸리티: 집계 메트릭을 플롯으로 저장한다."""
from __future__ import annotations

import os
from typing import Any


def plot_ctr_over_time(
    metrics_path: str = "/opt/airflow/data/processed/metrics.parquet",
    out_dir: str = "/opt/airflow/data/outputs"
) -> None:
    """광고별 일별 CTR 추이를 시각화하고 PNG로 저장한다.
    
    라이브러리(`matplotlib`, `pandas`, `seaborn`)는 함수 내부에서 지연 임포트합니다.
    이로 인해 Airflow가 DAG를 파싱할 때 해당 패키지가 없더라도 import 에러가 발생하지 않습니다.

    2개의 PNG 파일을 생성합니다:
    1. daily_ctr.png: 전체 일별 평균 CTR 추이
    2. top5_ads_ctr.png: 상위 5개 광고의 CTR 시계열 비교
    
    Args:
        metrics_path: 입력 Parquet 파일 경로 (집계 메트릭)
        out_dir: 출력 디렉토리 경로
    
    Returns:
        None (부작용: PNG 파일 2개 생성)
    """
    # 무거운 라이브러리 지연 임포트
    import matplotlib.pyplot as plt  # type: ignore
    import pandas as pd  # type: ignore
    import seaborn as sns  # type: ignore

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

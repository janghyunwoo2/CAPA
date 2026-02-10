"""로컬 데이터 처리기: raw 로그(Parquet) -> 집계 메트릭(Parquet)

AWS 대응 지점 표시:
- 로컬: 로컬 파일 시스템의 `data/raw` -> `data/processed`
- AWS: 수집은 Kinesis/Firehose, 저장은 S3 (Glue 카탈로그/Parquet). 아래 TODO에 표기.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Optional

import pandas as pd


@dataclass
class AdDataProcessor:
    """원시 로그를 읽어 일별/광고별 메트릭으로 집계한다."""

    raw_path: str = "data/raw/logs.parquet"
    out_path: str = "data/processed/metrics.parquet"

    def process(self) -> None:
        # 로컬 파일에서 읽기
        df = pd.read_parquet(self.raw_path)

        # 시간과 날짜 컬럼 정리
        if "timestamp" in df.columns:
            df["timestamp"] = pd.to_datetime(df["timestamp"])
            df["date"] = df["timestamp"].dt.date

        # 집계: 광고(ad_id)와 날짜별로 노출/클릭/전환 집계
        impressions = (
            df[df.event_type == "impression"]
            .groupby(["ad_id", "date"])['event_id']
            .count()
            .rename('impressions')
        )

        clicks = (
            df[df.event_type == "click"]
            .groupby(["ad_id", "date"])['event_id']
            .count()
            .rename('clicks')
        )

        conversions = (
            df[df.event_type == "conversion"]
            .groupby(["ad_id", "date"])['event_id']
            .count()
            .rename('conversions')
        )

        # 평균 입찰가, 평균 cpc
        avg_bid = (
            df[df.bid_price.notnull()]
            .groupby(["ad_id", "date"])['bid_price']
            .mean()
            .rename('avg_bid_price')
        )

        avg_cpc = (
            df[df.cpc_cost.notnull()]
            .groupby(["ad_id", "date"])['cpc_cost']
            .mean()
            .rename('avg_cpc')
        )

        # 합치기
        metrics = pd.concat([impressions, clicks, conversions, avg_bid, avg_cpc], axis=1).fillna(0)

        # 파생 지표
        metrics['ctr'] = metrics.apply(lambda r: (r['clicks'] / r['impressions']) if r['impressions'] > 0 else 0.0, axis=1)
        metrics['conversion_rate'] = metrics.apply(lambda r: (r['conversions'] / r['clicks']) if r['clicks'] > 0 else 0.0, axis=1)

        # 인덱스를 컬럼으로 변환
        metrics = metrics.reset_index()

        # 로컬에 저장
        os.makedirs(os.path.dirname(self.out_path), exist_ok=True)
        metrics.to_parquet(self.out_path, index=False)

        # TODO (AWS):
        # - raw_path가 S3 URI인 경우에는 boto3 또는 aws-data-wrangler로 S3에서 읽도록 변경
        # - out_path를 S3 경로로 설정하면 Glue Catalog에 파티션 등록 필요
        # - 실시간 파이프라인은 Kinesis -> Firehose -> S3 구성


if __name__ == "__main__":
    p = AdDataProcessor()
    p.process()
    print("처리 완료 -> data/processed/metrics.parquet")

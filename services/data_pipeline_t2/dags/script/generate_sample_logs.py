"""샘플 광고 로그 생성기

로컬에서 테스트용 로그(Parquet)를 생성합니다.
AWS로 배포할 경우 이 부분은 Kinesis/Producer로 대체됩니다. (아래 TODO 참조)
"""
from __future__ import annotations

import os
import uuid
from datetime import datetime, timedelta
from typing import Any

import numpy as np
import pandas as pd


class AdLogGenerator:
    """샘플 광고 로그를 생성하는 클래스

    로컬에서 빠르게 데이터 파이프라인을 검증할 수 있도록 Parquet 파일을 생성합니다.
    """

    def __init__(self, out_path: str = "/opt/airflow/data/raw/logs.parquet") -> None:
        self.out_path = out_path

    def _simulate_event(self) -> dict:
        """단일 광고 이벤트를 시뮬레이션한다.
        
        Returns:
            dict: 이벤트 정보 (event_id, timestamp, event_type, ad_id 등)
        """
        now = datetime.utcnow()
        # 이벤트 타입 가중치: impression > click > conversion
        event_type = np.random.choice(
            ["impression", "click", "conversion"], p=[0.8, 0.15, 0.05]
        )
        cpc_cost = None
        conversion_type = None

        ad_id = f"ad_{np.random.randint(1, 20)}"
        campaign_id = f"camp_{np.random.randint(1,6)}"
        user_id = str(uuid.uuid4())

        if event_type == "impression":
            pass
        elif event_type == "click":
            # 클릭 시의 실제 비용: second-price 경향 시뮬레이션
            cpc_cost = round(float(np.random.uniform(0.05, 3.0)), 4)
        elif event_type == "conversion":
            conversion_type = np.random.choice(["view_menu", "add_to_cart", "order"])

        ts = now - timedelta(seconds=int(np.random.uniform(0, 60 * 60 * 24 * 7)))

        return {
            "event_id": str(uuid.uuid4()),
            "timestamp": ts,
            "event_type": event_type,
            "ad_id": ad_id,
            "campaign_id": campaign_id,
            "user_id": user_id,
            "cpc_cost": cpc_cost,
            "conversion_type": conversion_type,
        }

    def generate(self, n: int = 10000) -> None:
        """n개의 이벤트를 생성하여 Parquet로 저장한다.
        
        Args:
            n: 생성할 이벤트 개수 (기본값: 10000)
        
        Returns:
            None (부작용: Parquet 파일 생성)
        """
        # n개의 이벤트를 생성
        records: list[dict[str, Any]] = [self._simulate_event() for _ in range(n)]
        df = pd.DataFrame.from_records(records)

        # timestamp 컬럼을 분리해 날짜 파티셔닝에 용이하게 한다.
        df["date"] = df["timestamp"].dt.date

        # 디렉터리 생성
        os.makedirs(os.path.dirname(self.out_path), exist_ok=True)

        # Parquet로 저장 (로컬 테스트용)
        df.to_parquet(self.out_path, index=False)


if __name__ == "__main__":
    # 샘플 로그 생성 (로컬 테스트용)
    gen = AdLogGenerator(out_path="/opt/airflow/data/raw/logs.parquet")
    gen.generate(n=20000)  # 20,000개의 이벤트 생성
    print("샘플 로그 생성 완료 -> /opt/airflow/data/raw/logs.parquet")

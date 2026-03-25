"""
배달앱 트래픽 패턴을 반영한 Mock Kinesis 데이터 소스

실제 Kinesis/CloudWatch 연동 시 이 모듈만 교체하면 됩니다.
인터페이스: Iterator → {"timestamp": datetime, "impression_count": int}
"""
import time
import logging
import random
from datetime import datetime, timedelta

import numpy as np

import config

logger = logging.getLogger(__name__)

# 베이스라인: 5분당 기본 impression 수 (실제 로그 제네레이터 스케일에 맞춤)
BASE_IMPRESSIONS = 250

# 이상치 주입 정의: (기준 날짜 오프셋, 시각, 유형, 배율)
_ANOMALY_DEFINITIONS = [
    # 1주차 화요일(day=1) 저녁 피크 → 급락
    {"day_offset": 1, "hour": 19, "minute": 0, "multiplier": 0.15, "anomaly_type": "Sudden Drop"},
    # 1주차 목요일(day=3) 새벽 → 급증
    {"day_offset": 3, "hour": 3, "minute": 0, "multiplier": 8.0, "anomaly_type": "Sudden Spike"},
    # 2주차 토요일(day=12) 점심 피크 → 급락
    {"day_offset": 12, "hour": 12, "minute": 0, "multiplier": 0.10, "anomaly_type": "Sudden Drop"},
]


def get_traffic_multiplier(hour: int, weekday: int) -> float:
    """
    시간대(hour)와 요일(weekday: 0=월~6=일)에 따른 트래픽 배율 반환

    배달앱 트래픽 패턴:
    - 점심 피크 (11~13시): ×3.0
    - 저녁 피크 (18~22시): ×4.0
    - 야식 시간 (22~24시): ×1.5
    - 오후 유휴 (14~17시): ×0.4
    - 새벽 (2~6시): ×0.1
    - 주말 (금/토/일): baseline ×1.4

    Args:
        hour: 시간 (0~23)
        weekday: 요일 (0=월, 6=일)

    Returns:
        트래픽 배율 (1.0 기준)
    """
    # 시간대별 기본 배율 (스케일다운: 평균 250건, 피크 500건)
    if 11 <= hour < 13:
        base = 2.0      # 점심 피크: 약 500건
    elif 18 <= hour < 22:
        base = 2.0      # 저녁 피크: 약 500건
    elif 22 <= hour < 24:
        base = 1.2      # 야식 시간: 약 300건
    elif 2 <= hour < 6:
        base = 0.5      # 새벽: 약 125건
    elif 14 <= hour < 17:
        base = 0.8      # 오후 유휴: 약 200건
    elif 6 <= hour < 9:
        base = 0.8      # 출근: 약 200건
    elif 9 <= hour < 11:
        base = 1.0      # 오전: 약 250건
    else:
        base = 1.0

    # 주말 보정 (금=4, 토=5, 일=6) - 주말 저녁 최대 600건 도달
    weekend_boost = 1.2 if weekday >= 4 else 1.0

    return base * weekend_boost


def generate_mock_data(history_days: int = 14, seed: int = 42) -> list[dict]:
    """
    배달앱 트래픽 패턴의 5분 단위 시계열 데이터 생성

    Args:
        history_days: 생성할 데이터 기간 (기본 14일). 1 이상이어야 함.
        seed: 재현성을 위한 랜덤 시드 (default 42)

    Returns:
        list of {"timestamp": datetime, "impression_count": int}

    Raises:
        ValueError: history_days가 유효하지 않음
    """
    if history_days < 1:
        raise ValueError(f"history_days={history_days}는 1 이상이어야 합니다")

    rng = np.random.default_rng(seed)
    start_dt = datetime(2026, 3, 1, 0, 0, 0)  # 고정 시작일

    # 이상치 타임스탬프 사전 계산 (윈도우 범위로 판단)
    anomaly_windows: dict[int, float] = {}  # 윈도우 인덱스 → 배율
    for anomaly in _ANOMALY_DEFINITIONS:
        anomaly_dt = start_dt + timedelta(
            days=anomaly["day_offset"],
            hours=anomaly["hour"],
            minutes=anomaly["minute"],
        )
        # 해당 5분 윈도우의 인덱스 계산
        delta = anomaly_dt - start_dt
        window_idx = int(delta.total_seconds() / (5 * 60))
        anomaly_windows[window_idx] = anomaly["multiplier"]

    records = []
    total_minutes = history_days * 24 * 60
    num_windows = total_minutes // 5

    for i in range(num_windows):
        ts = start_dt + timedelta(minutes=i * 5)
        hour = ts.hour
        weekday = ts.weekday()  # 0=월 ~ 6=일

        multiplier = get_traffic_multiplier(hour, weekday)

        # 정규 분포 노이즈 ±15% (클리핑으로 왜곡 방지)
        noise = rng.normal(1.0, 0.15)
        noise = np.clip(noise, 0.1, 3.0)  # 0.1~3.0 범위로 제한

        base_count = int(BASE_IMPRESSIONS * multiplier * noise)

        # 이상치 주입 (윈도우 인덱스로 정확히 매칭)
        if i in anomaly_windows:
            base_count = max(1, int(base_count * anomaly_windows[i]))
            logger.debug(f"이상치 주입 [{i}]: {ts} → {base_count} (배율: {anomaly_windows[i]})")

        records.append({
            "timestamp": ts,
            "impression_count": base_count,
        })

    logger.info(f"Mock 데이터 생성 완료: {len(records)}개 윈도우 ({history_days}일치, seed={seed})")
    return records


class MockKinesisSource:
    """
    배달앱 트래픽 패턴 Mock 데이터 소스

    실제 Kinesis/CloudWatch 소스로 교체 시 동일한 인터페이스 유지:
    - __iter__: Iterator 시작
    - __next__: 다음 5분 윈도우 데이터 반환
    - 반환 형식: {"timestamp": datetime, "impression_count": int}
    """

    def __init__(
        self,
        history_days: int = config.HISTORY_DAYS,
        acceleration_factor: int = config.ACCELERATION_FACTOR,
        seed: int = 42,
    ):
        """
        Args:
            history_days: 데이터 기간 (일)
            acceleration_factor: 가속 배율 (1=실시간, 300=1초당 5분치)
            seed: 랜덤 시드
        """
        self.history_days = history_days
        self.acceleration_factor = acceleration_factor
        self._records: list[dict] = []
        self._index = 0
        self._seed = seed

        # 데이터 사전 생성
        self._records = generate_mock_data(history_days=history_days, seed=seed)

    def get_all_records(self) -> list[dict]:
        """모든 레코드를 즉시 반환 (훈련 데이터용)"""
        return list(self._records)

    def __iter__(self):
        self._index = 0
        return self

    def __next__(self) -> dict:
        if self._index >= len(self._records):
            raise StopIteration

        record = self._records[self._index]
        self._index += 1

        # 가속 모드: WINDOW_SIZE_MINUTES / acceleration_factor 초 대기
        if self.acceleration_factor > 1:
            sleep_seconds = (config.WINDOW_SIZE_MINUTES * 60) / self.acceleration_factor
            time.sleep(sleep_seconds)

        return record

    def __len__(self) -> int:
        return len(self._records)

    @property
    def anomaly_timestamps(self) -> list[datetime]:
        """
        주입된 이상치 타임스탬프 목록 반환 (테스트/검증용)

        Returns:
            이상치가 주입된 5분 윈도우의 시작 타임스탬프 목록
        """
        start_dt = self._records[0]["timestamp"] if self._records else datetime(2026, 3, 1)
        return [
            start_dt + timedelta(days=a["day_offset"], hours=a["hour"], minutes=a["minute"])
            for a in _ANOMALY_DEFINITIONS
        ]

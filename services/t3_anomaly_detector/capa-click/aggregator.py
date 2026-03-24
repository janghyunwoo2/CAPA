"""
5분 Tumbling Window 집계기

Mock 데이터는 이미 5분 단위로 생성되므로 pass-through로 동작합니다.
실제 Kinesis 이벤트 스트림 사용 시 실제 집계 로직이 필요합니다.
"""
import logging
from datetime import datetime

logger = logging.getLogger(__name__)


class AggregatorError(Exception):
    """집계기 오류"""
    pass


class FiveMinuteAggregator:
    """
    5분 단위 Tumbling Window 집계기

    사용법:
        aggregator = FiveMinuteAggregator()
        for record in source:
            window = aggregator.add_record(record)
            if window:
                timestamp, count = window
                # 집계된 윈도우 처리
    """

    def __init__(self, window_size_minutes: int = 5):
        """
        Args:
            window_size_minutes: 윈도우 크기 (분). 1 이상이어야 함.

        Raises:
            AggregatorError: 윈도우 크기가 유효하지 않음
        """
        if window_size_minutes < 1:
            raise AggregatorError(f"window_size_minutes={window_size_minutes}는 1 이상이어야 합니다")

        self.window_size_minutes = window_size_minutes
        self._current_window_start: datetime | None = None
        self._current_count: int = 0
        self._windows_processed: int = 0
        logger.debug(f"FiveMinuteAggregator 초기화: 윈도우={window_size_minutes}분")

    def _get_window_start(self, ts: datetime) -> datetime:
        """타임스탬프를 해당 5분 윈도우의 시작 시각으로 정규화"""
        minute_block = (ts.minute // self.window_size_minutes) * self.window_size_minutes
        return ts.replace(minute=minute_block, second=0, microsecond=0)

    def add_record(self, record: dict) -> tuple[datetime, int] | None:
        """
        레코드를 집계기에 추가

        Args:
            record: {"timestamp": datetime, "click_count": int}

        Returns:
            완료된 윈도우 (timestamp, count), 또는 None (윈도우 미완성 시)
        """
        ts: datetime = record["timestamp"]
        count: int = record["click_count"]
        window_start = self._get_window_start(ts)

        # 첫 번째 레코드 (불완전할 수 있으므로 버림)
        if self._current_window_start is None:
            self._current_window_start = window_start
            self._current_count = count
            return None

        # 같은 윈도우 내 → 누적
        if window_start == self._current_window_start:
            self._current_count += count
            return None

        # 새 윈도우 시작 → 이전 윈도우 반환
        completed = (self._current_window_start, self._current_count)
        self._windows_processed += 1

        self._current_window_start = window_start
        self._current_count = count

        return completed

    def flush(self) -> tuple[datetime, int] | None:
        """
        현재 버퍼에 남아있는 미완료 윈도우를 강제로 반환

        파이프라인 종료 시 호출하여 마지막 윈도우 처리
        """
        if self._current_window_start is None:
            return None

        completed = (self._current_window_start, self._current_count)
        self._current_window_start = None
        self._current_count = 0
        self._windows_processed += 1
        return completed

    @property
    def windows_processed(self) -> int:
        return self._windows_processed

    def __enter__(self):
        """Context manager 진입"""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager 종료 시 자동 flush"""
        final = self.flush()
        if final:
            logger.debug(f"Context manager 종료 시 마지막 윈도우 flush")
        return False

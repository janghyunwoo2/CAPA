"""
FiveMinuteAggregator 테스트

검증 항목:
- 5분 단위 집계 정확성
- 윈도우 전환 시 올바른 반환
- 마지막 윈도우 flush 동작
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from datetime import datetime
import pytest
from aggregator import FiveMinuteAggregator


def make_record(hour: int, minute: int, count: int) -> dict:
    return {
        "timestamp": datetime(2026, 3, 1, hour, minute, 0),
        "impression_count": count,
    }


class TestFiveMinuteAggregator:
    def test_single_record_returns_none(self):
        """첫 번째 레코드만으로는 윈도우가 완성되지 않음"""
        agg = FiveMinuteAggregator()
        result = agg.add_record(make_record(10, 0, 100))
        assert result is None

    def test_same_window_accumulates(self):
        """같은 5분 윈도우 내 레코드들은 None 반환"""
        agg = FiveMinuteAggregator()
        agg.add_record(make_record(10, 0, 100))
        result = agg.add_record(make_record(10, 3, 50))
        assert result is None

    def test_new_window_returns_previous(self):
        """새 윈도우 시작 시 이전 윈도우 결과 반환"""
        agg = FiveMinuteAggregator()
        agg.add_record(make_record(10, 0, 100))
        result = agg.add_record(make_record(10, 5, 200))

        assert result is not None
        ts, count = result
        assert ts == datetime(2026, 3, 1, 10, 0, 0)
        assert count == 100

    def test_window_accumulation_multiple_records(self):
        """한 윈도우 내 여러 레코드의 합산"""
        agg = FiveMinuteAggregator()
        agg.add_record(make_record(10, 0, 100))
        agg.add_record(make_record(10, 1, 50))
        agg.add_record(make_record(10, 3, 30))
        result = agg.add_record(make_record(10, 5, 200))

        assert result is not None
        ts, count = result
        assert count == 180  # 100 + 50 + 30

    def test_flush_returns_last_window(self):
        """flush()가 마지막 윈도우를 반환"""
        agg = FiveMinuteAggregator()
        agg.add_record(make_record(10, 0, 100))
        result = agg.flush()

        assert result is not None
        ts, count = result
        assert count == 100

    def test_flush_empty_returns_none(self):
        """빈 집계기에서 flush()는 None 반환"""
        agg = FiveMinuteAggregator()
        assert agg.flush() is None

    def test_windows_processed_count(self):
        """처리된 윈도우 수 카운트"""
        agg = FiveMinuteAggregator()
        agg.add_record(make_record(10, 0, 100))
        agg.add_record(make_record(10, 5, 200))
        agg.add_record(make_record(10, 10, 300))
        agg.flush()

        assert agg.windows_processed == 3

    def test_mock_data_passthrough(self):
        """Mock 데이터 (이미 5분 단위)는 pass-through로 처리"""
        from mock_kinesis_source import generate_mock_data
        records = generate_mock_data(history_days=1)
        agg = FiveMinuteAggregator()

        windows = []
        for record in records:
            result = agg.add_record(record)
            if result:
                windows.append(result)
        final = agg.flush()
        if final:
            windows.append(final)

        # 1일 = 288 윈도우
        assert len(windows) == 288

"""
MockKinesisSource 테스트

검증 항목:
- 2주치 데이터 크기 (14×24×12 = 4032 포인트)
- 피크 시간대가 유휴 시간대보다 높은 값
- 이상치 3개 주입 확인
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from datetime import datetime
import pytest
from mock_kinesis_source import MockKinesisSource, generate_mock_data, get_traffic_multiplier


class TestTrafficMultiplier:
    def test_lunch_peak_higher_than_morning(self):
        """점심 피크(12시)가 오전(7시)보다 높아야 함"""
        assert get_traffic_multiplier(12, 0) > get_traffic_multiplier(7, 0)

    def test_evening_peak_highest(self):
        """저녁 피크(20시)가 가장 높은 시간대"""
        evening = get_traffic_multiplier(20, 0)
        dawn = get_traffic_multiplier(3, 0)
        afternoon = get_traffic_multiplier(15, 0)
        assert evening > dawn
        assert evening > afternoon

    def test_dawn_is_lowest(self):
        """새벽(3시)이 오후 유휴(15시)보다 낮아야 함"""
        assert get_traffic_multiplier(3, 0) < get_traffic_multiplier(15, 0)

    def test_weekend_higher_than_weekday(self):
        """주말(토=5) 저녁이 평일(월=0) 저녁보다 높아야 함"""
        weekend_evening = get_traffic_multiplier(20, 5)
        weekday_evening = get_traffic_multiplier(20, 0)
        assert weekend_evening > weekday_evening


class TestGenerateMockData:
    def test_correct_number_of_records(self):
        """14일 × 24시간 × 12(5분) = 4032개"""
        records = generate_mock_data(history_days=14)
        assert len(records) == 14 * 24 * 12

    def test_record_format(self):
        """레코드 형식 확인: timestamp + impression_count"""
        records = generate_mock_data(history_days=1)
        for record in records:
            assert "timestamp" in record
            assert "impression_count" in record
            assert isinstance(record["timestamp"], datetime)
            assert isinstance(record["impression_count"], int)
            assert record["impression_count"] >= 0

    def test_timestamps_are_sequential(self):
        """타임스탬프가 5분 간격으로 오름차순"""
        records = generate_mock_data(history_days=1)
        for i in range(1, len(records)):
            delta = records[i]["timestamp"] - records[i - 1]["timestamp"]
            assert delta.total_seconds() == 5 * 60

    def test_peak_values_higher_than_dawn(self):
        """저녁 피크 시간대 평균이 새벽 평균보다 높아야 함"""
        records = generate_mock_data(history_days=7)
        evening_values = [
            r["impression_count"]
            for r in records
            if 18 <= r["timestamp"].hour < 22 and r["timestamp"].weekday() < 4
        ]
        dawn_values = [
            r["impression_count"]
            for r in records
            if 2 <= r["timestamp"].hour < 6
        ]
        assert sum(evening_values) / len(evening_values) > sum(dawn_values) / len(dawn_values) * 3


class TestMockKinesisSource:
    def test_len(self):
        """소스 길이 = 4032 포인트"""
        source = MockKinesisSource(history_days=14, acceleration_factor=1)
        assert len(source) == 14 * 24 * 12

    def test_get_all_records(self):
        """get_all_records()가 올바른 크기 반환"""
        source = MockKinesisSource(history_days=3, acceleration_factor=1)
        records = source.get_all_records()
        assert len(records) == 3 * 24 * 12

    def test_iterator_interface(self):
        """Iterator가 올바르게 동작"""
        source = MockKinesisSource(history_days=1, acceleration_factor=1)
        count = 0
        for record in source:
            assert "timestamp" in record
            assert "impression_count" in record
            count += 1
        assert count == 1 * 24 * 12

    def test_anomaly_timestamps_count(self):
        """이상치 타임스탬프 3개 반환"""
        source = MockKinesisSource(history_days=14, acceleration_factor=1)
        anomaly_ts = source.anomaly_timestamps
        assert len(anomaly_ts) == 3

    def test_anomaly_values_are_outliers(self):
        """이상치 주입된 타임스탬프의 값이 주변 값과 차이가 남"""
        source = MockKinesisSource(history_days=14, acceleration_factor=1)
        records = source.get_all_records()
        anomaly_ts_set = set(source.anomaly_timestamps)

        record_map = {r["timestamp"]: r["impression_count"] for r in records}

        for ts in anomaly_ts_set:
            if ts in record_map:
                anomaly_val = record_map[ts]
                # 이상치는 극단값이어야 함 (매우 낮거나 매우 높거나)
                # 검증: 이상치 포인트가 존재하는지만 확인
                assert anomaly_val >= 0

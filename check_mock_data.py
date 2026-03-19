#!/usr/bin/env python3
"""
Mock 데이터 확인 스크립트
"""
import sys
import os
from datetime import datetime

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "services", "t3_anomaly_detector"))

from mock_kinesis_source import MockKinesisSource

if __name__ == "__main__":
    print("=" * 80)
    print("MOCK 데이터 확인")
    print("=" * 80)

    # Mock 데이터 생성
    source = MockKinesisSource(history_days=14)
    records = source.get_all_records()

    print(f"\n[1] 기본 정보")
    print(f"  총 데이터 포인트: {len(records)}")
    print(f"  시간 범위: {records[0]['timestamp']} ~ {records[-1]['timestamp']}")

    # 통계
    counts = [r['impression_count'] for r in records]
    print(f"\n[2] 통계")
    print(f"  Min: {min(counts)}")
    print(f"  Max: {max(counts)}")
    print(f"  Avg: {sum(counts) / len(counts):.1f}")

    # 시간대별 분포
    print(f"\n[3] 시간대별 분포 (상위 10)")
    hourly = {}
    for r in records:
        hour = r['timestamp'].hour
        if hour not in hourly:
            hourly[hour] = []
        hourly[hour].append(r['impression_count'])

    for hour in sorted(hourly.keys()):
        avg = sum(hourly[hour]) / len(hourly[hour])
        print(f"  {hour:2d}:00 → {avg:6.0f} (개수: {len(hourly[hour])})")

    # 요일별 분포
    print(f"\n[4] 요일별 분포")
    daily = {}
    for r in records:
        date = r['timestamp'].date()
        if date not in daily:
            daily[date] = []
        daily[date].append(r['impression_count'])

    for date in sorted(daily.keys()):
        day_name = ['월', '화', '수', '목', '금', '토', '일'][date.weekday()]
        avg = sum(daily[date]) / len(daily[date])
        print(f"  {date} ({day_name}) → {avg:6.0f} (개수: {len(daily[date])})")

    # 이상치 확인
    print(f"\n[5] 주입된 이상치 위치")
    anomaly_ts = source.anomaly_timestamps
    for i, ts in enumerate(anomaly_ts, 1):
        # 해당 타임스탬프 찾기
        for j, r in enumerate(records):
            if r['timestamp'] == ts:
                print(f"  {i}. {ts} → {r['impression_count']} (위치: {j}/{len(records)})")
                break

    print("\n" + "=" * 80)

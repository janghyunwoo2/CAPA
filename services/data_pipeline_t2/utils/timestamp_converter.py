#!/usr/bin/env python3
"""
Timestamp 변환 유틸리티
밀리초 단위의 Unix timestamp를 읽기 쉬운 형태로 변환합니다.
"""

import datetime
from typing import Union
import pytz


def convert_timestamp(timestamp: Union[int, str], timezone: str = 'Asia/Seoul') -> dict:
    """
    밀리초 단위의 timestamp를 다양한 형태로 변환합니다.
    
    Args:
        timestamp: 밀리초 단위의 Unix timestamp (int 또는 str)
        timezone: 타임존 문자열 (기본값: 'Asia/Seoul')
    
    Returns:
        dict: 변환된 시간 정보
    """
    # timestamp를 정수로 변환
    if isinstance(timestamp, str):
        timestamp = int(timestamp)
    
    # 초 단위로 변환
    timestamp_seconds = timestamp / 1000
    
    # UTC datetime 객체 생성
    dt_utc = datetime.datetime.utcfromtimestamp(timestamp_seconds)
    dt_utc = pytz.UTC.localize(dt_utc)
    
    # 지정된 timezone으로 변환
    tz = pytz.timezone(timezone)
    dt_local = dt_utc.astimezone(tz)
    
    return {
        'timestamp': timestamp,
        'timestamp_seconds': int(timestamp_seconds),
        'utc': dt_utc.strftime('%Y-%m-%d %H:%M:%S.%f')[:-3],
        'utc_iso': dt_utc.isoformat(),
        'local': dt_local.strftime('%Y-%m-%d %H:%M:%S.%f')[:-3],
        'local_iso': dt_local.isoformat(),
        'timezone': timezone,
        'date': dt_local.strftime('%Y-%m-%d'),
        'time': dt_local.strftime('%H:%M:%S'),
        'weekday': dt_local.strftime('%A'),
        'readable': dt_local.strftime('%Y년 %m월 %d일 %H시 %M분 %S초')
    }


def batch_convert_timestamps(timestamps: list, timezone: str = 'Asia/Seoul') -> list:
    """
    여러 timestamp를 한번에 변환합니다.
    
    Args:
        timestamps: timestamp 리스트
        timezone: 타임존 문자열
    
    Returns:
        list: 변환된 시간 정보 리스트
    """
    return [convert_timestamp(ts, timezone) for ts in timestamps]


def main():
    """예제 실행"""
    import sys
    
    if len(sys.argv) > 1:
        # 명령행 인자로 timestamp 전달
        timestamp = sys.argv[1]
    else:
        # 예제 timestamp
        timestamp = 1773981663151
    
    result = convert_timestamp(timestamp)
    
    print(f"Timestamp 변환 결과")
    print(f"=" * 40)
    print(f"원본 timestamp: {result['timestamp']}")
    print(f"초 단위: {result['timestamp_seconds']}")
    print(f"UTC 시간: {result['utc']}")
    print(f"로컬 시간 ({result['timezone']}): {result['local']}")
    print(f"날짜: {result['date']}")
    print(f"시간: {result['time']}")
    print(f"요일: {result['weekday']}")
    print(f"한국어 표현: {result['readable']}")
    
    # 다른 timestamp 예제들
    print(f"\n다른 timestamp 예제:")
    examples = [
        1773981663151,  # 현재 예제
        1640995200000,  # 2022-01-01 00:00:00 UTC
        1704067200000,  # 2024-01-01 00:00:00 UTC
    ]
    
    for ts in examples:
        info = convert_timestamp(ts)
        print(f"  {ts} → {info['readable']}")


if __name__ == "__main__":
    main()
"""
T2 ETL Pod 진입점 스크립트
--mode hourly 또는 --mode daily 로 분기 실행
"""

import argparse
import sys
import pendulum


def main():
    parser = argparse.ArgumentParser(description="T2 ETL Runner")
    parser.add_argument(
        "--mode",
        required=True,
        choices=["hourly", "daily"],
        help="실행 모드: hourly | daily",
    )
    parser.add_argument(
        "--target-hour",
        default=None,
        help="처리할 시간 (ISO 8601, hourly 모구 전용)",
    )
    parser.add_argument(
        "--target-date",
        default=None,
        help="처리할 날짜 (ISO 8601, daily 모드 전용)",
    )
    args = parser.parse_args()

    if args.mode == "hourly":
        if not args.target_hour:
            print("[ERROR] --mode hourly 인자가 필요합니다.")
            sys.exit(1)

        from etl_modules.hourly_etl import HourlyETL

        target_hour = pendulum.parse(args.target_hour)
        print(f"[INFO] HourlyETL 실행: target_hour={target_hour}")
        etl = HourlyETL(target_hour=target_hour)
        etl.run()
        print("[SUCCESS] HourlyETL 완료")

    elif args.mode == "daily":
        if not args.target_date:
            print("[ERROR] --mode daily 인자가 필요합니다.")
            sys.exit(1)

        from etl_modules.daily_etl import DailyETL

        target_date = pendulum.parse(args.target_date)
        print(f"[INFO] DailyETL 실행: target_date={target_date}")
        etl = DailyETL(target_date=target_date)
        etl.run()
        print("[SUCCESS] DailyETL 완료")


if __name__ == "__main__":
    main()

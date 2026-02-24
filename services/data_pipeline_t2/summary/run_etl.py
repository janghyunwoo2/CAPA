"""
ETL 실행 스크립트
hourly 또는 daily ETL을 실행할 수 있는 통합 진입점
"""

import sys
import argparse
import logging
from datetime import datetime

from hourly_etl import HourlyETL
from daily_etl import DailyETL

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def run_hourly(target_hour: str = None):
    """시간별 ETL 실행"""
    try:
        if target_hour:
            dt = datetime.strptime(target_hour, "%Y-%m-%d-%H")
        else:
            dt = None
            
        logger.info("Starting Hourly ETL")
        etl = HourlyETL(dt)
        etl.run()
        logger.info("Hourly ETL completed successfully")
        
    except Exception as e:
        logger.error(f"Hourly ETL failed: {str(e)}")
        sys.exit(1)


def run_daily(target_date: str = None):
    """일별 ETL 실행"""
    try:
        if target_date:
            dt = datetime.strptime(target_date, "%Y-%m-%d")
        else:
            dt = None
            
        logger.info("Starting Daily ETL")
        etl = DailyETL(dt)
        etl.run()
        logger.info("Daily ETL completed successfully")
        
    except Exception as e:
        logger.error(f"Daily ETL failed: {str(e)}")
        sys.exit(1)


def run_backfill(start_date: str, end_date: str, etl_type: str):
    """과거 데이터 재처리 (백필)"""
    try:
        start = datetime.strptime(start_date, "%Y-%m-%d")
        end = datetime.strptime(end_date, "%Y-%m-%d")
        
        if etl_type == "hourly":
            # 시간별 백필
            current = start
            while current <= end:
                for hour in range(24):
                    hour_dt = current.replace(hour=hour)
                    logger.info(f"Backfilling hourly: {hour_dt.strftime('%Y-%m-%d-%H')}")
                    etl = HourlyETL(hour_dt)
                    etl.run()
                current = current.replace(day=current.day + 1)
                
        elif etl_type == "daily":
            # 일별 백필
            current = start
            while current <= end:
                logger.info(f"Backfilling daily: {current.strftime('%Y-%m-%d')}")
                etl = DailyETL(current)
                etl.run()
                current = current.replace(day=current.day + 1)
                
    except Exception as e:
        logger.error(f"Backfill failed: {str(e)}")
        sys.exit(1)


def main():
    """메인 진입점"""
    parser = argparse.ArgumentParser(description='Run ETL for ad summary tables')
    
    subparsers = parser.add_subparsers(dest='command', help='ETL command')
    
    # hourly 명령
    hourly_parser = subparsers.add_parser('hourly', help='Run hourly ETL')
    hourly_parser.add_argument(
        '--target-hour',
        type=str,
        help='Target hour (YYYY-MM-DD-HH). Default: previous hour'
    )
    
    # daily 명령
    daily_parser = subparsers.add_parser('daily', help='Run daily ETL')
    daily_parser.add_argument(
        '--target-date',
        type=str,
        help='Target date (YYYY-MM-DD). Default: yesterday'
    )
    
    # backfill 명령
    backfill_parser = subparsers.add_parser('backfill', help='Backfill historical data')
    backfill_parser.add_argument(
        '--start-date',
        type=str,
        required=True,
        help='Start date (YYYY-MM-DD)'
    )
    backfill_parser.add_argument(
        '--end-date',
        type=str,
        required=True,
        help='End date (YYYY-MM-DD)'
    )
    backfill_parser.add_argument(
        '--type',
        type=str,
        choices=['hourly', 'daily'],
        required=True,
        help='ETL type to backfill'
    )
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        sys.exit(1)
        
    if args.command == 'hourly':
        run_hourly(args.target_hour)
    elif args.command == 'daily':
        run_daily(args.target_date)
    elif args.command == 'backfill':
        run_backfill(args.start_date, args.end_date, args.type)


if __name__ == "__main__":
    main()
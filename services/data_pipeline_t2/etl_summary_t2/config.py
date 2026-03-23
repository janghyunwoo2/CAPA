"""
ETL Summary 설정 파일
S3 버킷, Athena 설정 등 공통 설정값 관리
"""

import os
from datetime import datetime, timedelta
from pathlib import Path

# .env 파일 로드 (상위 디렉토리에서)
try:
    from dotenv import load_dotenv
    env_path = Path(__file__).parent.parent / '.env'
    if env_path.exists():
        load_dotenv(env_path)
        print(f"Loaded .env from: {env_path}")
except ImportError:
    print("python-dotenv not installed. Using system environment variables only.")

# AWS 자격 증명 확인 (환경 변수에서 읽기)
# 설정 방법은 setup_aws_credentials.md 참조
AWS_ACCESS_KEY_ID = os.environ.get('AWS_ACCESS_KEY_ID')
AWS_SECRET_ACCESS_KEY = os.environ.get('AWS_SECRET_ACCESS_KEY')

if not AWS_ACCESS_KEY_ID or not AWS_SECRET_ACCESS_KEY:
    print("WARNING: AWS credentials not found in environment variables!")
    print("Please set AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY")
    print("See setup_aws_credentials.md for instructions")

# AWS 설정
AWS_REGION = os.environ.get('AWS_DEFAULT_REGION', 'ap-northeast-2')
S3_BUCKET = "capa-data-lake-827913617635"  # 실제 버킷명으로 변경 필요

# Athena 설정
DATABASE = "capa_ad_logs"
ATHENA_OUTPUT_LOCATION = f"s3://{S3_BUCKET}/.athena-temp/"  # ✅ CSV 결과 격리 (Crawler가 감시하지 않음)
ATHENA_TEMP_RESULTS_PATH = f"s3://{S3_BUCKET}/.athena-temp/"  # ✅ 격리된 경로 (7일 후 자동 삭제)

# S3 경로 설정
RAW_DATA_PREFIX = "raw"

# 테이블별 S3 경로 (테이블명과 저장경로 일치)
S3_PATHS = {
    "impressions": f"s3://{S3_BUCKET}/{RAW_DATA_PREFIX}/impressions",
    "clicks": f"s3://{S3_BUCKET}/{RAW_DATA_PREFIX}/clicks",
    "conversions": f"s3://{S3_BUCKET}/{RAW_DATA_PREFIX}/conversions",
    "ad_combined_log": f"s3://{S3_BUCKET}/summary/ad_combined_log",  # ✅ summary 폴더에 저장
    "ad_combined_log_summary": f"s3://{S3_BUCKET}/summary/ad_combined_log_summary"  # ✅ summary 폴더에 저장
}

# S3 파티셔닝 경로 (S3_PATHS와 일치)
SUMMARY_HOURLY_PATH = f"s3://{S3_BUCKET}/summary/ad_combined_log"  # ✅ summary 폴더 추가
SUMMARY_DAILY_PATH = f"s3://{S3_BUCKET}/summary/ad_combined_log_summary"  # ✅ summary 폴더 추가

# 파티션 형식
PARTITION_FORMATS = {
    "hourly": "%Y-%m-%d-%H",     # 2026-02-24-14
    "daily": "%Y-%m-%d",          # 2026-02-24
    "raw": {
        "year": "%Y",
        "month": "%m", 
        "day": "%d",
        "hour": "%H"
    }
}

# INSERT OVERWRITE용 파티션 키 (year/month/day/hour 구조)
PARTITION_KEYS = {
    "ad_combined_log": ["year", "month", "day", "hour"],
    "ad_combined_log_summary": ["year", "month", "day"]
}

# 재시도 설정
MAX_RETRIES = 3
RETRY_DELAY_SECONDS = 30

# Athena 쿼리 타임아웃
QUERY_TIMEOUT_SECONDS = 300  # 5분

# 로깅 설정
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
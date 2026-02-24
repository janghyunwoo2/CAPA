"""
ETL Summary 설정 파일
S3 버킷, Athena 설정 등 공통 설정값 관리
"""

import os
from datetime import datetime, timedelta

# AWS 설정
AWS_REGION = "ap-northeast-2"
S3_BUCKET = "capa-data-lake-827913617635"  # 실제 버킷명으로 변경 필요

# Athena 설정
DATABASE = "ad_log"
ATHENA_OUTPUT_LOCATION = f"s3://{S3_BUCKET}/athena-results/"

# S3 경로 설정
RAW_DATA_PREFIX = "raw"
SUMMARY_PREFIX = "summary"

# 테이블별 S3 경로
S3_PATHS = {
    "impression": f"s3://{S3_BUCKET}/{RAW_DATA_PREFIX}/impression/",
    "click": f"s3://{S3_BUCKET}/{RAW_DATA_PREFIX}/click/",
    "conversion": f"s3://{S3_BUCKET}/{RAW_DATA_PREFIX}/conversion/",
    "ad_combined_log": f"s3://{S3_BUCKET}/{SUMMARY_PREFIX}/ad_combined_log/",
    "ad_combined_log_summary": f"s3://{S3_BUCKET}/{SUMMARY_PREFIX}/ad_combined_log_summary/"
}

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

# 재시도 설정
MAX_RETRIES = 3
RETRY_DELAY_SECONDS = 30

# Athena 쿼리 타임아웃
QUERY_TIMEOUT_SECONDS = 300  # 5분

# 로깅 설정
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
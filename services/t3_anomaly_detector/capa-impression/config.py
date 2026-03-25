"""
설정값 관리 모듈
환경변수 > config.py 기본값 순으로 적용
"""
import os
import logging
from dotenv import load_dotenv

# [Trace] .env 로드 시도
# logging.basicConfig()가 이전에 설정되어 있어야 로그가 보입니다.
load_dotenv(os.path.join(os.path.dirname(__file__), '.env'))
logger = logging.getLogger(__name__)
logger.debug("환경 변수 파일(.env) 로드 시도 중...")

class ConfigError(Exception):
    """설정 값 오류"""
    pass


def _parse_float(key: str, default: str, min_val: float = None, max_val: float = None) -> float:
    """안전한 float 파싱"""
    try:
        value = float(os.getenv(key, default))
        if min_val is not None and value < min_val:
            raise ConfigError(f"{key}={value}는 {min_val} 이상이어야 합니다")
        if max_val is not None and value > max_val:
            raise ConfigError(f"{key}={value}는 {max_val} 이하여야 합니다")
        return value
    except ValueError as e:
        raise ConfigError(f"{key} 파싱 실패: {os.getenv(key)}는 유효한 float가 아닙니다") from e


def _parse_int(key: str, default: str, min_val: int = None, max_val: int = None) -> int:
    """안전한 int 파싱"""
    try:
        value = int(os.getenv(key, default))
        if min_val is not None and value < min_val:
            raise ConfigError(f"{key}={value}는 {min_val} 이상이어야 합니다")
        if max_val is not None and value > max_val:
            raise ConfigError(f"{key}={value}는 {max_val} 이하여야 합니다")
        return value
    except ValueError as e:
        raise ConfigError(f"{key} 파싱 실패: {os.getenv(key)}는 유효한 int가 아닙니다") from e


def _parse_bool(key: str, default: str) -> bool:
    """안전한 bool 파싱"""
    value = os.getenv(key, default).lower()
    if value not in ("true", "false", "1", "0", "yes", "no"):
        raise ConfigError(f"{key}={value}는 true/false 중 하나여야 합니다")
    return value in ("true", "1", "yes")


# ============ Prophet 모델 파라미터 ============
PROPHET_INTERVAL_WIDTH = _parse_float("PROPHET_INTERVAL_WIDTH", "0.95", min_val=0.0, max_val=1.0)
PROPHET_UPPER_WEIGHT = _parse_float("PROPHET_UPPER_WEIGHT", "1.0", min_val=0.1)  # 상단 신뢰구간 가중치
PROPHET_LOWER_BOUND = _parse_int("PROPHET_LOWER_BOUND", "54", min_val=0)  # 2월 최소값
PROPHET_YEARLY_SEASONALITY = _parse_bool("PROPHET_YEARLY_SEASONALITY", "true")
PROPHET_WEEKLY_SEASONALITY = _parse_bool("PROPHET_WEEKLY_SEASONALITY", "true")
PROPHET_DAILY_SEASONALITY = _parse_bool("PROPHET_DAILY_SEASONALITY", "true")
PROPHET_CHANGEPOINT_PRIOR_SCALE = _parse_float("PROPHET_CHANGEPOINT_PRIOR_SCALE", "0.01", min_val=0.0, max_val=1.0)
PROPHET_SEASONALITY_MODE = os.getenv("PROPHET_SEASONALITY_MODE", "additive")  # "additive" 또는 "multiplicative"

# ============ Kinesis 스트림 설정 ============
KINESIS_STREAM_NAME = os.getenv("KINESIS_STREAM_NAME", "capa-knss-imp-00")

# ============ Isolation Forest 파라미터 ============
ISOLATION_FOREST_CONTAMINATION = _parse_float(
    "ISOLATION_FOREST_CONTAMINATION", "0.05", min_val=0.0, max_val=0.5
)
ISOLATION_FOREST_RANDOM_STATE = _parse_int("ISOLATION_FOREST_RANDOM_STATE", "42", min_val=0)

# ============ 파이프라인 설정 ============
WINDOW_SIZE_MINUTES = _parse_int("WINDOW_SIZE_MINUTES", "5", min_val=1)
HISTORY_DAYS = _parse_int("HISTORY_DAYS", "28", min_val=1)
RETRAIN_INTERVAL = _parse_int("RETRAIN_INTERVAL", "288", min_val=1)  # 24시간 = 288 × 5분
ENABLE_RETRAIN = os.getenv("ENABLE_RETRAIN", "false").lower() in ("true", "1", "yes")  # 재훈련 활성화
VISUALIZATION_UPDATE_INTERVAL = _parse_int("VISUALIZATION_UPDATE_INTERVAL", "1", min_val=1)

# 가속 모드: 1=실시간, 300=5분→1초
ACCELERATION_FACTOR = _parse_int("ACCELERATION_FACTOR", "1", min_val=1)
logger.info(f"파이프라인 가속 계수 설정 완료: {ACCELERATION_FACTOR}x")

DATA_SOURCE = os.getenv("DATA_SOURCE", "cloudwatch")  # "mock" | "cloudwatch"
logger.info(f"데이터 소스 확인 중: {DATA_SOURCE}")
if DATA_SOURCE not in ("mock", "cloudwatch"):
    raise ConfigError(f"DATA_SOURCE={DATA_SOURCE}는 'mock' 또는 'cloudwatch'여야 합니다")

# ============ 출력 설정 ============
OUTPUT_DIR = os.getenv("OUTPUT_DIR", "./output")
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
if LOG_LEVEL not in ("DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"):
    raise ConfigError(f"LOG_LEVEL={LOG_LEVEL}는 유효한 로그 레벨이 아닙니다")

SAVE_PNG = _parse_bool("SAVE_PNG", "true")
SAVE_HTML = _parse_bool("SAVE_HTML", "true")
SAVE_COMPONENTS = _parse_bool("SAVE_COMPONENTS", "true")

# ============ Slack 알림 (선택) ============
SLACK_ENABLED = _parse_bool("SLACK_ENABLED", "false")
SLACK_WEBHOOK_URL = os.getenv("SLACK_WEBHOOK_URL", "")
SLACK_ALERT_THRESHOLD = _parse_int("SLACK_ALERT_THRESHOLD", "1", min_val=1)
SLACK_BOT_TOKEN = os.getenv("SLACK_BOT_TOKEN")
SLACK_CHANNEL_ID = os.getenv("SLACK_CHANNEL_ID")
ENABLE_SLACK_NOTIF = _parse_bool("ENABLE_SLACK_NOTIF", "false")
TEST_MODE_FORCE_SLACK = _parse_bool("TEST_MODE_FORCE_SLACK", "false")

# 설정 검증 로그
logger.info(f"설정 로드 완료: LOG_LEVEL={LOG_LEVEL}, ACCELERATION_FACTOR={ACCELERATION_FACTOR}x")

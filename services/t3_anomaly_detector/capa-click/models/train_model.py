"""
훈련 전용 스크립트 (models/train_model.py)

1. 역사적 데이터(28일치)를 수집 (CSV, Mock 또는 CloudWatch)
2. Prophet 및 Isolation Forest 모델 초기 학습
3. 학습된 모델을 models/ 폴더 내에 .pkl 파일로 저장
4. 종료
"""
import os
import sys
import logging
import pandas as pd
from datetime import datetime

# [최우선] 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
    force=True
)
logger = logging.getLogger(__name__)

# [1단계] 경로 설정
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

import config
from mock_kinesis_source import MockKinesisSource
from cloudwatch_source import CloudWatchSource
import models
from models import IsolationForestDetector, ProphetDetector

# 경로 설정
MODELS_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(ROOT_DIR, "data")
PROPHET_MODEL_PATH = os.path.join(MODELS_DIR, "prophet_model.pkl")
ISO_FOREST_MODEL_PATH = os.path.join(MODELS_DIR, "iso_forest_model.pkl")

# 자동 감지할 CSV 경로 목록 (우선순위 순)
CSV_DATA_PATHS = [
    os.path.join(DATA_DIR, "historical_click_data_202602_from_athena.csv"),
    os.path.join(DATA_DIR, "historical_click_data_202602.csv")
]

def load_csv_records(csv_path: str) -> list:
    """CSV 파일을 읽어서 학습용 레코드 리스트로 변환"""
    logger.info(f"CSV 파일 로드 중: {csv_path}")
    df = pd.read_csv(csv_path, parse_dates=["timestamp"])
    # 중복 제거 및 시간순 정렬 (데이터 정합성 확보)
    df = df.drop_duplicates(subset=["timestamp"]).sort_values("timestamp")
    records = [
        {"timestamp": row["timestamp"].to_pydatetime(), "click_count": int(row["click_count"])}
        for _, row in df.iterrows()
    ]
    logger.info(f"CSV 로드 완료: {len(records)}개 포인트 ({df['timestamp'].min()} ~ {df['timestamp'].max()})")
    return records

def run_training():
    os.makedirs(MODELS_DIR, exist_ok=True)
    os.makedirs(DATA_DIR, exist_ok=True)

    # CSV 경로 자동 감지
    csv_path = None
    for path in CSV_DATA_PATHS:
        if os.path.exists(path):
            csv_path = path
            break

    logger.info("=" * 60)
    logger.info(f"데이터 소스: {'CSV 파일 (' + os.path.basename(csv_path) + ')' if csv_path else config.DATA_SOURCE}")
    logger.info("=" * 60)

    # 1. 데이터 수집
    if csv_path:
        all_records = load_csv_records(csv_path)
    elif config.DATA_SOURCE == "cloudwatch":
        source = CloudWatchSource()
        all_records = source.get_all_records()
    else:
        logger.info(f"Mock 데이터로 학습합니다 ({config.HISTORY_DAYS}일치)")
        source = MockKinesisSource(history_days=config.HISTORY_DAYS)
        all_records = source.get_all_records()
    
    if not all_records:
        logger.error("❌ 학습할 데이터가 없습니다. 종료합니다.")
        return

    # 2. 모델 학습
    logger.info(f"로그: 2. Prophet 모델 학습 시작 ({len(all_records)} 포인트)...")
    prophet = ProphetDetector()
    prophet.train(all_records)
    prophet.save(PROPHET_MODEL_PATH)

    logger.info("로그: 3. Isolation Forest 보조 모델 학습 중...")
    iso_forest = IsolationForestDetector()
    iso_forest.train(all_records)
    iso_forest.save(ISO_FOREST_MODEL_PATH)

    logger.info("=" * 60)
    logger.info("로그: 모든 훈련이 완료되었습니다! 🎉")
    logger.info("=" * 60)

if __name__ == "__main__":
    run_training()

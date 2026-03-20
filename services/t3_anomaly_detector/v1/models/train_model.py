"""
훈련 전용 스크립트 (models/train_model.py)

1. 역사적 데이터(28일치)를 수집 (Mock 또는 CloudWatch)
2. Prophet 및 Isolation Forest 모델 초기 학습
3. 학습된 모델을 models/ 폴더 내에 .pkl 파일로 저장
4. 종료
"""
import os
import sys
import logging

# [최우선] 로깅 설정을 가장 먼저 수행
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
    force=True
)
logger = logging.getLogger(__name__)

# 임포트 전 첫 로그 (사용자 안심용)
logger.info("=" * 60)
logger.info("경로 설정 및 라이브러리 초기화 중... (Trace Mode)")
logger.info("=" * 60)

# [1단계] 경로 추가
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)
logger.info(f"[1/5] 프로젝트 루트 설정 완료: {ROOT_DIR}")

# [2단계] 기본 라이브러리 임포트
logger.info("[2/5] 기본 데이터 분석 라이브러리(Pandas 등) 로드 시작...")
import pandas as pd
from datetime import datetime
logger.info("[2/5] 기본 데이터 도구 로드 완료.")

# [3단계] 설정 모듈 임포트
logger.info("[3/5] config 설정 파일 로드 시작...")
import config
logger.info("[3/5] 설정 파일 로드 완료.")

# [4단계] 데이터 소스 모듈 임포트
logger.info("[4/5] 데이터 소스 모듈(Kinesis/CloudWatch) 로드 시작...")
from mock_kinesis_source import MockKinesisSource
from cloudwatch_source import CloudWatchSource
logger.info("[4/5] 데이터 소스 엔진 준비 완료.")

# [5단계] AI 모델 모듈 임포트 (가장 무거운 구간!)
logger.info("[5/5] AI 모델 엔진(Prophet/IsolationForest) 로드 시작 (수 초 소요)...")
# 루트 폴더의 models.py를 명시적으로 찾습니다.
import models
from models import IsolationForestDetector, ProphetDetector
logger.info("[5/5] 모든 엔진 로드 완료! 이제 훈련을 시작합니다.")

# 경로 설정 (models 폴더 내부 기준)
MODELS_DIR = os.path.dirname(os.path.abspath(__file__)) # 현재 폴더
DATA_DIR = os.path.join(ROOT_DIR, "data") # 상위 폴더의 data 폴더
PROPHET_MODEL_PATH = os.path.join(MODELS_DIR, "prophet_model.pkl")
ISO_FOREST_MODEL_PATH = os.path.join(MODELS_DIR, "iso_forest_model.pkl")
HISTORICAL_DATA_PATH = os.path.join(DATA_DIR, "historical_data.csv")

def run_training():
    os.makedirs(MODELS_DIR, exist_ok=True)
    os.makedirs(DATA_DIR, exist_ok=True)

    logger.info("훈련 환경 설정 완료.")
    logger.info(f"학습 데이터 기간: {config.HISTORY_DAYS}일치")
    logger.info(f"데이터 소스: {config.DATA_SOURCE}")
    logger.info("-" * 60)

    # 1. 데이터 수집
    logger.info("로그: 1. 역사적 데이터 수집 시작...")
    if config.DATA_SOURCE == "cloudwatch":
        source = CloudWatchSource()
    else:
        source = MockKinesisSource(history_days=config.HISTORY_DAYS)
    
    all_records = source.get_all_records()
    
    # 기초 데이터 CSV 저장 (백업용)
    df = pd.DataFrame(all_records)
    df.to_csv(HISTORICAL_DATA_PATH, index=False)
    logger.info(f"로그: 기초 데이터 저장 완료 ({len(all_records)} 포인트)")

    # 2. 모델 초기화 및 학습
    logger.info("로그: 2. Prophet 모델 학습 시작 (데이터 양에 따라 수 초 ~ 수 분 소요)...")
    prophet = ProphetDetector()
    prophet.train(all_records)
    prophet.save(PROPHET_MODEL_PATH)

    logger.info("로그: 3. Isolation Forest 보조 모델 학습 중...")
    iso_forest = IsolationForestDetector()
    iso_forest.train(all_records)
    iso_forest.save(ISO_FOREST_MODEL_PATH)

    logger.info("=" * 60)
    logger.info("로그: 훈련 완료! 이제 main.py를 실행하여 이상 탐지를 시작할 수 있습니다.")
    logger.info("=" * 60)

if __name__ == "__main__":
    run_training()

"""
Ad Log Generator - 메인 실행 스크립트 (가중치 분포 버전)

기존 main.py에서 AdLogGenerator → AdLogGeneratorWeighted로 교체.
전체 데이터 생성량은 기존과 동일하게 유지하며,
각 컬럼 값의 선택 분포에 가중치를 적용하여 현실적인 데이터를 생성합니다.
"""

import time
import os
import random
from datetime import datetime
from dotenv import load_dotenv

from generator_weighted import AdLogGeneratorWeighted
from kinesis_stream_sender import KinesisStreamSender

# .env 파일 로드 (상위 디렉토리의 .env 파일 사용)
env_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), '.env')
load_dotenv(env_path)

import logging

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


# =============================================================================
# 설정
# =============================================================================

class Config:
    """환경 변수 기반 설정"""

    # Kinesis Stream 설정 (이벤트 타입별 3개 분리)
    KINESIS_IMPRESSION = os.getenv("KINESIS_IMPRESSION", "capa-knss-imp-00")
    KINESIS_CLICK = os.getenv("KINESIS_CLICK", "capa-knss-clk-00")
    KINESIS_CONVERSION = os.getenv("KINESIS_CONVERSION", "capa-knss-cvs-00")
    AWS_REGION = os.getenv("AWS_DEFAULT_REGION", "ap-northeast-2")

    # AWS 자격증명
    AWS_ACCESS_KEY_ID = os.getenv("AWS_ACCESS_KEY_ID")
    AWS_SECRET_ACCESS_KEY = os.getenv("AWS_SECRET_ACCESS_KEY")

    # 기본 sleep 시간 (초) — 트래픽 멀티플라이어로 나누어 동적 조정
    BASE_SLEEP = 0.1  # 기본 0.1초 (시간당 최대 ~36,000개)


# =============================================================================
# 트래픽 패턴 (main.py와 동일)
# =============================================================================

def get_traffic_multiplier(timestamp: datetime) -> float:
    """시간대별, 요일별 트래픽 멀티플라이어를 반환합니다."""
    hour = timestamp.hour
    weekday = timestamp.weekday()  # 0=월요일, 6=일요일

    if 0 <= hour < 1:
        hour_mult = random.uniform(0.2, 1.0)
    elif 1 <= hour < 6:
        hour_mult = random.uniform(0.2, 0.3)
    elif 6 <= hour < 7:
        hour_mult = random.uniform(0.2, 0.5)
    elif 7 <= hour < 9:
        hour_mult = random.uniform(0.3, 0.6)
    elif 9 <= hour < 11:
        hour_mult = random.uniform(0.5, 0.9)
    elif 11 <= hour < 12:
        hour_mult = random.uniform(0.9, 1.3)
    elif 12 <= hour < 13:
        hour_mult = random.uniform(1.5, 2.0)
    elif 13 <= hour < 14:
        hour_mult = random.uniform(0.7, 1.6)
    elif 14 <= hour < 17:
        hour_mult = random.uniform(0.8, 0.9)
    elif 17 <= hour < 18:
        hour_mult = random.uniform(0.8, 2.0)
    elif 18 <= hour < 21:
        hour_mult = random.uniform(2.0, 3.0)
    elif 21 <= hour < 22:
        hour_mult = random.uniform(1.3, 2.2)
    elif 22 <= hour < 23:
        hour_mult = random.uniform(1.0, 1.5)
    else:
        hour_mult = random.uniform(0.5, 1.0)

    if weekday < 4:      # 월~목
        day_mult = random.uniform(0.8, 1.0)
    elif weekday == 4:   # 금
        day_mult = random.uniform(1.2, 1.5)
    elif weekday == 5:   # 토
        day_mult = random.uniform(1.5, 2.0)
    else:                # 일
        day_mult = random.uniform(1.3, 1.7)

    return hour_mult * day_mult


# =============================================================================
# 메인 실행
# =============================================================================

def main() -> None:
    """메인 실행 함수"""

    logger.info("=" * 60)
    logger.info("Ad Log Generator (Weighted 버전) 시작")
    logger.info("=" * 60)

    # 로그 생성기 초기화 (가중치 버전)
    generator = AdLogGeneratorWeighted()
    logger.info("로그 생성기(가중치 분포) 초기화 완료")

    # Kinesis Stream Sender 초기화
    try:
        sender = KinesisStreamSender(
            stream_names={
                "impression": Config.KINESIS_IMPRESSION,
                "click": Config.KINESIS_CLICK,
                "conversion": Config.KINESIS_CONVERSION,
            },
            region=Config.AWS_REGION,
            aws_access_key_id=Config.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=Config.AWS_SECRET_ACCESS_KEY,
        )
        logger.info("Kinesis 전송 활성화 (%s)", Config.AWS_REGION)
    except Exception as e:
        logger.error("Kinesis 초기화 실패: %s", e)
        raise

    logger.info("Starting Ad Log Generator (Target: Kinesis Streams imp/clk/cvs)...")
    logger.info("=" * 60)

    try:
        while True:
            current_time = datetime.now()
            traffic_mult = get_traffic_multiplier(current_time)

            # 1. 노출 생성 및 전송
            try:
                impr = generator.generate_impression()
                sender.send(impr)
            except Exception as e:
                logger.error("노출 로그 생성/전송 실패: %s", e)
                raise

            internal_data = impr.get("_internal", {})
            ad_format = internal_data.get("ad_format", "display")
            delivery_region = internal_data.get("delivery_region", "")

            # 2. 클릭 확률 판정
            if generator.should_click(ad_format, delivery_region):
                time.sleep(random.uniform(0.5, 2.0))  # 클릭 딜레이

                try:
                    click = generator.generate_click(impr)
                    sender.send(click)
                except Exception as e:
                    logger.error("클릭 로그 생성/전송 실패: %s", e)
                    raise

                # 3. 전환 확률 판정
                if generator.should_convert():
                    time.sleep(random.uniform(1.0, 5.0))  # 전환 딜레이

                    try:
                        conv = generator.generate_conversion(click)
                        sender.send(conv)
                    except Exception as e:
                        logger.error("전환 로그 생성/전송 실패: %s", e)
                        raise

            # 동적 대기 시간 (트래픽 패턴에 따라 조정)
            sleep_time = Config.BASE_SLEEP / traffic_mult
            time.sleep(sleep_time)

    except KeyboardInterrupt:
        logger.info("=" * 60)
        logger.info("로그 생성 중지됨 (KeyboardInterrupt)")

        stats = sender.get_stats()
        stats_by_type = sender.get_stats_by_type()
        logger.info(
            "Kinesis 전송 통계 — 전체: 성공 %d / 실패 %d / 합계 %d",
            stats["success"], stats["error"], stats["total"],
        )
        for etype, s in stats_by_type.items():
            logger.info("  %s: 성공 %d / 실패 %d", etype, s["success"], s["error"])

        logger.info("=" * 60)


if __name__ == "__main__":
    main()

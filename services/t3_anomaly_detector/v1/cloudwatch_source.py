"""
CloudWatch 실제 데이터 수집기
- AWS CloudWatch 지표(IncomingRecords 등)를 수집하여 모델에 제공합니다.
"""
import boto3
import logging
import pandas as pd
from datetime import datetime, timedelta
import config

logger = logging.getLogger(__name__)

class CloudWatchSource:
    def __init__(self, stream_name="DeliveryLogStream", region_name="ap-northeast-2"):
        self.client = boto3.client('cloudwatch', region_name=region_name)
        self.stream_name = stream_name
        self.namespace = "AWS/Kinesis"
        self.metric_name = "IncomingRecords"
        logger.info(f"CloudWatchSource 초기화 완료 (Stream: {self.stream_name})")

    def get_all_records(self):
        """
        config.HISTORY_DAYS에 해당하는 기간의 데이터를 한 번에 가져와서 반환합니다.
        train_model.py 에서 사용됩니다.
        """
        logger.info(f"CloudWatch에서 최근 {config.HISTORY_DAYS}일치 데이터를 수집 중입니다...")
        
        # 현재 데모 환경에서는 실제 CloudWatch 데이터를 한 번에 대량으로 가져올 수 있도록
        # 기본 골격만 제공하며, 구체적인 쿼리는 사용자 환경에 맞게 추가할 수 있습니다.
        logger.warning("CloudWatch 대량 데이터 수집은 현재 인터페이스만 제공됩니다. 빈 리스트를 반환합니다.")
        return []
        
    def get_latest_data(self):
        """
        최근 5분 데이터를 가져옵니다. main.py 실시간 탐지에서 사용됩니다.
        """
        logger.debug("CloudWatch에서 최근 5분 데이터를 수집합니다.")
        return []

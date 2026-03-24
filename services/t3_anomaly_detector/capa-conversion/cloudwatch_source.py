"""
CloudWatch 실제 데이터 수집기
- AWS CloudWatch 지표(IncomingRecords)를 수집하여 모델에 제공합니다.
"""
import boto3
import logging
import time
from datetime import datetime, timedelta, timezone
import config

logger = logging.getLogger(__name__)

class CloudWatchSource:
    def __init__(self, stream_name="capa-knss-conv-00", region_name="ap-northeast-2"):
        self.client = boto3.client('cloudwatch', region_name=region_name)
        self.stream_name = stream_name
        self.namespace = "AWS/Kinesis"
        self.metric_name = "IncomingRecords"
        self.region = region_name
        logger.info(f"CloudWatchSource 초기화 완료 (Stream: {self.stream_name})")

    def get_all_records(self):
        """
        config.HISTORY_DAYS에 해당하는 기간의 데이터를 한 번에 가져와서 반환합니다.
        train_model.py 에서 사용됩니다.
        """
        logger.info(f"CloudWatch에서 3/21 00시부터 현재까지 데이터를 수집 중입니다...")

        try:
            # 시간 범위 설정 (KST 기준)
            kst = timezone(timedelta(hours=9))
            start_time = datetime(2026, 3, 21, 0, 0, 0, tzinfo=kst)  # KST 3월 21일 00:00:00
            #end_time = datetime.now(tz=kst)
            end_time = datetime(2026, 3, 22, 0, 0, 0, tzinfo=kst)  # KST 3월 21일 00:00:00

            logger.info(f"조회 기간: {start_time} ~ {end_time} (UTC)")

            # CloudWatch 메트릭 데이터 조회
            response = self.client.get_metric_data(
                MetricDataQueries=[
                    {
                        'Id': 'm1',
                        'MetricStat': {
                            'Metric': {
                                'Namespace': self.namespace,
                                'MetricName': self.metric_name,
                                'Dimensions': [
                                    {
                                        'Name': 'StreamName',
                                        'Value': self.stream_name
                                    }
                                ]
                            },
                            'Period': 300,  # 5분 단위
                            'Stat': 'Sum',
                        },
                        'ReturnData': True,
                    },
                ],
                StartTime=start_time,
                EndTime=end_time,
                ScanBy='TimestampDescending'
            )

            # [Zero-filling] 데이터 공백 정규화 (5분 단위)
            records = []
            results = response.get('MetricDataResults', [])
            if results and results[0].get('Timestamps'):
                timestamps = results[0]['Timestamps']
                values = results[0]['Values']
                
                # 시상(Timestamp)을 키로 하는 딕셔너리 생성
                data_dict = {ts.replace(tzinfo=None): val for ts, val in zip(timestamps, values)}
                
                # 시작 시각부터 종료 시각까지 5분 단위로 순회
                current_ptr = start_time.replace(tzinfo=None)
                end_ptr = end_time.replace(tzinfo=None)
                
                while current_ptr < end_ptr:
                    val = data_dict.get(current_ptr, 0) # 없으면 0
                    records.append({
                        "timestamp": current_ptr,
                        "conversion_count": int(val)
                    })
                    current_ptr += timedelta(minutes=5)

            logger.info(f"CloudWatch에서 {len(records)}개 데이터 포인트 수집 및 정규화 완료")
            return records

        except Exception as e:
            logger.error(f"CloudWatch 데이터 수집 실패: {e}")
            return []

    def __iter__(self):
        """
        실시간 스트리밍을 위한 generator (main.py에서 사용)
        1단계: 초기 12시간 데이터 모두 가져오기
        2단계: 그 후 5분마다 새 데이터 제공
        """
        logger.info("CloudWatch 실시간 스트리밍 시작...")
        kst = timezone(timedelta(hours=9))

        try:
            # [1단계] 실행 시점 기준 24시간 전 정각부터 현재까지 데이터 가져오기
            end_time = datetime.now(tz=kst)
            
            # 24시간 전 시간 계산 후, 분/초/마이크로초를 0으로 버림 (예: 13:36 -> 전날 13:00)
            past_24h = end_time - timedelta(hours=24)
            start_time = past_24h.replace(minute=0, second=0, microsecond=0)
            
            logger.info(f"초기 데이터: {start_time.strftime('%Y-%m-%d %H:%M')} 부터 현재({end_time.strftime('%H:%M')})까지 조회 중...")

            response = self.client.get_metric_data(
                MetricDataQueries=[
                    {
                        'Id': 'm1',
                        'MetricStat': {
                            'Metric': {
                                'Namespace': self.namespace,
                                'MetricName': self.metric_name,
                                'Dimensions': [
                                    {
                                        'Name': 'StreamName',
                                        'Value': self.stream_name
                                    }
                                ]
                            },
                            'Period': 300,  # 5분 단위
                            'Stat': 'Sum',
                        },
                        'ReturnData': True,
                    },
                ],
                StartTime=start_time,
                EndTime=end_time,
                ScanBy='TimestampDescending'
            )

            # [Zero-filling] 초기 데이터 반환 (5분 단위 정규화)
            results = response.get('MetricDataResults', [])
            if results and results[0].get('Timestamps'):
                timestamps = results[0]['Timestamps']
                values = results[0]['Values']
                
                data_dict = {ts.replace(tzinfo=None): val for ts, val in zip(timestamps, values)}
                
                current_ptr = start_time.replace(tzinfo=None)
                end_ptr = end_time.replace(tzinfo=None)
                
                count = 0
                while current_ptr < end_ptr:
                    val = data_dict.get(current_ptr, 0)
                    yield {
                        "timestamp": current_ptr,
                        "conversion_count": int(val)
                    }
                    current_ptr += timedelta(minutes=5)
                    count += 1
                
                logger.info(f"초기 데이터 정규화 완료: {count}개 포인트")

        except Exception as e:
            logger.error(f"CloudWatch 초기화 실패: {e}")

#!/usr/bin/env python3
"""
Kinesis 통합 예제 코드
ad_log_generator.py에 Kinesis 스트리밍 기능을 추가하는 예제
"""

import os
import json
import boto3
import logging
from typing import Dict, Optional
from datetime import datetime
import pandas as pd

logger = logging.getLogger(__name__)


class KinesisIntegratedAdLogGenerator:
    """Kinesis가 통합된 광고 로그 생성기 예제"""
    
    def __init__(self):
        # 기존 초기화 로직...
        self.s3_client = boto3.client('s3')
        
        # Kinesis 설정
        self.kinesis_enabled = os.getenv("ENABLE_KINESIS", "false").lower() == "true"
        self.execution_mode = os.getenv("EXECUTION_MODE", "batch")  # batch, streaming, hybrid
        
        if self.kinesis_enabled:
            self.kinesis_client = boto3.client(
                'kinesis',
                region_name=os.getenv("AWS_REGION", "ap-northeast-2")
            )
            self.kinesis_stream_name = os.getenv("KINESIS_STREAM_NAME", "capa-ad-logs-dev")
            logger.info(f"Kinesis 스트리밍 활성화: {self.kinesis_stream_name}")
    
    def send_to_kinesis(self, record: Dict, partition_key: Optional[str] = None) -> bool:
        """개별 레코드를 Kinesis로 전송"""
        if not self.kinesis_enabled:
            return False
        
        try:
            # timestamp를 ISO 형식 문자열로 변환
            if isinstance(record.get('timestamp'), datetime):
                record['timestamp'] = record['timestamp'].isoformat()
            
            # Kinesis로 전송
            response = self.kinesis_client.put_record(
                StreamName=self.kinesis_stream_name,
                Data=json.dumps(record, ensure_ascii=False),
                PartitionKey=partition_key or record.get('user_id', 'default')
            )
            
            return True
        except Exception as e:
            logger.error(f"Kinesis 전송 실패: {e}")
            return False
    
    def send_batch_to_kinesis(self, records: list, log_type: str) -> dict:
        """배치 레코드를 Kinesis로 전송"""
        if not self.kinesis_enabled or not records:
            return {"success": 0, "failed": 0}
        
        success_count = 0
        failed_count = 0
        
        # Kinesis PutRecords API는 한 번에 최대 500개 레코드 전송 가능
        batch_size = 500
        
        for i in range(0, len(records), batch_size):
            batch = records[i:i + batch_size]
            kinesis_records = []
            
            for record in batch:
                # timestamp 변환
                if isinstance(record.get('timestamp'), datetime):
                    record['timestamp'] = record['timestamp'].isoformat()
                
                # log_type 추가
                record['log_type'] = log_type
                
                kinesis_records.append({
                    'Data': json.dumps(record, ensure_ascii=False),
                    'PartitionKey': record.get('user_id', 'default')
                })
            
            try:
                response = self.kinesis_client.put_records(
                    StreamName=self.kinesis_stream_name,
                    Records=kinesis_records
                )
                
                # 실패한 레코드 확인
                failed_count += response.get('FailedRecordCount', 0)
                success_count += len(batch) - response.get('FailedRecordCount', 0)
                
            except Exception as e:
                logger.error(f"Kinesis 배치 전송 실패: {e}")
                failed_count += len(batch)
        
        logger.info(f"{log_type} Kinesis 전송 완료: 성공 {success_count}, 실패 {failed_count}")
        return {"success": success_count, "failed": failed_count}
    
    def generate_and_send_impressions(self, start_time: datetime, num_records: int):
        """노출 데이터 생성 및 전송 (하이브리드 모드)"""
        impressions = []
        
        for _ in range(num_records):
            impression = {
                'impression_id': 'imp_' + datetime.now().strftime('%Y%m%d%H%M%S%f'),
                'timestamp': start_time,
                'user_id': f'user_{_:06d}',
                'ad_id': f'ad_{_:04d}',
                # ... 기타 필드들 ...
            }
            impressions.append(impression)
            
            # 스트리밍 모드에서는 즉시 전송
            if self.execution_mode == "streaming":
                self.send_to_kinesis(impression)
        
        # DataFrame 생성
        df = pd.DataFrame(impressions)
        
        # 하이브리드 모드에서는 배치로 Kinesis 전송 + S3 저장
        if self.execution_mode == "hybrid":
            # Kinesis로 배치 전송
            self.send_batch_to_kinesis(impressions, "impression")
            
            # S3에도 저장
            self.save_to_s3(df, "impressions", start_time)
        
        # 배치 모드에서는 S3에만 저장
        elif self.execution_mode == "batch":
            self.save_to_s3(df, "impressions", start_time)
        
        return df
    
    def save_to_s3(self, df: pd.DataFrame, table_name: str, timestamp: datetime):
        """기존 S3 저장 로직"""
        # 기존 save_to_s3 메서드 구현...
        pass


# 사용 예제
if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='Kinesis 통합 광고 로그 생성기')
    parser.add_argument('--mode', choices=['batch', 'streaming', 'hybrid'],
                       default='batch', help='실행 모드')
    
    args = parser.parse_args()
    
    # 환경 변수 설정
    os.environ['EXECUTION_MODE'] = args.mode
    
    # 생성기 초기화
    generator = KinesisIntegratedAdLogGenerator()
    
    # 데이터 생성 및 전송
    start_time = datetime.now()
    
    if args.mode == "streaming":
        print("🚀 스트리밍 모드: 실시간으로 Kinesis로 전송")
        # 실시간 생성 로직...
    
    elif args.mode == "hybrid":
        print("🔄 하이브리드 모드: Kinesis와 S3 동시 저장")
        generator.generate_and_send_impressions(start_time, 1000)
    
    else:
        print("📦 배치 모드: S3에 직접 저장")
        generator.generate_and_send_impressions(start_time, 10000)
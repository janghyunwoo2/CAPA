"""
Kinesis Sender - AWS Kinesis Data Stream으로 로그 전송
"""

import json
import boto3
from typing import Dict, Optional
from botocore.exceptions import ClientError


class KinesisSender:
    """AWS Kinesis Data Stream으로 로그를 전송하는 클래스"""
    
    def __init__(
        self,
        stream_name: str,
        region: str = "ap-northeast-2",
        aws_access_key_id: Optional[str] = None,
        aws_secret_access_key: Optional[str] = None
    ):
        """
        Args:
            stream_name: Kinesis Stream 이름
            region: AWS 리전
            aws_access_key_id: AWS Access Key (선택, 환경 변수 사용 가능)
            aws_secret_access_key: AWS Secret Key (선택, 환경 변수 사용 가능)
        """
        self.stream_name = stream_name
        self.region = region
        
        # Kinesis 클라이언트 생성
        session_kwargs = {"region_name": region}
        if aws_access_key_id and aws_secret_access_key:
            session_kwargs["aws_access_key_id"] = aws_access_key_id
            session_kwargs["aws_secret_access_key"] = aws_secret_access_key
        
        try:
            self.client = boto3.client("kinesis", **session_kwargs)
            print(f"✅ Kinesis 클라이언트 생성 성공 (Stream: {stream_name}, Region: {region})", flush=True)
        except Exception as e:
            print(f"❌ Kinesis 클라이언트 생성 실패: {e}", flush=True)
            self.client = None
        
        # 통계
        self.success_count = 0
        self.error_count = 0
    
    def send(self, log: Dict) -> bool:
        """
        로그를 Kinesis Stream으로 전송
        
        Args:
            log: 전송할 로그 (dict)
        
        Returns:
            성공 여부 (bool)
        """
        if not self.client:
            # Kinesis 클라이언트가 없으면 콘솔 출력
            print(json.dumps(log, ensure_ascii=False), flush=True)
            return False
        
        try:
            # _internal 필드 제거 (전송하지 않음)
            log_copy = log.copy()
            log_copy.pop('_internal', None)
            
            # JSON으로 직렬화
            data = json.dumps(log_copy, ensure_ascii=False)
            
            # Kinesis로 전송
            # PartitionKey: user_id로 파티셔닝 (같은 유저는 같은 샤드로)
            response = self.client.put_record(
                StreamName=self.stream_name,
                Data=data + "\n",  # Athena/Firehose는 newline 구분 선호
                PartitionKey=log.get("user_id", "default")
            )
            
            self.success_count += 1
            
            # 성공 메시지 출력 (main.py 스타일)
            # 이벤트 타입 판단 (impression_id, click_id, conversion_id로)
            event_type = "impression"
            if log.get("conversion_id"):
                event_type = "conversion"
            elif log.get("click_id"):
                event_type = "click"
                
            print(
                f"[OK] Sent: {event_type} - Shard: {response['ShardId']}",
                flush=True
            )
            return True
            
        except ClientError as e:
            self.error_count += 1
            error_code = e.response.get("Error", {}).get("Code", "Unknown")
            error_msg = e.response.get("Error", {}).get("Message", str(e))
            print(f"[ERROR] Kinesis 전송 실패 [{error_code}]: {error_msg}", flush=True)
            return False
            
        except Exception as e:
            self.error_count += 1
            print(f"[ERROR] Kinesis 전송 오류: {type(e).__name__}: {e}", flush=True)
            return False
    
    def get_stats(self) -> Dict[str, int]:
        """전송 통계 반환"""
        return {
            "success": self.success_count,
            "error": self.error_count,
            "total": self.success_count + self.error_count
        }
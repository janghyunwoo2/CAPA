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
        
        self.client = boto3.client("kinesis", **session_kwargs)
        
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
        try:
            # JSON으로 직렬화
            data = json.dumps(log, ensure_ascii=False)
            
            # Kinesis로 전송
            # PartitionKey: user_id로 파티셔닝 (같은 유저는 같은 샤드로)
            response = self.client.put_record(
                StreamName=self.stream_name,
                Data=data,
                PartitionKey=log.get("user_id", "default")
            )
            
            self.success_count += 1
            return True
            
        except ClientError as e:
            self.error_count += 1
            error_code = e.response.get("Error", {}).get("Code", "Unknown")
            error_msg = e.response.get("Error", {}).get("Message", str(e))
            print(f"❌ Kinesis 전송 실패 [{error_code}]: {error_msg}", flush=True)
            return False
            
        except Exception as e:
            self.error_count += 1
            print(f"❌ Kinesis 전송 오류: {type(e).__name__}: {e}", flush=True)
            return False
    
    def get_stats(self) -> Dict[str, int]:
        """전송 통계 반환"""
        return {
            "success": self.success_count,
            "error": self.error_count,
            "total": self.success_count + self.error_count
        }

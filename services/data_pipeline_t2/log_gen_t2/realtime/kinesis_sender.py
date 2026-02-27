"""
Firehose Sender - AWS Kinesis Firehose로 이벤트 타입별 로그 전송
방법 2: Firehose 3개 (impression, click, conversion) 분리 전송
"""

import json
import boto3
from typing import Dict, Optional
from botocore.exceptions import ClientError


class FirehoseSender:
    """AWS Kinesis Firehose로 이벤트 타입별 로그를 분리 전송하는 클래스"""
    
    def __init__(
        self,
        firehose_names: Dict[str, str],
        region: str = "ap-northeast-2",
        aws_access_key_id: Optional[str] = None,
        aws_secret_access_key: Optional[str] = None
    ):
        """
        Args:
            firehose_names: 이벤트 타입별 Firehose 이름 매핑
                예: {"impression": "capa-fh-imp-00", "click": "capa-fh-clk-00", "conversion": "capa-fh-cvs-00"}
            region: AWS 리전
            aws_access_key_id: AWS Access Key (선택, 환경 변수 사용 가능)
            aws_secret_access_key: AWS Secret Key (선택, 환경 변수 사용 가능)
        """
        self.firehose_names = firehose_names
        self.region = region
        
        # Firehose 클라이언트 생성
        session_kwargs = {"region_name": region}
        if aws_access_key_id and aws_secret_access_key:
            session_kwargs["aws_access_key_id"] = aws_access_key_id
            session_kwargs["aws_secret_access_key"] = aws_secret_access_key
        
        try:
            self.client = boto3.client("firehose", **session_kwargs)
            print(f"✅ Firehose 클라이언트 생성 성공 (Region: {region})", flush=True)
            for event_type, name in firehose_names.items():
                print(f"   📌 {event_type} → {name}", flush=True)
        except Exception as e:
            print(f"❌ Firehose 클라이언트 생성 실패: {e}", flush=True)
            self.client = None
        
        # 이벤트 타입별 통계
        self.stats = {
            "impression": {"success": 0, "error": 0},
            "click": {"success": 0, "error": 0},
            "conversion": {"success": 0, "error": 0},
        }
    
    def _detect_event_type(self, log: Dict) -> str:
        """로그에서 이벤트 타입 판별"""
        if log.get("conversion_id"):
            return "conversion"
        elif log.get("click_id"):
            return "click"
        else:
            return "impression"
    
    def send(self, log: Dict) -> bool:
        """
        로그를 이벤트 타입에 맞는 Firehose로 전송
        
        Args:
            log: 전송할 로그 (dict)
        
        Returns:
            성공 여부 (bool)
        """
        # 이벤트 타입 판별
        event_type = self._detect_event_type(log)
        
        if not self.client:
            # Firehose 클라이언트가 없으면 콘솔 출력
            log_copy = log.copy()
            log_copy.pop('_internal', None)
            print(json.dumps(log_copy, ensure_ascii=False), flush=True)
            return False
        
        # 해당 이벤트 타입의 Firehose 이름 조회
        firehose_name = self.firehose_names.get(event_type)
        if not firehose_name:
            print(f"[ERROR] 알 수 없는 이벤트 타입: {event_type}", flush=True)
            return False
        
        try:
            # _internal 필드 제거 (전송하지 않음)
            log_copy = log.copy()
            log_copy.pop('_internal', None)
            
            # JSON으로 직렬화
            data = json.dumps(log_copy, ensure_ascii=False)
            
            # Firehose로 전송 (put_record)
            response = self.client.put_record(
                DeliveryStreamName=firehose_name,
                Record={"Data": data + "\n"}
            )
            
            self.stats[event_type]["success"] += 1
            
            record_id = response.get("RecordId", "")[:12]
            print(
                f"[OK] Sent: {event_type} → {firehose_name} (RecordId: {record_id}...)",
                flush=True
            )
            return True
            
        except ClientError as e:
            self.stats[event_type]["error"] += 1
            error_code = e.response.get("Error", {}).get("Code", "Unknown")
            error_msg = e.response.get("Error", {}).get("Message", str(e))
            print(f"[ERROR] Firehose 전송 실패 [{event_type} → {firehose_name}] [{error_code}]: {error_msg}", flush=True)
            return False
            
        except Exception as e:
            self.stats[event_type]["error"] += 1
            print(f"[ERROR] Firehose 전송 오류 [{event_type}]: {type(e).__name__}: {e}", flush=True)
            return False
    
    def get_stats(self) -> Dict[str, int]:
        """전송 통계 반환 (전체 합산)"""
        total_success = sum(s["success"] for s in self.stats.values())
        total_error = sum(s["error"] for s in self.stats.values())
        return {
            "success": total_success,
            "error": total_error,
            "total": total_success + total_error,
        }
    
    def get_stats_by_type(self) -> Dict[str, Dict[str, int]]:
        """이벤트 타입별 전송 통계 반환"""
        return self.stats
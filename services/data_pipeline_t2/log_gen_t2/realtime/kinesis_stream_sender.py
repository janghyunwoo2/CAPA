import json
import hashlib
from typing import Dict, Optional

import boto3
from botocore.exceptions import ClientError


class KinesisStreamSender:
    """이벤트 타입별로 Kinesis Data Streams로 전송하는 전송기.

    stream_names 예시:
        {
            "impression": "capa-knss-imp-00",
            "click": "capa-knss-clk-00",
            "conversion": "capa-knss-cvs-00",
        }
    """

    def __init__(
        self,
        stream_names: Dict[str, str],
        region: str = "ap-northeast-2",
        aws_access_key_id: Optional[str] = None,
        aws_secret_access_key: Optional[str] = None,
    ) -> None:
        self.stream_names = stream_names
        session_kwargs = {"region_name": region}
        if aws_access_key_id and aws_secret_access_key:
            session_kwargs.update(
                {
                    "aws_access_key_id": aws_access_key_id,
                    "aws_secret_access_key": aws_secret_access_key,
                }
            )
        self.client = boto3.client("kinesis", **session_kwargs)
        self.stats = {et: {"success": 0, "error": 0} for et in ("impression", "click", "conversion")}

    def _detect_event_type(self, log: Dict) -> str:
        if log.get("conversion_id"):
            return "conversion"
        if log.get("click_id"):
            return "click"
        return "impression"

    def _partition_key(self, log: Dict) -> str:
        # 분산 + 순서성 균형: session → user → impression → event
        key = log.get("session_id") or log.get("user_id") or log.get("impression_id") or log.get("event_id")
        return hashlib.md5(str(key).encode("utf-8")).hexdigest()

    def send(self, log: Dict) -> bool:
        et = self._detect_event_type(log)
        stream_name = self.stream_names.get(et)
        if not stream_name:
            print(f"[ERROR] Unknown event_type={et}", flush=True)
            return False
        try:
            payload = dict(log)
            payload.pop("_internal", None)
            data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            self.client.put_record(
                StreamName=stream_name,
                Data=data,
                PartitionKey=self._partition_key(payload),
            )
            self.stats[et]["success"] += 1
            print(f"[OK] Sent: {et} → {stream_name}", flush=True)
            return True
        except ClientError as e:
            self.stats[et]["error"] += 1
            code = e.response.get("Error", {}).get("Code", "Unknown")
            msg = e.response.get("Error", {}).get("Message", str(e))
            print(f"[ERROR] Kinesis send failed [{et}→{stream_name}] {code}: {msg}", flush=True)
            return False
        except Exception as e:
            self.stats[et]["error"] += 1
            print(f"[ERROR] Kinesis send error [{et}]: {type(e).__name__}: {e}", flush=True)
            return False

    def get_stats(self) -> Dict[str, int]:
        s = sum(v["success"] for v in self.stats.values())
        e = sum(v["error"] for v in self.stats.values())
        return {"success": s, "error": e, "total": s + e}

    def get_stats_by_type(self) -> Dict[str, Dict[str, int]]:
        return self.stats

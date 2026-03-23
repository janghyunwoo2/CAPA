"""
Redash 연동 모델 — 설계 문서 §4.4 기준
"""

from typing import Optional
from pydantic import BaseModel


class RedashConfig(BaseModel):
    base_url: str                       # K8s 내부 DNS
    api_key: str                        # Secrets Manager
    data_source_id: int                 # Athena 데이터소스 ID
    query_timeout_sec: int = 300
    poll_interval_sec: int = 3
    public_url: str                     # 사용자 전달 외부 URL
    enabled: bool = True                # FR-11 플래그


class RedashQueryCreateRequest(BaseModel):
    name: str               # "CAPA: {refined_question} [{timestamp}]"
    query: str
    data_source_id: int
    description: str = ""
    schedule: None = None


class RedashJobStatus(BaseModel):
    id: str
    status: int             # 1=대기, 2=실행중, 3=성공, 4=실패, 5=취소
    error: Optional[str] = None
    query_result_id: Optional[int] = None

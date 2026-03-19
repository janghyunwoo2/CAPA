"""
3단계 RAG 파이프라인 데이터 모델 (Phase 2)
설계 문서 §3.2 기준
"""

from typing import Literal, Optional
from pydantic import BaseModel


class CandidateDocument(BaseModel):
    """Step 4-1 벡터 검색 후보 문서"""

    text: str
    source: Literal["ddl", "documentation", "sql_example"]
    initial_score: float
    rerank_score: Optional[float] = None


class RerankResult(BaseModel):
    """Step 4-2 Reranker 출력"""

    candidates: list[CandidateDocument]
    top_k: int


class LLMFilterResult(BaseModel):
    """Step 4-3 LLM 선별 출력"""

    selected_indices: list[int]
    reason: str

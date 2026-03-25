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


class SchemaHint(BaseModel):
    """Step 3.5 SchemaMapper 출력 — 키워드 기반 테이블/컬럼 힌트"""

    tables: list[str]
    columns: list[str]
    confidence: float   # 0.5 (모호) / 0.8 (선호) / 1.0 (확정)
    is_definitive: bool  # True 시 DDL 직접 주입 + LLM 선별 스킵

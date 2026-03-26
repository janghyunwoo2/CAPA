"""
RAG 파이프라인 데이터 모델
Design §3.3 기준 — Phase 2 이후 3단계 RAG 모델 주석처리
"""

# from typing import Literal, Optional
# from pydantic import BaseModel

# 주석처리: 3단계 RAG 전용 모델 (Phase 2 이후 미사용 — 코드 참조용 보존)
# class CandidateDocument(BaseModel):
#     """Step 4-1 벡터 검색 후보 문서"""
#     text: str
#     source: Literal["ddl", "documentation", "sql_example"]
#     initial_score: float
#     rerank_score: Optional[float] = None

# class RerankResult(BaseModel):
#     """Step 4-2 Reranker 출력"""
#     candidates: list[CandidateDocument]
#     top_k: int

# class LLMFilterResult(BaseModel):
#     """Step 4-3 LLM 선별 출력"""
#     selected_indices: list[int]
#     reason: str

# 제거: SchemaHint (SchemaMapper 제거에 따라) — Design §3.3
# class SchemaHint(BaseModel):
#     """Step 3.5 SchemaMapper 출력 — 키워드 기반 테이블/컬럼 힌트"""
#     tables: list[str]
#     columns: list[str]
#     confidence: float
#     is_definitive: bool

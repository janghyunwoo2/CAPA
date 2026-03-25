"""
Step 4-2: CrossEncoderReranker — Cross-Encoder 기반 문서 재평가 (Phase 2)
설계 문서 §3.3 기준
실패 시 원본 순서 유지 (graceful degradation)
"""

import asyncio
import logging
from typing import Optional

from ..models.rag import CandidateDocument

logger = logging.getLogger(__name__)

RERANKER_MODEL = "jinaai/jina-reranker-v2-base-multilingual"


class CrossEncoderReranker:
    """Step 4-2 — Cross-Encoder 기반 문서 재평가"""

    def __init__(self, model_name: str = RERANKER_MODEL) -> None:
        self._model = None
        self._model_name = model_name
        try:
            from sentence_transformers import CrossEncoder
            self._model = CrossEncoder(model_name, trust_remote_code=True)
            logger.info(f"Reranker 모델 로드 완료: {model_name}")
        except Exception as e:
            logger.warning(f"Reranker 모델 로드 실패 (Step 4-2 스킵): {e}")

    async def rerank(
        self,
        query: str,
        candidates: list[CandidateDocument],
        top_k: int = 5,
    ) -> list[CandidateDocument]:
        """후보 문서를 Cross-Encoder로 재평가하고 상위 K개 반환.
        CPU 연산(predict)을 run_in_executor로 분리 — event loop 블록 방지.
        모델 미로드 또는 실패 시 원본 순서 그대로 반환.
        """
        if not candidates:
            return []

        if self._model is None:
            logger.warning("Reranker 모델 미로드 — 원본 순서 유지")
            return candidates[:top_k]

        pairs = [(query, doc.text) for doc in candidates]
        try:
            loop = asyncio.get_event_loop()
            scores = await loop.run_in_executor(None, self._model.predict, pairs)
            for doc, score in zip(candidates, scores):
                doc.rerank_score = float(score)

            sorted_candidates = sorted(
                candidates, key=lambda d: d.rerank_score or 0.0, reverse=True
            )
            logger.info(f"Reranker 재평가 완료: {len(candidates)}건 → 상위 {top_k}건 선별")
            return sorted_candidates[:top_k]
        except Exception as e:
            logger.error(f"Reranker 재평가 실패: {e}, 원본 순서 유지")
            return candidates[:top_k]

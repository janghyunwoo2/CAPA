"""
Phase 2 단위 테스트 — CrossEncoderReranker
커버 TC: TC-P2-U09 ~ TC-P2-U13, TC-P2-U48
대상 파일: services/vanna-api/src/pipeline/reranker.py
요구사항: FR-12 — 3단계 RAG 고도화 (Step 4-2: Reranker)
"""

import pytest
from unittest.mock import MagicMock, patch

from src.models.rag import CandidateDocument
from src.pipeline.reranker import CrossEncoderReranker


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def mock_cross_encoder():
    """CrossEncoder 모델 Mock — predict 반환값: 5건 점수"""
    model = MagicMock()
    model.predict.return_value = [0.9, 0.3, 0.7, 0.1, 0.5]
    return model


@pytest.fixture()
def sample_candidates() -> list[CandidateDocument]:
    """테스트용 후보 문서 5건"""
    return [
        CandidateDocument(text="CREATE TABLE ad_combined_log", source="ddl", initial_score=1.0),
        CandidateDocument(text="광고 로그 테이블 설명", source="documentation", initial_score=1.0),
        CandidateDocument(text="SELECT campaign_id FROM ad_combined_log", source="sql_example", initial_score=1.0),
        CandidateDocument(text="CREATE TABLE unrelated_table", source="ddl", initial_score=1.0),
        CandidateDocument(text="SELECT COUNT(*) FROM ad_combined_log", source="sql_example", initial_score=1.0),
    ]


@pytest.fixture()
def reranker_with_model(mock_cross_encoder) -> CrossEncoderReranker:
    """모델이 로드된 Reranker (mock)"""
    reranker = CrossEncoderReranker.__new__(CrossEncoderReranker)
    reranker._model = mock_cross_encoder
    reranker._model_name = "test-model"
    return reranker


@pytest.fixture()
def reranker_no_model() -> CrossEncoderReranker:
    """모델 미로드 Reranker (_model=None)"""
    reranker = CrossEncoderReranker.__new__(CrossEncoderReranker)
    reranker._model = None
    reranker._model_name = "test-model"
    return reranker


# ---------------------------------------------------------------------------
# TC-P2-U09: 빈 candidates
# ---------------------------------------------------------------------------


class TestRerankerEdgeCases:
    """경계값 및 Fallback 테스트"""

    def test_rerank_empty_candidates_returns_empty(self, reranker_with_model):
        """TC-P2-U09: 빈 후보 리스트 → 빈 리스트 반환"""
        result = reranker_with_model.rerank(query="Q", candidates=[], top_k=5)
        assert result == []

    def test_rerank_model_none_returns_original_order(self, reranker_no_model, sample_candidates):
        """TC-P2-U10: 모델 미로드(None) 시 원본 순서 상위 top_k 반환 (graceful degradation)"""
        result = reranker_no_model.rerank(query="테스트", candidates=sample_candidates, top_k=2)
        assert len(result) == 2
        assert result[0].text == sample_candidates[0].text
        assert result[1].text == sample_candidates[1].text

    def test_rerank_predict_exception_returns_original_order(self, mock_cross_encoder, sample_candidates):
        """TC-P2-U12: CrossEncoder.predict 예외 발생 시 원본 순서 유지, 예외 미전파"""
        mock_cross_encoder.predict.side_effect = RuntimeError("모델 추론 실패")
        reranker = CrossEncoderReranker.__new__(CrossEncoderReranker)
        reranker._model = mock_cross_encoder
        reranker._model_name = "test-model"

        result = reranker.rerank(query="테스트", candidates=sample_candidates, top_k=3)

        assert len(result) == 3
        assert result[0].text == sample_candidates[0].text

    def test_rerank_top_k_exceeds_candidates_returns_all(self, reranker_with_model, sample_candidates):
        """TC-P2-U13: top_k가 candidates 수 초과 시 전체 반환"""
        result = reranker_with_model.rerank(query="테스트", candidates=sample_candidates, top_k=10)
        assert len(result) == len(sample_candidates)


# ---------------------------------------------------------------------------
# TC-P2-U11: 정상 동작 (mock model)
# ---------------------------------------------------------------------------


class TestRerankerSuccess:
    """Reranker 정상 동작 테스트"""

    def test_rerank_sorts_by_score_descending(self, reranker_with_model, sample_candidates):
        """TC-P2-U11: Cross-Encoder 점수 기준 내림차순 정렬 후 상위 top_k 반환"""
        result = reranker_with_model.rerank(query="캠페인별 CTR", candidates=sample_candidates, top_k=3)

        assert len(result) == 3
        # 점수: [0.9, 0.3, 0.7, 0.1, 0.5] → 정렬 후 상위 3: [0.9, 0.7, 0.5]
        assert result[0].rerank_score >= result[1].rerank_score
        assert result[1].rerank_score >= result[2].rerank_score
        assert result[0].rerank_score == pytest.approx(0.9)


# ---------------------------------------------------------------------------
# TC-P2-U48: 모델 로드 실패 → _model=None
# ---------------------------------------------------------------------------


class TestRerankerInit:
    """초기화 실패 처리 테스트"""

    def test_init_model_load_failure_sets_model_none(self):
        """TC-P2-U48: CrossEncoder 로드 실패 시 _model=None, 예외 미전파"""
        with patch("sentence_transformers.CrossEncoder", side_effect=Exception("모델 없음")):
            reranker = CrossEncoderReranker(model_name="nonexistent-model")

        assert reranker._model is None

    def test_init_import_error_sets_model_none(self):
        """TC-P2-U48 변형: sentence_transformers ImportError 시 _model=None"""
        with patch.dict("sys.modules", {"sentence_transformers": None}):
            # sentence_transformers 임포트 실패를 시뮬레이션
            reranker = CrossEncoderReranker.__new__(CrossEncoderReranker)
            reranker._model = None
            reranker._model_name = "test"

        assert reranker._model is None

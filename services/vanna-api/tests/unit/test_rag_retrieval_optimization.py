"""
rag-retrieval-optimization 단위 테스트 (TDD Red Phase)

TC 목록:
  TC-A-01: get_related_ddl_with_score() 반환 형식 검증
  TC-A-02: score 변환 공식 검증 (distance=0 → score=1.0)
  TC-A-03: DDL 컬렉션 실패 시 fallback 동작
  TC-A-04: get_related_documentation_with_score() 반환 형식 검증
  TC-B-01: CVR 키워드 → summary 확정
  TC-B-02: ROAS 키워드 → summary 확정
  TC-B-03: 시간대 키워드 → log 확정
  TC-B-04: 피크타임 키워드 → log 확정
  TC-B-05: CTR+날짜 키워드 → summary 선호 (모호)
  TC-B-06: 빈 키워드 → 모호 처리
  TC-B-07: 충돌 키워드 (전환+시간대) → 모호 처리
  TC-B-08: is_conversion 컬럼명 직접 언급 → summary 확정
  TC-C-01: is_definitive=True 시 DDL 직접 주입 (벡터 검색 생략)
  TC-C-02: is_definitive=False 시 벡터 검색 경로 사용
  TC-D-01: is_definitive=True 시 LLM filter 호출 안 됨
  TC-D-02: is_definitive=False 시 LLM filter 호출됨
  TC-D-03: is_definitive=True 시 Reranker top_k=5
  TC-D-04: is_definitive=False 시 Reranker top_k=7
"""

import asyncio
import sys
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

# query_pipeline.py가 vanna를 최상위에서 임포트하므로 먼저 Mock 등록
if "vanna.chromadb" not in sys.modules:
    _mock_vanna_chromadb = MagicMock()
    _mock_vanna_chromadb.ChromaDB_VectorStore = type("ChromaDB_VectorStore", (), {
        "__init__": lambda self, *a, **kw: None
    })
    sys.modules["vanna.chromadb"] = _mock_vanna_chromadb
if "vanna.anthropic" not in sys.modules:
    _mock_vanna_anthropic = MagicMock()
    _mock_vanna_anthropic.Anthropic_Chat = type("Anthropic_Chat", (), {
        "__init__": lambda self, *a, **kw: None
    })
    sys.modules["vanna.anthropic"] = _mock_vanna_anthropic
for _mod in ["vanna", "vanna.base", "vanna.base.base", "vanna.utils"]:
    if _mod not in sys.modules:
        sys.modules[_mod] = MagicMock()

import chromadb.utils.embedding_functions as _chroma_ef
_chroma_ef.SentenceTransformerEmbeddingFunction = MagicMock(return_value=MagicMock())

for _mod in ["sqlglot", "sqlglot.exp"]:
    if _mod not in sys.modules:
        sys.modules[_mod] = MagicMock()
if "sqlglot.errors" not in sys.modules:
    _sqlglot_errors = MagicMock()
    _sqlglot_errors.ParseError = type("ParseError", (Exception,), {})
    sys.modules["sqlglot.errors"] = _sqlglot_errors

# ──────────────────────────────────────────────────────────────────────────────
# Phase A: VannaAthena score 오버라이드 테스트
# ──────────────────────────────────────────────────────────────────────────────

class TestPhaseADDLScore:
    """TC-A-01~04: DDL/Docs ChromaDB score 실측 반영"""

    def _make_vanna_with_ddl_collection(self, documents, distances):
        """ddl_collection.query()를 Mock한 vanna 인스턴스 생성"""
        mock_vanna = MagicMock()
        mock_vanna.ddl_collection.query.return_value = {
            "documents": [documents],
            "distances": [distances],
        }
        return mock_vanna

    def _make_vanna_with_doc_collection(self, documents, distances):
        """documentation_collection.query()를 Mock한 vanna 인스턴스 생성"""
        mock_vanna = MagicMock()
        mock_vanna.documentation_collection.query.return_value = {
            "documents": [documents],
            "distances": [distances],
        }
        return mock_vanna

    def test_tc_a_01_ddl_with_score_returns_correct_format(self):
        """TC-A-01: get_related_ddl_with_score() 반환 형식이 [{"text": str, "score": float}] 인지"""
        from src.query_pipeline import _VannaAthena

        mock_vanna = self._make_vanna_with_ddl_collection(
            documents=["CREATE TABLE ad_combined_log (...)"],
            distances=[0.5],
        )
        # _VannaAthena 인스턴스를 직접 생성하지 않고 메서드만 바인딩
        result = _VannaAthena.get_related_ddl_with_score(mock_vanna, question="어제 CTR 보여줘")

        assert isinstance(result, list)
        assert len(result) == 1
        assert "text" in result[0]
        assert "score" in result[0]
        assert result[0]["score"] == pytest.approx(1 / (1 + 0.5), rel=1e-3)

    def test_tc_a_02_score_formula_distance_zero(self):
        """TC-A-02: distance=0 (완벽 일치) 시 score=1.0"""
        from src.query_pipeline import _VannaAthena

        mock_vanna = self._make_vanna_with_ddl_collection(
            documents=["CREATE TABLE ad_combined_log (...)"],
            distances=[0.0],
        )
        result = _VannaAthena.get_related_ddl_with_score(mock_vanna, question="ad_combined_log")

        assert result[0]["score"] == pytest.approx(1.0)

    def test_tc_a_03_ddl_collection_failure_fallback(self):
        """TC-A-03: ddl_collection.query() 실패 시 get_related_ddl() fallback 호출"""
        from src.query_pipeline import _VannaAthena

        mock_vanna = MagicMock()
        mock_vanna.ddl_collection.query.side_effect = Exception("ChromaDB 연결 실패")
        mock_vanna.get_related_ddl.return_value = ["CREATE TABLE fallback (...)"]

        result = _VannaAthena.get_related_ddl_with_score(mock_vanna, question="아무거나")

        mock_vanna.get_related_ddl.assert_called_once()
        assert result[0]["score"] == 1.0  # fallback은 score=1.0 고정

    def test_tc_a_04_documentation_with_score_returns_correct_format(self):
        """TC-A-04: get_related_documentation_with_score() score=0.5 (distance=1.0)"""
        from src.query_pipeline import _VannaAthena

        mock_vanna = self._make_vanna_with_doc_collection(
            documents=["CTR 정의: 클릭수/노출수*100"],
            distances=[1.0],
        )
        result = _VannaAthena.get_related_documentation_with_score(mock_vanna, question="CTR 정의")

        assert len(result) == 1
        assert result[0]["score"] == pytest.approx(0.5)


# ──────────────────────────────────────────────────────────────────────────────
# Phase B: SchemaMapper 테스트
# ──────────────────────────────────────────────────────────────────────────────

class TestPhaseBSchemaMapper:
    """TC-B-01~08: SchemaMapper 키워드→테이블 매핑"""

    def test_tc_b_01_cvr_maps_to_summary_definitive(self):
        """TC-B-01: CVR → ad_combined_log_summary 확정"""
        from src.pipeline.schema_mapper import SchemaMapper

        mapper = SchemaMapper()
        hint = mapper.map(["CVR"])

        assert hint.tables == ["ad_combined_log_summary"]
        assert hint.is_definitive is True
        assert hint.confidence == 1.0

    def test_tc_b_02_roas_maps_to_summary_definitive(self):
        """TC-B-02: ROAS → ad_combined_log_summary 확정"""
        from src.pipeline.schema_mapper import SchemaMapper

        mapper = SchemaMapper()
        hint = mapper.map(["ROAS"])

        assert hint.tables == ["ad_combined_log_summary"]
        assert hint.is_definitive is True

    def test_tc_b_03_hourly_maps_to_log_definitive(self):
        """TC-B-03: 시간대 → ad_combined_log 확정"""
        from src.pipeline.schema_mapper import SchemaMapper

        mapper = SchemaMapper()
        hint = mapper.map(["시간대"])

        assert hint.tables == ["ad_combined_log"]
        assert hint.is_definitive is True
        assert hint.confidence == 1.0

    def test_tc_b_04_peaktime_maps_to_log_definitive(self):
        """TC-B-04: 피크타임 → ad_combined_log 확정"""
        from src.pipeline.schema_mapper import SchemaMapper

        mapper = SchemaMapper()
        hint = mapper.map(["피크타임"])

        assert hint.tables == ["ad_combined_log"]
        assert hint.is_definitive is True

    def test_tc_b_05_ctr_yesterday_prefers_summary_not_definitive(self):
        """TC-B-05: CTR+어제 → summary 선호, is_definitive=False, confidence=0.8"""
        from src.pipeline.schema_mapper import SchemaMapper

        mapper = SchemaMapper()
        hint = mapper.map(["CTR", "어제"])

        assert hint.is_definitive is False
        assert hint.confidence == pytest.approx(0.8)
        assert "ad_combined_log_summary" in hint.tables

    def test_tc_b_06_empty_keywords_returns_ambiguous(self):
        """TC-B-06: 빈 키워드 → 완전 모호 (tables=[], confidence=0.5)"""
        from src.pipeline.schema_mapper import SchemaMapper

        mapper = SchemaMapper()
        hint = mapper.map([])

        assert hint.tables == []
        assert hint.is_definitive is False
        assert hint.confidence == pytest.approx(0.5)

    def test_tc_b_07_conflict_keywords_returns_ambiguous(self):
        """TC-B-07: 전환(summary)+시간대(log) 충돌 → is_definitive=False"""
        from src.pipeline.schema_mapper import SchemaMapper

        mapper = SchemaMapper()
        hint = mapper.map(["전환", "시간대"])

        assert hint.is_definitive is False

    def test_tc_b_08_is_conversion_column_maps_to_summary(self):
        """TC-B-08: is_conversion 컬럼명 직접 → summary 확정"""
        from src.pipeline.schema_mapper import SchemaMapper

        mapper = SchemaMapper()
        hint = mapper.map(["is_conversion"])

        assert hint.tables == ["ad_combined_log_summary"]
        assert hint.is_definitive is True


# ──────────────────────────────────────────────────────────────────────────────
# Phase C: DDL 검색 최적화 테스트
# ──────────────────────────────────────────────────────────────────────────────

class TestPhaseCDDLOptimization:
    """TC-C-01~02: Schema Hint 기반 DDL 직접 주입"""

    def _make_retriever(self, mock_vanna, mock_reranker=None, mock_anthropic=None):
        from src.pipeline.rag_retriever import RAGRetriever
        return RAGRetriever(
            vanna_instance=mock_vanna,
            reranker=mock_reranker,
            anthropic_client=mock_anthropic,
        )

    def test_tc_c_01_definitive_hint_skips_vector_search(self):
        """TC-C-01: is_definitive=True 시 ddl_collection.query() 미호출"""
        from src.models.rag import SchemaHint

        mock_vanna = MagicMock()
        mock_vanna.get_related_ddl.return_value = []
        mock_vanna.get_related_documentation.return_value = []
        mock_vanna.get_similar_question_sql.return_value = []

        schema_hint = SchemaHint(
            tables=["ad_combined_log_summary"],
            columns=["is_conversion"],
            confidence=1.0,
            is_definitive=True,
        )

        retriever = self._make_retriever(mock_vanna)
        candidates = retriever._retrieve_candidates("어제 CTR", schema_hint=schema_hint)

        # DDL 벡터 검색 호출 안 됨
        mock_vanna.ddl_collection.query.assert_not_called()
        # DDL 후보가 주입됨
        ddl_candidates = [c for c in candidates if c.source == "ddl"]
        assert len(ddl_candidates) >= 1

    def test_tc_c_02_ambiguous_hint_uses_vector_search(self):
        """TC-C-02: is_definitive=False 시 벡터 검색 경로 사용"""
        from src.models.rag import SchemaHint

        mock_vanna = MagicMock()
        mock_vanna.ddl_collection.query.return_value = {
            "documents": [["CREATE TABLE ad_combined_log (...)"]],
            "distances": [[0.3]],
        }
        mock_vanna.documentation_collection.query.return_value = {
            "documents": [[]],
            "distances": [[]],
        }
        mock_vanna.get_similar_question_sql.return_value = []

        schema_hint = SchemaHint(
            tables=["ad_combined_log_summary"],
            columns=[],
            confidence=0.8,
            is_definitive=False,
        )

        retriever = self._make_retriever(mock_vanna)
        retriever._retrieve_candidates("CTR 추이", schema_hint=schema_hint)

        # 벡터 검색 호출됨 (ddl_collection.query 또는 get_related_ddl)
        called = (
            mock_vanna.ddl_collection.query.called
            or mock_vanna.get_related_ddl.called
        )
        assert called


# ──────────────────────────────────────────────────────────────────────────────
# Phase D: LLM 선별 조건부 테스트
# ──────────────────────────────────────────────────────────────────────────────

class TestPhaseDLLMFilterConditional:
    """TC-D-01~04: is_definitive 여부에 따른 LLM 선별 + Reranker top_k 분기"""

    def _make_candidates(self, n=3):
        from src.models.rag import CandidateDocument
        return [
            CandidateDocument(text=f"doc {i}", source="ddl", initial_score=0.8)
            for i in range(n)
        ]

    def _make_retriever(self, mock_vanna, mock_reranker, mock_anthropic):
        from src.pipeline.rag_retriever import RAGRetriever
        return RAGRetriever(
            vanna_instance=mock_vanna,
            reranker=mock_reranker,
            anthropic_client=mock_anthropic,
        )

    def test_tc_d_01_definitive_skips_llm_filter(self):
        """TC-D-01: is_definitive=True → anthropic_client.messages.create 미호출"""
        from src.models.rag import SchemaHint

        mock_vanna = MagicMock()
        mock_vanna.get_related_ddl.return_value = []
        mock_vanna.get_related_documentation.return_value = []
        mock_vanna.get_similar_question_sql.return_value = []

        mock_reranker = MagicMock()
        mock_reranker.rerank = AsyncMock(return_value=self._make_candidates())

        mock_anthropic = MagicMock()

        schema_hint = SchemaHint(
            tables=["ad_combined_log_summary"],
            columns=[],
            confidence=1.0,
            is_definitive=True,
        )

        retriever = self._make_retriever(mock_vanna, mock_reranker, mock_anthropic)
        asyncio.get_event_loop().run_until_complete(
            retriever.retrieve_v2("어제 CTR", keywords=["CTR"], schema_hint=schema_hint)
        )

        mock_anthropic.messages.create.assert_not_called()

    def test_tc_d_02_ambiguous_calls_llm_filter(self):
        """TC-D-02: is_definitive=False → anthropic_client.messages.create 1회 호출"""
        from src.models.rag import SchemaHint

        mock_vanna = MagicMock()
        mock_vanna.get_related_ddl.return_value = ["CREATE TABLE ..."]
        mock_vanna.get_related_documentation.return_value = []
        mock_vanna.get_similar_question_sql.return_value = []

        mock_reranker = MagicMock()
        mock_reranker.rerank = AsyncMock(return_value=self._make_candidates())

        mock_anthropic = MagicMock()
        mock_anthropic.messages.create.return_value = MagicMock(
            content=[MagicMock(text='{"selected_indices": [0], "reason": "관련"}')]
        )

        schema_hint = SchemaHint(
            tables=["ad_combined_log_summary"],
            columns=[],
            confidence=0.8,
            is_definitive=False,
        )

        retriever = self._make_retriever(mock_vanna, mock_reranker, mock_anthropic)
        asyncio.get_event_loop().run_until_complete(
            retriever.retrieve_v2("CTR 추이", keywords=["CTR"], schema_hint=schema_hint)
        )

        mock_anthropic.messages.create.assert_called_once()

    def test_tc_d_03_definitive_reranker_topk_5(self):
        """TC-D-03: is_definitive=True → Reranker top_k=5"""
        from src.models.rag import SchemaHint

        mock_vanna = MagicMock()
        mock_vanna.get_related_ddl.return_value = []
        mock_vanna.get_related_documentation.return_value = []
        mock_vanna.get_similar_question_sql.return_value = []

        mock_reranker = MagicMock()
        mock_reranker.rerank = AsyncMock(return_value=self._make_candidates())

        schema_hint = SchemaHint(
            tables=["ad_combined_log_summary"],
            columns=[],
            confidence=1.0,
            is_definitive=True,
        )

        retriever = self._make_retriever(mock_vanna, mock_reranker, MagicMock())
        asyncio.get_event_loop().run_until_complete(
            retriever.retrieve_v2("어제 CTR", keywords=["CTR"], schema_hint=schema_hint)
        )

        call_kwargs = mock_reranker.rerank.call_args.kwargs
        assert call_kwargs.get("top_k") == 5

    def test_tc_d_04_ambiguous_reranker_topk_7(self):
        """TC-D-04: is_definitive=False → Reranker top_k=7 (기본값)"""
        from src.models.rag import SchemaHint

        mock_vanna = MagicMock()
        mock_vanna.get_related_ddl.return_value = ["CREATE TABLE ..."]
        mock_vanna.get_related_documentation.return_value = []
        mock_vanna.get_similar_question_sql.return_value = []

        mock_reranker = MagicMock()
        mock_reranker.rerank = AsyncMock(return_value=self._make_candidates())

        mock_anthropic = MagicMock()
        mock_anthropic.messages.create.return_value = MagicMock(
            content=[MagicMock(text='{"selected_indices": [0], "reason": "관련"}')]
        )

        schema_hint = SchemaHint(
            tables=[],
            columns=[],
            confidence=0.5,
            is_definitive=False,
        )

        retriever = self._make_retriever(mock_vanna, mock_reranker, mock_anthropic)
        asyncio.get_event_loop().run_until_complete(
            retriever.retrieve_v2("아무 질문", keywords=[], schema_hint=schema_hint)
        )

        call_kwargs = mock_reranker.rerank.call_args.kwargs
        assert call_kwargs.get("top_k") == 7

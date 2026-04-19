"""
pipeline-rag-optimization 단위 테스트 (TDD)

TC 목록:
  TC-PRO-01: FR-PRO-02 — cosine score 변환식 (1-d)
  TC-PRO-02: FR-PRO-03 — retrieve_v2 시그니처에 schema_hint 없음
  TC-PRO-03: FR-PRO-03 — _extract_tables_from_qa_results 단일 테이블 파싱
  TC-PRO-04: FR-PRO-03 — _extract_tables_from_qa_results 두 테이블 중복 제거
  TC-PRO-05: FR-PRO-03 — _extract_tables_from_qa_results tables 없으면 빈 set
  TC-PRO-06: FR-PRO-03 — retrieve_v2 DDL 역추적 동작
  TC-PRO-07: FR-PRO-03 — retrieve_v2 fallback (tables 없으면 전체 DDL)
  TC-PRO-08: FR-PRO-03 — add_question_sql tables metadata 저장
  TC-PRO-09: FR-PRO-03 — SchemaHint models.rag에서 제거
  TC-PRO-10: FR-PRO-03 — PipelineContext schema_hint 필드 없음
  TC-PRO-11: FR-PRO-06 — DOCS_NEGATIVE_EXAMPLES 6개 항목
  TC-PRO-12: FR-PRO-07 — n_results=20 (PHASE2=true)
"""

import ast
import importlib
import inspect
import sys
import pytest
from unittest.mock import MagicMock, patch, call

# ---------------------------------------------------------------------------
# 공통 헬퍼
# ---------------------------------------------------------------------------

def _make_vanna_mock():
    """RAGRetriever용 기본 vanna mock."""
    vanna = MagicMock()
    vanna.get_similar_question_sql.return_value = []
    vanna.get_related_documentation.return_value = []
    return vanna


# ---------------------------------------------------------------------------
# TC-PRO-01: FR-PRO-02 — cosine score 변환식
# ---------------------------------------------------------------------------

class TestCosineScoreFormula:
    """TC-PRO-01: get_similar_question_sql score = max(0.0, 1.0 - distance)"""

    def test_score_is_cosine_not_l2(self):
        """distance=0.5 → score=0.5 (cosine), not 0.667 (L2)"""
        try:
            import src.query_pipeline as qp_module
        except Exception:
            pytest.skip("query_pipeline 임포트 불가 — Docker 환경에서 실행")

        mock_vanna = MagicMock()
        mock_sql_col = MagicMock()
        mock_sql_col.query.return_value = {
            "documents": [["어제 CTR은?"]],
            "metadatas": [[{"sql": "SELECT 1"}]],
            "distances": [[0.5]],
        }

        instance = qp_module._VannaAthena.__new__(qp_module._VannaAthena)
        instance.sql_collection = mock_sql_col
        instance.n_results_sql = 10

        with patch.object(qp_module, "PHASE2_RAG_ENABLED", False):
            results = instance.get_similar_question_sql(question="테스트")

        assert len(results) == 1
        score = results[0]["score"]
        # cosine: 1 - 0.5 = 0.5
        assert abs(score - 0.5) < 1e-6, f"cosine score 기대값 0.5, 실제값 {score}"

    def test_score_clamps_negative_to_zero(self):
        """distance > 1.0 → score = max(0.0, 1-d) = 0.0 (부동소수점 보호)"""
        try:
            import src.query_pipeline as qp_module
        except Exception:
            pytest.skip("query_pipeline 임포트 불가 — Docker 환경에서 실행")

        mock_sql_col = MagicMock()
        mock_sql_col.query.return_value = {
            "documents": [["질문"]],
            "metadatas": [[{"sql": "SELECT 1"}]],
            "distances": [[1.0000001]],   # 부동소수점 오차
        }

        instance = qp_module._VannaAthena.__new__(qp_module._VannaAthena)
        instance.sql_collection = mock_sql_col
        instance.n_results_sql = 10

        with patch.object(qp_module, "PHASE2_RAG_ENABLED", False):
            results = instance.get_similar_question_sql(question="테스트")

        assert len(results) == 1
        assert results[0]["score"] >= 0.0


# ---------------------------------------------------------------------------
# TC-PRO-02: FR-PRO-03 — retrieve_v2 시그니처에 schema_hint 없음
# ---------------------------------------------------------------------------

class TestRetrieveV2Signature:
    """TC-PRO-02: schema_hint 파라미터 제거 확인"""

    def test_retrieve_v2_has_no_schema_hint_param(self):
        """retrieve_v2() 시그니처에 schema_hint 없어야 함"""
        from src.pipeline.rag_retriever import RAGRetriever

        retriever = RAGRetriever(vanna_instance=_make_vanna_mock())
        params = inspect.signature(retriever.retrieve_v2).parameters
        assert "schema_hint" not in params, (
            f"schema_hint이 아직 시그니처에 남아 있음: {list(params.keys())}"
        )


# ---------------------------------------------------------------------------
# TC-PRO-03~05: FR-PRO-03 — _extract_tables_from_qa_results
# ---------------------------------------------------------------------------

class TestExtractTablesFromQaResults:
    """TC-PRO-03~05: QA metadata tables 파싱"""

    def _get_retriever(self) -> "RAGRetriever":
        from src.pipeline.rag_retriever import RAGRetriever
        return RAGRetriever(vanna_instance=_make_vanna_mock())

    def test_extracts_single_table(self):
        """TC-PRO-03: 단일 테이블 파싱"""
        retriever = self._get_retriever()
        qa_results = [
            {"tables": "['ad_combined_log']", "sql": "SELECT 1", "question": "q"},
        ]
        result = retriever._extract_tables_from_qa_results(qa_results)
        assert result == {"ad_combined_log"}

    def test_extracts_and_deduplicates_multiple_tables(self):
        """TC-PRO-04: 여러 QA에서 테이블 중복 제거"""
        retriever = self._get_retriever()
        qa_results = [
            {"tables": "['ad_combined_log']", "sql": "s1", "question": "q1"},
            {"tables": "['ad_combined_log_summary']", "sql": "s2", "question": "q2"},
            {"tables": "['ad_combined_log']", "sql": "s3", "question": "q3"},
        ]
        result = retriever._extract_tables_from_qa_results(qa_results)
        assert result == {"ad_combined_log", "ad_combined_log_summary"}

    def test_returns_empty_set_when_no_tables(self):
        """TC-PRO-05: tables metadata 없으면 빈 set 반환"""
        retriever = self._get_retriever()
        qa_results = [
            {"sql": "SELECT 1", "question": "q"},
        ]
        result = retriever._extract_tables_from_qa_results(qa_results)
        assert result == set()


# ---------------------------------------------------------------------------
# TC-PRO-06~07: FR-PRO-03 — retrieve_v2 DDL 역추적 + fallback
# ---------------------------------------------------------------------------

class TestRetrieveV2DdlInjection:
    """TC-PRO-06~07: retrieve_v2 DDL 역추적 및 fallback 동작"""

    @pytest.mark.anyio
    async def test_retrieve_v2_ddl_from_qa_metadata(self):
        """TC-PRO-06: tables metadata → 해당 DDL만 주입"""
        from src.pipeline.rag_retriever import RAGRetriever, _TABLE_DDL

        mock_vanna = _make_vanna_mock()
        mock_vanna.get_similar_question_sql.return_value = [
            {
                "question": "어제 CTR은?",
                "sql": "SELECT 1",
                "tables": "['ad_combined_log']",
                "score": 0.9,
            }
        ]
        mock_vanna.get_related_documentation.return_value = []

        retriever = RAGRetriever(vanna_instance=mock_vanna)
        ctx = await retriever.retrieve_v2(question="CTR 조회", keywords=[])

        assert len(ctx.ddl_context) == 1
        assert "ad_combined_log" in ctx.ddl_context[0]
        # summary DDL은 포함되면 안 됨
        assert "ad_combined_log_summary" not in ctx.ddl_context[0]

    @pytest.mark.anyio
    async def test_retrieve_v2_fallback_when_no_tables_metadata(self):
        """TC-PRO-07: tables 없는 QA → _TABLE_DDL 전체(2개) 주입"""
        from src.pipeline.rag_retriever import RAGRetriever, _TABLE_DDL

        mock_vanna = _make_vanna_mock()
        mock_vanna.get_similar_question_sql.return_value = [
            {"question": "q", "sql": "SELECT 1", "score": 0.9}
            # tables 없음
        ]
        mock_vanna.get_related_documentation.return_value = []

        retriever = RAGRetriever(vanna_instance=mock_vanna)
        ctx = await retriever.retrieve_v2(question="질문", keywords=[])

        assert len(ctx.ddl_context) == len(_TABLE_DDL), (
            f"fallback 시 _TABLE_DDL 전체({len(_TABLE_DDL)}개) 주입 기대, 실제 {len(ctx.ddl_context)}개"
        )


# ---------------------------------------------------------------------------
# TC-PRO-08: FR-PRO-03 — add_question_sql tables metadata 저장
# ---------------------------------------------------------------------------

class TestAddQuestionSqlTables:
    """TC-PRO-08: tables 파라미터 → metadata["tables"] 저장"""

    def test_tables_stored_in_metadata(self):
        """add_question_sql(tables=["t"]) → sql_collection.add에 tables 포함"""
        try:
            import src.query_pipeline as qp_module
        except Exception:
            pytest.skip("query_pipeline 임포트 불가 — Docker 환경에서 실행")

        mock_sql_col = MagicMock()
        instance = qp_module._VannaAthena.__new__(qp_module._VannaAthena)
        instance.sql_collection = mock_sql_col

        instance.add_question_sql(
            question="어제 CTR은?",
            sql="SELECT 1",
            tables=["ad_combined_log"],
        )

        mock_sql_col.add.assert_called_once()
        call_kwargs = mock_sql_col.add.call_args
        metadatas = call_kwargs.kwargs.get("metadatas") or call_kwargs.args[1]
        assert "tables" in metadatas[0], (
            f"metadata에 'tables' 키 없음: {metadatas}"
        )
        assert "ad_combined_log" in metadatas[0]["tables"]

    def test_tables_none_not_stored(self):
        """tables=None → metadata에 tables 키 없음"""
        try:
            import src.query_pipeline as qp_module
        except Exception:
            pytest.skip("query_pipeline 임포트 불가 — Docker 환경에서 실행")

        mock_sql_col = MagicMock()
        instance = qp_module._VannaAthena.__new__(qp_module._VannaAthena)
        instance.sql_collection = mock_sql_col

        instance.add_question_sql(question="q", sql="SELECT 1")

        call_kwargs = mock_sql_col.add.call_args
        metadatas = call_kwargs.kwargs.get("metadatas") or call_kwargs.args[1]
        assert "tables" not in metadatas[0]


# ---------------------------------------------------------------------------
# TC-PRO-09: FR-PRO-03 — SchemaHint models.rag에서 제거
# ---------------------------------------------------------------------------

class TestSchemaHintRemoved:
    """TC-PRO-09: SchemaHint 클래스 제거 확인"""

    def test_schema_hint_not_importable(self):
        """SchemaHint가 models.rag에 없어야 함"""
        import src.models.rag as rag_module
        assert not hasattr(rag_module, "SchemaHint"), (
            "SchemaHint이 아직 models.rag에 남아 있음 — 제거 필요"
        )


# ---------------------------------------------------------------------------
# TC-PRO-10: FR-PRO-03 — PipelineContext schema_hint 필드 없음
# ---------------------------------------------------------------------------

class TestPipelineContextSchemaHintRemoved:
    """TC-PRO-10: PipelineContext.schema_hint 필드 제거 확인"""

    def test_schema_hint_field_not_in_pipeline_context(self):
        """PipelineContext에 schema_hint 필드 없어야 함"""
        from src.models.domain import PipelineContext

        assert "schema_hint" not in PipelineContext.model_fields, (
            "schema_hint이 아직 PipelineContext에 남아 있음 — 제거 필요"
        )


# ---------------------------------------------------------------------------
# TC-PRO-11: FR-PRO-06 — DOCS_NEGATIVE_EXAMPLES 6개 항목
# ---------------------------------------------------------------------------

class TestDocsNegativeExamples:
    """TC-PRO-11: seed_chromadb.py에 DOCS_NEGATIVE_EXAMPLES 6개 존재"""

    def test_negative_examples_has_6_items(self):
        """DOCS_NEGATIVE_EXAMPLES가 정의되어 있고 6개 항목인지 확인"""
        import ast
        import pathlib

        # 로컬: parents[2]=services/vanna-api/, 컨테이너: parents[0]=/app/
        _base = pathlib.Path(__file__).parent
        seed_path = _base / "scripts" / "seed_chromadb.py"
        if not seed_path.exists():
            seed_path = _base.parent / "scripts" / "seed_chromadb.py"
        if not seed_path.exists():
            seed_path = _base.parents[1] / "scripts" / "seed_chromadb.py"
        source = seed_path.read_text(encoding="utf-8")

        # AST로 DOCS_NEGATIVE_EXAMPLES 변수 찾기
        # list[str] 타입 어노테이션이 있으면 AnnAssign, 없으면 Assign
        tree = ast.parse(source)
        found = False
        for node in ast.walk(tree):
            value_node = None
            if isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name) and target.id == "DOCS_NEGATIVE_EXAMPLES":
                        found = True
                        value_node = node.value
                        break
            elif isinstance(node, ast.AnnAssign):
                if isinstance(node.target, ast.Name) and node.target.id == "DOCS_NEGATIVE_EXAMPLES":
                    found = True
                    value_node = node.value

            if found and value_node is not None:
                if isinstance(value_node, ast.List):
                    count = len(value_node.elts)
                    assert count == 6, (
                        f"DOCS_NEGATIVE_EXAMPLES 항목 수 기대값 6, 실제값 {count}"
                    )
                break

        assert found, "DOCS_NEGATIVE_EXAMPLES 변수가 seed_chromadb.py에 없음"


# ---------------------------------------------------------------------------
# TC-PRO-12: FR-PRO-07 — n_results=20 (PHASE2=true)
# ---------------------------------------------------------------------------

class TestNResults:
    """TC-PRO-12: PHASE2=true 시 n_results = 20"""

    def test_n_results_is_20_when_phase2_enabled(self):
        """PHASE2_RAG_ENABLED=true → get_similar_question_sql n_results=20"""
        try:
            import src.query_pipeline as qp_module
        except Exception:
            pytest.skip("query_pipeline 임포트 불가 — Docker 환경에서 실행")

        mock_sql_col = MagicMock()
        mock_sql_col.query.return_value = {
            "documents": [[]], "metadatas": [[]], "distances": [[]]
        }

        instance = qp_module._VannaAthena.__new__(qp_module._VannaAthena)
        instance.sql_collection = mock_sql_col
        instance.n_results_sql = 10  # 기본값

        with patch.object(qp_module, "PHASE2_RAG_ENABLED", True):
            instance.get_similar_question_sql(question="테스트")

        call_kwargs = mock_sql_col.query.call_args.kwargs
        n_results = call_kwargs.get("n_results")
        assert n_results == 20, (
            f"PHASE2=true 시 n_results 기대값 20, 실제값 {n_results}"
        )

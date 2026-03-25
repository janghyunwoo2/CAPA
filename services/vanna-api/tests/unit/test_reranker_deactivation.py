"""
reranker-deactivation 단위 테스트

TC 목록:
  TC-RD-01: FR-RD-01 — RERANKER_ENABLED=false → 모듈 변수 False
  TC-RD-02: FR-RD-01 — RERANKER_ENABLED 미설정 → 기본값 True (하위 호환)
  TC-RD-03: FR-RD-01 — PHASE2=true + RERANKER=false → CrossEncoderReranker 미호출
  TC-RD-04: FR-RD-01 — PHASE2=false → RERANKER_ENABLED 무관하게 Reranker 미호출
"""

import sys
from unittest.mock import MagicMock

# query_pipeline.py가 vanna를 최상위에서 임포트하므로 먼저 Mock 등록
if "vanna.chromadb" not in sys.modules:
    _mock_vanna_chromadb = MagicMock()
    _mock_vanna_chromadb.ChromaDB_VectorStore = type(
        "ChromaDB_VectorStore", (), {"__init__": lambda self, *a, **kw: None}
    )
    sys.modules["vanna.chromadb"] = _mock_vanna_chromadb
if "vanna.anthropic" not in sys.modules:
    _mock_vanna_anthropic = MagicMock()
    _mock_vanna_anthropic.Anthropic_Chat = type(
        "Anthropic_Chat", (), {"__init__": lambda self, *a, **kw: None}
    )
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


def _reload_pipeline():
    """query_pipeline 모듈 재로드 (환경변수 반영)"""
    for mod in list(sys.modules.keys()):
        if mod == "src.query_pipeline":
            del sys.modules[mod]
    import src.query_pipeline as qp
    return qp


class TestRerankerDeactivation:
    """RERANKER_ENABLED 환경변수 동작 검증"""

    def test_reranker_enabled_false_parses_correctly(self, monkeypatch):
        """TC-RD-01: RERANKER_ENABLED=false → 모듈 변수 False"""
        monkeypatch.setenv("RERANKER_ENABLED", "false")
        monkeypatch.setenv("PHASE2_RAG_ENABLED", "false")

        qp = _reload_pipeline()

        assert qp.RERANKER_ENABLED is False

    def test_reranker_enabled_default_is_true(self, monkeypatch):
        """TC-RD-02: RERANKER_ENABLED 미설정 → 기본값 True (하위 호환)"""
        monkeypatch.delenv("RERANKER_ENABLED", raising=False)
        monkeypatch.setenv("PHASE2_RAG_ENABLED", "false")

        qp = _reload_pipeline()

        assert qp.RERANKER_ENABLED is True

    def test_crossencoder_not_called_when_reranker_disabled(self, monkeypatch):
        """TC-RD-03: PHASE2=true + RERANKER=false → CrossEncoderReranker 미호출"""
        monkeypatch.setenv("RERANKER_ENABLED", "false")
        monkeypatch.setenv("PHASE2_RAG_ENABLED", "true")

        mock_reranker_cls = MagicMock()
        sys.modules["src.pipeline.reranker"] = MagicMock(
            CrossEncoderReranker=mock_reranker_cls
        )

        qp = _reload_pipeline()

        assert qp.RERANKER_ENABLED is False
        mock_reranker_cls.assert_not_called()

    def test_phase2_disabled_reranker_irrelevant(self, monkeypatch):
        """TC-RD-04: PHASE2=false → RERANKER_ENABLED 무관하게 Reranker 미호출"""
        monkeypatch.setenv("PHASE2_RAG_ENABLED", "false")
        monkeypatch.setenv("RERANKER_ENABLED", "true")

        qp = _reload_pipeline()

        assert qp.PHASE2_RAG_ENABLED is False

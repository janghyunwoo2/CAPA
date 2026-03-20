"""
unit_phase2 공통 conftest
— vanna, chromadb 등 미설치 패키지를 세션 시작 전 Mock 등록
  (통합 테스트는 Docker Compose 환경에서 실제 패키지로 수행)
"""

import sys
from unittest.mock import MagicMock

# sqlglot: ParseError는 실제 Exception 서브클래스여야 함
if "sqlglot" not in sys.modules:
    _sqlglot_mock = MagicMock()
    sys.modules["sqlglot"] = _sqlglot_mock
if "sqlglot.exp" not in sys.modules:
    sys.modules["sqlglot.exp"] = MagicMock()
if "sqlglot.errors" not in sys.modules:
    _sqlglot_errors_mock = MagicMock()
    _sqlglot_errors_mock.ParseError = type("ParseError", (Exception,), {})
    sys.modules["sqlglot.errors"] = _sqlglot_errors_mock

# vanna: ChromaDB_VectorStore / Anthropic_Chat 은 base class로 사용됨
# → MagicMock 인스턴스 대신 일반 class로 등록해야 metaclass 충돌 방지
if "vanna.chromadb" not in sys.modules:
    _vanna_chromadb = MagicMock()
    _vanna_chromadb.ChromaDB_VectorStore = type("ChromaDB_VectorStore", (), {
        "__init__": lambda self, *a, **kw: None
    })
    sys.modules["vanna.chromadb"] = _vanna_chromadb

if "vanna.anthropic" not in sys.modules:
    _vanna_anthropic = MagicMock()
    _vanna_anthropic.Anthropic_Chat = type("Anthropic_Chat", (), {
        "__init__": lambda self, *a, **kw: None
    })
    sys.modules["vanna.anthropic"] = _vanna_anthropic

_MOCK_MODULES = [
    "vanna",
    "vanna.base",
    "vanna.base.base",
    "chromadb",
    "chromadb.config",
]

for _mod in _MOCK_MODULES:
    if _mod not in sys.modules:
        sys.modules[_mod] = MagicMock()

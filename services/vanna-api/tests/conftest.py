"""
공통 테스트 픽스처 — test-plan.md §2.1 기준
"""

import os
import pytest
import chromadb
from unittest.mock import MagicMock


@pytest.fixture
def mock_anthropic_client():
    """Anthropic API 클라이언트 Mock"""
    return MagicMock()


@pytest.fixture
def fake_api_key():
    """테스트용 API 키"""
    return "test-api-key-for-unit-tests"


@pytest.fixture
def ephemeral_chroma():
    """ChromaDB 임시 인메모리 클라이언트"""
    return chromadb.EphemeralClient()


@pytest.fixture
def mock_vanna_instance():
    """Vanna 인스턴스 Mock (RAGRetriever, SQLGenerator용)"""
    vanna = MagicMock()
    vanna.get_related_ddl.return_value = []
    vanna.get_related_documentation.return_value = []
    vanna.get_similar_question_sql.return_value = []
    vanna.generate_sql.return_value = "SELECT 1"
    return vanna


@pytest.fixture
def mock_athena_client():
    """Athena boto3 클라이언트 Mock"""
    client = MagicMock()
    client.start_query_execution.return_value = {"QueryExecutionId": "test-query-id"}
    client.get_query_execution.return_value = {
        "QueryExecution": {
            "Status": {"State": "SUCCEEDED"}
        }
    }
    return client

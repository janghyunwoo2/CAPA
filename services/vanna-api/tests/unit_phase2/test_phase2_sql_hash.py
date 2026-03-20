"""
Phase 2 단위 테스트 — SQL 해시 정규화 및 계산
커버 TC: TC-P2-U01 ~ TC-P2-U08
대상 파일: services/vanna-api/src/pipeline/sql_hash.py
요구사항: FR-17 — SQL 해시 중복 쿼리 방지
"""

import pytest

from src.pipeline.sql_hash import normalize_sql, compute_sql_hash


class TestNormalizeSQL:
    """TC-P2-U01~U05: normalize_sql() 단위 테스트"""

    def test_normalize_sql_removes_inline_comment(self):
        """TC-P2-U01: -- 인라인 주석 제거"""
        result = normalize_sql("SELECT * FROM t -- comment")
        assert result == "select * from t"

    def test_normalize_sql_removes_block_comment(self):
        """TC-P2-U02: /* */ 블록 주석 제거"""
        result = normalize_sql("SELECT /* block */ 1")
        assert result == "select 1"

    def test_normalize_sql_collapses_whitespace(self):
        """TC-P2-U03: 연속 공백·개행 → 단일 공백"""
        result = normalize_sql("SELECT   a,\n  b\nFROM   t")
        assert result == "select a, b from t"

    def test_normalize_sql_lowercases(self):
        """TC-P2-U04: 대문자 입력 소문자 변환"""
        result = normalize_sql("SELECT A FROM T")
        assert result == result.lower()
        assert result == "select a from t"

    def test_normalize_sql_empty_string(self):
        """TC-P2-U05: 빈 문자열 경계값"""
        result = normalize_sql("")
        assert result == ""


class TestComputeSQLHash:
    """TC-P2-U06~U08: compute_sql_hash() 단위 테스트"""

    def test_compute_sql_hash_same_for_equivalent_sql(self):
        """TC-P2-U06: 동일한 논리의 다른 포맷 SQL → 동일 해시"""
        sql1 = "SELECT * FROM t"
        sql2 = "select  *  from  t  -- dup"
        assert compute_sql_hash(sql1) == compute_sql_hash(sql2)

    def test_compute_sql_hash_different_for_different_sql(self):
        """TC-P2-U07: 다른 SQL → 다른 해시"""
        sql1 = "SELECT a FROM t"
        sql2 = "SELECT b FROM t"
        assert compute_sql_hash(sql1) != compute_sql_hash(sql2)

    def test_compute_sql_hash_returns_sha256_format(self):
        """TC-P2-U08: SHA-256 형식 — 64자 16진수 문자열"""
        result = compute_sql_hash("SELECT 1")
        assert len(result) == 64
        assert all(c in "0123456789abcdef" for c in result)

"""
SQL 정규화 + SHA-256 해시 (Phase 2)
설계 문서 §4.2.1 기준
"""

import hashlib
import re


def normalize_sql(sql: str) -> str:
    """SQL 정규화: 주석 제거 + 공백 통일 + 소문자 변환"""
    sql = re.sub(r'--[^\n]*', '', sql)
    sql = re.sub(r'/\*.*?\*/', '', sql, flags=re.DOTALL)
    sql = re.sub(r'\s+', ' ', sql).strip()
    return sql.lower()


def compute_sql_hash(sql: str) -> str:
    """정규화된 SQL의 SHA-256 해시"""
    return hashlib.sha256(normalize_sql(sql).encode('utf-8')).hexdigest()

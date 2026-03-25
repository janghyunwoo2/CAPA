"""
Spider EM/Exec 평가 체계 단위 테스트

TC 목록:
  TC-SN-01 ~ TC-SN-05: SQLNormalizer 테스트
  TC-EV-01 ~ TC-EV-05: ExecutionValidator 테스트
  TC-SE-01 ~ TC-SE-04: SpiderEvaluator 테스트
"""

import pytest
from unittest.mock import MagicMock, patch
from typing import Optional, Dict


# ============ 실제 구현 import ============

from spider_evaluation import (
    SpiderEvalResult,
    SQLNormalizer,
    ExecutionValidator,
    SpiderEvaluator
)


# ============ 테스트 코드 ============

class TestSQLNormalizer:
    """TC-SN-01 ~ TC-SN-05: SQLNormalizer 테스트"""

    def test_normalize_whitespace_multiple_spaces(self):
        """TC-SN-01: 연속 공백을 단일 공백으로 정규화"""
        input_sql = "SELECT  campaign_name  FROM  campaigns"
        expected = "SELECT CAMPAIGN_NAME FROM CAMPAIGNS"

        result = SQLNormalizer.normalize(input_sql)
        assert result == expected

    def test_normalize_tabs_to_spaces(self):
        """TC-SN-01: 탭을 공백으로 변환"""
        input_sql = "SELECT\tcampaign_name\tFROM\tcampaigns"
        expected = "SELECT CAMPAIGN_NAME FROM CAMPAIGNS"

        result = SQLNormalizer.normalize(input_sql)
        assert result == expected

    def test_normalize_remove_line_comments(self):
        """TC-SN-02: -- 주석 제거"""
        input_sql = "SELECT campaign_name -- 캠페인 이름\nFROM campaigns"
        result = SQLNormalizer.normalize(input_sql)

        assert "--" not in result
        assert "SELECT" in result and "FROM" in result

    def test_normalize_remove_block_comments(self):
        """TC-SN-02: /* */ 주석 제거"""
        input_sql = "SELECT campaign_name /* 이름 */ FROM campaigns"
        result = SQLNormalizer.normalize(input_sql)

        assert "/*" not in result and "*/" not in result

    def test_normalize_uppercase_conversion(self):
        """TC-SN-03: 소문자를 대문자로 변환"""
        input_sql = "select campaign_name from campaigns where year='2026'"
        result = SQLNormalizer.normalize(input_sql)

        assert "SELECT" in result
        assert "FROM" in result
        assert "WHERE" in result

    def test_normalize_keyword_spacing(self):
        """TC-SN-03: 키워드 주변 공백 정규화"""
        input_sql = "SELECT campaign_name,SUM(cost)AS total FROM campaigns"
        result = SQLNormalizer.normalize(input_sql)

        assert "SELECT" in result
        assert ", " in result  # 쉼표 뒤 공백
        assert " FROM " in result  # FROM 주변 공백

    def test_exact_match_identical_sql(self):
        """TC-SN-04: 정확히 일치하는 SQL"""
        sql1 = "SELECT campaign_name FROM campaigns"
        sql2 = "select campaign_name from campaigns"

        result = SQLNormalizer.exact_match(sql1, sql2)
        assert result is True

    def test_exact_match_different_formatting(self):
        """TC-SN-04: 형식이 다르지만 같은 SQL"""
        sql1 = "SELECT campaign_name FROM campaigns"
        sql2 = """
            select
                campaign_name
            from
                campaigns
        """

        result = SQLNormalizer.exact_match(sql1, sql2)
        assert result is True

    def test_exact_match_different_columns(self):
        """TC-SN-05: 다른 SQL (컬럼 다름)"""
        sql1 = "SELECT campaign_name FROM campaigns"
        sql2 = "SELECT campaign_name, cost FROM campaigns"

        result = SQLNormalizer.exact_match(sql1, sql2)
        assert result is False

    def test_exact_match_different_conditions(self):
        """TC-SN-05: 다른 SQL (WHERE 조건 다름)"""
        sql1 = "SELECT campaign_name FROM campaigns WHERE year='2026'"
        sql2 = "SELECT campaign_name FROM campaigns WHERE year='2025'"

        result = SQLNormalizer.exact_match(sql1, sql2)
        assert result is False


class TestExecutionValidator:
    """TC-EV-01 ~ TC-EV-05: ExecutionValidator 테스트"""

    @pytest.fixture
    def validator(self):
        """ExecutionValidator 인스턴스"""
        return ExecutionValidator("test-key", "http://localhost:5000")

    def test_execute_sql_success(self, validator):
        """TC-EV-01: Redash API Mock에서 SQL 정상 실행"""
        mock_result = {
            "rows": [
                {"campaign_name": "Campaign_A", "ctr": 0.085},
                {"campaign_name": "Campaign_B", "ctr": 0.072},
            ],
            "row_count": 2,
            "columns": ["campaign_name", "ctr"]
        }

        with patch('requests.post') as mock_post, \
             patch('requests.get') as mock_get:
            # 첫 번째 post (쿼리 생성)
            post_create = MagicMock()
            post_create.status_code = 200
            post_create.json.return_value = {"id": 123}

            # 두 번째 post (쿼리 실행)
            post_refresh = MagicMock()
            post_refresh.status_code = 200
            post_refresh.json.return_value = {"query_hash": "abc123"}

            mock_post.side_effect = [post_create, post_refresh]

            # get (결과 조회)
            mock_get.return_value.status_code = 200
            mock_get.return_value.json.return_value = {"query_result": {"data": {
                "rows": mock_result["rows"],
                "columns": [{"name": "campaign_name"}, {"name": "ctr"}]
            }}}

            result = validator.execute_sql("SELECT campaign_name, ctr FROM campaigns LIMIT 2")

            # 실제 반환 값 확인 (구현 후)
            assert result is not None
            assert result["row_count"] == 2

    def test_execute_sql_timeout(self, validator):
        """TC-EV-02: SQL 실행 타임아웃 (60초 초과)"""
        with patch('requests.post') as mock_post:
            from concurrent.futures import TimeoutError as FuturesTimeoutError
            mock_post.side_effect = TimeoutError()

            result = validator.execute_sql("SELECT * FROM campaigns", timeout_seconds=1)

            assert result is None  # 타임아웃 시 None 반환

    def test_execute_sql_api_error(self, validator):
        """TC-EV-02: Redash API 오류"""
        with patch('requests.post') as mock_post:
            mock_post.side_effect = Exception("API Error")

            result = validator.execute_sql("SELECT * FROM campaigns")

            assert result is None  # 오류 시 None 반환

    def test_compare_results_identical(self, validator):
        """TC-EV-03: 결과 일치"""
        result1 = {
            "rows": [{"campaign_name": "A", "ctr": 0.085}],
            "row_count": 1,
            "columns": ["campaign_name", "ctr"]
        }
        result2 = {
            "rows": [{"campaign_name": "A", "ctr": 0.085}],
            "row_count": 1,
            "columns": ["campaign_name", "ctr"]
        }

        assert validator.compare_results(result1, result2) is True

    def test_compare_results_different_row_count(self, validator):
        """TC-EV-04: 행 수 다름"""
        result1 = {
            "rows": [{"id": 1}, {"id": 2}, {"id": 3}],
            "row_count": 3,
            "columns": ["id"]
        }
        result2 = {
            "rows": [{"id": 1}, {"id": 2}],
            "row_count": 2,
            "columns": ["id"]
        }

        assert validator.compare_results(result1, result2) is False

    def test_compare_results_different_data(self, validator):
        """TC-EV-05: 데이터 값 다름"""
        result1 = {
            "rows": [{"ctr": 0.085}],
            "row_count": 1,
            "columns": ["ctr"]
        }
        result2 = {
            "rows": [{"ctr": 0.075}],
            "row_count": 1,
            "columns": ["ctr"]
        }

        assert validator.compare_results(result1, result2) is False

    def test_compare_results_order_independent(self, validator):
        """TC-EV-03: 행 순서는 무관"""
        result1 = {
            "rows": [{"id": 1}, {"id": 2}],
            "row_count": 2,
            "columns": ["id"]
        }
        result2 = {
            "rows": [{"id": 2}, {"id": 1}],  # 순서 다름
            "row_count": 2,
            "columns": ["id"]
        }

        assert validator.compare_results(result1, result2) is True


class TestSpiderEvaluator:
    """TC-SE-01 ~ TC-SE-04: SpiderEvaluator 테스트"""

    @pytest.fixture
    def evaluator(self):
        """SpiderEvaluator 인스턴스"""
        return SpiderEvaluator("http://localhost:8000", "test-key")

    @pytest.fixture
    def mock_vanna(self):
        """Vanna Mock 클라이언트"""
        vanna = MagicMock()
        vanna.generate_sql.return_value = "SELECT campaign_name FROM campaigns LIMIT 5"
        return vanna

    def test_evaluate_single_perfect_match(self, evaluator, mock_vanna):
        """TC-SE-01: 완벽한 일치 (EM=1.0, Exec=1.0)"""
        test_case = {
            "id": "T001",
            "question": "지난주 CTR이 높은 캠페인 5개",
            "ground_truth_sql": "SELECT campaign_name FROM campaigns LIMIT 5"
        }

        with patch.object(evaluator._validator, 'execute_sql') as mock_exec, \
             patch.object(evaluator._validator, 'compare_results') as mock_compare, \
             patch.object(SQLNormalizer, 'exact_match') as mock_em:

            mock_exec.return_value = {"rows": [], "row_count": 5, "columns": []}
            mock_compare.return_value = True
            mock_em.return_value = True

            result = evaluator.evaluate_single(test_case, mock_vanna)

            assert result.em_score == 1.0
            assert result.exec_score == 1.0
            assert result.avg_score == 1.0

    def test_evaluate_single_generation_failure(self, evaluator, mock_vanna):
        """TC-SE-02: SQL 생성 실패 (Graceful degradation)"""
        test_case = {
            "id": "T002",
            "question": "불가능한 질문",
            "ground_truth_sql": "SELECT * FROM campaigns"
        }

        mock_vanna.generate_sql.side_effect = Exception("Generation failed")

        result = evaluator.evaluate_single(test_case, mock_vanna)

        assert result.em_score == 0.0
        assert result.exec_score == 0.0
        assert result.exec_error is not None

    def test_evaluate_batch_multiple_cases(self, evaluator, mock_vanna):
        """TC-SE-04: 배치 평가 (3개 케이스)"""
        test_cases = [
            {
                "id": "T001",
                "question": "캠페인 조회",
                "ground_truth_sql": "SELECT campaign_name FROM campaigns"
            },
            {
                "id": "T002",
                "question": "캠페인 이름",
                "ground_truth_sql": "SELECT campaign_name FROM campaigns"
            },
            {
                "id": "T003",
                "question": "캠페인 목록",
                "ground_truth_sql": "SELECT campaign_name FROM campaigns"
            }
        ]

        results = evaluator.evaluate_batch(test_cases, mock_vanna)

        assert len(results) == 3
        assert all(isinstance(r, SpiderEvalResult) for r in results)

    def test_generate_report_format(self, evaluator):
        """TC-SE-03: JSON 리포트 형식"""
        results = [
            SpiderEvalResult("T001", "Q1", "SQL1", "SQL1", 1.0, 1.0),
            SpiderEvalResult("T002", "Q2", "SQL2", "SQL2", 0.0, 0.0),
            SpiderEvalResult("T003", "Q3", "SQL3", "SQL3", 1.0, 1.0)
        ]

        report = evaluator.generate_report(results)

        assert report["total_cases"] == 3
        assert report["em"]["passed"] == 2
        assert report["em"]["accuracy"] == 2/3
        assert report["exec"]["passed"] == 2
        assert report["exec"]["accuracy"] == 2/3
        assert len(report["details"]) == 3

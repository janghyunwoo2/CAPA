"""
Spider EM/Exec 평가 엔진 — SQLNormalizer, ExecutionValidator, SpiderEvaluator

구현 기준: Design 문서 (spider-em-exec-evaluation.design.md)
"""

import re
import json
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, Any
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError
import requests

_KST = timezone(timedelta(hours=9))

logger = logging.getLogger(__name__)


class SQLNormalizer:
    """SQL 정규화 — EM (Exact Match) 계산용"""

    @staticmethod
    def normalize(sql_str: str) -> str:
        """
        SQL을 정규화된 형식으로 변환

        처리:
        1. 주석 제거 (-- /* */)
        2. 공백 통일 (탭→공백, 연속 공백→1칸)
        3. 대문자 변환
        4. 키워드 주변 공백 정규화

        Args:
            sql_str: 입력 SQL

        Returns:
            정규화된 SQL 문자열
        """
        # 1. -- 주석 제거
        sql_str = re.sub(r"--.*$", "", sql_str, flags=re.MULTILINE)

        # 2. /* */ 주석 제거
        sql_str = re.sub(r"/\*.*?\*/", "", sql_str, flags=re.DOTALL)

        # 3. 탭을 공백으로 변환
        sql_str = sql_str.replace("\t", " ")

        # 4. 연속 공백을 단일 공백으로
        sql_str = re.sub(r"\s+", " ", sql_str).strip()

        # 5. 대문자 변환
        sql_str = sql_str.upper()

        # 6. 키워드 주변 공백 정규화
        keywords = [
            "SELECT", "FROM", "WHERE", "ORDER BY", "GROUP BY", "LIMIT",
            "AS", "AND", "OR", "JOIN", "INNER JOIN", "LEFT JOIN",
            "INSERT", "UPDATE", "DELETE", "HAVING"
        ]
        for keyword in keywords:
            # 키워드 앞뒤 공백 정규화
            sql_str = re.sub(rf"\s+({re.escape(keyword)})\s+", rf" {keyword} ", sql_str)

        # 7. 쉼표 뒤 공백 정규화
        sql_str = re.sub(r",\s*", ", ", sql_str)

        return sql_str.strip()

    @staticmethod
    def strip_limit(sql: str) -> str:
        """EM 비교용: LIMIT 절 제거.

        sql_validator.py가 LIMIT 없는 SQL에 자동으로 LIMIT 1000을 추가하므로,
        EM 비교 전 양쪽 SQL에서 LIMIT 절을 제거하여 비교 공정성 확보.

        Args:
            sql: SQL 문자열

        Returns:
            LIMIT 절이 제거된 SQL 문자열
        """
        return re.sub(r'\s+LIMIT\s+\d+\s*;?\s*$', '', sql.strip(), flags=re.IGNORECASE).strip()

    @staticmethod
    def exact_match(sql1: str, sql2: str) -> bool:
        """
        두 SQL이 정확히 일치하는가?

        Args:
            sql1: 첫 번째 SQL
            sql2: 두 번째 SQL

        Returns:
            일치 여부
        """
        return SQLNormalizer.normalize(sql1) == SQLNormalizer.normalize(sql2)


class ExecutionValidator:
    """SQL 실행 & 결과 비교 — Redash API 연동"""

    def __init__(self, redash_api_key: str, redash_base_url: str):
        """
        Redash 클라이언트 초기화

        Args:
            redash_api_key: Redash API 키
            redash_base_url: Redash 베이스 URL (예: http://localhost:5000)
        """
        self._api_key = redash_api_key
        self._base_url = redash_base_url
        self._headers = {"Authorization": f"Key {redash_api_key}"}

    def execute_sql(self, sql: str, timeout_seconds: int = 60, name: Optional[str] = None) -> Optional[Dict]:
        """
        Redash에서 SQL 실행

        프로세스:
        1. 임시 쿼리 생성 (POST /api/queries)
        2. 쿼리 실행 (POST /api/queries/{id}/refresh)
        3. 결과 조회 (GET /api/query_results/{hash})

        Args:
            sql: 실행할 SQL
            timeout_seconds: 타임아웃 (초)
            name: Redash 쿼리 이름 (없으면 자동 생성)

        Returns:
            {
                "rows": [
                    {col1: val1, col2: val2, ...},
                    ...
                ],
                "row_count": int,
                "columns": ["col1", "col2", ...]
            }
            또는 None (실패 시)
        """
        import time as _time
        try:
            # 1. 임시 쿼리 생성
            ts = datetime.now(_KST).strftime('%Y-%m-%d %H:%M')
            query_name = name or f"CAPA: [GT] [{ts}]"
            create_resp = requests.post(
                f"{self._base_url}/api/queries",
                headers=self._headers,
                json={"query": sql, "data_source_id": 1, "name": query_name},
                timeout=timeout_seconds
            )
            if create_resp.status_code != 200:
                logger.error(f"쿼리 생성 실패: {create_resp.text}")
                return None
            query_id = create_resp.json()["id"]

            # 2. 쿼리 실행 (job 반환)
            refresh_resp = requests.post(
                f"{self._base_url}/api/queries/{query_id}/refresh",
                headers=self._headers,
                timeout=timeout_seconds
            )
            if refresh_resp.status_code != 200:
                logger.error(f"쿼리 실행 요청 실패: {refresh_resp.text}")
                return None
            job_id = refresh_resp.json().get("job", {}).get("id")
            if not job_id:
                logger.error("job_id 없음")
                return None

            # 3. Job 폴링 (status: 1=PENDING, 2=STARTED, 3=SUCCESS, 4=FAILURE)
            query_result_id = None
            for _ in range(timeout_seconds):
                _time.sleep(1)
                job_resp = requests.get(
                    f"{self._base_url}/api/jobs/{job_id}",
                    headers=self._headers,
                    timeout=10
                )
                if job_resp.status_code != 200:
                    continue
                job = job_resp.json().get("job", {})
                status = job.get("status")
                if status == 3:  # SUCCESS
                    query_result_id = job.get("query_result_id")
                    break
                elif status == 4:  # FAILURE
                    logger.warning(f"Athena 실행 실패: {job.get('error', '')[:100]}")
                    return None

            if not query_result_id:
                logger.error("query_result_id 없음 (타임아웃)")
                return None

            # 4. 결과 조회
            result_resp = requests.get(
                f"{self._base_url}/api/query_results/{query_result_id}",
                headers=self._headers,
                timeout=timeout_seconds
            )
            if result_resp.status_code != 200:
                logger.error(f"결과 조회 실패: {result_resp.text}")
                return None

            data = result_resp.json().get("query_result", {}).get("data", {})
            rows = data.get("rows", [])[:10]  # /query 응답과 동일한 10행 제한 — 공정한 비교
            columns = [col.get("name") for col in data.get("columns", [])]
            return {"rows": rows, "row_count": len(rows), "columns": columns}

        except (requests.Timeout, TimeoutError, FuturesTimeoutError) as e:
            logger.error(f"SQL 실행 타임아웃: {e}")
            return None
        except Exception as e:
            logger.error(f"SQL 실행 오류: {e}")
            return None

    def compare_results(self, result1: Dict, result2: Dict) -> bool:
        """
        두 쿼리 결과가 같은가?

        비교 기준:
        1. 행 수 동일
        2. 컬럼 수 동일
        3. 데이터 값 동일 (순서 무관, 컬럼명 무시)
           alias가 달라도 실제 값이 같으면 PASS

        Args:
            result1: 첫 번째 결과
            result2: 두 번째 결과

        Returns:
            일치 여부
        """
        # 1. 행 수 비교
        if result1.get("row_count") != result2.get("row_count"):
            return False

        # 2. 컬럼 수 비교 (이름은 무시 — alias 차이 허용)
        cols1 = result1.get("columns", [])
        cols2 = result2.get("columns", [])
        if len(cols1) != len(cols2):
            return False

        # 3. 데이터 값 비교 (순서 무관, 컬럼명 무시 — values만 추출)
        rows1 = sorted(
            [json.dumps(list(r.values()), default=str) for r in result1.get("rows", [])]
        )
        rows2 = sorted(
            [json.dumps(list(r.values()), default=str) for r in result2.get("rows", [])]
        )

        return rows1 == rows2


class SpiderEvalResult:
    """Spider 평가 결과 데이터 클래스"""

    def __init__(
        self,
        test_id: str,
        question: str,
        generated_sql: str,
        ground_truth_sql: str,
        exec_score: float,
        exec_error: Optional[str] = None
    ):
        self.test_id = test_id
        self.question = question
        self.generated_sql = generated_sql
        self.ground_truth_sql = ground_truth_sql
        self.exec_score = exec_score
        self.exec_error = exec_error


class SpiderEvaluator:
    """배치 평가 엔진"""

    def __init__(self, vanna_api_url: str, redash_api_key: str):
        """
        SpiderEvaluator 초기화

        Args:
            vanna_api_url: Vanna API URL
            redash_api_key: Redash API 키
        """
        self._vanna_url = vanna_api_url
        self._validator = ExecutionValidator(redash_api_key, "http://localhost:5000")

    def evaluate_single(self, test_case: Dict, vanna_client) -> SpiderEvalResult:
        """
        단일 테스트 케이스 평가

        Args:
            test_case: 테스트 케이스 (id, question, ground_truth_sql 포함)
            vanna_client: Vanna 클라이언트

        Returns:
            SpiderEvalResult
        """
        test_id = test_case.get("id")
        question = test_case.get("question")
        ground_truth_sql = test_case.get("ground_truth_sql")

        # 1. /query API로 SQL 생성 + Athena 실행 결과 한번에 수신
        try:
            generated_sql, gen_rows = vanna_client.query(question=question)
            if not generated_sql or not generated_sql.strip():
                generated_sql = ""
        except Exception as e:
            logger.error(f"[{test_id}] SQL 생성 실패: {e}")
            return SpiderEvalResult(
                test_id=test_id,
                question=question,
                generated_sql="",
                ground_truth_sql=ground_truth_sql,
                exec_score=0.0,
                exec_error=str(e)
            )

        # 2. Exec (Execution Accuracy) 계산
        # /query 결과(gen_rows)와 ground truth SQL 실행 결과만 비교 — 생성 SQL 재실행 없음
        exec_score = 0.0
        exec_error = None

        ts = datetime.now(_KST).strftime('%Y-%m-%d %H:%M')
        gt_name = f"CAPA: {question} [GT] [{ts}]"

        if not gen_rows:
            # LLM 결과 없음 → GT도 실행해서 양쪽 빈 결과인지 확인
            try:
                gt_result = self._validator.execute_sql(ground_truth_sql, name=gt_name)
                gt_rows = gt_result.get("rows", []) if gt_result else []
                if not gt_rows and generated_sql:
                    # 양쪽 모두 빈 결과 → SQL 유사도로 판정
                    import difflib
                    norm_gen = SQLNormalizer.normalize(generated_sql)
                    norm_gt = SQLNormalizer.normalize(ground_truth_sql)
                    similarity = difflib.SequenceMatcher(None, norm_gen, norm_gt).ratio()
                    if similarity >= 0.6:
                        exec_score = 1.0
                        exec_error = f"양쪽 데이터 없음 — SQL 유사도 {similarity:.2f} ≥ 0.6 → PASS"
                        logger.info(f"[{test_id}] 양쪽 빈 결과, 유사도={similarity:.2f} → PASS")
                    else:
                        exec_error = f"양쪽 데이터 없음 — SQL 유사도 {similarity:.2f} < 0.6 → FAIL (쿼리 구조 불일치)"
                        logger.info(f"[{test_id}] 양쪽 빈 결과, 유사도={similarity:.2f} → FAIL")
                else:
                    exec_error = "생성 SQL Athena 실행 실패 (results 없음)"
            except Exception:
                exec_error = "생성 SQL Athena 실행 실패 (results 없음)"
        else:
            try:
                # ground truth SQL 실행 (동일한 10행 제한 적용 — 공정한 비교)
                gt_result = self._validator.execute_sql(ground_truth_sql, name=gt_name)
                if not gt_result:
                    exec_error = "정답 SQL 실행 실패"
                else:
                    gen_cols = list(gen_rows[0].keys()) if gen_rows else []
                    gen_result = {
                        "rows": gen_rows[:10],
                        "row_count": len(gen_rows[:10]),
                        "columns": gen_cols,
                    }
                    exec_score = 1.0 if self._validator.compare_results(gen_result, gt_result) else 0.0
            except Exception as e:
                logger.error(f"[{test_id}] Exec 검증 실패: {e}")
                exec_error = str(e)

        return SpiderEvalResult(
            test_id=test_id,
            question=question,
            generated_sql=generated_sql,
            ground_truth_sql=ground_truth_sql,
            exec_score=exec_score,
            exec_error=exec_error
        )

    def evaluate_batch(self, test_cases: list, vanna_client) -> list:
        """
        배치 평가 (여러 테스트 케이스)

        Args:
            test_cases: 테스트 케이스 리스트
            vanna_client: Vanna 클라이언트

        Returns:
            [SpiderEvalResult, ...]
        """
        results = []
        for test_case in test_cases:
            logger.info(f"평가 진행: {test_case.get('id')}")
            result = self.evaluate_single(test_case, vanna_client)
            results.append(result)

        return results

    def generate_report(self, results: list) -> Dict:
        """
        평가 리포트 생성

        Args:
            results: SpiderEvalResult 리스트

        Returns:
            {
                "total_cases": int,
                "exec": {"passed": int, "accuracy": float},
                "details": [...]
            }
        """
        total = len(results)
        exec_passed = sum(1 for r in results if r.exec_score == 1.0)
        exec_accuracy = exec_passed / total if total > 0 else 0.0

        details = [
            {
                "test_id": r.test_id,
                "question": r.question,
                "exec": r.exec_score,
                "error": r.exec_error
            }
            for r in results
        ]

        return {
            "total_cases": total,
            "exec": {
                "passed": exec_passed,
                "accuracy": exec_accuracy
            },
            "details": details
        }

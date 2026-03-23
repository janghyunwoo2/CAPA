"""
Spider EM/Exec 평가 실행 스크립트

평가 대상: Step 5 (SQL 생성) 단독
  - SQL 생성: vanna-api 컨테이너에 POST /query (execute=false) 요청
  - Exec 비교: ExecutionValidator가 Redash에 직접 요청

사용법:
  python run_evaluation.py [--test-cases FILE] [--output FILE] [--limit N]

필수 환경변수:
  VANNA_API_URL   vanna-api 컨테이너 URL (기본: http://localhost:8080)
  REDASH_API_KEY  Redash API 키 (Exec 평가 사용)
  REDASH_BASE_URL Redash URL (기본: http://localhost:5000)
"""

import json
import os
import sys
import logging
import argparse
import requests
from pathlib import Path
from typing import Optional

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)8s] %(name)s — %(message)s'
)
logger = logging.getLogger(__name__)

try:
    from spider_evaluation import SpiderEvaluator
except ImportError:
    print("❌ Error: spider_evaluation 모듈을 찾을 수 없습니다.")
    print("   실행 위치: services/vanna-api/evaluation 디렉토리")
    sys.exit(1)


class _SQLGeneratorAdapter:
    """
    vanna-api 컨테이너에 POST /query (execute=false) 를 보내서 SQL만 받아오는 어댑터.
    spider_evaluation.py 내부에서 vanna_client.generate_sql(question=...) 로 호출한다.
    """

    def __init__(self, api_url: str = "http://localhost:8080") -> None:
        self._url = f"{api_url}/query"
        logger.info(f"✅ HTTP 어댑터 초기화 완료 (endpoint: {self._url})")

    def generate_sql(self, question: str) -> str:
        """
        POST /query (Step 1~9 전체 실행) 후 sql 필드 반환.
        - 200 성공: sql 필드 직접 반환
        - REDASH_ERROR: 생성된 SQL은 성공했으나 Athena 실행 실패 (컬럼 오류 등)
          → EM 평가는 가능하도록 detail에서 SQL 추출, Exec는 0점 처리됨
        """
        import re as _re
        token = os.getenv("INTERNAL_API_TOKEN", "test-token")
        headers = {"X-Internal-Token": token}
        try:
            resp = requests.post(
                self._url,
                json={"question": question},
                headers=headers,
                timeout=120,
            )
            resp.raise_for_status()
            sql = resp.json().get("sql", "")
            if not sql:
                logger.warning(f"SQL 미반환: question={question[:50]}")
            return sql or ""
        except requests.HTTPError as e:
            # REDASH_ERROR: Athena 실행 실패지만 SQL은 생성됨 → EM용으로 추출
            if e.response.status_code in (422, 500):
                try:
                    detail = e.response.json().get("detail", {})
                    if isinstance(detail, dict):
                        sql = detail.get("detail", "")
                        if sql:
                            sql = _re.sub(r"^```(?:sql)?\s*\n?", "", sql, flags=_re.IGNORECASE)
                            sql = _re.sub(r"\n?```\s*$", "", sql).strip()
                            if sql:
                                logger.info(f"SQL 추출 ({detail.get('error_code')}): {question[:50]}")
                                return sql
                except Exception:
                    pass
            logger.error(f"API 오류 ({e.response.status_code}): {e.response.text[:200]}")
            raise
        except requests.Timeout:
            logger.error("API 타임아웃 (120초 초과)")
            raise


class EvaluationRunner:
    """Spider 평가 실행기 (컨테이너 HTTP 방식)"""

    def __init__(
        self,
        vanna_api_url: Optional[str] = None,
        redash_api_key: Optional[str] = None,
        redash_base_url: Optional[str] = None,
    ):
        vanna_api_url  = vanna_api_url  or os.getenv("VANNA_API_URL",  "http://localhost:8080")
        redash_api_key = redash_api_key or os.getenv("REDASH_API_KEY", "")
        redash_base_url = redash_base_url or os.getenv("REDASH_BASE_URL", "http://localhost:5000")

        if not redash_api_key:
            logger.warning("⚠️  REDASH_API_KEY 미설정 — Exec 평가는 None 반환됩니다.")

        self.evaluator = SpiderEvaluator(
            vanna_api_url=vanna_api_url,
            redash_api_key=redash_api_key,
        )
        self.evaluator._validator._base_url = redash_base_url

        self.sql_generator = _SQLGeneratorAdapter(api_url=vanna_api_url)

    def load_test_cases(self, path: str, limit: Optional[int] = None) -> list:
        file_path = Path(path)
        if not file_path.exists():
            logger.error(f"❌ 파일 없음: {file_path}")
            sys.exit(1)
        with open(file_path, encoding="utf-8") as f:
            cases = json.load(f)
        if limit:
            cases = cases[:limit]
        logger.info(f"테스트 케이스 {len(cases)}개 로드")
        return cases

    def run(self, test_cases_file: str = "test_cases.json", limit: Optional[int] = None) -> dict:
        logger.info("=" * 60)
        logger.info("Spider EM/Exec 평가 시작 (Step 5: SQL 생성 정확도)")
        logger.info("=" * 60)

        cases = self.load_test_cases(test_cases_file, limit)
        results = self.evaluator.evaluate_batch(cases, self.sql_generator)
        report = self.evaluator.generate_report(results)

        logger.info("=" * 60)
        logger.info(f"  총 케이스  : {report['total_cases']}")
        logger.info(f"  EM Accuracy: {report['em']['accuracy']*100:.1f}%  ({report['em']['passed']}/{report['total_cases']} PASS)")
        logger.info(f"  Exec Accura: {report['exec']['accuracy']*100:.1f}%  ({report['exec']['passed']}/{report['total_cases']} PASS)")
        logger.info(f"  Average    : {report['average']*100:.1f}%")
        logger.info("=" * 60)

        em_ok   = report['em']['accuracy']   >= 0.85
        exec_ok = report['exec']['accuracy'] >= 0.90
        avg_ok  = report['average']          >= 0.87

        if em_ok and exec_ok and avg_ok:
            logger.info("✅ 모든 목표 달성 (EM≥85%, Exec≥90%, Avg≥87%)")
        else:
            if not em_ok:
                logger.warning(f"⚠️  EM 미달: {report['em']['accuracy']*100:.1f}% < 85%")
            if not exec_ok:
                logger.warning(f"⚠️  Exec 미달: {report['exec']['accuracy']*100:.1f}% < 90%")
            if not avg_ok:
                logger.warning(f"⚠️  Average 미달: {report['average']*100:.1f}% < 87%")

        return report

    def save_report(self, report: dict, output_file: str = "evaluation_report.json") -> None:
        output_path = Path(output_file)
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2, ensure_ascii=False)
        logger.info(f"결과 저장: {output_path}")


def main():
    parser = argparse.ArgumentParser(description="Spider EM/Exec 평가 (Step 5: SQL 생성 정확도)")
    parser.add_argument("--test-cases", default="test_cases.json")
    parser.add_argument("--output",     default="evaluation_report.json")
    parser.add_argument("--limit",      type=int)
    parser.add_argument("--redash-url", default=None)
    args = parser.parse_args()

    runner = EvaluationRunner(redash_base_url=args.redash_url)
    report = runner.run(args.test_cases, args.limit)
    runner.save_report(report, args.output)

    ok = (report['em']['accuracy'] >= 0.85 and
          report['exec']['accuracy'] >= 0.90 and
          report['average'] >= 0.87)
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()

"""
Spider EM/Exec 평가 실행 스크립트

사용법:
  python run_evaluation.py [--test-cases FILE] [--output OUTPUT] [--limit N]

옵션:
  --test-cases FILE: 테스트 케이스 JSON 파일 (기본: test_cases.json)
  --output OUTPUT:   결과 JSON 파일 (기본: evaluation_report.json)
  --limit N:         평가할 케이스 수 제한 (기본: 전체)
"""

import json
import os
import sys
import logging
import argparse
from pathlib import Path
from typing import Optional

# Vanna 및 평가 엔진 import
try:
    from src.pipeline.spider_evaluation import SpiderEvaluator
except ImportError:
    print("❌ Error: spider_evaluation 모듈을 찾을 수 없습니다.")
    print("   실행 위치: services/vanna-api 디렉토리")
    sys.exit(1)

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)8s] %(name)s — %(message)s'
)
logger = logging.getLogger(__name__)


class EvaluationRunner:
    """Spider 평가 실행기"""

    def __init__(
        self,
        vanna_api_url: str = "http://localhost:8000",
        redash_api_key: Optional[str] = None,
        redash_base_url: str = "http://localhost:5000"
    ):
        """
        초기화

        Args:
            vanna_api_url: Vanna API URL
            redash_api_key: Redash API 키 (.env에서 로드)
            redash_base_url: Redash 베이스 URL
        """
        if not redash_api_key:
            redash_api_key = os.getenv("REDASH_API_KEY", "")
            if not redash_api_key:
                logger.warning("⚠️  REDASH_API_KEY가 설정되지 않았습니다.")

        self.vanna_api_url = vanna_api_url
        self.redash_api_key = redash_api_key
        self.redash_base_url = redash_base_url
        self.evaluator = SpiderEvaluator(vanna_api_url, redash_api_key)

        # Mock Vanna 클라이언트 (실제 구현에서는 실제 Vanna 클라이언트 사용)
        self.vanna_client = self._init_vanna_client()

    def _init_vanna_client(self):
        """Vanna 클라이언트 초기화"""
        try:
            from vanna.vanna import Vanna
            # 실제 프로덕션 환경에서는 DB 연결 설정 필요
            vanna = Vanna(api_key=os.getenv("VANNA_API_KEY", ""))
            logger.info("✅ Vanna 클라이언트 초기화 완료")
            return vanna
        except ImportError:
            logger.warning("⚠️  Vanna 라이브러리를 찾을 수 없습니다.")
            # Mock 클라이언트 반환
            class MockVanna:
                def generate_sql(self, question: str) -> str:
                    return ""
            return MockVanna()

    def load_test_cases(self, test_cases_file: str, limit: Optional[int] = None) -> list:
        """테스트 케이스 로드"""
        file_path = Path(test_cases_file)
        if not file_path.exists():
            logger.error(f"❌ 테스트 케이스 파일을 찾을 수 없습니다: {file_path}")
            sys.exit(1)

        with open(file_path, encoding="utf-8") as f:
            test_cases = json.load(f)

        if limit:
            test_cases = test_cases[:limit]

        logger.info(f"✅ {len(test_cases)}개 테스트 케이스 로드 완료")
        return test_cases

    def run(self, test_cases_file: str = "test_cases.json", limit: Optional[int] = None) -> dict:
        """평가 실행"""
        logger.info("=" * 70)
        logger.info("🔍 Spider EM/Exec 평가 시작")
        logger.info("=" * 70)

        # 1. 테스트 케이스 로드
        test_cases = self.load_test_cases(test_cases_file, limit)

        # 2. 평가 실행
        logger.info(f"📊 총 {len(test_cases)}개 케이스 평가 진행 중...")
        results = self.evaluator.evaluate_batch(test_cases, self.vanna_client)

        # 3. 리포트 생성
        report = self.evaluator.generate_report(results)

        # 4. 결과 출력
        logger.info("=" * 70)
        logger.info("📈 평가 결과 요약")
        logger.info("=" * 70)
        logger.info(f"  총 케이스: {report['total_cases']}")
        logger.info(f"  EM (Exact Match):")
        logger.info(f"    - PASS: {report['em']['passed']}/{report['total_cases']}")
        logger.info(f"    - Accuracy: {report['em']['accuracy']*100:.1f}%")
        logger.info(f"  Exec (Execution Accuracy):")
        logger.info(f"    - PASS: {report['exec']['passed']}/{report['total_cases']}")
        logger.info(f"    - Accuracy: {report['exec']['accuracy']*100:.1f}%")
        logger.info(f"  Average: {report['average']*100:.1f}%")
        logger.info("=" * 70)

        # 5. 목표 달성 여부
        em_goal = report['em']['accuracy'] >= 0.85
        exec_goal = report['exec']['accuracy'] >= 0.90
        avg_goal = report['average'] >= 0.87

        if em_goal and exec_goal and avg_goal:
            logger.info("✅ 모든 목표 달성!")
        else:
            if not em_goal:
                logger.warning(f"⚠️  EM 목표 미달: {report['em']['accuracy']*100:.1f}% < 85%")
            if not exec_goal:
                logger.warning(f"⚠️  Exec 목표 미달: {report['exec']['accuracy']*100:.1f}% < 90%")
            if not avg_goal:
                logger.warning(f"⚠️  Average 목표 미달: {report['average']*100:.1f}% < 87%")

        return report

    def save_report(self, report: dict, output_file: str = "evaluation_report.json"):
        """결과 저장"""
        output_path = Path(output_file)
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2, ensure_ascii=False)
        logger.info(f"✅ 결과 저장: {output_path}")


def main():
    """메인 함수"""
    parser = argparse.ArgumentParser(description="Spider EM/Exec 평가 실행")
    parser.add_argument(
        "--test-cases",
        default="test_cases.json",
        help="테스트 케이스 JSON 파일 (기본: test_cases.json)"
    )
    parser.add_argument(
        "--output",
        default="evaluation_report.json",
        help="결과 JSON 파일 (기본: evaluation_report.json)"
    )
    parser.add_argument(
        "--limit",
        type=int,
        help="평가할 케이스 수 제한"
    )
    parser.add_argument(
        "--vanna-url",
        default="http://localhost:8000",
        help="Vanna API URL (기본: http://localhost:8000)"
    )
    parser.add_argument(
        "--redash-url",
        default="http://localhost:5000",
        help="Redash 베이스 URL (기본: http://localhost:5000)"
    )

    args = parser.parse_args()

    # 평가 실행
    runner = EvaluationRunner(
        vanna_api_url=args.vanna_url,
        redash_base_url=args.redash_url
    )
    report = runner.run(args.test_cases, args.limit)
    runner.save_report(report, args.output)

    # 종료 코드
    if (report['em']['accuracy'] >= 0.85 and
        report['exec']['accuracy'] >= 0.90 and
        report['average'] >= 0.87):
        sys.exit(0)  # 성공
    else:
        sys.exit(1)  # 목표 미달


if __name__ == "__main__":
    main()

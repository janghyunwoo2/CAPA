"""
Step 5: SQLGenerator — Vanna + Claude 기반 SQL 생성
설계 문서 §2.3.2 기준
실패 시 파이프라인 중단 + PipelineError 반환
"""

import logging
from datetime import date, timedelta
from typing import Any, Optional
from ..models.domain import RAGContext

logger = logging.getLogger(__name__)


class SQLGenerationError(Exception):
    """SQL 생성 실패 예외"""
    pass


class SQLGenerator:
    """Step 5 — Vanna 기반 SQL 생성"""

    def __init__(self, vanna_instance: Any) -> None:
        """
        Args:
            vanna_instance: 초기화된 VannaAthena 인스턴스
        """
        self._vanna = vanna_instance

    def generate(self, question: str, rag_context: Optional[RAGContext] = None) -> str:
        """자연어 질문을 SQL로 변환하여 반환.
        실패 시 SQLGenerationError 발생 → 파이프라인 중단.
        """
        try:
            today = date.today()
            yesterday = today - timedelta(days=1)
            last_month_start = (today.replace(day=1) - timedelta(days=1)).replace(day=1)
            last_month_end = today.replace(day=1) - timedelta(days=1)
            date_context = (
                f"[날짜 컨텍스트: 오늘={today}, 어제={yesterday}, "
                f"이번달={today.strftime('%Y-%m')}-01~{today}, "
                f"지난달={last_month_start}~{last_month_end}] "
            )
            sql = self._vanna.generate_sql(question=f"{date_context}{question}")
            if not sql or not sql.strip():
                raise SQLGenerationError("빈 SQL이 생성되었습니다")

            logger.info(f"SQL 생성 완료: {sql[:100]}...")
            return sql.strip()

        except SQLGenerationError:
            raise
        except Exception as e:
            logger.error(f"SQL 생성 실패: {e}")
            raise SQLGenerationError(f"SQL 생성 중 오류가 발생했습니다: {str(e)}")

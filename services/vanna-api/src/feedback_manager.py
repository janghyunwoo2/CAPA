"""
FeedbackManager — 피드백 처리 (Phase 1 + Phase 2)
설계 문서 §4.1.3 기준

Phase 1 (PHASE2_FEEDBACK_ENABLED=false, 기본값):
  긍정 피드백 → vanna.train() 즉시 호출 (하위 호환)

Phase 2 (PHASE2_FEEDBACK_ENABLED=true):
  긍정 피드백 → DynamoDB pending_feedbacks에만 저장 (즉시 학습 제거)
  실제 학습은 Airflow DAG(FR-18) 배치 검증 후 수행
"""

import logging
import os
from typing import Any, Optional

from .history_recorder import HistoryRecorder
from .models.domain import FeedbackType

logger = logging.getLogger(__name__)

PHASE2_FEEDBACK_ENABLED = os.getenv("PHASE2_FEEDBACK_ENABLED", "false").lower() == "true"


class FeedbackManager:
    """피드백 수집 및 처리 (FR-21, §2.5.1)"""

    def __init__(
        self,
        vanna_instance: Any,
        history_recorder: HistoryRecorder,
        feedback_store: Optional[Any] = None,
    ) -> None:
        self._vanna = vanna_instance
        self._recorder = history_recorder
        self._feedback_store = feedback_store

    def record_positive(
        self, history_id: str, slack_user_id: str
    ) -> tuple[bool, str]:
        """긍정 피드백 처리.

        Phase 2 (PHASE2_FEEDBACK_ENABLED=true):
          DynamoDB pending_feedbacks에 저장만 수행, vanna.train() 호출 안 함.
        Phase 1 (PHASE2_FEEDBACK_ENABLED=false, 기본값):
          vanna.train() 즉시 호출 (하위 호환).

        Returns:
            (trained: bool, message: str)
        """
        record = self._recorder.get_record(history_id)
        if not record:
            logger.warning(f"이력 레코드를 찾을 수 없음: {history_id}")
            return False, "이력 레코드를 찾을 수 없습니다"

        if PHASE2_FEEDBACK_ENABLED:
            # Phase 2: DynamoDB에 pending으로 저장만 (즉시 학습 제거)
            if record.refined_question and record.generated_sql and self._feedback_store:
                try:
                    self._feedback_store.save_pending(
                        history_id=history_id,
                        question=record.refined_question,
                        sql=record.generated_sql,
                    )
                except Exception as e:
                    logger.error(f"피드백 pending 저장 실패 (무시): {e}")
            self._recorder.update_feedback(
                history_id=history_id,
                feedback=FeedbackType.POSITIVE.value,
                trained=False,
            )
            logger.info(f"Phase 2 긍정 피드백 pending 저장 완료: {history_id}")
            return False, "피드백이 기록되었습니다. 주간 학습 배치에서 검증 후 반영됩니다."

        # Phase 1: 즉시 학습 (하위 호환)
        trained = False
        if record.refined_question and record.generated_sql:
            trained = self._train_vanna(
                question=record.refined_question,
                sql=record.generated_sql,
            )
        self._recorder.update_feedback(
            history_id=history_id,
            feedback=FeedbackType.POSITIVE.value,
            trained=trained,
        )
        msg = "피드백이 기록되었으며 학습 데이터에 추가되었습니다." if trained else "피드백이 기록되었습니다."
        logger.info(f"Phase 1 긍정 피드백 처리 완료: {history_id}, trained={trained}")
        return trained, msg

    def record_negative(
        self, history_id: str, slack_user_id: str, comment: Optional[str] = None
    ) -> str:
        """부정 피드백 처리 — History 업데이트만 (학습 제외)."""
        self._recorder.update_feedback(
            history_id=history_id,
            feedback=FeedbackType.NEGATIVE.value,
            trained=False,
        )
        logger.info(f"부정 피드백 기록 완료: {history_id}")
        return "피드백이 기록되었습니다. 더 나은 서비스를 위해 개선하겠습니다."

    def _train_vanna(self, question: str, sql: str) -> bool:
        """vanna.train()을 통해 ChromaDB sql-qa 컬렉션에 학습 데이터 추가"""
        try:
            self._vanna.train(question=question, sql=sql)
            logger.info(f"ChromaDB 학습 추가 완료: Q='{question[:50]}'")
            return True
        except Exception as e:
            logger.error(f"vanna.train() 실패: {e}")
            return False

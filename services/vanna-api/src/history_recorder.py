"""
Step 11: HistoryRecorder — 질문-SQL-결과 이력 저장 (JSON Lines, Phase 1)
설계 문서 §4.3 기준 (FR-10)
저장 실패 시 로그만 기록 (사용자 영향 없음)
"""

import hashlib
import json
import logging
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional

from .models.domain import PipelineContext
from .models.feedback import QueryHistoryRecord

logger = logging.getLogger(__name__)

HISTORY_FILE = Path("/data/query_history.jsonl")
MAX_HISTORY_RECORDS = 10_000


def _hash_user_id(user_id: str) -> str:
    """PII 보호를 위해 Slack user_id를 SHA-256 해싱 처리"""
    if not user_id:
        return ""
    return hashlib.sha256(user_id.encode()).hexdigest()[:16]


class HistoryRecorder:
    """Step 11 — 성공한 쿼리 이력을 JSON Lines 파일에 저장 (FR-10)"""

    def __init__(self, history_file: Optional[Path] = None) -> None:
        self._file = history_file or HISTORY_FILE
        self._ensure_directory()

    def _ensure_directory(self) -> None:
        try:
            self._file.parent.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            logger.warning(f"이력 저장 디렉토리 생성 실패: {e}")

    def record(self, ctx: PipelineContext) -> str:
        """파이프라인 컨텍스트에서 이력 레코드를 생성하여 저장.
        실패 시 로그만 기록하고 history_id 반환.
        """
        history_id = str(uuid.uuid4())
        record = QueryHistoryRecord(
            history_id=history_id,
            timestamp=datetime.utcnow(),
            slack_user_id=_hash_user_id(ctx.slack_user_id),
            slack_channel_id=ctx.slack_channel_id,
            original_question=ctx.original_question,
            refined_question=ctx.refined_question,
            intent=ctx.intent.value if ctx.intent else "unknown",
            keywords=ctx.keywords,
            generated_sql=ctx.validation_result.normalized_sql if ctx.validation_result else ctx.generated_sql,
            sql_validated=ctx.validation_result.is_valid if ctx.validation_result else False,
            row_count=ctx.query_results.row_count if ctx.query_results else None,
            redash_query_id=ctx.redash_query_id,
            redash_url=ctx.redash_url,
        )

        try:
            self._append_record(record)
            logger.info(f"이력 저장 완료: {history_id}")
        except Exception as e:
            logger.error(f"이력 저장 실패 (사용자 영향 없음): {e}")

        return history_id

    def _append_record(self, record: QueryHistoryRecord) -> None:
        with self._file.open("a", encoding="utf-8") as f:
            f.write(record.model_dump_json() + "\n")

    def update_feedback(
        self,
        history_id: str,
        feedback: str,
        trained: bool = False,
    ) -> bool:
        """이력 레코드의 피드백을 업데이트.
        실패 시 False 반환.
        """
        try:
            if not self._file.exists():
                logger.warning("이력 파일이 없습니다")
                return False

            lines = self._file.read_text(encoding="utf-8").splitlines()
            updated = False
            new_lines = []

            for line in lines:
                if not line.strip():
                    continue
                try:
                    data = json.loads(line)
                    if data.get("history_id") == history_id:
                        data["feedback"] = feedback
                        data["feedback_at"] = datetime.utcnow().isoformat()
                        data["trained"] = trained
                        updated = True
                    new_lines.append(json.dumps(data, ensure_ascii=False))
                except json.JSONDecodeError:
                    new_lines.append(line)

            if updated:
                self._file.write_text(
                    "\n".join(new_lines) + "\n", encoding="utf-8"
                )
                logger.info(f"피드백 업데이트 완료: {history_id} → {feedback}")

            return updated

        except Exception as e:
            logger.error(f"피드백 업데이트 실패: {e}")
            return False

    def get_record(self, history_id: str) -> Optional[QueryHistoryRecord]:
        """history_id로 이력 레코드 조회"""
        try:
            if not self._file.exists():
                return None
            for line in self._file.read_text(encoding="utf-8").splitlines():
                if not line.strip():
                    continue
                try:
                    data = json.loads(line)
                    if data.get("history_id") == history_id:
                        return QueryHistoryRecord(**data)
                except (json.JSONDecodeError, Exception):
                    continue
            return None
        except Exception as e:
            logger.error(f"이력 조회 실패: {e}")
            return None

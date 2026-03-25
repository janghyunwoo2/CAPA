"""
Step 5: SQLGenerator — Vanna + Claude 기반 SQL 생성 (FR-PE-01, 02, 03)
설계 문서 §2.3.2 + prompt-engineering-enhancement.design.md 기준
실패 시 파이프라인 중단 + PipelineError 반환
"""

import logging
import os
import re
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FuturesTimeoutError
from datetime import date, timedelta
from typing import Any, Optional

from ..models.domain import RAGContext
from ..prompt_loader import load_prompt

logger = logging.getLogger(__name__)

LLM_TIMEOUT_SECONDS = float(os.getenv("LLM_TIMEOUT_SECONDS", "60"))

# YAML 없을 때 날짜 컨텍스트 fallback
_FALLBACK_DATE_CONTEXT = (
    "[날짜 컨텍스트] 파티션 형식: year/month/day는 STRING 2자리. "
    "DATE() 함수 금지, 문자열 등호(year='YYYY', month='MM', day='DD')만 사용. "
    "[경고: 예시 SQL의 날짜 값을 그대로 복사하지 말 것]"
)


class SQLGenerationError(Exception):
    """SQL 생성 실패 예외"""
    pass


def _strip_thinking_block(sql: str) -> str:
    """<thinking>...</thinking> 블록 제거 후 SQL만 반환 (FR-PE-02)"""
    cleaned = re.sub(r"<thinking>.*?</thinking>", "", sql, flags=re.DOTALL).strip()
    return cleaned if cleaned else sql


class SQLGenerator:
    """Step 5 — Vanna 기반 SQL 생성"""

    def __init__(
        self,
        vanna_instance: Any,
        anthropic_client: Optional[Any] = None,
        model: str = "claude-haiku-4-5-20251001",
    ) -> None:
        self._vanna = vanna_instance
        self._anthropic = anthropic_client
        self._model = model

    def generate(
        self,
        question: str,
        rag_context: Optional[RAGContext] = None,
        conversation_history: Optional[list] = None,
        error_feedback: Optional[str] = None,
    ) -> str:
        """자연어 질문을 SQL로 변환하여 반환.
        실패 시 SQLGenerationError 발생 → 파이프라인 중단.
        LLM_TIMEOUT_SECONDS 환경변수로 타임아웃 제어 (기본 60초).
        """
        try:
            # 날짜 변수 계산
            today = date.today()
            yesterday = today - timedelta(days=1)
            last_month_start = (today.replace(day=1) - timedelta(days=1)).replace(day=1)
            week_end = yesterday
            week_start = today - timedelta(days=7)
            week_days = ", ".join(
                f"'{(week_start + timedelta(days=i)).strftime('%d')}'"
                for i in range(7)
            )

            # YAML 로드 (핫 리로드 지원, 없으면 빈 딕셔너리)
            prompts = load_prompt(
                "sql_generator",
                today=today,
                year=today.strftime("%Y"),
                month=today.strftime("%m"),
                day=today.strftime("%d"),
                yesterday=yesterday,
                y_year=yesterday.strftime("%Y"),
                y_month=yesterday.strftime("%m"),
                y_day=yesterday.strftime("%d"),
                this_month=today.strftime("%Y-%m"),
                last_month=last_month_start.strftime("%Y-%m"),
                lm_year=last_month_start.strftime("%Y"),
                lm_month=last_month_start.strftime("%m"),
                week_start=week_start.strftime("%Y-%m-%d"),
                week_end=week_end.strftime("%Y-%m-%d"),
                week_days=week_days,
            )

            schema = prompts.get("schema", "")
            date_rules = prompts.get("date_rules", _FALLBACK_DATE_CONTEXT)
            cot_template = prompts.get("cot_template", "")

            # [FR-PE-01] conversation_history 주입 (버그 수정)
            history_block = ""
            if conversation_history:
                prev_sqls = [t.generated_sql for t in conversation_history if t.generated_sql]
                if prev_sqls:
                    sql_list = "\n".join(f"  {i+1}. {sql}" for i, sql in enumerate(prev_sqls))
                    history_block = f"이전 대화에서 생성된 SQL:\n{sql_list}\n"

            # [FR-12] Phase 2 RAG 컨텍스트 주입 (rag_context 제공 시)
            rag_block = ""
            if rag_context:
                sections: list[str] = []
                if rag_context.ddl_context:
                    sections.append("<ddl>\n" + "\n".join(rag_context.ddl_context) + "\n</ddl>")
                if rag_context.documentation_context:
                    sections.append("<documentation>\n" + "\n".join(rag_context.documentation_context) + "\n</documentation>")
                if rag_context.sql_examples:
                    sections.append("<sql_examples>\n" + "\n".join(rag_context.sql_examples) + "\n</sql_examples>")
                if sections:
                    rag_block = "<rag_context>\n" + "\n".join(sections) + "\n</rag_context>\n"
                    logger.info(f"RAG 컨텍스트 주입: DDL {len(rag_context.ddl_context)}건, Docs {len(rag_context.documentation_context)}건, SQL {len(rag_context.sql_examples)}건")

            # [FR-PE-02, FR-PE-03] CoT + 구조화 날짜 규칙 + RAG 컨텍스트 + history 주입
            negative_rules = prompts.get("negative_rules", "")
            table_selection_rules = prompts.get("table_selection_rules", "")

            # error_feedback 블록 (Self-Correction용)
            error_block = error_feedback or ""

            if self._anthropic:
                # [A-2] anthropic_client 주입 시: temperature=0 + system/user 분리
                system_content = "\n".join(filter(None, [
                    schema, date_rules, negative_rules, table_selection_rules
                ]))
                user_content = (
                    f"{rag_block}{history_block}{error_block}"
                    f"{cot_template}\n질문: {question}"
                )
                response = self._anthropic.messages.create(
                    model=self._model,
                    max_tokens=1024,
                    temperature=0,
                    system=system_content,
                    messages=[{"role": "user", "content": user_content}],
                )
                sql = response.content[0].text
            else:
                # [하위 호환] anthropic_client 없는 경우 기존 Vanna 경로
                prompt = (
                    f"{schema}\n{date_rules}\n"
                    f"{rag_block}{history_block}{error_block}"
                    f"{cot_template}\n질문: {question}"
                )
                with ThreadPoolExecutor(max_workers=1) as executor:
                    if rag_context:
                        future = executor.submit(
                            self._vanna.submit_prompt,
                            [{"role": "user", "content": prompt}],
                        )
                    else:
                        future = executor.submit(self._vanna.generate_sql, question=prompt)
                    try:
                        sql = future.result(timeout=LLM_TIMEOUT_SECONDS)
                    except FuturesTimeoutError:
                        logger.error(f"LLM 응답 타임아웃 ({LLM_TIMEOUT_SECONDS}초 초과)")
                        raise SQLGenerationError(
                            f"LLM 응답 타임아웃 ({LLM_TIMEOUT_SECONDS}초 초과)"
                        )

            if not sql or not sql.strip():
                raise SQLGenerationError("빈 SQL이 생성되었습니다")

            # CoT <thinking> 블록 제거
            sql = _strip_thinking_block(sql.strip())

            logger.info(f"SQL 생성 완료: {sql[:100]}...")
            return sql

        except SQLGenerationError:
            raise
        except Exception as e:
            logger.error(f"SQL 생성 실패: {e}")
            raise SQLGenerationError(f"SQL 생성 중 오류가 발생했습니다: {str(e)}")

    def generate_with_error_feedback(
        self,
        question: str,
        failed_sql: str,
        error_message: str,
        rag_context: Optional[RAGContext] = None,
        conversation_history: Optional[list] = None,
    ) -> str:
        """Self-Correction용: 실패한 SQL과 에러 메시지를 LLM에 재주입하여 재생성.

        Args:
            question: 원래 사용자 질문
            failed_sql: 검증 실패한 SQL
            error_message: 검증 에러 메시지
            rag_context: RAG 컨텍스트 (1차와 동일)
            conversation_history: 대화 이력

        Returns:
            재생성된 SQL 문자열
        """
        error_block = (
            "<error_feedback>\n"
            f"이전에 생성된 SQL: {failed_sql}\n"
            f"오류 내용: {error_message}\n"
            "위 오류를 반드시 수정하여 올바른 SQL을 다시 작성하세요.\n"
            "</error_feedback>\n"
        )
        logger.info(f"Self-Correction 재생성: error={error_message[:80]}")
        return self.generate(
            question=question,
            rag_context=rag_context,
            conversation_history=conversation_history,
            error_feedback=error_block,
        )

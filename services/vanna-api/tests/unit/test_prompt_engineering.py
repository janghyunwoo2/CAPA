"""
Prompt Engineering Enhancement 단위 테스트 (FR-PE)

TC 목록:
  TC-PE-01: PromptLoader — YAML 정상 로드
  TC-PE-02: PromptLoader — YAML 없을 때 빈 딕셔너리 반환 (fallback)
  TC-PE-03: PromptLoader — Jinja2 날짜 변수 치환
  TC-PE-04: PromptLoader — mtime 변경 시 캐시 갱신 (핫 리로드)
  TC-PE-05: SQLGenerator — conversation_history 프롬프트 주입 (버그 수정)
  TC-PE-06: SQLGenerator — history=None 시 <history> 블록 미포함
  TC-PE-07: SQLGenerator — CoT cot_template 프롬프트 주입
  TC-PE-08: SQLGenerator — date_rules 구조화 주입
  TC-PE-09: _strip_thinking_block — CoT 블록 제거 후 SQL만 반환
  TC-PE-10: _strip_thinking_block — <thinking> 없으면 원본 그대로
  TC-PE-11: IntentClassifier — YAML 프롬프트 사용
  TC-PE-12: IntentClassifier — YAML 없을 때 코드 내 기본값 fallback
  TC-PE-13: QuestionRefiner — YAML 프롬프트 사용
  TC-PE-14: AIAnalyzer — YAML instructions 사용
"""

import json
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# ─────────────────────────────────────────────────
# 공통 헬퍼
# ─────────────────────────────────────────────────

def _make_anthropic_response(text: str) -> MagicMock:
    """Anthropic API 응답 Mock"""
    response = MagicMock()
    cb = MagicMock()
    cb.text = text
    response.content = [cb]
    return response


def _make_query_results(rows: list[dict] | None = None) -> MagicMock:
    """QueryResults Mock"""
    qr = MagicMock()
    qr.rows = rows or [{"campaign": "A", "ctr": 0.09}]
    qr.row_count = len(qr.rows)
    return qr


# ─────────────────────────────────────────────────
# TC-PE-01 ~ TC-PE-04: PromptLoader
# ─────────────────────────────────────────────────

class TestPromptLoader:
    """PromptLoader YAML 로드 / fallback / 핫 리로드 검증"""

    def test_load_yaml_returns_dict(self, tmp_path: Path):
        """TC-PE-01: YAML 파일 정상 로드 → 딕셔너리 반환"""
        yaml_file = tmp_path / "sql_generator.yaml"
        yaml_file.write_text("system: '당신은 SQL 전문가입니다.'\nschema: '<schema>ad_logs</schema>'\n", encoding="utf-8")

        from src.prompt_loader import PromptLoader
        loader = PromptLoader(prompts_dir=tmp_path)
        result = loader.load("sql_generator")

        assert isinstance(result, dict)
        assert "system" in result
        assert "schema" in result

    def test_load_missing_yaml_returns_empty_dict(self, tmp_path: Path):
        """TC-PE-02: YAML 없을 때 빈 딕셔너리 반환 (예외 없음)"""
        from src.prompt_loader import PromptLoader
        loader = PromptLoader(prompts_dir=tmp_path)
        result = loader.load("nonexistent")

        assert result == {}

    def test_load_renders_jinja2_variables(self, tmp_path: Path):
        """TC-PE-03: Jinja2 {{ today }} 변수가 실제 날짜로 치환"""
        yaml_file = tmp_path / "sql_generator.yaml"
        yaml_file.write_text("date_rules: '오늘={{ today }}'\n", encoding="utf-8")

        from src.prompt_loader import PromptLoader
        loader = PromptLoader(prompts_dir=tmp_path)
        result = loader.load("sql_generator", today="2026-03-23")

        assert "2026-03-23" in result["date_rules"]

    def test_load_reloads_on_mtime_change(self, tmp_path: Path):
        """TC-PE-04: 파일 내용 수정 후 재로드 시 새 내용 반환 (핫 리로드)"""
        yaml_file = tmp_path / "sql_generator.yaml"
        yaml_file.write_text("system: 'version 1'\n", encoding="utf-8")

        from src.prompt_loader import PromptLoader
        loader = PromptLoader(prompts_dir=tmp_path)
        result_v1 = loader.load("sql_generator")
        assert result_v1["system"] == "version 1"

        # 파일 수정 (mtime 변경 보장)
        time.sleep(0.05)
        yaml_file.write_text("system: 'version 2'\n", encoding="utf-8")

        result_v2 = loader.load("sql_generator")
        assert result_v2["system"] == "version 2"


# ─────────────────────────────────────────────────
# TC-PE-05 ~ TC-PE-10: SQLGenerator
# ─────────────────────────────────────────────────

class TestSQLGeneratorPromptInjection:
    """SQLGenerator 프롬프트 주입 로직 검증"""

    def _make_history_turn(self, sql: str) -> MagicMock:
        """ConversationTurn Mock (generated_sql 있음)"""
        turn = MagicMock()
        turn.generated_sql = sql
        return turn

    @patch("src.pipeline.sql_generator.load_prompt")
    def test_conversation_history_injected_in_prompt(self, mock_load, mock_vanna_instance):
        """TC-PE-05: conversation_history가 있을 때 <history> 블록이 프롬프트에 포함 (FR-PE-01 버그 수정)"""
        mock_load.return_value = {"schema": "", "date_rules": "", "cot_template": ""}
        mock_vanna_instance.generate_sql.return_value = "SELECT 1"

        from src.pipeline.sql_generator import SQLGenerator
        generator = SQLGenerator(vanna_instance=mock_vanna_instance)

        history = [self._make_history_turn("SELECT campaign FROM ad_logs WHERE year='2026'")]
        generator.generate("그 중 비용이 적은 것은?", conversation_history=history)

        captured_prompt = mock_vanna_instance.generate_sql.call_args[1]["question"]
        assert "<history>" in captured_prompt
        assert "SELECT campaign FROM ad_logs" in captured_prompt

    @patch("src.pipeline.sql_generator.load_prompt")
    def test_no_history_no_history_block(self, mock_load, mock_vanna_instance):
        """TC-PE-06: history=None 시 <history> 블록 미포함"""
        mock_load.return_value = {"schema": "", "date_rules": "", "cot_template": ""}
        mock_vanna_instance.generate_sql.return_value = "SELECT 1"

        from src.pipeline.sql_generator import SQLGenerator
        generator = SQLGenerator(vanna_instance=mock_vanna_instance)
        generator.generate("지난달 CTR 알려줘", conversation_history=None)

        captured_prompt = mock_vanna_instance.generate_sql.call_args[1]["question"]
        assert "<history>" not in captured_prompt

    @patch("src.pipeline.sql_generator.load_prompt")
    def test_cot_template_injected_in_prompt(self, mock_load, mock_vanna_instance):
        """TC-PE-07: YAML cot_template이 Vanna 프롬프트에 포함 (FR-PE-02)"""
        mock_load.return_value = {
            "schema": "",
            "date_rules": "",
            "cot_template": "<thinking>\nStep 1: 테이블 선택\n</thinking>",
        }
        mock_vanna_instance.generate_sql.return_value = "SELECT 1"

        from src.pipeline.sql_generator import SQLGenerator
        generator = SQLGenerator(vanna_instance=mock_vanna_instance)
        generator.generate("테스트 질문")

        captured_prompt = mock_vanna_instance.generate_sql.call_args[1]["question"]
        assert "<thinking>" in captured_prompt

    @patch("src.pipeline.sql_generator.load_prompt")
    def test_date_rules_injected_in_prompt(self, mock_load, mock_vanna_instance):
        """TC-PE-08: YAML date_rules가 Vanna 프롬프트에 포함 (FR-PE-03)"""
        mock_load.return_value = {
            "schema": "",
            "date_rules": "<date_rules>금지: DATE()</date_rules>",
            "cot_template": "",
        }
        mock_vanna_instance.generate_sql.return_value = "SELECT 1"

        from src.pipeline.sql_generator import SQLGenerator
        generator = SQLGenerator(vanna_instance=mock_vanna_instance)
        generator.generate("지난달 실적")

        captured_prompt = mock_vanna_instance.generate_sql.call_args[1]["question"]
        assert "<date_rules>" in captured_prompt
        assert "DATE()" in captured_prompt


class TestStripThinkingBlock:
    """_strip_thinking_block 유틸 함수 검증"""

    def test_removes_thinking_block(self):
        """TC-PE-09: <thinking>...</thinking> 제거 후 SQL만 반환"""
        from src.pipeline.sql_generator import _strip_thinking_block
        raw = "<thinking>\nStep 1: 테이블 선택\nStep 2: 날짜 변환\n</thinking>\nSELECT * FROM ad_logs"
        result = _strip_thinking_block(raw)
        assert result == "SELECT * FROM ad_logs"
        assert "<thinking>" not in result

    def test_no_thinking_block_returns_original(self):
        """TC-PE-10: <thinking> 없으면 원본 SQL 그대로 반환"""
        from src.pipeline.sql_generator import _strip_thinking_block
        sql = "SELECT * FROM ad_logs WHERE year='2026'"
        result = _strip_thinking_block(sql)
        assert result == sql


# ─────────────────────────────────────────────────
# TC-PE-11 ~ TC-PE-12: IntentClassifier
# ─────────────────────────────────────────────────

class TestIntentClassifierYaml:
    """IntentClassifier YAML 프롬프트 로드 검증"""

    @patch("src.pipeline.intent_classifier.load_prompt")
    @patch("src.pipeline.intent_classifier.anthropic.Anthropic")
    def test_uses_yaml_system_prompt(self, mock_anthropic_cls, mock_load, fake_api_key):
        """TC-PE-11: YAML 있을 때 YAML system 프롬프트로 API 호출"""
        mock_load.return_value = {"system": "YAML 시스템 프롬프트"}
        mock_client = mock_anthropic_cls.return_value
        mock_client.messages.create.return_value = _make_anthropic_response("DATA_QUERY")

        from src.pipeline.intent_classifier import IntentClassifier
        classifier = IntentClassifier(api_key=fake_api_key)
        classifier.classify("지난달 CTR 알려줘")

        call_kwargs = mock_client.messages.create.call_args[1]
        assert call_kwargs["system"] == "YAML 시스템 프롬프트"

    @patch("src.pipeline.intent_classifier.load_prompt")
    @patch("src.pipeline.intent_classifier.anthropic.Anthropic")
    def test_falls_back_to_code_prompt_when_yaml_empty(self, mock_anthropic_cls, mock_load, fake_api_key):
        """TC-PE-12: YAML 없을 때(빈 딕셔너리) 코드 내 _SYSTEM_PROMPT 사용"""
        mock_load.return_value = {}
        mock_client = mock_anthropic_cls.return_value
        mock_client.messages.create.return_value = _make_anthropic_response("DATA_QUERY")

        from src.pipeline.intent_classifier import IntentClassifier
        classifier = IntentClassifier(api_key=fake_api_key)
        classifier.classify("테스트")

        call_kwargs = mock_client.messages.create.call_args[1]
        # 코드 내 기본값에 DATA_QUERY 분류 기준이 포함되어 있어야 함
        assert "DATA_QUERY" in call_kwargs["system"]


# ─────────────────────────────────────────────────
# TC-PE-13: QuestionRefiner
# ─────────────────────────────────────────────────

class TestQuestionRefinerYaml:
    """QuestionRefiner YAML 프롬프트 로드 검증"""

    @patch("src.pipeline.question_refiner.load_prompt")
    @patch("src.pipeline.question_refiner.anthropic.Anthropic")
    def test_uses_yaml_system_prompt(self, mock_anthropic_cls, mock_load, fake_api_key):
        """TC-PE-13: YAML system 프롬프트로 질문 정제 API 호출"""
        mock_load.return_value = {"system": "YAML 정제기 프롬프트"}
        mock_client = mock_anthropic_cls.return_value
        mock_client.messages.create.return_value = _make_anthropic_response("지난달 CTR 상위 캠페인 5개")

        from src.pipeline.question_refiner import QuestionRefiner
        refiner = QuestionRefiner(api_key=fake_api_key)
        refiner.refine("안녕하세요! 지난달 CTR 알려주세요")

        call_kwargs = mock_client.messages.create.call_args[1]
        assert call_kwargs["system"] == "YAML 정제기 프롬프트"


# ─────────────────────────────────────────────────
# TC-PE-14: AIAnalyzer
# ─────────────────────────────────────────────────

class TestAIAnalyzerYaml:
    """AIAnalyzer YAML instructions 로드 검증"""

    @patch("src.pipeline.ai_analyzer.load_prompt")
    @patch("src.pipeline.ai_analyzer.anthropic.Anthropic")
    def test_uses_yaml_instructions(self, mock_anthropic_cls, mock_load, fake_api_key):
        """TC-PE-14: YAML instructions(광고 지표 정의 포함)으로 분석 API 호출"""
        mock_load.return_value = {
            "instructions": "<instructions>CTR=clicks/impressions</instructions>"
        }
        mock_client = mock_anthropic_cls.return_value
        mock_client.messages.create.return_value = _make_anthropic_response(
            json.dumps({"answer": "분석 완료", "chart_type": "bar", "insight_points": []})
        )

        from src.pipeline.ai_analyzer import AIAnalyzer
        analyzer = AIAnalyzer(api_key=fake_api_key)
        analyzer.analyze(
            question="지난달 CTR은?",
            sql="SELECT ctr FROM ad_logs WHERE year='2026' AND month='02'",
            query_results=_make_query_results(),
        )

        call_args = mock_client.messages.create.call_args[1]
        content_blocks = call_args["messages"][0]["content"]
        instructions_text = content_blocks[0]["text"]
        assert "CTR=clicks/impressions" in instructions_text

"""
sql-accuracy-tuning 단위 테스트 (TDD Red → Green)

TC 목록:
  TC-SAT-01: SQLGenerator — anthropic_client 주입 시 temperature=0 전달
  TC-SAT-02: SQLGenerator — system/user 메시지 분리 전달
  TC-SAT-03: SQLGenerator — anthropic_client 없을 때 Vanna fallback
  TC-SAT-04: SQLGenerator — generate_with_error_feedback() 에러 블록 포함
  TC-SAT-05: Self-Correction — 1회 성공 시 재시도 없음
  TC-SAT-06: Self-Correction — SQL_PARSE_ERROR 시 재시도
  TC-SAT-07: Self-Correction — SQL_BLOCKED_KEYWORD는 재시도 안 함
  TC-SAT-08: Self-Correction — MAX_CORRECTION_ATTEMPTS 초과 시 중단
  TC-SAT-09: _render_ground_truth() — 어제 날짜 변수 렌더링
  TC-SAT-10: _render_ground_truth() — 오늘/이번달 변수 렌더링
  TC-SAT-11: run_evaluation.py — --limit 기본값 None
  TC-SAT-12: SQLNormalizer.strip_limit() — LIMIT 절 제거
  TC-SAT-13: SQLNormalizer.strip_limit() — LIMIT 없는 SQL 보존
  TC-KWF-01: _filter_keywords() — 화이트리스트에 없는 키워드 제거
  TC-KWF-02: _filter_keywords() — 유효한 컬럼명 보존
  TC-KWF-03: _filter_keywords() — 대소문자 무관 처리
  TC-KWF-04: _filter_keywords() — 빈 입력 처리
  TC-KWF-05: KeywordExtractor.extract() — LLM 출력에 필터 적용
  TC-YAML-01: sql_generator.yaml — negative_rules 섹션 존재 확인
  TC-YAML-02: sql_generator.yaml — table_selection_rules 섹션 존재 확인
  TC-YAML-03: sql_generator.yaml — cot_template 6-Step 확인
  TC-SEED-01: seed_chromadb.py — 존재하지 않는 컬럼 Documentation 존재 확인
  TC-SEED-02: seed_chromadb.py — 컬럼 범주값 통합 Documentation 존재 확인
  TC-SEED-03: seed_chromadb.py — Jinja2 패턴 QA 존재 확인
"""

import argparse
import os
import sys
from datetime import date, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# query_pipeline.py가 vanna를 최상위에서 임포트하므로 먼저 Mock 등록
if "vanna.chromadb" not in sys.modules:
    _mock_vanna_chromadb = MagicMock()
    _mock_vanna_chromadb.ChromaDB_VectorStore = type("ChromaDB_VectorStore", (), {
        "__init__": lambda self, *a, **kw: None
    })
    sys.modules["vanna.chromadb"] = _mock_vanna_chromadb
if "vanna.anthropic" not in sys.modules:
    _mock_vanna_anthropic = MagicMock()
    _mock_vanna_anthropic.Anthropic_Chat = type("Anthropic_Chat", (), {
        "__init__": lambda self, *a, **kw: None
    })
    sys.modules["vanna.anthropic"] = _mock_vanna_anthropic
for _mod in ["vanna", "vanna.base", "vanna.base.base", "vanna.utils"]:
    if _mod not in sys.modules:
        sys.modules[_mod] = MagicMock()

# query_pipeline.py가 모듈 레벨에서 SentenceTransformerEmbeddingFunction(model_name=...)을 호출함.
# 실제 chromadb는 설치되어 있으나 sentence_transformers가 없어 ValueError 발생.
# 실제 모듈의 클래스를 직접 Mock으로 교체하여 임포트 전에 무력화.
import chromadb.utils.embedding_functions as _chroma_ef
_chroma_ef.SentenceTransformerEmbeddingFunction = MagicMock(return_value=MagicMock())

# sqlglot 미설치 환경 대응 (unit_phase2/conftest.py 패턴 적용)
if "sqlglot" not in sys.modules:
    _sqlglot_mock = MagicMock()
    sys.modules["sqlglot"] = _sqlglot_mock
if "sqlglot.exp" not in sys.modules:
    sys.modules["sqlglot.exp"] = MagicMock()
if "sqlglot.errors" not in sys.modules:
    _sqlglot_errors = MagicMock()
    _sqlglot_errors.ParseError = type("ParseError", (Exception,), {})
    sys.modules["sqlglot.errors"] = _sqlglot_errors

from src.models.domain import RAGContext, PipelineContext, ValidationResult
from src.pipeline.sql_generator import SQLGenerator, SQLGenerationError

# evaluation 모듈은 services/vanna-api/evaluation/ 에 위치
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../evaluation"))


# ──────────────────────────────────────────────
# Phase A: SQLGenerator (temperature=0, system/user 분리)
# ──────────────────────────────────────────────

class TestSQLGeneratorWithAnthropicClient:
    """TC-SAT-01 ~ TC-SAT-04: anthropic_client 주입 시 동작 검증"""

    def _make_anthropic_mock(self, sql_text: str = "SELECT 1") -> MagicMock:
        """Anthropic client Mock — messages.create() 반환값 설정"""
        client = MagicMock()
        response = MagicMock()
        response.content = [MagicMock(text=sql_text)]
        client.messages.create.return_value = response
        return client

    def _make_rag_context(self) -> RAGContext:
        return RAGContext(
            ddl_context=["CREATE TABLE ad_combined_log (campaign_id STRING)"],
            documentation_context=["캠페인별 CTR 집계"],
            sql_examples=["SELECT campaign_id FROM ad_combined_log"],
        )

    def test_temperature_zero_passed_to_api(self, mock_vanna_instance):
        """TC-SAT-01: anthropic_client 주입 시 temperature=0 전달"""
        anthropic_client = self._make_anthropic_mock(
            "SELECT campaign_id FROM ad_combined_log_summary"
        )
        generator = SQLGenerator(
            vanna_instance=mock_vanna_instance,
            anthropic_client=anthropic_client,
            model="claude-haiku-4-5-20251001",
        )

        generator.generate(
            question="어제 CTR 알려줘",
            rag_context=self._make_rag_context(),
        )

        call_kwargs = anthropic_client.messages.create.call_args[1]
        assert call_kwargs.get("temperature") == 0, (
            f"temperature=0이어야 하는데 {call_kwargs.get('temperature')} 전달됨"
        )

    def test_system_user_message_separated(self, mock_vanna_instance):
        """TC-SAT-02: anthropic_client 주입 시 system/user 메시지 분리"""
        anthropic_client = self._make_anthropic_mock(
            "SELECT campaign_id FROM ad_combined_log_summary"
        )
        generator = SQLGenerator(
            vanna_instance=mock_vanna_instance,
            anthropic_client=anthropic_client,
            model="claude-haiku-4-5-20251001",
        )

        generator.generate(
            question="어제 CTR 알려줘",
            rag_context=self._make_rag_context(),
        )

        call_kwargs = anthropic_client.messages.create.call_args[1]
        assert "system" in call_kwargs, "system 파라미터가 전달되지 않음"
        messages = call_kwargs.get("messages", [])
        assert len(messages) >= 1, "messages 배열이 비어있음"
        assert messages[0]["role"] == "user", (
            f"첫 메시지가 user여야 하는데 '{messages[0]['role']}'"
        )

    def test_fallback_to_vanna_when_no_anthropic_client(self, mock_vanna_instance):
        """TC-SAT-03: anthropic_client 없을 때 Vanna fallback"""
        mock_vanna_instance.submit_prompt.return_value = "SELECT 1"
        mock_vanna_instance.generate_sql.return_value = "SELECT 1"

        generator = SQLGenerator(
            vanna_instance=mock_vanna_instance,
            anthropic_client=None,
        )
        generator.generate(question="어제 CTR 알려줘")

        called = (
            mock_vanna_instance.submit_prompt.called
            or mock_vanna_instance.generate_sql.called
        )
        assert called, "anthropic_client 없을 때 vanna 메서드가 호출되어야 함"

    def test_generate_with_error_feedback_includes_error(self, mock_vanna_instance):
        """TC-SAT-04: generate_with_error_feedback() 호출 시 에러 정보가 user 메시지에 포함"""
        anthropic_client = self._make_anthropic_mock(
            "SELECT campaign_id FROM ad_combined_log_summary"
        )
        generator = SQLGenerator(
            vanna_instance=mock_vanna_instance,
            anthropic_client=anthropic_client,
            model="claude-haiku-4-5-20251001",
        )

        generator.generate_with_error_feedback(
            question="어제 CTR",
            failed_sql="SELECT x FROM ad_combined_log",
            error_message="column x not found",
            rag_context=self._make_rag_context(),
        )

        call_kwargs = anthropic_client.messages.create.call_args[1]
        user_content = call_kwargs["messages"][0]["content"]
        assert "column x not found" in user_content, (
            "에러 메시지가 user 메시지 content에 포함되어야 함"
        )


# ──────────────────────────────────────────────
# Phase C: Self-Correction Loop
# ──────────────────────────────────────────────

class TestSelfCorrectionLoop:
    """TC-SAT-05 ~ TC-SAT-08: Self-Correction Loop 동작 검증"""

    def _make_ctx(self) -> PipelineContext:
        ctx = PipelineContext(original_question="어제 CTR 알려줘")
        ctx.refined_question = "어제 CTR 알려줘"
        ctx.rag_context = RAGContext(
            ddl_context=[], documentation_context=[], sql_examples=[]
        )
        return ctx

    def _valid_result(self, sql: str = "SELECT 1") -> ValidationResult:
        return ValidationResult(is_valid=True, normalized_sql=sql)

    def _invalid_result(self, code: str) -> ValidationResult:
        return ValidationResult(
            is_valid=False,
            error_message=f"{code} 오류 발생",
            error_code=code,
        )

    @pytest.mark.asyncio
    async def test_no_retry_when_first_attempt_valid(self):
        """TC-SAT-05: 1회 성공 시 재시도 없음"""
        from src.query_pipeline import QueryPipeline

        mock_generator = MagicMock()
        mock_generator.generate.return_value = "SELECT campaign_id FROM ad_combined_log_summary"
        mock_validator = MagicMock()
        mock_validator.validate.return_value = self._valid_result(
            "SELECT campaign_id FROM ad_combined_log_summary"
        )

        with patch("src.query_pipeline.SELF_CORRECTION_ENABLED", True):
            pipeline = QueryPipeline.__new__(QueryPipeline)
            pipeline._sql_generator = mock_generator
            pipeline._sql_validator = mock_validator

            sql, result = await pipeline._generate_and_validate_with_correction(
                self._make_ctx()
            )

        assert result.is_valid
        assert mock_generator.generate.call_count == 1, "1회만 호출되어야 함"
        assert mock_generator.generate_with_error_feedback.call_count == 0

    @pytest.mark.asyncio
    async def test_retries_on_sql_parse_error(self):
        """TC-SAT-06: SQL_PARSE_ERROR 발생 시 재시도"""
        from src.query_pipeline import QueryPipeline

        mock_generator = MagicMock()
        mock_generator.generate.return_value = "INVALID SQL"
        mock_generator.generate_with_error_feedback.return_value = (
            "SELECT campaign_id FROM ad_combined_log_summary"
        )
        mock_validator = MagicMock()
        mock_validator.validate.side_effect = [
            self._invalid_result("SQL_PARSE_ERROR"),
            self._valid_result("SELECT campaign_id FROM ad_combined_log_summary"),
        ]

        with patch("src.query_pipeline.SELF_CORRECTION_ENABLED", True):
            pipeline = QueryPipeline.__new__(QueryPipeline)
            pipeline._sql_generator = mock_generator
            pipeline._sql_validator = mock_validator

            sql, result = await pipeline._generate_and_validate_with_correction(
                self._make_ctx()
            )

        assert result.is_valid
        assert mock_generator.generate_with_error_feedback.call_count == 1, (
            "1회 재시도가 이뤄져야 함"
        )

    @pytest.mark.asyncio
    async def test_no_retry_on_blocked_keyword(self):
        """TC-SAT-07: SQL_BLOCKED_KEYWORD는 재시도 안 함 (보안)"""
        from src.query_pipeline import QueryPipeline

        mock_generator = MagicMock()
        mock_generator.generate.return_value = "DROP TABLE ad_combined_log"
        mock_validator = MagicMock()
        mock_validator.validate.return_value = self._invalid_result("SQL_BLOCKED_KEYWORD")

        with patch("src.query_pipeline.SELF_CORRECTION_ENABLED", True):
            pipeline = QueryPipeline.__new__(QueryPipeline)
            pipeline._sql_generator = mock_generator
            pipeline._sql_validator = mock_validator

            sql, result = await pipeline._generate_and_validate_with_correction(
                self._make_ctx()
            )

        assert not result.is_valid
        assert mock_generator.generate_with_error_feedback.call_count == 0, (
            "보안 차단 에러는 재시도하지 않아야 함"
        )

    @pytest.mark.asyncio
    async def test_stops_at_max_correction_attempts(self):
        """TC-SAT-08: MAX_CORRECTION_ATTEMPTS 초과 시 중단"""
        from src.query_pipeline import QueryPipeline

        mock_generator = MagicMock()
        mock_generator.generate.return_value = "INVALID SQL"
        mock_generator.generate_with_error_feedback.return_value = "STILL INVALID"
        mock_validator = MagicMock()
        mock_validator.validate.return_value = self._invalid_result("SQL_PARSE_ERROR")

        with (
            patch("src.query_pipeline.SELF_CORRECTION_ENABLED", True),
            patch("src.query_pipeline.MAX_CORRECTION_ATTEMPTS", 2),
        ):
            pipeline = QueryPipeline.__new__(QueryPipeline)
            pipeline._sql_generator = mock_generator
            pipeline._sql_validator = mock_validator

            sql, result = await pipeline._generate_and_validate_with_correction(
                self._make_ctx()
            )

        assert mock_generator.generate_with_error_feedback.call_count == 2, (
            f"MAX_CORRECTION_ATTEMPTS=2 이므로 정확히 2회만 재시도해야 함, "
            f"실제: {mock_generator.generate_with_error_feedback.call_count}"
        )


# ──────────────────────────────────────────────
# Phase D: run_evaluation.py — Jinja2 렌더링
# ──────────────────────────────────────────────

class TestRenderGroundTruth:
    """TC-SAT-09 ~ TC-SAT-11: _render_ground_truth() 및 --limit 검증"""

    def _import_render_fn(self):
        """run_evaluation.py의 _render_ground_truth 함수 임포트"""
        from run_evaluation import _render_ground_truth
        return _render_ground_truth

    def test_renders_yesterday_variables(self):
        """TC-SAT-09: y_year, y_month, y_day → 실제 어제 날짜로 치환"""
        _render_ground_truth = self._import_render_fn()
        sql = (
            "WHERE year='{{ y_year }}' AND month='{{ y_month }}' AND day='{{ y_day }}'"
        )
        result = _render_ground_truth(sql)

        yesterday = date.today() - timedelta(days=1)
        assert yesterday.strftime("%Y") in result, f"y_year 치환 실패: {result}"
        assert yesterday.strftime("%m") in result, f"y_month 치환 실패: {result}"
        assert yesterday.strftime("%d") in result, f"y_day 치환 실패: {result}"
        assert "{{" not in result, "Jinja2 변수가 치환되지 않음"

    def test_renders_today_variables(self):
        """TC-SAT-10: year, month, day → 오늘 날짜로 치환"""
        _render_ground_truth = self._import_render_fn()
        sql = "WHERE year='{{ year }}' AND month='{{ month }}'"
        result = _render_ground_truth(sql)

        today = date.today()
        assert today.strftime("%Y") in result, f"year 치환 실패: {result}"
        assert today.strftime("%m") in result, f"month 치환 실패: {result}"
        assert "{{" not in result

    def test_limit_argument_default_is_none(self):
        """TC-SAT-11: --limit 인수의 기본값이 None (전체 실행)"""
        parser = argparse.ArgumentParser()
        parser.add_argument("--limit", type=int, default=None)
        args = parser.parse_args([])
        assert args.limit is None, f"--limit 기본값이 None이어야 함, 실제: {args.limit}"


# ──────────────────────────────────────────────
# Phase D: spider_evaluation.py — SQLNormalizer.strip_limit()
# ──────────────────────────────────────────────

class TestSQLNormalizerStripLimit:
    """TC-SAT-12 ~ TC-SAT-13: LIMIT 절 제거 검증"""

    def test_strip_limit_removes_limit_clause(self):
        """TC-SAT-12: LIMIT N 절이 제거됨"""
        from spider_evaluation import SQLNormalizer

        sql = "SELECT campaign_id FROM ad_combined_log_summary LIMIT 1000"
        result = SQLNormalizer.strip_limit(sql)
        assert "LIMIT" not in result.upper(), (
            f"LIMIT이 제거되어야 함, 실제: {result}"
        )
        assert "campaign_id" in result.lower(), "본 쿼리 내용은 보존되어야 함"

    def test_strip_limit_preserves_sql_without_limit(self):
        """TC-SAT-13: LIMIT 없는 SQL은 그대로"""
        from spider_evaluation import SQLNormalizer

        sql = "SELECT campaign_id FROM ad_combined_log_summary GROUP BY campaign_id"
        result = SQLNormalizer.strip_limit(sql)
        assert result.strip() == sql.strip(), (
            f"LIMIT 없는 SQL은 변경 없이 보존되어야 함\n원본: {sql}\n결과: {result}"
        )


# ──────────────────────────────────────────────
# Phase A-3: KeywordExtractor 화이트리스트 필터
# ──────────────────────────────────────────────

class TestKeywordFilter:
    """TC-KWF-01 ~ TC-KWF-05: 키워드 화이트리스트 필터 검증"""

    def test_filter_removes_hallucinated_keywords(self):
        """TC-KWF-01: 스키마에 없는 키워드(hallucination) 자동 제거"""
        from src.pipeline.keyword_extractor import _filter_keywords

        result = _filter_keywords(["CTR", "campaign_name", "channel", "어제"])
        assert "campaign_name" not in result, "campaign_name은 스키마에 없으므로 제거되어야 함"
        assert "channel" not in result, "channel은 스키마에 없으므로 제거되어야 함"
        assert "CTR" in result, "CTR은 유효한 지표명이므로 보존되어야 함"
        assert "어제" in result, "어제는 허용 시간 표현이므로 보존되어야 함"

    def test_filter_keeps_valid_column_names(self):
        """TC-KWF-02: 실제 컬럼명은 그대로 통과"""
        from src.pipeline.keyword_extractor import _filter_keywords

        valid = ["campaign_id", "device_type", "is_click", "CVR"]
        result = _filter_keywords(valid)
        assert len(result) == 4, f"4개 모두 보존되어야 함, 실제: {result}"

    def test_filter_case_insensitive(self):
        """TC-KWF-03: 대소문자 무관 비교 (ctr, Ctr, CTR 모두 허용)"""
        from src.pipeline.keyword_extractor import _filter_keywords

        result = _filter_keywords(["ctr", "Ctr", "CTR"])
        assert len(result) == 3, (
            f"대소문자 관계없이 3개 모두 허용되어야 함, 실제: {result}"
        )

    def test_filter_empty_input(self):
        """TC-KWF-04: 빈 리스트 입력 시 빈 리스트 반환"""
        from src.pipeline.keyword_extractor import _filter_keywords

        result = _filter_keywords([])
        assert result == [], f"빈 입력에 빈 결과 반환, 실제: {result}"

    def test_extract_applies_filter_to_llm_output(self):
        """TC-KWF-05: LLM이 hallucination 키워드 반환해도 extract() 결과에서 제거"""
        from src.pipeline.keyword_extractor import KeywordExtractor

        mock_client = MagicMock()
        response = MagicMock()
        # LLM이 campaign_name(없는 컬럼)을 포함해 반환
        response.content = [MagicMock(text='["CTR", "campaign_name", "ROAS"]')]
        mock_client.messages.create.return_value = response

        extractor = KeywordExtractor.__new__(KeywordExtractor)
        extractor._client = mock_client
        extractor._model = "claude-haiku-4-5-20251001"

        result = extractor.extract("어제 CTR 알려줘")
        assert "campaign_name" not in result, (
            "campaign_name은 필터로 제거되어야 함"
        )
        assert "CTR" in result, "CTR은 보존되어야 함"
        assert "ROAS" in result, "ROAS는 보존되어야 함"


# ──────────────────────────────────────────────
# Phase A: sql_generator.yaml 구조 검증
# ──────────────────────────────────────────────

class TestSQLGeneratorYaml:
    """TC-YAML-01 ~ TC-YAML-03: sql_generator.yaml 섹션 존재 및 내용 검증"""

    def _load_yaml(self):
        import yaml
        yaml_path = os.path.join(
            os.path.dirname(__file__), "..", "..", "prompts", "sql_generator.yaml"
        )
        with open(yaml_path, encoding="utf-8") as f:
            return yaml.safe_load(f)

    def test_negative_rules_section_exists(self):
        """TC-YAML-01: negative_rules 섹션이 추가되어 있는지 확인"""
        data = self._load_yaml()
        assert "negative_rules" in data, "negative_rules 섹션이 yaml에 없음"
        assert "campaign_name" in data["negative_rules"], (
            "negative_rules에 campaign_name 경고가 포함되어야 함"
        )

    def test_table_selection_rules_section_exists(self):
        """TC-YAML-02: table_selection_rules 섹션이 추가되어 있는지 확인"""
        data = self._load_yaml()
        assert "table_selection_rules" in data, "table_selection_rules 섹션이 yaml에 없음"
        assert "ad_combined_log_summary" in data["table_selection_rules"], (
            "table_selection_rules에 ad_combined_log_summary 내용 필요"
        )

    def test_cot_template_has_six_steps(self):
        """TC-YAML-03: cot_template이 6-Step으로 확장되었는지 확인"""
        data = self._load_yaml()
        assert "cot_template" in data, "cot_template 섹션이 yaml에 없음"
        assert "Step 6" in data["cot_template"], (
            "cot_template이 6-Step으로 확장되어야 함 (현재 4-Step)"
        )


# ──────────────────────────────────────────────
# Phase B: seed_chromadb.py Documentation·QA 검증
# ──────────────────────────────────────────────

class TestSeedChromaDB:
    """TC-SEED-01 ~ TC-SEED-03: seed_chromadb.py Documentation·QA 내용 검증"""

    def _all_docs(self):
        """seed_chromadb의 모든 Documentation 문자열을 1개 리스트로 반환."""
        seed_path = os.path.join(
            os.path.dirname(__file__), "..", "..", "scripts", "seed_chromadb.py"
        )
        import importlib.util
        spec = importlib.util.spec_from_file_location("seed_chromadb", seed_path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        docs: list[str] = []
        for attr in dir(mod):
            if attr.startswith("DOCS_"):
                val = getattr(mod, attr)
                if isinstance(val, list):
                    docs.extend(val)
        return docs, mod

    def test_nonexistent_columns_documentation_exists(self):
        """TC-SEED-01: campaign_name 등 존재하지 않는 컬럼 경고 Documentation 존재 확인"""
        docs, _ = self._all_docs()
        assert any("campaign_name" in doc for doc in docs), (
            "존재하지 않는 컬럼(campaign_name) 경고 Documentation이 없음"
        )
        assert any("ad_name" in doc for doc in docs), (
            "존재하지 않는 컬럼(ad_name) 경고 Documentation이 없음"
        )

    def test_categorical_values_documentation_exists(self):
        """TC-SEED-02: 컬럼 범주값 통합 Documentation이 단일 항목에 app_ios·purchase 포함"""
        docs, _ = self._all_docs()
        assert any("app_ios" in doc and "purchase" in doc for doc in docs), (
            "app_ios와 purchase를 함께 포함하는 통합 범주값 Documentation이 없음"
        )

    def test_qa_has_jinja2_date_pattern(self):
        """TC-SEED-03: QA 예제에 {{ y_year }} Jinja2 날짜 패턴 SQL 존재 확인"""
        _, mod = self._all_docs()
        qa_examples = mod.QA_EXAMPLES
        assert any("{{ y_year }}" in qa["sql"] for qa in qa_examples), (
            "Jinja2 패턴({{ y_year }})을 사용하는 QA SQL이 없음"
        )

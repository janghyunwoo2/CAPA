# [Test Result] sql-accuracy-tuning

| 항목 | 내용 |
|------|------|
| **Feature** | sql-accuracy-tuning |
| **테스트 방법** | TDD — pytest 단위 테스트 |
| **실행일** | 2026-03-24 |
| **실행 결과** | 24 passed / 0 failed (TC-YAML 3개 + TC-SEED 3개 추가) |

---

## TDD 사이클 요약

### Red Phase
- 총 13개 TC 중 12개 FAIL (TC-SAT-11만 PASS)
- 주요 실패 원인:
  - `SQLGenerator.__init__()` 에 `anthropic_client` 파라미터 없음
  - `query_pipeline.py` 임포트 시 `vanna`, `sentence_transformers`, `sqlglot` 미설치 오류
  - `run_evaluation.py`에 `_render_ground_truth()` 미구현
  - `SQLNormalizer.strip_limit()` 미구현

### Green Phase (구현 완료)
- 13/13 PASS (1.29s)
- 구현 내용:
  - `src/pipeline/sql_generator.py`: `anthropic_client` 주입, temperature=0, system/user 분리, `generate_with_error_feedback()`
  - `src/query_pipeline.py`: `SELF_CORRECTION_ENABLED`, `MAX_CORRECTION_ATTEMPTS` 환경변수, `_generate_and_validate_with_correction()` 메서드
  - `src/models/domain.py`: `ValidationResult.error_code` 필드 추가
  - `src/pipeline/sql_validator.py`: `error_code`를 `ValidationResult`에 전달
  - `evaluation/run_evaluation.py`: `_render_ground_truth()` 추가, `--limit` 기본값 None
  - `evaluation/spider_evaluation.py`: `SQLNormalizer.strip_limit()` 추가
- TC-KWF 5개 추가 (키워드 화이트리스트 필터):
  - `src/pipeline/keyword_extractor.py`: `_ALLOWED_KEYWORDS` 화이트리스트 + `_filter_keywords()` 추가, 시스템 프롬프트 제약 강화, `extract()` 내 필터 적용
- TC-YAML 3개 추가 (sql_generator.yaml 구조 검증):
  - `prompts/sql_generator.yaml`: `cot_template` 4-Step → 6-Step 교체, `negative_rules` 섹션 추가, `table_selection_rules` 섹션 추가
- TC-SEED 3개 추가 (seed_chromadb.py Documentation·QA 검증):
  - `scripts/seed_chromadb.py`: `DOCS_NONEXISTENT_COLUMNS` 추가 (존재하지 않는 컬럼 경고), `DOCS_CATEGORICAL_VALUES` 추가 (통합 범주값 목록), Jinja2 패턴 QA 7개 추가 (`{{ y_year }}` 등)

---

## 테스트 결과 상세

| TC | Step | 스텝 역할 | 인풋 | 아웃풋 (실제값) | assert 단언 | 판정 | 왜 이렇게 나왔나 |
|----|------|-----------|------|----------------|-------------|------|-----------------|
| TC-SAT-01 | A | temperature=0 전달 | `generate(question, rag_context)` with anthropic_client | `messages.create(temperature=0, ...)` 호출 | `assert call_kwargs["temperature"] == 0` | ✅ PASS | anthropic_client 직접 호출 경로에서 temperature=0 명시적 전달 |
| TC-SAT-02 | A | system/user 메시지 분리 | `generate(question, rag_context)` with anthropic_client | `messages.create(system=<규칙>, messages=[{role:user, ...}])` | `assert "system" in call_kwargs` | ✅ PASS | system_content에 규칙 통합, user_content에 RAG+질문 분리 구현 |
| TC-SAT-03 | A | Vanna fallback | `generate(question)` without anthropic_client | `vanna.submit_prompt` 또는 `generate_sql` 호출 | `assert called` | ✅ PASS | `if self._anthropic:` 분기로 하위 호환 유지 |
| TC-SAT-04 | A | 에러 피드백 포함 | `generate_with_error_feedback(question, failed_sql, error)` | user 메시지에 "column x not found" 포함 | `assert "column x not found" in user_content` | ✅ PASS | error_block을 `<error_feedback>` 태그로 user 메시지에 삽입 |
| TC-SAT-05 | C | 1회 성공 시 재시도 없음 | `_generate_and_validate_with_correction(ctx)` — 1차 유효 | `generate.call_count == 1` | `assert generate.call_count == 1` | ✅ PASS | `if not SELF_CORRECTION_ENABLED or validation.is_valid: return` |
| TC-SAT-06 | C | SQL_PARSE_ERROR 재시도 | 1차 실패(PARSE_ERROR) → 2차 성공 | `generate_with_error_feedback.call_count == 1` | `assert call_count == 1` | ✅ PASS | RETRYABLE_ERRORS에 SQL_PARSE_ERROR 포함, 1회 재시도 후 성공 |
| TC-SAT-07 | C | 보안 차단 재시도 없음 | SQL_BLOCKED_KEYWORD 발생 | `generate_with_error_feedback.call_count == 0` | `assert call_count == 0` | ✅ PASS | `_RETRYABLE_CORRECTION_ERRORS`에 BLOCKED_KEYWORD 미포함 → break |
| TC-SAT-08 | C | MAX 횟수 후 중단 | MAX_CORRECTION_ATTEMPTS=2, 모든 시도 실패 | `generate_with_error_feedback.call_count == 2` | `assert call_count == 2` | ✅ PASS | range(1, MAX+1) 루프가 정확히 2회 후 종료 |
| TC-SAT-09 | D | 어제 날짜 렌더링 | `"WHERE year='{{ y_year }}' AND month='{{ y_month }}' AND day='{{ y_day }}'"` | 실제 어제 날짜로 치환됨 | `assert yesterday.strftime("%Y") in result` | ✅ PASS | jinja2.Environment로 렌더링, y_year/y_month/y_day 변수 주입 |
| TC-SAT-10 | D | 오늘 날짜 렌더링 | `"WHERE year='{{ year }}' AND month='{{ month }}'"` | 오늘 날짜로 치환됨 | `assert today.strftime("%Y") in result` | ✅ PASS | 동일 패턴, year/month 변수 주입 |
| TC-SAT-11 | D | --limit 기본값 None | argparse 파싱 (인수 없음) | `args.limit is None` | `assert args.limit is None` | ✅ PASS | `default=3` → `default=None` 변경 |
| TC-SAT-12 | D | LIMIT 절 제거 | `"SELECT ... LIMIT 1000"` | `"SELECT ..."` (LIMIT 없음) | `assert "LIMIT" not in result.upper()` | ✅ PASS | `re.sub(r'\s+LIMIT\s+\d+...')` 정규식 제거 |
| TC-SAT-13 | D | LIMIT 없는 SQL 보존 | `"SELECT ... GROUP BY campaign_id"` | 동일 SQL 반환 | `assert result.strip() == sql.strip()` | ✅ PASS | 정규식이 매칭 안 되면 원본 반환 |

---

| TC-KWF-01 | A-3 | 화이트리스트 필터 | `["CTR", "campaign_name", "channel", "어제"]` | `["CTR", "어제"]` | `assert "campaign_name" not in result` | ✅ PASS | `_filter_keywords()` - allowed_lower 교차 검증으로 스키마 없는 컬럼 제거 |
| TC-KWF-02 | A-3 | 유효 컬럼 보존 | `["campaign_id", "device_type", "is_click", "CVR"]` | 4개 모두 보존 | `assert len(result) == 4` | ✅ PASS | 모두 _ALLOWED_KEYWORDS에 포함 |
| TC-KWF-03 | A-3 | 대소문자 무관 | `["ctr", "Ctr", "CTR"]` | 3개 모두 보존 | `assert len(result) == 3` | ✅ PASS | `kw.strip().lower() in allowed_lower` 비교 |
| TC-KWF-04 | A-3 | 빈 입력 | `[]` | `[]` | `assert result == []` | ✅ PASS | list comprehension이 빈 리스트 반환 |
| TC-KWF-05 | A-3 | extract() 필터 적용 | LLM Mock: `["CTR", "campaign_name", "ROAS"]` | `["CTR", "ROAS"]` | `assert "campaign_name" not in result` | ✅ PASS | extract() 내부에서 `_filter_keywords()` 호출, 로그: "키워드 추출 결과 (필터 후): ['CTR', 'ROAS']" |

---

| TC-YAML-01 | A | negative_rules 섹션 존재 | `yaml.safe_load("sql_generator.yaml")` | `data["negative_rules"]` 존재, `"campaign_name"` 포함 | `assert "negative_rules" in data` | ✅ PASS | yaml에 `negative_rules` 키 추가, campaign_name 포함 경고 문자열 |
| TC-YAML-02 | A | table_selection_rules 섹션 존재 | `yaml.safe_load("sql_generator.yaml")` | `data["table_selection_rules"]` 존재, `"ad_combined_log_summary"` 포함 | `assert "table_selection_rules" in data` | ✅ PASS | yaml에 `table_selection_rules` 키 추가, 두 테이블 선택 기준 명시 |
| TC-YAML-03 | A | cot_template 6-Step | `data["cot_template"]` | `"Step 6"` 포함 | `assert "Step 6" in data["cot_template"]` | ✅ PASS | 4-Step → 6-Step 교체 (DDL 컬럼 확인 + 최종 검증 Step 추가) |
| TC-SEED-01 | B | 존재하지 않는 컬럼 Doc | `DOCS_*` 전체 스캔 | `"campaign_name"`, `"ad_name"` 포함 항목 존재 | `assert any("campaign_name" in doc ...)` | ✅ PASS | `DOCS_NONEXISTENT_COLUMNS` 추가 — campaign_name/ad_name/advertiser_name/channel 경고 |
| TC-SEED-02 | B | 통합 범주값 Doc | `DOCS_*` 전체 스캔 | `"app_ios"`와 `"purchase"` 동시 포함 항목 존재 | `assert any("app_ios" in doc and "purchase" in doc ...)` | ✅ PASS | `DOCS_CATEGORICAL_VALUES` 추가 — 모든 컬럼 범주값 단일 항목으로 통합 |
| TC-SEED-03 | B | Jinja2 패턴 QA | `QA_EXAMPLES` 전체 스캔 | `"{{ y_year }}"` 포함 SQL 존재 | `assert any("{{ y_year }}" in qa["sql"] ...)` | ✅ PASS | 어제 날짜 기반 QA 3개 포함 (`{{ y_year }}/{{ y_month }}/{{ y_day }}` 패턴) |

## pytest 실행 로그 (요약)

```
============================= test session starts =============================
collected 13 items

TestSQLGeneratorWithAnthropicClient::test_temperature_zero_passed_to_api      PASSED
TestSQLGeneratorWithAnthropicClient::test_system_user_message_separated        PASSED
TestSQLGeneratorWithAnthropicClient::test_fallback_to_vanna_when_no_client     PASSED
TestSQLGeneratorWithAnthropicClient::test_generate_with_error_feedback         PASSED
TestSelfCorrectionLoop::test_no_retry_when_first_attempt_valid                 PASSED
TestSelfCorrectionLoop::test_retries_on_sql_parse_error                        PASSED
TestSelfCorrectionLoop::test_no_retry_on_blocked_keyword                       PASSED
TestSelfCorrectionLoop::test_stops_at_max_correction_attempts                  PASSED
TestRenderGroundTruth::test_renders_yesterday_variables                        PASSED
TestRenderGroundTruth::test_renders_today_variables                            PASSED
TestRenderGroundTruth::test_limit_argument_default_is_none                     PASSED
TestSQLNormalizerStripLimit::test_strip_limit_removes_limit_clause             PASSED
TestSQLNormalizerStripLimit::test_strip_limit_preserves_sql_without_limit      PASSED

======================= 13 passed, 4 warnings in 1.29s ========================
```

## pytest 실행 로그 — TC-YAML/TC-SEED 추가 (2026-03-24)

```
============================= test session starts =============================
collected 24 items

TestSQLGeneratorWithAnthropicClient::test_temperature_zero_passed_to_api      PASSED
TestSQLGeneratorWithAnthropicClient::test_system_user_message_separated        PASSED
TestSQLGeneratorWithAnthropicClient::test_fallback_to_vanna_when_no_client     PASSED
TestSQLGeneratorWithAnthropicClient::test_generate_with_error_feedback         PASSED
TestSelfCorrectionLoop::test_no_retry_when_first_attempt_valid                 PASSED
TestSelfCorrectionLoop::test_retries_on_sql_parse_error                        PASSED
TestSelfCorrectionLoop::test_no_retry_on_blocked_keyword                       PASSED
TestSelfCorrectionLoop::test_stops_at_max_correction_attempts                  PASSED
TestRenderGroundTruth::test_renders_yesterday_variables                        PASSED
TestRenderGroundTruth::test_renders_today_variables                            PASSED
TestRenderGroundTruth::test_limit_argument_default_is_none                     PASSED
TestSQLNormalizerStripLimit::test_strip_limit_removes_limit_clause             PASSED
TestSQLNormalizerStripLimit::test_strip_limit_preserves_sql_without_limit      PASSED
TestKeywordFilter::test_filter_removes_hallucinated_keywords                   PASSED
TestKeywordFilter::test_filter_keeps_valid_column_names                        PASSED
TestKeywordFilter::test_filter_case_insensitive                                PASSED
TestKeywordFilter::test_filter_empty_input                                     PASSED
TestKeywordFilter::test_extract_applies_filter_to_llm_output                   PASSED
TestSQLGeneratorYaml::test_negative_rules_section_exists                       PASSED
TestSQLGeneratorYaml::test_table_selection_rules_section_exists                PASSED
TestSQLGeneratorYaml::test_cot_template_has_six_steps                          PASSED
TestSeedChromaDB::test_nonexistent_columns_documentation_exists                PASSED
TestSeedChromaDB::test_categorical_values_documentation_exists                 PASSED
TestSeedChromaDB::test_qa_has_jinja2_date_pattern                              PASSED

======================= 24 passed, 4 warnings in 2.73s ========================
```

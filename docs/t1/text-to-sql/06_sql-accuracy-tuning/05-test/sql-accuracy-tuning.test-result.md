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
| **[배선 버그]** | C | `run()`에서 루프 메서드 미호출 | 실제 파이프라인 실행 | Self-Correction 미동작 | `run()`이 `_generate_and_validate_with_correction()` 대신 `generate()+validate()` 직접 호출 | ❌ **배선 누락** | TC-SAT-05~08은 메서드 단독 호출로만 검증 — `run()` 통합 테스트 부재. 2026-03-25 `run()` 수정 완료, `SELF_CORRECTION_ENABLED=true` docker-compose 환경변수 추가 완료 |
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

---

## 버그 수정 이력 (2026-03-24 — 실제 Exec 평가 실행 중 발견)

| # | 파일 | 버그 | 수정 내용 |
|---|------|------|----------|
| BUG-01 | `evaluation/spider_evaluation.py` | generated SQL을 Athena에서 재실행 (중복) — `/query`가 이미 실행했음에도 `ExecutionValidator`가 동일 SQL을 다시 실행해 Redash에 `eval_*` 쿼리 중복 생성 | `execute_sql(generated_sql)` 제거 → `/query` 응답의 `results` 직접 사용 |
| BUG-02 | `evaluation/spider_evaluation.py` | ground truth 결과 행 수 제한 없음 — `/query`는 최대 10행 반환하는데 ground truth는 전체 반환하여 비교 불공정 | `execute_sql()` 반환 rows에 `[:10]` 제한 추가 |
| BUG-03 | `evaluation/run_evaluation.py` | `generate_sql()` 메서드가 SQL만 반환 — Exec 평가에 results가 필요함에도 SQL만 반환 | `generate_sql()` → `query()` 변경, `(sql, results)` tuple 반환 |
| BUG-04 | `src/query_pipeline.py`, `src/redash_client.py` | Redash 쿼리 이름에 UTC 시간 사용 — `datetime.utcnow()`로 기록되어 Redash UI에서 KST와 9시간 차이 | `datetime.now(_KST)` 로 변경 (KST = UTC+9) |
| BUG-05 | `prompts/sql_generator.yaml` | `table_selection_rules` 기준 모호 — "일별 집계면 summary" 설명이 불명확해 LLM이 `ad_combined_log` 오선택 | 컬럼 존재 여부 기반 결정 규칙으로 교체 (전환 컬럼 필요 시 summary 필수, hour 분석 시 log 필수, 기본값 summary) |
| BUG-06 | `evaluation/spider_evaluation.py` | `compare_results()` 컬럼명까지 비교 — alias가 달라도 값이 같으면 동일 결과인데 컬럼명 불일치로 FAIL 처리 | 컬럼명 비교 제거 → 컬럼 수만 비교, 값은 `list(r.values())`로 위치 기준 비교 |
| BUG-07 | `evaluation/spider_evaluation.py` | ground truth 쿼리명이 `eval_{hash}` 형식 — Redash에서 어떤 질문의 정답 SQL인지 식별 불가 | `execute_sql()`에 `name` 파라미터 추가, `CAPA: {question} [GT] [{KST}]` 형식으로 변경 |
| BUG-08 | `src/query_pipeline.py` | Reranker 후보 풀 20건 — CPU 환경에서 41초 소요, 슬랙봇 타임아웃 유발 | 후보 수 20 → 10으로 축소 (처리 시간 약 50% 단축) |
| BUG-09 | `src/pipeline/reranker.py`, `src/pipeline/rag_retriever.py`, `src/query_pipeline.py` | Reranker `predict()`가 동기 함수라 비동기(async) 처리 불가 — event loop 블록으로 여러 사용자 동시 요청 시 병렬 처리 불가 | `predict()` → `run_in_executor`로 분리, `rerank()` / `retrieve_v2()` → `async def` + `await` 적용 |

---

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

## E2E 동작 검증 (2026-03-27)

> 배선 버그(2026-03-25) 수정 이후 실제 컨테이너 환경에서 Self-Correction이 end-to-end로 동작하는지 검증.
> `capa-vanna-api-e2e` 컨테이너에서 Python 스크립트로 직접 실행.

### 테스트 환경

| 항목 | 값 |
|------|----|
| 컨테이너 | `capa-vanna-api-e2e` (Up 27h, healthy) |
| 실행 방식 | `docker exec` → `python /app/test_self_correction.py` |
| `SELF_CORRECTION_ENABLED` | `true` (docker-compose.local-e2e.yml) |
| `MAX_CORRECTION_ATTEMPTS` | `3` |
| LLM | Anthropic Claude (실제 API 호출) |
| ChromaDB | `capa-chromadb-e2e` (실제 RAG) |
| Athena | 실제 AWS Athena (EXPLAIN 검증 포함) |

### 테스트 결과

| TC | Step | 스텝 역할 | 인풋 | 아웃풋 (실제값) | assert 단언 | 판정 | 왜 이렇게 나왔나 |
|----|------|-----------|------|----------------|-------------|------|-----------------|
| TC-SAT-E2E-01 | C | Self-Correction 루프 E2E 실행 | `SQLValidator.validate()` 1번째 호출 강제 `SQL_PARSE_ERROR` 반환 → 2번째부터 실제 검증 / 질문: "어제 광고 클릭 수 알려줘" | `Self-Correction 시도 1/3` 로그 출력 → `generate_with_error_feedback()` 실제 Anthropic API 재호출 → 2번째 validate 통과 → `Self-Correction 1회 만에 성공` 로그 → 파이프라인 완료 (12.58초) | `Self-Correction 시도 1/3` 로그 존재, `generate_with_error_feedback` Anthropic HTTP 200, `Self-Correction 1회 만에 성공` 로그 존재 | ✅ PASS | `run()` 내 `_generate_and_validate_with_correction()` 정상 호출, `SELF_CORRECTION_ENABLED=true` 환경변수 적용, `SQL_PARSE_ERROR`가 `_RETRYABLE_CORRECTION_ERRORS`에 포함되어 재시도 수행 |

### 핵심 로그 증거

```
src.query_pipeline:Self-Correction 시도 1/3: SQL 구문 분석에 실패했습니다 (테스트용 강제 실패)
src.pipeline.sql_generator:Self-Correction 재생성: error=SQL 구문 분석에 실패했습니다 (테스트용 강제 실패)
httpx:HTTP Request: POST https://api.anthropic.com/v1/messages "HTTP/1.1 200 OK"
src.pipeline.sql_generator:SQL 생성 완료: SELECT SUM(CAST(is_click AS INT)) AS total_clicks FROM ad_combined_log_summary ...
src.pipeline.sql_validator:SQL 검증 통과 (3계층 + EXPLAIN 모두 성공)
src.query_pipeline:Self-Correction 1회 만에 성공
src.query_pipeline:파이프라인 완료: 12.58초
```

---

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

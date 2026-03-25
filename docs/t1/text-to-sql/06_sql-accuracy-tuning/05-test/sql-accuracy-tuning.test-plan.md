# [Test Plan] sql-accuracy-tuning

| 항목 | 내용 |
|------|------|
| **Feature** | sql-accuracy-tuning |
| **테스트 방법** | TDD — pytest 단위 테스트 |
| **참고 설계서** | `../02-design/sql-accuracy-tuning.design.md` |
| **테스트 파일** | `services/vanna-api/tests/unit/test_sql_accuracy_tuning.py` |

---

## 테스트 대상 (Design 구현 항목 기준)

| Phase | 대상 파일 | 테스트 가능 항목 |
|-------|----------|----------------|
| A | `sql_generator.py` | temperature=0, system/user 분리, `generate_with_error_feedback()` |
| C | `query_pipeline.py` | Self-Correction Loop (`_generate_and_validate_with_correction`) |
| D | `run_evaluation.py` | `_render_ground_truth()`, `--limit` 기본값 |
| D | `spider_evaluation.py` | `SQLNormalizer.strip_limit()` |

---

## 테스트 케이스

### TC-SAT-01: SQLGenerator — anthropic_client 주입 시 temperature=0 전달

| 항목 | 내용 |
|------|------|
| **목적** | `anthropic_client` 주입 시 Anthropic API에 `temperature=0`이 전달되는지 확인 |
| **사전 조건** | `anthropic_client` Mock 주입, `PHASE2_RAG_ENABLED` 무관 |
| **테스트 입력** | `generate(question="어제 CTR", rag_context=RAGContext(...))` |
| **기대 결과** | `anthropic_client.messages.create` 호출 시 `temperature=0` 포함 |
| **검증 코드** | `assert call_kwargs["temperature"] == 0` |

---

### TC-SAT-02: SQLGenerator — system/user 메시지 분리 전달

| 항목 | 내용 |
|------|------|
| **목적** | `anthropic_client` 주입 시 system 메시지와 user 메시지가 분리되는지 확인 |
| **사전 조건** | `anthropic_client` Mock, `sql_generator.yaml` 로드 가능 환경 |
| **테스트 입력** | `generate(question="어제 CTR", rag_context=RAGContext(...))` |
| **기대 결과** | `messages.create(system=<규칙블록>, messages=[{"role":"user","content":...}])` |
| **검증 코드** | `assert "system" in call_kwargs` / `assert call_kwargs["messages"][0]["role"] == "user"` |

---

### TC-SAT-03: SQLGenerator — anthropic_client 없을 때 Vanna fallback

| 항목 | 내용 |
|------|------|
| **목적** | `anthropic_client=None` 시 기존 `vanna.submit_prompt` 경로로 동작 확인 |
| **사전 조건** | `anthropic_client` 미주입 |
| **테스트 입력** | `generate(question="어제 CTR")` |
| **기대 결과** | `vanna.submit_prompt` 또는 `vanna.generate_sql` 호출됨 |
| **검증 코드** | `mock_vanna.submit_prompt.called or mock_vanna.generate_sql.called` |

---

### TC-SAT-04: SQLGenerator — generate_with_error_feedback() 에러 블록 포함

| 항목 | 내용 |
|------|------|
| **목적** | `generate_with_error_feedback()` 호출 시 에러 정보가 프롬프트에 포함되는지 확인 |
| **사전 조건** | `anthropic_client` Mock |
| **테스트 입력** | `generate_with_error_feedback(question="CTR", failed_sql="SELECT x", error_message="column x not found")` |
| **기대 결과** | user 메시지 content에 `"column x not found"` 포함 |
| **검증 코드** | `assert "column x not found" in call_kwargs["messages"][0]["content"]` |

---

### TC-SAT-05: Self-Correction — 1회 성공 시 재시도 없음

| 항목 | 내용 |
|------|------|
| **목적** | 첫 SQL 생성이 유효할 때 Self-Correction이 실행되지 않음 확인 |
| **사전 조건** | `SELF_CORRECTION_ENABLED=true`, SQLValidator가 `is_valid=True` 반환 |
| **테스트 입력** | `_generate_and_validate_with_correction(ctx)` |
| **기대 결과** | `sql_generator.generate()` 1회만 호출됨 |
| **검증 코드** | `mock_generator.generate.call_count == 1` |

---

### TC-SAT-06: Self-Correction — SQL_PARSE_ERROR 시 재시도

| 항목 | 내용 |
|------|------|
| **목적** | `SQL_PARSE_ERROR` 발생 시 `SELF_CORRECTION_ENABLED=true`이면 재시도하는지 확인 |
| **사전 조건** | `SELF_CORRECTION_ENABLED=true`, 1차 검증 실패(SQL_PARSE_ERROR) → 2차 성공 |
| **테스트 입력** | `_generate_and_validate_with_correction(ctx)` |
| **기대 결과** | `generate_with_error_feedback()` 1회 호출 후 성공 |
| **검증 코드** | `mock_generator.generate_with_error_feedback.call_count == 1` |

---

### TC-SAT-07: Self-Correction — SQL_BLOCKED_KEYWORD는 재시도 안 함

| 항목 | 내용 |
|------|------|
| **목적** | 보안 차단 에러는 Self-Correction 대상에서 제외되는지 확인 |
| **사전 조건** | `SELF_CORRECTION_ENABLED=true`, 검증 실패(SQL_BLOCKED_KEYWORD) |
| **테스트 입력** | `_generate_and_validate_with_correction(ctx)` |
| **기대 결과** | `generate_with_error_feedback()` 호출 없이 원래 SQL 반환 |
| **검증 코드** | `mock_generator.generate_with_error_feedback.call_count == 0` |

---

### TC-SAT-08: Self-Correction — MAX_CORRECTION_ATTEMPTS 초과 시 중단

| 항목 | 내용 |
|------|------|
| **목적** | 최대 재시도 횟수 초과 시 마지막 SQL을 반환하는지 확인 |
| **사전 조건** | `SELF_CORRECTION_ENABLED=true`, `MAX_CORRECTION_ATTEMPTS=2`, 모든 시도 실패 |
| **테스트 입력** | `_generate_and_validate_with_correction(ctx)` |
| **기대 결과** | `generate_with_error_feedback()` 정확히 2회 호출 후 중단 |
| **검증 코드** | `mock_generator.generate_with_error_feedback.call_count == 2` |

---

### TC-SAT-09: _render_ground_truth() — 어제 날짜 변수 렌더링

| 항목 | 내용 |
|------|------|
| **목적** | `y_year`, `y_month`, `y_day` 변수가 실제 어제 날짜로 치환되는지 확인 |
| **사전 조건** | 테스트 실행일 기준 어제 날짜 사용 |
| **테스트 입력** | `"WHERE year='{{ y_year }}' AND month='{{ y_month }}' AND day='{{ y_day }}'"` |
| **기대 결과** | 실제 어제 날짜 문자열 포함 (예: `year='2026' AND month='03' AND day='23'`) |
| **검증 코드** | `assert yesterday.strftime("%Y") in result` |

---

### TC-SAT-10: _render_ground_truth() — 오늘/이번달 변수 렌더링

| 항목 | 내용 |
|------|------|
| **목적** | `year`, `month`, `day` 변수가 오늘 날짜로 치환되는지 확인 |
| **테스트 입력** | `"WHERE year='{{ year }}' AND month='{{ month }}'"` |
| **기대 결과** | 오늘의 `year`, `month` 값 포함 |
| **검증 코드** | `assert today.strftime("%Y") in result` |

---

### TC-SAT-11: run_evaluation.py — --limit 기본값 None

| 항목 | 내용 |
|------|------|
| **목적** | `--limit` 인수의 기본값이 None (전체 실행)인지 확인 |
| **테스트 입력** | `argparse` 파싱 (인수 없음) |
| **기대 결과** | `args.limit is None` |
| **검증 코드** | `assert args.limit is None` |

---

### TC-KWF-01: _filter_keywords() — 화이트리스트에 없는 키워드 제거

| 항목 | 내용 |
|------|------|
| **목적** | 스키마에 없는 컬럼명(hallucination)이 자동 제거되는지 확인 |
| **테스트 입력** | `["CTR", "campaign_name", "channel", "어제"]` |
| **기대 결과** | `["CTR", "어제"]` (campaign_name, channel 제거) |
| **검증 코드** | `assert "campaign_name" not in result` / `assert "CTR" in result` |

---

### TC-KWF-02: _filter_keywords() — 유효한 컬럼명 보존

| 항목 | 내용 |
|------|------|
| **목적** | 실제 컬럼명은 그대로 통과되는지 확인 |
| **테스트 입력** | `["campaign_id", "device_type", "is_click", "CVR"]` |
| **기대 결과** | 4개 모두 보존 |
| **검증 코드** | `assert len(result) == 4` |

---

### TC-KWF-03: _filter_keywords() — 대소문자 무관 처리

| 항목 | 내용 |
|------|------|
| **목적** | `CTR`, `ctr`, `Ctr` 모두 유효로 처리되는지 확인 |
| **테스트 입력** | `["ctr", "Ctr", "CTR"]` |
| **기대 결과** | 3개 모두 보존 |
| **검증 코드** | `assert len(result) == 3` |

---

### TC-KWF-04: _filter_keywords() — 빈 입력 처리

| 항목 | 내용 |
|------|------|
| **목적** | 빈 리스트 입력 시 빈 리스트 반환 |
| **테스트 입력** | `[]` |
| **기대 결과** | `[]` |
| **검증 코드** | `assert result == []` |

---

### TC-KWF-05: KeywordExtractor.extract() — LLM 출력에 필터 적용

| 항목 | 내용 |
|------|------|
| **목적** | LLM이 hallucination 키워드를 반환해도 extract() 최종 결과에서 제거 확인 |
| **사전 조건** | LLM Mock이 `["CTR", "campaign_name", "ROAS"]` 반환 |
| **기대 결과** | `["CTR", "ROAS"]` (campaign_name 제거) |
| **검증 코드** | `assert "campaign_name" not in result` |

---

### TC-YAML-01: sql_generator.yaml — negative_rules 섹션 존재 확인

| 항목 | 내용 |
|------|------|
| **목적** | `prompts/sql_generator.yaml`에 `negative_rules` 섹션이 추가되었는지 확인 |
| **사전 조건** | yaml 파일 직접 파싱 |
| **테스트 입력** | `yaml.safe_load(open("prompts/sql_generator.yaml"))` |
| **기대 결과** | `"negative_rules"` 키 존재, 내용에 `"campaign_name"` 포함 |
| **검증 코드** | `assert "negative_rules" in data` / `assert "campaign_name" in data["negative_rules"]` |

---

### TC-YAML-02: sql_generator.yaml — table_selection_rules 섹션 존재 확인

| 항목 | 내용 |
|------|------|
| **목적** | `prompts/sql_generator.yaml`에 `table_selection_rules` 섹션이 추가되었는지 확인 |
| **테스트 입력** | `yaml.safe_load(open("prompts/sql_generator.yaml"))` |
| **기대 결과** | `"table_selection_rules"` 키 존재, 내용에 `"ad_combined_log_summary"` 포함 |
| **검증 코드** | `assert "table_selection_rules" in data` / `assert "ad_combined_log_summary" in data["table_selection_rules"]` |

---

### TC-YAML-03: sql_generator.yaml — cot_template 6-Step 확인

| 항목 | 내용 |
|------|------|
| **목적** | `cot_template`이 6-Step으로 확장되었는지 확인 |
| **테스트 입력** | `yaml.safe_load(open("prompts/sql_generator.yaml"))["cot_template"]` |
| **기대 결과** | `"Step 6"` 포함 |
| **검증 코드** | `assert "Step 6" in data["cot_template"]` |

---

### TC-SEED-01: seed_chromadb.py — 존재하지 않는 컬럼 Documentation 존재 확인

| 항목 | 내용 |
|------|------|
| **목적** | `seed_chromadb.py`에 `campaign_name` 등 존재하지 않는 컬럼 경고 Documentation이 추가되었는지 확인 |
| **테스트 입력** | `seed_chromadb` 모듈 임포트 후 Documentation 상수 검사 |
| **기대 결과** | Documentation 문자열 중 `"campaign_name"`, `"ad_name"` 포함 항목 존재 |
| **검증 코드** | `assert any("campaign_name" in doc for doc in all_docs)` |

---

### TC-SEED-02: seed_chromadb.py — 컬럼 범주값 통합 Documentation 존재 확인

| 항목 | 내용 |
|------|------|
| **목적** | 컬럼 범주값 목록이 단일 통합 Documentation으로 존재하는지 확인 |
| **테스트 입력** | `seed_chromadb` 모듈 임포트 후 Documentation 상수 검사 |
| **기대 결과** | `"app_ios"`, `"app_android"`, `"purchase"`, `"signup"` 등을 모두 포함하는 단일 항목 존재 |
| **검증 코드** | `assert any("app_ios" in doc and "purchase" in doc for doc in all_docs)` |

---

### TC-SEED-03: seed_chromadb.py — Jinja2 패턴 QA 존재 확인

| 항목 | 내용 |
|------|------|
| **목적** | QA 예제에 `{{ y_year }}` 형식의 Jinja2 날짜 패턴 SQL이 포함되는지 확인 |
| **테스트 입력** | `seed_chromadb.QA_EXAMPLES` 목록 검사 |
| **기대 결과** | 1개 이상의 QA SQL에 `"{{ y_year }}"` 포함 |
| **검증 코드** | `assert any("{{ y_year }}" in qa["sql"] for qa in QA_EXAMPLES)` |

---

### TC-SAT-12: SQLNormalizer.strip_limit() — LIMIT 절 제거

| 항목 | 내용 |
|------|------|
| **목적** | EM 비교 전 `LIMIT N` 절이 제거되는지 확인 |
| **테스트 입력** | `"SELECT campaign_id FROM ad_combined_log_summary LIMIT 1000"` |
| **기대 결과** | `"SELECT campaign_id FROM ad_combined_log_summary"` |
| **검증 코드** | `assert "LIMIT" not in SQLNormalizer.strip_limit(sql)` |

---

### TC-SAT-13: SQLNormalizer.strip_limit() — LIMIT 없는 SQL 보존

| 항목 | 내용 |
|------|------|
| **목적** | LIMIT 없는 SQL이 strip_limit 후에도 그대로인지 확인 |
| **테스트 입력** | `"SELECT campaign_id FROM ad_combined_log_summary GROUP BY campaign_id"` |
| **기대 결과** | 동일 SQL 반환 |
| **검증 코드** | `assert strip_limit(sql).strip() == sql.strip()` |

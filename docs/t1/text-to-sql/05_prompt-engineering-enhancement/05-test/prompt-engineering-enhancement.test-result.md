# [Test Result] Prompt Engineering Enhancement (FR-PE)

| 항목 | 내용 |
|------|------|
| **Feature** | prompt-engineering-enhancement |
| **테스트 파일** | `services/vanna-api/tests/unit/test_prompt_engineering.py` |
| **실행일** | 2026-03-23 |
| **최종 결과** | ✅ 14/14 PASS |

---

## 테스트 결과 테이블

| TC | Step | 스텝 역할 | 인풋 | 아웃풋 (실제값) | assert 단언 | 판정 | 왜 이렇게 나왔나 |
|----|------|-----------|------|----------------|-------------|------|-----------------|
| TC-PE-01 | - | PromptLoader YAML 로드 | `loader.load("sql_generator")` | `{"system": "...", "schema": "..."}` dict | `assert "system" in result` | ✅ PASS | YAML 파일 정상 파싱, dict 반환 |
| TC-PE-02 | - | PromptLoader fallback | `loader.load("nonexistent")` | `{}` | `assert result == {}` | ✅ PASS | 파일 없으면 경고 로그 후 빈 dict 반환 |
| TC-PE-03 | - | Jinja2 변수 치환 | `loader.load("sql_generator", today="2026-03-23")` | `date_rules`에 `"2026-03-23"` 포함 | `assert "2026-03-23" in result["date_rules"]` | ✅ PASS | Jinja2 `Template.render()` 정상 동작 |
| TC-PE-04 | - | mtime 캐시 핫 리로드 | 파일 수정 후 재로드 | `result["system"] == "version 2"` | `assert result_v2["system"] == "version 2"` | ✅ PASS | mtime 변경 감지 → 캐시 갱신 |
| TC-PE-05 | Step 5 | SQLGenerator history 주입 | `generate(question, conversation_history=[turn])` | question에 `<history>` 블록 포함 | `assert "<history>" in captured_prompt` | ✅ PASS | FR-PE-01 버그 수정 — history 주입 코드 정상 동작 |
| TC-PE-06 | Step 5 | SQLGenerator history 미주입 | `generate(question, conversation_history=None)` | question에 `<history>` 없음 | `assert "<history>" not in captured_prompt` | ✅ PASS | history=None 시 history_block="" 유지 |
| TC-PE-07 | Step 5 | CoT cot_template 주입 | `generate("테스트")`, cot_template=`<thinking>...` | question에 `<thinking>` 포함 | `assert "<thinking>" in captured_prompt` | ✅ PASS | YAML cot_template이 prompt 문자열에 포함됨 |
| TC-PE-08 | Step 5 | date_rules 구조화 주입 | `generate("지난달 실적")`, date_rules=`<date_rules>...` | question에 `<date_rules>` 포함 | `assert "<date_rules>" in captured_prompt` | ✅ PASS | YAML date_rules가 prompt 문자열에 포함됨 |
| TC-PE-09 | - | `_strip_thinking_block` 제거 | `"<thinking>Step 1</thinking>\nSELECT * FROM ad_logs"` | `"SELECT * FROM ad_logs"` | `assert result == "SELECT * FROM ad_logs"` | ✅ PASS | regex DOTALL로 블록 제거 후 strip() |
| TC-PE-10 | - | `_strip_thinking_block` 원본 유지 | `"SELECT * FROM ad_logs WHERE year='2026'"` | 동일 문자열 반환 | `assert result == sql` | ✅ PASS | `<thinking>` 없으면 원본 그대로 반환 |
| TC-PE-11 | Step 1 | IntentClassifier YAML 프롬프트 | `classify("지난달 CTR 알려줘")`, YAML system="YAML 시스템 프롬프트" | `messages.create(system="YAML 시스템 프롬프트")` | `assert call_kwargs["system"] == "YAML 시스템 프롬프트"` | ✅ PASS | `load_prompt` 결과를 `system` 파라미터에 주입 |
| TC-PE-12 | Step 1 | IntentClassifier fallback | `classify("테스트")`, YAML={} | `messages.create(system=_SYSTEM_PROMPT)` | `assert "DATA_QUERY" in call_kwargs["system"]` | ✅ PASS | YAML 빈 dict → `prompts.get("system", _SYSTEM_PROMPT)` fallback |
| TC-PE-13 | Step 2 | QuestionRefiner YAML 프롬프트 | `refine("안녕하세요! 지난달 CTR 알려주세요")`, YAML system="YAML 정제기 프롬프트" | `messages.create(system="YAML 정제기 프롬프트")` | `assert call_kwargs["system"] == "YAML 정제기 프롬프트"` | ✅ PASS | `load_prompt` 결과를 `system` 파라미터에 주입 |
| TC-PE-14 | Step 10 | AIAnalyzer YAML instructions | `analyze(question, sql, query_results)`, YAML instructions=`<instructions>CTR=...` | content[0]["text"]에 `"CTR=clicks/impressions"` 포함 | `assert "CTR=clicks/impressions" in instructions_text` | ✅ PASS | `load_prompt` 결과를 첫 번째 content block text에 주입 |

---

## TDD 사이클 요약

### Red Phase
- **총 14개 TC 중 14개 FAIL** (초기 Red)
- 주요 원인:
  - `src.prompt_loader` 모듈 미존재
  - `src.pipeline.sql_generator.load_prompt` 속성 없음
  - `_strip_thinking_block` 함수 미존재
  - `intent_classifier`, `question_refiner`, `ai_analyzer`에 `load_prompt` 없음

### Green Phase

**1차 구현** (TC-PE-01~10 통과):
- `src/prompt_loader.py` 신규 생성 (PromptLoader + load_prompt)
- `src/pipeline/sql_generator.py` 수정:
  - `load_prompt` 임포트 및 YAML 로드
  - `_strip_thinking_block()` 함수 추가
  - `conversation_history` → `<history>` 블록 주입 (FR-PE-01 버그 수정)
  - `date_rules`, `cot_template` YAML에서 로드하여 prompt 구성 (FR-PE-02, FR-PE-03)
- `requirements.txt`에 `pyyaml>=6.0`, `jinja2>=3.1` 추가

**2차 구현** (TC-PE-11~14 통과):
- `src/pipeline/intent_classifier.py`: `load_prompt` 임포트 + `prompts.get("system", _SYSTEM_PROMPT)` fallback 적용
- `src/pipeline/question_refiner.py`: `load_prompt` 임포트 + `prompts.get("system", _SYSTEM_PROMPT)` fallback 적용
- `src/pipeline/ai_analyzer.py`: `load_prompt` 임포트 + `prompts.get("instructions", _INSTRUCTIONS_FALLBACK)` fallback 적용

### 최종 결과: 14/14 PASS (2.44s)

---

## pytest 실행 로그

```
============================= test session starts =============================
platform win32 -- Python 3.13.5, pytest-8.3.4
configfile: pytest.ini

tests/unit/test_prompt_engineering.py::TestPromptLoader::test_load_yaml_returns_dict PASSED
tests/unit/test_prompt_engineering.py::TestPromptLoader::test_load_missing_yaml_returns_empty_dict PASSED
tests/unit/test_prompt_engineering.py::TestPromptLoader::test_load_renders_jinja2_variables PASSED
tests/unit/test_prompt_engineering.py::TestPromptLoader::test_load_reloads_on_mtime_change PASSED
tests/unit/test_prompt_engineering.py::TestSQLGeneratorPromptInjection::test_conversation_history_injected_in_prompt PASSED
tests/unit/test_prompt_engineering.py::TestSQLGeneratorPromptInjection::test_no_history_no_history_block PASSED
tests/unit/test_prompt_engineering.py::TestSQLGeneratorPromptInjection::test_cot_template_injected_in_prompt PASSED
tests/unit/test_prompt_engineering.py::TestSQLGeneratorPromptInjection::test_date_rules_injected_in_prompt PASSED
tests/unit/test_prompt_engineering.py::TestStripThinkingBlock::test_removes_thinking_block PASSED
tests/unit/test_prompt_engineering.py::TestStripThinkingBlock::test_no_thinking_block_returns_original PASSED
tests/unit/test_prompt_engineering.py::TestIntentClassifierYaml::test_uses_yaml_system_prompt PASSED
tests/unit/test_prompt_engineering.py::TestIntentClassifierYaml::test_falls_back_to_code_prompt_when_yaml_empty PASSED
tests/unit/test_prompt_engineering.py::TestQuestionRefinerYaml::test_uses_yaml_system_prompt PASSED
tests/unit/test_prompt_engineering.py::TestAIAnalyzerYaml::test_uses_yaml_instructions PASSED
============================= 14 passed in 2.44s ==============================
```

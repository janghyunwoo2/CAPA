# [Analysis] Prompt Engineering Enhancement — Gap 분석

| 항목 | 내용 |
|------|------|
| **Feature** | prompt-engineering-enhancement |
| **분석일** | 2026-03-23 |
| **Design 문서** | `docs/t1/text-to-sql/05_prompt-engineering-enhancement/02-design/features/prompt-engineering-enhancement.design.md` |
| **Match Rate** | **97%** ✅ |
| **판정** | PASS (≥ 90%) |

---

## 1. FR별 구현 현황

| FR ID | 요구사항 | 구현 상태 | 근거 |
|-------|---------|:---------:|------|
| FR-PE-01 | conversation_history 주입 버그 수정 | ✅ PASS | `sql_generator.py:93-105` `<history>` 블록 주입 구현 완료 |
| FR-PE-02 | CoT 단계 추가 | ✅ PASS | `sql_generator.yaml` cot_template + `sql_generator.py:108` 프롬프트 조합 + `_strip_thinking_block()` 후처리 |
| FR-PE-03 | 날짜 파티션 규칙 XML 구조화 | ✅ PASS | `sql_generator.yaml` `<date_rules>` 블록 + Jinja2 변수 치환 |
| FR-PE-04 | 프롬프트 YAML 외부화 + 핫 리로드 | ✅ PASS | `prompt_loader.py` mtime 캐시 구현, 4개 YAML 파일 존재 |
| FR-PE-05 | AIAnalyzer 지표 참조 추가 | ✅ PASS | `ai_analyzer.yaml` Ad Metrics Reference (CTR/CVR/ROAS 정의) 추가 |

---

## 2. 파일 존재 확인

| 파일 | 구분 | 존재 여부 |
|------|------|:---------:|
| `src/prompt_loader.py` | 신규 | ✅ |
| `prompts/sql_generator.yaml` | 신규 | ✅ |
| `prompts/intent_classifier.yaml` | 신규 | ✅ |
| `prompts/question_refiner.yaml` | 신규 | ✅ |
| `prompts/ai_analyzer.yaml` | 신규 | ✅ |
| `src/pipeline/sql_generator.py` | 수정 | ✅ |
| `src/pipeline/intent_classifier.py` | 수정 | ✅ |
| `src/pipeline/question_refiner.py` | 수정 | ✅ |
| `src/pipeline/ai_analyzer.py` | 수정 | ✅ |
| `requirements.txt` | 수정 | ✅ (pyyaml>=6.0, jinja2>=3.1) |

---

## 3. Gap 목록

### 3.1 Medium (기능 영향 없음, 설계 일치 개선 필요)

| # | 항목 | Design | Implementation | 비고 |
|---|------|--------|---------------|------|
| G-01 | `sql_generator.yaml` 키 구성 | `system`, `schema`, `date_rules`, `cot_template` | `date_rules`, `cot_template` (system, schema 미포함) | `sql_generator.py`에서 `prompts.get("schema", "")` fallback 처리 중. 기능 장애 없음. YAML에 추가하면 FR-PE-04 취지에 완전 부합 |

### 3.2 Low (설계 대비 개선된 부분)

| # | 항목 | Design | Implementation | 비고 |
|---|------|--------|---------------|------|
| G-02 | `PromptLoader.__init__` 시그니처 | `def __init__(self)` | `def __init__(self, prompts_dir=None)` | 테스트 유연성 향상 (DI 지원) — 개선 |
| G-03 | `_PROMPTS_DIR` 변수명 | `_PROMPTS_DIR` | `_DEFAULT_PROMPTS_DIR` | 의미 명확화 — 개선 |
| G-04 | yaml.safe_load null 처리 | `yaml.safe_load(raw)` | `yaml.safe_load(raw) or {}` | null-safe 강화 — 개선 |
| G-05 | `_FALLBACK_DATE_CONTEXT` 경고 문구 | 기본 경고 | `[경고: 예시 SQL의 날짜 값을 그대로 복사하지 말 것]` 추가 | 개선 |

---

## 4. Match Rate 산출

| 분류 | 항목 수 | Match |
|------|---------|-------|
| FR 구현 (FR-PE-01~05) | 5 | 5 |
| 파일 존재 (10개) | 10 | 10 |
| 핵심 구현 패턴 (15개) | 15 | 14 |
| **합계** | **30** | **29** |

**Match Rate: 29/30 = 97%** ✅

---

## 5. 권장 조치

### 즉시 조치 (선택)
- `prompts/sql_generator.yaml`에 `system`/`schema` 키 추가 → G-01 해소, 100% 달성

### 문서 업데이트
- Design 문서 `PromptLoader.__init__` 시그니처를 구현 기준으로 업데이트

---

## 6. 결론

**Match Rate 97% — 기준(90%) 초과 달성.**
FR-PE-01~05 전체 구현 완료. Gap은 설계 대비 개선된 부분(Low)과 YAML 키 구성 차이(Medium, 기능 영향 없음) 뿐. `/pdca report`로 완료 보고서 생성 가능.

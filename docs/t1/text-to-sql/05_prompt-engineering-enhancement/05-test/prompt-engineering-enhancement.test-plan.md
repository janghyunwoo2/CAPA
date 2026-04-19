# [Test Plan] Prompt Engineering Enhancement (FR-PE)

| 항목 | 내용 |
|------|------|
| **Feature** | prompt-engineering-enhancement |
| **테스트 방법** | TDD — pytest 단위 테스트 |
| **참고 설계서** | `docs/t1/text-to-sql/05_prompt-engineering-enhancement/02-design/features/prompt-engineering-enhancement.design.md` |
| **테스트 파일** | `services/vanna-api/tests/unit/test_prompt_engineering.py` |

---

## 테스트 케이스

### TC-PE-01: PromptLoader — YAML 정상 로드
| 항목 | 내용 |
|------|------|
| **대상 FR** | FR-PE-04 |
| **목적** | YAML 파일이 존재할 때 딕셔너리로 정상 반환 |
| **사전 조건** | tmp_path에 `sql_generator.yaml` 생성 |
| **테스트 입력** | `loader.load("sql_generator")` |
| **기대 결과** | `{"system": "...", "schema": "..."}` 딕셔너리 반환 |
| **검증 코드** | `assert "system" in result` |

### TC-PE-02: PromptLoader — YAML 없을 때 빈 딕셔너리 반환 (fallback)
| 항목 | 내용 |
|------|------|
| **대상 FR** | FR-PE-04 |
| **목적** | YAML 파일 없으면 빈 딕셔너리 반환 → 호출부 fallback 보장 |
| **사전 조건** | 존재하지 않는 파일명 |
| **테스트 입력** | `loader.load("nonexistent")` |
| **기대 결과** | `{}` 반환 (예외 없음) |
| **검증 코드** | `assert result == {}` |

### TC-PE-03: PromptLoader — Jinja2 날짜 변수 치환
| 항목 | 내용 |
|------|------|
| **대상 FR** | FR-PE-03, FR-PE-04 |
| **목적** | `{{ today }}` 변수가 실제 날짜로 치환되는지 확인 |
| **사전 조건** | `date_rules: "오늘={{ today }}"` YAML |
| **테스트 입력** | `loader.load("sql_generator", today="2026-03-23")` |
| **기대 결과** | `result["date_rules"]`에 `"2026-03-23"` 포함 |
| **검증 코드** | `assert "2026-03-23" in result["date_rules"]` |

### TC-PE-04: PromptLoader — mtime 변경 시 캐시 갱신 (핫 리로드)
| 항목 | 내용 |
|------|------|
| **대상 FR** | FR-PE-04 |
| **목적** | 파일 수정 후 재로드 시 새 내용 반환 |
| **사전 조건** | YAML 로드 후 파일 내용 변경 |
| **테스트 입력** | 파일 수정 후 `loader.load()` 재호출 |
| **기대 결과** | 수정된 내용 반환 |
| **검증 코드** | `assert result["system"] == "updated content"` |

### TC-PE-05: SQLGenerator — conversation_history 프롬프트 주입 (FR-PE-01 버그 수정)
| 항목 | 내용 |
|------|------|
| **대상 FR** | FR-PE-01 |
| **목적** | conversation_history가 있을 때 Vanna에 전달되는 프롬프트에 이전 SQL 포함 |
| **사전 조건** | generated_sql이 있는 ConversationTurn 1개 |
| **테스트 입력** | `generate(question, conversation_history=[turn])` |
| **기대 결과** | `vanna.generate_sql`에 전달된 question에 `<history>` 블록 포함 |
| **검증 코드** | `assert "<history>" in captured_prompt` |

### TC-PE-06: SQLGenerator — history=None 시 <history> 블록 미포함
| 항목 | 내용 |
|------|------|
| **대상 FR** | FR-PE-01 |
| **목적** | history가 없을 때 <history> 블록이 프롬프트에 없어야 함 |
| **테스트 입력** | `generate(question, conversation_history=None)` |
| **기대 결과** | `<history>` 블록 미포함 |
| **검증 코드** | `assert "<history>" not in captured_prompt` |

### TC-PE-07: SQLGenerator — CoT cot_template 프롬프트 주입 (FR-PE-02)
| 항목 | 내용 |
|------|------|
| **대상 FR** | FR-PE-02 |
| **목적** | YAML cot_template가 Vanna 프롬프트에 포함되는지 확인 |
| **사전 조건** | `load_prompt` Mock → `{"cot_template": "<thinking>Step 1...</thinking>"}` |
| **테스트 입력** | `generate("테스트")` |
| **기대 결과** | Vanna에 전달된 question에 `<thinking>` 포함 |
| **검증 코드** | `assert "<thinking>" in captured_prompt` |

### TC-PE-08: SQLGenerator — date_rules 구조화 주입 (FR-PE-03)
| 항목 | 내용 |
|------|------|
| **대상 FR** | FR-PE-03 |
| **목적** | YAML date_rules가 Vanna 프롬프트에 포함되는지 확인 |
| **사전 조건** | `load_prompt` Mock → `{"date_rules": "<date_rules>금지: DATE()</date_rules>"}` |
| **테스트 입력** | `generate("지난달 실적")` |
| **기대 결과** | Vanna 프롬프트에 `<date_rules>` 포함 |
| **검증 코드** | `assert "<date_rules>" in captured_prompt` |

### TC-PE-09: _strip_thinking_block — CoT 블록 제거 후 SQL만 반환
| 항목 | 내용 |
|------|------|
| **대상 FR** | FR-PE-02 |
| **목적** | `<thinking>...</thinking>` 블록 제거 후 순수 SQL만 남기는지 확인 |
| **테스트 입력** | `"<thinking>Step 1...</thinking>\nSELECT * FROM ad_logs"` |
| **기대 결과** | `"SELECT * FROM ad_logs"` |
| **검증 코드** | `assert result == "SELECT * FROM ad_logs"` |

### TC-PE-10: _strip_thinking_block — <thinking> 없으면 원본 그대로
| 항목 | 내용 |
|------|------|
| **대상 FR** | FR-PE-02 |
| **목적** | thinking 블록 없는 SQL은 그대로 반환 |
| **테스트 입력** | `"SELECT * FROM ad_logs WHERE year='2026'"` |
| **기대 결과** | 동일한 SQL 반환 |
| **검증 코드** | `assert result == "SELECT * FROM ad_logs WHERE year='2026'"` |

### TC-PE-11: IntentClassifier — YAML 프롬프트 사용 (FR-PE-04)
| 항목 | 내용 |
|------|------|
| **대상 FR** | FR-PE-04 |
| **목적** | YAML 있을 때 YAML system 프롬프트로 API 호출 |
| **사전 조건** | `load_prompt` Mock → `{"system": "YAML 시스템 프롬프트"}` |
| **테스트 입력** | `classify("지난달 CTR 알려줘")` |
| **기대 결과** | `messages.create` system 파라미터에 "YAML 시스템 프롬프트" 사용 |
| **검증 코드** | `assert call_kwargs["system"] == "YAML 시스템 프롬프트"` |

### TC-PE-12: IntentClassifier — YAML 없을 때 코드 내 기본값 fallback
| 항목 | 내용 |
|------|------|
| **대상 FR** | FR-PE-04 |
| **목적** | `load_prompt` 빈 딕셔너리 반환 시 기존 _SYSTEM_PROMPT 사용 |
| **사전 조건** | `load_prompt` Mock → `{}` |
| **테스트 입력** | `classify("테스트")` |
| **기대 결과** | 기존 _SYSTEM_PROMPT 내용으로 API 호출 (서비스 중단 없음) |
| **검증 코드** | `assert "DATA_QUERY" in call_kwargs["system"]` |

### TC-PE-13: QuestionRefiner — YAML 프롬프트 사용 (FR-PE-04)
| 항목 | 내용 |
|------|------|
| **대상 FR** | FR-PE-04 |
| **목적** | YAML system 프롬프트로 질문 정제 API 호출 |
| **사전 조건** | `load_prompt` Mock → `{"system": "YAML 정제기 프롬프트"}` |
| **테스트 입력** | `refine("안녕하세요! 지난달 CTR 알려주세요")` |
| **기대 결과** | API 호출 system에 "YAML 정제기 프롬프트" 사용 |
| **검증 코드** | `assert "YAML 정제기" in call_kwargs["system"]` |

### TC-PE-14: AIAnalyzer — YAML instructions 사용 (FR-PE-04, FR-PE-05)
| 항목 | 내용 |
|------|------|
| **대상 FR** | FR-PE-04, FR-PE-05 |
| **목적** | YAML instructions(광고 지표 정의 포함)으로 분석 API 호출 |
| **사전 조건** | `load_prompt` Mock → `{"instructions": "<instructions>CTR=clicks/impressions</instructions>"}` |
| **테스트 입력** | `analyze(question, sql, query_results)` |
| **기대 결과** | API content[0]["text"]에 "CTR=clicks/impressions" 포함 |
| **검증 코드** | `assert "CTR=clicks/impressions" in content[0]["text"]` |

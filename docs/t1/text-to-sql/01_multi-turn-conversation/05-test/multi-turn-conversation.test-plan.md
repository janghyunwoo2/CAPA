# [Test Plan] Multi-Turn Conversation (FR-20)

| 항목 | 내용 |
|------|------|
| **Feature** | multi-turn-conversation |
| **FR ID** | FR-20 |
| **테스트 방법** | TDD — pytest 단위 테스트 |
| **참고 설계서** | `docs/t1/text-to-sql/01_multi-turn-conversation/02-design/features/multi-turn-conversation.design.md` |
| **테스트 파일** | `services/vanna-api/tests/unit/test_multi_turn_conversation.py` |

---

## 테스트 케이스

### TC-MT-01: FR-20 도메인 모델 — ConversationTurn 생성
| 항목 | 내용 |
|------|------|
| **목적** | `ConversationTurn` 모델이 필수/선택 필드를 올바르게 처리하는지 확인 |
| **사전 조건** | `domain.py`에 `ConversationTurn` 클래스 정의 |
| **테스트 입력** | `turn_number=1, question="신규 가입자 수?"` |
| **기대 결과** | 모델 생성 성공, `refined_question/generated_sql/answer` = None |
| **검증 코드** | `assert turn.turn_number == 1` |

### TC-MT-02: FR-20 도메인 모델 — PipelineContext FR-20 필드
| 항목 | 내용 |
|------|------|
| **목적** | `PipelineContext`에 `session_id`, `turn_number`, `slack_thread_ts`, `conversation_history` 필드가 추가됐는지 확인 |
| **사전 조건** | `domain.py` PipelineContext 수정 |
| **테스트 입력** | `PipelineContext(original_question="test", session_id="1711.111", turn_number=2)` |
| **기대 결과** | 필드 설정 성공, `conversation_history` 기본값 = `[]` |
| **검증 코드** | `assert ctx.session_id == "1711.111"` |

### TC-MT-03: FR-20-01 Step 0 — 이력 있을 때 조회
| 항목 | 내용 |
|------|------|
| **목적** | `session_id`로 GSI 조회 시 이전 대화 이력이 `ctx.conversation_history`에 채워지는지 확인 |
| **사전 조건** | DynamoDB Mock, Turn 1 이력 존재 |
| **테스트 입력** | `ctx.session_id = "1711.111"`, DynamoDB 반환 1건 |
| **기대 결과** | `ctx.conversation_history` 1건, `ctx.turn_number = 2` |
| **검증 코드** | `assert len(ctx.conversation_history) == 1` |

### TC-MT-04: FR-20-03 Step 0 — 첫 번째 턴 (이력 없음)
| 항목 | 내용 |
|------|------|
| **목적** | DynamoDB에 이력이 없을 때 `turn_number = 1`, `conversation_history = []` 처리 |
| **사전 조건** | DynamoDB Mock, 빈 Items 반환 |
| **테스트 입력** | `ctx.session_id = "1711.111"` |
| **기대 결과** | `ctx.turn_number = 1`, `ctx.conversation_history = []` |
| **검증 코드** | `assert ctx.turn_number == 1` |

### TC-MT-05: FR-20-08 Step 0 — session_id 없으면 건너뜀
| 항목 | 내용 |
|------|------|
| **목적** | `conversation_id` 미전달 시 Step 0이 DynamoDB 조회 없이 ctx를 그대로 반환 |
| **사전 조건** | `ctx.session_id = None` |
| **테스트 입력** | `ctx.session_id = None` |
| **기대 결과** | DynamoDB 조회 0회, `ctx.conversation_history = []` |
| **검증 코드** | `mock_table.query.assert_not_called()` |

### TC-MT-06: FR-20-01 Step 0 — DynamoDB 오류 시 graceful degradation
| 항목 | 내용 |
|------|------|
| **목적** | GSI 조회 실패(ClientError)해도 예외 없이 기존 파이프라인 진행 |
| **사전 조건** | DynamoDB Mock → ClientError 발생 |
| **테스트 입력** | `ctx.session_id = "1711.111"` |
| **기대 결과** | 예외 미발생, `ctx.conversation_history = []` |
| **검증 코드** | `assert ctx.conversation_history == []` |

### TC-MT-07: FR-20-07 Step 0 — 최근 5턴 초과 시 잘라냄
| 항목 | 내용 |
|------|------|
| **목적** | DynamoDB에 7턴이 있어도 `conversation_history`는 최근 5턴만 포함 |
| **사전 조건** | DynamoDB Mock → 7건 반환 |
| **테스트 입력** | `ctx.session_id = "1711.111"`, `CONVERSATION_MAX_TURNS=5` |
| **기대 결과** | `len(ctx.conversation_history) == 5`, `ctx.turn_number = 8` |
| **검증 코드** | `assert len(ctx.conversation_history) == 5` |

### TC-MT-08: FR-20-06 Step 11 — session_id 있을 때 멀티턴 필드 저장
| 항목 | 내용 |
|------|------|
| **목적** | `session_id` 있으면 DynamoDB PutItem에 `session_id`, `turn_number`, `answer`, `slack_thread_ts` 포함 |
| **사전 조건** | DynamoDB Mock, `ctx.session_id = "1711.111"`, `ctx.turn_number = 2`, `ctx.analysis.answer = "결과는..."` |
| **테스트 입력** | `recorder.record(ctx)` |
| **기대 결과** | `put_item` 호출 시 item에 4개 필드 포함 |
| **검증 코드** | `assert call_args["session_id"] == "1711.111"` |

### TC-MT-09: FR-20-08 Step 11 — session_id 없으면 멀티턴 필드 미저장
| 항목 | 내용 |
|------|------|
| **목적** | `session_id` 없으면 멀티턴 필드 저장 없이 기존 동작 유지 |
| **사전 조건** | `ctx.session_id = None` |
| **기대 결과** | `put_item` item에 `session_id` 키 없음 |
| **검증 코드** | `assert "session_id" not in call_args` |

### TC-MT-10: FR-20-04 QuestionRefiner — conversation_history 주입
| 항목 | 내용 |
|------|------|
| **목적** | `conversation_history` 있을 때 LLM 프롬프트에 이전 대화 맥락이 포함되는지 확인 |
| **사전 조건** | LLM Mock, Turn 1 이력 1건 |
| **테스트 입력** | `question="연령대별로", conversation_history=[Turn1]` |
| **기대 결과** | LLM에 전달된 메시지에 "이전 대화 맥락" 포함 |
| **검증 코드** | `assert "이전 대화 맥락" in prompt_sent_to_llm` |

### TC-MT-11: FR-20-08 QuestionRefiner — conversation_history 없으면 기존 동작
| 항목 | 내용 |
|------|------|
| **목적** | `conversation_history=None` 전달 시 mutable default argument 버그 없이 정상 동작 |
| **사전 조건** | LLM Mock |
| **테스트 입력** | `question="신규 가입자 수", conversation_history=None` |
| **기대 결과** | 예외 없이 정제된 질문 반환 |
| **검증 코드** | `assert result is not None` |

### TC-MT-12: FR-20-05 SQLGenerator — conversation_history 이전 SQL 주입
| 항목 | 내용 |
|------|------|
| **목적** | `conversation_history` 있을 때 이전 SQL이 Vanna 프롬프트에 포함되는지 확인 |
| **사전 조건** | Vanna Mock, Turn 1 이력 (generated_sql 포함) 1건 |
| **테스트 입력** | `question="연령대별로", conversation_history=[Turn1]` |
| **기대 결과** | Vanna에 전달된 question 문자열에 "이전 대화에서 생성된 SQL" 포함 |
| **검증 코드** | `assert "이전 대화에서 생성된 SQL" in vanna_prompt` |

### TC-MT-13: FR-20-08 SQLGenerator — conversation_history 없으면 기존 동작
| 항목 | 내용 |
|------|------|
| **목적** | `conversation_history=None` 전달 시 기존 SQL 생성 정상 동작 |
| **사전 조건** | Vanna Mock |
| **테스트 입력** | `question="신규 가입자 수", conversation_history=None` |
| **기대 결과** | 예외 없이 SQL 문자열 반환 |
| **검증 코드** | `assert result == "SELECT 1"` |

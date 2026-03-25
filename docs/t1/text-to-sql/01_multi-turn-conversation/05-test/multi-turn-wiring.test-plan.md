# [Test Plan] Multi-Turn Conversation 배선 (FR-20 Wiring)

| 항목 | 내용 |
|------|------|
| **Feature** | multi-turn-conversation (wiring) |
| **FR ID** | FR-20 |
| **테스트 방법** | TDD — pytest 단위 테스트 |
| **참고 설계서** | `docs/t1/text-to-sql/01_multi-turn-conversation/02-design/features/multi-turn-conversation.design.md` |
| **테스트 파일** | `services/vanna-api/tests/unit/test_multi_turn_wiring.py`, `services/slack-bot/tests/unit/test_multi_turn_thread.py` |

---

## 테스트 케이스

### TC-WI-01: QueryResponse.session_id 필드 존재 (api.py)
| 항목 | 내용 |
|------|------|
| **목적** | `QueryResponse`에 `session_id: Optional[str]` 필드가 추가됐는지 확인 |
| **사전 조건** | `src/models/api.py` 수정 |
| **테스트 입력** | `QueryResponse(query_id="test", ...)` 생성 |
| **기대 결과** | `session_id` 필드 존재, 기본값 None |
| **검증 코드** | `assert hasattr(QueryResponse, 'model_fields') and 'session_id' in QueryResponse.model_fields` |

### TC-WI-02: run(conversation_id=...) → ctx.session_id 설정
| 항목 | 내용 |
|------|------|
| **목적** | `QueryPipeline.run(conversation_id="thread_ts")` 호출 시 `ctx.session_id`에 값이 설정되는지 확인 |
| **사전 조건** | `query_pipeline.py` `run()` 파라미터 추가 |
| **테스트 입력** | `await pipeline.run(question="...", conversation_id="1711111.111")` |
| **기대 결과** | 반환된 ctx.session_id == "1711111.111" |
| **검증 코드** | `assert ctx.session_id == "1711111.111"` |

### TC-WI-03: MULTI_TURN_ENABLED=true → retriever 호출
| 항목 | 내용 |
|------|------|
| **목적** | `MULTI_TURN_ENABLED=true` + `session_id` 있을 때 `ConversationHistoryRetriever.retrieve()` 호출 확인 |
| **사전 조건** | `query_pipeline.py` Step 0 연결 |
| **테스트 입력** | `MULTI_TURN_ENABLED=true`, `conversation_id="1711111.111"` |
| **기대 결과** | `retriever.retrieve(ctx)` 1회 호출 |
| **검증 코드** | `mock_retriever.retrieve.assert_called_once()` |

### TC-WI-04: MULTI_TURN_ENABLED=false → retriever 미호출
| 항목 | 내용 |
|------|------|
| **목적** | Feature Flag=false이면 Step 0 건너뜀 |
| **사전 조건** | `MULTI_TURN_ENABLED=false` (기본값) |
| **테스트 입력** | `conversation_id="1711111.111"` |
| **기대 결과** | `retriever.retrieve()` 미호출 |
| **검증 코드** | `mock_retriever.retrieve.assert_not_called()` |

### TC-WI-05: run() 시 Step 2에 conversation_history 전달
| 항목 | 내용 |
|------|------|
| **목적** | `run()` 내부에서 `QuestionRefiner.refine()` 호출 시 `conversation_history` 파라미터 전달 확인 |
| **사전 조건** | `query_pipeline.py` Step 2 수정 |
| **테스트 입력** | ctx.conversation_history에 이력 1건 있는 상태에서 `run()` |
| **기대 결과** | `refine(question, conversation_history=[...])` 호출 |
| **검증 코드** | `assert 'conversation_history' in refine_call_kwargs` |

### TC-WI-06: run() 시 Step 5에 conversation_history 전달
| 항목 | 내용 |
|------|------|
| **목적** | `SQLGenerator.generate()` 호출 시 `conversation_history` 파라미터 전달 확인 |
| **사전 조건** | `query_pipeline.py` Step 5 수정 |
| **테스트 입력** | ctx.conversation_history에 이력 1건 있는 상태에서 `run()` |
| **기대 결과** | `generate(question, rag_context, conversation_history=[...])` 호출 |
| **검증 코드** | `assert 'conversation_history' in generate_call_kwargs` |

### TC-WI-07: 스레드 답글 → event["thread_ts"]를 conversation_id로 사용
| 항목 | 내용 |
|------|------|
| **목적** | Turn 2+ (스레드 답글) 시 `event["thread_ts"]`가 `conversation_id`로 vanna-api에 전달 |
| **사전 조건** | `slack-bot/app.py` 멀티턴 분기 |
| **테스트 입력** | `event = {"ts": "REPLY_TS", "thread_ts": "ROOT_TS_111", ...}` |
| **기대 결과** | `requests.post` payload의 `conversation_id == "ROOT_TS_111"` |
| **검증 코드** | `assert payload["conversation_id"] == "ROOT_TS_111"` |

### TC-WI-08: 새 채널 메시지 → event["ts"]를 conversation_id로 사용
| 항목 | 내용 |
|------|------|
| **목적** | Turn 1 (새 메시지) 시 `event["ts"]`가 `conversation_id`로 전달 (기존 BUG-03 fix 유지) |
| **사전 조건** | `event["thread_ts"]` 없음 |
| **테스트 입력** | `event = {"ts": "MSG_TS_111", ...}` (thread_ts 없음) |
| **기대 결과** | `requests.post` payload의 `conversation_id == "MSG_TS_111"` |
| **검증 코드** | `assert payload["conversation_id"] == "MSG_TS_111"` |

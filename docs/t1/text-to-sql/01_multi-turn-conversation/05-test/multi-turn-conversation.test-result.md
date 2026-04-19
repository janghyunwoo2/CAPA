# [Test Result] Multi-Turn Conversation (FR-20)

| 항목 | 내용 |
|------|------|
| **Feature** | multi-turn-conversation |
| **FR ID** | FR-20 |
| **테스트 방법** | TDD — pytest 단위 테스트 |
| **테스트 파일** | `services/vanna-api/tests/unit/test_multi_turn_conversation.py` |
| **실행일** | 2026-03-22 |
| **결과** | 18 / 18 PASS ✅ |

---

## 테스트 결과 테이블

| TC | Step | 스텝 역할 | 인풋 | 아웃풋 (실제값) | assert 단언 | 판정 | 왜 이렇게 나왔나 |
|----|------|-----------|------|----------------|-------------|------|-----------------|
| TC-MT-01 | - | ConversationTurn 모델 생성 | `turn_number=1, question="어제 전체 광고 클릭수는?"` | `turn_number=1, question=..., refined_question=None` | `assert turn.turn_number == 1` | ✅ PASS | `ConversationTurn` BaseModel 정상 생성 |
| TC-MT-01 | - | ConversationTurn 전체 필드 | `turn_number=1, generated_sql=..., answer=...` | 모든 필드 정상 설정 | `assert turn.generated_sql == "SELECT COUNT(*) FROM ad_combined_log WHERE is_click = true"` | ✅ PASS | 선택 필드 모두 정상 저장 |
| TC-MT-02 | - | PipelineContext FR-20 필드 | `session_id="1711234567.111", turn_number=2` | 필드 설정 성공, `conversation_history=[]` | `assert ctx.session_id == "1711234567.111"` | ✅ PASS | FR-20 신규 필드 추가 완료 |
| TC-MT-02 | - | PipelineContext 기본값 | `PipelineContext(original_question="테스트")` | `session_id=None, turn_number=None, slack_thread_ts=None` | `assert ctx.conversation_history == []` | ✅ PASS | 기본값 None/빈 리스트 정상 |
| TC-MT-03 | Step 0 | 이력 1건 조회 | `session_id="1711234567.111"`, DynamoDB turn_1 반환 | `conversation_history` 1건, `turn_number=2` | `assert len(ctx.conversation_history) == 1` | ✅ PASS | GSI 조회 결과를 ConversationTurn으로 매핑 성공 |
| TC-MT-04 | Step 0 | 첫 번째 턴 (이력 없음) | DynamoDB 빈 Items 반환 | `turn_number=1, conversation_history=[]` | `assert ctx.turn_number == 1` | ✅ PASS | 이력 없으면 turn_number=1 기본값 설정 |
| TC-MT-05 | Step 0 | session_id 없으면 건너뜀 | `ctx.session_id=None` | DynamoDB 조회 0회 | `mock_table.query.assert_not_called()` | ✅ PASS | 하위 호환 — session_id 없으면 early return |
| TC-MT-06 | Step 0 | DynamoDB 오류 graceful degradation | `table.query` → ClientError | 예외 없이 `conversation_history=[]` | `assert ctx.conversation_history == []` | ✅ PASS | ClientError catch 후 빈 이력으로 계속 진행 |
| TC-MT-07 | Step 0 | 최근 5턴 잘라냄 | 7건 반환, `_max_turns=5` | `conversation_history` 5건, `turn_number=8`, `history[0].turn_number=3` | `assert len(ctx.conversation_history) == 5` | ✅ PASS | `all_items[-5:]` 로 최근 5턴 슬라이스, turn_number는 전체 max+1 |
| TC-MT-08 | Step 11 | 멀티턴 필드 저장 | `session_id="1711234567.111", turn_number=2, answer="기기별..."` | put_item item에 4개 필드 포함 | `assert item["session_id"] == "1711234567.111"` | ✅ PASS | `ctx.session_id` 있을 때 session_id/turn_number/answer/slack_thread_ts 저장 |
| TC-MT-09 | Step 11 | session_id 없으면 멀티턴 미저장 | `ctx.session_id=None` | item에 멀티턴 필드 없음 | `assert "session_id" not in item` | ✅ PASS | session_id 조건부 분기 정상 동작 |
| TC-MT-08 | Step 11 | answer 500자 트림 | `answer="A"*600` | `item["answer"]` 길이 500 | `assert len(item["answer"]) == 500` | ✅ PASS | `answer_text[:500]` 슬라이스 적용 |
| TC-MT-10 | Step 2 | QuestionRefiner 이력 주입 | `conversation_history=[Turn1]`, question="기기별로 나눠줘" | LLM 메시지에 "이전 대화 맥락" 포함 | `assert "이전 대화 맥락" in prompt_text` | ✅ PASS | history 있으면 "이전 대화 맥락:" 메시지 추가 |
| TC-MT-11 | Step 2 | QuestionRefiner history=None | `conversation_history=None` | 예외 없이 "정제된 질문입니다." 반환 | `assert result is not None` | ✅ PASS | `history = conversation_history or []` 로 None 안전 처리 |
| TC-MT-11 | Step 2 | QuestionRefiner 파라미터 생략 | `refiner.refine("어제 전체 광고 클릭수는?")` | 정상 반환 | `assert result is not None` | ✅ PASS | 기본값 None, 기존 동작 유지 |
| TC-MT-12 | Step 5 | SQLGenerator 이전 SQL 주입 | `conversation_history=[Turn1(sql=...)]`, question="기기별로 나눠줘" | vanna 호출 question에 "이전 대화에서 생성된 SQL" 포함 | `assert "이전 대화에서 생성된 SQL" in prompt` | ✅ PASS | history SQL을 date_context 뒤에 prepend |
| TC-MT-13 | Step 5 | SQLGenerator history=None | `conversation_history=None` | `"SELECT COUNT(*) FROM ad_combined_log WHERE is_click = true"` 반환 | `assert result == "SELECT COUNT(*) FROM ad_combined_log WHERE is_click = true"` | ✅ PASS | sql_context="" 로 기존 SQL 생성 동작 유지 |
| TC-MT-13 | Step 5 | SQLGenerator 파라미터 생략 | `generator.generate("어제 전체 광고 클릭수는?")` | 정상 SQL 반환 | `assert result == "SELECT COUNT(*) FROM ad_combined_log WHERE is_click = true"` | ✅ PASS | 기본값 None, 기존 동작 유지 |

---

## TDD 사이클 요약

### Red Phase
- **상태**: ImportError (`ConversationTurn` 미존재)
- **원인**: `domain.py`에 `ConversationTurn` 클래스, `PipelineContext` FR-20 필드 미구현
- **FAIL 수**: 18개 중 0 수집 (collection error)

### Green Phase
- **구현 파일 5개**:
  1. `src/models/domain.py` — `ConversationTurn` 추가, `PipelineContext` FR-20 필드 추가
  2. `src/pipeline/conversation_history_retriever.py` — 신규 생성 (Step 0)
  3. `src/stores/dynamodb_history.py` — 멀티턴 필드 저장 로직 추가
  4. `src/pipeline/question_refiner.py` — 생성자 변경(api_key→llm_client), `conversation_history` 파라미터 추가
  5. `src/pipeline/sql_generator.py` — `conversation_history` 파라미터 추가, SQL context prepend
- **최종 결과**: 18 / 18 PASS (4.09s)

### pytest 실행 로그

```
============================= test session starts =============================
platform win32 -- Python 3.13.5, pytest-8.3.4
collected 18 items

tests/unit/test_multi_turn_conversation.py::TestDomainModels::test_conversation_turn_creation PASSED
tests/unit/test_multi_turn_conversation.py::TestDomainModels::test_conversation_turn_with_all_fields PASSED
tests/unit/test_multi_turn_conversation.py::TestDomainModels::test_pipeline_context_fr20_fields PASSED
tests/unit/test_multi_turn_conversation.py::TestDomainModels::test_pipeline_context_fr20_fields_default_none PASSED
tests/unit/test_multi_turn_conversation.py::TestConversationHistoryRetriever::test_retrieve_with_existing_history PASSED
tests/unit/test_multi_turn_conversation.py::TestConversationHistoryRetriever::test_retrieve_first_turn_empty_history PASSED
tests/unit/test_multi_turn_conversation.py::TestConversationHistoryRetriever::test_retrieve_skips_when_no_session_id PASSED
tests/unit/test_multi_turn_conversation.py::TestConversationHistoryRetriever::test_retrieve_graceful_on_dynamodb_error PASSED
tests/unit/test_multi_turn_conversation.py::TestConversationHistoryRetriever::test_retrieve_limits_to_max_turns PASSED
tests/unit/test_multi_turn_conversation.py::TestDynamoDBHistoryRecorderMultiTurn::test_record_saves_multi_turn_fields PASSED
tests/unit/test_multi_turn_conversation.py::TestDynamoDBHistoryRecorderMultiTurn::test_record_omits_multi_turn_fields_without_session PASSED
tests/unit/test_multi_turn_conversation.py::TestDynamoDBHistoryRecorderMultiTurn::test_record_trims_answer_to_500_chars PASSED
tests/unit/test_multi_turn_conversation.py::TestQuestionRefinerMultiTurn::test_refine_includes_history_in_prompt PASSED
tests/unit/test_multi_turn_conversation.py::TestQuestionRefinerMultiTurn::test_refine_without_history_no_error PASSED
tests/unit/test_multi_turn_conversation.py::TestQuestionRefinerMultiTurn::test_refine_without_history_param_no_error PASSED
tests/unit/test_multi_turn_conversation.py::TestSQLGeneratorMultiTurn::test_generate_includes_prev_sql_in_prompt PASSED
tests/unit/test_multi_turn_conversation.py::TestSQLGeneratorMultiTurn::test_generate_without_history_returns_sql PASSED
tests/unit/test_multi_turn_conversation.py::TestSQLGeneratorMultiTurn::test_generate_without_history_param_returns_sql PASSED

======================= 18 passed, 13 warnings in 4.09s =======================
```

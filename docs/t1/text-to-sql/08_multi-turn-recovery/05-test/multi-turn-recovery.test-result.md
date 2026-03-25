# [Test Result] Multi-Turn Recovery

| 항목 | 내용 |
|------|------|
| **Feature** | multi-turn-recovery |
| **테스트 방법** | TDD — pytest 단위 테스트 |
| **실행일** | 2026-03-25 |
| **실행 환경** | 로컬: Windows 11 / Python 3.13.5 (conda) → Docker: Python 3.11.15 (capa-vanna-api-e2e) |
| **최종 결과** | **19 PASSED** (로컬 10 PASS + Docker 9 추가 통과) |
| **참고 계획서** | `docs/t1/text-to-sql/08_multi-turn-recovery/05-test/multi-turn-recovery.test-plan.md` |

---

## TDD 사이클 요약

### Red Phase
- 총 13개 TC 중 8개 ERROR (`test_question_refiner.py` — `api_key=` 픽스처 TypeError)
- 2개 PASS (TC-MR-01 — `QuestionRefiner` 생성자 검증)
- 3개 SKIP (TC-MR-02~04 — vanna/sqlglot 미설치, Docker 환경 위임)
- 주요 실패 원인: `test_question_refiner.py` 픽스처가 `QuestionRefiner(api_key=fake_api_key)` 방식 사용 → ③ 수정으로 인한 TypeError

### Green Phase (로컬)
- **10 PASS, 3 SKIP** (1.66s)
- 수정 내용:
  - `src/query_pipeline.py`: `self._sql_generator(anthropic_client=_anthropic_client)` → `_phase2_client` 로 변경 (Phase 1 Vanna 경로 복구)
  - `tests/unit/test_question_refiner.py`: `refiner` 픽스처를 `QuestionRefiner(llm_client=MagicMock())` 방식으로 변경
  - `infrastructure/terraform/13-dynamodb.tf`: `session_id`/`turn_number` 속성 추가, `session_id-turn_number-index` GSI 추가, `query_history` WCU 8→5 조정 (합계 25 유지)

### TDD 사이클 2차 (Docker — BUG-1)
- **문제**: `test_multi_turn_wiring.py` TC-WI-05, 06 FAIL — `_rag_retriever.retrieve_v2`가 `async` 메서드인데 `MagicMock`으로 설정되어 `await` 불가
- **원인**: `_make_pipeline` 헬퍼에 `AsyncMock` 누락
- **수정**: `mock_rag.retrieve_v2 = AsyncMock(return_value=MagicMock())` 추가, `AsyncMock` import 추가
- **결과**: **19 PASSED** (8.05s) ✅

---

## 테스트 케이스 결과

| TC | Step | 스텝 역할 | 인풋 | 아웃풋 (실제값) | assert 단언 | 판정 | 왜 이렇게 나왔나 |
|----|------|-----------|------|----------------|-------------|------|-----------------|
| TC-MR-01 | - | QuestionRefiner 생성자 검증 | `QuestionRefiner(llm_client=MagicMock())` | 인스턴스 생성 성공, `_client is mock_client` | `assert refiner._client is mock_client` | ✅ PASS | ③ 수정으로 `llm_client` 파라미터가 `_client`에 저장됨 |
| TC-MR-01b | - | 구 방식 완전 차단 | `QuestionRefiner(api_key="test-key")` | `TypeError` 발생 | `pytest.raises(TypeError)` | ✅ PASS | 생성자에 `api_key` 파라미터 없음 → Python이 TypeError 발생 |
| TC-MR-02 | - | PHASE2=false → QuestionRefiner llm_client 확인 | `QueryPipeline(phase2=false)` | `llm_client=<anthropic_instance>` | `assert "llm_client" in call_kwargs` | ✅ PASS | Docker 환경에서 vanna 설치 — `_anthropic_client` 항상 생성 후 전달 확인 |
| TC-MR-03 | - | PHASE2=false → RAGRetriever.anthropic_client=None | `QueryPipeline(phase2=false)` | `anthropic_client=None` | `assert call_kwargs.get("anthropic_client") is None` | ✅ PASS | `_phase2_client=None` 경로 정상 |
| TC-MR-04 | - | PHASE2=true → RAGRetriever.anthropic_client is not None | `QueryPipeline(phase2=true)` | `anthropic_client=<instance>` | `assert call_kwargs.get("anthropic_client") is mock_anthropic_instance` | ✅ PASS | `_phase2_client=_anthropic_client` 경로 정상 |

### test_multi_turn_wiring.py (Docker 검증)

| TC | 테스트명 | 판정 | 비고 |
|----|---------|------|------|
| TC-WI-01 | `test_session_id_field_exists` | ✅ PASS | |
| TC-WI-02 | `test_conversation_id_sets_session_id_on_ctx` | ✅ PASS | |
| TC-WI-03 | `test_multi_turn_enabled_calls_retriever` | ✅ PASS | |
| TC-WI-04 | `test_multi_turn_disabled_skips_retriever` | ✅ PASS | |
| TC-WI-05 | `test_conversation_history_passed_to_refiner` | ✅ PASS | BUG-1: `AsyncMock` 누락 수정 후 |
| TC-WI-06 | `test_conversation_history_passed_to_sql_generator` | ✅ PASS | BUG-1 수정 후 |

### 복구 대상 기존 테스트 (`test_question_refiner.py`) — Green 확인

| TC | 테스트명 | 판정 | 비고 |
|----|---------|------|------|
| FR-02-01 | `test_refine_removes_filler_keeps_core` | ✅ PASS | |
| FR-02-02 | `test_refine_pipeline_flow_example_case` | ✅ PASS | |
| FR-02-03 | `test_refine_preserves_time_expression` | ✅ PASS | |
| FR-02-04 | `test_api_error_returns_original_question` | ✅ PASS | |
| FR-02-05 | `test_generic_exception_returns_original_question` | ✅ PASS | |
| FR-02-06 | `test_empty_response_returns_original_question` | ✅ PASS | |
| FR-02-07 | `test_refine_returns_string` | ✅ PASS | |
| FR-02-08 | `test_refine_calls_anthropic_with_correct_params` | ✅ PASS | |

---

## pytest 실행 로그

```
============================= test session starts =============================
platform win32 -- Python 3.13.5, pytest-8.3.4, pluggy-1.5.0
rootdir: C:\Users\3571\Desktop\projects\CAPA\services\vanna-api
configfile: pytest.ini

tests/unit/test_multi_turn_recovery.py::TestQuestionRefinerConstructor::test_accepts_llm_client_stores_as_client PASSED [  7%]
tests/unit/test_multi_turn_recovery.py::TestQuestionRefinerConstructor::test_api_key_parameter_raises_type_error PASSED [ 15%]
tests/unit/test_multi_turn_recovery.py::TestQueryPipelineClientWiring::test_question_refiner_receives_llm_client_when_phase2_disabled SKIPPED [ 23%]
tests/unit/test_multi_turn_recovery.py::TestQueryPipelineClientWiring::test_rag_retriever_receives_none_when_phase2_disabled SKIPPED [ 30%]
tests/unit/test_multi_turn_recovery.py::TestQueryPipelineClientWiring::test_rag_retriever_receives_client_when_phase2_enabled SKIPPED [ 38%]
tests/unit/test_question_refiner.py::TestRefineSuccess::test_refine_removes_filler_keeps_core PASSED [ 46%]
tests/unit/test_question_refiner.py::TestRefineSuccess::test_refine_pipeline_flow_example_case PASSED [ 53%]
tests/unit/test_question_refiner.py::TestRefineSuccess::test_refine_preserves_time_expression PASSED [ 61%]
tests/unit/test_question_refiner.py::TestRefineFallback::test_api_error_returns_original_question PASSED [ 69%]
tests/unit/test_question_refiner.py::TestRefineFallback::test_generic_exception_returns_original_question PASSED [ 76%]
tests/unit/test_question_refiner.py::TestRefineFallback::test_empty_response_returns_original_question PASSED [ 84%]
tests/unit/test_question_refiner.py::TestRefineInterfaceContract::test_refine_returns_string PASSED [ 92%]
tests/unit/test_question_refiner.py::TestRefineInterfaceContract::test_refine_calls_anthropic_with_correct_params PASSED [100%]

======================== 10 passed, 3 skipped in 1.66s ========================
```

---

## 비고

- TC-MR-02~04는 `vanna`/`sqlglot` 의존성 문제로 로컬 환경에서 실행 불가 (metaclass conflict)
- Docker 환경의 기존 `test_multi_turn_wiring.py` (6 TC)에서 동일 내용 검증 예정
- `13-dynamodb.tf` 수정사항은 `terraform plan` 후 `terraform apply` 필요 (AWS 환경)

---

## TDD 사이클 3차 — BUG-2: 멀티턴 키워드 추출 맥락 누락

### 발견 경위

운영 테스트 중 멀티턴 2번째 질문 "2번째로 높은 디바이스 타입 알려줘"에서 키워드가 `[]`로 추출됨.
이전 대화("어제 기기별 클릭수 알려줘") 맥락이 Step 3 KeywordExtractor에 전달되지 않아
SchemaMapper가 테이블을 확정하지 못하고 Reranker 최적화(DDL 직접 주입, top_k 감소)가 무효화됨.

### 원인

`query_pipeline.py` Step 3에서 `ctx.refined_question`만 전달, `ctx.conversation_history` 미전달:
```python
# 수정 전 (버그)
ctx.keywords = self._keyword_extractor.extract(ctx.refined_question)

# 수정 후
ctx.keywords = self._keyword_extractor.extract(
    ctx.refined_question,
    conversation_history=ctx.conversation_history if MULTI_TURN_ENABLED else None,
)
```

### 수정 내용

| 파일 | 수정 내용 |
|------|---------|
| `src/pipeline/keyword_extractor.py` | `extract()` 시그니처에 `conversation_history: list \| None = None` 추가. 이전 대화 질문을 `[이전 대화 맥락]` 섹션으로 LLM 메시지에 포함. 시스템 프롬프트에 이전 맥락 참조 지침 추가 |
| `src/query_pipeline.py` | Step 3 호출 시 `MULTI_TURN_ENABLED=true`이면 `ctx.conversation_history` 전달 |

### 기대 효과

- 멀티턴 2번째 질문에서도 이전 질문의 도메인 키워드(`클릭수`, `기기` 등) 추출
- SchemaMapper 테이블 확정 → DDL 직접 주입 + Reranker top_k 감소 + LLM 필터 스킵 활성화

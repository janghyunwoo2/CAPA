# [Test Plan] Multi-Turn Recovery

| 항목 | 내용 |
|------|------|
| **Feature** | multi-turn-recovery |
| **테스트 방법** | TDD — pytest 단위 테스트 |
| **참고 설계서** | `docs/t1/text-to-sql/08_multi-turn-recovery/02-design/multi-turn-recovery.design.md` |
| **작성일** | 2026-03-25 |

---

## 테스트 케이스

### TC-MR-01: QuestionRefiner — llm_client 생성자 수락 확인

| 항목 | 내용 |
|------|------|
| **목적** | question_refiner.py가 llm_client 파라미터로 생성 가능한지 확인 (⑦ 픽스처 수정 전제) |
| **사전 조건** | question_refiner.py가 `llm_client: Any` 방식으로 수정 완료 상태 |
| **테스트 입력** | `QuestionRefiner(llm_client=MagicMock())` |
| **기대 결과** | TypeError 없이 인스턴스 생성, `_client`가 전달한 mock과 동일 |
| **검증 코드** | `assert refiner._client is mock_client` |

---

### TC-MR-02: QueryPipeline PHASE2=false → QuestionRefiner에 llm_client 전달

| 항목 | 내용 |
|------|------|
| **목적** | PHASE2_RAG_ENABLED=false여도 _anthropic_client가 생성되어 QuestionRefiner에 전달되는지 확인 |
| **사전 조건** | `PHASE2_RAG_ENABLED=false` 환경 |
| **테스트 입력** | `QueryPipeline(anthropic_api_key="test", vanna_instance=mock, athena_client=mock)` |
| **기대 결과** | `QuestionRefiner(llm_client=<anthropic_instance>, ...)` 호출됨 |
| **검증 코드** | `assert "llm_client" in call_kwargs` and `assert call_kwargs["llm_client"] is mock_anthropic_instance` |

---

### TC-MR-03: QueryPipeline PHASE2=false → RAGRetriever.anthropic_client=None

| 항목 | 내용 |
|------|------|
| **목적** | PHASE2 비활성화 시 RAGRetriever에 None이 전달되어 Vanna 경로가 유지되는지 확인 |
| **사전 조건** | `PHASE2_RAG_ENABLED=false` 환경 |
| **테스트 입력** | `QueryPipeline(...)` 초기화 |
| **기대 결과** | `RAGRetriever(anthropic_client=None, ...)` 호출됨 |
| **검증 코드** | `assert call_kwargs.get("anthropic_client") is None` |

---

### TC-MR-04: QueryPipeline PHASE2=true → RAGRetriever.anthropic_client is not None

| 항목 | 내용 |
|------|------|
| **목적** | PHASE2 활성화 시 RAGRetriever에 실제 client가 전달되어 LLM 필터 동작 가능한지 확인 |
| **사전 조건** | `PHASE2_RAG_ENABLED=true` 환경 |
| **테스트 입력** | `QueryPipeline(...)` 초기화 |
| **기대 결과** | `RAGRetriever(anthropic_client=<anthropic_instance>, ...)` 호출됨 |
| **검증 코드** | `assert call_kwargs.get("anthropic_client") is mock_anthropic_instance` |

---

## 연관 테스트 (기존 — 복구 후 통과 확인)

| 파일 | TC 수 | 복구 전 상태 | 복구 후 기대 |
|------|-------|------------|------------|
| `test_question_refiner.py` | 8개 | ❌ 전부 FAIL (api_key 픽스처) | ✅ 전부 PASS |
| `test_multi_turn_conversation.py` | 18개 | 대부분 PASS | ✅ 전부 PASS |
| `test_multi_turn_wiring.py` | 6개 | PASS | ✅ 전부 PASS |

# [Analysis] Multi-Turn Recovery — Gap 분석

| 항목 | 내용 |
|------|------|
| **Feature** | multi-turn-recovery |
| **분석일** | 2026-03-25 |
| **분석자** | gap-detector |
| **Design 문서** | `docs/t1/text-to-sql/08_multi-turn-recovery/02-design/multi-turn-recovery.design.md` |
| **Match Rate** | **100%** |

---

## 분석 결과 요약

| 카테고리 | 설계 항목 수 | 일치 수 | Match Rate |
|---------|:-----------:|:-------:|:----------:|
| ⑤ `query_pipeline.py` | 6 | 6 | 100% |
| ⑥ `13-dynamodb.tf` | 11 | 11 | 100% |
| ⑦ `test_question_refiner.py` | 5 | 5 | 100% |
| **전체** | **22** | **22** | **100%** |

---

## 상세 분석

### ⑤ query_pipeline.py

Design §3.1.2 변경 후 코드 vs 실제 구현 대조:

| 설계 항목 | 설계 명세 | 구현 확인 | 판정 |
|---------|---------|---------|------|
| (B') `import anthropic` 위치 | Phase 2 조건 밖으로 이동 — 항상 import | `import anthropic as _anthropic` (Line 232, 조건 밖) | ✅ |
| (C') `_anthropic_client` 생성 위치 | Phase 2 조건 밖 — 항상 생성 | `_anthropic_client = _anthropic.Anthropic(api_key=anthropic_api_key)` (Line 233) | ✅ |
| (A') `QuestionRefiner` 호출 방식 | `llm_client=_anthropic_client` | `QuestionRefiner(llm_client=_anthropic_client, model=llm_model)` (Line 239-241) | ✅ |
| `_phase2_client` 변수 도입 | Phase 1: `None`, Phase 2: `_anthropic_client` | `_phase2_client = _anthropic_client` / `_phase2_client = None` (Line 249/252) | ✅ |
| `RAGRetriever` 호출 | `anthropic_client=_phase2_client` | `anthropic_client=_phase2_client` (Line 257) | ✅ |
| `SQLGenerator` 호출 | `anthropic_client=_phase2_client` | `anthropic_client=_phase2_client` (Line 268) | ✅ |

---

### ⑥ 13-dynamodb.tf

Design §3.2.1 추가 내용 vs 실제 구현 대조:

| 설계 항목 | 설계 명세 | 구현 확인 | 판정 |
|---------|---------|---------|------|
| `session_id` 속성 type | `"S"` | `type = "S"` | ✅ |
| `turn_number` 속성 type | `"N"` | `type = "N"` | ✅ |
| GSI 이름 | `"session_id-turn_number-index"` | `name = "session_id-turn_number-index"` | ✅ |
| GSI hash_key | `"session_id"` | `hash_key = "session_id"` | ✅ |
| GSI range_key | `"turn_number"` | `range_key = "turn_number"` | ✅ |
| GSI projection_type | `"ALL"` | `projection_type = "ALL"` | ✅ |
| GSI write_capacity | `3` | `write_capacity = 3` | ✅ |
| GSI read_capacity | `3` | `read_capacity = 3` | ✅ |
| `query_history` write_capacity | `8 → 5` (WCU 합계 25 유지) | `write_capacity = 5` | ✅ |
| `query_history` read_capacity | `8 → 5` | `read_capacity = 5` | ✅ |
| WCU 합계 | 25 (프리티어 한도) | 5+3+3+3+7+4 = **25** | ✅ |

---

### ⑦ test_question_refiner.py

Design §3.3 픽스처 변경 vs 실제 구현 대조:

| 설계 항목 | 설계 명세 | 구현 확인 | 판정 |
|---------|---------|---------|------|
| `fake_api_key` 픽스처 의존 제거 | `refiner(fake_api_key)` → `refiner()` | 파라미터 없는 `refiner()` 픽스처 | ✅ |
| `patch(anthropic.Anthropic)` 제거 | `with patch(...)` 블록 삭제 | `with patch` 블록 없음 | ✅ |
| `mock_client = MagicMock()` 생성 | mock 직접 생성 | `mock_client = MagicMock()` | ✅ |
| `QuestionRefiner(llm_client=mock_client)` | llm_client 방식으로 변경 | `QuestionRefiner(llm_client=mock_client)` | ✅ |
| `yield instance, mock_client` | mock_client 직접 반환 | `yield instance, mock_client` | ✅ |

---

## Gap 목록

**없음.** 모든 설계 항목이 구현 코드에 완전히 반영됨.

---

## 설계 외 추가 구현 (긍정적)

| 파일 | 추가 내용 | 평가 |
|------|---------|------|
| `test_multi_turn_wiring.py` | `AsyncMock` import 추가 + `mock_rag.retrieve_v2 = AsyncMock(return_value=MagicMock())` | ✅ 필수 버그 수정 (BUG-1) — `retrieve_v2`가 async 메서드임에도 `MagicMock`으로 설정되어 `await` 불가했던 문제 수정 |

---

## 종합 결론

| 항목 | 결과 |
|------|------|
| **Match Rate** | **100%** |
| **Gap** | 없음 |
| **추가 버그 수정** | BUG-1 (`test_multi_turn_wiring.py` AsyncMock 누락) |
| **terraform apply** | 완료 (`Apply complete! 0 added, 1 changed, 0 destroyed`) |
| **pytest (Docker)** | **19 PASSED** (8.05s) |
| **다음 단계** | `/pdca report multi-turn-recovery` |

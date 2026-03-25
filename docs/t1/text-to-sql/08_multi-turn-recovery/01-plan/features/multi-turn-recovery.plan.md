# [Plan] Multi-Turn Recovery (FR-20 복구)

## Executive Summary

| 항목 | 내용 |
|------|------|
| **Feature** | multi-turn-recovery |
| **FR ID** | FR-20 (기존 멀티턴 복구) |
| **작성일** | 2026-03-25 |
| **담당** | t1 |
| **참고 문서** | `docs/t1/text-to-sql/01_multi-turn-conversation/00_수정사항/multi-turn-broken-items.md` |

### Value Delivered (4관점)

| 관점 | 내용 |
|------|------|
| **Problem** | SQL 정확도 개선 작업(2026-03-23) 중 멀티턴 관련 코드 7개 파일이 파손되어 FR-20(멀티턴 대화)이 동작하지 않음 |
| **Solution** | 파손된 4개 파일 수정 완료 + 미완료 3개 항목(query_pipeline.py, Terraform GSI, 테스트 픽스처)을 안전하게 적용 |
| **Function UX Effect** | MULTI_TURN_ENABLED=true 시 Slack 스레드 기반 멀티턴 대화가 정상 동작하며, conversation_id 없을 때는 기존 Phase 1/2 파이프라인이 동일하게 동작함 |
| **Core Value** | 기존 Phase 1(단일턴), Phase 2(RAG 고도화) 기능을 손상시키지 않고 멀티턴만 선택적으로 복구함 |

---

## 1. 배경 및 목적

### 1.1 파손 경위

2026-03-23 SQL 정확도 개선 작업(YAML 프롬프트 엔지니어링, RAG 버그 수정) 중 아래 커밋들이 멀티턴 코드를 파손:

| 커밋 | 날짜 | 파손 내용 |
|------|------|----------|
| `5594276` | 2026-03-23 13:55 | `sql_generator.py` history_block 문자열 형식 변경 → 테스트 단언 불일치 |
| `c4248f7` | 2026-03-23 18:10 | `question_refiner.py` conversation_history 파라미터 추가했으나 "현재 미사용" 처리 |
| `bd3ccc1` | 2026-03-22 20:38 | FR-20 원본 구현 시 `domain.py`/`dynamodb_history.py` 일부 항목 누락 |

추가로 발견된 문제:
- `query_pipeline.py`가 변경된 `QuestionRefiner` 생성자(`api_key` → `llm_client`)를 반영하지 않아 런타임 TypeError 발생 예정
- Terraform `13-dynamodb.tf`에 `session_id-turn_number-index` GSI가 없어 Step 0 ConversationHistoryRetriever가 ClientError 발생(graceful degradation으로 빈 이력 반환)

### 1.2 복구 목표

1. **기존 기능 보존**: Phase 1(단일턴, PHASE2_RAG_ENABLED=false) 및 Phase 2(RAG 고도화) 파이프라인이 현재와 동일하게 동작
2. **멀티턴 복구**: `MULTI_TURN_ENABLED=true`이고 `conversation_id`가 있을 때 FR-20 전체 흐름이 정상 동작
3. **하위 호환**: `conversation_id` 없으면 Step 0 건너뛰고 기존 파이프라인 그대로 실행

---

## 2. 파손 항목 및 복구 현황

### 2.1 수정 완료 항목 (4개)

| # | 파일 | 파손 내용 | 수정 내용 | 상태 |
|---|------|----------|----------|------|
| ① | `src/models/domain.py` | `PipelineContext`에 `slack_thread_ts` 필드 없음 | `slack_thread_ts: Optional[str] = None` 추가 | ✅ 완료 |
| ② | `src/stores/dynamodb_history.py` | `record()`에 session_id, turn_number, answer, slack_thread_ts 저장 로직 없음 | `if ctx.session_id:` 블록으로 조건부 저장 추가 | ✅ 완료 |
| ③ | `src/pipeline/question_refiner.py` | 생성자가 `api_key` 방식, conversation_history LLM 미주입 | `llm_client: Any` 직접 주입 방식으로 변경 + 이력 주입 구현 | ✅ 완료 |
| ④ | `src/pipeline/sql_generator.py` | history_block이 `"이전 SQL N:"` 형식 → 테스트 기대 형식과 불일치 | `"이전 대화에서 생성된 SQL:\n  1. {sql}"` 형식으로 변경 | ✅ 완료 |

### 2.2 미완료 항목 (3개)

| # | 파일 | 문제 | 필요 수정 | 상태 |
|---|------|------|----------|------|
| ⑤ | `src/query_pipeline.py` | `QuestionRefiner(api_key=...)` 호출 → 변경된 생성자와 불일치 → TypeError | `_anthropic_client` 생성 후 `QuestionRefiner(llm_client=...)` 전달 | ❌ 미완료 |
| ⑥ | `infrastructure/terraform/13-dynamodb.tf` | `session_id-turn_number-index` GSI 없음 → ConversationHistoryRetriever ClientError | `session_id`/`turn_number` attribute + GSI 추가 | ❌ 미완료 |
| ⑦ | `tests/unit/test_question_refiner.py` | `QuestionRefiner(api_key=fake)` 픽스처 → ③ 수정으로 인해 실패 | `QuestionRefiner(llm_client=MagicMock())` 방식으로 변경 | ❌ 미완료 |

---

## 3. 안전성 분석 (기존 기능 영향 검증)

### 3.1 Phase 1 (PHASE2_RAG_ENABLED=false) 영향 없음 근거

| 컴포넌트 | Phase 1 동작 | 복구 후 변화 |
|---------|------------|------------|
| `RAGRetriever.retrieve()` | `self._anthropic` 미사용 | 변경 없음 |
| `SQLGenerator` | `if self._anthropic:` → False → Vanna 경로 | `anthropic_client=None` 전달 시 동일 경로 유지 |
| `QuestionRefiner` | `conversation_history=None` → 이력 없이 기존 동작 | `session_id` 없으면 history=[] → messages에 추가 없음 |
| `ConversationHistoryRetriever` | `session_id` 없으면 즉시 return → Step 0 건너뜀 | 동일 |

### 3.2 query_pipeline.py 수정 안전성 (⑤번 핵심)

```
현재 (파손):
  PHASE2_RAG_ENABLED=false → _anthropic_client = None
  → QuestionRefiner(api_key=anthropic_api_key, ...)  # api_key 방식 → TypeError 잠재

복구 후:
  항상: _anthropic_client = anthropic.Anthropic(api_key=...)
  → QuestionRefiner(llm_client=_anthropic_client, ...)   # 생성자 통일

  PHASE2_RAG_ENABLED=false:
    → RAGRetriever(anthropic_client=None)     # Phase 1 경로 유지
    → SQLGenerator(anthropic_client=None)     # Vanna 경로 유지

  PHASE2_RAG_ENABLED=true:
    → RAGRetriever(anthropic_client=_anthropic_client)  # Phase 2 유지
    → SQLGenerator(anthropic_client=_anthropic_client)  # Anthropic 경로 유지
```

**결론**: `anthropic_client`를 `QuestionRefiner`와 `RAGRetriever/SQLGenerator`에 분리하여 전달하므로 Phase 1/2 동작에 영향 없음.

### 3.3 Terraform GSI 추가 안전성 (⑥번)

- 기존 테이블(`capa-dev-query-history`)에 GSI만 추가 — 기존 데이터 유지
- 기존 GSI(`feedback-status-index`, `channel-index`) 변경 없음
- WCU 배분: 기존 합계 25 → 복구 후 합계 28 (프리티어 초과 주의)

> **WCU 프리티어 초과 대응**: 기존 `query_history` 테이블 WCU를 8→5로 줄이거나,
> `session_id-turn_number-index` WCU를 2/2로 최소화하여 합계 25 이하 유지.

---

## 4. 구현 계획

### 4.1 수정 파일 목록

| # | 파일 | 변경 내용 | 기존 기능 영향 |
|---|------|----------|--------------|
| ⑤ | `services/vanna-api/src/query_pipeline.py` | QuestionRefiner 호출 방식 변경, anthropic 클라이언트 분리 | 없음 |
| ⑥ | `infrastructure/terraform/13-dynamodb.tf` | `session_id-turn_number-index` GSI + 속성 2개 추가 | 기존 GSI/데이터 유지 |
| ⑦ | `services/vanna-api/tests/unit/test_question_refiner.py` | MagicMock 직접 주입 방식으로 픽스처 변경 | 테스트만 해당 |

### 4.2 ⑤ query_pipeline.py 수정 상세

```python
# 변경 전 (파손)
if PHASE2_RAG_ENABLED:
    import anthropic as _anthropic
    _anthropic_client = _anthropic.Anthropic(api_key=anthropic_api_key)
else:
    _anthropic_client = None

self._question_refiner = QuestionRefiner(
    api_key=anthropic_api_key, model=llm_model  # ← 구 방식
)

# 변경 후 (복구)
import anthropic as _anthropic_lib
_anthropic_client = _anthropic_lib.Anthropic(api_key=anthropic_api_key)  # 항상 생성

self._question_refiner = QuestionRefiner(
    llm_client=_anthropic_client, model=llm_model  # ← 신 방식
)

if PHASE2_RAG_ENABLED:
    from .pipeline.reranker import CrossEncoderReranker
    _reranker = CrossEncoderReranker()
    _phase2_client = _anthropic_client  # Phase 2만 전달
else:
    _reranker = None
    _phase2_client = None  # Phase 1 → None 유지

self._rag_retriever = RAGRetriever(
    vanna_instance=vanna_instance,
    reranker=_reranker,
    anthropic_client=_phase2_client,   # Phase 1: None, Phase 2: client
)
self._sql_generator = SQLGenerator(
    vanna_instance=vanna_instance,
    anthropic_client=_phase2_client,   # Phase 1: None → Vanna 경로 유지
    model=llm_model,
)
```

### 4.3 ⑥ Terraform GSI 추가 상세

```hcl
# 추가할 attribute
attribute {
  name = "session_id"
  type = "S"
}
attribute {
  name = "turn_number"
  type = "N"
}

# 추가할 GSI
global_secondary_index {
  name               = "session_id-turn_number-index"
  hash_key           = "session_id"
  range_key          = "turn_number"
  projection_type    = "ALL"
  write_capacity     = 3
  read_capacity      = 3
}
```

> **WCU 조정**: 현재 합계 25(프리티어 한도). GSI 추가(+3) 시 28이 되므로
> `query_history.write_capacity`를 8→5로 조정하여 합계 25 유지 권장.

### 4.4 ⑦ test_question_refiner.py 수정 상세

```python
# 변경 전
refiner = QuestionRefiner(api_key="fake-api-key")

# 변경 후
from unittest.mock import MagicMock
mock_client = MagicMock()
mock_client.messages.create.return_value.content[0].text = "정제된 질문"
refiner = QuestionRefiner(llm_client=mock_client)
```

---

## 5. 구현 순서

```
1. [⑤] query_pipeline.py 수정
   → QuestionRefiner 호출 방식 변경 + anthropic 클라이언트 분리
   → 기존 pytest 단위 테스트 통과 확인

2. [⑥] 13-dynamodb.tf GSI 추가
   → session_id, turn_number attribute 추가
   → session_id-turn_number-index GSI 추가
   → WCU 합계 25 유지 여부 확인 후 terraform apply

3. [⑦] test_question_refiner.py 픽스처 수정
   → MagicMock 직접 주입 방식으로 변경
   → pytest 전체 통과 확인

4. [검증] 단위 테스트 실행
   → test_multi_turn_conversation.py
   → test_multi_turn_wiring.py
   → test_question_refiner.py
```

---

## 6. 성공 기준

| 항목 | 기준 | 검증 방법 |
|------|------|---------|
| Phase 1 하위 호환 | `conversation_id` 없으면 기존과 동일 동작 | `MULTI_TURN_ENABLED=false` 상태 pytest |
| 멀티턴 정상 동작 | Step 0 → Step 2/5 이력 주입 → DynamoDB 저장 | test_multi_turn_conversation.py PASS |
| TypeError 없음 | `QuestionRefiner(api_key=...)` 호출 제거 | pytest 전체 PASS |
| DynamoDB GSI | `session_id-turn_number-index` 조회 가능 | terraform apply 성공 + AWS 콘솔 확인 |
| WCU 합계 | 25 이하 (프리티어 유지) | terraform plan WCU 합산 확인 |
| 기존 테스트 | test_multi_turn_wiring.py PASS | pytest 전체 |

---

## 7. 연관 문서

| 문서 | 경로 |
|------|------|
| 원본 파손 항목 목록 | `docs/t1/text-to-sql/01_multi-turn-conversation/00_수정사항/multi-turn-broken-items.md` |
| 멀티턴 원본 Plan | `docs/t1/text-to-sql/01_multi-turn-conversation/01-plan/features/multi-turn-conversation.plan.md` |
| 멀티턴 테스트 계획서 | `docs/t1/text-to-sql/01_multi-turn-conversation/05-test/multi-turn-conversation.test-plan.md` |
| DynamoDB Terraform | `infrastructure/terraform/13-dynamodb.tf` |
| query_pipeline | `services/vanna-api/src/query_pipeline.py` |

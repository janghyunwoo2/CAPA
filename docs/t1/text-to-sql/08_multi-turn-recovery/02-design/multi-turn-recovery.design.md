# [Design] Multi-Turn Recovery (FR-20 복구)

- **Feature**: multi-turn-recovery
- **Phase**: Design
- **작성일**: 2026-03-25
- **작성자**: t1
- **관련 Plan**: `docs/t1/text-to-sql/08_multi-turn-recovery/01-plan/features/multi-turn-recovery.plan.md`

---

## 목차

1. [개요](#1-개요)
2. [수정 대상 현황](#2-수정-대상-현황)
3. [상세 설계](#3-상세-설계)
   - 3.1 query_pipeline.py
   - 3.2 13-dynamodb.tf
   - 3.3 test_question_refiner.py
4. [안전성 검증](#4-안전성-검증)
5. [수정 순서](#5-수정-순서)

---

## 1. 개요

Plan 문서에서 정의한 미완료 3개 항목의 **코드 레벨 설계**를 기술한다.
이미 완료된 4개 항목(domain.py, dynamodb_history.py, question_refiner.py, sql_generator.py)은
현재 코드에 반영되어 있으므로 이 문서에서 다루지 않는다.

### 1.1 수정 파일 요약

| # | 파일 | 수정 유형 | 목적 |
|---|------|----------|------|
| ⑤ | `services/vanna-api/src/query_pipeline.py` | 수정 | QuestionRefiner 생성자 호출 방식 정합 |
| ⑥ | `infrastructure/terraform/13-dynamodb.tf` | 수정 | session_id-turn_number-index GSI 추가 |
| ⑦ | `services/vanna-api/tests/unit/test_question_refiner.py` | 수정 | 변경된 생성자에 맞게 픽스처 수정 |

---

## 2. 수정 대상 현황

### 2.1 query_pipeline.py — 현재 파손 상태

```python
# Line 235-237: QuestionRefiner 여전히 api_key 방식 (파손)
self._question_refiner = QuestionRefiner(
    api_key=anthropic_api_key, model=llm_model  # ← TypeError 발생 예정
)

# Line 242-250: _anthropic_client는 Phase 2에서만 생성
if PHASE2_RAG_ENABLED:
    from .pipeline.reranker import CrossEncoderReranker
    import anthropic as _anthropic
    _reranker = CrossEncoderReranker()
    _anthropic_client = _anthropic.Anthropic(api_key=anthropic_api_key)
else:
    _reranker = None
    _anthropic_client = None  # ← Phase 1에서 None이므로 QuestionRefiner에 넘길 수 없음
```

**문제**: `question_refiner.py`는 이미 `llm_client: Any` 방식으로 변경되었으나,
`query_pipeline.py`가 여전히 구 방식(`api_key=`)으로 호출 중 → `TypeError` 확정.

### 2.2 13-dynamodb.tf — GSI 누락

```hcl
# 현재: feedback-status-index, channel-index 2개만 존재
# 누락: session_id-turn_number-index
# 결과: ConversationHistoryRetriever → ClientError → graceful degradation (빈 이력)
```

### 2.3 test_question_refiner.py — 픽스처 파손

```python
# 현재 픽스처 (파손)
@pytest.fixture
def refiner(fake_api_key):
    with patch("src.pipeline.question_refiner.anthropic.Anthropic") as mock_cls:
        instance = QuestionRefiner(api_key=fake_api_key)  # ← TypeError
        yield instance, mock_cls.return_value
```

**문제**: `question_refiner.py` 내부에서 더 이상 `anthropic.Anthropic()`을 생성하지 않으므로
`patch(...anthropic.Anthropic)`이 무의미하고, `api_key=` 생성자도 TypeError.

---

## 3. 상세 설계

### 3.1 query_pipeline.py 수정

#### 3.1.1 수정 위치

`__init__` 메서드 내 컴포넌트 초기화 블록 (Line 231~268)

#### 3.1.2 변경 전 → 변경 후

```python
# ===== 변경 전 =====

# 컴포넌트 초기화
self._intent_classifier = IntentClassifier(
    api_key=anthropic_api_key, model=llm_model
)
self._question_refiner = QuestionRefiner(        # ← (A) api_key 방식
    api_key=anthropic_api_key, model=llm_model
)
self._keyword_extractor = KeywordExtractor(
    api_key=anthropic_api_key, model=llm_model
)
# Phase 2: PHASE2_RAG_ENABLED=true 시 CrossEncoderReranker + Anthropic 주입
if PHASE2_RAG_ENABLED:
    from .pipeline.reranker import CrossEncoderReranker
    import anthropic as _anthropic              # ← (B) Phase 2에서만 import
    _reranker = CrossEncoderReranker()
    _anthropic_client = _anthropic.Anthropic(api_key=anthropic_api_key)  # ← (C) Phase 2에서만 생성
else:
    _reranker = None
    _anthropic_client = None

self._rag_retriever = RAGRetriever(
    vanna_instance=vanna_instance,
    reranker=_reranker,
    anthropic_client=_anthropic_client,
)
...
self._sql_generator = SQLGenerator(
    vanna_instance=vanna_instance,
    anthropic_client=_anthropic_client,
    model=llm_model,
)
```

```python
# ===== 변경 후 =====

# Anthropic 클라이언트 생성 — QuestionRefiner(멀티턴) + Phase 2(LLM 필터/SQL 생성) 공용
import anthropic as _anthropic                  # ← (B') 항상 import
_anthropic_client = _anthropic.Anthropic(       # ← (C') 항상 생성
    api_key=anthropic_api_key
)

# 컴포넌트 초기화
self._intent_classifier = IntentClassifier(
    api_key=anthropic_api_key, model=llm_model
)
self._question_refiner = QuestionRefiner(        # ← (A') llm_client 방식
    llm_client=_anthropic_client, model=llm_model
)
self._keyword_extractor = KeywordExtractor(
    api_key=anthropic_api_key, model=llm_model
)
# Phase 2: PHASE2_RAG_ENABLED=true 시 CrossEncoderReranker 활성화
if PHASE2_RAG_ENABLED:
    from .pipeline.reranker import CrossEncoderReranker
    _reranker = CrossEncoderReranker()
    _phase2_client = _anthropic_client          # ← Phase 2: 실제 client 전달
else:
    _reranker = None
    _phase2_client = None                       # ← Phase 1: None 유지 (Vanna 경로)

self._rag_retriever = RAGRetriever(
    vanna_instance=vanna_instance,
    reranker=_reranker,
    anthropic_client=_phase2_client,            # ← Phase 1: None, Phase 2: client
)
...
self._sql_generator = SQLGenerator(
    vanna_instance=vanna_instance,
    anthropic_client=_phase2_client,            # ← Phase 1: None(Vanna 경로 유지), Phase 2: client
    model=llm_model,
)
```

#### 3.1.3 변경 요점

| 변경 항목 | 이유 |
|---------|------|
| `_anthropic_client` 생성을 Phase 2 조건 밖으로 이동 | QuestionRefiner는 Phase 1/2 무관하게 항상 client 필요 |
| `QuestionRefiner(api_key=...)` → `QuestionRefiner(llm_client=...)` | question_refiner.py 생성자 변경에 맞춤 |
| `_phase2_client` 변수 도입 | RAGRetriever/SQLGenerator는 여전히 Phase 2에서만 client 받아야 함 |

---

### 3.2 13-dynamodb.tf 수정

#### 3.2.1 추가 내용

`aws_dynamodb_table.query_history` 리소스에 아래 3개 블록 추가:

```hcl
# 1. session_id 속성 정의
attribute {
  name = "session_id"
  type = "S"
}

# 2. turn_number 속성 정의
attribute {
  name = "turn_number"
  type = "N"
}

# 3. GSI 추가
global_secondary_index {
  name               = "session_id-turn_number-index"
  hash_key           = "session_id"
  range_key          = "turn_number"
  projection_type    = "ALL"
  write_capacity     = 3
  read_capacity      = 3
}
```

#### 3.2.2 WCU/RCU 프리티어 유지 전략

DynamoDB 프리티어: 테이블 + GSI 전체 합산 **25 WCU/RCU** 이하.

| 리소스 | 현재 WCU/RCU | 변경 후 |
|--------|------------|--------|
| query_history 테이블 | 8 | **5** (조정) |
| feedback-status-index GSI | 3 | 3 |
| channel-index GSI | 3 | 3 |
| session_id-turn_number-index GSI | - | **3** (신규) |
| pending_feedbacks 테이블 | 7 | 7 |
| status-index GSI | 4 | 4 |
| **합계** | **25** | **25** ✅ |

> `query_history` 테이블 WCU/RCU를 8 → 5로 줄여 프리티어 한도 유지.
> query_history는 write가 빈번하지 않으므로 5로도 충분.

#### 3.2.3 주석 업데이트

파일 상단 WCU 설명 주석도 함께 업데이트:

```hcl
# 무료 요금 범위 (테이블 + GSI 전체 합산 25 WCU/RCU 이하):
#   query_history 테이블 5 + feedback-status-index GSI 3 + channel-index GSI 3
#   + session_id-turn_number-index GSI 3
#   + pending_feedbacks 테이블 7 + status-index GSI 4 = 합계 25 WCU/RCU
```

#### 3.2.4 IAM 권한 — 추가 불필요

기존 `aws_iam_policy.vanna_dynamodb`가 이미 포함:
```hcl
"dynamodb:Query",
"${aws_dynamodb_table.query_history.arn}/index/*",  # ← GSI 조회 권한 포함
```
신규 GSI도 `index/*` 와일드카드로 자동 커버됨.

---

### 3.3 test_question_refiner.py 수정

#### 3.3.1 픽스처 변경

```python
# ===== 변경 전 =====
@pytest.fixture
def refiner(fake_api_key):
    """QuestionRefiner 인스턴스 (API 호출은 Mock 처리)"""
    with patch("src.pipeline.question_refiner.anthropic.Anthropic") as mock_cls:
        instance = QuestionRefiner(api_key=fake_api_key)
        yield instance, mock_cls.return_value


# ===== 변경 후 =====
@pytest.fixture
def refiner():
    """QuestionRefiner 인스턴스 (llm_client MagicMock 직접 주입)"""
    mock_client = MagicMock()
    instance = QuestionRefiner(llm_client=mock_client)
    yield instance, mock_client
```

**변경 이유**:
- `question_refiner.py`가 내부에서 `anthropic.Anthropic()`을 생성하지 않으므로 `patch`가 불필요
- `MagicMock()` 직접 주입으로 단순화
- `fake_api_key` fixture 의존성 제거 (이 파일에서만 사용 안 하므로)

#### 3.3.2 test_refine_calls_anthropic_with_correct_params 수정

현재 테스트:
```python
def test_refine_calls_anthropic_with_correct_params(self, refiner):
    ...
    call_kwargs = mock_client.messages.create.call_args.kwargs
    assert call_kwargs["max_tokens"] == 200
    assert call_kwargs["messages"][0]["content"] == "테스트 질문"  # ← 주의
```

`conversation_history=None` 시 messages 구조:
```python
messages = [{"role": "user", "content": "테스트 질문"}]  # 인덱스 0이 질문 → 단언 유지
```

**결론**: `conversation_history=None`(기본값)이면 `messages[0]`이 질문 그대로이므로 **단언 변경 불필요**.

---

## 4. 안전성 검증

### 4.1 Phase 1 (PHASE2_RAG_ENABLED=false) 동작 보존

| 컴포넌트 | 기존 동작 | 복구 후 동작 | 동일 여부 |
|---------|---------|------------|---------|
| `IntentClassifier` | `api_key` 전달 | 변경 없음 | ✅ |
| `QuestionRefiner` | `api_key`(파손) → TypeError | `llm_client` 전달 → 정상 | ✅ (복구) |
| `RAGRetriever` | `anthropic_client=None` | `anthropic_client=None` 유지 | ✅ |
| `SQLGenerator` | `anthropic_client=None` → Vanna 경로 | `anthropic_client=None` 유지 | ✅ |
| `LLM 선별` | `_should_skip_llm_filter()` 로직 | 변경 없음 (Phase 2 전용) | ✅ |

### 4.2 Phase 2 (PHASE2_RAG_ENABLED=true) 동작 보존

| 컴포넌트 | 기존 동작 | 복구 후 동작 | 동일 여부 |
|---------|---------|------------|---------|
| `RAGRetriever` | `anthropic_client=client` | `anthropic_client=_phase2_client(=client)` | ✅ |
| `SQLGenerator` | `anthropic_client=client` → Anthropic 경로 | 동일 | ✅ |
| LLM 선별 조건부 스킵 | `_should_skip_llm_filter()` 그대로 | 변경 없음 | ✅ |

### 4.3 멀티턴 (MULTI_TURN_ENABLED=true + conversation_id 있음)

| 단계 | 동작 |
|------|------|
| Step 0 | DynamoDB GSI 조회 → turn_number 계산, conversation_history 반환 |
| Step 2 | `QuestionRefiner.refine(question, conversation_history)` → 맥락 주입 |
| Step 5 | `SQLGenerator` 이전 SQL 참조 |
| Step 11 | `DynamoDBHistoryRecorder.record()` → session_id, turn_number, answer 저장 |

### 4.4 멀티턴 (conversation_id 없음) — 하위 호환

| 단계 | 동작 |
|------|------|
| Step 0 | `ctx.session_id=None` → 즉시 return, 건너뜀 |
| Step 2 | `conversation_history=[]` → messages에 이력 없음 → 기존 동작 |
| Step 11 | `ctx.session_id=None` → session_id/turn_number 저장 안 함 |

---

## 5. 수정 순서

```
1. query_pipeline.py
   - _anthropic_client 생성 위치 이동 (조건 밖으로)
   - QuestionRefiner(llm_client=_anthropic_client) 으로 변경
   - _phase2_client 변수 도입

2. 13-dynamodb.tf
   - session_id / turn_number attribute 추가
   - session_id-turn_number-index GSI 추가
   - query_history WCU/RCU 8 → 5 조정
   - 주석 업데이트

3. test_question_refiner.py
   - refiner 픽스처 MagicMock 직접 주입 방식으로 변경
   - with patch(...) 블록 제거
   - fake_api_key 파라미터 제거

4. 단위 테스트 검증
   - pytest services/vanna-api/tests/unit/test_question_refiner.py
   - pytest services/vanna-api/tests/unit/test_multi_turn_conversation.py
   - pytest services/vanna-api/tests/unit/test_multi_turn_wiring.py
```

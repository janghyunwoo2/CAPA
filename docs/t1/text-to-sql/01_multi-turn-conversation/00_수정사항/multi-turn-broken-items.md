# 멀티턴 대화 (FR-20) 수정 필요 항목

> **작성일**: 2026-03-24
> **원인**: 2026-03-23 SQL 성능 개선 작업(YAML 프롬프트 엔지니어링, RAG 버그 수정) 중 멀티턴 코드 파손
> **상태**: 미수정 (수정 대기)

---

## 파손 원인 커밋

| 커밋 | 날짜 | 내용 | 멀티턴 피해 |
|------|------|------|------------|
| `5594276` | 2026-03-23 13:55 | YAML 기반 프롬프트 엔지니어링 도입 | SQLGenerator history_block 문자열 형식 변경 |
| `c4248f7` | 2026-03-23 18:10 | QuestionRefiner conversation_history 파라미터 추가 | "현재 미사용" 명시, 실제 LLM 주입 없음 |
| `bd3ccc1` | 2026-03-22 20:38 | FR-20 멀티턴 원본 구현 | domain.py/dynamodb_history.py 일부 항목 누락 |

---

## 수정 항목 목록

### ① `src/models/domain.py` — `slack_thread_ts` 필드 누락

**현재 코드 (PipelineContext)**:
```python
# Step 0: 멀티턴 (FR-20)
session_id: Optional[str] = None
turn_number: Optional[int] = None
conversation_history: list["ConversationTurn"] = Field(default_factory=list)
# ← slack_thread_ts 필드 없음
```

**필요한 수정**:
```python
# Step 0: 멀티턴 (FR-20)
session_id: Optional[str] = None
turn_number: Optional[int] = None
slack_thread_ts: Optional[str] = None          # ← 추가
conversation_history: list["ConversationTurn"] = Field(default_factory=list)
```

**깨진 테스트**: TC-MT-02 (×2)
```python
assert ctx.slack_thread_ts == "1711234567.111"
assert ctx.slack_thread_ts is None  # 기본값
```

---

### ② `src/stores/dynamodb_history.py` — 멀티턴 필드 저장 누락

**현재 코드 (`record()` 메서드)**: session_id, turn_number, answer, slack_thread_ts 저장 코드 없음

**필요한 수정** — `record()` 메서드 내 item 딕셔너리에 조건부 추가:
```python
# session_id 있을 때만 멀티턴 필드 저장
if ctx.session_id:
    answer_text = ctx.analysis.answer if ctx.analysis else None
    item["session_id"] = ctx.session_id
    item["turn_number"] = ctx.turn_number
    if answer_text:
        item["answer"] = answer_text[:500]   # 500자 트림
    if ctx.slack_thread_ts:
        item["slack_thread_ts"] = ctx.slack_thread_ts
```

**깨진 테스트**: TC-MT-08 (×3), TC-MT-09
```python
assert item["session_id"] == "1711234567.111"
assert item["turn_number"] == 2
assert item["answer"] == "기기별 클릭수 집계 결과입니다."
assert item["slack_thread_ts"] == "1711234567.111"
assert len(item["answer"]) == 500  # 500자 트림
assert "session_id" not in item    # session_id 없을 때
```

---

### ③ `src/pipeline/question_refiner.py` — 생성자 + 이력 주입 누락

**현재 코드**:
```python
# 생성자: api_key 방식 (테스트는 llm_client 직접 주입 기대)
def __init__(self, api_key: str, model: str = "claude-haiku-4-5-20251001") -> None:
    self._client = anthropic.Anthropic(api_key=api_key)
    self._model = model

# refine(): conversation_history 받지만 LLM에 전달 안 함
def refine(self, question: str, conversation_history: Optional[list] = None) -> str:
    """...현재 미사용, 시그니처 호환 용도."""
    # conversation_history 미사용
```

**필요한 수정 (생성자)**:
```python
# llm_client를 직접 받도록 변경
def __init__(self, llm_client: Any, model: str = "claude-haiku-4-5-20251001") -> None:
    self._client = llm_client
    self._model = model
```

> ⚠️ 생성자 변경 시 `query_pipeline.py`도 함께 수정 필요:
> ```python
> # 변경 전
> self._question_refiner = QuestionRefiner(api_key=anthropic_api_key, model=llm_model)
> # 변경 후
> import anthropic as _anthropic_lib
> _llm_client = _anthropic_lib.Anthropic(api_key=anthropic_api_key)
> self._question_refiner = QuestionRefiner(llm_client=_llm_client, model=llm_model)
> ```

**필요한 수정 (이력 주입)**:
```python
def refine(self, question: str, conversation_history: Optional[list] = None) -> str:
    history = conversation_history or []
    messages = []
    if history:
        history_text = "\n".join(
            f"- Q: {t.question} / A: {t.answer or '(답변 없음)'}"
            for t in history
        )
        messages.append({
            "role": "user",
            "content": f"이전 대화 맥락:\n{history_text}"
        })
        messages.append({"role": "assistant", "content": "이전 대화 맥락을 참고하겠습니다."})
    messages.append({"role": "user", "content": question})
    # ... LLM 호출
```

**깨진 테스트**: TC-MT-10 (×3)
```python
assert "이전 대화 맥락" in prompt_text   # LLM 메시지에 이전 대화 포함 여부
assert result is not None               # history=None 예외 없음
assert result is not None               # 파라미터 생략 시 기존 동작 유지
```

---

### ④ `src/pipeline/sql_generator.py` — history_block 문자열 형식 불일치

**현재 코드** (`5594276` 커밋에서 변경됨):
```python
history_block = (
    "<history>\n"
    + "\n".join(
        f"  이전 SQL {i + 1}: {sql}"   # ← "이전 SQL 1:", "이전 SQL 2:"
        for i, sql in enumerate(prev_sqls)
    )
    + "\n</history>\n"
)
```

**테스트가 기대하는 형식** (TC-MT-12 line 343):
```python
assert "이전 대화에서 생성된 SQL" in prompt  # ← 이 문자열이 없음!
```

**필요한 수정**: history_block 형식을 테스트 단언에 맞게 변경
```python
history_block = ""
if conversation_history:
    prev_sqls = [t.generated_sql for t in conversation_history if t.generated_sql]
    if prev_sqls:
        sql_list = "\n".join(f"  {i+1}. {sql}" for i, sql in enumerate(prev_sqls))
        history_block = f"이전 대화에서 생성된 SQL:\n{sql_list}\n"
```

**깨진 테스트**: TC-MT-12
```python
assert "이전 대화에서 생성된 SQL" in prompt
```

---

## 전체 예상 실패 TC 요약

| TC | 파일 | 단언 | 실패 이유 |
|----|------|------|----------|
| TC-MT-02 (×2) | `domain.py` | `ctx.slack_thread_ts` 필드 접근 | 필드 없음 |
| TC-MT-08 (×3) | `dynamodb_history.py` | `item["session_id"]` 등 | 저장 로직 없음 |
| TC-MT-09 | `dynamodb_history.py` | `"session_id" not in item` | 저장 안 해서 역설적으로 PASS 가능성 있으나, answer/turn_number도 없어서 다른 단언 FAIL |
| TC-MT-10 (×3) | `question_refiner.py` | `"이전 대화 맥락" in prompt_text` | 미주입 |
| TC-MT-12 | `sql_generator.py` | `"이전 대화에서 생성된 SQL" in prompt` | 형식 불일치 |

**예상: 18개 중 최소 6~9개 FAIL**

---

## 수정 우선순위

| 순위 | 항목 | 난이도 | 영향 범위 |
|------|------|--------|----------|
| 1 | `sql_generator.py` history_block 형식 | 낮음 | TC-MT-12 1개 |
| 2 | `domain.py` slack_thread_ts 추가 | 낮음 | TC-MT-02 2개 |
| 3 | `dynamodb_history.py` 멀티턴 필드 저장 | 중간 | TC-MT-08/09 4개 |
| 4 | `question_refiner.py` 생성자 + 이력 주입 | 높음 | TC-MT-10 3개 + query_pipeline.py 연동 |

---

## 참고 파일

- 테스트 계획서: `05-test/multi-turn-conversation.test-plan.md`
- 테스트 결과서 (원본 PASS): `05-test/multi-turn-conversation.test-result.md`
- 배선 테스트 결과서: `05-test/multi-turn-wiring.test-result.md`
- 테스트 파일: `services/vanna-api/tests/unit/test_multi_turn_conversation.py`
- 테스트 파일: `services/vanna-api/tests/unit/test_multi_turn_wiring.py`

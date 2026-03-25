# Design: SQL 정확도 튜닝

**Feature**: sql-accuracy-tuning
**작성일**: 2026-03-24
**담당자**: t1 (Text-to-SQL)
**참조 Plan**: `../01-plan/sql-accuracy-tuning.plan.md`

---

## 1. 구현 개요

Plan에서 정의한 4개 Phase를 파일별 수정 단위로 세분화한다.

```
Phase A — 프롬프트 강화 + Config 튜닝
  ├── prompts/sql_generator.yaml         (CoT 6-Step, 네거티브 규칙 추가)
  ├── src/pipeline/sql_generator.py      (temperature=0, system/user 분리)
  └── src/pipeline/keyword_extractor.py  (프롬프트 제약 + 화이트리스트 필터)

Phase B — RAG 시딩 재설계
  └── scripts/seed_chromadb.py           (패턴 기반 QA, 패러프레이징, Documentation)

Phase C — Self-Correction Loop
  ├── src/query_pipeline.py              (Step 6.5 루프 삽입)
  └── src/pipeline/sql_generator.py      (에러 피드백 재생성 메서드 추가)

Phase D — 평가 스크립트 수정 + Config 튜닝
  └── evaluation/run_evaluation.py       (Jinja2 렌더링, --limit 기본값 제거)
```

---

## 2. Phase A — 프롬프트 강화 + Config 튜닝 + 키워드 필터

### 2.0 `src/pipeline/keyword_extractor.py` 수정 (A-3)

#### 문제

`retrieve()` / `retrieve_v2()` 모두 `search_query = question + " " + keywords` 로 단순 결합.
잘못된 키워드 하나가 embedding vector를 오염시켜 엉뚱한 QA 예제 검색 → SQL 품질 저하.
Phase 2 Reranker도 동일 오염 query로 관련성 재평가 → 문제 전파.

#### 2.0.1 시스템 프롬프트 제약 강화

```python
_SYSTEM_PROMPT = """당신은 광고 도메인 키워드 추출기입니다.
사용자의 질문에서 광고 분석에 관련된 핵심 명사와 지표를 추출하세요.

[중요] 반드시 질문에 직접 언급된 단어/표현만 추출하세요.
질문에 없는 관련 지표나 컬럼명을 절대 추가하지 마세요.
예시:
  - "어제 CTR 보여줘" → ["CTR", "어제"]  ← 올바름
  - "어제 CTR 보여줘" → ["CTR", "ROAS", "cost"]  ← 잘못됨 (질문에 없는 ROAS, cost 추가)

추출 대상:
- 광고 지표: CTR, CVR, ROAS, CPA, CPC, 클릭률, 전환율 등 (질문에 언급된 것만)
- 도메인 객체: 캠페인, 광고, 광고주, 디바이스, 플랫폼 등 (질문에 언급된 것만)
- 시간 표현: 어제, 지난주, 지난달, 최근 7일 등
- 컬럼명: campaign_id, device_type 등 (질문에 언급된 것만)

JSON 배열 형식으로만 응답하세요: ["키워드1", "키워드2", ...]
키워드가 없으면 빈 배열 []을 반환하세요."""
```

#### 2.0.2 허용 키워드 화이트리스트 + 필터 함수

```python
_ALLOWED_KEYWORDS: frozenset[str] = frozenset({
    # 실제 컬럼명 (ad_combined_log + ad_combined_log_summary)
    "impression_id", "user_id", "ad_id", "campaign_id", "advertiser_id",
    "platform", "device_type", "os", "delivery_region", "store_id",
    "food_category", "ad_position", "ad_format", "keyword",
    "cost_per_impression", "cost_per_click", "is_click", "click_id",
    "is_conversion", "conversion_id", "conversion_type", "conversion_value",
    "product_id", "quantity", "attribution_window",
    "year", "month", "day", "hour",
    # 표준 지표 (영문 대문자)
    "CTR", "CVR", "ROAS", "CPA", "CPC",
    # 표준 지표 (한국어)
    "클릭률", "전환율", "노출수", "클릭수", "전환수", "노출", "클릭", "전환", "비용", "광고비",
    # 도메인 객체
    "캠페인", "광고", "광고주", "디바이스", "플랫폼", "지역", "카테고리", "시간대", "기기",
    # 컬럼 범주값
    "web", "app_ios", "app_android", "tablet_ios", "tablet_android",
    "mobile", "tablet", "desktop", "others",
    "ios", "android", "macos", "windows",
    "purchase", "signup", "download", "view_content", "add_to_cart",
    "display", "native", "video", "discount_coupon",
    "home_top_rolling", "list_top_fixed", "search_ai_recommend", "checkout_bottom",
    "1day", "7day", "30day",
    # 시간 표현
    "어제", "오늘", "이번달", "지난달", "지난주", "이번주", "최근7일",
})

def _filter_keywords(keywords: list[str]) -> list[str]:
    """추출된 키워드를 화이트리스트와 교차 검증 — 없는 컬럼명/지표 자동 제거.
    대소문자 무관 비교 (CTR, ctr, Ctr 모두 허용).
    """
    allowed_lower = {k.lower() for k in _ALLOWED_KEYWORDS}
    return [kw for kw in keywords if kw.strip().lower() in allowed_lower]
```

`extract()` 메서드 마지막에 `_filter_keywords()` 적용:
```python
keywords = _filter_keywords(keywords)
```

---

### 2.1 `prompts/sql_generator.yaml` 수정

#### 현재 구조
```yaml
date_rules: |  # <date_rules> XML 블록
cot_template: | # 4-Step CoT + 출력 규칙
```

#### 추가할 섹션

**① `cot_template` — 4-Step → 6-Step 교체**

```yaml
cot_template: |
  <thinking>
  Step 1. DDL에서 실제 존재하는 테이블과 컬럼을 먼저 확인한다.
          - 반드시 제공된 DDL에 명시된 컬럼만 사용할 것.
          - DDL에 없는 컬럼은 절대 추측하거나 생성하지 않는다.
          - 존재하지 않는 컬럼 예시: campaign_name, ad_name, advertiser_name
            (실제로는 campaign_id, ad_id, advertiser_id만 존재)
  Step 2. 질문 유형에 맞는 테이블을 선택한다.
          - 시간대별(hour) 분석 → ad_combined_log (hour 파티션 보유)
          - 일별 집계 / 전환(conversion) 데이터 → ad_combined_log_summary
          - 두 테이블 모두 필요한 경우에만 JOIN 사용
  Step 3. 날짜/기간 표현을 파티션 조건으로 변환한다.
          - 반드시 year='YYYY' AND month='MM' AND day='DD' 형식 사용
          - month, day는 반드시 2자리 zero-padded 문자열 (예: '03', '09')
  Step 4. 집계·필터·정렬 로직을 설계한다.
          - CTR = COUNT(CASE WHEN is_click = true THEN 1 END) * 1.0 / NULLIF(COUNT(*), 0)
          - CVR = COUNT(CASE WHEN is_conversion = true THEN 1 END) * 1.0 / NULLIF(COUNT(*), 0)
          - 0 나눗셈 방지: NULLIF(분모, 0) 항상 사용
  Step 5. 위 분석을 바탕으로 SQL을 작성한다.
  Step 6. 최종 검증: 사용한 모든 컬럼이 DDL에 존재하는지 재확인한다.
  </thinking>

  ⚠️ 출력 규칙:
  - SQL 쿼리만 출력할 것 (마크다운 코드블록 금지: ```sql 사용 금지)
  - 설명·주석·제목 없이 SELECT 문부터 바로 시작할 것
```

**② `negative_rules` 섹션 신규 추가**

```yaml
negative_rules: |
  <constraints>
    ❌ 절대 금지 사항:
    1. DDL에 정의되지 않은 컬럼 사용 금지
       (campaign_name, ad_name, advertiser_name, channel 등은 존재하지 않음)
    2. DATE(), TO_DATE(), CAST(... AS DATE), BETWEEN, date_format(), DATE_TRUNC() 사용 금지
    3. 파티션 컬럼(year, month, day, hour)에 함수 적용 금지
    4. SELECT * 금지 — 필요한 컬럼만 명시적으로 선택
    5. 불필요한 서브쿼리 중첩 금지 — 단일 쿼리로 해결 가능하면 단일 쿼리 사용
    6. 존재하지 않는 테이블 참조 금지 — ad_combined_log, ad_combined_log_summary 두 개만 존재
    7. 비율 계산 시 NULLIF 없이 나눗셈 금지 (ZeroDivisionError 방지)
    8. CAST(hour AS INT) 없이 hour 컬럼 숫자 비교 금지 (hour는 STRING 타입)
  </constraints>
```

**③ `table_selection_rules` 섹션 신규 추가**

```yaml
table_selection_rules: |
  <table_rules>
    테이블 선택 기준:
    - ad_combined_log: 시간대별(hour) 분석, 개별 이벤트 레벨 조회
      → 보유 파티션: year, month, day, hour
    - ad_combined_log_summary: 일별 집계, 전환(conversion) 데이터, 비용 분석
      → 보유 파티션: year, month, day
      → 전용 컬럼: conversion_id, conversion_type, conversion_value,
                   product_id, quantity, attribution_window, is_conversion
    - 두 테이블 공통 컬럼: impression_id, user_id, ad_id, campaign_id,
      advertiser_id, platform, device_type, os, delivery_region,
      is_click, cost_per_impression, cost_per_click
  </table_rules>
```

---

### 2.2 `src/pipeline/sql_generator.py` 수정

#### 2.2.1 temperature=0 설정

현재 `submit_prompt()` 호출은 Vanna 내부 기본값을 사용 (temperature 미설정).
Phase 2 RAG 활성화 시 이미 `rag_context`가 있으므로 Anthropic 클라이언트를 직접 사용할 수 있다.

**변경 방식**: `SQLGenerator`에 `anthropic_client` 선택적 주입, 있을 때 직접 API 호출.

```python
# __init__ 시그니처 변경
class SQLGenerator:
    def __init__(
        self,
        vanna_instance: Any,
        anthropic_client: Optional[Any] = None,  # 추가
        model: str = "claude-haiku-4-5-20251001", # 추가
    ) -> None:
        self._vanna = vanna_instance
        self._anthropic = anthropic_client
        self._model = model
```

#### 2.2.2 system/user 프롬프트 분리

**분리 기준**:

| system 메시지 (고정 규칙) | user 메시지 (요청별 동적) |
|--------------------------|--------------------------|
| `date_rules` | `rag_block` (DDL + Docs + SQL 예제) |
| `negative_rules` | `history_block` (대화 이력) |
| `table_selection_rules` | `cot_template` (CoT 지시 + 질문) |
| `schema` | |

**구현 방식**:

```python
# anthropic_client 주입 시 직접 호출 (system/user 분리 + temperature=0)
if self._anthropic:
    system_content = f"{schema}\n{date_rules}\n{negative_rules}\n{table_rules}"
    user_content = f"{rag_block}{history_block}{cot_template}\n질문: {question}"
    response = self._anthropic.messages.create(
        model=self._model,
        max_tokens=1024,
        temperature=0,
        system=system_content,
        messages=[{"role": "user", "content": user_content}],
    )
    sql = response.content[0].text

# 하위 호환 (anthropic_client 없는 경우 — Phase 1 Fallback)
else:
    prompt = f"{schema}\n{date_rules}\n{rag_block}{history_block}{cot_template}\n질문: {question}"
    future = executor.submit(
        self._vanna.submit_prompt,
        [{"role": "user", "content": prompt}],
    )
    sql = future.result(timeout=LLM_TIMEOUT_SECONDS)
```

#### 2.2.3 에러 피드백 재생성 메서드 추가 (Phase C 준비)

```python
def generate_with_error_feedback(
    self,
    question: str,
    failed_sql: str,
    error_message: str,
    rag_context: Optional[RAGContext] = None,
    conversation_history: Optional[list] = None,
) -> str:
    """Self-Correction용: 실패한 SQL + 에러 메시지를 LLM에 재주입하여 재생성."""
    # error_feedback 블록을 기존 generate() 흐름에 삽입
    error_block = (
        f"<error_feedback>\n"
        f"이전에 생성된 SQL: {failed_sql}\n"
        f"오류 내용: {error_message}\n"
        f"위 오류를 반드시 수정하여 올바른 SQL을 다시 작성하세요.\n"
        f"</error_feedback>\n"
    )
    return self.generate(
        question=question,
        rag_context=rag_context,
        conversation_history=conversation_history,
        error_feedback=error_block,  # generate() 내부에서 user 메시지에 삽입
    )
```

---

### 2.3 `src/query_pipeline.py` — SQLGenerator에 anthropic_client 주입

`QueryPipeline.__init__`에서 `SQLGenerator` 초기화 시 `anthropic_client` 전달:

```python
# 기존
self._sql_generator = SQLGenerator(vanna_instance=vanna_instance)

# 변경
self._sql_generator = SQLGenerator(
    vanna_instance=vanna_instance,
    anthropic_client=_anthropic_client,  # PHASE2_RAG_ENABLED=true 시 이미 생성됨
    model=llm_model,
)
```

> **주의**: `PHASE2_RAG_ENABLED=false` 시 `_anthropic_client`가 None이므로 SQLGenerator는 기존 Vanna submit_prompt 방식으로 동작 (하위 호환 유지).

---

## 3. Phase B — RAG 시딩 재설계

### 3.1 `scripts/seed_chromadb.py` 구조 변경

현재 파일에는 DDL 2개, Documentation ~15개, QA 28개가 하드코딩되어 있다.
아래 구조로 교체한다.

#### 3.1.1 Documentation 추가 항목

기존 Documentation에 **4개 섹션 추가**:

**① 테이블 선택 가이드**
```
[테이블 선택 가이드]
- 시간대별(hour) 분석 필요 시: ad_combined_log (hour 파티션 보유)
- 일별 집계 / CTR / CVR / ROAS / 전환 데이터: ad_combined_log_summary
- 두 테이블 동시 필요 시에만 JOIN 사용 (성능 주의)
```

**② 존재하지 않는 컬럼 목록**
```
[주의: 존재하지 않는 컬럼]
- campaign_name → 없음. campaign_id만 존재 (campaign_01~campaign_05)
- ad_name       → 없음. ad_id만 존재 (ad_0001~ad_1000)
- advertiser_name → 없음. advertiser_id만 존재 (advertiser_01~advertiser_30)
- channel       → 없음. platform, ad_format, ad_position으로 세분화됨
- gender        → 없음
- age           → 없음
```

**③ 컬럼 허용 범주값 목록**
```
[컬럼 범주값 (정확한 값만 WHERE 조건에 사용할 것)]
- platform:         web | app_ios | app_android | tablet_ios | tablet_android
- device_type:      mobile | tablet | desktop | others
- os:               ios | android | macos | windows
- conversion_type:  purchase | signup | download | view_content | add_to_cart
- ad_format:        display | native | video | discount_coupon
- ad_position:      home_top_rolling | list_top_fixed | search_ai_recommend | checkout_bottom
- attribution_window: 1day | 7day | 30day
- food_category:    chicken | pizza | korean | chinese | dessert (외 10개)
- campaign_id:      campaign_01 ~ campaign_05
- delivery_region:  강남구 | 서초구 | 마포구 등 서울 25개 자치구 (예: '강남구', '종로구')
```

**④ Athena SQL 방언 규칙** ← ChromaDB Documentation으로 시딩 (프롬프트 negative_rules와 별도)
```
[Athena(Presto) SQL 방언 규칙]
- TOP N 구문 미지원 → ORDER BY col DESC LIMIT N 사용
- ROWNUM 미지원 → ROW_NUMBER() OVER (...) 사용
- 문자열 비교: = 연산자 사용 (LIKE 불필요 시 = 권장)
- 파티션 컬럼(year/month/day/hour)은 STRING → 숫자 비교 불가, 문자열로만 비교
- hour 컬럼 숫자 비교 시: CAST(hour AS INT) > 12 형식 사용
- ILIKE (대소문자 무시 LIKE) 미지원 → LOWER(col) LIKE LOWER('%val%') 사용
```

**⑤ 지표 계산 공식**
```
[표준 지표 계산 공식]
- CTR  = COUNT(CASE WHEN is_click = true THEN 1 END) * 1.0 / NULLIF(COUNT(*), 0)
- CVR  = COUNT(CASE WHEN is_conversion = true THEN 1 END) * 1.0 / NULLIF(COUNT(*), 0)
- ROAS = SUM(conversion_value) / NULLIF(SUM(cost_per_click), 0)
- CPA  = SUM(cost_per_click) / NULLIF(COUNT(CASE WHEN is_conversion = true THEN 1 END), 0)
- CPC  = SUM(cost_per_click) / NULLIF(COUNT(CASE WHEN is_click = true THEN 1 END), 0)
- 노출수 = COUNT(*)
- 클릭수 = COUNT(CASE WHEN is_click = true THEN 1 END)
- 전환수 = COUNT(CASE WHEN is_conversion = true THEN 1 END)
```

---

#### 3.1.2 QA 패턴 카테고리 재설계

**설계 원칙**: 특정 날짜/값 고정 QA 제거 → SQL 패턴 카테고리별 패러프레이징 QA로 교체

총 **10개 카테고리, ~23개 QA 쌍** (현재 28개 → 과적합 QA 제거 + 패러프레이징 추가):

| # | 카테고리 | QA 수 | 핵심 SQL 패턴 | 패러프레이징 소스 |
|---|---------|-------|--------------|----------------|
| 1 | 기본 집계 | 3 | GROUP BY + COUNT/SUM | 일간 1, 3, 5번 |
| 2 | CTR 계산 | 3 | CASE WHEN is_click + NULLIF | 일간 3, 20번, 주간 8번 |
| 3 | CVR 계산 | 2 | CASE WHEN is_conversion + NULLIF | 일간 2, 15번 |
| 4 | 기간 비교 (CTE) | 3 | WITH prev AS, WITH curr AS | 일간 11번, 월간 4·8번 |
| 5 | 시간대별 분석 | 2 | ad_combined_log + GROUP BY hour | 일간 4·25번 |
| 6 | TOP N 순위 | 2 | ORDER BY + LIMIT N | 일간 3·12번 |
| 7 | 전환/ROAS 분석 | 2 | conversion_value, is_conversion | 일간 10·16번 |
| 8 | 비용 분석 | 2 | cost_per_click, SUM | 월간 11번 |
| 9 | 지역별/기기별 분석 | 2 | delivery_region / device_type GROUP BY | 일간 7·6번 |
| 10 | HAVING 필터 | 2 | GROUP BY + HAVING COUNT > N | 일간 9·13번 |

**패러프레이징 QA 예시** (카테고리 2 — CTR 계산):
```python
# 같은 SQL 패턴에 3가지 자연어 표현 매핑
qa_pairs = [
    {
        "question": "어제 캠페인별 클릭률(CTR)을 내림차순으로 보여줘",
        "sql": "SELECT campaign_id, COUNT(CASE WHEN is_click = true THEN 1 END) * 1.0 / NULLIF(COUNT(*), 0) AS ctr FROM ad_combined_log_summary WHERE year='{{ y_year }}' AND month='{{ y_month }}' AND day='{{ y_day }}' GROUP BY campaign_id ORDER BY ctr DESC"
    },
    {
        "question": "각 캠페인의 어제 CTR은?",
        "sql": "SELECT campaign_id, COUNT(CASE WHEN is_click = true THEN 1 END) * 1.0 / NULLIF(COUNT(*), 0) AS ctr FROM ad_combined_log_summary WHERE year='{{ y_year }}' AND month='{{ y_month }}' AND day='{{ y_day }}' GROUP BY campaign_id ORDER BY ctr DESC"
    },
    {
        "question": "어제 캠페인별로 노출 대비 클릭 비율을 비교해줘",
        "sql": "SELECT campaign_id, COUNT(CASE WHEN is_click = true THEN 1 END) * 1.0 / NULLIF(COUNT(*), 0) AS ctr FROM ad_combined_log_summary WHERE year='{{ y_year }}' AND month='{{ y_month }}' AND day='{{ y_day }}' GROUP BY campaign_id ORDER BY ctr DESC"
    },
]
```

> **스키마 불일치 필터링**: 05-sample-queries.md 59개 중 스키마 없는 항목 7개 제외
> - 일간 14번 (신규 캠페인 시작일), 일간 22번 / 주간 3·9번 / 월간 7·14번 (광고채널별 검색/SNS — 컬럼 없음)
> - 사용 가능: 약 52개 → 패러프레이징 소스로 활용

---

## 4. Phase C — Self-Correction Loop

### 4.1 `src/query_pipeline.py` — Step 6.5 추가

**환경변수**:
- `SELF_CORRECTION_ENABLED` (기본: `"false"`) — 기능 on/off
- `MAX_CORRECTION_ATTEMPTS` (기본: `"3"`) — 최대 재시도 횟수

**Self-Correction 조건**: `ValidationResult.is_valid = False` 이고 `error_code`가 `SQL_PARSE_ERROR` 또는 `SQL_DISALLOWED_TABLE` 인 경우에만 재시도 (보안 관련 차단 키워드는 재시도 없음).

```python
SELF_CORRECTION_ENABLED = os.getenv("SELF_CORRECTION_ENABLED", "false").lower() == "true"
MAX_CORRECTION_ATTEMPTS = int(os.getenv("MAX_CORRECTION_ATTEMPTS", "3"))

# Step 5 + Step 6 + Step 6.5 통합 흐름
async def _generate_and_validate_with_correction(
    self,
    ctx: PipelineContext,
) -> tuple[str, "ValidationResult"]:
    """SQL 생성 → 검증 → Self-Correction Loop (최대 MAX_CORRECTION_ATTEMPTS회)."""
    question = ctx.refined_question or ctx.original_question
    rag_context = ctx.rag_context
    conv_history = ctx.conversation_history if MULTI_TURN_ENABLED else None

    # 1차 생성
    sql = self._sql_generator.generate(
        question=question,
        rag_context=rag_context,
        conversation_history=conv_history,
    )
    validation = self._sql_validator.validate(sql)

    if not SELF_CORRECTION_ENABLED or validation.is_valid:
        return sql, validation

    # Self-Correction Loop
    RETRYABLE_ERRORS = {"SQL_PARSE_ERROR", "SQL_DISALLOWED_TABLE", "SQL_NO_TABLE"}
    for attempt in range(1, MAX_CORRECTION_ATTEMPTS + 1):
        error_code = getattr(validation, "error_code", "")
        if error_code not in RETRYABLE_ERRORS:
            logger.info(f"Self-Correction 불가 (error_code={error_code}) — 원래 SQL 반환")
            break

        logger.info(f"Self-Correction 시도 {attempt}/{MAX_CORRECTION_ATTEMPTS}: {validation.error_message}")
        try:
            sql = self._sql_generator.generate_with_error_feedback(
                question=question,
                failed_sql=sql,
                error_message=validation.error_message or "",
                rag_context=rag_context,
                conversation_history=conv_history,
            )
        except SQLGenerationError as e:
            logger.warning(f"Self-Correction {attempt}회 생성 실패: {e}")
            break

        validation = self._sql_validator.validate(sql)
        if validation.is_valid:
            logger.info(f"Self-Correction {attempt}회 만에 성공")
            break

    return sql, validation
```

**`query_pipeline.run()` 내 Step 5~6 교체**:

```python
# 기존 Step 5 + 6 블록 → 아래로 교체
try:
    ctx.generated_sql, ctx.validation_result = await self._generate_and_validate_with_correction(ctx)
except SQLGenerationError as e:
    ctx.error = PipelineError(failed_step=5, ...)
    return ctx

if not ctx.validation_result.is_valid:
    ctx.error = PipelineError(failed_step=6, ...)
    return ctx
```

---

## 5. Phase D — 평가 스크립트 수정

### 5.1 `evaluation/run_evaluation.py` — Jinja2 렌더링 + LIMIT 처리

#### 5.1.1 Jinja2 렌더링

`ground_truth_sql`의 `{{ y_year }}`, `{{ month }}` 등을 실행 시점 날짜로 치환.

```python
from datetime import date, timedelta
from jinja2 import Environment

def _render_ground_truth(sql: str) -> str:
    """ground_truth_sql의 Jinja2 날짜 변수를 실행 시점 날짜로 렌더링."""
    today = date.today()
    yesterday = today - timedelta(days=1)
    last_month_start = (today.replace(day=1) - timedelta(days=1)).replace(day=1)
    env = Environment()
    template = env.from_string(sql)
    return template.render(
        year=today.strftime("%Y"),
        month=today.strftime("%m"),
        day=today.strftime("%d"),
        y_year=yesterday.strftime("%Y"),
        y_month=yesterday.strftime("%m"),
        y_day=yesterday.strftime("%d"),
        lm_year=last_month_start.strftime("%Y"),
        lm_month=last_month_start.strftime("%m"),
    )
```

**적용 위치**: `EvaluationRunner.run()` 루프 내 `case` 딕셔너리 처리 시

```python
for i, case in enumerate(cases, 1):
    # ground_truth_sql Jinja2 렌더링
    raw_truth = case.get("ground_truth_sql", "")
    case = {**case, "ground_truth_sql": _render_ground_truth(raw_truth)}
    ...
```

#### 5.1.2 LIMIT 처리 — 평가 시 LIMIT 절 무시

`sql_validator.py`가 LIMIT 없는 SQL에 `LIMIT 1000`을 자동 추가하므로, EM 비교 시 양쪽 SQL에서 LIMIT 절을 제거하고 비교한다.

**적용 위치**: `spider_evaluation.py`의 `SQLNormalizer` (기존 정규화 로직 확장)

```python
import re

def _strip_limit(sql: str) -> str:
    """EM 비교용: LIMIT 절 제거 (sql_validator 자동 추가 영향 제거)."""
    return re.sub(r'\s+LIMIT\s+\d+\s*;?\s*$', '', sql.strip(), flags=re.IGNORECASE).strip()
```

> **결정 근거**: ground_truth_sql에 LIMIT을 일괄 추가하면 테스트 케이스 유지보수 부담 증가.
> 평가 스크립트에서 제거하는 방식이 더 깨끗하고 단방향 수정으로 처리 가능.

#### 5.1.3 `src/pipeline/rag_retriever.py` — Config 튜닝 (G-01 반영)

Plan D-1에서 정의한 실험 파라미터를 환경변수로 제어할 수 있도록 변경:

| 파라미터 | 환경변수 | 실험 범위 | 기본값 |
|---------|---------|---------|-------|
| `n_results_sql` | `N_RESULTS_SQL` | 10, 15, 20, 30 | 10 |
| Reranker `top_k` | `RERANKER_TOP_K` | 5, 7, 10 | 7 |

```python
# rag_retriever.py 내 설정 읽기 위치
import os
N_RESULTS_SQL = int(os.getenv("N_RESULTS_SQL", "10"))
RERANKER_TOP_K = int(os.getenv("RERANKER_TOP_K", "7"))
```

각 값 조합으로 `run_evaluation.py` 실행 후 Exec 수치를 비교해 최적값 결정.

#### 5.1.4 `--limit` 기본값 제거

```python
# 기존
parser.add_argument("--limit", type=int, default=3)  # TODO: 검증 후 제거

# 변경
parser.add_argument("--limit", type=int, default=None)  # 전체 실행
```

---

## 6. 수정 파일 목록 및 변경 요약

| 파일 | Phase | 변경 내용 | 변경 규모 |
|------|-------|----------|---------|
| `prompts/sql_generator.yaml` | A | CoT 6-Step 교체, `negative_rules` + `table_selection_rules` 추가 | +40줄 |
| `src/pipeline/sql_generator.py` | A, C | `anthropic_client` 주입, temperature=0, system/user 분리, `generate_with_error_feedback()` 추가 | +60줄 |
| `src/query_pipeline.py` | A, C | `SQLGenerator` 초기화 시 `anthropic_client` 전달, `_generate_and_validate_with_correction()` 추가 | +50줄 |
| `scripts/seed_chromadb.py` | B | Documentation 5섹션 추가, QA 28개 → 패턴 기반 23개 교체 | 전체 재작성 |
| `src/pipeline/rag_retriever.py` | D | n_results_sql / top_k 환경변수 기반 튜닝 | +15줄 |
| `evaluation/run_evaluation.py` | D | `_render_ground_truth()` 추가, `--limit` 기본값 제거 | +20줄 |
| `evaluation/spider_evaluation.py` | D | `SQLNormalizer._strip_limit()` 추가 | +10줄 |

### 성공 기준 (Plan 연동)

| 지표 | 최소 목표 | Stretch |
|------|---------|---------|
| Exec Accuracy | >= 60% (36/60) | >= 80% |
| EM Accuracy | >= 40% (24/60) | >= 60% |

---

## 7. 환경변수 추가

| 변수명 | 기본값 | 설명 |
|--------|--------|------|
| `SELF_CORRECTION_ENABLED` | `false` | Self-Correction Loop 활성화 |
| `MAX_CORRECTION_ATTEMPTS` | `3` | Self-Correction 최대 재시도 횟수 |

> 기존 `PHASE2_RAG_ENABLED`, `MULTI_TURN_ENABLED` 환경변수는 그대로 유지.

---

## 8. 구현 순서 (Day별)

| Day | 작업 | 완료 기준 |
|-----|------|---------|
| Day 1 | ① `run_evaluation.py` Jinja2 렌더링 + LIMIT strip + `--limit` 제거 → 베이스라인 측정 | evaluation_report.json 생성 |
| Day 2 | ② `sql_generator.yaml` 6-Step CoT + 네거티브 규칙 + 테이블 선택 규칙 추가 | Exec/EM 수치 측정 |
| Day 3 | ③ `sql_generator.py` temperature=0 + system/user 분리 + `anthropic_client` 연결 | 단일 케이스 수동 검증 후 전체 평가 |
| Day 4 | ④ `seed_chromadb.py` Documentation 4섹션 + 패턴 기반 QA 23개 교체 → 재시딩 | ChromaDB 재시딩 후 평가 |
| Day 5 | ⑤ Self-Correction Loop 구현 + 환경변수 설정 | SELF_CORRECTION_ENABLED=true 후 평가 |
| Day 6 | ⑥ 실패 패턴 분석 → 타겟 수정 → 최종 측정 | 최종 Exec/EM 기록 |

> **Day 1 우선**: 평가 스크립트가 정상 동작해야 이후 개선 효과 측정 가능.

---

## 9. 리스크 및 대응

| 리스크 | 대응 |
|--------|------|
| `anthropic_client`를 SQLGenerator에 직접 주입 시 `PHASE2_RAG_ENABLED=false` 환경에서 None 처리 | `if self._anthropic:` 분기로 Phase 1 하위 호환 유지 |
| `seed_chromadb.py` 전체 재작성 시 기존 ChromaDB 컬렉션과 충돌 | 시딩 전 `vanna.remove_training_data()` 또는 ChromaDB 컬렉션 초기화 후 재시딩 |
| Jinja2가 평가 환경에 설치되지 않은 경우 | `requirements-eval.txt`에 `jinja2>=3.0` 추가 |
| `spider_evaluation.py`의 LIMIT strip이 의도하지 않은 SQL 변환 | LIMIT 제거는 EM 비교 직전에만 적용, 원본 SQL은 보존 |

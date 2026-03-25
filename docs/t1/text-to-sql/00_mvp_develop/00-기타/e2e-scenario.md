# Text-to-SQL E2E 시나리오 보고서

> **작성일**: 2026-03-13
> **담당**: t1
> **Phase**: **Phase 1 (핵심 기능) 기준** — Phase 2 이후 시나리오는 Phase 1 완료 후 별도 작성
> **참고 문서**:
> - Plan: `docs/t1/text-to-sql/00_mvp_develop/01-plan/features/text-to-sql.plan.md`
> - Design: `docs/t1/text-to-sql/02-design/features/text-to-sql.design.md`

---

## 0. 전체 아키텍처 구조도

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
                         CAPA Text-to-SQL 전체 구조
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

  [마케터]
     │  "어제 캠페인별 CTR 알려줘"
     ▼
┌─────────────────────────────────────────┐
│            Slack (Socket Mode)           │
│  ┌─────────────────────────────────────┐│
│  │         slack-bot (Flask)            ││  namespace: slack-bot
│  │  - 메시지 수신                       ││
│  │  - rate limit: 5req/min/user         ││
│  │  - timeout: 310초                    ││
│  └────────────────┬────────────────────┘│
└───────────────────┼─────────────────────┘
                    │ POST /query
                    │ X-Internal-Token: ***
                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                   vanna-api (FastAPI)                    namespace: vanna │
│                                                                           │
│  POST /query ──▶  QueryPipeline (11 Steps)                               │
│                                                                           │
│  ┌──────────────────────────────────────────────────────────────────┐    │
│  │                       PipelineContext                             │    │
│  │  original_question ──▶ intent ──▶ refined_question               │    │
│  │  ──▶ keywords ──▶ rag_context ──▶ generated_sql                  │    │
│  │  ──▶ validation_result ──▶ redash_query_id ──▶ query_results     │    │
│  │  ──▶ analysis ──▶ chart_base64 ──▶ [error]                       │    │
│  └──────────────────────────────────────────────────────────────────┘    │
│                                                                           │
│  Step 1  IntentClassifier    ──▶ SQL_QUERY / GENERAL / OUT_OF_DOMAIN     │
│  Step 2  QuestionRefiner     ──▶ 정제된 질문                             │
│  Step 3  KeywordExtractor    ──▶ 도메인 키워드 ["CTR", "campaign_id"...] │
│  Step 4  RAGRetriever        ──▶ DDL + Few-shot + 비즈니스 규칙          │
│  Step 5  SQLGenerator        ──▶ SELECT ... FROM ad_combined_log_summary │
│  Step 6  SQLValidator        ──▶ AST 파싱 + EXPLAIN 실행                 │
│  Step 7  RedashQueryCreator  ──▶ redash_query_id = 42                    │
│  Step 8  RedashExecutor      ──▶ 폴링 (3초 간격, 최대 300초)             │
│  Step 9  ResultCollector     ──▶ rows 10행 + columns                     │
│  Step 10 AIAnalyzer          ──▶ 인사이트 텍스트 + chart_type            │
│  Step10.5 ChartRenderer      ──▶ PNG → Base64                            │
│  Step 11 HistoryRecorder     ──▶ query_history.jsonl 저장                │
└──────────┬──────────────────────────┬────────────────────────────────────┘
           │                          │
     ┌─────▼──────┐           ┌───────▼──────────┐
     │  ChromaDB  │           │   AWS Athena      │
     │ namespace: │           │   (EXPLAIN 검증)   │
     │ chromadb   │           │   Workgroup:      │
     │            │           │   capa-text2sql-wg│
     │ sql-ddl    │           │   스캔 제한: 1GB  │
     │ sql-docs   │           └───────┬───────────┘
     │ sql-qa     │                   │ 결과 저장
     └────────────┘           ┌───────▼───────────┐
                              │   S3 (결과 버킷)   │
                              │ capa-athena-results│
                              └───────────────────┘
           │
     ┌─────▼───────────────────────────────────────┐
     │            Redash                namespace: redash │
     │  POST /api/queries  → query_id = 42         │
     │  POST /api/queries/42/results → job polling │
     │  결과 영속화 + 전체 결과 영구 링크 제공      │
     │  (차트 시각화는 Phase 3 FR-23에서 구현)     │
     │  Public URL: https://redash.capa.internal   │
     └────────────────────────────────────────────┘
           │ QueryResponse
           ▼
  ┌─────────────────────────────────────────┐
  │   Slack Block Kit 응답                   │
  │  ✅ 어제 캠페인별 CTR 분석                │
  │  📊 [차트 이미지]                        │
  │  💡 Campaign A의 CTR이 가장 높습니다...   │
  │  🔗 Redash에서 보기: https://...         │
  │  [👍 좋아요]  [👎 별로예요]              │
  └─────────────────────────────────────────┘
           │ 피드백
           ▼
  POST /feedback → FeedbackManager
  → 👍: vanna.train() + ChromaDB sql-qa 추가
  → 👎: History DB 저장만 (학습 제외)
```

---

## 1. 정상 흐름 E2E 시나리오 (Happy Path)

### 케이스 A: 단순 SQL 질문 (Happy Path)

#### 1-1. 입력 데이터

| 항목 | 값 |
|------|---|
| **Slack 메시지** | "어제 캠페인별 CTR 알려줘" |
| **사용자** | `U0123ABCDE` (Slack User ID) |
| **채널** | `C9876FGHIJ` |

**API 요청 (slack-bot → vanna-api)**:
```json
POST http://vanna-api.vanna.svc.cluster.local:8000/query
Headers:
  X-Internal-Token: capa-internal-xxxx
  Content-Type: application/json

Body:
{
  "question": "어제 캠페인별 CTR 알려줘",
  "execute": true,
  "conversation_id": null
}
```

---

#### 1-2. Step별 처리 흐름 및 중간 데이터

**[Step 1] IntentClassifier**
```
입력: "어제 캠페인별 CTR 알려줘"
LLM 판단: SQL_QUERY (광고 데이터 조회 의도 명확)
출력: intent = "data_query"
```

**[Step 2] QuestionRefiner**
```
입력: "어제 캠페인별 CTR 알려줘"
처리: 인사말/부연설명 없음, 핵심 보존
출력: refined_question = "어제 날짜의 캠페인별 CTR(클릭률)을 보여주세요"
```

**[Step 3] KeywordExtractor**
```
입력: "어제 날짜의 캠페인별 CTR(클릭률)을 보여주세요"
출력: keywords = ["CTR", "캠페인", "campaign_id", "어제", "클릭률"]
```

**[Step 4] RAGRetriever (ChromaDB 3단계 검색)**
```
검색 키워드: ["CTR", "캠페인", "campaign_id", "어제", "클릭률"]

ChromaDB 검색 결과:
  sql-ddl:
    → "ad_combined_log_summary (Daily): impression_id, campaign_id,
       is_click, is_conversion, year, month, day ..."
  sql-documentation:
    → "CTR = COUNT(click_id) / COUNT(impression_id) × 100"
    → "어제 데이터 = ad_combined_log_summary WHERE day = 어제날짜"
    → "전환 데이터는 ad_combined_log_summary 테이블에만 존재"
  sql-qa:
    → Q: "어제 CTR 알려줘" → SQL: "SELECT ... WHERE year='2026' AND month='03' AND day='12'"

출력: rag_context = {ddl, business_rules, few_shots}
```

**[Step 5] SQLGenerator**
```
입력: refined_question + rag_context
Vanna + Claude 생성:

generated_sql =
  SELECT
    campaign_id,
    COUNT(impression_id)                   AS impressions,
    COUNT(CASE WHEN is_click THEN 1 END)   AS clicks,
    ROUND(
      COUNT(CASE WHEN is_click THEN 1 END) * 100.0
      / NULLIF(COUNT(impression_id), 0), 2
    )                                      AS ctr_pct
  FROM ad_combined_log_summary
  WHERE year = '2026'
    AND month = '03'
    AND day = '12'
  GROUP BY campaign_id
  ORDER BY ctr_pct DESC
  LIMIT 1000
```

**[Step 6] SQLValidator**
```
검증 1 - 키워드 차단:
  DROP, DELETE, INSERT, UPDATE ... 없음 ✅

검증 2 - sqlglot AST 파싱:
  statement type = SELECT ✅
  테이블 = ad_combined_log_summary ✅ (허용 목록에 있음)

검증 3 - Athena EXPLAIN:
  EXPLAIN SELECT campaign_id, ...
  → "Query plan: ..."  ✅ 문법 오류 없음
  → 예상 스캔 크기 < 1GB ✅

검증 통과: sql_validated = True
```

**[Step 7] RedashQueryCreator**
```
입력: generated_sql, data_source_id=1

POST http://redash.redash.svc.cluster.local:5000/api/queries
Body: {
  "name": "CAPA: 어제 날짜의 캠페인별 CTR [2026-03-13T10:30:00]",
  "query": "SELECT campaign_id, ...",
  "data_source_id": 1,
  "description": ""
}

출력: redash_query_id = 42
```

**[Step 8] RedashExecutor (폴링)**
```
POST /api/queries/42/results
→ job.id = "job-abc-123"

폴링 (3초 간격):
  GET /api/jobs/job-abc-123
  T+3s  → status=2 (실행중)
  T+6s  → status=2 (실행중)
  T+9s  → status=3 (완료) → query_result_id = 77
```

**[Step 9] ResultCollector**
```
GET /api/query_results/77
출력: QueryResults = {
  columns: ["campaign_id", "impressions", "clicks", "ctr_pct"],
  rows: [
    {"campaign_id": "C-001", "impressions": 15420, "clicks": 847, "ctr_pct": 5.49},
    {"campaign_id": "C-007", "impressions": 23100, "clicks": 1155, "ctr_pct": 5.00},
    {"campaign_id": "C-012", "impressions": 8900,  "clicks": 356,  "ctr_pct": 4.00},
    ...
  ],
  row_count: 18,  ← 실제 캠페인 수
  truncated: False
}
```

**[Step 10] AIAnalyzer**
```
입력: question, sql, rows (최대 10행)
PII 마스킹: user_id, ip_address 컬럼 없음 → 그대로 사용

출력: AnalysisResult = {
  answer: "어제(2026-03-12) 기준 총 18개 캠페인의 CTR을 분석했습니다.
           C-001 캠페인이 5.49%로 가장 높은 CTR을 기록했으며,
           상위 3개 캠페인이 전체 클릭의 42%를 차지합니다.
           평균 CTR은 3.21%로 업계 평균(2~3%) 대비 양호한 수준입니다.",
  chart_type: "bar"
}
```

**[Step 10.5] ChartRenderer**
```
입력: rows, columns, chart_type="bar"
matplotlib (MPLBACKEND=Agg) 렌더링:
  X축: campaign_id (상위 10개)
  Y축: ctr_pct (%)

출력: chart_base64 = "iVBORw0KGgoAAAANSUhEUgAA..." (PNG Base64)
```

**[Step 11] HistoryRecorder**
```
/data/query_history.jsonl 저장:
{
  "history_id": "hist-2026031310300001",
  "timestamp": "2026-03-13T10:30:09Z",
  "slack_user_id": "sha256(U0123ABCDE)",  ← PII 해시
  "slack_channel_id": "C9876FGHIJ",
  "original_question": "어제 캠페인별 CTR 알려줘",
  "refined_question": "어제 날짜의 캠페인별 CTR(클릭률)을 보여주세요",
  "intent": "data_query",
  "keywords": ["CTR", "캠페인", "campaign_id", "어제", "클릭률"],
  "generated_sql": "SELECT campaign_id, ...",
  "sql_validated": true,
  "row_count": 18,
  "redash_query_id": 42,
  "redash_url": "https://redash.capa.internal/queries/42",
  "feedback": null,
  "trained": false
}
```

---

#### 1-3. 최종 출력 데이터

**API 응답 (vanna-api → slack-bot)**:
```json
HTTP 200 OK
{
  "query_id": "hist-2026031310300001",
  "intent": "data_query",
  "refined_question": "어제 날짜의 캠페인별 CTR(클릭률)을 보여주세요",
  "sql": "SELECT campaign_id, COUNT(impression_id) AS impressions, ...",
  "sql_validated": true,
  "results": [
    {"campaign_id": "C-001", "impressions": 15420, "clicks": 847, "ctr_pct": 5.49},
    {"campaign_id": "C-007", "impressions": 23100, "clicks": 1155, "ctr_pct": 5.00},
    ...
  ],
  "answer": "어제(2026-03-12) 기준 총 18개 캠페인의 CTR을 분석했습니다...",
  "chart_image_base64": "iVBORw0KGgoAAAANSUhEUgAA...",
  "redash_url": "https://redash.capa.internal/queries/42",
  "redash_query_id": 42,
  "execution_path": "redash",
  "error": null,
  "elapsed_seconds": 11.3
}
```

**Slack 최종 응답 (Block Kit)**:
```
┌────────────────────────────────────────────────────┐
│ ✅ 어제 캠페인별 CTR 분석                            │
│                                                    │
│ 📊 [Bar Chart: 캠페인별 CTR% 상위 10개]             │
│                                                    │
│ 💡 어제(2026-03-12) 기준 총 18개 캠페인의 CTR을    │
│    분석했습니다. C-001 캠페인이 5.49%로 가장 높은  │
│    CTR을 기록했으며, 상위 3개 캠페인이 전체 클릭의  │
│    42%를 차지합니다. 평균 CTR은 3.21%로 업계 평균  │
│    (2~3%) 대비 양호한 수준입니다.                   │
│                                                    │
│ 🔗 Redash에서 전체 결과 보기                        │
│    https://redash.capa.internal/queries/42         │
│                                                    │
│  [👍 좋아요]     [👎 별로예요]                      │
└────────────────────────────────────────────────────┘
```

---

### 케이스 B: 피드백 루프 포함 (Happy Path + 학습)

**[👍 클릭 시]**
```
Slack Block Kit Callback → slack-bot

POST /feedback
{
  "history_id": "hist-2026031310300001",
  "feedback": "positive",
  "slack_user_id": "U0123ABCDE",
  "comment": null
}

처리:
  1. History DB: feedback = "positive", feedback_at 갱신
  2. vanna.train(
       question = "어제 날짜의 캠페인별 CTR(클릭률)을 보여주세요",
       sql = "SELECT campaign_id, ..."
     )
  3. ChromaDB sql-qa 컬렉션에 Q-A 쌍 추가
  4. trained = true 업데이트

응답: {"status": "accepted", "trained": true, "message": "학습 데이터로 등록되었습니다."}
```

**[👎 클릭 시]**
```
POST /feedback { "feedback": "negative", ... }

처리:
  1. History DB: feedback = "negative", feedback_at 갱신
  2. 학습 없음 (ChromaDB 변경 없음)
  3. trained = false 유지

응답: {"status": "accepted", "trained": false, "message": "피드백이 기록되었습니다."}
```

---

## 2. 폴백 흐름 (REDASH_ENABLED=false)

> Redash 장애 또는 ENV 설정으로 비활성화 시

```
Step 1~6: 동일 (Intent → Validate)
Step 7~8: 스킵 (RedashQueryCreator, RedashExecutor 건너뜀)
Step 9: Athena 직접 실행 (boto3)
  → client.start_query_execution(
      QueryString = generated_sql,
      WorkGroup = "capa-text2sql-wg",
      ResultConfiguration = {
        "OutputLocation": "s3://capa-athena-results/vanna-api/2026/03/13/{execution_id}.csv"
      }
    )
  → 폴링 (3초 간격, 최대 300초)
Step 10~11: 동일

응답:
{
  "redash_url": null,
  "redash_query_id": null,
  "execution_path": "athena_direct",
  ...
}

Slack: Redash 링크 없이 AI 분석 + 차트만 전달
```

---

## 3. 예외 시나리오 (Exception Scenarios)

### EX-1. 범위 외 질문 (Step 1 실패)

```
입력: "요즘 날씨 어때?"
Intent 판단: OUT_OF_DOMAIN

즉시 반환 (Step 2 이하 실행 안 함):
HTTP 422
{
  "error_code": "INTENT_OUT_OF_SCOPE",
  "message": "죄송합니다. 광고 데이터와 관련된 질문만 답변할 수 있습니다.",
  "detail": null
}

Slack: "⚠️ 죄송합니다. 광고 데이터와 관련된 질문만 답변할 수 있습니다."
elapsed_seconds: ~0.8초 (LLM 1회 호출만 발생)
```

---

### EX-2. SQL 생성 실패 (Step 5 실패)

```
입력: "지난 5년간 모든 광고주의 일별 ROAS 전체 다 보여줘"
(과도하게 넓은 범위, 구체적 조건 없음)

Step 1~4: 통과
Step 5 실패: LLM이 유효한 SQL 생성 불가 또는 타임아웃(30초)

파이프라인 중단:
HTTP 422
{
  "error_code": "SQL_GENERATION_FAILED",
  "message": "SQL 생성에 실패했습니다. 질문을 더 구체적으로 입력해 주세요.",
  "detail": null,  ← DEBUG=false
  "prompt_used": "<instructions>...</instructions>" ← FR-09 실패 투명성
}

Slack:
❌ SQL 생성 실패
질문을 더 구체적으로 입력해 주세요.
예: "지난달 광고주 A의 ROAS 보여줘"
```

---

### EX-3. SQL 검증 실패 (Step 6 실패)

**케이스 A — 위험 키워드 감지**
```
generated_sql 에 DROP TABLE 포함 (LLM hallucination)

검증 1 실패 — 키워드 차단:
HTTP 422
{
  "error_code": "SQL_VALIDATION_FAILED",
  "message": "안전하지 않은 SQL이 생성되었습니다. 다시 시도해 주세요.",
  "generated_sql": "DROP TABLE ...",  ← FR-09
  "used_prompt": "..."               ← FR-09
}
```

**케이스 B — SELECT 외 구문**
```
generated_sql = "INSERT INTO ..."

검증 2 실패 — AST 파싱:
HTTP 422 { "error_code": "SQL_NOT_SELECT", "message": "SELECT 쿼리만 허용됩니다." }
```

**케이스 C — EXPLAIN 실패 (문법 오류)**
```
generated_sql = "SELECT FROM WHERE ..."  (잘못된 문법)

검증 3 실패 — Athena EXPLAIN 오류:
HTTP 422
{
  "error_code": "SQL_VALIDATION_FAILED",
  "message": "SQL 문법 오류가 감지되었습니다.",
  "generated_sql": "SELECT FROM WHERE ...",
  "used_prompt": "..."
}
```

**케이스 D — 스캔 크기 초과 (1GB 제한)**
```
EXPLAIN 결과: estimated bytes scanned = 5GB

Athena Workgroup 정책으로 실행 차단:
HTTP 422
{
  "error_code": "SQL_VALIDATION_FAILED",
  "message": "쿼리가 허용된 데이터 스캔 크기를 초과합니다. 파티션 조건(날짜)을 추가해 주세요.",
  "generated_sql": "SELECT * FROM ad_combined_log_summary"
}
```

---

### EX-4. Redash 타임아웃 (Step 8 실패)

```
RedashExecutor 폴링 300초 초과 (Athena 실행 지연)

HTTP 504
{
  "error_code": "QUERY_TIMEOUT",
  "message": "쿼리 실행이 5분을 초과했습니다. 조회 범위를 줄여보세요.",
  "detail": "redash_job_id: job-abc-123, elapsed: 300s"
}

Slack:
⏱️ 쿼리 시간 초과 (5분 초과)
조회 기간을 줄이거나 파티션 조건을 추가해 보세요.
예: "최근 7일 → 어제 하루"로 변경
```

---

### EX-5. Redash 연결 실패 (Step 7 실패, 자동 폴백)

```
Redash API 503 응답

Step 7 실패 감지 → 자동 폴백(Athena 직접 실행)으로 전환:
  REDASH_ENABLED 플래그와 무관하게 Redash 오류 시 폴백
  Step 9: boto3 Athena 직접 실행

응답: execution_path = "athena_fallback"

Slack:
✅ 어제 캠페인별 CTR 분석 (Redash 일시 오류로 직접 실행)
[차트 + AI 분석 정상 전달]
⚠️ Redash 링크 없이 제공됩니다.
```

---

### EX-6. AIAnalyzer 실패 (Step 10 실패, Graceful Degradation)

```
LLM API 오류 또는 타임아웃 (30초)

Step 10 실패 → 원시 데이터만 반환 (파이프라인 중단 없음):
{
  "answer": null,             ← AI 분석 없음
  "chart_image_base64": null, ← 차트 없음
  "results": [...],           ← 데이터는 정상 전달
  "sql": "SELECT ...",
  "redash_url": "https://...",
  "error": {
    "failed_step": 10,
    "step_name": "AIAnalyzer",
    "error_message": "AI 분석 생성에 실패했습니다."
  }
}

Slack:
✅ 쿼리 결과 (AI 분석 불가)
[데이터 테이블: campaign_id | ctr_pct]
🔗 Redash에서 전체 결과 보기: https://...
⚠️ AI 분석을 일시적으로 제공할 수 없습니다.
```

---

### EX-7. ChromaDB 연결 불가 (Step 4 실패, Graceful Degradation)

```
ChromaDB Pod 재시작 또는 네트워크 오류

Step 4 실패 → 빈 RAG 컨텍스트로 Step 5 진행:
  RAGContext = {ddl: [], few_shots: [], business_rules: []}

Step 5: LLM 자체 지식만으로 SQL 생성 시도
  → 정확도 저하 가능성 있음
  → SQL 검증(Step 6)은 정상 동작

응답: 정상 응답 (단, SQL 정확도 감소 가능)
HealthCheck: GET /health → {"chromadb": "unhealthy"}
```

---

### EX-8. HistoryRecorder 실패 (Step 11 실패, 무시)

```
/data/query_history.jsonl 파일 쓰기 실패 (디스크 풀, 권한 오류)

Step 11 실패 → 로그만 기록, 사용자 응답에 영향 없음:
  logger.error("이력 저장 실패: {e}")

사용자: 정상 응답 수신 (이력 저장 실패는 투명하게 숨김)
운영: 로그 모니터링으로 감지
```

---

### EX-9. Rate Limit 초과

```
단일 사용자가 1분 내 6번 요청

HTTP 429
{
  "error_code": "RATE_LIMIT_EXCEEDED",
  "message": "너무 많은 요청입니다. 1분 후 다시 시도해 주세요."
}

Rate Limit 정책:
  - Slack User별: 5 req/min
  - Slack Channel별: 20 req/min
  - vanna-api 전체: 10 req/sec
  - Athena Workgroup 동시 실행: 5 쿼리
```

---

### EX-10. 인증 실패

```
X-Internal-Token 누락 또는 불일치

HTTP 403
{
  "error_code": "FORBIDDEN",
  "message": "접근이 거부되었습니다."
}

K8s NetworkPolicy: slack-bot 네임스페이스 이외의 접근 차단
→ 정책 레벨에서 이미 차단되어 API 레벨까지 도달하지 않음
```

---

## 4. 입출력 데이터 요약 (Input/Output Spec)

### 4-1. 주요 입력 데이터 유형

| 유형 | 예시 질문 | 사용 테이블 |
|------|---------|-----------|
| 일간 집계 | "어제 캠페인별 CTR", "이번달 일별 광고비" | `ad_combined_log_summary` |
| 시간별 조회 | "오늘 오전 광고 노출 현황" | `ad_combined_log` |
| 전환 분석 | "지난주 ROAS TOP 5 캠페인" | `ad_combined_log_summary` |
| 디바이스별 | "모바일 vs 데스크톱 클릭 비교" | `ad_combined_log_summary` |
| 식품 카테고리 | "음식 카테고리별 전환율" | `ad_combined_log_summary` |
| 비용 분석 | "최근 7일 CPC 추이" | `ad_combined_log_summary` |

### 4-2. Athena 테이블 스키마 요약

```
ad_combined_log (Hourly 파티션: year/month/day/hour)
  impression_id, user_id, ad_id, campaign_id, advertiser_id
  platform (web/app_ios/app_android/tablet_ios/tablet_android)
  device_type (mobile/tablet/desktop/others)
  food_category, ad_position, ad_format (display/native/video/discount_coupon)
  cost_per_impression, cost_per_click
  is_click (BOOLEAN), click_id (NULL=클릭없음)
  ※ Conversion 데이터 없음

ad_combined_log_summary (Daily 파티션: year/month/day)
  → ad_combined_log 모든 컬럼 포함
  conversion_id, conversion_type (purchase/signup/download/view_content/add_to_cart)
  conversion_value (매출액), is_conversion (BOOLEAN)
  ※ Conversion은 이 테이블에만 존재
```

### 4-3. 주요 출력 데이터 형태

| 출력 항목 | 타입 | 설명 |
|---------|------|------|
| `sql` | string | 실제 실행된 SELECT 쿼리 |
| `results` | list[dict] | 최대 10행 (보안: SEC-16) |
| `answer` | string | AI 생성 인사이트 (한국어) |
| `chart_image_base64` | string | matplotlib PNG (bar/line, 단일 숫자 등 적합하지 않을 경우 None) |
| `redash_url` | string | 전체 결과 영구 링크 |
| `elapsed_seconds` | float | 총 처리 시간 |

---

## 5. 타임라인 (처리 시간 분석)

```
정상 경로 예상 소요 시간:

Step 1  IntentClassifier      ~0.5초  (LLM 호출)
Step 2  QuestionRefiner       ~0.5초  (LLM 호출)
Step 3  KeywordExtractor      ~0.3초  (LLM 호출)
Step 4  RAGRetriever          ~0.5초  (ChromaDB 벡터 검색, 제한 10초)
Step 5  SQLGenerator          ~2.0초  (Vanna + Claude LLM 호출, 제한 30초)
Step 6  SQLValidator          ~2.0초  (sqlglot + Athena EXPLAIN)
Step 7  RedashQueryCreator    ~0.5초  (Redash API POST)
Step 8  RedashExecutor        ~5.0초  (Athena 실행 + 폴링, 최대 300초)
Step 9  ResultCollector       ~0.3초  (Redash GET)
Step 10 AIAnalyzer            ~1.5초  (LLM 호출, 제한 30초)
Step 10.5 ChartRenderer       ~0.5초  (matplotlib 렌더링)
Step 11 HistoryRecorder       ~0.1초  (파일 쓰기)
─────────────────────────────────────────
전체 (정상 경로)            ~13~15초

SLA 목표 (NFR-01):  P95 < 30초
SLA 한계 (NFR-01):  최대 300초 (Athena 폴링 포함)
Slack Bot timeout:  310초 이상 설정 필수 (NFR-06)
```

---

## 6. 보안 체크리스트 (배포 전 필수)

| 우선순위 | 항목 | 상태 |
|---------|------|------|
| P0 | SQL Allowlist 검증 (validate_sql) | 구현 필요 |
| P0 | Athena Workgroup 스캔 1GB 제한 (Terraform) | 구현 필요 |
| P1 | Secrets Manager 이관 (API Key, Token) | 구현 필요 |
| P1 | Internal Service Token + K8s NetworkPolicy | 구현 필요 |
| P1 | 에러 메시지 추상화 (str(e) 직접 노출 금지) | 구현 필요 |
| P1 | 프롬프트 시스템/데이터 영역 분리 (SEC-09) | 구현 필요 |
| P2 | 응답 PII 마스킹 (user_id, ip_address) | 다음 스프린트 |
| P2 | 차트 PII 마스킹 (축 라벨) | 다음 스프린트 |
| P2 | Rate Limiting 미들웨어 | 다음 스프린트 |
| P3 | Lake Formation 열 수준 제어 | 백로그 |

---

*이 문서는 Plan/Design 문서 기반으로 작성된 E2E 시나리오 참조용 보고서입니다.*
*실제 구현 시 동작과 차이가 있을 수 있으며, 구현 완료 후 갭 분석으로 보완합니다.*

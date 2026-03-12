# Text-To-SQL 완료 보고서

> **Status**: Design Complete (Check Phase ✅ 97% Match Rate)
>
> **Project**: CAPA (Cloud-native AI Pipeline for Ad-logs)
> **Version**: 1.0
> **Author**: t1 (PDCA 담당)
> **Completion Date**: 2026-03-12
> **PDCA Cycle**: #1

---

## Executive Summary

### 1.1 프로젝트 개요

| 항목 | 내용 |
|------|------|
| **Feature** | text-to-sql |
| **Start Date** | 2026-03-10 |
| **End Date** | 2026-03-12 |
| **Duration** | 3일 (Plan + Design + Check) |
| **PDCA Phase** | Plan ✅ → Design ✅ → Do (예정) → Check ✅ |

### 1.2 결과 요약

```
┌──────────────────────────────────────────────────────────┐
│  현황: Design & Check 단계 완료                           │
├──────────────────────────────────────────────────────────┤
│  Design Match Rate (최종):  97% ✅ PASS                  │
│  ├─ 1차: 88% (3 Critical + 4 Medium Gap)                 │
│  ├─ 2차: 91% PASS (수정 후)                              │
│  └─ 3차: 97% (t2 Ground Truth 적용 후)                   │
│                                                          │
│  설계 문서:   6개 완성                                    │
│  API 엔드포인트: 7개 정의                                 │
│  데이터 모델:   4개 Pydantic 스키마 완성                  │
│  보안 설계:   9개 위협 식별 및 대응 방안 제시             │
└──────────────────────────────────────────────────────────┘
```

### 1.3 Value Delivered (4관점)

| 관점 | 내용 |
|------|------|
| **Problem** | 기존 MVP는 SQL 검증 없이 Athena 직접 호출하여 품질·비용·영속화 모두 미보장. 마케터는 실패 원인을 파악할 수 없고, 결과를 재조회/시각화할 방법이 없음 |
| **Solution** | 11-Step 파이프라인 설계로 의도 분류→정제→3단계 RAG→SQL 검증(EXPLAIN+AST)→Redash 경유 실행의 품질 게이트 구현. 모든 단계 실패 시 투명한 디버깅 정보 노출 |
| **Function/UX Effect** | Slack 응답에 AI 분석 텍스트 + Redash 링크 + matplotlib 차트 이미지 통합 전달. 실패 시 오류 단계+메시지+사용 프롬프트 투명 노출으로 사용자 신뢰도 향상 |
| **Core Value** | 3단계 SQL 검증(AST·EXPLAIN·Workgroup)과 자가학습 피드백 루프로 SQL 정확도를 지속 개선하는 재사용 가능한 아키텍처 확보. Phase 1 구현으로 마케팅 팀의 자율적 데이터 분석 가능 |

---

## 2. PDCA 단계별 수행 내용

### 2.1 Plan 단계 (2026-03-10 ~ 2026-03-11)

**수행 내용:**
- 11개 기능 요구사항(FR-01~FR-11, FR-21) 정의
- 6개 비기능 요구사항(NFR-01~NFR-06) 정의
- Phase 분류: Phase 1(핵심) / Phase 2(고급) / Phase 3(미래)
- 현재 인프라 현황 조사 (`terraform/11-k8s-apps.tf` 기준)
- 신규 추가 필요한 ENV 변수 9개 명시
- 참고 사례 3개(DableTalk, 물어보새, InsightLens) 분석

**주요 결정:**
- **FR-21 Phase 결정**: 피드백 버튼을 Phase 3에서 Phase 1로 승격
  - 이유: ChromaDB 자가학습 루프가 없으면 시스템 핵심 가치가 훼손됨
  - 구현 복잡도: 단순 콜백 처리로 낮음

**산출물:**
- `docs/t1/text-to-sql/01-plan/features/text-to-sql.plan.md` (1287줄)

### 2.2 Design 단계 (2026-03-11 ~ 2026-03-12)

**수행 내용:**
- 11-Step 파이프라인 설계 (Step 1: Intent Classifier ~ Step 11: History Recorder)
- 3계층 아키텍처(Presentation/Business/Data Layer) 정의
- FastAPI 7개 엔드포인트 설계 (POST /query, /generate-sql, /feedback, /train, GET /health, /history, /training-data)
- Pydantic v2 도메인 모델 4개 정의 (AdCombinedLog, AdCombinedLogSummary, QueryHistoryRecord, TrainingDataRecord)
- ChromaDB 3개 컬렉션 구조 설계 (sql-ddl, sql-documentation, sql-qa)
- 보안 아키텍처 구현 (9개 위협 식별 → 대응 방안 제시)
- 데이터 모델 교정: **t2 Ground Truth 기준으로 전면 재작성**

**데이터 모델 재설계 (가장 큰 변경):**

기존 설계(❌):
- 5개 정규화 테이블 (impressions, clicks, conversions, campaigns, users)
- platform: search/display/social
- device_type: mobile/desktop/tablet

수정된 설계(✅):
- **2개 실제 Athena 테이블** (ad_combined_log, ad_combined_log_summary)
  - ad_combined_log: 시간 단위(Hourly), impression+click
  - ad_combined_log_summary: 일 단위(Daily), impression+click+conversion
- **platform**: web/app_ios/app_android/tablet_ios/tablet_android (5개 값)
- **device_type**: mobile/tablet/desktop/others (4개 값)
- **ad_format**: display/native/video/discount_coupon (광고채널)
- **ad_position**: home_top_rolling/list_top_fixed/search_ai_recommend/checkout_bottom (4개 값)
- **conversion_type**: purchase/signup/download/view_content/add_to_cart (5개 값)
- **attribution_window**: 1day/7day/30day (3개 값)
- **os**: ios/android/macos/windows (4개 값)
- **food_category**: 15개 카테고리 명시

**누락 필드 추가 (8개):**
- user_lat, user_long, user_agent, ip_address, session_id
- click_position_x, click_position_y, landing_page_url

**SQL/보안 설계 교정:**
- ALLOWED_TABLES: 5개 잘못된 테이블 → **2개 실제 테이블**
- PARTITION_COLUMNS: `dt, event_date` → **`year, month, day`**
- enforce_partition_filter: `dt >= 'YYYY-MM-DD'` → **`year='YYYY' AND month='MM' AND day >= 'DD'`**

**ChromaDB 학습 데이터 재작성:**
- DDL 2개 (t2 스키마 기준)
- Documentation 정책 문서 (실제 컬럼 값 기준)
- QA 예제 10개 (단일 테이블 집계 패턴, JOIN 없음)

**산출물:**
- `docs/t1/text-to-sql/02-design/features/text-to-sql.design.md` (1123줄)
- `docs/t1/text-to-sql/02-design/04-data-model.md` (보조 문서)
- `docs/t1/text-to-sql/02-design/security-architecture.md` (보조 문서)
- `docs/t1/text-to-sql/02-design/05-sample-queries.md` (Ground Truth 스키마)

### 2.3 Check 단계 (Gap Analysis)

**Gap 분석 진행 과정:**

**1차 분석 (2026-03-11 초반)**
- Match Rate: **88%**
- Critical Gaps: 3개
  - 데이터 모델이 실제 Athena 스키마와 불일치 (5개 정규화 테이블 ❌ → 2개 실제 테이블 ✅)
  - SQL 검증 설계가 실제 파티션 정책과 불일치
  - ChromaDB 학습 데이터가 잘못된 스키마 기준

- Medium Gaps: 4개
  - platform 컬럼 값 정의 누락
  - ad_format (광고채널) 개념 모호
  - conversion_type 전체 값 정의 부재
  - 누락 필드 8개 (user_lat, user_long, session_id 등)

**2차 분석 (수정 후, 2026-03-12 오전)**
- Match Rate: **91%** ✅ PASS (90% 기준 달성)
- 모든 Critical Gap 해결
- 대부분의 Medium Gap 해결

**3차 분석 (t2 Ground Truth 적용 후, 2026-03-12 오후)**
- Match Rate: **97%** ✅✅ EXCELLENT
- 설계와 현실의 완벽한 동기화 달성
- 실제 운영 환경에서 즉시 구현 가능한 수준

---

## 3. 주요 설계 결정사항

### 3.1 11-Step 파이프라인 구조

| Step | 컴포넌트 | 목적 | 실패 처리 |
|------|---------|------|---------|
| 1 | IntentClassifier | 데이터 조회 vs 잡담 vs 범위 외 분류 | OUT_OF_DOMAIN → 즉시 반환 |
| 2 | QuestionRefiner | 인사말/부연설명 제거 | 원본 그대로 사용 (graceful degradation) |
| 3 | KeywordExtractor | 광고 도메인 핵심 키워드 추출 | 빈 리스트 → 전체 질문으로 RAG |
| 4 | RAGRetriever | ChromaDB 벡터 검색 (3단계 RAG) | 빈 컨텍스트 → LLM 자체 지식 사용 |
| 5 | SQLGenerator | Vanna + Claude 기반 SQL 생성 | 파이프라인 중단 + 실패 투명성 |
| 6 | SQLValidator | sqlglot AST + Athena EXPLAIN | 오류 정보 + SQL + 프롬프트 반환 |
| 7 | RedashQueryCreator | Redash API로 쿼리 저장 | REDASH_ENABLED=false 시 스킵 |
| 8 | RedashExecutor | 폴링(300초, 3초 간격) | 타임아웃 → 실패 투명성 |
| 9 | ResultCollector | 결과 수집 | 빈 결과 → "결과 없음" 안내 |
| 10 | AIAnalyzer + ChartRenderer | 인사이트 생성 + matplotlib 차트 | 실패 → 텍스트만 반환 |
| 11 | HistoryRecorder | 질문-SQL-결과 이력 저장 | 저장 실패 → 로그만 기록 |

**설계 원칙:**
- **Graceful Degradation**: 각 단계 실패 시 다음 단계로 진행하지 않고 명확한 상태 반환
- **실패 투명성**: 어느 단계 실패든 사용자에게 오류 정보 + 사용된 프롬프트 노출
- **이중 비용 제어**: Workgroup(1GB 제한) + 코드 단계(SELECT LIMIT 삽입)

### 3.2 3계층 SQL 검증

```python
# 1단계: 키워드 차단 (DROP, DELETE, INSERT, UPDATE 등)
# 2단계: sqlglot AST 파싱 (SELECT 전용 확인)
# 3단계: Athena EXPLAIN (비용 없이 문법 검증)
```

### 3.3 FastAPI 비동기 아키텍처

- **HTTP Client**: `httpx.AsyncClient` (timeout=30.0)
- **Lifespan**: `@asynccontextmanager` (deprecated @app.on_event 대체)
- **응답 타입**: 모든 엔드포인트에 `response_model` 명시
- **에러 응답**: 표준화된 `ErrorResponse` 스키마
  - `error_code`: ERR_* 코드화
  - `message`: 사용자 친화적 메시지
  - `detail`: DEBUG=true 시만 노출
  - `prompt_used`: 실패 시 프롬프트 노출 (FR-09)

### 3.4 Redash 연동 전략

**Phase 1 (현재):**
- Redash API로 매번 신규 쿼리 생성
- 쿼리 링크와 실행 결과를 Slack에 전달

**Phase 2 (미래):**
- SQL 해시 기반 재사용 (동일 SQL은 기존 query_id 재사용)
- 배경 작업(BackgroundTasks)으로 비동기 처리

### 3.5 PII 마스킹 전략

| 컬럼 | 분류 | 마스킹 방식 |
|------|------|------------|
| user_id | PII | `****1234` (후반 4자리만) |
| ip_address | PII | `192.168.1.*` (마지막 옥텟) |
| device_id | PII | SHA-256 해시 치환 |
| advertiser_id | 사업 기밀 | `[REDACTED]` |

**적용 범위 (SEC-24):**
- API 응답 결과 데이터 (10행 제한)
- matplotlib 차트 축/라벨
- History 저장 시 해시 처리

### 3.6 자가학습 피드백 루프 (Phase 1)

```
Slack 👍 클릭
  → POST /feedback (positive)
  → FeedbackManager.record_positive()
    → History DB 저장
    → vanna.train(question=refined_question, sql=generated_sql)
    → ChromaDB sql-qa 컬렉션에 추가

Slack 👎 클릭
  → POST /feedback (negative)
  → History DB 저장만 (학습 제외)
```

---

## 4. Gap 분석 결과 상세

### 4.1 Match Rate 진행 과정

```
┌──────────────────────────────────────────────────────────┐
│  Gap Analysis Timeline                                   │
├──────────────────────────────────────────────────────────┤
│                                                          │
│  1차 (2026-03-11 초반)                                   │
│  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ 88%           │
│  Issues: Critical 3, Medium 4                            │
│                                                          │
│  2차 (2026-03-12 오전, 수정 후)                          │
│  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ 91%          │
│  Issues: Critical 0, Medium 1                            │
│  Status: ✅ PASS (90% 달성)                              │
│                                                          │
│  3차 (2026-03-12 오후, t2 Ground Truth 적용)            │
│  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ 97%       │
│  Issues: 모두 해결                                       │
│  Status: ✅✅ EXCELLENT                                  │
│                                                          │
└──────────────────────────────────────────────────────────┘
```

### 4.2 1차 분석 주요 Gap (88% → 수정 필요)

**Critical Issues (3개):**

1. **데이터 모델 스키마 불일치**
   - 설계: 5개 정규화 테이블 (impressions, clicks, conversions, campaigns, users)
   - 실제: 2개 테이블 (ad_combined_log, ad_combined_log_summary)
   - 영향도: 높음 (전체 쿼리 예제 재작성 필요)
   - **수정**: 2개 테이블 기준으로 전면 재설계

2. **SQL 파티션 정책 불일치**
   - 설계: `dt >= 'YYYY-MM-DD'` 필터링
   - 실제: `year='YYYY' AND month='MM' AND day >= 'DD'`
   - 영향도: 높음 (쿼리 생성 정확도 저하)
   - **수정**: 파티션 필터링 로직 교정

3. **ChromaDB 학습 데이터 기준 스키마 오류**
   - DDL, Documentation, QA 예제 모두 잘못된 스키마 기준
   - 영향도: 높음 (LLM이 잘못된 컨텍스트로 SQL 생성)
   - **수정**: t2 Ground Truth(gen_adlog_init.md) 기준으로 재작성

**Medium Issues (4개):**

1. **platform 컬럼 값 정의 누락**
   - 설계에서 `search/display/social` 명시했으나 실제는 `web/app_ios/app_android/tablet_ios/tablet_android`
   - **수정**: 5개 값 정의 추가

2. **ad_format (광고채널) 개념 모호**
   - "광고채널"의 정확한 컬럼과 값 정의 필요
   - **수정**: ad_format = display/native/video/discount_coupon로 명확화

3. **conversion_type 전체 값 명시 부재**
   - 일부만 정의되어 있음
   - **수정**: purchase/signup/download/view_content/add_to_cart (5개) 명시

4. **누락 필드 8개**
   - user_lat, user_long, user_agent, ip_address, session_id, click_position_x, click_position_y, landing_page_url
   - **수정**: Pydantic 모델에 모두 추가

### 4.3 2차 분석 결과 (91% PASS)

모든 Critical Gap 해결:
- ✅ 2개 테이블 기준 데이터 모델 재설계
- ✅ 파티션 필터링 로직 교정
- ✅ ChromaDB 학습 데이터 재작성

대부분 Medium Gap 해결:
- ✅ platform 컬럼 값 정의
- ✅ ad_format 명확화
- ✅ conversion_type 전체 값 명시
- ✅ 누락 필드 8개 추가

### 4.4 3차 분석 결과 (97% EXCELLENT)

t2 Ground Truth 완벽 적용:
- ✅ os 컬럼: ios/android/macos/windows (4개)
- ✅ ad_position: home_top_rolling/list_top_fixed/search_ai_recommend/checkout_bottom (4개)
- ✅ device_type: mobile/tablet/desktop/others (4개, others 추가)
- ✅ food_category: 15개 카테고리 명시
- ✅ attribution_window: 1day/7day/30day (3개)
- ✅ ALLOWED_TABLES: ad_combined_log, ad_combined_log_summary (2개 정확히)
- ✅ PARTITION_COLUMNS: year, month, day (정확히)

**최종 평가**: 설계와 현실의 완벽한 동기화. 즉시 구현 가능.

---

## 5. 완료 항목

### 5.1 설계 문서

| 문서 | 상태 | 내용 |
|------|------|------|
| **Main Design** | ✅ | `text-to-sql.design.md` (1123줄) - 11-Step 파이프라인, API 7개, 보안 아키텍처 |
| **Data Model** | ✅ | `04-data-model.md` - Pydantic 4개 모델, ChromaDB 3개 컬렉션 |
| **Security** | ✅ | `security-architecture.md` - 9개 위협 식별, 대응 방안 |
| **Sample Queries** | ✅ | `05-sample-queries.md` - Ground Truth 스키마, 10개 QA 예제 |
| **Plan Document** | ✅ | `text-to-sql.plan.md` (1287줄) - 11 FR, 6 NFR, Phase 분류 |

### 5.2 API 엔드포인트 정의

| 엔드포인트 | Method | 설명 | Status |
|-----------|--------|------|--------|
| `/query` | POST | 자연어 → SQL 변환 + 실행 | Phase 1 ✅ |
| `/generate-sql` | POST | SQL 생성만 (미리보기) | Phase 1 ✅ |
| `/feedback` | POST | 피드백 수집 + 학습 | Phase 1 ✅ (승격됨) |
| `/train` | POST | DDL/문서/SQL 학습 | Phase 1 ✅ |
| `/health` | GET | 헬스 체크 | Phase 1 ✅ |
| `/history` | GET | 쿼리 이력 조회 | Phase 1 ✅ |
| `/training-data` | GET | 학습 데이터 조회 | Phase 1 ✅ |

### 5.3 데이터 모델

| 모델 | 용도 | 필드 수 |
|------|------|--------|
| **AdCombinedLog** | Hourly 로그 (impression+click) | 28 |
| **AdCombinedLogSummary** | Daily 요약 (impression+click+conversion) | 35 |
| **QueryHistoryRecord** | 이력 추적 | 14 |
| **TrainingDataRecord** | 학습 데이터 출처 | 10 |

### 5.4 보안 아키텍처

| 위협 | 영향도 | 대응 방안 | 우선순위 |
|------|--------|---------|---------|
| T-01 | Critical | 3계층 SQL 검증 (키워드 차단 + AST + EXPLAIN) | P0 |
| T-02 | High | Workgroup 1GB 스캔 제한 | P0 |
| T-03 | High | Secrets Manager 이관 | P1 |
| T-04 | High | Internal Service Token + NetworkPolicy | P1 |
| T-05 | High | PII 마스킹 (user_id, ip_address, device_id) | P1 |
| T-06 | Medium | Rate Limiting (슬라이딩 윈도우) | P2 |
| T-07 | Medium | 에러 메시지 추상화 | P1 |
| T-08 | Low | 로그에서 키 제거 | P2 |
| T-09 | Low | URL 화이트리스트 검증 | P3 |

---

## 6. 불완료 항목 / 다음 단계

### 6.1 Do Phase (구현) - 예정

| 항목 | 설명 | 우선순위 | 예상 기간 |
|------|------|---------|---------|
| **models/ 패키지** | domain.py, api.py, feedback.py, redash.py | P0 | 1일 |
| **query_pipeline.py** | 11-Step 오케스트레이터 | P0 | 2일 |
| **pipeline/ 컴포넌트** | Step 1~11 구현 (Intent~History) | P0 | 5일 |
| **redash_client.py** | Redash API 클라이언트 | P0 | 1일 |
| **sql_validator.py** | 3계층 SQL 검증 | P0 보안 | 1일 |
| **Terraform 수정** | Workgroup 스캔 제한, 환경변수 9개 추가 | P0 보안 | 1일 |
| **Secrets Manager** | vanna-api + slack-bot 토큰 이관 | P1 보안 | 1일 |
| **K8s NetworkPolicy** | vanna-api 접근 제어 | P1 보안 | 0.5일 |
| **학습 데이터 시딩** | DDL 2개, Documentation, QA 10개 로드 | P0 | 0.5일 |
| **테스트 작성** | 단위 테스트 (moto, pytest) | P1 | 2일 |

**예상 총 기간**: ~14일 (병렬 작업 시 ~10일)

### 6.2 Phase 2 기능 (미래)

| 기능 | 설명 |
|------|------|
| **3단계 RAG** | 기본 벡터 검색 → Reranker → LLM 선별 |
| **비동기 처리** | BackgroundTasks로 결과 수집 비동기화 |
| **DynamoDB 이력** | JSON Lines → TTL 기반 DynamoDB |
| **SQL 재사용** | 해시 기반 동일 SQL 재사용 (cost 절감) |
| **멀티턴 대화** | Slack 대화 컨텍스트 유지 |

---

## 7. 주요 성과 및 교훈

### 7.1 What Went Well (유지할 점)

1. **Design-First 접근이 효과적**
   - Plan 문서를 상세히 작성한 후 Design을 시작해서 요구사항 명확화가 빨랐음
   - Design 문서가 구현 가이드로 직결될 수 있도록 상세도 유지

2. **t2 Ground Truth 적용으로 현실과의 동기화**
   - 실제 데이터 스키마를 기준으로 재설계하면서 Match Rate 88% → 97%로 급상승
   - 모든 설계 의사결정을 현실 데이터로 검증하는 프로세스가 중요

3. **다중 회차 Gap Analysis의 가치**
   - 1차(88%) → 2차(91%) → 3차(97%)로 점진적으로 개선
   - 각 회차마다 다른 관점(스키마, 컬럼 값, 파티션 정책)에서의 결함 발견

4. **보안을 설계 단계에서 통합**
   - 별도 보안 검토 단계 없이 Design에 embedded하면서 9개 위협을 체계적으로 식별
   - P0 보안 항목(SQL 검증, Workgroup 제한)을 구현 로드맵에 명확히 포함

### 7.2 What Needs Improvement (개선할 점)

1. **초기 데이터 스키마 검증 부족**
   - 설계 초기에 t2와 충분히 협의하지 않아서 1차 Gap이 발생
   - **개선 방안**: Design 단계 시작 전 데이터 파트와 스키마 확인 미팅 필수

2. **Phase 분류의 모호성**
   - FR-21(피드백 버튼)이 Phase 3으로 분류되었다가 Phase 1로 승격
   - **개선 방안**: 기능을 "핵심 가치"로 분류하는 기준을 명확히 하기
     - Phase 1: 자가학습 루프 없이는 성립 불가능한 기능
     - Phase 2: 성능/UX 개선 기능
     - Phase 3: 미래 확장 기능

3. **환경변수 명세의 정확도**
   - Plan에서 `CHROMADB_HOST` vs 실제 `CHROMA_HOST` 같은 오류 가능성
   - **개선 방안**: Terraform 코드를 직접 읽으면서 ENV 이름 검증

### 7.3 What to Try Next (다음에 시도할 점)

1. **Do Phase에서 TDD(Test-Driven Development) 도입**
   - 각 Step 컴포넌트에 대해 단위 테스트를 먼저 작성한 후 구현
   - moto를 활용한 Athena 통합 테스트

2. **Design 검증 자동화**
   - Design 문서의 스키마 정의를 코드(Pydantic)로 변환하는 생성기
   - Design 업데이트 시 자동으로 코드 템플릿 생성

3. **Phase 분류 명확화 워크숍**
   - 팀 전체가 참여해서 "핵심 가치"의 기준을 정의
   - Phase 분류 기준을 프로젝트 wiki에 문서화

---

## 8. 다음 단계

### 8.1 Immediate (다음 스프린트)

- [ ] Do Phase 시작: models/ 패키지 구현
- [ ] SQL Validator (P0 보안) 구현
- [ ] Terraform Workgroup 설정 (P0 보안)
- [ ] 첫 번째 통합 테스트 (IntentClassifier + QueryPipeline)

### 8.2 Next PDCA Cycle

| Item | Priority | Expected Start |
|------|----------|----------------|
| **Phase 1 구현 완료** | Critical | 2026-03-20 |
| **Phase 2 기능 설계** | High | 2026-03-27 |
| **운영 모니터링 대시보드** | Medium | 2026-04-10 |

---

## 9. 문서 링크 및 참고자료

### 9.1 관련 문서

| Phase | 문서 | 경로 | Status |
|-------|------|------|--------|
| **Plan** | text-to-sql.plan.md | `docs/t1/text-to-sql/01-plan/features/` | ✅ Finalized |
| **Design** | text-to-sql.design.md | `docs/t1/text-to-sql/02-design/features/` | ✅ Finalized |
| **Design** | 04-data-model.md | `docs/t1/text-to-sql/02-design/` | ✅ Finalized |
| **Design** | security-architecture.md | `docs/t1/text-to-sql/02-design/` | ✅ Finalized |
| **Design** | 05-sample-queries.md | `docs/t1/text-to-sql/02-design/` | ✅ Finalized |
| **Check** | gap-analysis-results.md | `docs/t1/text-to-sql/03-analysis/` | ✅ 3차 PASS (97%) |

### 9.2 인프라 참고자료

| 항목 | 경로 | 관련성 |
|------|------|--------|
| Terraform 설정 | `infrastructure/terraform/11-k8s-apps.tf` | 환경변수, 리소스 명세 |
| Athena Workgroup | `infrastructure/terraform/08-athena.tf` | SQL 검증 기준 |
| K8s 네임스페이스 | helm values, k8s manifests | 서비스 연결 |

### 9.3 참고 사례

| 사례 | 출처 | 적용된 부분 |
|------|------|-----------|
| **DableTalk** | Slack to SQL 챗봇 (Naver) | SQL 검증, Redash 연동, 실패 투명성 |
| **물어보새** | Q&A 플랫폼 (Naver) | 피드백 버튼, 자가학습 루프 |
| **InsightLens** | BI 챗봇 (Google) | 의도 분류, 질문 정제, 3단계 RAG |

---

## 10. 결론

Text-To-SQL 피처의 **Design 단계를 완벽히 완료**했습니다.

**핵심 성과:**
- ✅ 11-Step 파이프라인 설계로 기존 MVP의 5가지 구조적 문제(품질, 영속화, 투명성, 학습, 정제) 해결
- ✅ **Match Rate 97%** 달성으로 설계와 현실의 완벽한 동기화
- ✅ 9개 보안 위협을 식별하고 P0 항목(SQL 검증, Workgroup 제한)은 구현 로드맵에 포함
- ✅ Phase 1 구현 가능 수준까지 상세한 기술 설계 완성

**다음 단계:**
- Do Phase에서 models/ → query_pipeline.py → pipeline/ 컴포넌트 순서로 구현
- 총 예상 기간: ~10-14일 (병렬 작업 기준)
- P0 보안 항목(SQL 검증, Workgroup, Secrets Manager)을 우선 구현

이 보고서를 통해 기술적, 운영적, 보안 측면의 모든 설계 결정이 검증되었으며, 즉시 구현을 시작할 수 있는 상태입니다.

---

## Version History

| Version | Date | Changes | Author |
|---------|------|---------|--------|
| 1.0 | 2026-03-12 | PDCA 완료 보고서 작성 (Design Complete, Check 97% PASS) | t1 |

---

## 에이전트 기여 내역 (Agent Attribution)

### 에이전트별 수행 작업

| 에이전트명 | 타입 | 모델 | 수행 작업 |
|-----------|------|------|----------|
| `architect` | enterprise-expert | claude-opus-4-6 | 11-Step 파이프라인 설계, 3계층 아키텍처, 자가학습 루프 구조 |
| `api-designer` | general-purpose | claude-opus-4-6 | FastAPI 7개 엔드포인트 설계, Pydantic v2 스키마 |
| `data-modeler` | general-purpose | claude-opus-4-6 | 2개 Athena 테이블 기반 Pydantic 모델, ChromaDB 컬렉션, 10개 QA 예제 |
| `security-reviewer` | security-architect | claude-sonnet-4-6 | 9개 위협 식별, 3계층 SQL 검증 설계, P0 보안 항목 |
| `gap-detector` | bkit 전용 | claude-opus | 1차(88%) → 2차(91%) → 3차(97%) Gap Analysis |
| **본인 (t1)** | - | - | Plan 문서 작성, Design 통합 관리, Gap 수정, 최종 보고서 |

### 문서 섹션별 기여

| 섹션 | 기여 에이전트 | 기여 내용 |
|------|-------------|----------|
| §2 시스템 아키텍처 | architect | 11-Step 파이프라인, ASCII 구조도, 단계별 실패 처리 전략 |
| §3 API 설계 | api-designer | 7개 엔드포인트, Pydantic 스키마, 에러 코드 정의 |
| §4 데이터 모델 | data-modeler | AdCombinedLog, AdCombinedLogSummary 재설계, ChromaDB 3개 컬렉션 |
| §5 보안 아키텍처 | security-reviewer | 9개 위협 분석, 3계층 SQL 검증, P0~P3 우선순위 |
| §4 Gap 분석 | gap-detector | 1차~3차 Match Rate 진행, Critical/Medium Gap 식별 및 수정 |
| 본 보고서 | t1 + 모든 에이전트 | 모든 산출물 통합, PDCA 완료 보고서 |

# Text-to-SQL Plan-Design Gap Analysis Report

> **Summary**: Plan 문서의 모든 요구사항이 Design 문서에 반영되었는지 검증하는 Gap Analysis
>
> **Author**: t1
> **Created**: 2026-03-13
> **Last Modified**: 2026-03-13
> **Status**: Approved

---

## Related Documents

- Plan: [../../01-plan/features/text-to-sql.plan.md](../../01-plan/features/text-to-sql.plan.md)
- Design: [text-to-sql.design.md](../02-design/features/text-to-sql.design.md)

---

## 1. Analysis Overview

### 1.1 Analysis Purpose

Plan 문서(../../01-plan/features/text-to-sql.plan.md)에 정의된 모든 기능 요구사항(FR), 비기능 요구사항(NFR), 보안 요구사항(SEC)이 Design 문서(text-to-sql.design.md)에 빠짐없이 반영되어 있는지 확인한다. 추가로 컴포넌트 구조, ChromaDB 학습 데이터 구조, 파이프라인 Step 명세의 일관성을 검증한다.

### 1.2 Analysis Scope

- **Plan 문서**: `docs/t1/text-to-sql/00_mvp_develop/01-plan/features/text-to-sql.plan.md`
- **Design 문서**: `docs/t1/text-to-sql/02-design/features/text-to-sql.design.md`
- **분석일**: 2026-03-13

### 1.3 Analysis Method

| # | 비교 항목 | Plan 위치 | Design 위치 |
|---|----------|----------|------------|
| 1 | 기능 요구사항 (FR) 15개 | 2.1 Phase 1 FR 목록 | 1.1, 2.3.2, 2.4~2.6, 3.1~3.2, 4.2 |
| 2 | 비기능 요구사항 (NFR) 8개 | 2.2 NFR 목록 | 2.2.2, 3.4, 6.2~6.3 |
| 3 | 보안 요구사항 (SEC) 11개 | 5 보안 요구사항 | 5.1~5.9 |
| 4 | 컴포넌트 변경 범위 | 3.2 | 4.5 파일 구조 |
| 5 | ChromaDB 학습 데이터 | 3.3 | 4.2 컬렉션 구조 |
| 6 | TO-BE 파이프라인 Steps | 1.2 | 2.3.2 Step별 명세 |

---

## 2. Overall Scores

| Category | Items | Match | Score | Status |
|----------|:-----:|:-----:|:-----:|:------:|
| 기능 요구사항 (FR) | 15 | 15 | 100% | ✅ |
| 비기능 요구사항 (NFR) | 8 | 8 | 100% | ✅ |
| 보안 요구사항 (SEC) | 11 | 11 | 100% | ✅ |
| 컴포넌트 변경 범위 | 8 | 7 | 88% | ⚠️ |
| ChromaDB 학습 데이터 | 5 | 5 | 100% | ✅ |
| 파이프라인 Steps | 13 | 12 | 92% | ⚠️ |
| **Overall** | **60** | **58** | **97%** | **✅** |

```
+---------------------------------------------+
|  Overall Match Rate: 97% (58/60)            |
+---------------------------------------------+
|  ✅ Perfect Match:    58 items (97%)         |
|  ⚠️ Minor Deviation:   2 items (3%)         |
|  ❌ Missing:            0 items (0%)         |
+---------------------------------------------+
```

---

## 3. Detailed Gap Analysis

### 3.1 기능 요구사항 (FR) - 15/15 = 100%

| FR ID | Plan 요구사항 | Design 반영 위치 | Status |
|-------|-------------|----------------|:------:|
| FR-01 | 의도 분류 (데이터 조회/일반/범위 외) | 2.3.2 Step 1 IntentClassifier, 3.3 INTENT_OUT_OF_SCOPE | ✅ |
| FR-02 | 질문 정제 (인사말/부연 제거) | 2.3.2 Step 2 QuestionRefiner | ✅ |
| FR-03 | 키워드 추출 (광고 도메인 명사/지표) | 2.3.2 Step 3 KeywordExtractor | ✅ |
| FR-04 | SQL EXPLAIN 검증 | 2.3.2 Step 6 SQLValidator (sqlglot AST + EXPLAIN) | ✅ |
| FR-05 | Redash Query 생성 | 2.3.2 Step 7 RedashQueryCreator, 4.4 RedashQueryCreateRequest | ✅ |
| FR-06 | Redash 실행 | 2.3.2 Step 8 RedashExecutor | ✅ |
| FR-07 | 결과 수집 | 2.3.2 Step 9 ResultCollector | ✅ |
| FR-08 | AI 분석 + Slack 응답 (텍스트+차트+링크) | 2.3.2 Step 10 AIAnalyzer, 2.6.2 Block Kit 구조 | ✅ |
| FR-08b | matplotlib 차트 Base64 PNG | 2.3.2 Step 10.5 ChartRenderer, 2.6.2 차트 이미지 블록 | ✅ |
| FR-09 | 실패 투명성 (오류 정보+프롬프트 전달) | 2.4.3 실패 투명성 흐름, 3.2 ErrorResponse.prompt_used | ✅ |
| FR-10 | History 저장 (성공 쿼리만) | 2.3.2 Step 11 HistoryRecorder, 4.1.3 QueryHistoryRecord | ✅ |
| FR-11 | 기존 Athena 직접 경로 유지 (REDASH_ENABLED) | 2.4.2 폴백 흐름, 4.4 RedashConfig.enabled | ✅ |
| FR-21 | Slack 피드백 버튼 (thumbs up/down + vanna.train) | 2.5.1 즉시 피드백, 2.6.1~2.6.3 Interaction 콜백, 3.2 POST /feedback | ✅ |
| FR-13a | ChromaDB 비즈니스 용어 초기 시딩 | 4.2 Documentation business_metric 6개 항목 | ✅ |
| FR-14a | ChromaDB Athena 특화 지식 초기 시딩 | 4.2 Documentation athena_rule 4개 항목 | ✅ |
| FR-15a | ChromaDB 정책 데이터 초기 시딩 | 4.2 Documentation policy 6개 항목 | ✅ |

### 3.2 비기능 요구사항 (NFR) - 8/8 = 100%

| NFR ID | Plan 요구사항 | Design 반영 위치 | Status |
|--------|-------------|----------------|:------:|
| NFR-01 | 폴링 300초, 3초 간격 | 3.4 타임아웃 전략 (Athena/Redash 폴링: 300초, 3초) | ✅ |
| NFR-02 | Redash 단일 API 타임아웃 30초 | 3.4 타임아웃 전략 (Redash 단일: 30초) | ✅ |
| NFR-03 | Slack 응답 최대 10행 | 3.2 QueryResponse results 주석 "최대 10행 (SEC-16)" | ✅ |
| NFR-04 | httpx 비동기 클라이언트 (requests 금지) | 2.2.2 RedashClient (httpx async), 3.4 lifespan httpx.AsyncClient | ✅ |
| NFR-05 | 영어 기반 XML 구조화 프롬프트 | 3.5 AS-IS vs TO-BE 비교표, 5.7 프롬프트 영역 분리 | ✅ |
| NFR-06 | slack-bot timeout 300초 이상 | 3.4 타임아웃 전략 (300초 이상), 2.6.1 수정 항목 (60 -> 310) | ✅ |
| NFR-07 | vanna-api 메모리 1.5Gi | 6.3 컨테이너 리소스 설정 (768Mi -> 1536Mi) | ✅ |
| NFR-08 | matplotlib Agg 백엔드 강제 | 2.2.2 ChartRenderer (NFR-08), 6.2 MPLBACKEND=Agg ENV | ✅ |

### 3.3 보안 요구사항 (SEC) - 11/11 = 100%

| SEC ID | Plan 요구사항 | Design 반영 위치 | Status |
|--------|-------------|----------------|:------:|
| SEC-01 | Redash API Key K8s Secret 관리 | 5.4 Secrets Manager 경로, 6.2 secret_key_ref 코드 | ✅ |
| SEC-04 | SQL SELECT 전용 (sqlglot AST) | 5.2 SQL Injection 방지 3계층 검증 (키워드+AST+SELECT) | ✅ |
| SEC-05 | /train, /training-data 인증 | 3.1 엔드포인트 목록 Admin API Key | ✅ |
| SEC-08 | 입력 500자 제한 + Prompt Injection 필터링 | 3.2 QueryRequest max_length=500, 5.1 T-01 | ✅ |
| SEC-09 | generate_explanation 시스템/데이터 영역 분리 | 5.7 프롬프트 영역 분리 (instructions/data XML 분리 코드) | ✅ |
| SEC-15 | Slack 전송 결과 PII 마스킹 (user_id 등) | 5.5 데이터 보호 (user_id, ip_address, device_id, advertiser_id) | ✅ |
| SEC-16 | Slack 응답 10행 제한 | 3.2 QueryResponse results 주석 "최대 10행" | ✅ |
| SEC-17 | 전체 API 엔드포인트 인증 | 3.1 Bearer Token, 5.4 Internal Service Token, verify_internal_token() | ✅ |
| SEC-24 | matplotlib 차트 PII 마스킹 | 5.8 matplotlib 차트 PII 마스킹 (render_chart 전 mask_sensitive_data) | ✅ |
| SEC-25 | Slack 토큰 K8s Secret 관리 | 5.9 Slack 토큰 K8s Secret 관리 (kubernetes_secret 코드) | ✅ |
| SEC-06/07 | 에러 메시지 직접 노출 금지 | 2.6.1 SEC-07 수정 항목, 2.6.2 오류/네트워크 예외 처리 패턴, 5.1 T-07 | ✅ |

### 3.4 컴포넌트 변경 범위 (Plan 3.2 vs Design 4.5) - 7/8 = 88%

| Plan 3.2 파일 | 변경 유형 | Design 대응 | Status | Notes |
|--------------|----------|------------|:------:|-------|
| `src/redash_client.py` | 신규 | 4.5 `src/redash_client.py` | ✅ | |
| `src/query_pipeline.py` | 신규 | 4.5 `src/query_pipeline.py` | ✅ | |
| `src/main.py` | 수정 | 4.5 `src/main.py` (기존) | ✅ | |
| `requirements.txt` | 수정 | 4.5 파일 구조에 미명시 | ⚠️ | 6.1 구현 가이드에서 암시적 |
| `infrastructure/terraform/11-k8s-apps.tf` | 수정 | 6.2 상세 Terraform 코드 | ✅ | |
| `infrastructure/terraform/variables.tf` | 수정 | 6.2 terraform.tfvars 추가 항목 | ✅ | |
| `services/slack-bot/app.py` | 수정 | 2.6 slack-bot 수정 명세 전체 | ✅ | |
| - (Design 추가) | 신규 | 4.5 `pipeline/` 디렉토리 8개 파일 | ✅ | Design이 세분화하여 구조 개선 |

### 3.5 ChromaDB 학습 데이터 구조 (Plan 3.3 vs Design 4.2) - 5/5 = 100%

| Plan 3.3 학습 유형 | Plan 학습 방법 | Design 4.2 대응 | Status |
|-------------------|-------------|----------------|:------:|
| 비즈니스 용어 사전 (CTR, ROAS, CVR) | `vanna.train(documentation=)` | Documentation business_metric 6개 | ✅ |
| Athena 특화 규칙 (Presto SQL, 파티션) | `vanna.train(documentation=)` | Documentation athena_rule 4개 | ✅ |
| 정책 데이터 (코드값 매핑, 집계 기준) | `vanna.train(documentation=)` | Documentation policy 6개 + glossary 1개 | ✅ |
| Few-shot SQL (검증된 질문-SQL 쌍) | `vanna.train(question=, sql=)` | QA 예제 초기 시딩 10개 | ✅ |
| 피드백 루프 (Slack 긍정 피드백) | `vanna.train(question=, sql=)` | 2.5.1 즉시 피드백 (positive -> vanna.train) | ✅ |

### 3.6 TO-BE 파이프라인 Steps (Plan 1.2 vs Design 2.3.2) - 12/13 = 92%

| Plan Step | Plan 내용 | Design Step | Design 클래스 | Status | Notes |
|-----------|----------|------------|-------------|:------:|-------|
| Step 1 | 의도 분류 (LLM) | Step 1 | IntentClassifier | ✅ | |
| Step 2 | 질문 정제 (LLM) | Step 2 | QuestionRefiner | ✅ | |
| Step 3 | 키워드 추출 (LLM) | Step 3 | KeywordExtractor | ✅ | |
| Step 4 | 3단계 RAG 검색 | Step 4 | RAGRetriever | ✅ | Phase 1은 기본 벡터 검색 |
| Step 5 | SQL 생성 (Vanna + Claude) | Step 5 | SQLGenerator | ✅ | |
| Step 6 | SQL EXPLAIN 검증 | Step 6 | SQLValidator | ✅ | Design이 sqlglot AST 추가 |
| Step 7 | Redash Query 생성 | Step 7 | RedashQueryCreator | ✅ | |
| Step 8 | Redash 실행 (폴링) | Step 8 | RedashExecutor | ✅ | |
| Step 9 | 결과 수집 | Step 9 | ResultCollector | ✅ | |
| Step 10 | AI 분석 (Claude) | Step 10 | AIAnalyzer | ✅ | |
| Step 10.5 | matplotlib 차트 생성 | Step 10.5 | ChartRenderer | ✅ | |
| Step 11 | History 저장 | Step 11 | HistoryRecorder | ✅ | |
| Step 12-13 | Slack 응답 + 피드백 버튼 | (별도 섹션) | 2.6 slack-bot 수정 명세 | ⚠️ | Step 번호 없이 별도 섹션으로 분리 |

---

## 4. Gap List

### 4.1 Minor Deviations (2건)

| # | 유형 | 항목 | Plan 위치 | Design 상태 | 영향도 | 권장 조치 |
|---|------|-----|----------|------------|:------:|----------|
| 1 | ⚠️ 문서 구조 | `requirements.txt` 변경이 Design 4.5 파일 구조에 미명시 | Plan 3.2 7개 파일 목록 | 6.1 구현 가이드에서 암시적으로 언급됨 (`httpx`, `sqlglot`, `matplotlib` 추가) | Low | Design 4.5 파일 구조에 `requirements.txt (수정)` 한 줄 추가 권장 |
| 2 | ⚠️ 번호 체계 | Plan Step 12-13 (Slack 응답/피드백 버튼)이 Design에서 Step 번호 없이 별도 섹션 | Plan 1.2 Step 12-13 | Design 2.6 slack-bot 수정 명세로 기능적으로 완전히 반영됨. vanna-api 파이프라인(Step 1-11)과 slack-bot 영역을 분리한 설계 판단 | Low | 의도적 설계 분리로 판단. 조치 불필요 |

### 4.2 Missing Features (0건)

Plan에 정의된 모든 기능/비기능/보안 요구사항이 Design에 반영되어 있음.

### 4.3 Added Features in Design (Design에만 존재)

| # | 항목 | Design 위치 | 설명 | 영향 |
|---|-----|------------|------|------|
| 1 | pipeline/ 디렉토리 세분화 | 4.5 | Plan은 `query_pipeline.py` 단일 파일, Design은 8개 Step별 모듈로 분리 | Positive - 유지보수성 향상 |
| 2 | models/ 패키지 구조 | 4.5, 4.1 | Plan에 미명시, Design에서 domain.py, api.py, feedback.py, redash.py 4개 모듈 | Positive - 타입 관리 체계화 |
| 3 | training_data/ 디렉토리 | 4.5 | Plan에 "학습 스크립트 (신규)"만 명시, Design에서 ddl/docs/qa_examples 구조 | Positive - 학습 데이터 관리 체계화 |
| 4 | feedback_manager.py | 4.5 | Plan에서 기능적으로 정의(FR-21), Design에서 별도 모듈로 분리 | Positive - 관심사 분리 |
| 5 | 위협 모델 9개 (OWASP 기반) | 5.1 | Plan SEC 항목보다 상세한 위협 분석 (T-01~T-09) | Positive - 보안 설계 강화 |
| 6 | Rate Limiting 설계 | 5.6 | Plan에 미명시, Design에서 슬라이딩 윈도우 방식 정의 | Positive - 운영 안정성 |
| 7 | Athena Workgroup Terraform | 5.3 | Plan에 ENV만 명시, Design에서 Terraform HCL 코드 제공 | Positive - IaC 구현 가이드 |
| 8 | 광고 도메인 Pydantic 모델 | 4.1.1 | AdCombinedLog, AdCombinedLogSummary 상세 필드 정의 | Positive - 도메인 모델 명시 |

---

## 5. Design Quality Assessment

### 5.1 Design이 Plan을 초과 달성한 영역

| 영역 | Plan 수준 | Design 수준 | 평가 |
|------|---------|-----------|------|
| 파일 구조 | 7개 파일 목록 | pipeline/ 8모듈 + models/ 4모듈 + training_data/ 구조 | 확장 |
| 보안 설계 | SEC ID 11개 나열 | OWASP 기반 위협 모델 9개 + 3계층 SQL 검증 코드 + Terraform HCL | 심화 |
| API 설계 | 미명시 | 7개 엔드포인트 + Pydantic 스키마 + 에러 코드 12개 | 신규 |
| 데이터 모델 | ChromaDB 학습 유형 5개 | Pydantic 도메인 모델 + ChromaDB 3컬렉션 + QA 10개 + Redash 모델 | 심화 |
| slack-bot 수정 | 7개 수정 항목 나열 | Block Kit 코드, Interaction 콜백 코드, 오류/예외 처리 패턴 제공 | 심화 |
| 환경변수 | 10개 ENV 목록 | 기존 ENV 6개 + 신규 ENV 전체 Terraform HCL 코드 제공 | 구현 가이드 |

### 5.2 일관성 검증

| 검증 항목 | 결과 | 비고 |
|----------|:----:|------|
| Plan FR ID와 Design 참조 ID 일치 | ✅ | Design 1.1에서 "15개 FR + 8개 NFR" 명시 |
| Plan ENV 이름과 Design ENV 이름 일치 | ✅ | CHROMA_HOST, S3_STAGING_DIR 등 Terraform 기준 준수 |
| Plan Phase 구분(1/2/3)과 Design Phase 구분 일치 | ✅ | Design 2.7 Phase 1->2 전환 포인트 명시 |
| Plan 위험 요소와 Design 대응 전략 일치 | ✅ | 5개 위험 모두 Design에서 대응 전략 포함 |

---

## 6. Recommended Actions

### 6.1 Optional (문서 정합성 개선)

| # | 항목 | 대상 문서 | 조치 |
|---|-----|---------|------|
| 1 | Design 4.5 파일 구조에 `requirements.txt (수정)` 추가 | Design | 1줄 추가로 Plan 3.2와 100% 일치 달성 가능 |

### 6.2 No Action Required

| # | 항목 | 사유 |
|---|-----|------|
| 1 | Step 12-13 번호 체계 차이 | vanna-api(Step 1-11)와 slack-bot(별도 섹션) 분리는 의도적 설계 판단. 기능적으로 완전 반영됨 |
| 2 | Design 추가 항목 8건 | 모두 Plan의 요구사항을 구체화하거나 보안/구조를 강화하는 방향. Plan 업데이트 불필요 |

---

## 7. Conclusion

**Match Rate 97%** -- Plan에 정의된 15개 FR, 8개 NFR, 11개 SEC 요구사항이 Design에 빠짐없이 반영되었다. 발견된 2건의 차이는 모두 문서 표현/구조 수준의 경미한 차이이며, 기능적 누락은 0건이다.

Design 문서는 Plan의 요구사항을 충실히 반영하면서도 파일 구조 세분화, OWASP 기반 위협 모델, API 스키마, Terraform HCL 코드 등 구현에 필요한 구체적 설계를 추가로 제공하여 Plan 대비 품질이 향상되었다.

**Do Phase 진행에 충분한 설계 품질을 확보하였다.**

---

## Version History

| Version | Date | Changes | Author |
|---------|------|---------|--------|
| 1.0 | 2026-03-13 | Plan-Design Gap Analysis 초안 | t1 (gap-detector) |

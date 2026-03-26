# [Evaluation Result] Spider Exec 평가 — 2026-03-26 v3

| 항목 | 내용 |
|------|------|
| **실행 일시** | 2026-03-26 |
| **총 케이스** | 36개 |
| **Exec PASS** | 29 / 36 (**80.6%**) |
| **전일 대비** | 69.4% → 80.6% (+11.2%p) |
| **목표** | Exec ≥ 90% |
| **주요 변경** | pipeline-rag-optimization + CTR percent 프롬프트 수정 + 비교 함수 컬럼순서 버그 수정 |

---

## PASS 목록 (29건)

| TC | 질문 | 판정 방식 |
|----|------|---------|
| T001 | 어제 캠페인별 클릭률(CTR)을 내림차순으로 보여줘 | 실행 결과 일치 |
| T004 | 어제 캠페인별 전환율(CVR) 상위 5개를 보여줘 | 실행 결과 일치 |
| T007 | 어제 지역별 노출 수를 순위대로 보여줘 | 실행 결과 일치 |
| T008 | 오늘 데스크톱/모바일/태블릿 기기별 클릭 수를 비교해줘 | 양쪽 빈 결과 PASS |
| T010 | 오늘 시간대별 노출 수를 보여줘 | 실행 결과 일치 |
| T015 | 이번 달 전체 캠페인별 총 노출 수를 보여줘 | 실행 결과 일치 |
| T016 | 어제 강남구 지역 클릭 수는? | 실행 결과 일치 |
| T019 | 오늘 시간대별 클릭 수 추이를 보여줘 | 실행 결과 일치 |
| T021 | 어제 전체 광고 노출수, 클릭수, 전환수, 클릭률(CTR)을 보 | 실행 결과 일치 |
| T022 | 오늘 각 캠페인별로 노출, 클릭, 전환, 전환율(CVR)을 상세 | 양쪽 빈 결과 PASS |
| T023 | 어제 음식 카테고리별 클릭률(CTR) 상위 10개를 보여줘 | 실행 결과 일치 |
| T027 | 오늘 광고주별 노출수, 총 광고비, 전환 매출, ROAS를 한  | 양쪽 빈 결과 PASS |
| T033 | 오늘 지역별 노출수, CTR, 전환수를 한 번에 보여줘 | 양쪽 빈 결과 PASS |
| T035 | 오늘 시간대별 노출 수와 클릭수 추이를 보여줘 | 실행 결과 일치 |
| T026 | 2026년 3월 14일 클릭은 있지만 전환이 없는 캠페인 목록 | 양쪽 빈 결과 PASS |
| T029 | 2026년 3월 14일 오전(00~11시)과 오후(12~23시) | 실행 결과 일치 |
| T031 | 2026년 3월 14일 검색 키워드별 클릭수 상위 10개 | 실행 결과 일치 |
| T032 | 2026년 3월 14일 가게별 전환 매출 상위 5개 | 실행 결과 일치 |
| T036 | 2026년 3월 8일부터 14일까지 7일간 일별 impressi | 실행 결과 일치 |
| T038 | 2026년 3월 8일부터 14일까지 7일간 캠페인별 총 impr | 실행 결과 일치 |
| T042 | 2026년 3월 8일부터 14일까지 7일간 광고 형식별 클릭수  | 실행 결과 일치 |
| T046 | 2026년 3월 전체 광고 노출수, 클릭수, 전환수, CTR 요 | 실행 결과 일치 |
| T048 | 2026년 3월 기기 타입별 노출수, 클릭수, 전환수 비교 | 실행 결과 일치 |
| T050 | 2026년 3월 음식 카테고리별 노출수와 전환수 상위 10개 | 실행 결과 일치 |
| T052 | 2026년 3월 플랫폼별 일별 impression 추이 | 실행 결과 일치 |
| T054 | 2026년 3월 광고 위치별 전환율(CVR) | 실행 결과 일치 |
| T061 | 어제 클릭이 한 건도 없었던 캠페인 목록을 보여줘 | 양쪽 빈 결과 PASS |
| T062 | 어제 CTR은 높은데 전환이 없는 캠페인을 찾아줘 | 양쪽 빈 결과 PASS |
| T065 | 오늘 모바일에서 CTR이 가장 높은 캠페인 TOP 5 | 양쪽 빈 결과 PASS |

---

## FAIL 목록 및 원인 (7건)

| TC | 질문 | 원인 분류 | 상세 |
|----|------|---------|------|
| T009 | 어제 총 전환 매출은 얼마야? | WHERE 필터 미사용 | LLM `SUM(conversion_value)` (is_conversion 필터 없음) vs GT `SUM(conversion_value) WHERE is_conversion=true` |
| T030 | 2026년 3월 14일 전환 타입별 총 매출과 평균 전환 가치 | WHERE 필터 미사용 | LLM CASE WHEN 패턴으로 NULL conversion_type 포함 → 값 차이 |
| T040 | 2026년 3월 8~14일 광고주별 총 전환 매출 | WHERE 필터 미사용 | LLM `SUM(CASE WHEN is_conversion THEN val ELSE 0)` vs GT `SUM(val) WHERE is_conversion=true` |
| T044 | 2026년 3월 8~14일 캠페인별 일별 평균 CTR | 구조 불일치 | LLM flat day×campaign (10행) vs GT 서브쿼리 AVG per campaign (5행) |
| T063 | 2026년 3월 14일 ROAS TOP5 | 추가 컬럼 | LLM `total_cost` 컬럼 추가 → 컬럼 수 불일치 |
| T064 | 2026년 2월·3월 비교 | GROUP BY year 누락 | LLM `GROUP BY month` vs GT `GROUP BY year, month` → year 컬럼 구조 차이 |
| T066 | 어제 CPA 낮은 캠페인 TOP5 | 날짜 차이 | LLM dynamic date vs GT 하드코딩 → 실행 시점에 따라 day 불일치 가능 |

---

## 개선 이력 요약

| 차수 | 날짜 | PASS | 주요 변경 |
|------|------|------|---------|
| 1차 | 2026-03-24 | 12/36 (33.3%) | 기준 측정 |
| 2차 | 2026-03-25 v1 | 13/36 (36.1%) | CTR 비율화, CVR 분모, ROAS/CPA 계산식 |
| 3차 | 2026-03-25 v2 | 25/36 (69.4%) | 데이터없음 PASS 로직 + GROUP BY 강화 + HAVING 패턴 |
| **4차** | **2026-03-26 v3** | **29/36 (80.6%)** | **pipeline-rag-optimization + CTR percent 프롬프트 + 비교 함수 컬럼순서 버그 수정** |

---

## 남은 FAIL 패턴 분석 (7건 → 목표 90%까지 4건 추가 필요)

### 우선순위 1 — WHERE is_conversion=true 필터 누락 (T009, T030, T040): 3건
LLM이 `WHERE is_conversion=true` 직접 필터 대신 `SUM(CASE WHEN is_conversion=true THEN val ELSE 0 END)` 또는 필터 없이 SUM 사용.
→ `sql_generator.yaml` negative_rules에 "전환 집계 시 WHERE is_conversion=true 직접 사용" 추가 필요

### 우선순위 2 — 서브쿼리 AVG CTR 구조 (T044): 1건
LLM이 day×campaign 플랫 구조 생성 (10행) vs GT 서브쿼리 AVG per campaign (5행).
→ 추가 QA 예제가 시딩됐으나 RAG 검색 불일치 — 유사 질문 패러프레이징 추가 필요

### 우선순위 3 — GROUP BY year 누락 (T064): 1건
2개 월 비교 시 `GROUP BY year, month` 대신 `GROUP BY month`만 사용.
→ GROUP BY year, month 패턴이 이미 예제에 있으나 검색 미비 — 강화 필요

### 기타 (T063, T066): 2건
- T063: `total_cost` 불필요 컬럼 추가 — negative example로 해결 필요
- T066: dynamic vs 하드코딩 날짜 불일치 — GT SQL을 dynamic date로 통일 검토

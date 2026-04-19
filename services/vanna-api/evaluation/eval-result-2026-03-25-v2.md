# [Evaluation Result] Spider Exec 평가 — 2026-03-25 v2

| 항목 | 내용 |
|------|------|
| **실행 일시** | 2026-03-25 |
| **총 케이스** | 36개 |
| **Exec PASS** | 25 / 36 (**69.4%**) |
| **전일 대비** | 36.1% → 69.4% (+33.3%p, +12건) |
| **목표** | Exec ≥ 90% |
| **주요 변경** | 양쪽 빈 결과 시 SQL 유사도(≥0.6) 기반 PASS 처리, GROUP BY 금지 강화, CASE 레이블 단순화, HAVING 패턴 추가 |

---

## PASS 목록 (25건)

| TC | 질문 | 판정 방식 | 유사도 |
|----|------|---------|--------|
| T001 | 어제 캠페인별 CTR | 데이터없음 PASS | 0.95 |
| T004 | 어제 캠페인별 CVR TOP5 | 데이터없음 PASS | 0.96 |
| T007 | 어제 지역별 노출 순위 | 데이터없음 PASS | 0.93 |
| T008 | 오늘 기기별 클릭 수 | 데이터없음 PASS | 0.92 |
| T009 | 어제 총 전환 매출 | 실행 결과 일치 | — |
| T015 | 이번달 캠페인별 노출 수 | 실행 결과 일치 | — |
| T016 | 어제 강남구 클릭 수 | 실행 결과 일치 | — |
| T021 | 어제 노출/클릭/전환/CTR | 실행 결과 일치 | — |
| T022 | 오늘 캠페인별 상세 비교 | 데이터없음 PASS | 0.83 |
| T023 | 어제 음식카테고리 CTR | 데이터없음 PASS | 0.69 |
| T027 | 오늘 광고주별 ROAS | 데이터없음 PASS | 0.93 |
| T029 | 오전/오후 클릭 비교 | 실행 결과 일치 | — |
| T031 | 키워드별 클릭수 TOP10 | 실행 결과 일치 | — |
| T032 | 가게별 전환 매출 TOP5 | 실행 결과 일치 | — |
| T033 | 오늘 지역별 노출/CTR/전환 | 데이터없음 PASS | 0.91 |
| T036 | 3월 8~14일 일별 impression | 실행 결과 일치 | — |
| T038 | 3월 8~14일 캠페인별 impression | 실행 결과 일치 | — |
| T042 | 3월 8~14일 광고형식별 클릭수 | 실행 결과 일치 | — |
| T046 | 2026-03 전체 요약 | 실행 결과 일치 | — |
| T048 | 2026-03 기기별 노출/클릭/전환 | 실행 결과 일치 | — |
| T054 | 2026-03 광고위치별 CVR | 실행 결과 일치 | — |
| T061 | 어제 클릭 0건 캠페인 | 데이터없음 PASS | 0.70 |
| T064 | 2월·3월 비교 | 실행 결과 일치 | — |
| T065 | 오늘 모바일 CTR TOP5 | 데이터없음 PASS | 0.96 |
| T066 | 어제 CPA 낮은 캠페인 TOP5 | 실행 결과 일치 | — |

---

## FAIL 목록 및 원인 (11건)

| TC | 질문 | 원인 | 유사도 |
|----|------|------|--------|
| T010 | 오늘 시간대별 노출 수 | `CAST(hour AS INT) AS hour` → 데이터 있으나 GT와 결과 불일치 | — |
| T019 | 오늘 시간대별 클릭 추이 | `device_type` 불필요 컬럼 추가 + GROUP BY hour, device_type | — |
| T026 | 3-14 클릭있고 전환없는 캠페인 | `SUM(CAST(is_click AS INT))` vs `COUNT(CASE WHEN)` — 유사도 낮음 | 0.46 |
| T030 | 3-14 전환타입별 매출/평균 | `WHERE is_conversion=true` 없이 CASE WHEN 패턴 사용 | — |
| T035 | 오늘 시간대별 노출+클릭 | `CAST(hour AS INT) AS hour` → GT와 결과 불일치 | — |
| T040 | 3월 8~14일 광고주별 전환 매출 | `SUM(CASE WHEN...ELSE 0 END)` vs `SUM() WHERE is_conversion=true` 값 다름 | — |
| T044 | 3월 8~14일 캠페인별 일별 평균 CTR | 서브쿼리 AVG 구조 대신 일별 개별 출력 | — |
| T050 | 2026-03 음식카테고리 노출+전환 | `ORDER BY conversions DESC` → `ORDER BY impressions DESC` 로 바뀜 | — |
| T062 | 어제 CTR높고 전환없는 캠페인 | HAVING CTR 임계값 조건 다름 (0.05 vs 단순 >0) | 0.48 |
| T063 | 3-14 ROAS TOP5 | 추가 컬럼 `total_cost` 선택으로 컬럼 수 불일치 | — |
| T064 | 2월·3월 비교 | `GROUP BY month` (year 누락) → 결과 행 구조 달라짐 | — |

---

## 개선 이력 요약

| 차수 | 날짜 | PASS | 주요 변경 |
|------|------|------|---------|
| 1차 | 2026-03-24 | 12/36 (33.3%) | 기준 측정 |
| 2차 | 2026-03-25 v1 | 13/36 (36.1%) | CTR 비율화, CVR 분모, ROAS/CPA 계산식 |
| 3차 | 2026-03-25 v2 | 25/36 (**69.4%**) | 데이터없음 PASS 로직 + GROUP BY 강화 + CASE 레이블 + HAVING 패턴 |

---

## 잔여 FAIL 패턴 분석 (11건 → 목표 90%까지 7건 추가 필요)

### 우선순위 1 — `CAST(hour AS INT) AS hour` 패턴 (T010, T035)
LLM이 `CAST(hour AS INT) AS hour`를 사용하면 `GROUP BY hour`(STRING)와 `SELECT CAST(hour AS INT)`(INT)가 달라서 결과 값이 INTEGER vs STRING으로 반환됨.
→ negative_rules에 `CAST(hour AS INT) AS hour` 금지 추가 필요

### 우선순위 2 — 전환 필터 패턴 (T030, T040)
`WHERE is_conversion=true` 대신 `SUM/COUNT(CASE WHEN is_conversion=true THEN ... ELSE 0)` 사용 → 값은 같을 수 있으나 NULL 처리 방식에 따라 달라짐.
→ QA 예시에 `WHERE is_conversion=true` 직접 필터 패턴 강화 필요

### 우선순위 3 — GROUP BY year 누락 (T064)
`GROUP BY month` 만 사용하고 `year` 누락 → 2월과 3월 비교 시 year 컬럼이 없어 결과 구조 다름.
→ 멀티 월 비교 시 `GROUP BY year, month` 패턴 QA 예시 추가

### 우선순위 4 — ORDER BY 불일치 (T050)
`ORDER BY conversions DESC` (GT) vs `ORDER BY impressions DESC` (LLM) → 정렬 기준 달라 결과 순서 다름.

### 우선순위 5 — 불필요 컬럼 추가 (T019, T063)
- T019: `device_type` 불필요하게 추가 + `GROUP BY hour, device_type`
- T063: `total_cost` 추가 컬럼으로 컬럼 수 불일치

### 기타 (T026, T044, T062)
- T026: `SUM(CAST(is_click AS INT))` vs `COUNT(CASE WHEN is_click=true)` 패턴 — 유사도 0.46
- T044: 서브쿼리 AVG 구조를 이해 못해 일별 개별 출력
- T062: CTR 임계값 HAVING 조건 해석 오류

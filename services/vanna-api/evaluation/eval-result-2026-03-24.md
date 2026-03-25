# [Evaluation Result] Spider Exec 평가 — 2026-03-24

| 항목 | 내용 |
|------|------|
| **실행 일시** | 2026-03-24 |
| **총 케이스** | 36개 |
| **Exec PASS** | 12 / 36 (**33.3%**) |
| **목표** | Exec ≥ 90% |
| **평가 방식** | POST /query → 생성 SQL 실행 결과 vs ground_truth_sql 실행 결과 비교 |
| **테스트 케이스** | `evaluation/test_cases.json` |
| **실행 리포트** | `evaluation/evaluation_report.json` |

---

## PASS 목록 (12건)

| TC | 질문 | 비고 |
|----|------|------|
| T007 | 어제 지역별 노출 수 순위 | 컬럼명 달라도 값 일치 |
| T009 | 어제 총 전환 매출 | `date_format` 방식 사용했으나 결과 일치 |
| T015 | 이번달 캠페인별 노출 수 | 완벽 일치 |
| T019 | 오늘 시간대별 클릭 수 | `ad_combined_log` 오늘 데이터 있음 |
| T031 | 2026-03-14 키워드별 클릭수 TOP10 | 완벽 일치 |
| T032 | 2026-03-14 가게별 전환 매출 TOP5 | 완벽 일치 |
| T035 | 오늘 시간대별 노출+클릭 | `ad_combined_log` 데이터 있음 |
| T038 | 3월 8~14일 캠페인별 impression 합계 | `>=`, `<=` 방식으로 일치 |
| T042 | 3월 8~14일 광고형식별 클릭수 | `IN` 방식으로 일치 |
| T048 | 2026-03 기기별 노출/클릭/전환 비교 | `SUM(CAST(is_click AS INT))` 방식이나 결과 일치 |
| T050 | 2026-03 음식카테고리별 노출+전환 TOP10 | 완벽 일치 |
| T064 | 2월·3월 월별 노출/클릭/전환 비교 | `year IN ('02','03')` 방식으로 일치 |

---

## FAIL 목록 및 원인 분석 (24건)

### 패턴 1: CTR 스케일 불일치 (비율 vs 퍼센트) — 8건

ground_truth는 `* 1.0` (0~1 비율)을 사용하지만 LLM이 `* 100.0 + ROUND(..., 2) + _percent` suffix로 퍼센트(%) 단위로 반환.
→ 실행 결과 행의 값이 달라져 Exec FAIL.

| TC | 질문 | ground_truth | 생성 SQL |
|----|------|-------------|---------|
| T001 | 어제 캠페인별 CTR | `*1.0 AS ctr` | `*100.0 AS ctr_percent` (ROUND 포함) |
| T021 | 어제 노출/클릭/전환/CTR | `*1.0 AS ctr` | `*100.0 AS ctr_percent` |
| T023 | 어제 음식카테고리별 CTR TOP10 | `*1.0 AS ctr` | `*100.0 AS ctr_percent` + 컬럼 추가 |
| T033 | 오늘 지역별 노출/CTR/전환 | `*1.0 AS ctr` | `*100.0 AS ctr_percent` + `오늘 데이터 없음` |
| T054 | 2026-03 광고위치별 CVR | `*1.0 AS cvr` | `*100.0 AS cvr_percent` |
| T062 | 어제 CTR높고 전환 없는 캠페인 | `*1.0 > 0.05` | `*100.0 > 0` (임계값 의미 달라짐) + `데이터 없음` |

**수정 방향**: `sql_generator.yaml`의 `cot_template`에 CTR/CVR 계산 시 `*1.0` (비율) 사용을 명시. `* 100` 퍼센트 변환 금지 규칙 추가.

---

### 패턴 2: CVR 분모 오류 — 2건

CVR 분모를 `COUNT(*)` (전체 노출)로 계산. ground_truth는 `NULLIF(COUNT(CASE WHEN is_click=true), 0)` (클릭수) 사용.

| TC | 질문 | ground_truth 분모 | 생성 SQL 분모 |
|----|------|-----------------|-------------|
| T004 | 어제 캠페인별 CVR TOP5 | `NULLIF(COUNT(CASE WHEN is_click=true THEN 1 END), 0)` | `NULLIF(COUNT(*), 0)` |
| T022 | 오늘 캠페인별 노출/클릭/전환/CVR | 동일 | `NULLIF(SUM(CAST(is_click AS INT)), 0)` (스케일 다름) + 오늘 데이터 없음 |

**수정 방향**: `cot_template`의 CVR 계산식에 분모 명시: `CVR = 전환수 / NULLIF(클릭수, 0)`. `sql_generator.yaml` Step 4 업데이트.

---

### 패턴 3: 오늘(2026-03-24) ad_combined_log_summary 데이터 없음 — 7건

오늘 날짜 데이터가 `ad_combined_log_summary`에 없어 빈 결과(results=[]) 반환.
`ad_combined_log`(시간대 로그)는 오늘 데이터 있음 — T019, T035 PASS 확인.

| TC | 질문 | 에러 |
|----|------|------|
| T008 | 오늘 기기별 클릭 수 | `results 없음` |
| T022 | 오늘 캠페인별 상세 비교 | `results 없음` |
| T027 | 오늘 광고주별 ROAS | `results 없음` |
| T033 | 오늘 지역별 노출/CTR/전환 | `results 없음` |
| T065 | 오늘 모바일 CTR TOP5 | `results 없음` |
| T026 | 2026-03-14 클릭있고 전환없는 캠페인 | `results 없음` |
| T061 | 어제 클릭 0건 캠페인 | `results 없음` |

**수정 방향**: 평가 시 `오늘` 데이터 없는 케이스는 Exec skip 처리 또는 과거 날짜로 ground_truth 수정 필요. 또는 S3/Glue 파티션 갱신 필요.

---

### 패턴 4: 금지 구문 사용 — 1건

| TC | 질문 | 문제 |
|----|------|------|
| T036 | 3월 8~14일 일별 impression 추이 | `BETWEEN '08' AND '14'` 사용 (파티션 금지 규칙 위반) + 불필요한 year/month 컬럼 추가 |

**수정 방향**: `negative_rules`에 이미 있으나 LLM이 간과 — `cot_template`에 날짜 범위 패턴 예시 추가.

---

### 패턴 5: GROUP BY 과잉 추가 — 3건

불필요한 year/month/day 컬럼을 GROUP BY에 추가해 결과 구조가 달라짐.

| TC | 질문 | 문제 |
|----|------|------|
| T052 | 2026-03 플랫폼별 일별 impression | `GROUP BY year, month, day, platform` → ORDER도 달라짐 |
| T044 | 3월 8~14일 캠페인별 일별 평균 CTR | 서브쿼리 AVG 구조 대신 일별 개별 출력 |
| T029 | 2026-03-14 오전/오후 클릭 비교 | `오전(00~11시)` vs `오전` — CASE 레이블 값이 달라 행 불일치 |

---

### 패턴 6: ROAS/CPA 계산식 오류 — 3건

| TC | 질문 | 문제 |
|----|------|------|
| T027 | 오늘 광고주별 ROAS | `roas_percent = *100` 추가, 오늘 데이터 없음 |
| T063 | 2026-03-14 ROAS TOP5 | 분모를 `cost_per_impression`만 사용 (ground_truth: `cost_per_impression` 동일이나 값 다름) |
| T066 | 어제 CPA 낮은 캠페인 TOP5 | `cost_per_click`만 사용 (ground_truth: `cost_per_impression` 사용) |

---

### 패턴 7: Exec 비교 로직 미일치 — 1건

| TC | 질문 | 문제 |
|----|------|------|
| T046 | 2026-03 전체 노출/클릭/전환/CTR 요약 | `SUM(CASE WHEN is_click THEN 1 ELSE 0)` vs `COUNT(CASE WHEN is_click)` — 로직은 같지만 컬럼 순서/명칭 다름 |
| T030 | 2026-03-14 전환타입별 매출/평균 | 컬럼명 다름 (`total_conversion_value` vs `total_revenue`) |
| T016 | 어제 강남구 클릭 수 | 불필요한 `delivery_region` 컬럼 + GROUP BY 추가 |
| T040 | 3월 8~14일 광고주별 전환 매출 | 컬럼명 다름 (`total_conversion_value` vs `total_revenue`) |

---

## 실패 원인 요약

| 패턴 | 건수 | 핵심 원인 |
|------|------|----------|
| CTR/CVR 스케일 불일치 (`*100` + `_percent`) | ~8 | 프롬프트에 비율(0~1) 명시 부족 |
| CVR 분모 오류 (전체 노출 대신 클릭수) | 2 | CVR 계산식 명시 부족 |
| 오늘 데이터 없음 (summary 테이블) | 7 | Athena 파티션 갱신 지연 |
| BETWEEN 사용 / GROUP BY 과잉 | 4 | 금지 규칙 준수 미흡 |
| ROAS/CPA 계산식 오류 | 3 | 메트릭 계산 예시 부족 |
| 컬럼명/레이블 불일치 | 4 | 별칭 자유 생성 허용 |
| **합계** | **28** | (복수 패턴 중복 포함) |

---

## 시딩 업그레이드 우선순위

### 우선순위 1 — 프롬프트 수정 (`sql_generator.yaml`)

1. **CTR 계산식 고정**: `cot_template` Step 4에 명시
   ```
   - CTR = COUNT(CASE WHEN is_click = true THEN 1 END) * 1.0 / NULLIF(COUNT(*), 0)  ← 비율(0~1)
   - 퍼센트(%) 변환(*100) 금지 — ROUND, _percent suffix 사용 금지
   ```

2. **CVR 계산식 고정**:
   ```
   - CVR = COUNT(CASE WHEN is_conversion = true THEN 1 END) * 1.0 / NULLIF(COUNT(CASE WHEN is_click = true THEN 1 END), 0)
   - 분모는 반드시 클릭수 (전체 노출수 사용 금지)
   ```

3. **ROAS/CPA 계산식 고정**:
   ```
   - ROAS = SUM(CASE WHEN is_conversion=true THEN conversion_value ELSE 0 END) / NULLIF(SUM(cost_per_impression + cost_per_click), 0)
   - CPA = SUM(cost_per_impression + cost_per_click) / NULLIF(SUM(CASE WHEN is_conversion=true THEN 1 END), 0)
   ```

### 우선순위 2 — QA 예제 추가 (`seed_chromadb.py`)

- 날짜 범위 `IN` 패턴 예시 추가 (BETWEEN 대신)
- CVR 분모 올바른 예시 추가
- CASE 레이블 단순화 예시 (`오전` / `오후` — 괄호 없이)
- GROUP BY에 year/month 미포함 예시 추가

### 우선순위 3 — 평가 케이스 수정

- `오늘` 날짜 케이스 (T008, T022, T027, T033, T065) ground_truth를 과거 날짜로 변경하거나 skip 처리

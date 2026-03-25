# [Test Plan] ChromaDB 시딩 업그레이드 품질 검증

| 항목 | 내용 |
|------|------|
| **Feature** | chromadb-seed-upgrade |
| **테스트 방법** | TDD — pytest 단위 테스트 (외부 API 연결 없음) |
| **참고 설계서** | `docs/t1/text-to-sql/00_mvp_develop/02-design/05-sample-queries.md` |
| **대상 파일** | `services/vanna-api/scripts/seed_chromadb.py` |
| **테스트 파일** | `services/vanna-api/tests/unit/test_seed_chromadb.py` |
| **작성일** | 2026-03-22 |

---

## 테스트 목적

1. **편향 해소 검증**: `ad_combined_log` 예제가 충분히 포함됐는지
2. **카테고리 커버리지**: 설계서 59개 질문을 12개 카테고리로 묶어 각 카테고리 커버 확인
3. **SQL 품질 규칙**: NULLIF, 파티션 조건 등 Athena 규칙 준수 확인
4. **과적합 방지**: GROUP BY 차원 다양성, 날짜 분산, 테이블 편중도 측정

---

## 테스트 전략

`QA_EXAMPLES` 데이터를 직접 분석하는 **정적 품질 검사** 방식.
ChromaDB, Vanna, Athena 실제 연결 없이 Python만으로 실행.

---

## 테스트 케이스

### [구조 검증] TC-SD

#### TC-SD-01: QA_EXAMPLES 기본 구조 검증
| 항목 | 내용 |
|------|------|
| **목적** | 모든 QA 예제에 question, sql 키가 존재하고 비어있지 않은지 확인 |
| **사전 조건** | seed_chromadb.py 임포트 가능 |
| **입력** | QA_EXAMPLES 전체 리스트 |
| **기대 결과** | 모든 항목에 question(str), sql(str) 존재 |
| **검증 코드** | `assert "question" in qa and "sql" in qa` |

#### TC-SD-02: DDL 2개 테이블 정의 검증
| 항목 | 내용 |
|------|------|
| **목적** | ad_combined_log, ad_combined_log_summary DDL 모두 정의됐는지 확인 |
| **입력** | DDL_AD_COMBINED_LOG, DDL_AD_COMBINED_LOG_SUMMARY |
| **기대 결과** | CREATE TABLE 포함, summary에만 conversion_id 존재 |
| **검증 코드** | `assert "conversion_id" in DDL_SUMMARY and "conversion_id" not in DDL_LOG` |

#### TC-SD-03: Documentation 4개 문서 검증
| 항목 | 내용 |
|------|------|
| **목적** | 비즈니스 지표(CTR/CVR/ROAS/CPA/CPC), Athena 규칙, 정책, 용어사전 정의 확인 |
| **기대 결과** | 각 문서에 핵심 키워드 존재 |
| **검증 코드** | `assert "CTR" in BUSINESS_METRICS`, `assert "파티션" in ATHENA_RULES` 등 |

---

### [테이블 선택 정확성] TC-TB

#### TC-TB-01: ad_combined_log (hourly) 예제 수 검증
| 항목 | 내용 |
|------|------|
| **목적** | 편향 해소 — hourly 테이블 예제 최소 3개 확인 |
| **기대 결과** | `FROM ad_combined_log` (summary 제외) 예제 >= 3개 |
| **검증 코드** | `assert len(hourly_examples) >= 3` |

#### TC-TB-02: 시간대 분석 질문 → ad_combined_log 테이블 선택 정확성
| 항목 | 내용 |
|------|------|
| **목적** | "시간대" 포함 질문 예제가 반드시 ad_combined_log 사용하는지 확인 |
| **기대 결과** | 시간대 질문 예제 모두 ad_combined_log 사용 |
| **검증 코드** | `assert "FROM ad_combined_log" in qa["sql"] and "summary" not in qa["sql"]` |

#### TC-TB-03: 전환/CVR/ROAS 지표 → ad_combined_log_summary 사용 확인
| 항목 | 내용 |
|------|------|
| **목적** | conversion 데이터가 summary 테이블에만 있음을 예제가 반영하는지 확인 |
| **기대 결과** | CVR/ROAS/CPA/전환 질문 예제 전부 ad_combined_log_summary 사용 |
| **검증 코드** | `assert "ad_combined_log_summary" in qa["sql"]` |

---

### [NULLIF 규칙 준수] TC-NF

#### TC-NF-01: CVR 계산 예제 NULLIF 적용 확인
| 항목 | 내용 |
|------|------|
| **목적** | CVR 분모(클릭 수) 0 시 Division by Zero 방지 |
| **기대 결과** | CVR 계산 예제에 NULLIF 포함 |
| **검증 코드** | `assert "nullif" in qa["sql"].lower()` |

#### TC-NF-02: ROAS 계산 예제 NULLIF 적용 확인
| 항목 | 내용 |
|------|------|
| **목적** | ROAS 분모(광고비 합계) 0 시 오류 방지 |
| **기대 결과** | roas_percent 계산 SQL에 NULLIF 포함 |
| **검증 코드** | `assert "nullif" in roas_sql.lower()` |

#### TC-NF-03: CPA 계산 예제 NULLIF 적용 확인
| 항목 | 내용 |
|------|------|
| **목적** | CPA 분모(전환 수) 0 시 오류 방지 |
| **기대 결과** | CPA 계산 SQL에 NULLIF 포함 |
| **검증 코드** | `assert "nullif" in cpa_sql.lower()` |

#### TC-NF-04: CPC 계산 예제 NULLIF 적용 확인
| 항목 | 내용 |
|------|------|
| **목적** | CPC 분모(클릭 수) 0 시 오류 방지 |
| **기대 결과** | CPC 계산 SQL에 NULLIF 포함 |
| **검증 코드** | `assert "nullif" in cpc_sql.lower()` |

---

### [파티션 조건] TC-PT

#### TC-PT-01: 모든 SQL year 파티션 포함
| 항목 | 내용 |
|------|------|
| **목적** | Athena 풀스캔 방지 — year 조건 누락 예제 없는지 확인 |
| **기대 결과** | 21개 전 예제에 `year=` 조건 존재 |
| **검증 코드** | `assert "year=" not missing in any sql` |

#### TC-PT-02: 모든 SQL month 파티션 포함
| 항목 | 내용 |
|------|------|
| **목적** | Athena 비용 절감 — month 조건 누락 예제 없는지 확인 |
| **기대 결과** | `month=` 또는 `month IN` 모든 예제에 존재 |
| **검증 코드** | `assert len(missing) == 0` |

#### TC-PT-03: ad_combined_log SQL에 day 파티션 포함
| 항목 | 내용 |
|------|------|
| **목적** | hourly 테이블은 year+month+day 파티션 필수 |
| **기대 결과** | 모든 ad_combined_log 예제에 `AND day=` 조건 존재 |
| **검증 코드** | `assert "day=" in qa["sql"] or "AND day" in qa["sql"]` |

---

### [카테고리 커버리지] TC-CV (05-sample-queries.md 59개 → 12 카테고리)

| TC | 카테고리 | 대표 설계서 질문 | 판별 기준 |
|----|---------|--------------|---------|
| TC-CV-01 | C01 CTR | 일간 #1, #3, 주간 #1 | SQL에 `ctr_percent` 또는 `is_click` + `COUNT(*)` |
| TC-CV-02 | C02 CVR | 일간 #2, #15, 주간 #8 | SQL에 `cvr_percent` 또는 `is_conversion` + `is_click` |
| TC-CV-03 | C03 ROAS | 일간 관련, 주간 #관련 | SQL에 `roas` + `conversion_value` |
| TC-CV-04 | C04 CPA | 일간 #21 관련 | SQL에 `as cpa` |
| TC-CV-05 | C05 CPC | Documentation 정의 | SQL에 `as cpc` |
| TC-CV-06 | C06 시간대별 | 일간 #4, #17, #25 | SQL에 `hour` + `FROM ad_combined_log` |
| TC-CV-07 | C07 지역별 | 일간 #7, #19, #24 | SQL에 `delivery_region` |
| TC-CV-08 | C08 채널별 | 일간 #22, 주간 #3, #9 | SQL에 `platform` GROUP BY, 2개 이상 |
| TC-CV-09 | C09 기간비교 | 주간 #2, 월간 #4 | CTE(WITH) + 증감/growth 포함, 2개 이상 |
| TC-CV-10 | C10 3개월추이 | 월간 #15 | SQL에 `month IN` 또는 질문에 "3개월" |
| TC-CV-11 | C11 주중/주말 | 월간 #13 | SQL에 `day_of_week` 또는 질문에 "주말" |
| **TC-CV-12** | **C12 전환 0 탐지** | **일간 #10** | **`SUM(CAST(is_conversion AS INT)) = 0` in HAVING** |

> **TC-CV-12 예상 FAIL (Red Phase)**: 현재 "클릭 0" 예제만 있고 "전환 0" 예제 미존재

---

### [과적합 방지] TC-OV

| TC | 지표 | 임계값 | 근거 |
|----|------|-------|------|
| TC-OV-01 | campaign_id GROUP BY 편중도 | <= 40% | campaign_id만 반복 시 다른 차원 쿼리 생성 불가 |
| TC-OV-02 | month 값 다양성 | >= 3종 ('01', '02', '03') | 특정 월 암기 방지 |
| TC-OV-03 | ad_combined_log_summary 편중도 | <= 90% | hourly 테이블 예제 최소 확보 |
| TC-OV-04 | CTE(WITH) 패턴 수 | >= 2개 | 비교형 쿼리 학습 |
| TC-OV-05 | CASE WHEN 패턴 수 | >= 1개 | 조건부 집계 학습 |
| TC-OV-06 | GROUP BY 고유 차원 수 | >= 8종 | 다차원 집계 일반화 |
| TC-OV-07 | day_of_week() 함수 사용 | >= 1개 | 요일 함수 패턴 학습 |

---

## 예상 Red/Green 결과

| 단계 | 예상 결과 |
|------|---------|
| **Red Phase** | TC-CV-12 1건 FAIL (전환 0 탐지 예제 없음) |
| **Green Phase** | 전환 0 예제 추가 후 32개 전체 PASS |

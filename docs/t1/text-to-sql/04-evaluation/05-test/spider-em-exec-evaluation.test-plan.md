# [Test Plan] Spider EM/Exec 평가 체계

| 항목 | 내용 |
|------|------|
| **Feature** | spider-em-exec-evaluation |
| **테스트 방법** | TDD — pytest 단위 테스트 (Red → Green) |
| **참고 설계서** | `docs/t1/text-to-sql/04-evaluation/02-design/features/spider-em-exec-evaluation.design.md` |
| **작성일** | 2026-03-22 |

---

## 테스트 범위

**대상 모듈** (Design 문서 기반):
1. `SQLNormalizer` — SQL 정규화 (EM 계산용)
2. `ExecutionValidator` — Redash 연동 (SQL 실행 & 결과 비교)
3. `SpiderEvaluator` — 배치 평가 엔진

**테스트 유형**:
- Unit Test (각 클래스 메서드)
- Integration Test (Redash Mock 연동)
- Error Handling (타임아웃, 네트워크 오류)

---

## 테스트 케이스

### TC-SN-01: SQLNormalizer.normalize() — 공백 정규화
| 항목 | 내용 |
|------|------|
| **FR ID** | FR-05 (EM 계산 로직) |
| **목적** | SQL 공백 차이를 무시하고 정규화 |
| **사전 조건** | - |
| **테스트 입력** | `"SELECT  campaign_name  FROM  campaigns"` (연속 공백 있음) |
| **기대 결과** | `"SELECT CAMPAIGN_NAME FROM CAMPAIGNS"` |
| **검증 코드** | `assert normalize(input) == expected` |
| **주의사항** | 탭 → 공백 변환도 포함 |

---

### TC-SN-02: SQLNormalizer.normalize() — 주석 제거
| 항목 | 내용 |
|------|------|
| **FR ID** | FR-05 |
| **목적** | SQL 주석을 제거하고 정규화 |
| **사전 조건** | - |
| **테스트 입력** | `"SELECT campaign_name -- 캠페인 이름\nFROM campaigns"` |
| **기대 결과** | `"SELECT CAMPAIGN_NAME FROM CAMPAIGNS"` |
| **검증 코드** | `assert "--" not in normalize(input)` |

---

### TC-SN-03: SQLNormalizer.normalize() — 대문자 변환
| 항목 | 내용 |
|------|------|
| **FR ID** | FR-05 |
| **목적** | 소문자 SQL을 대문자로 정규화 |
| **사전 조건** | - |
| **테스트 입력** | `"select campaign_name from campaigns where year='2026'"` |
| **기대 결과** | `"SELECT CAMPAIGN_NAME FROM CAMPAIGNS WHERE YEAR = '2026'"` |
| **검증 코드** | `assert "select" not in normalize(input).lower()` |

---

### TC-SN-04: SQLNormalizer.exact_match() — 정확히 일치
| 항목 | 내용 |
|------|------|
| **FR ID** | FR-05 |
| **목적** | 두 SQL이 정규화 후 동일한지 판정 |
| **사전 조건** | - |
| **테스트 입력** | sql1: `"SELECT campaign_name FROM campaigns"`, sql2: `"select campaign_name from campaigns"` |
| **기대 결과** | `True` (정규화 후 동일) |
| **검증 코드** | `assert exact_match(sql1, sql2) == True` |

---

### TC-SN-05: SQLNormalizer.exact_match() — 다름
| 항목 | 내용 |
|------|------|
| **FR ID** | FR-05 |
| **목적** | 다른 SQL은 False 반환 |
| **사전 조건** | - |
| **테스트 입력** | sql1: `"SELECT campaign_name FROM campaigns"`, sql2: `"SELECT campaign_name, cost FROM campaigns"` |
| **기대 결과** | `False` (컬럼 다름) |
| **검증 코드** | `assert exact_match(sql1, sql2) == False` |

---

### TC-EV-01: ExecutionValidator.execute_sql() — 정상 실행 (Mock)
| 항목 | 내용 |
|------|------|
| **FR ID** | FR-03, FR-04 (SQL 실행) |
| **목적** | Redash API Mock에서 SQL 실행 및 결과 조회 |
| **사전 조건** | Redash API Mock 준비됨 |
| **테스트 입력** | sql: `"SELECT campaign_name, ctr FROM campaigns LIMIT 5"` |
| **기대 결과** | `{"rows": [...], "row_count": 5, "columns": [...]}`  |
| **검증 코드** | `assert result["row_count"] == 5` |
| **Mock 대상** | `requests.post`, `requests.get` |

---

### TC-EV-02: ExecutionValidator.execute_sql() — 타임아웃
| 항목 | 내용 |
|------|------|
| **FR ID** | FR-03, FR-04 |
| **목적** | 60초 이상 걸리면 타임아웃 처리 |
| **사전 조건** | Redash API Mock이 TimeoutError 발생 |
| **테스트 입력** | sql: (어떤 SQL이든) |
| **기대 결과** | `None` (타임아웃 반환) |
| **검증 코드** | `assert execute_sql(sql, timeout=1) is None` |

---

### TC-EV-03: ExecutionValidator.compare_results() — 결과 일치
| 항목 | 내용 |
|------|------|
| **FR ID** | FR-06 (Exec 계산) |
| **목적** | 두 쿼리 결과가 동일한지 판정 |
| **사전 조건** | - |
| **테스트 입력** | result1: `{"rows": [{"name": "A"}, {"name": "B"}], "row_count": 2, "columns": ["name"]}`, result2: (동일) |
| **기대 결과** | `True` |
| **검증 코드** | `assert compare_results(result1, result2) == True` |

---

### TC-EV-04: ExecutionValidator.compare_results() — 행 수 다름
| 항목 | 내용 |
|------|------|
| **FR ID** | FR-06 |
| **목적** | 행 수가 다르면 False |
| **사전 조건** | - |
| **테스트 입력** | result1: `{"rows": [...5개...], "row_count": 5}`, result2: `{"rows": [...3개...], "row_count": 3}` |
| **기대 결과** | `False` |
| **검증 코드** | `assert compare_results(result1, result2) == False` |

---

### TC-EV-05: ExecutionValidator.compare_results() — 데이터 다름
| 항목 | 내용 |
|------|------|
| **FR ID** | FR-06 |
| **목적** | 데이터 값이 다르면 False |
| **사전 조건** | - |
| **테스트 입력** | result1: `{"rows": [{"ctr": 0.085}]}`, result2: `{"rows": [{"ctr": 0.075}]}` |
| **기대 결과** | `False` |
| **검증 코드** | `assert compare_results(result1, result2) == False` |

---

### TC-SE-01: SpiderEvaluator.evaluate_single() — 정상 (EM & Exec 모두 1.0)
| 항목 | 내용 |
|------|------|
| **FR ID** | FR-02, FR-05, FR-06 |
| **목적** | 완벽한 테스트 케이스 평가 |
| **사전 조건** | Vanna Mock, Redash Mock 준비됨 |
| **테스트 입력** | test_case: `{id: "T001", question: "CTR...", ground_truth_sql: "...", ...}` |
| **기대 결과** | `SpiderEvalResult{em_score: 1.0, exec_score: 1.0, avg_score: 1.0}` |
| **검증 코드** | `assert result.em_score == 1.0 and result.exec_score == 1.0` |

---

### TC-SE-02: SpiderEvaluator.evaluate_single() — SQL 생성 실패
| 항목 | 내용 |
|------|------|
| **FR ID** | FR-02 |
| **목적** | Vanna API 실패 시 Graceful degradation |
| **사전 조건** | Vanna Mock이 Exception 발생 |
| **테스트 입력** | test_case: (어떤 케이스든) |
| **기대 결과** | `SpiderEvalResult{em_score: 0.0, exec_score: 0.0, error: "..."}` |
| **검증 코드** | `assert result.em_score == 0.0` |

---

### TC-SE-03: SpiderEvaluator.generate_report() — JSON 형식 생성
| 항목 | 내용 |
|------|------|
| **FR ID** | FR-07 |
| **목적** | 평가 결과를 JSON 리포트로 생성 |
| **사전 조건** | 3개 평가 결과 준비됨 |
| **테스트 입력** | results: `[SpiderEvalResult(...), ...]` (3개) |
| **기대 결과** | `{"total_cases": 3, "em": {"passed": 2, "accuracy": 0.67}, ...}` |
| **검증 코드** | `assert report["total_cases"] == 3 and report["em"]["accuracy"] == 0.67` |

---

### TC-SE-04: SpiderEvaluator.evaluate_batch() — 배치 평가 (3개)
| 항목 | 내용 |
|------|------|
| **FR ID** | FR-02 ~ FR-06 |
| **목적** | 여러 테스트 케이스를 순차 평가 |
| **사전 조건** | Vanna Mock, Redash Mock, 3개 test_case |
| **테스트 입력** | test_cases: `[T001, T002, T003]` |
| **기대 결과** | 3개 SpiderEvalResult 반환 |
| **검증 코드** | `assert len(results) == 3` |

---

## 테스트 순서 (우선순위)

1. **SQLNormalizer** (TC-SN-01 ~ TC-SN-05) — 의존성 없음, 빨리 테스트
2. **ExecutionValidator** (TC-EV-01 ~ TC-EV-05) — Mock Redash API
3. **SpiderEvaluator** (TC-SE-01 ~ TC-SE-04) — 통합 테스트

---

## Mock 전략

| 대상 | Mock 방식 | 이유 |
|------|----------|------|
| Redash API | `unittest.mock.patch` (requests) | 실제 API 호출 방지 |
| Vanna API | `MagicMock` | 외부 의존성 제거 |
| boto3 | `mock_dynamodb` (moto) | DynamoDB 로컬 테스트 |

---

## 예상 TC 통과율

| 단계 | 목표 |
|------|------|
| Red Phase | 14개 TC 전부 FAIL (구현 전) |
| Green Phase | 14개 TC 전부 PASS (구현 후) |

---

**테스트 계획서 끝**


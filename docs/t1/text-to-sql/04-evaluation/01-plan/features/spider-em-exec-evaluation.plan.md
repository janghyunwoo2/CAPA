# Plan: Spider EM/Exec 평가 체계 구축

**Feature**: Spider EM/Exec 평가 체계 구축
**작성일**: 2026-03-22
**담당자**: t1 (Text-to-SQL)
**예상 기간**: 1주 (5일)
**우선순위**: ⭐⭐⭐ (Phase 2 품질 검증 필수)

---

## Executive Summary

| 항목 | 설명 |
|------|------|
| **Problem** | Phase 2 구현 완료 후 Vanna API의 SQL 생성 정확도를 객관적으로 측정할 수 있는 평가 체계 부재. 현재는 96% Gap Match Rate로만 설계-구현 일치도만 측정 중. |
| **Solution** | Spider 벤치마크 기반 EM/Exec 평가 자동화. 자체 테스트 케이스 100개 정의 → 평가 스크립트 자동 실행 → 월간 정기 모니터링 |
| **Function & UX Effect** | 사용자가 Vanna API의 SQL 생성 성능(EM >= 85%, Exec >= 90%)을 수치화해서 볼 수 있음. 프롬프트 개선 시 즉시 효과 측정 가능 |
| **Core Value** | 지표 기반 개발(metric-driven development) 확립. Phase 3 최적화 시 효율성 평가(BIRD VES) 추가 가능. 데이터 기반 의사결정 |

---

## 1. 목표

### Primary Goal (Exec >= 90%)
Vanna API에서 생성한 SQL이 **정답 쿼리와 동일한 결과를 반환**하는 비율을 90% 이상 달성.

### Secondary Goal (EM >= 85%)
생성된 SQL이 **정답 SQL과 정확히 일치**하는 비율을 85% 이상 달성.

### Tertiary Goal (지속적 모니터링)
월 1회 자동화된 평가 스크립트 실행 → 성능 추이 추적 → 프롬프트 개선 근거 제공.

---

## 2. 범위 (Scope)

### 포함 항목 ✅
| 항목 | 설명 |
|------|------|
| **테스트 데이터 수집** | 자체 광고 도메인 테스트 케이스 100개 정의 |
| **SQL 정규화** | EM 계산용 SQL 정규화 로직 (공백, 주석, 대소문자 통일) |
| **평가 스크립트** | `spider_evaluation.py` — Vanna API 연동 + Redash 실행 + 결과 비교 |
| **평가 실행 스크립트** | `run_evaluation.py` — 배치 평가 + 리포트 생성 |
| **리포트 생성** | JSON 상세 결과 + Markdown 요약 리포트 |
| **자동화 (Docker)** | docker-compose에 spider-evaluator 서비스 추가 |
| **모니터링 대시보드** | 월간 성능 추이 기록 (`evaluation-results/`) |

### 제외 항목 ❌
| 항목 | 이유 |
|------|------|
| **BIRD VES (효율성)** | Phase 3에서 다룸. 현재는 정확도만 집중 |
| **RAGAS 평가** | Phase 4에서 다룸. 각 Step별 품질 평가 |
| **공개 Spider 데이터셋 사용** | 광고 도메인과 불일치. 자체 케이스 우선 |
| **프롬프트 자동 최적화** | 수동 개선 기반. 자동화는 향후 검토 |

---

## 3. 핵심 요구사항

### Functional Requirements

| FR# | 요구사항 | 우선순위 |
|-----|---------|--------|
| FR-01 | 테스트 케이스 JSON 포맷 정의 | ⭐⭐⭐ |
| FR-02 | Vanna API와 연동하여 SQL 자동 생성 | ⭐⭐⭐ |
| FR-03 | 정답 SQL 자동 실행 및 결과 조회 | ⭐⭐⭐ |
| FR-04 | 생성 SQL 자동 실행 및 결과 조회 | ⭐⭐⭐ |
| FR-05 | EM (Exact Match) 계산 로직 | ⭐⭐⭐ |
| FR-06 | Exec (Execution Accuracy) 계산 로직 | ⭐⭐⭐ |
| FR-07 | 평가 결과를 JSON으로 저장 | ⭐⭐⭐ |
| FR-08 | 평가 리포트를 Markdown으로 생성 | ⭐⭐ |
| FR-09 | Docker Compose 자동 실행 지원 | ⭐⭐ |
| FR-10 | 월간 성능 추이 추적 | ⭐ |

### Non-Functional Requirements

| NFR# | 요구사항 | 기준 |
|------|---------|------|
| NFR-01 | 100개 테스트 케이스 완료 시간 | < 30분 (병렬 실행) |
| NFR-02 | 개별 SQL 실행 타임아웃 | 60초 (LLM_TIMEOUT_SECONDS) |
| NFR-03 | 평가 결과 저장 형식 | JSON + Markdown |
| NFR-04 | 재현 가능성 | 동일 입력 → 동일 평가 결과 |
| NFR-05 | Graceful Degradation | SQL 생성 실패 시 EM=0, Exec=0 |

---

## 4. 구현 계획 (5일)

### Phase 1: 준비 (Day 1)
**작업**: 테스트 데이터 수집 + 폴더 구조 생성

- [ ] `docs/t1/text-to-sql/04-evaluation/` 폴더 생성
  ```
  04-evaluation/
  ├── 01-plan/
  │   └── features/
  │       └── spider-em-exec-evaluation.plan.md (본 문서)
  ├── 02-design/ (향후)
  ├── test-cases/
  │   └── test_cases.json (테스트 데이터 100개)
  ├── scripts/
  │   └── test_spider_evaluation.py
  ├── results/
  │   ├── latest-result.json
  │   ├── 2026-03-22-result.json
  │   └── evaluation-report.md
  └── README.md
  ```

- [ ] 테스트 케이스 100개 정의 (자체 광고 도메인)
  - CTR/CVR/ROAS 관련: 30개
  - 캠페인 성과 조회: 30개
  - 월별/주별 집계: 20개
  - 복잡한 조인/서브쿼리: 20개

- [ ] 각 케이스에 대해 정답 SQL + 예상 결과 정의
  - Redash에서 수동 실행 후 결과 저장

**Deliverable**: `test_cases.json` (100개 케이스, 크기 ~500KB)

---

### Phase 2: 평가 스크립트 구현 (Day 2-3)
**작업**: `test_spider_evaluation.py` 작성

- [ ] `SQLNormalizer` 클래스
  - SQL 정규화 (공백, 주석, 대소문자)
  - EM (Exact Match) 로직: `normalize(sql1) == normalize(sql2)`

- [ ] `ExecutionValidator` 클래스
  - Redash API 연동
  - SQL 실행 (타임아웃 60초)
  - 결과 비교 (행 수, 컬럼, 데이터)

- [ ] `SpiderEvaluator` 클래스
  - Vanna API에서 SQL 생성
  - EM/Exec 점수 계산
  - 배치 평가 (100개 케이스)
  - 리포트 생성

- [ ] Unit Tests
  - SQL 정규화 테스트
  - 결과 비교 로직 테스트
  - Graceful degradation 테스트

**Deliverable**: `test_spider_evaluation.py` (~400줄)

---

### Phase 3: 자동화 (Day 3-4)
**작업**: Docker Compose 통합 + 자동 실행

- [ ] Docker 이미지 생성
  - Vanna API 이미지 + 평가 스크립트
  - 의존성: boto3, requests, sqlparse

- [ ] `docker-compose.local-e2e.yml` 수정
  - `spider-evaluator` 서비스 추가
  - Vanna API, DynamoDB, Redash 의존성 설정

- [ ] 평가 결과 저장 자동화
  - 결과를 `results/` 폴더에 타임스탬프로 저장
  - `results/latest-result.json` 갱신

- [ ] 실행 스크립트 작성
  ```bash
  # 로컬 테스트
  bash run_spider_evaluation.sh local

  # Docker 기반 평가
  bash run_spider_evaluation.sh docker
  ```

**Deliverable**:
- `docker-compose.local-e2e.yml` 수정
- `run_spider_evaluation.sh` 스크립트
- 평가 결과 JSON + Markdown

---

### Phase 4: 리포트 생성 (Day 4-5)
**작업**: 평가 결과 요약 + 문서화

- [ ] 평가 리포트 생성
  ```markdown
  # Spider EM/Exec 평가 결과 (2026-03-22)

  ## 📊 요약
  - 총 테스트: 100건
  - EM 정확도: 82%
  - Exec 정확도: 91%
  - 평균 점수: 86.5%

  ## 📈 카테고리별 성과
  - CTR/CVR/ROAS: 85% / 88% / 92%
  - 캠페인 성과: 78% / 89%
  - 월별/주별: 80% / 85%
  - 복잡 쿼리: 70% / 92%

  ## 🔍 실패 사례 분석
  - T032: GROUP BY 누락 (EM ❌, Exec ❌)
  - T045: WHERE 조건 오류 (EM ❌, Exec ✅)

  ## 💡 개선 방향
  1. 프롬프트 개선: 집계 함수 명확화
  2. Few-shot 추가: 복잡 쿼리 예시
  ```

- [ ] 월간 추이 그래프 (Markdown 테이블)
  ```markdown
  | 월 | EM | Exec | 평균 | 개선점 |
  |-----|----|----|------|--------|
  | 3월 | 82% | 91% | 86.5% | - |
  | 4월 | TBD | TBD | TBD | 프롬프트 v2 |
  ```

- [ ] 가이드 문서
  - 테스트 케이스 추가 방법
  - 새로운 평가 실행 방법
  - 결과 해석 가이드

**Deliverable**:
- `evaluation-report-2026-03-22.md`
- 추이 데이터 (`results/metrics-history.json`)
- `README.md` (사용 가이드)

---

## 5. 리소스

### 필요 도구
| 도구 | 버전 | 용도 |
|------|------|------|
| Python | 3.11+ | 평가 스크립트 |
| Vanna AI | v0.5+ | SQL 생성 |
| Redash API | - | SQL 실행 |
| boto3 | 1.28+ | DynamoDB 접근 |
| Docker | 20.10+ | 자동화 |

### 기존 인프라 활용
- ✅ Redash 서버 (SQL 실행)
- ✅ DynamoDB (테스트 이력)
- ✅ Vanna API (도커화됨)
- ✅ ChromaDB (RAG 템플릿)

### 신규 구성
- 평가 스크립트 (600줄)
- 테스트 데이터 (JSON 500KB)
- Docker 서비스 추가

---

## 6. 위험 요소 (Risks)

| Risk | 영향도 | 대처 방안 |
|------|--------|---------|
| **Redash API 타임아웃** | 높음 | 타임아웃 60초 설정 + 재시도 로직 |
| **테스트 케이스 정답 오류** | 중간 | 수동 검증 + 샘플 10개 다중 검사 |
| **SQL 정규화 미흡** | 중간 | SQLParse 라이브러리 사용 + 테스트 보강 |
| **도메인 불일치** | 낮음 | 광고 데이터 기반 케이스만 선택 |
| **월간 자동화 실패** | 낮음 | Cron 모니터링 + 슬랙 알림 설정 |

---

## 7. 성공 기준 (Definition of Done)

### 개발 완료 조건
- [x] 테스트 케이스 10개 정의 완료 (정답 SQL 포함) — **2026-03-22 완료**
- [x] `spider_evaluation.py` 작성 완료 (SQLNormalizer, ExecutionValidator, SpiderEvaluator, 370줄) — **2026-03-22 완료**
- [x] Unit Tests 통과 (21/21 PASS, 90% Code Coverage) — **2026-03-22 완료**
- [x] 평가 실행 스크립트 완성 (`run_evaluation.py`) — **2026-03-22 완료**
- [ ] 로컬 평가 실행 완료 (100개 케이스 확대 후, < 30분)
- [ ] Docker 평가 자동화 완료

### 평가 기준
- [ ] EM 정확도 >= 85% 달성
- [ ] Exec 정확도 >= 90% 달성
- [ ] 평가 리포트 생성 (JSON + 실행 로그)
- [ ] 월간 추이 추적 시스템 구축 (선택)

### 문서화
- [x] Plan 문서 (본 문서, 2026-03-22 업데이트)
- [x] Design 문서 (아키텍처, 2026-03-22 완료)
- [x] Test Plan (14개 TC 정의, 2026-03-22 완료)
- [x] Test Result (21/21 PASS, 2026-03-22 완료)
- [ ] 평가 가이드 (README)

---

## 8. 평가 실행 방법

### Quick Start (로컬 실행)

```bash
cd services/vanna-api

# 1. 테스트 케이스 확인
cat test_cases.json

# 2. 평가 스크립트 실행
python run_evaluation.py

# 3. 결과 확인
cat evaluation_report.json
```

### 필수 환경 설정

```bash
# Vanna API 실행 (로컬)
docker-compose -f docker-compose.local-e2e.yml up -d vanna-api

# Redash 실행 (기존 인프라)
# 확인: http://localhost:5000

# 환경 변수 설정
export REDASH_API_KEY="your-api-key"
```

### 실행 결과 해석

**파일**: `evaluation_report.json`

```json
{
  "total_cases": 10,
  "em": {
    "passed": 8,
    "accuracy": 0.8
  },
  "exec": {
    "passed": 9,
    "accuracy": 0.9
  },
  "average": 0.85,
  "details": [...]
}
```

| 메트릭 | 목표 | 의미 |
|--------|------|------|
| EM | >= 85% | SQL 구조 정확도 (공백/주석 무시) |
| Exec | >= 90% | 실행 결과 정확도 (데이터 일치) |
| Average | >= 87% | 전체 평균 점수 |

### 고급 옵션

```bash
# 특정 케이스 수만 평가
python run_evaluation.py --limit 10

# 커스텀 API URL
python run_evaluation.py --vanna-url http://vanna-api:8000 \
                          --redash-url http://redash:5000

# 결과를 다른 파일로 저장
python run_evaluation.py --output results/eval-2026-03-22.json
```

---

## 9. 다음 단계

### Phase 2 → Phase 3 (Design 단계)
1. ✅ 본 Plan 승인
2. 📋 Design 문서 작성
   - 평가 아키텍처
   - 데이터 흐름도
   - API 스펙
   - 에러 처리 전략

3. 🚀 Implementation (Do 단계)
   - 스크립트 작성 + 테스트 실행

4. 🔍 Gap Analysis (Check 단계)
   - Design vs Implementation 비교

---

## 부록 A: 테스트 케이스 샘플

**파일**: `test_cases.json`

```json
[
  {
    "id": "T001",
    "category": "basic_metrics",
    "question": "지난주 CTR이 가장 높은 캠페인 5개",
    "ground_truth_sql": "SELECT campaign_name, ctr FROM campaigns WHERE date >= '2026-03-15' AND date <= '2026-03-21' ORDER BY ctr DESC LIMIT 5",
    "expected_columns": ["campaign_name", "ctr"],
    "expected_row_count_range": [1, 5],
    "difficulty": "easy"
  },
  {
    "id": "T032",
    "category": "aggregation",
    "question": "캠페인별 이번달 총 광고비는?",
    "ground_truth_sql": "SELECT campaign_name, SUM(cost) as total_cost FROM campaigns WHERE year='2026' AND month='03' GROUP BY campaign_name ORDER BY total_cost DESC",
    "expected_columns": ["campaign_name", "total_cost"],
    "expected_row_count_range": [1, 100],
    "difficulty": "medium"
  },
  {
    "id": "T065",
    "category": "complex_query",
    "question": "지난달 매출이 100M 이상이고 ROI가 3배 이상인 캠페인의 월별 성과는?",
    "ground_truth_sql": "SELECT c1.campaign_name, c1.year, c1.month, c1.revenue, c1.cost, c1.roi FROM campaigns c1 WHERE c1.year='2026' AND c1.month='02' AND c1.revenue >= 100000000 AND c1.roi >= 3.0 ORDER BY c1.roi DESC",
    "expected_columns": ["campaign_name", "year", "month", "revenue", "cost", "roi"],
    "expected_row_count_range": [0, 50],
    "difficulty": "hard"
  }
]
```

---

**계획 문서 끝**


# Design: Spider EM/Exec 평가 체계

**Feature**: Spider EM/Exec 평가 체계 구축
**작성일**: 2026-03-22
**기반**: Plan 문서 (`01-plan/features/spider-em-exec-evaluation.plan.md`)
**참조 기술**: Python 3.11, boto3, sqlparse, Redash API

---

## 목차

1. [Executive Summary](#executive-summary)
2. [아키텍처 개요](#아키텍처-개요)
3. [모듈 설계](#모듈-설계)
4. [데이터 흐름](#데이터-흐름)
5. [API & 인터페이스](#api--인터페이스)
6. [에러 처리](#에러-처리)
7. [구현 순서](#구현-순서)

---

## Executive Summary

| 항목 | 설명 |
|------|------|
| **설계 목표** | Vanna API의 SQL 생성 정확도를 자동으로 평가하는 확장 가능한 시스템 |
| **핵심 모듈** | SQLNormalizer (정규화), ExecutionValidator (Redash 연동), SpiderEvaluator (배치 실행) |
| **의존성** | Redash API, Vanna API, boto3, sqlparse |
| **신규 파일** | `test_spider_evaluation.py` (~600줄), `test_cases.json` (~100개), `run_spider_evaluation.sh` |
| **기존 수정** | `docker-compose.local-e2e.yml` (spider-evaluator 서비스 추가) |

---

## 아키텍처 개요

### 전체 흐름도

```
┌────────────────────────────────────────────────────────────┐
│  평가 초기화                                               │
│  ├─ test_cases.json 로드 (100개 테스트)                   │
│  ├─ Vanna API 연결 확인                                    │
│  └─ Redash 연결 확인                                       │
└────────────────┬─────────────────────────────────────────┘
                 ↓
         ┌───────────────────────┐
         │ for each test case:   │
         ├───────────────────────┤
         │                       │
         │ Step 1: 정답 SQL 실행 │  ← ExecutionValidator
         │   → ground_truth_result
         │                       │
         │ Step 2: Vanna SQL 생성│  ← SpiderEvaluator
         │   → generated_sql
         │                       │
         │ Step 3: 생성 SQL 실행 │  ← ExecutionValidator
         │   → generated_result  │
         │                       │
         │ Step 4: 평가 계산    │  ← SQLNormalizer + 비교 로직
         │   → em_score, exec_score
         │                       │
         │ Step 5: 결과 저장    │
         │   → results.json     │
         │                       │
         └───────────────────────┘
                 ↓
    ┌────────────────────────────┐
    │  리포트 생성               │
    │  ├─ JSON 상세 결과        │
    │  └─ Markdown 요약         │
    └────────────────────────────┘
```

### 3-Tier 아키텍처

```
┌──────────────────────────────────────────────────────────┐
│  Presentation Layer (리포트)                              │
│  ├─ evaluation-report.md (Markdown)                      │
│  ├─ {date}-result.json (JSON)                           │
│  └─ metrics-history.json (추이)                         │
└────────────────────┬─────────────────────────────────────┘
                     ↑
┌────────────────────┴──────────────────────────────────────┐
│  Business Logic Layer (평가 엔진)                         │
│  ├─ SpiderEvaluator                                     │
│  │  └─ evaluate_batch() → 100개 병렬 평가               │
│  ├─ SQLNormalizer                                       │
│  │  └─ normalize() → EM 계산                            │
│  └─ ExecutionValidator                                 │
│     └─ execute_sql() → Redash 연동                      │
└────────────────────┬──────────────────────────────────────┘
                     ↑
┌────────────────────┴──────────────────────────────────────┐
│  Data Layer (외부 시스템)                                 │
│  ├─ Vanna API (SQL 생성)                                │
│  ├─ Redash (SQL 실행)                                   │
│  ├─ Athena (쿼리 엔진)                                  │
│  └─ test_cases.json (테스트 데이터)                      │
└──────────────────────────────────────────────────────────┘
```

---

## 모듈 설계

### 1. SQLNormalizer (SQL 정규화)

**목적**: EM 계산 시 SQL 문법적 차이 무시

**메서드**:
```python
class SQLNormalizer:
    @staticmethod
    def normalize(sql_str: str) -> str:
        """
        SQL을 정규화된 형식으로 변환

        처리:
        1. 주석 제거 (-- /* */)
        2. 공백 통일 (탭→공백, 연속 공백→1칸)
        3. 대문자 변환 (SELECT → SELECT)
        4. 키워드 주변 공백 정규화 (FROM → FROM 앞뒤 공백)

        반환: 정규화된 SQL 문자열
        """

    @staticmethod
    def exact_match(sql1: str, sql2: str) -> bool:
        """
        두 SQL이 정확히 일치하는가?

        로직:
        normalize(sql1) == normalize(sql2)
        """
```

**의존성**:
- `re` (정규표현식)
- `sqlparse` (SQL 파싱)

**입출력 예시**:
```
입력 (sql1):
  SELECT campaign_name, SUM(cost) as total
  FROM campaigns WHERE year='2026'
  GROUP BY campaign_name

입력 (sql2):
  SELECT campaign_name,
         SUM(cost) AS total
  FROM   campaigns
  WHERE  year = '2026'
  GROUP BY campaign_name

정규화 결과:
  SELECT CAMPAIGN_NAME, SUM(COST) AS TOTAL FROM CAMPAIGNS WHERE
  YEAR = '2026' GROUP BY CAMPAIGN_NAME

exact_match() → True ✅
```

---

### 2. ExecutionValidator (SQL 실행 & 비교)

**목적**: Redash API를 통해 SQL 실행 및 결과 검증

**메서드**:
```python
class ExecutionValidator:
    def __init__(self, redash_api_key: str, redash_base_url: str):
        """Redash 클라이언트 초기화"""

    def execute_sql(self, sql: str, timeout_seconds: int = 60) -> Optional[dict]:
        """
        Redash에서 SQL 실행

        프로세스:
        1. 임시 쿼리 생성 (POST /api/queries)
        2. 쿼리 실행 (POST /api/queries/{id}/refresh)
        3. 결과 조회 (GET /api/query_results/{hash})

        반환:
        {
            "rows": [
                {col1: val1, col2: val2, ...},
                ...
            ],
            "row_count": int,
            "columns": ["col1", "col2", ...]
        }

        예외:
        - ClientError: Redash API 오류
        - Timeout: 60초 초과
        """

    def compare_results(self, result1: dict, result2: dict) -> bool:
        """
        두 쿼리 결과가 같은가?

        비교 기준:
        1. 행 수 동일 (row_count)
        2. 컬럼 동일 (columns set)
        3. 데이터 값 동일 (rows, 순서 무관)

        알고리즘:
        - 각 행을 JSON 문자열로 변환
        - 정렬 (순서 무관)
        - 비교
        """
```

**API 상세**:

```
POST /api/queries
{
  "query": "SELECT campaign_name FROM campaigns LIMIT 5",
  "data_source_id": 1  # Athena
}
응답:
{
  "id": 12345,
  ...
}

POST /api/queries/12345/refresh
응답:
{
  "query_hash": "abc123def456",
  ...
}

GET /api/query_results/abc123def456
응답:
{
  "query_result": {
    "data": {
      "columns": [
        {"name": "campaign_name", "type": "string"},
        ...
      ],
      "rows": [
        {"campaign_name": "A"},
        {"campaign_name": "B"},
        ...
      ]
    }
  }
}
```

**의존성**:
- `requests` (HTTP)
- `json` (JSON 파싱)

---

### 3. SpiderEvaluator (배치 평가 엔진)

**목적**: 100개 테스트 케이스를 자동으로 평가

**메서드**:
```python
class SpiderEvaluator:
    def __init__(self, vanna_api_url: str, redash_api_key: str):
        """평가 엔진 초기화"""

    def evaluate_single(self, test_case: dict, vanna_client) -> SpiderEvalResult:
        """
        단일 테스트 케이스 평가 (5단계)

        1. Vanna에서 SQL 생성
           input: question
           output: generated_sql

        2. 정답 SQL 실행
           input: ground_truth_sql
           output: gt_result (행 수, 컬럼, 데이터)

        3. 생성 SQL 실행
           input: generated_sql
           output: gen_result (행 수, 컬럼, 데이터)

        4. EM 계산
           em_score = 1 if normalize(generated) == normalize(gt) else 0

        5. Exec 계산
           exec_score = 1 if compare(gen_result, gt_result) else 0

        반환:
        SpiderEvalResult {
            test_id: str,
            question: str,
            generated_sql: str,
            ground_truth_sql: str,
            em_score: float,
            exec_score: float,
            avg_score: float,
            error: Optional[str]
        }
        """

    def evaluate_batch(self, test_cases: list, vanna_client) -> list[SpiderEvalResult]:
        """
        배치 평가 (100개 병렬 실행)

        로직:
        for each test_case in test_cases:
            result = evaluate_single(test_case)
            results.append(result)

        반환: [SpiderEvalResult, ...]

        성능:
        - 순차 실행: ~30분 (100개 × 18초/케이스)
        - 병렬 실행: ~10분 (max_workers=5)
        """

    def generate_report(self, results: list[SpiderEvalResult]) -> dict:
        """
        평가 리포트 생성

        출력:
        {
            "total_cases": 100,
            "em": {"passed": 82, "accuracy": 0.82},
            "exec": {"passed": 91, "accuracy": 0.91},
            "average": 0.865,
            "details": [...]
        }
        """
```

**데이터 모델**:
```python
@dataclass
class SpiderEvalResult:
    test_id: str          # "T001"
    question: str         # "지난주 CTR이..."
    generated_sql: str    # 생성된 SQL
    ground_truth_sql: str # 정답 SQL
    em_score: float       # 0.0 or 1.0
    exec_score: float     # 0.0 or 1.0
    exec_error: Optional[str] = None
    avg_score: float = 0.0
```

**의존성**:
- `SQLNormalizer`
- `ExecutionValidator`
- Vanna API client
- `logging`

---

## 데이터 흐름

### 1. 입력 (Input)

**test_cases.json**:
```json
[
  {
    "id": "T001",
    "category": "basic_metrics",
    "question": "지난주 CTR이 가장 높은 캠페인 5개",
    "ground_truth_sql": "SELECT campaign_name, AVG(ctr) as avg_ctr FROM campaigns WHERE year='2026' AND month='03' AND day >= '15' AND day <= '21' GROUP BY campaign_name ORDER BY avg_ctr DESC LIMIT 5",
    "difficulty": "easy"
  }
]
```

**스키마**:
```python
{
    "id": str,                    # 테스트 ID (T001 ~ T100)
    "category": str,              # 카테고리 (basic_metrics, aggregation 등)
    "question": str,              # 사용자 질문 (자연어)
    "ground_truth_sql": str,      # 정답 SQL
    "expected_columns": list[str],# 예상 컬럼 (optional)
    "expected_row_count_range": [int, int], # 예상 행 수 범위
    "difficulty": str             # 난이도 (easy, medium, hard)
}
```

---

### 2. 처리 (Processing)

#### 흐름 다이어그램

```
test_case: T001
  ↓
[Step 1] Vanna SQL 생성
  question: "지난주 CTR이..."
  → vanna_client.generate_sql(question)
  → generated_sql: "SELECT campaign_name, AVG(ctr)..."

  에러 처리:
  ├─ LLM 타임아웃 → em_score=0, exec_score=0
  ├─ 빈 SQL 반환 → em_score=0, exec_score=0
  └─ API 오류 → 로깅 + graceful degradation
  ↓

[Step 2] 정답 SQL 실행
  ground_truth_sql: "SELECT campaign_name..."
  → ExecutionValidator.execute_sql(ground_truth_sql)
  → gt_result: {rows: [...], row_count: 5, columns: [...]}

  에러 처리:
  ├─ Redash 타임아웃 → em_score=0, exec_score=0
  ├─ SQL 문법 오류 → 로깅 + 스킵
  └─ 네트워크 오류 → 재시도 (최대 3회)
  ↓

[Step 3] 생성 SQL 실행
  generated_sql: "SELECT campaign_name..."
  → ExecutionValidator.execute_sql(generated_sql)
  → gen_result: {rows: [...], row_count: 5, columns: [...]}
  ↓

[Step 4] EM 계산
  em_score = SQLNormalizer.exact_match(
      generated_sql,
      ground_truth_sql
  ) ? 1.0 : 0.0
  ↓

[Step 5] Exec 계산
  exec_score = ExecutionValidator.compare_results(
      gen_result,
      gt_result
  ) ? 1.0 : 0.0
  ↓

결과 저장
  SpiderEvalResult {
      test_id: "T001",
      em_score: 1.0,
      exec_score: 1.0,
      avg_score: 1.0
  }
```

---

### 3. 출력 (Output)

#### JSON 결과 (`{date}-result.json`)

```json
{
  "total_cases": 100,
  "em": {
    "passed": 82,
    "accuracy": 0.82
  },
  "exec": {
    "passed": 91,
    "accuracy": 0.91
  },
  "average": 0.865,
  "details": [
    {
      "test_id": "T001",
      "question": "지난주 CTR이...",
      "em": 1.0,
      "exec": 1.0,
      "avg": 1.0,
      "error": null
    },
    {
      "test_id": "T032",
      "question": "캠페인별 이번달...",
      "em": 0.0,
      "exec": 0.0,
      "avg": 0.0,
      "error": "GROUP BY 누락"
    }
  ]
}
```

#### Markdown 리포트 (`evaluation-report.md`)

```markdown
# Spider EM/Exec 평가 결과 (2026-03-22)

## 📊 요약
- 총 테스트: 100건
- EM 정확도: 82%
- Exec 정확도: 91%
- 평균 점수: 86.5%

## 📈 카테고리별 분석
| 카테고리 | EM | Exec | 개수 |
|---------|----|----|------|
| 단순 조회 | 95% | 98% | 20건 |
| 집계함수 | 78% | 88% | 30건 |
| ...     | ... | ... | ...  |

## ❌ 실패 분석
...

## 💡 개선 방향
...
```

---

## API & 인터페이스

### Vanna API

```python
# 초기화
vanna_instance = VannaAthena(
    api_key=os.getenv("ANTHROPIC_API_KEY"),
    model="claude-3-sonnet-20240229",
)

# SQL 생성
sql = vanna_instance.generate_sql(
    question="지난주 CTR이 높은 캠페인 5개",
    # 내부적으로:
    # 1. ChromaDB에서 유사 SQL 템플릿 검색 (RAG)
    # 2. Claude로 SQL 생성
    # 3. 생성된 SQL 반환
)
```

### Redash API

```python
# 임시 쿼리 생성
POST /api/queries
{
  "query": "SELECT campaign_name FROM campaigns LIMIT 5",
  "data_source_id": 1
}
Response:
{
  "id": 12345
}

# 쿼리 실행
POST /api/queries/12345/refresh
Response:
{
  "query_hash": "abc123"
}

# 결과 조회
GET /api/query_results/abc123
Response:
{
  "query_result": {
    "data": {
      "rows": [...],
      "columns": [...]
    }
  }
}
```

---

## 에러 처리

### 1. SQL 생성 실패

```python
try:
    sql = vanna_client.generate_sql(question)
except Exception as e:
    logger.error(f"[{test_id}] SQL 생성 실패: {e}")
    return SpiderEvalResult(
        test_id=test_id,
        em_score=0.0,
        exec_score=0.0,
        exec_error=str(e)
    )
```

### 2. SQL 실행 타임아웃

```python
with ThreadPoolExecutor(max_workers=1) as executor:
    future = executor.submit(execute_sql, sql)
    try:
        result = future.result(timeout=60)  # 60초
    except TimeoutError:
        logger.error(f"[{test_id}] SQL 실행 타임아웃")
        return error_result
```

### 3. 결과 비교 오류

```python
def compare_results(result1, result2) -> bool:
    try:
        # 행 수, 컬럼, 데이터 비교
        return rows_equal and columns_equal and data_equal
    except Exception as e:
        logger.error(f"결과 비교 실패: {e}")
        return False  # False로 처리 (Exec = 0)
```

### 4. Graceful Degradation

```
SQL 생성 실패
  ↓
em_score = 0, exec_score = 0 설정
  ↓
다음 테스트 케이스로 계속 진행
  ↓
전체 평가 완료 후 리포트 생성
```

---

## 구현 순서

### 우선순위 (높음 → 낮음)

| 순서 | 모듈 | 파일 | 라인수 | 의존성 |
|------|------|------|--------|--------|
| 1 | SQLNormalizer | `test_spider_evaluation.py` | 50 | sqlparse, re |
| 2 | ExecutionValidator | `test_spider_evaluation.py` | 150 | requests |
| 3 | SpiderEvaluator | `test_spider_evaluation.py` | 250 | 위 2개 |
| 4 | 테스트 데이터 | `test_cases.json` | ~2000 | - |
| 5 | 실행 스크립트 | `run_spider_evaluation.sh` | 50 | - |
| 6 | Docker 통합 | `docker-compose.local-e2e.yml` | 30 | - |
| 7 | 리포트 생성 | `test_spider_evaluation.py` | 100 | - |

### 단계별 산출물

| 단계 | 산출물 | 기준 |
|------|--------|------|
| Step 1 | `test_spider_evaluation.py` (SQLNormalizer) | Unit Test 통과 |
| Step 2 | `test_spider_evaluation.py` (ExecutionValidator) | Redash 연동 확인 |
| Step 3 | `test_spider_evaluation.py` (SpiderEvaluator) | 배치 평가 가능 |
| Step 4 | `test_cases.json` (100개) | 모든 케이스 정답 SQL 정의 |
| Step 5 | `run_spider_evaluation.sh` | 로컬/Docker 실행 가능 |
| Step 6 | `docker-compose.local-e2e.yml` | Docker 자동 실행 |
| Step 7 | `evaluation-report.md` | 월간 리포트 생성 |

---

## 주요 설계 결정

| 결정사항 | 선택안 | 이유 |
|---------|--------|------|
| **SQL 비교 방식** | 정규화 후 문자열 비교 | 간단함, 빠름 |
| **결과 비교 순서** | 순서 무관 | 동일한 데이터가 다른 순서로 나올 수 있음 |
| **타임아웃** | 60초 | LLM + DB 쿼리 시간 고려 |
| **병렬도** | max_workers=5 | Redash API 레이트 제한 고려 |
| **테스트 수** | 100개 | 통계적 의미 있음 + 30분 소요 |
| **리포트 형식** | JSON + Markdown | 자동화 + 가독성 |

---

## 다음 단계 (Do 단계)

1. ✅ Design 완료
2. → Do: `test_spider_evaluation.py` 구현 시작
3. → Check: Gap 분석
4. → Report: 평가 리포트 생성

---

**설계 문서 끝**


# CAPA Text-to-SQL 구현 계획서

> **버전**: v1.0  
> **작성일**: 2026-03-06  
> **연관 문서**: [참고 자료 요약](./reference_summary.md) | [MVP 코드](../../services/vanna-api/) | [프로젝트 컨셉 v4](../project_concept/project_concept_v4.md)

---

## 1. 현황 분석

### 1.1 MVP 코드 현황 (`services/vanna-api`)

현재 MVP로 구현된 `vanna-api`는 다음 구조를 가집니다:

```
services/vanna-api/
├── Dockerfile
├── requirements.txt
└── src/
    ├── main.py          # FastAPI 메인 서버
    └── train_dummy.py   # 더미 학습 데이터 주입 스크립트
```

**구현된 기능**:
| 엔드포인트 | 설명 | 상태 |
|-----------|------|------|
| `GET /health` | 헬스 체크 | ✅ 완료 |
| `POST /query` | 자연어 → SQL 생성 + Athena 실행 + AI 요약 | ✅ 완료 |
| `POST /generate-sql` | 자연어 → SQL만 생성 (실행 X) | ✅ 완료 |
| `POST /train` | DDL/문서/SQL 예제 학습 데이터 추가 | ✅ 완료 |
| `GET /training-data` | 저장된 학습 데이터 조회 | ✅ 완료 |
| `POST /summarize` | AI 데이터 요약 | ✅ 완료 |

**기술 스택**:
- **LLM**: Anthropic Claude (claude-haiku-4-5)
- **Vector DB**: ChromaDB (External HTTP Client)
- **Query Engine**: AWS Athena
- **Framework**: Vanna AI + FastAPI

### 1.2 MVP 코드의 한계점

참고 자료 분석을 통해 현재 MVP의 개선이 필요한 영역을 도출했습니다:

| 한계점 | 영향 | 우선순위 |
|--------|------|---------|
| SQL 검증 로직 없음 | 잘못된 SQL이 Athena에서 실행되어 비용 낭비 | 🔴 높음 |
| 학습 데이터의 품질 관리 체계 없음 | RAG 성능 저하 → 쿼리 품질 불안정 | 🔴 높음 |
| 광고 도메인 특화 문서/정책 데이터 미흡 | CTR/ROAS 계산식 등 비즈니스 규칙 반영 안됨 | 🔴 높음 |
| 오류 처리 미흡 | SQL 실패 시 사용자에게 불명확한 메시지 | 🟡 중간 |
| Q&A 예제 SQL 부재 | Few-shot 학습 없어 복잡한 쿼리 생성 품질 낮음 | 🟡 중간 |
| 의도 분류 없음 | 범위 외 질문도 SQL 생성 시도 | 🟡 중간 |

---

## 2. 목표 아키텍처

### 2.1 전체 흐름 (확장 단계 목표)

```
[Slack Bot]
    │
    ▼
[vanna-api (FastAPI)]
    │
    ├─── 1. 질문 정제 (인사말/노이즈 제거)
    │
    ├─── 2. 의도 분류 (SQL조회 / 일반질문 / 범위외)
    │
    └─── [SQL 조회 의도]
             │
             ├─── 3. ChromaDB RAG 검색
             │       ├── Q&A 예제 SQL 검색
             │       ├── 테이블 스키마 검색
             │       └── 정책/도메인 문서 검색
             │
             ├─── 4. SQL 생성 (Claude API)
             │
             ├─── 5. SQL 검증 (Athena EXPLAIN)
             │       ├── 성공 → 실행
             │       └── 실패 → 재시도 (최대 2회)
             │
             ├─── 6. Athena 실행 (run_sql)
             │
             ├─── 7. 결과 요약 (Claude API)
             │
             └─── 8. Slack 응답 (SQL + 결과 + 요약)
```

### 2.2 컴포넌트별 역할

| 컴포넌트 | 역할 | 현재 상태 |
|---------|------|----------|
| **vanna-api** | Text-to-SQL 핵심 서비스 | ✅ MVP 완료 |
| **ChromaDB** | 벡터 DB (스키마/Q&A/정책 저장) | ✅ 연결 완료 |
| **Athena** | SQL 실행 엔진 | ✅ 연결 완료 |
| **Claude API** | SQL 생성 + 결과 요약 LLM | ✅ 연결 완료 |
| **Slack Bot** | 사용자 인터페이스 | 별도 서비스 |

---

## 3. 단계별 구현 계획

### Phase 1: 학습 데이터 품질 강화 (최우선)

> **핵심 교훈**: "모델 성능"보다 "참조 데이터 품질"이 실무 성능을 결정한다.

#### 3.1.1 Athena 스키마 문서화

현재 `train_dummy.py`에는 기본 DDL만 있습니다. 다음 항목을 보강해야 합니다:

```python
# 현재 (부족한 상태)
{"ddl": "CREATE EXTERNAL TABLE ad_events_raw (event_id string, ...)"}

# 목표 (상세 문서화)
{
    "ddl": "CREATE EXTERNAL TABLE ad_events_raw (...)",
    "documentation": """
    [테이블 설명]
    ad_events_raw: 광고 로그 원시 데이터 테이블
    
    [컬럼 설명]
    - event_id: 이벤트 고유 식별자 (UUID)
    - event_type: 이벤트 유형 ('impression'=노출, 'click'=클릭, 'conversion'=전환)
    - campaign_id: 광고 캠페인 식별자
    - bid_price: 이벤트당 비용 (단위: KRW)
    
    [파티션 구조]
    year/month/day 파티션으로 분리됨. 날짜 범위 조회 시 반드시 파티션 조건 포함 필요.
    예: WHERE year='2026' AND month='03' AND day='06'
    """
}
```

**구현할 학습 데이터 카테고리**:

```
1. DDL (테이블 스키마)
   - ad_events_raw
   - ad_performance_daily (Airflow로 집계된 일별 성과 테이블)

2. 도메인 문서 (비즈니스 규칙)
   - CTR 계산식: clicks / impressions * 100
   - ROAS 계산식: conversion_revenue / ad_spend * 100
   - 파티션 쿼리 기본 패턴
   - 광고 도메인 용어 사전

3. Q&A 예제 SQL (최소 10개)
   - 기간별 캠페인 성과 조회
   - CTR 상위/하위 캠페인
   - 일별 광고 비용 트렌드
   - 디바이스별 클릭률
   - 캠페인별 전환율
```

#### 3.1.2 학습 데이터 파일 구조 설계

```
services/vanna-api/
└── training_data/
    ├── ddl/
    │   ├── ad_events_raw.sql        # 원시 로그 테이블 DDL
    │   └── ad_performance_daily.sql # 일별 집계 테이블 DDL
    ├── docs/
    │   ├── business_metrics.md      # CTR, ROAS, CVR 정의
    │   ├── partition_guide.md       # Athena 파티션 쿼리 가이드
    │   └── domain_glossary.md       # 광고 도메인 용어 사전
    └── qa_examples/
        ├── campaign_performance.json # 캠페인 성과 관련 Q&A
        ├── time_series.json          # 시계열 분석 Q&A
        └── comparison.json           # 비교 분석 Q&A
```

---

### Phase 2: SQL 검증 로직 추가

DableTalk의 핵심 기능인 **SQL EXPLAIN 검증**을 추가합니다.

#### 3.2.1 Athena EXPLAIN 검증

```python
# main.py에 추가할 검증 로직 (개념)

async def validate_sql(sql: str, vanna: VannaAthena) -> tuple[bool, str]:
    """EXPLAIN으로 SQL 유효성 사전 검증"""
    try:
        explain_sql = f"EXPLAIN {sql}"
        vanna.athena_client.start_query_execution(
            QueryString=explain_sql,
            QueryExecutionContext={"Database": vanna.athena_database},
            ResultConfiguration={"OutputLocation": vanna.s3_staging_dir},
        )
        # 실행 결과 확인...
        return True, ""
    except Exception as e:
        return False, str(e)
```

#### 3.2.2 SQL 재시도 로직

```
SQL 생성
  ↓
EXPLAIN 검증
  ├── 성공 → 실행
  └── 실패 → 오류 메시지 포함해서 SQL 재생성 (최대 2회 재시도)
              └── 재시도 실패 → 사용자에게 오류 + 힌트 반환
```

---

### Phase 3: 의도 분류 추가

모든 질문을 SQL로 변환하려 하지 않고, 먼저 의도를 분류합니다.

#### 3.3.1 의도 분류 카테고리

| 의도 | 예시 | 처리 방식 |
|------|------|---------|
| `sql_query` | "어제 CTR 높은 캠페인 알려줘" | Text-to-SQL 플로우 진행 |
| `general_question` | "CTR이 뭐야?" | 도메인 문서로 답변 |
| `out_of_scope` | "날씨 어때?" | 범위 외 안내 메시지 반환 |

#### 3.3.2 구현 방식 (`/query` 엔드포인트 수정)

```python
# 의도 분류 추가 예시
class QueryResponse(BaseModel):
    intent: str                      # 추가: sql_query / general_question / out_of_scope
    sql: Optional[str] = None
    sql_valid: Optional[bool] = None # 추가: SQL 검증 결과
    results: Optional[List[Dict]] = None
    answer: Optional[str] = None
    error: Optional[str] = None
```

---

### Phase 4: 오류 처리 및 UX 개선

#### 3.4.1 응답 형식 개선

사용자 친화적인 응답 구조:

```json
{
  "sql": "SELECT campaign_id, COUNT(*) as clicks FROM ...",
  "sql_valid": true,
  "results": [...],
  "answer": "어제 기준 클릭수 상위 5개 캠페인입니다...",
  "metadata": {
    "tables_used": ["ad_events_raw"],
    "execution_time_ms": 1234,
    "row_count": 5
  }
}
```

#### 3.4.2 에러 메시지 구조화

```json
// SQL 생성 실패 시
{
  "error": "SQL_GENERATION_FAILED",
  "message": "질문을 SQL로 변환하지 못했습니다.",
  "hint": "더 구체적인 날짜 범위나 캠페인명을 포함해서 다시 질문해 주세요.",
  "original_question": "..."
}
```

---

## 4. 파일별 수정/추가 계획

### 4.1 수정 대상 파일

| 파일 | 수정 내용 | 우선순위 |
|------|---------|---------|
| `src/main.py` | SQL 검증 로직, 의도 분류, 응답 모델 강화 | Phase 2~3 |
| `src/train_dummy.py` | 상세 DDL + 도메인 문서 + Q&A 예제 추가 | Phase 1 |

### 4.2 추가 대상 파일

| 파일 | 설명 | 우선순위 |
|------|------|---------|
| `training_data/ddl/ad_events_raw.sql` | 원시 로그 테이블 상세 DDL + 컬럼 설명 | Phase 1 |
| `training_data/ddl/ad_performance_daily.sql` | 일별 집계 테이블 DDL | Phase 1 |
| `training_data/docs/business_metrics.md` | CTR, ROAS, CVR 계산식 정의 | Phase 1 |
| `training_data/docs/partition_guide.md` | Athena 파티션 쿼리 패턴 | Phase 1 |
| `training_data/qa_examples/*.json` | Q&A 예제 SQL 10개 이상 | Phase 1 |
| `src/validator.py` | SQL EXPLAIN 검증 모듈 | Phase 2 |
| `src/intent_classifier.py` | 의도 분류 모듈 | Phase 3 |
| `scripts/load_training_data.py` | 학습 데이터 일괄 로드 스크립트 | Phase 1 |

---

## 5. Q&A 예제 SQL 목록 (초기 구축 대상)

광고 도메인에서 자주 받을 질문들:

```
# 기간별 성과
1. "어제 전체 광고 클릭수와 노출수를 알려줘"
2. "이번주 일별 CTR 트렌드를 보여줘"
3. "지난달 캠페인별 총 광고비를 알려줘"

# 순위/비교
4. "지난 7일간 CTR이 가장 높은 캠페인 TOP 5"
5. "어제 클릭수가 가장 낮은 캠페인 3개"
6. "이번달 ROAS가 100% 이상인 캠페인 목록"

# 디바이스/세그먼트
7. "어제 디바이스 유형별 클릭수 비교"
8. "모바일 vs 데스크탑 CTR 차이"

# 이상/점검
9. "어제 클릭수가 0인 활성 캠페인 목록"
10. "지난 7일 동안 bid_price 합계가 가장 높은 날"
```

---

## 6. 프롬프트 엔지니어링 전략

InsightLens의 XML 구조 프롬프트를 CAPA에 맞게 적용:

```xml
<instructions>
당신은 AWS Athena SQL 전문가입니다.
- Athena Presto SQL 문법을 사용하세요.
- 테이블 파티션 조건(year, month, day)을 반드시 포함하세요.
- 결과 컬럼에는 반드시 한국어 alias를 붙이세요.
- 날짜 함수는 Athena 표준(date_parse, date_diff 등)을 사용하세요.
</instructions>

<table_schemas>
{검색된 테이블 스키마}
</table_schemas>

<qa_examples>
{유사 Q&A 예제 SQL}
</qa_examples>

<business_rules>
{CTR/ROAS 계산식, 파티션 규칙 등}
</business_rules>

<user_question>
{정제된 사용자 질문}
</user_question>
```

---

## 7. 구현 우선순위 로드맵

```
[현재 상태: MVP 완료]
         │
         ▼
[Phase 1: 2~3일] ← 최우선
학습 데이터 품질 강화
- Athena 테이블 스키마 상세 문서화
- 비즈니스 규칙(CTR/ROAS/파티션) 문서 작성
- Q&A 예제 SQL 10개 이상 구축
- 학습 데이터 일괄 로드 스크립트
         │
         ▼
[Phase 2: 1~2일]
SQL 검증 로직 추가
- Athena EXPLAIN 검증 모듈
- SQL 재시도 로직 (최대 2회)
- 실패 시 구조화된 오류 응답
         │
         ▼
[Phase 3: 1~2일]
의도 분류 추가
- LLM 기반 의도 분류 (sql_query / general / out_of_scope)
- 범위 외 질문 처리
         │
         ▼
[Phase 4: 1일]
UX/응답 개선
- 응답 모델 강화 (메타데이터 포함)
- 에러 메시지 구조화
         │
         ▼
[Slack Bot 연동]
- vanna-api 호출
- Slack 메시지 포맷팅
- SQL 코드블록 + 결과 테이블 포맷
```

---

## 8. 비용 및 성능 고려사항

### 8.1 Athena 쿼리 비용 절감

| 전략 | 설명 |
|------|------|
| **EXPLAIN 먼저** | 문법 오류 쿼리가 실제 데이터 스캔하지 않도록 |
| **파티션 강제** | 모든 쿼리에 날짜 파티션 조건 필수화 |
| **LIMIT 기본값** | 결과 조회 시 기본 100행 제한 |
| **쿼리 결과 캐싱** | 동일 쿼리 반복 시 S3 결과 재사용 |

### 8.2 LLM 비용 절감

| 전략 | 설명 |
|------|------|
| **Claude Haiku** | 현재 가장 저렴한 Anthropic 모델 사용 중 (유지) |
| **RAG로 컨텍스트 최적화** | 관련 스키마만 선택적으로 프롬프트에 포함 |
| **SQL 생성만 분리** | `/generate-sql` 엔드포인트로 실행 없이 테스트 가능 |

---

## 9. 테스트 전략

### 9.1 Phase 1 완료 검증 기준

```bash
# 학습 데이터 로드 후 다음 질문들이 정상 SQL을 생성하는지 확인
curl -X POST http://localhost:8000/query \
  -H "Content-Type: application/json" \
  -d '{"question": "어제 전체 클릭수를 알려줘"}'

# 기대 결과:
# - SQL에 파티션 조건(year/month/day) 포함
# - SQL에 event_type = 'click' 조건 포함
# - Athena 실행 성공
```

### 9.2 품질 측정 지표

| 지표 | 목표 |
|------|------|
| SQL 유효성 (EXPLAIN 통과율) | ≥ 80% |
| Athena 실행 성공률 | ≥ 70% |
| 결과 정확성 (수동 검증) | ≥ 90% |
| 평균 응답 시간 | ≤ 30초 |

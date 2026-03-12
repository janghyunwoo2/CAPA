# 4. 데이터 모델 & ChromaDB 스키마 설계

> **작성일**: 2026-03-12
> **담당**: data-modeler (에이전트)
> **관련 문서**: `data_schema_design.md` (3+2 테이블 설계), `text-to-sql.plan.md` (Plan)

---

## 4.1 Pydantic 도메인 모델

> **규칙**: 프로젝트 코딩 규칙에 따라 딕셔너리 대신 `pydantic.BaseModel`을 사용하고, 모든 함수에 타입 힌트를 명시한다.

### 4.1.1 광고 도메인 이벤트 모델

기존 `data_schema_design.md`의 3+2 테이블 구조를 Pydantic v2 모델로 표현한다. 이 모델들은 ChromaDB 학습 데이터 등록 시 DDL 자동 생성 및 검증에 활용된다.

```python
"""
services/vanna-api/src/models/domain.py
광고 도메인 이벤트 모델 - Athena 테이블 스키마와 1:1 매핑
"""
from datetime import date, datetime
from enum import Enum
from pydantic import BaseModel, Field


# ⚠️ 실제 Athena 테이블 기준 (docs/t1/text-to-sql/02-design/05-sample-queries.md)
# - ad_combined_log        : 시간(Hourly) 단위, impression + click 데이터
# - ad_combined_log_summary: 일(Daily)  단위, impression + click + conversion 데이터
# - Conversion 데이터는 ad_combined_log_summary 에만 존재

class DeviceType(str, Enum):
    """디바이스 유형 (device_type 컬럼 값) — t2 gen_adlog_init.md 기준"""
    MOBILE = "mobile"
    DESKTOP = "desktop"
    TABLET = "tablet"
    OTHERS = "others"


class AdCombinedLog(BaseModel):
    """ad_combined_log — 시간(Hourly) 단위 로그 테이블
    impression + click 데이터 포함. 파티션: year/month/day/hour.
    """
    # Impression
    impression_id: str = Field(description="광고 노출 고유 ID")
    user_id: str = Field(description="사용자 ID (PII)")
    ad_id: str = Field(description="광고 ID")
    campaign_id: str = Field(description="캠페인 ID")
    advertiser_id: str = Field(description="광고주 ID")
    platform: str = Field(description="플랫폼/앱채널 (web / app_ios / app_android / tablet_ios / tablet_android) — 5개 값")
    device_type: DeviceType
    os: str = Field(description="운영체제 (ios / android / macos / windows)")
    delivery_region: str = Field(description="배달 지역 (서울 25개 자치구: 강남구, 서초구, 마포구 등)")
    user_lat: Optional[float] = Field(None, description="사용자 위도 (37.4~37.7, 서울 범위)")
    user_long: Optional[float] = Field(None, description="사용자 경도 (126.8~127.1, 서울 범위)")
    store_id: str = Field(description="가게 ID (store_0001~store_5000, 5,000개)")
    food_category: str = Field(description="음식/상품 카테고리 (15개: chicken/pizza/korean/chinese/dessert 등)")
    ad_position: str = Field(description="광고 위치 (home_top_rolling / list_top_fixed / search_ai_recommend / checkout_bottom)")
    ad_format: str = Field(description="광고 포맷 = 광고채널 (display / native / video / discount_coupon)")
    user_agent: Optional[str] = Field(None, description="사용자 에이전트 (PII)")
    ip_address: Optional[str] = Field(None, description="IP 주소 (PII — 마지막 옥텟 마스킹: XXX.XXX.XXX.0)")
    session_id: Optional[str] = Field(None, description="세션 ID (UUID v4)")
    keyword: str
    cost_per_impression: float = Field(description="노출당 비용 = 광고비 (0.005~0.10)")
    impression_timestamp: int = Field(description="노출 시각 (BIGINT Unix timestamp)")
    # Click (클릭 없으면 click_id=NULL)
    click_id: Optional[str] = Field(None, description="클릭 ID (NULL=클릭 없음)")
    click_position_x: Optional[int] = None
    click_position_y: Optional[int] = None
    landing_page_url: Optional[str] = None
    cost_per_click: Optional[float] = Field(None, description="클릭당 비용 (CPC, 0.1~5.0)")
    click_timestamp: Optional[int] = None
    is_click: bool = Field(description="클릭 여부 플래그")
    # Partition
    year: str
    month: str
    day: str
    hour: str


class AdCombinedLogSummary(BaseModel):
    """ad_combined_log_summary — 일(Daily) 단위 요약 테이블
    impression + click + conversion 포함.
    ※ Conversion 데이터는 이 테이블에만 존재.
    파티션: year/month/day (hour 없음).
    """
    # Impression + Click (ad_combined_log와 동일 구조)
    impression_id: str
    user_id: str
    ad_id: str
    campaign_id: str
    advertiser_id: str
    platform: str = Field(description="플랫폼/앱채널 (web / app_ios / app_android / tablet_ios / tablet_android)")
    device_type: DeviceType
    os: str = Field(description="운영체제 (ios / android / macos / windows)")
    delivery_region: str
    user_lat: Optional[float] = None
    user_long: Optional[float] = None
    store_id: str
    food_category: str
    ad_position: str = Field(description="광고 위치 (home_top_rolling / list_top_fixed / search_ai_recommend / checkout_bottom)")
    ad_format: str = Field(description="광고 포맷 = 광고채널 (display / native / video / discount_coupon)")
    user_agent: Optional[str] = None
    ip_address: Optional[str] = Field(None, description="IP 주소 (PII — 마지막 옥텟 마스킹)")
    session_id: Optional[str] = None
    keyword: str
    cost_per_impression: float
    impression_timestamp: int
    click_id: Optional[str] = None
    click_position_x: Optional[int] = None
    click_position_y: Optional[int] = None
    landing_page_url: Optional[str] = None
    cost_per_click: Optional[float] = None
    click_timestamp: Optional[int] = None
    is_click: bool
    # Conversion (이 테이블에만 존재)
    conversion_id: Optional[str] = Field(None, description="전환 ID (NULL=전환 없음)")
    conversion_type: Optional[str] = Field(None, description="purchase / signup / download / view_content / add_to_cart")
    conversion_value: Optional[float] = Field(None, description="전환 가치 = 매출액 (1.0~10,000.0)")
    product_id: Optional[str] = None
    quantity: Optional[int] = None
    attribution_window: Optional[str] = None
    conversion_timestamp: Optional[int] = None
    is_conversion: bool = Field(description="전환 여부 플래그")
    # Partition (일 단위, hour 없음)
    year: str
    month: str
    day: str
```

### 4.1.2 API 요청/응답 모델

기존 MVP의 `QueryRequest`/`QueryResponse`를 Plan 문서의 FR-01~FR-11 요구사항에 맞게 확장한다.

```python
"""
services/vanna-api/src/models/api.py
API 요청/응답 모델 - Plan FR-01~FR-11 대응
"""
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class IntentType(str, Enum):
    """의도 분류 결과 (FR-01)"""
    DATA_QUERY = "data_query"       # SQL 조회 의도
    GENERAL = "general"             # 일반 질문 (도메인 문서로 답변)
    OUT_OF_SCOPE = "out_of_scope"   # 범위 외


class QueryRequest(BaseModel):
    """자연어 질의 요청 - 기존 MVP 유지 + 확장"""
    question: str = Field(description="사용자 자연어 질문", max_length=500)  # SEC-08 길이 제한


class QueryMetadata(BaseModel):
    """쿼리 실행 메타데이터"""
    intent: IntentType = Field(description="의도 분류 결과")
    refined_question: Optional[str] = Field(default=None, description="정제된 질문 (FR-02)")
    keywords: list[str] = Field(default_factory=list, description="추출된 키워드 (FR-03)")
    tables_used: list[str] = Field(default_factory=list, description="SQL에 사용된 테이블 목록")
    execution_time_ms: Optional[int] = Field(default=None, description="실행 시간 (ms)")
    row_count: Optional[int] = Field(default=None, description="결과 행 수")
    sql_validated: Optional[bool] = Field(default=None, description="EXPLAIN 검증 통과 여부 (FR-04)")


class QueryResponse(BaseModel):
    """자연어 질의 응답 - Plan FR-05~FR-09 대응

    기존 MVP 필드 유지 (sql, results, answer, error) + 신규 필드 추가
    """
    # 기존 MVP 필드 (하위 호환)
    sql: Optional[str] = Field(default=None, description="생성된 SQL")
    results: Optional[list[dict]] = Field(default=None, description="쿼리 결과 (최대 10행, NFR-03)")
    answer: Optional[str] = Field(default=None, description="AI 분석 텍스트")
    error: Optional[str] = Field(default=None, description="일반화된 오류 메시지")

    # Phase 1 신규 필드
    metadata: Optional[QueryMetadata] = Field(default=None, description="실행 메타데이터")
    redash_url: Optional[str] = Field(default=None, description="Redash 쿼리 링크 (FR-05)")
    redash_query_id: Optional[int] = Field(default=None, description="Redash query_id (FR-05)")
    chart_image_base64: Optional[str] = Field(default=None, description="matplotlib 차트 PNG Base64 (FR-08b)")

    # 실패 투명성 (FR-09)
    debug_info: Optional["DebugInfo"] = Field(default=None, description="실패 시 디버깅 정보")


class DebugInfo(BaseModel):
    """실패 투명성을 위한 디버깅 정보 (FR-09)"""
    error_code: str = Field(description="오류 코드: SQL_GENERATION_FAILED / SQL_VALIDATION_FAILED / EXECUTION_FAILED / REDASH_ERROR")
    hint: Optional[str] = Field(default=None, description="사용자 힌트 메시지")
    original_question: Optional[str] = Field(default=None, description="원본 질문")
    generated_sql: Optional[str] = Field(default=None, description="생성된 SQL (검증 실패 시)")


# forward reference 해소
QueryResponse.model_rebuild()


class TrainRequest(BaseModel):
    """학습 데이터 등록 요청 - 기존 MVP 유지 + question 필드 추가"""
    ddl: Optional[str] = Field(default=None, description="테이블 DDL")
    documentation: Optional[str] = Field(default=None, description="비즈니스 문서/정책")
    sql: Optional[str] = Field(default=None, description="SQL 예제")
    question: Optional[str] = Field(default=None, description="질문 (sql과 함께 사용 시 Q&A 쌍으로 학습)")
```

### 4.1.3 피드백 & 학습 데이터 모델

```python
"""
services/vanna-api/src/models/feedback.py
피드백 및 자가학습 데이터 모델 - Plan FR-10, FR-16, FR-21 대응
"""
from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class FeedbackType(str, Enum):
    """사용자 피드백 유형 (FR-21)"""
    POSITIVE = "positive"   # Slack 👍 - ChromaDB 학습 대상
    NEGATIVE = "negative"   # Slack 👎 - 학습 제외, 분석 대상


class QueryHistoryRecord(BaseModel):
    """쿼리 이력 레코드 (FR-10) - History 저장소의 단일 레코드

    성공/실패 모두 저장한다.
    """
    history_id: str = Field(description="이력 고유 ID (UUID)")
    timestamp: datetime = Field(description="질의 시각")
    slack_user_id: str = Field(description="Slack 사용자 ID (PII - 저장 시 해시 처리)")
    slack_channel_id: str = Field(description="Slack 채널 ID")

    # 질의 정보
    original_question: str = Field(description="원본 질문")
    refined_question: Optional[str] = Field(default=None, description="정제된 질문")
    intent: str = Field(description="의도 분류 결과")
    keywords: list[str] = Field(default_factory=list, description="추출된 키워드")

    # SQL 정보
    generated_sql: Optional[str] = Field(default=None, description="생성된 SQL")
    sql_validated: Optional[bool] = Field(default=None, description="EXPLAIN 통과 여부")

    # 실행 결과
    success: bool = Field(description="실행 성공 여부")
    error_code: Optional[str] = Field(default=None, description="오류 코드 (실패 시)")
    row_count: Optional[int] = Field(default=None, description="결과 행 수")
    execution_time_ms: Optional[int] = Field(default=None, description="총 실행 시간 (ms)")

    # Redash 연동
    redash_query_id: Optional[int] = Field(default=None, description="Redash query_id")
    redash_url: Optional[str] = Field(default=None, description="Redash 쿼리 URL")

    # 피드백 (나중에 업데이트)
    feedback: Optional[FeedbackType] = Field(default=None, description="사용자 피드백")
    feedback_at: Optional[datetime] = Field(default=None, description="피드백 시각")
    trained: bool = Field(default=False, description="ChromaDB 학습 완료 여부")


class FeedbackRequest(BaseModel):
    """Slack 피드백 콜백 요청 (FR-21)"""
    history_id: str = Field(description="대상 이력 ID")
    feedback: FeedbackType = Field(description="피드백 유형")
    slack_user_id: str = Field(description="피드백 제공 사용자")
    comment: Optional[str] = Field(None, max_length=500, description="추가 코멘트 (design.md 동기화)")


class TrainingDataRecord(BaseModel):
    """ChromaDB 학습 데이터 레코드

    vanna.train() 호출 시 사용되는 데이터 구조.
    DDL / Documentation / QA 예제 3가지 유형을 통합 관리한다.
    """
    training_id: str = Field(description="학습 데이터 고유 ID (UUID)")
    data_type: str = Field(description="유형: ddl / documentation / qa_example")
    source: str = Field(description="출처: manual_seed / feedback_loop / airflow_sync")
    created_at: datetime = Field(description="등록 시각")

    # DDL 유형
    ddl: Optional[str] = Field(default=None, description="테이블 DDL")
    table_name: Optional[str] = Field(default=None, description="대상 테이블명")

    # Documentation 유형
    documentation: Optional[str] = Field(default=None, description="비즈니스 문서 텍스트")
    doc_category: Optional[str] = Field(default=None, description="문서 카테고리: business_metric / athena_rule / policy / glossary")

    # QA 예제 유형
    question: Optional[str] = Field(default=None, description="질문")
    sql: Optional[str] = Field(default=None, description="SQL")
    sql_hash: Optional[str] = Field(default=None, description="SQL SHA-256 해시 (중복 방지)")
```

---

## 4.2 ChromaDB 컬렉션 구조

Vanna AI는 내부적으로 ChromaDB에 3개 컬렉션을 생성하여 RAG 검색에 활용한다. 기존 Vanna의 컬렉션 구조를 그대로 유지하되, 학습 데이터의 품질과 메타데이터를 강화한다.

### 4.2.1 컬렉션 개요

Vanna AI SDK는 `ChromaDB_VectorStore` 내부에서 다음 3개 컬렉션을 자동 관리한다:

| # | 컬렉션명 (Vanna 내부) | 학습 메서드 | 용도 | 임베딩 대상 |
|---|----------------------|-------------|------|------------|
| 1 | `sql-ddl` | `vanna.train(ddl=)` | 테이블 스키마 검색 | DDL 텍스트 전체 |
| 2 | `sql-documentation` | `vanna.train(documentation=)` | 비즈니스 규칙/정책 검색 | 문서 텍스트 전체 |
| 3 | `sql-qa` | `vanna.train(question=, sql=)` | Few-shot SQL 예제 검색 | 질문 텍스트 |

> **설계 원칙**: Vanna의 내부 컬렉션 구조를 변경하지 않는다. 대신 학습 시 메타데이터를 풍부하게 주입하고, 학습 데이터의 품질을 체계적으로 관리한다.

### 4.2.2 DDL 컬렉션 (`sql-ddl`) 학습 데이터

실제 Athena 테이블 2개에 대해 상세 DDL + 컬럼 설명을 학습한다.

```python
DDL_AD_COMBINED_LOG = """
CREATE EXTERNAL TABLE ad_combined_log (
    impression_id       STRING  COMMENT '광고 노출 고유 ID',
    user_id             STRING  COMMENT '사용자 ID (PII)',
    ad_id               STRING  COMMENT '광고 ID',
    campaign_id         STRING  COMMENT '캠페인 ID',
    advertiser_id       STRING  COMMENT '광고주 ID',
    platform            STRING  COMMENT '플랫폼/앱채널: web / app_ios / app_android / tablet_ios / tablet_android',
    device_type         STRING  COMMENT '디바이스 유형: mobile / tablet / desktop / others',
    os                  STRING  COMMENT '운영체제: ios / android / macos / windows',
    delivery_region     STRING  COMMENT '배달 지역 (서울 25개 자치구: 강남구, 서초구, 마포구 등)',
    store_id            STRING  COMMENT '가게 ID (store_0001~store_5000)',
    food_category       STRING  COMMENT '음식/상품 카테고리 (15개: chicken/pizza/korean/chinese/dessert 등)',
    ad_position         STRING  COMMENT '광고 위치: home_top_rolling / list_top_fixed / search_ai_recommend / checkout_bottom',
    ad_format           STRING  COMMENT '광고 포맷/광고채널: display / native / video / discount_coupon',
    keyword             STRING  COMMENT '검색 키워드',
    cost_per_impression DOUBLE  COMMENT '노출당 비용 = 광고비. SUM(cost_per_impression)으로 총 광고비 계산',
    impression_timestamp BIGINT COMMENT '노출 시각 (Unix timestamp)',
    click_id            STRING  COMMENT '클릭 ID. NULL이면 클릭 없음',
    click_position_x    INT     COMMENT '클릭 X 좌표',
    click_position_y    INT     COMMENT '클릭 Y 좌표',
    landing_page_url    STRING  COMMENT '랜딩 페이지 URL',
    cost_per_click      DOUBLE  COMMENT '클릭당 비용 (CPC). 클릭 없으면 NULL',
    click_timestamp     BIGINT  COMMENT '클릭 시각',
    is_click            BOOLEAN COMMENT '클릭 여부 플래그. 클릭수 = COUNT(CASE WHEN is_click THEN 1 END)'
) PARTITIONED BY (year STRING, month STRING, day STRING, hour STRING)
STORED AS PARQUET
LOCATION 's3://capa-data-lake/ad_combined_log/';

-- 파티션 조건 필수: WHERE year='YYYY' AND month='MM' AND day='DD' [AND hour='HH']
-- 노출수 = COUNT(*) 또는 COUNT(impression_id)
-- 클릭수 = COUNT(CASE WHEN is_click THEN 1 END)
-- CTR   = COUNT(CASE WHEN is_click THEN 1 END) * 100.0 / COUNT(*)
-- 광고비 = SUM(cost_per_impression) + SUM(COALESCE(cost_per_click, 0))
-- ※ Conversion 데이터 없음 → 전환 관련 쿼리는 ad_combined_log_summary 사용
"""

DDL_AD_COMBINED_LOG_SUMMARY = """
CREATE EXTERNAL TABLE ad_combined_log_summary (
    -- Impression + Click (ad_combined_log와 동일)
    impression_id       STRING,
    user_id             STRING  COMMENT '사용자 ID (PII)',
    ad_id               STRING,
    campaign_id         STRING,
    advertiser_id       STRING,
    platform            STRING  COMMENT '플랫폼/앱채널: web / app_ios / app_android / tablet_ios / tablet_android',
    device_type         STRING  COMMENT '디바이스 유형: mobile / tablet / desktop / others',
    os                  STRING  COMMENT '운영체제: ios / android / macos / windows',
    delivery_region     STRING  COMMENT '배달 지역 (서울 25개 자치구)',
    store_id            STRING  COMMENT '가게 ID (store_0001~store_5000)',
    food_category       STRING  COMMENT '음식/상품 카테고리 (15개: chicken/pizza/korean/chinese/dessert 등)',
    ad_position         STRING  COMMENT '광고 위치: home_top_rolling / list_top_fixed / search_ai_recommend / checkout_bottom',
    ad_format           STRING  COMMENT '광고 포맷/광고채널: display / native / video / discount_coupon',
    keyword             STRING,
    cost_per_impression DOUBLE  COMMENT '노출당 비용',
    impression_timestamp BIGINT,
    click_id            STRING  COMMENT 'NULL이면 클릭 없음',
    click_position_x    INT,
    click_position_y    INT,
    landing_page_url    STRING,
    cost_per_click      DOUBLE  COMMENT 'CPC. 클릭 없으면 NULL',
    click_timestamp     BIGINT,
    is_click            BOOLEAN COMMENT '클릭 여부',
    -- Conversion (이 테이블에만 존재)
    conversion_id       STRING  COMMENT '전환 ID. NULL이면 전환 없음',
    conversion_type     STRING  COMMENT '전환 타입: purchase / signup / download / view_content / add_to_cart',
    conversion_value    DOUBLE  COMMENT '전환 가치 = 매출액. SUM(COALESCE(conversion_value,0))으로 총 매출',
    product_id          STRING,
    quantity            INT,
    attribution_window  STRING  COMMENT '귀속 기간: 1day / 7day / 30day',
    conversion_timestamp BIGINT,
    is_conversion       BOOLEAN COMMENT '전환 여부 플래그'
) PARTITIONED BY (year STRING, month STRING, day STRING)
STORED AS PARQUET
LOCATION 's3://capa-data-lake/ad_combined_log_summary/';

-- 파티션 조건 필수: WHERE year='YYYY' AND month='MM' AND day='DD' (hour 파티션 없음)
-- 전환수  = COUNT(CASE WHEN is_conversion THEN 1 END)
-- CVR    = 전환수 * 100.0 / NULLIF(클릭수, 0)
-- 매출   = SUM(COALESCE(conversion_value, 0))
-- ROAS   = 매출 / NULLIF(광고비, 0) * 100
-- ※ 시간대별(hour) 분석은 ad_combined_log 사용
"""
```

**전체 DDL 학습 목록 (2개 테이블)**:

| 테이블 | 단위 | DDL 파일 경로 | 핵심 설명 |
|--------|------|-------------|----------|
| `ad_combined_log` | **시간(Hourly)** | `training_data/ddl/ad_combined_log.sql` | impression+click. is_click 플래그로 클릭 판별. 파티션: year/month/day/hour |
| `ad_combined_log_summary` | **일(Daily)** | `training_data/ddl/ad_combined_log_summary.sql` | impression+click+conversion. is_conversion 플래그. 파티션: year/month/day |

### 4.2.3 Documentation 컬렉션 (`sql-documentation`) 학습 데이터

4개 카테고리로 분류하여 학습한다.

#### (a) 비즈니스 지표 정의 (`business_metric`)

```python
DOCS_BUSINESS_METRICS = [
    """
    [비즈니스 지표: CTR (클릭률)]
    정의: 노출 대비 클릭 비율
    계산식: COUNT(CASE WHEN is_click THEN 1 END) * 100.0 / COUNT(*)
    단위: 퍼센트 (%)
    사용 테이블: ad_combined_log 또는 ad_combined_log_summary (단일 테이블, JOIN 불필요)
    """,
    """
    [비즈니스 지표: CVR (전환율)]
    정의: 클릭 대비 전환 비율
    계산식: COUNT(CASE WHEN is_conversion THEN 1 END) * 100.0 / NULLIF(COUNT(CASE WHEN is_click THEN 1 END), 0)
    단위: 퍼센트 (%)
    사용 테이블: ad_combined_log_summary 전용 (Conversion은 이 테이블에만 존재)
    """,
    """
    [비즈니스 지표: ROAS (광고 수익률)]
    정의: 광고비 대비 매출 비율
    계산식: SUM(COALESCE(conversion_value, 0)) / NULLIF(SUM(cost_per_impression) + SUM(COALESCE(cost_per_click, 0)), 0) * 100
    단위: 퍼센트 (%)
    사용 테이블: ad_combined_log_summary 전용
    """,
    """
    [비즈니스 지표: CPA (전환당 비용)]
    정의: 전환 1건당 평균 광고비
    계산식: (SUM(cost_per_impression) + SUM(COALESCE(cost_per_click, 0))) / NULLIF(COUNT(CASE WHEN is_conversion THEN 1 END), 0)
    단위: 원 (KRW)
    사용 테이블: ad_combined_log_summary 전용
    """,
    """
    [비즈니스 지표: CPC (클릭당 비용)]
    정의: 클릭 1건당 평균 비용
    계산식: SUM(COALESCE(cost_per_click, 0)) / NULLIF(COUNT(CASE WHEN is_click THEN 1 END), 0)
    단위: 원 (KRW)
    """,
    """
    [비즈니스 용어 매핑]
    - "노출수"          = COUNT(*) 또는 COUNT(impression_id)
    - "클릭수"          = COUNT(CASE WHEN is_click THEN 1 END)
    - "전환수"          = COUNT(CASE WHEN is_conversion THEN 1 END)  ← summary 테이블만
    - "광고비" / "비용" = SUM(cost_per_impression) + SUM(COALESCE(cost_per_click, 0))
    - "매출" / "수익"   = SUM(COALESCE(conversion_value, 0))  ← summary 테이블만
    - "상품 카테고리"   = food_category 컬럼
    - "광고채널"        = ad_format 컬럼 (display / native / video / discount_coupon) — platform은 기술 플랫폼 구분
    - "지역구"          = delivery_region 컬럼
    """,
]
```

#### (b) Athena 특화 규칙 (`athena_rule`)

```python
DOCS_ATHENA_RULES = [
    """
    [Athena SQL 필수 규칙: 파티션 조건]
    모든 테이블(ad_combined_log, ad_combined_log_summary) 쿼리 시 반드시 파티션 조건을 포함해야 한다.
    파티션 컬럼: year, month, day (STRING 타입)

    올바른 예:
    WHERE year = '2026' AND month = '03' AND day = '12'
    WHERE year = '2026' AND month = '03' AND day BETWEEN '01' AND '07'

    잘못된 예 (파티션 조건 없음):
    SELECT * FROM impressions  -- 전체 스캔 발생, 비용 폭증
    """,
    """
    [Athena SQL 규칙: 날짜 함수]
    Athena는 Presto SQL 방언을 사용한다.

    - 현재 날짜: current_date
    - 날짜 차이: date_diff('day', start_date, end_date)
    - 날짜 포맷: date_format(timestamp_col, '%Y-%m-%d')
    - 문자열→날짜: date_parse(string_col, '%Y-%m-%d')
    - 날짜 절삭: date_trunc('month', timestamp_col)
    - N일 전: date_add('day', -7, current_date)

    주의: MySQL의 DATE_SUB(), DATEDIFF()는 사용 불가
    """,
    """
    [Athena SQL 규칙: 결과 제한]
    모든 SELECT 쿼리에 LIMIT 절을 포함해야 한다.
    기본값: LIMIT 100
    TOP N 조회: ORDER BY ... DESC LIMIT N

    집계 쿼리(GROUP BY)는 결과가 제한적이므로 LIMIT 생략 가능
    """,
    """
    [Athena SQL 규칙: SELECT 전용]
    오직 SELECT 문만 허용된다.
    INSERT, UPDATE, DELETE, DROP, CREATE, ALTER 등 DDL/DML은 절대 생성하지 않는다.
    """,
]
```

#### (c) 정책 데이터 (`policy`)

```python
DOCS_POLICIES = [
    """
    [정책: 코드값 매핑 - device_type]
    ad_combined_log / ad_combined_log_summary 의 device_type 컬럼 값 (4개):
    - 'mobile':  모바일 기기 (스마트폰)
    - 'tablet':  태블릿 기기
    - 'desktop': 데스크탑 PC
    - 'others':  기타 기기

    ※ 출처: t2 gen_adlog_init.md 기준
    """,
    """
    [정책: 코드값 매핑 - platform]
    ad_combined_log / ad_combined_log_summary 의 platform 컬럼 값 (5개):
    - 'web':            웹 브라우저
    - 'app_ios':        iOS 앱
    - 'app_android':    Android 앱
    - 'tablet_ios':     iPad 앱
    - 'tablet_android': Android 태블릿 앱

    주의: platform은 기술적 소프트웨어 환경 구분이다. 광고채널(디스플레이/네이티브 등) 분석은 ad_format 컬럼을 사용한다.
    ※ 출처: t2 gen_adlog_init.md 기준
    """,
    """
    [정책: 코드값 매핑 - ad_format (광고포맷/광고채널)]
    "광고채널별", "채널별", "포맷별" 분석 요청 시 ad_format 컬럼을 사용한다.
    ad_format 컬럼 값 (4개):
    - 'display':         디스플레이 배너 광고
    - 'native':          네이티브 광고
    - 'video':           동영상 광고
    - 'discount_coupon': 할인쿠폰 광고

    예: "광고채널별 CTR" → GROUP BY ad_format
    ※ 출처: t2 gen_adlog_init.md 기준
    """,
    """
    [정책: 코드값 매핑 - ad_position (광고위치)]
    ad_position 컬럼 값 (4개):
    - 'home_top_rolling':     홈 상단 롤링
    - 'list_top_fixed':       목록 상단 고정
    - 'search_ai_recommend':  검색 AI 추천
    - 'checkout_bottom':      결제화면 하단

    ※ 출처: t2 gen_adlog_init.md 기준
    """,
    """
    [정책: 코드값 매핑 - conversion_type]
    ad_combined_log_summary 의 conversion_type 컬럼 값 (전환 없으면 NULL):
    - 'purchase':      구매 완료 → conversion_value에 매출액 기록
    - 'signup':        회원가입 완료
    - 'download':      앱 다운로드
    - 'view_content':  컨텐츠 조회
    - 'add_to_cart':   장바구니 추가

    주의: "전환" 또는 "매출"을 물어볼 때는 is_conversion = TRUE 인 행만 집계.
    ※ 출처: t2 gen_adlog_init.md 기준
    """,
    """
    [정책: 코드값 매핑 - attribution_window]
    ad_combined_log_summary 의 attribution_window 컬럼 값 (3개):
    - '1day':  1일 귀속
    - '7day':  7일 귀속
    - '30day': 30일 귀속
    ※ 출처: t2 gen_adlog_init.md 기준
    """,
    """
    [정책: 테이블 선택 기준]
    - 시간대별(hour) 분석, 빠른 노출/클릭 조회 → ad_combined_log
    - 전환 데이터 포함, 일별/주간/월간 집계, 매출/ROAS 계산 → ad_combined_log_summary
    두 테이블은 JOIN 없이 각각 독립적으로 쿼리한다.
    """,
    """
    [정책: 단일 테이블 집계 패턴]
    두 테이블 모두 impression + click이 한 행에 있는 비정규화 구조.
    노출·클릭·전환을 한 번에 집계할 때 JOIN 불필요:

    SELECT
        campaign_id,
        COUNT(*) AS 노출수,
        COUNT(CASE WHEN is_click THEN 1 END) AS 클릭수,
        COUNT(CASE WHEN is_conversion THEN 1 END) AS 전환수  -- summary만
    FROM ad_combined_log_summary
    WHERE year='YYYY' AND month='MM' AND day='DD'
    GROUP BY campaign_id
    """,
]
```

#### (d) 도메인 용어 사전 (`glossary`)

```python
DOCS_GLOSSARY = [
    """
    [광고 도메인 용어 사전]
    - 노출 (Impression): 광고가 사용자 화면에 표시된 이벤트. ad_combined_log / ad_combined_log_summary 의 각 행이 노출 1건
    - 클릭 (Click): 사용자가 광고를 클릭한 이벤트. is_click=TRUE 인 행
    - 전환 (Conversion): 클릭 후 목표 행동(구매 등)을 완료한 이벤트. is_conversion=TRUE 인 행 (summary 테이블만)
    - 캠페인 (Campaign): 광고 집행의 기본 단위. campaign_id 컬럼으로 식별
    - 광고주 (Advertiser): 광고를 집행하는 주체. advertiser_id 컬럼으로 식별
    - 광고채널 (Channel): ad_format 컬럼 (display / native / video / discount_coupon) — platform은 배달앱 기술 채널(web/app_ios/app_android 등)
    - 상품/음식 카테고리: food_category 컬럼
    - 광고비: cost_per_impression (노출당 비용) + cost_per_click (클릭당 비용, 클릭 없으면 NULL)
    - 매출: conversion_value 컬럼 (summary 테이블만, 전환 없으면 NULL)
    - ROAS: Return On Ad Spend. 매출 / 광고비 * 100
    - CTR: Click Through Rate. 클릭수 / 노출수 * 100
    - CVR: Conversion Rate. 전환수 / 클릭수 * 100
    - CPA: Cost Per Action. 광고비 / 전환수
    - CPC: Cost Per Click. 클릭 광고비 / 클릭수
    """,
]
```

### 4.2.4 QA 예제 컬렉션 (`sql-qa`) 학습 데이터

`vanna.train(question=, sql=)` 형태로 질문-SQL 쌍을 학습한다. Plan 문서의 10개 초기 구축 대상 + `target_user_queries.md`의 핵심 질문을 포함한다.

```python
# ⚠️ 모든 SQL은 ad_combined_log / ad_combined_log_summary 실제 스키마 기준
# JOIN 없이 단일 테이블 집계 패턴 사용
QA_EXAMPLES: list[dict[str, str]] = [
    # --- 기간별 성과 ---
    {
        "question": "어제 전체 광고 노출수, 클릭수, CTR을 알려줘",
        "sql": """
SELECT
    COUNT(*) AS 노출수,
    COUNT(CASE WHEN is_click THEN 1 END) AS 클릭수,
    ROUND(COUNT(CASE WHEN is_click THEN 1 END) * 100.0 / COUNT(*), 2) AS CTR
FROM ad_combined_log_summary
WHERE year  = date_format(date_add('day', -1, current_date), '%Y')
  AND month = date_format(date_add('day', -1, current_date), '%m')
  AND day   = date_format(date_add('day', -1, current_date), '%d')
"""
    },
    {
        "question": "이번주 일별 CTR 트렌드를 보여줘",
        "sql": """
SELECT
    day AS 날짜,
    COUNT(*) AS 노출수,
    COUNT(CASE WHEN is_click THEN 1 END) AS 클릭수,
    ROUND(COUNT(CASE WHEN is_click THEN 1 END) * 100.0 / COUNT(*), 2) AS CTR
FROM ad_combined_log_summary
WHERE year  = date_format(current_date, '%Y')
  AND month = date_format(current_date, '%m')
  AND day  >= date_format(date_add('day', -7, current_date), '%d')
GROUP BY day
ORDER BY day
"""
    },
    {
        "question": "지난달 캠페인별 총 광고비를 알려줘",
        "sql": """
SELECT
    campaign_id,
    ROUND(SUM(cost_per_impression) + SUM(COALESCE(cost_per_click, 0)), 0) AS 총광고비
FROM ad_combined_log_summary
WHERE year  = date_format(date_add('month', -1, current_date), '%Y')
  AND month = date_format(date_add('month', -1, current_date), '%m')
GROUP BY campaign_id
ORDER BY 총광고비 DESC
"""
    },
    # --- 순위/비교 ---
    {
        "question": "지난 7일간 CTR이 가장 높은 캠페인 TOP 5",
        "sql": """
SELECT
    campaign_id,
    COUNT(*) AS 노출수,
    COUNT(CASE WHEN is_click THEN 1 END) AS 클릭수,
    ROUND(COUNT(CASE WHEN is_click THEN 1 END) * 100.0 / COUNT(*), 2) AS CTR
FROM ad_combined_log_summary
WHERE year  = date_format(current_date, '%Y')
  AND month = date_format(current_date, '%m')
  AND day  >= date_format(date_add('day', -7, current_date), '%d')
GROUP BY campaign_id
HAVING COUNT(*) > 0
ORDER BY CTR DESC
LIMIT 5
"""
    },
    {
        "question": "이번달 ROAS가 100% 이상인 캠페인 목록",
        "sql": """
SELECT
    campaign_id,
    ROUND(SUM(cost_per_impression) + SUM(COALESCE(cost_per_click, 0)), 0) AS 광고비,
    ROUND(SUM(COALESCE(conversion_value, 0)), 0) AS 매출,
    ROUND(
        SUM(COALESCE(conversion_value, 0))
        / NULLIF(SUM(cost_per_impression) + SUM(COALESCE(cost_per_click, 0)), 0) * 100,
    2) AS ROAS
FROM ad_combined_log_summary
WHERE year  = date_format(current_date, '%Y')
  AND month = date_format(current_date, '%m')
GROUP BY campaign_id
HAVING ROUND(
    SUM(COALESCE(conversion_value, 0))
    / NULLIF(SUM(cost_per_impression) + SUM(COALESCE(cost_per_click, 0)), 0) * 100,
2) >= 100
ORDER BY ROAS DESC
"""
    },
    # --- 디바이스/세그먼트 ---
    {
        "question": "어제 디바이스 유형별 클릭수 비교",
        "sql": """
SELECT
    device_type AS 디바이스,
    COUNT(CASE WHEN is_click THEN 1 END) AS 클릭수
FROM ad_combined_log_summary
WHERE year  = date_format(date_add('day', -1, current_date), '%Y')
  AND month = date_format(date_add('day', -1, current_date), '%m')
  AND day   = date_format(date_add('day', -1, current_date), '%d')
GROUP BY device_type
ORDER BY 클릭수 DESC
"""
    },
    {
        "question": "food_category별 전환율(CVR) TOP 5",
        "sql": """
SELECT
    food_category AS 카테고리,
    COUNT(*) AS 노출수,
    COUNT(CASE WHEN is_click THEN 1 END) AS 클릭수,
    COUNT(CASE WHEN is_conversion THEN 1 END) AS 전환수,
    ROUND(
        COUNT(CASE WHEN is_conversion THEN 1 END) * 100.0
        / NULLIF(COUNT(CASE WHEN is_click THEN 1 END), 0),
    2) AS CVR
FROM ad_combined_log_summary
WHERE year  = date_format(current_date, '%Y')
  AND month = date_format(current_date, '%m')
GROUP BY food_category
ORDER BY CVR DESC
LIMIT 5
"""
    },
    # --- 이상/점검 ---
    {
        "question": "최근 7일간 클릭이 0인 campaign_id 목록",
        "sql": """
SELECT
    campaign_id,
    COUNT(*) AS 노출수,
    COUNT(CASE WHEN is_click THEN 1 END) AS 클릭수
FROM ad_combined_log_summary
WHERE year  = date_format(current_date, '%Y')
  AND month = date_format(current_date, '%m')
  AND day  >= date_format(date_add('day', -7, current_date), '%d')
GROUP BY campaign_id
HAVING COUNT(CASE WHEN is_click THEN 1 END) = 0
ORDER BY 노출수 DESC
"""
    },
    {
        "question": "지난 7일 중 총 광고비가 가장 높은 날은?",
        "sql": """
SELECT
    day AS 날짜,
    ROUND(SUM(cost_per_impression) + SUM(COALESCE(cost_per_click, 0)), 0) AS 총광고비
FROM ad_combined_log_summary
WHERE year  = date_format(current_date, '%Y')
  AND month = date_format(current_date, '%m')
  AND day  >= date_format(date_add('day', -7, current_date), '%d')
GROUP BY day
ORDER BY 총광고비 DESC
LIMIT 1
"""
    },
    # --- 캠페인 상세 ---
    {
        "question": "캠페인별 일별 광고비 합계를 보여줘",
        "sql": """
SELECT
    campaign_id,
    day AS 날짜,
    ROUND(SUM(cost_per_impression) + SUM(COALESCE(cost_per_click, 0)), 0) AS 일별광고비
FROM ad_combined_log_summary
WHERE year  = date_format(current_date, '%Y')
  AND month = date_format(current_date, '%m')
GROUP BY campaign_id, day
ORDER BY campaign_id, day
"""
    },
]
```

### 4.2.5 ChromaDB 학습 데이터 등록 흐름

```
[초기 시딩 (Phase 1)]
training_data/
├── ddl/                    # DDL 2개 파일 (실제 Athena 테이블 기준)
│   ├── ad_combined_log.sql
│   └── ad_combined_log_summary.sql
├── docs/                   # Documentation 15+개
│   ├── business_metrics.md
│   ├── athena_rules.md
│   ├── policies.md
│   └── glossary.md
└── qa_examples/            # QA 예제 10+개
    └── seed_examples.json

        │
        ▼ scripts/load_training_data.py
[ChromaDB 3개 컬렉션에 등록]
  sql-ddl           ← 2개 DDL
  sql-documentation ← 15+개 문서
  sql-qa            ← 10+개 Q&A 쌍
```

---

## 4.3 피드백 & 자가학습 스키마

### 4.3.1 데이터 흐름

```
[사용자 질문] → [vanna-api 처리] → [Slack 응답 + 👍/👎 버튼]
                                           │
                              ┌─────────────┴─────────────┐
                              ▼                           ▼
                        👍 (positive)               👎 (negative)
                              │                           │
                              ▼                           ▼
                   ┌──────────────────┐        ┌─────────────────┐
                   │ History 저장     │        │ History 저장     │
                   │ (feedback=pos)   │        │ (feedback=neg)   │
                   └────────┬─────────┘        └─────────────────┘
                            │                         (학습 안함)
                            ▼
                   ┌──────────────────┐
                   │ vanna.train(     │
                   │   question=,     │
                   │   sql=           │
                   │ )                │
                   └────────┬─────────┘
                            │
                            ▼
                   ┌──────────────────┐
                   │ ChromaDB sql-qa  │
                   │ 컬렉션에 추가     │
                   │ (trained=True)   │
                   └──────────────────┘
```

### 4.3.2 피드백 처리 API

```python
# POST /feedback (신규 엔드포인트)
# Slack Bot의 Block Kit 인터랙션 콜백에서 호출

# 요청
FeedbackRequest(
    history_id="uuid-xxx",
    feedback=FeedbackType.POSITIVE,
    slack_user_id="U12345"
)

# 처리 로직 (의사 코드):
# 1. QueryHistoryRecord 조회 by history_id
# 2. feedback, feedback_at 필드 업데이트
# 3. feedback == POSITIVE인 경우:
#    a. SQL 해시로 중복 체크 (FR-17 대응)
#    b. 중복 없으면 vanna.train(question=record.refined_question, sql=record.generated_sql)
#    c. trained = True 업데이트
```

### 4.3.3 History 저장소 선택

| 옵션 | 장점 | 단점 | 결정 |
|------|------|------|------|
| **로컬 JSON 파일** | 구현 간단, 외부 의존성 없음 | 동시성 이슈, 영속성 불안 | Phase 1 채택 |
| DynamoDB | 영속성, 쿼리 유연성 | 추가 인프라 비용 | Phase 2 검토 |
| SQLite | 로컬 영속성, SQL 쿼리 가능 | 컨테이너 재시작 시 유실 (PV 필요) | 대안 |

**Phase 1 구현**: JSON Lines 파일 (`/data/query_history.jsonl`)
- 각 줄이 하나의 `QueryHistoryRecord` JSON
- 컨테이너 PV 마운트 경로: `/data/`
- 최대 보관: 10,000건 (초과 시 오래된 순 삭제)

---

## 4.4 쿼리 이력 저장소

### 4.4.1 S3 경로 규칙 (Athena 쿼리 결과)

Athena 쿼리 결과는 자동으로 S3에 저장된다. Redash 경유 실행 시 Redash가 관리하므로 별도 경로 설계 불필요. 기존 Athena 직접 경로(Fallback) 사용 시:

```
s3://capa-athena-results/
└── vanna-api/
    └── {year}/{month}/{day}/
        └── {query_execution_id}.csv
```

### 4.4.2 Redash 쿼리 이력

Redash에 생성된 쿼리는 Redash 내부 PostgreSQL에 자동 저장된다. vanna-api에서는 `redash_query_id`만 보관하면 된다.

```
QueryHistoryRecord.redash_query_id → Redash GET /api/queries/{id}로 원본 SQL/결과 재조회 가능
QueryHistoryRecord.redash_url → 사용자에게 전달할 Redash 대시보드 링크
```

### 4.4.3 학습 데이터 이력 관리

ChromaDB에 학습된 데이터의 출처를 추적하기 위해 `TrainingDataRecord`를 별도 JSON Lines로 관리한다.

```
/data/training_history.jsonl

각 레코드:
{
    "training_id": "uuid-xxx",
    "data_type": "qa_example",
    "source": "feedback_loop",       # manual_seed | feedback_loop | airflow_sync
    "created_at": "2026-03-12T10:00:00",
    "question": "어제 CTR 높은 캠페인 TOP 5",
    "sql": "SELECT ...",
    "sql_hash": "sha256-abc..."
}
```

---

## 4.5 Redash 연동 스키마

### 4.5.1 Redash API 요청/응답 모델

```python
"""
services/vanna-api/src/models/redash.py
Redash API 연동 데이터 구조
"""
from typing import Optional

from pydantic import BaseModel, Field


class RedashQueryCreateRequest(BaseModel):
    """Redash POST /api/queries 요청 본문"""
    name: str = Field(description="쿼리 이름 (자동 생성: 'CAPA: {refined_question}')")
    query: str = Field(description="실행할 SQL")
    data_source_id: int = Field(description="Athena 데이터소스 ID (환경변수)")
    description: str = Field(default="", description="쿼리 설명 (원본 질문)")
    schedule: None = Field(default=None, description="스케줄 없음 (일회성)")


class RedashQueryCreateResponse(BaseModel):
    """Redash POST /api/queries 응답"""
    id: int = Field(description="생성된 query_id")
    name: str
    query: str
    data_source_id: int


class RedashJobStatus(BaseModel):
    """Redash GET /api/jobs/{job_id} 응답의 job 필드"""
    id: str = Field(description="job_id")
    status: int = Field(description="1=대기, 2=실행중, 3=성공, 4=실패")
    error: Optional[str] = Field(default=None, description="실패 시 오류 메시지")
    query_result_id: Optional[int] = Field(default=None, description="성공 시 결과 ID")


class RedashQueryResult(BaseModel):
    """Redash GET /api/queries/{id}/results 응답의 query_result.data 필드"""
    columns: list[dict[str, str]] = Field(description="컬럼 정보 [{name, type}, ...]")
    rows: list[dict] = Field(description="결과 행 리스트")


class RedashConfig(BaseModel):
    """Redash 연동 설정 (환경변수 매핑)"""
    base_url: str = Field(description="Redash 내부 URL (K8s DNS)")
    api_key: str = Field(description="Redash API Key (Secret)")
    data_source_id: int = Field(description="Athena 데이터소스 ID")
    query_timeout_sec: int = Field(default=300, description="최대 폴링 대기 시간")
    poll_interval_sec: int = Field(default=3, description="폴링 주기")
    public_url: str = Field(description="사용자에게 전달할 외부 URL")
    enabled: bool = Field(default=True, description="Redash 경유 활성화 (FR-11)")
```

### 4.5.2 Redash 쿼리 이름 규칙

```
패턴: "CAPA: {refined_question} [{timestamp}]"
예시: "CAPA: 지난 7일간 CTR 높은 캠페인 TOP 5 [2026-03-12 14:30]"
```

- `CAPA:` 접두사로 vanna-api가 생성한 쿼리를 식별
- `refined_question`으로 검색 가능성 확보
- `timestamp`로 동일 질문의 시간대별 구분
- SQL 해시 기반 중복 탐지 (FR-17): 동일 SQL 해시가 존재하면 기존 query_id 재사용

### 4.5.3 SQL 해시 기반 중복 방지 (FR-17)

```python
import hashlib

def compute_sql_hash(sql: str) -> str:
    """SQL 정규화 후 SHA-256 해시 생성"""
    normalized = " ".join(sql.strip().split()).lower()
    return hashlib.sha256(normalized.encode()).hexdigest()
```

중복 탐지 흐름:
```
1. 생성된 SQL의 해시 계산
2. History에서 동일 해시 + redash_query_id 존재 여부 확인
3. 존재하면 → 기존 redash_query_id 재사용 (Redash 신규 생성 건너뜀)
4. 존재하지 않으면 → Redash 신규 쿼리 생성
```

---

## 4.6 모델 파일 구조 요약

```
services/vanna-api/src/
├── models/                    # 🆕 신규 디렉토리
│   ├── __init__.py
│   ├── domain.py              # §4.1.1 Athena 테이블 모델 (AdCombinedLog, AdCombinedLogSummary)
│   ├── api.py                 # §4.1.2 API 요청/응답 모델 (QueryRequest/Response 확장)
│   ├── feedback.py            # §4.1.3 피드백 & 학습 모델 (QueryHistoryRecord 등)
│   └── redash.py              # §4.5.1 Redash 연동 모델
├── main.py                    # 기존 MVP (models/ 임포트로 교체)
└── train_dummy.py             # 기존 더미 학습 (Phase 1에서 load_training_data.py로 대체)

training_data/                 # 🆕 신규 디렉토리
├── ddl/                       # §4.2.2 DDL 2개 파일 (ad_combined_log, ad_combined_log_summary)
├── docs/                      # §4.2.3 Documentation 문서
└── qa_examples/               # §4.2.4 QA 예제 JSON (단일 테이블 집계 패턴)
```

---

## 에이전트 기여 내역 (Agent Attribution)

### 에이전트별 수행 작업

| 에이전트 | 모델 | 수행 작업 |
|---------|------|----------|
| `data-modeler` | Opus 4.6 | 기존 data_schema_design.md 분석, Plan 문서의 FR 요구사항 매핑, Pydantic v2 도메인 모델 설계, ChromaDB 3개 컬렉션 학습 데이터 구조 설계, 피드백 루프 스키마 설계, Redash 연동 데이터 모델 설계 |

### 문서 섹션별 주요 기여

| 섹션 | 기여 에이전트 | 기여 내용 |
|------|-------------|----------|
| §4.1 Pydantic 도메인 모델 | `data-modeler` | data_schema_design.md 3+2 테이블 → Pydantic v2 모델 변환, MVP QueryResponse 확장 설계 |
| §4.2 ChromaDB 컬렉션 구조 | `data-modeler` | Vanna SDK 내부 컬렉션 분석, 4카테고리 Documentation 설계, QA 예제 10개 SQL 작성 |
| §4.3 피드백 & 자가학습 | `data-modeler` | Plan FR-10/FR-16/FR-21 기반 피드백 흐름 설계, History 저장소 옵션 비교 |
| §4.4 쿼리 이력 저장소 | `data-modeler` | S3 경로 규칙, Redash 이력 연동 방안, TrainingDataRecord 출처 추적 |
| §4.5 Redash 연동 스키마 | `data-modeler` | Plan §4 환경변수 기반 Redash API 모델 설계, SQL 해시 중복 방지 로직 |

#!/usr/bin/env python3
"""
ChromaDB 초기 학습 데이터 시딩 스크립트.

Vanna AI SDK의 3개 컬렉션(sql-ddl, sql-documentation, sql-qa)에
설계 문서 기준의 학습 데이터를 주입합니다.

참조: docs/t1/text-to-sql/02-design/features/text-to-sql.design.md §4.2
"""

import os
import sys
import logging

# sys.path 설정 — /app 이하의 모듈 임포트 가능
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from src.query_pipeline import QueryPipeline
except ImportError as e:
    raise ImportError(
        "Required packages not found. Install with: pip install -r services/vanna-api/requirements.txt"
    ) from e

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


# ========================= DDL 정의 =========================

DDL_AD_COMBINED_LOG = """
CREATE TABLE ad_combined_log (
    -- Impression 관련 컬럼
    impression_id STRING,
    user_id STRING,
    ad_id STRING,
    campaign_id STRING,
    advertiser_id STRING,
    platform STRING,
    device_type STRING,
    os STRING,
    delivery_region STRING,
    user_lat DOUBLE,
    user_long DOUBLE,
    store_id STRING,
    food_category STRING,
    ad_position STRING,
    ad_format STRING,
    user_agent STRING,
    ip_address STRING,
    session_id STRING,
    keyword STRING,
    cost_per_impression DOUBLE,
    impression_timestamp BIGINT,

    -- Click 관련 컬럼
    click_id STRING,
    click_position_x INT,
    click_position_y INT,
    landing_page_url STRING,
    cost_per_click DOUBLE,
    click_timestamp BIGINT,

    -- Flag
    is_click BOOLEAN,

    -- Partition 컬럼
    year STRING,
    month STRING,
    day STRING,
    hour STRING
)
PARTITIONED BY (year STRING, month STRING, day STRING, hour STRING)
STORED AS PARQUET
COMMENT '광고 노출 및 클릭 이벤트 (시간 단위 로그)'
"""

DDL_AD_COMBINED_LOG_SUMMARY = """
CREATE TABLE ad_combined_log_summary (
    -- Impression 관련 컬럼
    impression_id STRING,
    user_id STRING,
    ad_id STRING,
    campaign_id STRING,
    advertiser_id STRING,
    platform STRING,
    device_type STRING,
    os STRING,
    delivery_region STRING,
    user_lat DOUBLE,
    user_long DOUBLE,
    store_id STRING,
    food_category STRING,
    ad_position STRING,
    ad_format STRING,
    user_agent STRING,
    ip_address STRING,
    session_id STRING,
    keyword STRING,
    cost_per_impression DOUBLE,
    impression_timestamp BIGINT,

    -- Click 관련 컬럼
    click_id STRING,
    click_position_x INT,
    click_position_y INT,
    landing_page_url STRING,
    cost_per_click DOUBLE,
    click_timestamp BIGINT,

    -- Click Flag
    is_click BOOLEAN,

    -- Conversion 관련 컬럼
    conversion_id STRING,
    conversion_type STRING,
    conversion_value DOUBLE,
    product_id STRING,
    quantity INT,
    attribution_window STRING,
    conversion_timestamp BIGINT,

    -- Conversion Flag
    is_conversion BOOLEAN,

    -- Partition 컬럼
    year STRING,
    month STRING,
    day STRING
)
PARTITIONED BY (year STRING, month STRING, day STRING)
STORED AS PARQUET
COMMENT '광고 성과 일일 요약 (노출+클릭+전환 데이터)'
"""


# ========================= Documentation 정의 =========================

DOCUMENTATION_BUSINESS_METRICS = """
# 비즈니스 지표 (Business Metrics)

## CTR (Click-Through Rate) — 퍼센트(%) 단위
- 정의: (클릭 수) / (노출 수) * 100
- 의미: 사용자가 광고를 본 후 클릭할 확률 (%)
- Athena 계산식: ROUND(SUM(CAST(is_click AS INT)) * 100.0 / COUNT(*), 2) AS ctr_percent
- 예시값: 2.35 (2.35%)

## CVR (Conversion Rate) — 퍼센트(%) 단위
- 정의: (전환 수) / (클릭 수) * 100
- 의미: 클릭한 사용자 중 실제 전환까지 이르는 확률 (%)
- Athena 계산식: ROUND(SUM(CAST(is_conversion AS INT)) * 100.0 / NULLIF(SUM(CAST(is_click AS INT)), 0), 2) AS cvr_percent
- 주의: ad_combined_log_summary 테이블 필수 (conversion 데이터가 여기에만 있음)
- NULLIF(분모, 0) 으로 클릭이 0인 경우 NULL 처리 필수

## ROAS (Return On Ad Spend) — 퍼센트(%) 단위
- 정의: (전환 매출액) / (광고비 총액) * 100
- 의미: 광고비 100원당 얼마의 매출을 얻었는가 (%)
- 광고비 = cost_per_impression + cost_per_click
- Athena 계산식: ROUND(SUM(conversion_value) / NULLIF(SUM(cost_per_impression + cost_per_click), 0) * 100, 2) AS roas_percent
- 예시값: 250.0 (광고비 대비 250% 매출, 즉 2.5배 ROAS)
- 주의: ad_combined_log_summary 테이블 필수 (conversion_value가 여기에만 있음)

## CPA (Cost Per Acquisition)
- 정의: (광고비 총액) / (전환 수)
- 의미: 하나의 전환을 얻기 위한 평균 광고비
- Athena 계산식: ROUND(SUM(cost_per_impression + cost_per_click) / NULLIF(SUM(CAST(is_conversion AS INT)), 0), 2) AS cpa

## CPC (Cost Per Click)
- 정의: (광고비 총액) / (클릭 수)
- 의미: 하나의 클릭을 얻기 위한 평균 광고비
- Athena 계산식: ROUND(SUM(cost_per_click) / NULLIF(SUM(CAST(is_click AS INT)), 0), 2) AS cpc
"""

DOCUMENTATION_ATHENA_RULES = """
# Athena 쿼리 규칙 (Athena Query Rules)
# Athena는 Presto/Trino SQL 방언을 사용합니다.

## 파티션 조건 (필수 — 누락 시 풀스캔으로 비용 급증)
- ad_combined_log 테이블: year, month, day, hour 파티션 필수
  단일 시점: WHERE year='2026' AND month='03' AND day='14' AND hour='09'
  범위 조건: WHERE year='2026' AND month='03' AND day >= '08' AND day <= '14'
- ad_combined_log_summary 테이블: year, month, day 파티션 필수
  단일 날짜: WHERE year='2026' AND month='03' AND day='14'
  범위 조건: WHERE year='2026' AND month='03' AND day BETWEEN '08' AND '14'
- 항상 파티션 컬럼(year/month/day)을 WHERE 절 맨 앞에 위치

## Presto SQL 방언 — 날짜/시간 함수
- UNIX 타임스탐프 → TIMESTAMP: from_unixtime(impression_timestamp)
- 날짜 추출: date(from_unixtime(impression_timestamp))
- 시간대 추출: hour(from_unixtime(impression_timestamp))
- 주 시작일 truncate: date_trunc('week', date(from_unixtime(impression_timestamp)))
- 월 시작일 truncate: date_trunc('month', date(from_unixtime(impression_timestamp)))
- 날짜 차이(일): date_diff('day', date('2026-03-01'), date('2026-03-14'))
- 현재 날짜: current_date  (주의: Athena에서는 NOW() 대신 current_date 사용)
- 날짜 포맷: date_format(from_unixtime(impression_timestamp), '%Y-%m-%d')

## Presto SQL 방언 — 타입 캐스팅
- BOOLEAN → INT: CAST(is_click AS INT)  (true=1, false=0)
- STRING → BIGINT: CAST(year AS BIGINT)
- NULL 안전 나눗셈: NULLIF(분모, 0) 사용 (0으로 나누기 방지)

## 제한사항
- SELECT 전용 쿼리만 허용 (INSERT, UPDATE, DELETE, DROP 금지)
- LIMIT 절은 반드시 최대 10,000 이하로 지정
- 스캔 크기 제한: 최대 1GB (Athena Workgroup 강제 설정)

## 비용 절감
- 파티션 조건으로 스캔 범위 반드시 제한
- 필요한 컬럼만 SELECT (SELECT * 지양)
- 집계 쿼리는 GROUP BY 사용
- 서브쿼리보다 WITH(CTE) 구문 선호
"""

DOCUMENTATION_POLICY = """
# 비즈니스 정책 및 코드값 (Policy & Code Values)

## device_type 코드값
- 'mobile': 모바일 기기
- 'tablet': 태블릿 기기
- 'desktop': 데스크톱 컴퓨터
- 'others': 기타 기기

## conversion_type 코드값
- 'purchase': 구매 전환
- 'signup': 회원가입 전환
- 'download': 앱 다운로드 전환
- 'view_content': 콘텐츠 조회 전환
- 'add_to_cart': 장바구니 추가 전환

## platform 실제 컬럼값
- 'web': 웹 플랫폼
- 'app_ios': iOS 앱
- 'app_android': Android 앱
- 'tablet_ios': iPad
- 'tablet_android': Android 태블릿

## ad_format 광고 포맷
- 'display': 디스플레이 광고
- 'native': 네이티브 광고
- 'video': 비디오 광고
- 'discount_coupon': 할인 쿠폰 광고

## 테이블 선택 기준
- **시간 단위 분석 필요** (시간대별, 시간 범위 내 데이터): ad_combined_log 사용
- **전환 데이터 필요, 일간 집계**: ad_combined_log_summary 사용
- **일간 분석** (일별 합계, 추이): ad_combined_log_summary 선호

## JOIN 패턴
- 같은 테이블 내에서 campaign_id, user_id, advertiser_id로 JOIN 가능
- 외부 테이블과의 JOIN은 store_id, food_category 기준
"""

DOCUMENTATION_GLOSSARY = """
# 광고 도메인 용어사전 (Glossary)

## 용어 정의
- **노출(Impression)**: 광고가 사용자 화면에 보여진 횟수
- **클릭(Click)**: 사용자가 노출된 광고를 클릭한 횟수
- **전환(Conversion)**: 광고 클릭 이후 구매, 가입 등 목표 행동 달성
- **속성(Attribution)**: 전환을 어느 광고에 귀속할지 결정하는 방식
- **캠페인(Campaign)**: 하나의 광고 목표를 위해 묶인 광고 그룹
- **광고주(Advertiser)**: 광고를 집행하는 주체
- **매출액(Revenue/conversion_value)**: 전환으로 발생한 실제 매출
"""


# ========================= QA 예제 =========================

QA_EXAMPLES = [
    {
        "question": "어제 전체 광고의 노출수와 클릭수, 클릭률(CTR)을 보여줘",
        "sql": """
SELECT
    COUNT(*) as total_impressions,
    SUM(CAST(is_click AS INT)) as total_clicks,
    ROUND(SUM(CAST(is_click AS INT)) * 100.0 / COUNT(*), 2) as ctr_percent
FROM ad_combined_log_summary
WHERE year='2026' AND month='03' AND day='13'
"""
    },
    {
        "question": "지난달 캠페인별 광고비(cost_per_impression+cost_per_click 합계)를 구해줘",
        "sql": """
SELECT
    campaign_id,
    ROUND(SUM(cost_per_impression + cost_per_click), 2) as total_ad_spend
FROM ad_combined_log_summary
WHERE year='2026' AND month='02'
GROUP BY campaign_id
ORDER BY total_ad_spend DESC
"""
    },
    {
        "question": "이번주 일별 클릭률 추이를 보여줘",
        "sql": """
SELECT
    day,
    COUNT(*) as impressions,
    SUM(CAST(is_click AS INT)) as clicks,
    ROUND(SUM(CAST(is_click AS INT)) * 100.0 / COUNT(*), 2) as ctr_percent
FROM ad_combined_log_summary
WHERE year='2026' AND month='03' AND day BETWEEN '08' AND '14'
GROUP BY day
ORDER BY day
"""
    },
    {
        "question": "ROAS가 100% 이상인 캠페인을 찾아줘",
        "sql": """
SELECT
    campaign_id,
    ROUND(SUM(cost_per_impression + cost_per_click), 2) as ad_spend,
    ROUND(SUM(conversion_value), 2) as revenue,
    ROUND(SUM(conversion_value) / (SUM(cost_per_impression + cost_per_click)) * 100, 2) as roas_percent
FROM ad_combined_log_summary
WHERE year='2026' AND month='03'
GROUP BY campaign_id
HAVING SUM(conversion_value) >= SUM(cost_per_impression + cost_per_click)
ORDER BY roas_percent DESC
"""
    },
    {
        "question": "기기별(device_type) 클릭수를 비교해줘",
        "sql": """
SELECT
    device_type,
    COUNT(*) as impressions,
    SUM(CAST(is_click AS INT)) as total_clicks,
    ROUND(SUM(CAST(is_click AS INT)) * 100.0 / COUNT(*), 2) as ctr_percent
FROM ad_combined_log_summary
WHERE year='2026' AND month='03' AND day='14'
GROUP BY device_type
ORDER BY total_clicks DESC
"""
    },
    {
        "question": "food_category별 전환율(CVR) TOP 5를 구해줘",
        "sql": """
SELECT
    food_category,
    SUM(CAST(is_click AS INT)) as clicks,
    SUM(CAST(is_conversion AS INT)) as conversions,
    ROUND(SUM(CAST(is_conversion AS INT)) * 100.0 / SUM(CAST(is_click AS INT)), 2) as cvr_percent
FROM ad_combined_log_summary
WHERE year='2026' AND month='03'
GROUP BY food_category
HAVING SUM(CAST(is_click AS INT)) > 0
ORDER BY cvr_percent DESC
"""
    },
    {
        "question": "최근 7일간 클릭이 0인 campaign_id 목록을 보여줘",
        "sql": """
SELECT DISTINCT
    campaign_id
FROM ad_combined_log_summary
WHERE year='2026' AND month='03' AND day BETWEEN '08' AND '14'
GROUP BY campaign_id
HAVING SUM(CAST(is_click AS INT)) = 0
ORDER BY campaign_id
"""
    },
    {
        "question": "일별 cost_per_impression 합계가 가장 높은 날짜는?",
        "sql": """
SELECT
    day,
    ROUND(SUM(cost_per_impression), 2) as total_cpi_spend
FROM ad_combined_log_summary
WHERE year='2026' AND month='03'
GROUP BY day
ORDER BY total_cpi_spend DESC
"""
    },
    {
        "question": "캠페인별 일별 광고비(cost_per_impression+cost_per_click 합계) 분포를 보여줘",
        "sql": """
SELECT
    campaign_id,
    day,
    ROUND(SUM(cost_per_impression + cost_per_click), 2) as daily_ad_spend
FROM ad_combined_log_summary
WHERE year='2026' AND month='03'
GROUP BY campaign_id, day
ORDER BY campaign_id, day
"""
    },
    {
        "question": "지난주 대비 이번주 노출수 증감률을 구해줘",
        "sql": """
WITH last_week AS (
    SELECT SUM(1) as last_week_impressions
    FROM ad_combined_log_summary
    WHERE year='2026' AND month='03' AND day BETWEEN '01' AND '07'
),
this_week AS (
    SELECT SUM(1) as this_week_impressions
    FROM ad_combined_log_summary
    WHERE year='2026' AND month='03' AND day BETWEEN '08' AND '14'
)
SELECT
    lw.last_week_impressions,
    tw.this_week_impressions,
    ROUND((tw.this_week_impressions - lw.last_week_impressions) * 100.0 / lw.last_week_impressions, 2) as growth_rate_percent
FROM last_week lw, this_week tw
"""
    }
]


def initialize_vanna():
    """Vanna + ChromaDB 인스턴스 초기화 (QueryPipeline을 통한 접근)."""
    logger.info("Vanna + ChromaDB 인스턴스 초기화 중...")

    try:
        # QueryPipeline 초기화 — vanna_instance=None 으로 실제 ChromaDB 자동 연결
        pipeline = QueryPipeline(
            vanna_instance=None,  # 실제 ChromaDB 자동 연결 (CHROMA_HOST 환경변수 사용)
            anthropic_api_key=os.getenv("ANTHROPIC_API_KEY", ""),
            athena_client=None,    # 시딩용으로는 Athena 불필요
            database=os.getenv("ATHENA_DATABASE", "capa_db"),
            workgroup=os.getenv("ATHENA_WORKGROUP", "primary"),
            s3_staging_dir=os.getenv("S3_STAGING_DIR", "s3://test-bucket/results/"),
        )

        vanna_instance = pipeline._vanna
        logger.info("Vanna 인스턴스 생성 완료 (QueryPipeline._vanna)")
        return vanna_instance
    except Exception as e:
        logger.error(f"Vanna 초기화 실패: {e}")
        raise


def train_ddl(vanna_instance) -> None:
    """DDL 학습."""
    logger.info("DDL 학습 시작...")

    try:
        # ad_combined_log DDL 학습
        vanna_instance.train(
            ddl=DDL_AD_COMBINED_LOG,
            documentation="테이블: ad_combined_log - 광고 노출 및 클릭 이벤트 (시간 단위)"
        )
        logger.info("✓ ad_combined_log DDL 학습 완료")

        # ad_combined_log_summary DDL 학습
        vanna_instance.train(
            ddl=DDL_AD_COMBINED_LOG_SUMMARY,
            documentation="테이블: ad_combined_log_summary - 광고 성과 일일 요약 (전환 데이터 포함)"
        )
        logger.info("✓ ad_combined_log_summary DDL 학습 완료")

    except Exception as e:
        logger.error(f"DDL 학습 실패: {e}")
        raise


def train_documentation(vanna_instance) -> None:
    """Documentation 학습."""
    logger.info("Documentation 학습 시작...")

    docs = [
        ("비즈니스 지표", DOCUMENTATION_BUSINESS_METRICS),
        ("Athena 쿼리 규칙", DOCUMENTATION_ATHENA_RULES),
        ("비즈니스 정책", DOCUMENTATION_POLICY),
        ("용어사전", DOCUMENTATION_GLOSSARY),
    ]

    try:
        for doc_name, doc_content in docs:
            vanna_instance.train(
                documentation=doc_content
            )
            logger.info(f"✓ {doc_name} 학습 완료")
    except Exception as e:
        logger.error(f"Documentation 학습 실패: {e}")
        raise


def train_qa_examples(vanna_instance) -> None:
    """QA 예제 학습."""
    logger.info(f"QA 예제 학습 시작 ({len(QA_EXAMPLES)}개)...")

    try:
        for idx, qa in enumerate(QA_EXAMPLES, 1):
            vanna_instance.train(
                question=qa["question"],
                sql=qa["sql"]
            )
            logger.info(f"✓ QA 예제 {idx}/{len(QA_EXAMPLES)} 학습 완료")
    except Exception as e:
        logger.error(f"QA 예제 학습 실패: {e}")
        raise


def verify_training(vanna_instance) -> None:
    """학습 데이터 검증 (RAG 테스트)."""
    logger.info("학습 데이터 검증 시작...")

    test_queries = [
        "어제 클릭률을 구해줘",
        "CTR을 계산하는 방법은?",
        "ROAS가 높은 캠페인을 찾아줘",
    ]

    try:
        for test_query in test_queries:
            retrieved_context = vanna_instance.get_similar_question_sql(test_query)
            if retrieved_context:
                logger.info(f"✓ 테스트 쿼리 '{test_query}': 관련 예제 검색 성공")
            else:
                logger.warning(f"⚠ 테스트 쿼리 '{test_query}': 관련 예제 미검색")
    except Exception as e:
        logger.warning(f"검증 중 오류 (무시 가능): {e}")


def main() -> None:
    """메인 실행 함수."""
    logger.info("=" * 80)
    logger.info("ChromaDB 초기 학습 데이터 시딩 시작")
    logger.info("=" * 80)

    try:
        # 1. Vanna 인스턴스 초기화
        vanna = initialize_vanna()

        # 2. DDL 학습 (테이블 스키마)
        train_ddl(vanna)

        # 3. Documentation 학습 (비즈니스 규칙, 정책)
        train_documentation(vanna)

        # 4. QA 예제 학습 (Few-shot 예제)
        train_qa_examples(vanna)

        # 5. 검증
        verify_training(vanna)

        logger.info("=" * 80)
        logger.info("✓ ChromaDB 시딩 완료!")
        logger.info("=" * 80)
        logger.info(f"학습된 컨텐츠:")
        logger.info(f"  - DDL: 2개 테이블")
        logger.info(f"  - Documentation: 4개 문서 (비즈니스 지표, Athena 규칙, 정책, 용어사전)")
        logger.info(f"  - QA 예제: {len(QA_EXAMPLES)}개 (Few-shot 학습)")

    except Exception as e:
        logger.error("=" * 80)
        logger.error(f"시딩 실패: {e}")
        logger.error("=" * 80)
        raise


if __name__ == "__main__":
    main()

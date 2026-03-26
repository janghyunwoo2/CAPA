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
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


# ========================= DDL 정의 =========================

DDL_AD_COMBINED_LOG = """
CREATE EXTERNAL TABLE ad_combined_log (
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
CREATE EXTERNAL TABLE ad_combined_log_summary (
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


# ========================= Documentation 정의 (list[str]) =========================

DOCS_BUSINESS_METRICS: list[str] = [
    """CTR(클릭률)은 사용자가 광고를 본 후 실제로 클릭할 확률을 나타내는 지표로,
클릭 수를 노출 수로 나눈 후 100을 곱한 퍼센트(%) 값으로 반환합니다.
올바른 Athena 계산식: ROUND(SUM(CAST(is_click AS INT)) * 100.0 / NULLIF(COUNT(*), 0), 2) AS ctr_percent
주의: NULLIF로 노출수 0인 경우 Division by Zero 방지 필수""",
    """CVR(전환율)은 광고를 클릭한 사용자 중 전환까지 이른 비율을 나타내며,
전환 수를 클릭 수로 나눈 후 100을 곱한 퍼센트(%) 값으로 반환합니다.
분모는 반드시 클릭수여야 하며 전체 노출수(COUNT(*))를 분모로 사용하면 안 됩니다.
올바른 Athena 계산식: ROUND(SUM(CAST(is_conversion AS INT)) * 100.0 / NULLIF(SUM(CAST(is_click AS INT)), 0), 2) AS cvr_percent
주의: ad_combined_log_summary 테이블 필수 (is_conversion 컬럼이 여기에만 존재)""",
    """ROAS (Return On Ad Spend) — 광고 수익률 (비율)
정의: (전환 매출액) / (광고비 총액)
의미: 광고비 대비 매출 비율
⚠️ SQL 출력 규칙:
  - 분모는 반드시 cost_per_impression + cost_per_click 합산 (단일 컬럼 사용 금지)
  - NULLIF로 0 나눗셈 방지 필수
올바른 Athena 계산식:
  SUM(CASE WHEN is_conversion = true THEN conversion_value ELSE 0 END)
  / NULLIF(SUM(cost_per_impression + cost_per_click), 0) AS roas
주의: ad_combined_log_summary 테이블 필수 (conversion_value가 여기에만 있음)""",
    """CPA (Cost Per Acquisition) — 전환당 광고비
정의: (광고비 총액) / (전환 수)
의미: 하나의 전환을 얻기 위한 평균 광고비
⚠️ SQL 출력 규칙:
  - 분자는 반드시 cost_per_impression + cost_per_click 합산 (단일 컬럼 사용 금지)
  - NULLIF로 0 나눗셈 방지 필수
올바른 Athena 계산식:
  SUM(cost_per_impression + cost_per_click)
  / NULLIF(COUNT(CASE WHEN is_conversion = true THEN 1 END), 0) AS cpa
주의: 전환이 0인 경우 NULLIF로 NULL 처리 필수""",
    """CPC (Cost Per Click) — 클릭당 광고비
정의: (광고비 총액) / (클릭 수)
의미: 하나의 클릭을 얻기 위한 평균 광고비
Athena 계산식: SUM(cost_per_click) / NULLIF(COUNT(CASE WHEN is_click = true THEN 1 END), 0) AS cpc
주의: 클릭이 0인 경우 NULLIF로 NULL 처리 필수""",
    """비즈니스 지표 공통 규칙:
- CTR, CVR, ROAS, CPA, CPC 모두 NULLIF(분모, 0) 필수 — Division by Zero 방지
- CVR, ROAS, CPA는 반드시 ad_combined_log_summary 테이블 사용 (conversion 데이터 필요)
- CTR, CPC는 ad_combined_log 또는 ad_combined_log_summary 모두 사용 가능
- 시간대별(hour) 분석은 ad_combined_log 테이블 사용 (hour 파티션 존재)
- CTR/CVR은 퍼센트(%) 형식으로 반환 (ROUND(...* 100.0 / NULLIF(...), 2) AS ctr_percent/cvr_percent)""",
]

DOCS_ATHENA_RULES: list[str] = [
    """Athena 파티션 조건 (필수 — 누락 시 풀스캔으로 비용 급증)
ad_combined_log 테이블: year, month, day, hour 파티션 필수
  단일 시점: WHERE year='2026' AND month='03' AND day='14' AND hour='09'
  범위 조건: WHERE year='2026' AND month='03' AND day >= '08' AND day <= '14'
ad_combined_log_summary 테이블: year, month, day 파티션 필수
  단일 날짜: WHERE year='2026' AND month='03' AND day='14'
  범위 조건: WHERE year='2026' AND month='03' AND day BETWEEN '08' AND '14'
항상 파티션 컬럼(year/month/day)을 WHERE 절 맨 앞에 위치
동적 날짜 사용 권장: date_format(date_add('day', -1, current_date), '%d') AS 어제의 day값""",
    """Athena(Presto/Trino) SQL 날짜·시간 함수
UNIX 타임스탬프 → TIMESTAMP: from_unixtime(impression_timestamp)
날짜 추출: date(from_unixtime(impression_timestamp))
시간대 추출: hour(from_unixtime(impression_timestamp))
주 시작일 truncate: date_trunc('week', date(from_unixtime(impression_timestamp)))
월 시작일 truncate: date_trunc('month', date(from_unixtime(impression_timestamp)))
현재 날짜: current_date (Athena에서는 NOW() 대신 current_date 사용)
날짜 포맷: date_format(current_date, '%Y-%m-%d')
날짜 더하기: date_add('day', -1, current_date) / date_add('month', -1, current_date)
요일 번호: day_of_week(date) — 1=월요일, 7=일요일""",
    """Athena SQL 타입 캐스팅 및 NULL 처리
BOOLEAN → INT: CAST(is_click AS INT)  (true=1, false=0)
STRING → BIGINT: CAST(year AS BIGINT)
NULL 안전 나눗셈: NULLIF(분모, 0) 사용 (0으로 나누기 방지)
NULL 대체: COALESCE(값, 기본값) 사용
서브쿼리보다 WITH(CTE) 구문 선호 — 가독성 및 재사용성 향상""",
    """Athena 쿼리 제한사항 및 비용 절감
SELECT 전용 쿼리만 허용 (INSERT, UPDATE, DELETE, DROP 금지)
LIMIT 절은 반드시 최대 10,000 이하로 지정
스캔 크기 제한: 최대 1GB (Athena Workgroup 강제 설정)
파티션 조건으로 스캔 범위 반드시 제한
필요한 컬럼만 SELECT (SELECT * 지양)
집계 쿼리는 GROUP BY 사용""",
    """Athena 미지원 SQL 구문 — 반드시 대체 방법 사용
[OFFSET 미지원]
  금지: ORDER BY click_count DESC LIMIT 1 OFFSET 1
  대체: ROW_NUMBER() OVER (ORDER BY click_count DESC) — 'N번째로 높은/낮은' 결과
  예시:
    SELECT device_type FROM (
      SELECT device_type,
             ROW_NUMBER() OVER (ORDER BY click_count DESC) AS rn
      FROM (SELECT device_type, COUNT(*) AS click_count
            FROM ad_combined_log_summary
            WHERE year='2026' AND month='03' AND day='24'
            GROUP BY device_type)
    ) WHERE rn = 2

[DATEDIFF 미지원]
  금지: DATEDIFF(click_timestamp, impression_timestamp)
  대체: date_diff('second', from_unixtime(impression_timestamp), from_unixtime(click_timestamp))
  단위: 'day' | 'hour' | 'minute' | 'second'

[MEDIAN 미지원]
  금지: MEDIAN(cost_per_click)
  대체: approx_percentile(cost_per_click, 0.5)

[ILIKE 미지원 — 대소문자 무관 검색]
  금지: keyword ILIKE '%패션%'
  대체: LOWER(keyword) LIKE LOWER('%패션%')

[SELECT TOP N 미지원 — SQL Server 방언]
  금지: SELECT TOP 10 campaign_id FROM ...
  대체: SELECT campaign_id FROM ... LIMIT 10

[QUALIFY 미지원 — BigQuery/Snowflake 방언]
  금지: SELECT ... QUALIFY ROW_NUMBER() OVER (...) = 1
  대체: SELECT * FROM (SELECT ..., ROW_NUMBER() OVER (...) AS rn FROM ...) WHERE rn = 1

[STRING_AGG 미지원 — PostgreSQL/BigQuery 방언]
  금지: STRING_AGG(device_type, ',')
  대체: array_join(array_agg(device_type), ',')""",
]

DOCS_POLICIES: list[str] = [
    """device_type 코드값 정의
'mobile': 모바일 기기
'tablet': 태블릿 기기
'desktop': 데스크톱 컴퓨터
'others': 기타 기기""",
    """conversion_type 코드값 정의
'purchase': 구매 전환
'signup': 회원가입 전환
'download': 앱 다운로드 전환
'view_content': 콘텐츠 조회 전환
'add_to_cart': 장바구니 추가 전환""",
    """platform 컬럼 실제 코드값
'web': 웹 플랫폼
'app_ios': iOS 앱
'app_android': Android 앱
'tablet_ios': iPad
'tablet_android': Android 태블릿""",
    """ad_format 광고 포맷 코드값
'display': 디스플레이 광고
'native': 네이티브 광고
'video': 비디오 광고
'discount_coupon': 할인 쿠폰 광고
광고채널별 분석 시 ad_format 컬럼 사용 (platform 아님)""",
    """테이블 선택 기준
시간 단위 분석 필요 (시간대별, hour 기준): ad_combined_log 사용
전환 데이터 필요, 일간 집계: ad_combined_log_summary 사용
일간 분석 (일별 합계, 추이): ad_combined_log_summary 선호
주의: conversion_id, conversion_value, is_conversion 컬럼은 ad_combined_log_summary에만 존재""",
    """파티션 동적 날짜 표현 패턴 (하드코딩 금지)
어제: date_format(date_add('day', -1, current_date), '%Y/%m/%d')
이번달: date_format(current_date, '%Y') / date_format(current_date, '%m')
지난달: date_format(date_add('month', -1, current_date), '%Y/%m')
2개월 전: date_format(date_add('month', -2, current_date), '%Y/%m')
이번주 (최근 7일): day >= date_format(date_add('day', -6, current_date), '%d')""",
    """delivery_region 배달 지역 코드값
강남구, 서초구, 마포구, 종로구, 중구 등 서울 25개 자치구
지역별 분석 시 delivery_region 컬럼으로 GROUP BY""",
    """JOIN 패턴
같은 테이블 내에서 campaign_id, user_id, advertiser_id로 GROUP BY 가능
외부 테이블과의 JOIN은 store_id, food_category 기준
CTR/CVR를 campaign_id별로 분석할 때: GROUP BY campaign_id""",
    """이상 탐지 패턴 (Anomaly Detection)
클릭 0인 캠페인: HAVING SUM(CAST(is_click AS INT)) = 0
전환 0인 캠페인: HAVING COUNT(CASE WHEN is_conversion THEN 1 END) = 0
ROAS 100% 미만: HAVING roas_percent < 100""",
    """비용 집계 컬럼 정의
cost_per_impression: 노출 1회당 비용
cost_per_click: 클릭 1회당 비용
광고비 총액: SUM(cost_per_impression + cost_per_click)
클릭 비용만: SUM(cost_per_click)""",
]

DOCS_NONEXISTENT_COLUMNS: list[str] = [
    """[주의: 존재하지 않는 컬럼 — 절대 사용 금지]
- campaign_name → 없음. campaign_id만 존재 (campaign_01~campaign_05)
- ad_name       → 없음. ad_id만 존재 (ad_0001~ad_1000)
- advertiser_name → 없음. advertiser_id만 존재 (advertiser_01~advertiser_30)
- channel       → 없음. platform, ad_format, ad_position으로 세분화됨
- gender        → 없음
- age           → 없음
위 컬럼들을 WHERE 절이나 SELECT 절에 사용하면 Athena 쿼리 오류 발생.""",
]

DOCS_CATEGORICAL_VALUES: list[str] = [
    """[컬럼 범주값 및 범위 — 정확한 값만 조건에 사용할 것]
- platform:          web | app_ios | app_android | tablet_ios | tablet_android
- device_type:       mobile | tablet | desktop | others
- os:                ios | android | macos | windows
- conversion_type:   purchase | signup | download | view_content | add_to_cart
- ad_format:         display | native | video | discount_coupon
- ad_position:       home_top_rolling | list_top_fixed | search_ai_recommend | checkout_bottom
- attribution_window: 1day | 7day | 30day
- food_category:     chicken | pizza | korean | chinese | dessert (외 10개)
- delivery_region:   강남구 | 서초구 | 마포구 등 서울 25개 자치구 (예: '강남구', '종로구')
- user_id:           user_000001 ~ user_100000
- ad_id:             ad_0001 ~ ad_1000
- campaign_id:       campaign_01 ~ campaign_05
- advertiser_id:     advertiser_01 ~ advertiser_30
- store_id:          store_0001 ~ store_5000
- product_id:        prod_00001 ~ prod_10000
- cost_per_impression: 0.005 ~ 0.10
- cost_per_click:    0.1 ~ 5.0
- conversion_value:  1.0 ~ 10000.0
- quantity:          1 ~ 10
- user_lat:          37.4 ~ 37.7 (서울 범위)
- user_long:         126.8 ~ 127.1 (서울 범위)
대소문자 구분: 모두 소문자 (예: 'Mobile' → 오류, 'mobile' → 정상)""",
]

DOCS_GLOSSARY: list[str] = [
    """광고 도메인 용어사전 (Glossary)
노출(Impression): 광고가 사용자 화면에 보여진 횟수
클릭(Click): 사용자가 노출된 광고를 클릭한 횟수
전환(Conversion): 광고 클릭 이후 구매, 가입 등 목표 행동 달성
속성(Attribution): 전환을 어느 광고에 귀속할지 결정하는 방식
캠페인(Campaign): 하나의 광고 목표를 위해 묶인 광고 그룹
광고주(Advertiser): 광고를 집행하는 주체
매출액(Revenue/conversion_value): 전환으로 발생한 실제 매출
광고채널(Ad Format/ad_format): 광고가 노출되는 형태 (display/native/video/discount_coupon)
플랫폼(Platform): 광고가 노출되는 환경 (web/app_ios/app_android)""",
]

DOCS_NEGATIVE_EXAMPLES: list[str] = [
    """[오답 패턴 1] CTR/CVR 계산 시 NULLIF 누락 금지
CTR이나 CVR을 계산할 때 분모에 NULLIF를 사용하지 않으면 노출수가 0인 경우 Division by Zero 오류가 발생합니다.
잘못된 쿼리: SUM(CAST(is_click AS INT)) * 100.0 / COUNT(*) AS ctr_percent
올바른 쿼리: ROUND(SUM(CAST(is_click AS INT)) * 100.0 / NULLIF(COUNT(*), 0), 2) AS ctr_percent
CVR도 동일하게 NULLIF(SUM(CAST(is_click AS INT)), 0)을 분모로 사용해야 합니다.""",

    """[오답 패턴 2] 파티션 조건 날짜 하드코딩 금지
Athena 쿼리에서 날짜를 직접 상수로 입력하면 시간이 지나면 틀린 쿼리가 됩니다.
잘못된 쿼리: WHERE year='2026' AND month='03' AND day='25'
올바른 쿼리 (어제): WHERE year=date_format(date_add('day',-1,current_date),'%Y')
  AND month=date_format(date_add('day',-1,current_date),'%m')
  AND day=date_format(date_add('day',-1,current_date),'%d')
파티션 조건은 반드시 current_date 기반의 동적 날짜 표현을 사용해야 합니다.""",

    """[오답 패턴 3] CVR 분모 혼동 (노출수 대신 클릭수 사용)
CVR(전환율)의 분모는 반드시 클릭수여야 하며, 전체 노출수를 분모로 사용하면 안 됩니다.
잘못된 쿼리: ROUND(SUM(CAST(is_conversion AS INT)) * 100.0 / NULLIF(COUNT(*), 0), 2) AS cvr_percent
올바른 쿼리: ROUND(SUM(CAST(is_conversion AS INT)) * 100.0 / NULLIF(SUM(CAST(is_click AS INT)), 0), 2) AS cvr_percent
COUNT(*)는 전체 노출수이므로 CVR이 아닌 CTR의 분모가 됩니다.""",

    """[오답 패턴 4] Athena 미지원 OFFSET 사용 금지
Athena(Presto/Trino)는 OFFSET 구문을 지원하지 않으므로 N번째 순위 조회에 사용하면 안 됩니다.
잘못된 쿼리: ORDER BY click_count DESC LIMIT 1 OFFSET 1
올바른 쿼리: SELECT device_type FROM (
  SELECT device_type, ROW_NUMBER() OVER (ORDER BY click_count DESC) AS rn FROM ...
) WHERE rn = 2
N번째로 높은 값을 구할 때는 반드시 ROW_NUMBER() 윈도우 함수를 사용해야 합니다.""",

    """[오답 패턴 5] 존재하지 않는 컬럼 사용 금지
아래 컬럼들은 스키마에 존재하지 않아 Athena 쿼리 실행 시 오류가 발생합니다.
금지 컬럼: campaign_name, ad_name, advertiser_name, channel, gender, age
대체 방법: campaign_id (campaign_01~05), ad_id (ad_0001~1000), advertiser_id (advertiser_01~30) 사용
이름(name) 대신 ID 컬럼만 존재하므로 GROUP BY나 WHERE 조건에 name 계열 컬럼을 절대 쓰면 안 됩니다.""",

    """[오답 패턴 6] conversion 관련 컬럼을 ad_combined_log에서 조회 금지
conversion_id, conversion_value, is_conversion, conversion_type, attribution_window 컬럼은
ad_combined_log_summary 테이블에만 존재하며 ad_combined_log에는 없습니다.
잘못된 쿼리: SELECT COUNT(CASE WHEN is_conversion=true THEN 1 END) FROM ad_combined_log
올바른 쿼리: SELECT COUNT(CASE WHEN is_conversion=true THEN 1 END) FROM ad_combined_log_summary
CVR, ROAS, CPA 등 전환 관련 지표는 반드시 ad_combined_log_summary 테이블을 사용해야 합니다.""",

    """[오답 패턴 7] 질문에서 요청하지 않은 컬럼을 SELECT에 추가 금지
사용자가 특정 지표만 요청하면 그 지표만 SELECT에 포함해야 합니다.
잘못된 예: '음식 카테고리별 CTR 상위 10개'를 요청했는데 impressions, clicks를 추가로 SELECT
올바른 쿼리: SELECT food_category, ROUND(SUM(CAST(is_click AS INT)) * 100.0 / NULLIF(COUNT(*), 0), 2) AS ctr_percent
잘못된 쿼리: SELECT food_category, COUNT(*) AS impressions, SUM(CAST(is_click AS INT)) AS clicks, ROUND(...) AS ctr_percent
요청한 컬럼과 집계 기준(GROUP BY 대상)만 SELECT에 포함하세요.""",

    """[오답 패턴 8] 전환 매출 집계 시 CASE WHEN...ELSE 0 대신 WHERE is_conversion=true 사용
전환이 발생한 행의 conversion_value를 합산할 때 CASE WHEN으로 우회하면 안 됩니다.
잘못된 쿼리: SUM(CASE WHEN is_conversion=true THEN conversion_value ELSE 0 END) AS total_revenue
올바른 쿼리: SUM(conversion_value) AS total_revenue ... WHERE is_conversion=true
전환 데이터만 조회할 때는 반드시 WHERE 절에 AND is_conversion=true를 추가하세요.""",
]

# DOCS_SCHEMA_MAPPER 삭제 — SchemaMapper 제거로 불필요 (Design §4.2)
# DDL 선택은 QA metadata 역추적(_extract_tables_from_qa_results)으로 대체됨


# ========================= QA 예제 (70개) =========================

QA_EXAMPLES = [
    # ── GROUP 1: CTR 기본 분석 ──────────────────────────────────────────────
    {
        "question": "어제 전체 광고의 노출수와 클릭수, 클릭률(CTR)을 보여줘",
        "sql": """
SELECT
    COUNT(*) AS total_impressions,
    SUM(CAST(is_click AS INT)) AS total_clicks,
    ROUND(SUM(CAST(is_click AS INT)) * 100.0 / COUNT(*), 2) AS ctr_percent
FROM ad_combined_log_summary
WHERE year  = date_format(date_add('day', -1, current_date), '%Y')
  AND month = date_format(date_add('day', -1, current_date), '%m')
  AND day   = date_format(date_add('day', -1, current_date), '%d')
""",
    },
    {
        "question": "이번주 일별 클릭률 추이를 보여줘",
        "sql": """
SELECT
    day,
    COUNT(*) AS impressions,
    SUM(CAST(is_click AS INT)) AS clicks,
    ROUND(SUM(CAST(is_click AS INT)) * 100.0 / COUNT(*), 2) AS ctr_percent
FROM ad_combined_log_summary
WHERE year  = date_format(current_date, '%Y')
  AND month = date_format(current_date, '%m')
  AND day  >= date_format(date_add('day', -6, current_date), '%d')
GROUP BY day
ORDER BY day
""",
    },
    {
        "question": "기기별로 시간대별 클릭 패턴을 분석해줘",
        "sql": """
SELECT
    device_type,
    hour,
    COUNT(*) AS impressions,
    SUM(CAST(is_click AS INT)) AS clicks,
    ROUND(SUM(CAST(is_click AS INT)) * 100.0 / COUNT(*), 2) AS ctr_percent
FROM ad_combined_log
WHERE year  = date_format(date_add('day', -1, current_date), '%Y')
  AND month = date_format(date_add('day', -1, current_date), '%m')
  AND day   = date_format(date_add('day', -1, current_date), '%d')
GROUP BY device_type, hour
ORDER BY device_type, hour
""",
    },
    {
        "question": "기기별(device_type) 클릭수와 클릭률(CTR)을 비교해줘",
        "sql": """
SELECT
    device_type,
    COUNT(*) AS impressions,
    SUM(CAST(is_click AS INT)) AS total_clicks,
    ROUND(SUM(CAST(is_click AS INT)) * 100.0 / COUNT(*), 2) AS ctr_percent
FROM ad_combined_log_summary
WHERE year  = date_format(date_add('day', -1, current_date), '%Y')
  AND month = date_format(date_add('day', -1, current_date), '%m')
  AND day   = date_format(date_add('day', -1, current_date), '%d')
GROUP BY device_type
ORDER BY total_clicks DESC
""",
    },
    # ── GROUP 2: CVR 전환율 분석 ──────────────────────────────────────────
    {
        "question": "food_category별 전환율(CVR) TOP 5를 구해줘",
        "sql": """
SELECT
    food_category,
    SUM(CAST(is_click AS INT)) AS clicks,
    SUM(CAST(is_conversion AS INT)) AS conversions,
    ROUND(SUM(CAST(is_conversion AS INT)) * 100.0 / NULLIF(SUM(CAST(is_click AS INT)), 0), 2) AS cvr_percent
FROM ad_combined_log_summary
WHERE year  = date_format(date_add('month', -1, current_date), '%Y')
  AND month = date_format(date_add('month', -1, current_date), '%m')
GROUP BY food_category
ORDER BY cvr_percent DESC
LIMIT 5
""",
    },
    {
        "question": "이번달 캠페인별 일별 전환율(CVR) 추이를 보여줘",
        "sql": """
SELECT
    campaign_id,
    day,
    SUM(CAST(is_click AS INT)) AS clicks,
    SUM(CAST(is_conversion AS INT)) AS conversions,
    ROUND(SUM(CAST(is_conversion AS INT)) * 100.0 / NULLIF(SUM(CAST(is_click AS INT)), 0), 2) AS cvr_percent
FROM ad_combined_log_summary
WHERE year  = date_format(current_date, '%Y')
  AND month = date_format(current_date, '%m')
GROUP BY campaign_id, day
ORDER BY campaign_id, day
""",
    },
    # ── GROUP 3: ROAS / CPA / CPC 수익성 분석 ────────────────────────────
    {
        "question": "ROAS가 100% 이상인 캠페인을 찾아줘",
        "sql": """
SELECT
    campaign_id,
    ROUND(SUM(cost_per_impression + cost_per_click), 2) AS ad_spend,
    ROUND(SUM(conversion_value), 2) AS revenue,
    ROUND(SUM(conversion_value) / NULLIF(SUM(cost_per_impression + cost_per_click), 0) * 100, 2) AS roas_percent
FROM ad_combined_log_summary
WHERE year  = date_format(current_date, '%Y')
  AND month = date_format(current_date, '%m')
GROUP BY campaign_id
HAVING SUM(conversion_value) >= SUM(cost_per_impression + cost_per_click)
ORDER BY roas_percent DESC
""",
    },
    {
        "question": "지난달 캠페인별 CPA(전환당 광고비)를 계산해줘",
        "sql": """
SELECT
    campaign_id,
    SUM(CAST(is_conversion AS INT)) AS conversions,
    ROUND(SUM(cost_per_impression + cost_per_click), 2) AS ad_spend,
    ROUND(SUM(cost_per_impression + cost_per_click) / NULLIF(SUM(CAST(is_conversion AS INT)), 0), 2) AS cpa
FROM ad_combined_log_summary
WHERE year  = date_format(date_add('month', -1, current_date), '%Y')
  AND month = date_format(date_add('month', -1, current_date), '%m')
GROUP BY campaign_id
ORDER BY cpa ASC
""",
    },
    {
        "question": "이번달 캠페인별 CPC(클릭당 광고비)를 구해줘",
        "sql": """
SELECT
    campaign_id,
    SUM(CAST(is_click AS INT)) AS total_clicks,
    ROUND(SUM(cost_per_click), 2) AS click_spend,
    ROUND(SUM(cost_per_click) / NULLIF(SUM(CAST(is_click AS INT)), 0), 2) AS cpc
FROM ad_combined_log_summary
WHERE year  = date_format(current_date, '%Y')
  AND month = date_format(current_date, '%m')
GROUP BY campaign_id
ORDER BY cpc ASC
""",
    },
    # ── GROUP 4: ad_combined_log 시간대별 분석 ───────────────────────────
    {
        "question": "어제 피크타임이 언제야?",
        "sql": """
SELECT
    hour,
    SUM(CAST(is_click AS INT)) AS clicks
FROM ad_combined_log
WHERE year  = date_format(date_add('day', -1, current_date), '%Y')
  AND month = date_format(date_add('day', -1, current_date), '%m')
  AND day   = date_format(date_add('day', -1, current_date), '%d')
GROUP BY hour
ORDER BY clicks DESC
LIMIT 1
""",
    },
    {
        "question": "어제 시간대별 클릭률(CTR)을 분석해줘",
        "sql": """
SELECT
    hour,
    COUNT(*) AS impressions,
    SUM(CAST(is_click AS INT)) AS clicks,
    ROUND(SUM(CAST(is_click AS INT)) * 100.0 / COUNT(*), 2) AS ctr_percent
FROM ad_combined_log
WHERE year  = date_format(date_add('day', -1, current_date), '%Y')
  AND month = date_format(date_add('day', -1, current_date), '%m')
  AND day   = date_format(date_add('day', -1, current_date), '%d')
GROUP BY hour
ORDER BY hour
""",
    },
    {
        "question": "이번주 시간대별 노출 수 추이를 보여줘",
        "sql": """
SELECT
    day,
    hour,
    COUNT(*) AS impressions
FROM ad_combined_log
WHERE year  = date_format(current_date, '%Y')
  AND month = date_format(current_date, '%m')
  AND day  >= date_format(date_add('day', -6, current_date), '%d')
GROUP BY day, hour
ORDER BY day, hour
""",
    },
    {
        "question": "지난 7일 시간대별 광고비 패턴을 보여줘",
        "sql": """
SELECT
    hour,
    ROUND(SUM(cost_per_impression + cost_per_click), 2) AS total_ad_spend
FROM ad_combined_log
WHERE year  = date_format(current_date, '%Y')
  AND month = date_format(current_date, '%m')
  AND day  >= date_format(date_add('day', -6, current_date), '%d')
GROUP BY hour
ORDER BY total_ad_spend DESC
""",
    },
    # ── GROUP 5: 광고채널(ad_format)별 분석 ─────────────────────────────
    {
        "question": "이번달 광고채널별(ad_format) 클릭률(CTR)을 비교해줘",
        "sql": """
SELECT
    ad_format,
    COUNT(*) AS impressions,
    SUM(CAST(is_click AS INT)) AS clicks,
    ROUND(SUM(CAST(is_click AS INT)) * 100.0 / COUNT(*), 2) AS ctr_percent
FROM ad_combined_log_summary
WHERE year  = date_format(current_date, '%Y')
  AND month = date_format(current_date, '%m')
GROUP BY ad_format
ORDER BY ctr_percent DESC
""",
    },
    {
        "question": "지난달 광고채널별(ad_format) 전환율(CVR)을 분석해줘",
        "sql": """
SELECT
    ad_format,
    SUM(CAST(is_click AS INT)) AS clicks,
    SUM(CAST(is_conversion AS INT)) AS conversions,
    ROUND(SUM(CAST(is_conversion AS INT)) * 100.0 / NULLIF(SUM(CAST(is_click AS INT)), 0), 2) AS cvr_percent
FROM ad_combined_log_summary
WHERE year  = date_format(date_add('month', -1, current_date), '%Y')
  AND month = date_format(date_add('month', -1, current_date), '%m')
GROUP BY ad_format
ORDER BY cvr_percent DESC
""",
    },
    {
        "question": "어제 광고 포맷별(ad_format) 노출 수를 비교해줘",
        "sql": """
SELECT
    ad_format,
    COUNT(*) AS impressions,
    SUM(CAST(is_click AS INT)) AS clicks,
    ROUND(SUM(CAST(is_click AS INT)) * 100.0 / COUNT(*), 2) AS ctr_percent
FROM ad_combined_log_summary
WHERE year  = date_format(date_add('day', -1, current_date), '%Y')
  AND month = date_format(date_add('day', -1, current_date), '%m')
  AND day   = date_format(date_add('day', -1, current_date), '%d')
GROUP BY ad_format
ORDER BY impressions DESC
""",
    },
    # ── GROUP 6: 지역별 분석 ─────────────────────────────────────────────
    {
        "question": "지난달 지역별(delivery_region) 전환율(CVR)을 비교해줘",
        "sql": """
SELECT
    delivery_region,
    SUM(CAST(is_click AS INT)) AS clicks,
    SUM(CAST(is_conversion AS INT)) AS conversions,
    ROUND(SUM(CAST(is_conversion AS INT)) * 100.0 / NULLIF(SUM(CAST(is_click AS INT)), 0), 2) AS cvr_percent
FROM ad_combined_log_summary
WHERE year  = date_format(date_add('month', -1, current_date), '%Y')
  AND month = date_format(date_add('month', -1, current_date), '%m')
GROUP BY delivery_region
ORDER BY cvr_percent DESC
""",
    },
    {
        "question": "이번달 지역별(delivery_region) 전환 수와 전환 매출을 보여줘",
        "sql": """
SELECT
    delivery_region,
    SUM(CAST(is_conversion AS INT)) AS conversions,
    ROUND(SUM(conversion_value), 2) AS total_revenue
FROM ad_combined_log_summary
WHERE year  = date_format(current_date, '%Y')
  AND month = date_format(current_date, '%m')
GROUP BY delivery_region
ORDER BY total_revenue DESC
""",
    },
    # ── GROUP 7: 기간 비교 (CTE) ─────────────────────────────────────────
    {
        "question": "지난주 대비 이번주 노출수 증감률을 구해줘",
        "sql": """
WITH last_week AS (
    SELECT COUNT(*) AS last_week_impressions
    FROM ad_combined_log_summary
    WHERE year  = date_format(current_date, '%Y')
      AND month = date_format(current_date, '%m')
      AND day  BETWEEN date_format(date_add('day', -13, current_date), '%d')
                   AND date_format(date_add('day', -7, current_date), '%d')
),
this_week AS (
    SELECT COUNT(*) AS this_week_impressions
    FROM ad_combined_log_summary
    WHERE year  = date_format(current_date, '%Y')
      AND month = date_format(current_date, '%m')
      AND day  >= date_format(date_add('day', -6, current_date), '%d')
)
SELECT
    lw.last_week_impressions,
    tw.this_week_impressions,
    ROUND((tw.this_week_impressions - lw.last_week_impressions) * 100.0 / NULLIF(lw.last_week_impressions, 0), 2) AS growth_rate_percent
FROM last_week lw, this_week tw
""",
    },
    {
        "question": "이번달 대비 지난달 클릭률(CTR) 변화율은?",
        "sql": """
WITH current_month AS (
    SELECT
        ROUND(SUM(CAST(is_click AS INT)) * 100.0 / COUNT(*), 2) AS ctr_percent
    FROM ad_combined_log_summary
    WHERE year  = date_format(current_date, '%Y')
      AND month = date_format(current_date, '%m')
),
prev_month AS (
    SELECT
        ROUND(SUM(CAST(is_click AS INT)) * 100.0 / COUNT(*), 2) AS ctr_percent
    FROM ad_combined_log_summary
    WHERE year  = date_format(date_add('month', -1, current_date), '%Y')
      AND month = date_format(date_add('month', -1, current_date), '%m')
)
SELECT
    cm.ctr_percent AS this_month_ctr,
    pm.ctr_percent AS last_month_ctr,
    ROUND(cm.ctr_percent - pm.ctr_percent, 2) AS ctr_growth
FROM current_month cm, prev_month pm
""",
    },
    {
        "question": "광고주별 이번달 대비 지난달 광고비 증감을 보여줘",
        "sql": """
WITH this_month AS (
    SELECT
        advertiser_id,
        ROUND(SUM(cost_per_impression + cost_per_click), 2) AS spend
    FROM ad_combined_log_summary
    WHERE year  = date_format(current_date, '%Y')
      AND month = date_format(current_date, '%m')
    GROUP BY advertiser_id
),
last_month AS (
    SELECT
        advertiser_id,
        ROUND(SUM(cost_per_impression + cost_per_click), 2) AS spend
    FROM ad_combined_log_summary
    WHERE year  = date_format(date_add('month', -1, current_date), '%Y')
      AND month = date_format(date_add('month', -1, current_date), '%m')
    GROUP BY advertiser_id
)
SELECT
    tm.advertiser_id,
    COALESCE(lm.spend, 0) AS last_month_spend,
    tm.spend AS this_month_spend,
    ROUND(tm.spend - COALESCE(lm.spend, 0), 2) AS spend_growth
FROM this_month tm
LEFT JOIN last_month lm ON tm.advertiser_id = lm.advertiser_id
ORDER BY spend_growth DESC
""",
    },
    # ── GROUP 8: 3개월+ 추이 ──────────────────────────────────────────────
    {
        "question": "지난 3개월 월별 ROAS 추이를 보여줘",
        "sql": """
SELECT
    year,
    month,
    ROUND(SUM(conversion_value) / NULLIF(SUM(cost_per_impression + cost_per_click), 0) * 100, 2) AS roas_percent
FROM ad_combined_log_summary
WHERE year  = date_format(current_date, '%Y')
  AND month IN (
      date_format(date_add('month', -1, current_date), '%m'),
      date_format(date_add('month', -2, current_date), '%m'),
      date_format(date_add('month', -3, current_date), '%m')
  )
GROUP BY year, month
ORDER BY year, month
""",
    },
    # ── GROUP 9: 주중/주말 패턴 ──────────────────────────────────────────
    {
        "question": "주중과 주말의 클릭률(CTR) 차이를 분석해줘",
        "sql": """
SELECT
    CASE
        WHEN day_of_week(date(from_unixtime(impression_timestamp))) IN (1, 7) THEN '주말'
        ELSE '주중'
    END AS week_type,
    COUNT(*) AS impressions,
    SUM(CAST(is_click AS INT)) AS clicks,
    ROUND(SUM(CAST(is_click AS INT)) * 100.0 / COUNT(*), 2) AS ctr_percent
FROM ad_combined_log_summary
WHERE year  = date_format(current_date, '%Y')
  AND month = date_format(current_date, '%m')
GROUP BY CASE
    WHEN day_of_week(date(from_unixtime(impression_timestamp))) IN (1, 7) THEN '주말'
    ELSE '주중'
END
ORDER BY ctr_percent DESC
""",
    },
    # ── GROUP 10: 이상 탐지 ──────────────────────────────────────────────
    {
        "question": "어제 전환이 0인 캠페인을 찾아줘. 해당 캠페인의 노출과 클릭은?",
        "sql": """
SELECT
    campaign_id,
    COUNT(*) AS impressions,
    SUM(CAST(is_click AS INT)) AS clicks
FROM ad_combined_log_summary
WHERE year  = date_format(date_add('day', -1, current_date), '%Y')
  AND month = date_format(date_add('day', -1, current_date), '%m')
  AND day   = date_format(date_add('day', -1, current_date), '%d')
GROUP BY campaign_id
HAVING COUNT(CASE WHEN is_conversion THEN 1 END) = 0
ORDER BY impressions DESC
""",
    },
    {
        "question": "최근 7일간 클릭이 0인 campaign_id 목록을 보여줘",
        "sql": """
SELECT
    campaign_id,
    COUNT(*) AS impressions
FROM ad_combined_log_summary
WHERE year  = date_format(current_date, '%Y')
  AND month = date_format(current_date, '%m')
  AND day  >= date_format(date_add('day', -6, current_date), '%d')
GROUP BY campaign_id
HAVING SUM(CAST(is_click AS INT)) = 0
ORDER BY campaign_id
""",
    },
    # ── GROUP 11: 광고비·매출 분석 ───────────────────────────────────────
    {
        "question": "지난달 캠페인별 광고비(cost_per_impression+cost_per_click 합계)를 구해줘",
        "sql": """
SELECT
    campaign_id,
    ROUND(SUM(cost_per_impression + cost_per_click), 2) AS total_ad_spend
FROM ad_combined_log_summary
WHERE year  = date_format(date_add('month', -1, current_date), '%Y')
  AND month = date_format(date_add('month', -1, current_date), '%m')
GROUP BY campaign_id
ORDER BY total_ad_spend DESC
""",
    },
    {
        "question": "일별 cost_per_impression 합계가 가장 높은 날짜는?",
        "sql": """
SELECT
    day,
    ROUND(SUM(cost_per_impression), 2) AS total_cpi_spend
FROM ad_combined_log_summary
WHERE year  = date_format(current_date, '%Y')
  AND month = date_format(current_date, '%m')
GROUP BY day
ORDER BY total_cpi_spend DESC
LIMIT 1
""",
    },
    {
        "question": "캠페인별 일별 광고비(cost_per_impression+cost_per_click 합계) 분포를 보여줘",
        "sql": """
SELECT
    campaign_id,
    day,
    ROUND(SUM(cost_per_impression + cost_per_click), 2) AS daily_ad_spend
FROM ad_combined_log_summary
WHERE year  = date_format(current_date, '%Y')
  AND month = date_format(current_date, '%m')
GROUP BY campaign_id, day
ORDER BY campaign_id, day
""",
    },
    {
        "question": "지난달 전환 유형별(conversion_type) 매출을 분석해줘",
        "sql": """
SELECT
    conversion_type,
    SUM(CAST(is_conversion AS INT)) AS conversions,
    ROUND(SUM(conversion_value), 2) AS total_revenue,
    ROUND(AVG(conversion_value), 2) AS avg_order_value
FROM ad_combined_log_summary
WHERE year  = date_format(date_add('month', -1, current_date), '%Y')
  AND month = date_format(date_add('month', -1, current_date), '%m')
GROUP BY conversion_type
ORDER BY total_revenue DESC
""",
    },
    # ── GROUP 12: ROAS 추이·비교 ─────────────────────────────────────────
    # ── BUG TDD: TC-RAG-07 평균 CTR 임계값 CTE 갭 보완 ───────────────────
    {
        "question": "평균보다 CTR이 낮은 캠페인을 찾아줘",
        "sql": """
WITH avg_ctr AS (
    SELECT AVG(ctr_val) AS overall_avg_ctr
    FROM (
        SELECT campaign_id,
               ROUND(SUM(CAST(is_click AS INT)) * 100.0 / COUNT(*), 2) AS ctr_val
        FROM ad_combined_log_summary
        WHERE year  = date_format(current_date, '%Y')
          AND month = date_format(current_date, '%m')
        GROUP BY campaign_id
    ) t
),
campaign_ctr AS (
    SELECT campaign_id,
           ROUND(SUM(CAST(is_click AS INT)) * 100.0 / COUNT(*), 2) AS ctr_percent
    FROM ad_combined_log_summary
    WHERE year  = date_format(current_date, '%Y')
      AND month = date_format(current_date, '%m')
    GROUP BY campaign_id
)
SELECT c.campaign_id, c.ctr_percent, a.overall_avg_ctr,
       ROUND(c.ctr_percent - a.overall_avg_ctr, 2) AS ctr_growth
FROM campaign_ctr c, avg_ctr a
WHERE c.ctr_percent < a.overall_avg_ctr
ORDER BY ctr_percent ASC
""",
    },
    # ── BUG TDD: TC-RAG-08 "클릭 패턴" 구어체 갭 보완 ───────────────────
    {
        "question": "주중과 주말의 클릭 패턴 차이를 분석해줘",
        "sql": """
SELECT
    CASE
        WHEN day_of_week(date(from_unixtime(impression_timestamp))) IN (1, 7) THEN '주말'
        ELSE '주중'
    END AS week_type,
    COUNT(*) AS impressions,
    SUM(CAST(is_click AS INT)) AS clicks,
    ROUND(SUM(CAST(is_click AS INT)) * 100.0 / COUNT(*), 2) AS ctr_percent
FROM ad_combined_log_summary
WHERE year  = date_format(current_date, '%Y')
  AND month = date_format(current_date, '%m')
GROUP BY CASE
    WHEN day_of_week(date(from_unixtime(impression_timestamp))) IN (1, 7) THEN '주말'
    ELSE '주중'
END
ORDER BY week_type
""",
    },
    # ── BUG TDD: TC-RAG-09 "한 건도 없는" 구어체 갭 보완 ────────────────
    {
        "question": "어제 전환이 한 건도 없는 캠페인이 어디야?",
        "sql": """
SELECT
    campaign_id,
    COUNT(*) AS impressions,
    SUM(CAST(is_click AS INT)) AS clicks
FROM ad_combined_log_summary
WHERE year  = date_format(date_add('day', -1, current_date), '%Y')
  AND month = date_format(date_add('day', -1, current_date), '%m')
  AND day   = date_format(date_add('day', -1, current_date), '%d')
GROUP BY campaign_id
HAVING COUNT(CASE WHEN is_conversion THEN 1 END) = 0
ORDER BY impressions DESC
""",
    },
    # ── BUG TDD: TC-RAG-03 "채널별" 구어체 갭 보완 ──────────────────────
    {
        "question": "채널별 전환율이 어떻게 돼?",
        "sql": """
SELECT
    ad_format,
    SUM(CAST(is_click AS INT)) AS clicks,
    SUM(CAST(is_conversion AS INT)) AS conversions,
    ROUND(SUM(CAST(is_conversion AS INT)) * 100.0 / NULLIF(SUM(CAST(is_click AS INT)), 0), 2) AS cvr_percent
FROM ad_combined_log_summary
WHERE year  = date_format(current_date, '%Y')
  AND month = date_format(current_date, '%m')
GROUP BY ad_format
ORDER BY cvr_percent DESC
""",
    },
    # ── BUG TDD: TC-RAG-11 고유사용자수 갭 보완 ─────────────────────────
    {
        "question": "이번달 고유 사용자(unique user) 수를 알려줘",
        "sql": """
SELECT
    COUNT(DISTINCT user_id) AS unique_users,
    COUNT(*) AS total_impressions
FROM ad_combined_log_summary
WHERE year  = date_format(current_date, '%Y')
  AND month = date_format(current_date, '%m')
""",
    },
    # ── BUG TDD: TC-RAG-12 ad_format + hour 복합 갭 보완 ────────────────
    {
        "question": "광고채널별(ad_format) 시간대별 클릭 패턴을 분석해줘",
        "sql": """
SELECT
    ad_format,
    hour,
    COUNT(*) AS impressions,
    SUM(CAST(is_click AS INT)) AS clicks,
    ROUND(SUM(CAST(is_click AS INT)) * 100.0 / COUNT(*), 2) AS ctr_percent
FROM ad_combined_log
WHERE year  = date_format(date_add('day', -1, current_date), '%Y')
  AND month = date_format(date_add('day', -1, current_date), '%m')
  AND day   = date_format(date_add('day', -1, current_date), '%d')
GROUP BY ad_format, hour
ORDER BY ad_format, hour
""",
    },
    # ── Jinja2 날짜 패턴 QA (평가용 ground_truth와 동일 포맷) ─────────────
    # 설계서 §3.1.2: 파티션 조건에 {{ y_year }}/{{ y_month }}/{{ y_day }} 사용
    # run_evaluation.py의 _render_ground_truth()가 실행 시점 날짜로 치환
    {
        "question": "어제 캠페인별 클릭률(CTR)을 내림차순으로 보여줘",
        "sql": """SELECT campaign_id,
    COUNT(CASE WHEN is_click = true THEN 1 END) * 1.0 / NULLIF(COUNT(*), 0) AS ctr
FROM ad_combined_log_summary
WHERE year='{{ y_year }}' AND month='{{ y_month }}' AND day='{{ y_day }}'
GROUP BY campaign_id
ORDER BY ctr DESC""",
    },
    {
        "question": "각 캠페인의 어제 CTR은?",
        "sql": """SELECT campaign_id,
    COUNT(CASE WHEN is_click = true THEN 1 END) * 1.0 / NULLIF(COUNT(*), 0) AS ctr
FROM ad_combined_log_summary
WHERE year='{{ y_year }}' AND month='{{ y_month }}' AND day='{{ y_day }}'
GROUP BY campaign_id
ORDER BY ctr DESC""",
    },
    {
        "question": "어제 캠페인별로 노출 대비 클릭 비율을 비교해줘",
        "sql": """SELECT campaign_id,
    COUNT(CASE WHEN is_click = true THEN 1 END) * 1.0 / NULLIF(COUNT(*), 0) AS ctr
FROM ad_combined_log_summary
WHERE year='{{ y_year }}' AND month='{{ y_month }}' AND day='{{ y_day }}'
GROUP BY campaign_id
ORDER BY ctr DESC""",
    },
    {
        "question": "어제 기기별 노출수와 클릭수를 보여줘",
        "sql": """SELECT device_type,
    COUNT(*) AS impressions,
    COUNT(CASE WHEN is_click = true THEN 1 END) AS clicks
FROM ad_combined_log_summary
WHERE year='{{ y_year }}' AND month='{{ y_month }}' AND day='{{ y_day }}'
GROUP BY device_type
ORDER BY impressions DESC""",
    },
    {
        "question": "어제 전환율(CVR)이 가장 높은 캠페인 TOP 3는?",
        "sql": """SELECT campaign_id,
    COUNT(CASE WHEN is_conversion = true THEN 1 END) * 1.0 / NULLIF(COUNT(CASE WHEN is_click = true THEN 1 END), 0) AS cvr
FROM ad_combined_log_summary
WHERE year='{{ y_year }}' AND month='{{ y_month }}' AND day='{{ y_day }}'
GROUP BY campaign_id
ORDER BY cvr DESC
LIMIT 3""",
    },
    {
        "question": "이번달 캠페인별 총 광고비를 구해줘",
        "sql": """SELECT campaign_id,
    SUM(cost_per_impression + cost_per_click) AS total_ad_spend
FROM ad_combined_log_summary
WHERE year='{{ year }}' AND month='{{ month }}'
GROUP BY campaign_id
ORDER BY total_ad_spend DESC""",
    },
    {
        "question": "이번달 ROAS가 가장 높은 캠페인은?",
        "sql": """SELECT campaign_id,
    SUM(conversion_value) / NULLIF(SUM(cost_per_click), 0) AS roas
FROM ad_combined_log_summary
WHERE year='{{ year }}' AND month='{{ month }}'
GROUP BY campaign_id
ORDER BY roas DESC
LIMIT 1""",
    },
    {
        "question": "이번달 대비 2개월 전 ROAS 변화를 알려줘",
        "sql": """
WITH two_months_ago AS (
    SELECT
        ROUND(SUM(conversion_value) / NULLIF(SUM(cost_per_impression + cost_per_click), 0) * 100, 2) AS roas_percent
    FROM ad_combined_log_summary
    WHERE year  = date_format(date_add('month', -2, current_date), '%Y')
      AND month = date_format(date_add('month', -2, current_date), '%m')
),
current_month AS (
    SELECT
        ROUND(SUM(conversion_value) / NULLIF(SUM(cost_per_impression + cost_per_click), 0) * 100, 2) AS roas_percent
    FROM ad_combined_log_summary
    WHERE year  = date_format(current_date, '%Y')
      AND month = date_format(current_date, '%m')
)
SELECT
    tma.roas_percent AS two_months_ago_roas,
    cm.roas_percent AS current_roas,
    ROUND(cm.roas_percent - tma.roas_percent, 2) AS roas_growth
FROM two_months_ago tma, current_month cm
""",
    },
    # ── GAP-B-01/02: 패러프레이징 QA 확장 (설계서 §3.1.2 우선순위 1~4) ─────
    # ── 카테고리 2 추가: CTR 계산 패러프레이징 (동일 SQL 다른 표현) ─────────
    # 이미 존재하는 3개(Jinja2 섹션)에 date_format 동적 패턴 표현 추가
    {
        "question": "어제 캠페인별 광고 클릭률을 높은 순으로 정렬해줘",
        "sql": """SELECT campaign_id,
    COUNT(CASE WHEN is_click = true THEN 1 END) * 1.0 / NULLIF(COUNT(*), 0) AS ctr
FROM ad_combined_log_summary
WHERE year='{{ y_year }}' AND month='{{ y_month }}' AND day='{{ y_day }}'
GROUP BY campaign_id
ORDER BY ctr DESC""",
    },
    {
        "question": "어제 캠페인 중 CTR이 제일 높은 건 어디야?",
        "sql": """SELECT campaign_id,
    COUNT(CASE WHEN is_click = true THEN 1 END) * 1.0 / NULLIF(COUNT(*), 0) AS ctr
FROM ad_combined_log_summary
WHERE year='{{ y_year }}' AND month='{{ y_month }}' AND day='{{ y_day }}'
GROUP BY campaign_id
ORDER BY ctr DESC
LIMIT 1""",
    },
    # ── 카테고리 6: TOP N 순위 패턴 패러프레이징 ───────────────────────────
    {
        "question": "이번달 클릭수 상위 5개 캠페인을 알려줘",
        "sql": """SELECT campaign_id,
    COUNT(CASE WHEN is_click = true THEN 1 END) AS total_clicks
FROM ad_combined_log_summary
WHERE year='{{ year }}' AND month='{{ month }}'
GROUP BY campaign_id
ORDER BY total_clicks DESC
LIMIT 5""",
    },
    {
        "question": "이번달 광고비 가장 많이 쓴 캠페인 TOP 3는?",
        "sql": """SELECT campaign_id,
    SUM(cost_per_impression + cost_per_click) AS total_ad_spend
FROM ad_combined_log_summary
WHERE year='{{ year }}' AND month='{{ month }}'
GROUP BY campaign_id
ORDER BY total_ad_spend DESC
LIMIT 3""",
    },
    {
        "question": "지난달 전환 수 기준 상위 3개 광고주를 보여줘",
        "sql": """SELECT advertiser_id,
    COUNT(CASE WHEN is_conversion = true THEN 1 END) AS total_conversions
FROM ad_combined_log_summary
WHERE year = date_format(date_add('month', -1, current_date), '%Y')
  AND month = date_format(date_add('month', -1, current_date), '%m')
GROUP BY advertiser_id
ORDER BY total_conversions DESC
LIMIT 3""",
    },
    # ── 카테고리 4: 기간 비교(CTE) 패턴 패러프레이징 ──────────────────────
    {
        "question": "어제 대비 오늘 노출수는 얼마나 늘었어?",
        "sql": """WITH yesterday AS (
    SELECT COUNT(*) AS impressions
    FROM ad_combined_log_summary
    WHERE year='{{ y_year }}' AND month='{{ y_month }}' AND day='{{ y_day }}'
),
today AS (
    SELECT COUNT(*) AS impressions
    FROM ad_combined_log_summary
    WHERE year='{{ year }}' AND month='{{ month }}' AND day='{{ day }}'
)
SELECT
    y.impressions AS yesterday_impressions,
    t.impressions AS today_impressions,
    ROUND((t.impressions - y.impressions) * 100.0 / NULLIF(y.impressions, 0), 2) AS growth_rate_percent
FROM yesterday y, today t""",
    },
    {
        "question": "전일 대비 클릭률 변화량을 알려줘",
        "sql": """WITH yesterday AS (
    SELECT ROUND(COUNT(CASE WHEN is_click = true THEN 1 END) * 100.0 / COUNT(*), 2) AS ctr_percent
    FROM ad_combined_log_summary
    WHERE year='{{ y_year }}' AND month='{{ y_month }}' AND day='{{ y_day }}'
),
today AS (
    SELECT ROUND(COUNT(CASE WHEN is_click = true THEN 1 END) * 100.0 / COUNT(*), 2) AS ctr_percent
    FROM ad_combined_log_summary
    WHERE year='{{ year }}' AND month='{{ month }}' AND day='{{ day }}'
)
SELECT
    y.ctr_percent AS yesterday_ctr,
    t.ctr_percent AS today_ctr,
    ROUND(t.ctr_percent - y.ctr_percent, 2) AS ctr_change
FROM yesterday y, today t""",
    },
    {
        "question": "이번달과 지난달 전환율(CVR) 비교해줘",
        "sql": """WITH this_month AS (
    SELECT ROUND(COUNT(CASE WHEN is_conversion = true THEN 1 END) * 100.0
                 / NULLIF(COUNT(CASE WHEN is_click = true THEN 1 END), 0), 2) AS cvr_percent
    FROM ad_combined_log_summary
    WHERE year='{{ year }}' AND month='{{ month }}'
),
last_month AS (
    SELECT ROUND(COUNT(CASE WHEN is_conversion = true THEN 1 END) * 100.0
                 / NULLIF(COUNT(CASE WHEN is_click = true THEN 1 END), 0), 2) AS cvr_percent
    FROM ad_combined_log_summary
    WHERE year = date_format(date_add('month', -1, current_date), '%Y')
      AND month = date_format(date_add('month', -1, current_date), '%m')
)
SELECT
    lm.cvr_percent AS last_month_cvr,
    tm.cvr_percent AS this_month_cvr,
    ROUND(tm.cvr_percent - lm.cvr_percent, 2) AS cvr_change
FROM this_month tm, last_month lm""",
    },
    # ── 카테고리 9: 지역별/기기별 GROUP BY 패러프레이징 ───────────────────
    {
        "question": "지역별로 어제 노출수와 클릭수를 비교해줘",
        "sql": """SELECT delivery_region,
    COUNT(*) AS impressions,
    COUNT(CASE WHEN is_click = true THEN 1 END) AS clicks,
    ROUND(COUNT(CASE WHEN is_click = true THEN 1 END) * 100.0 / COUNT(*), 2) AS ctr_percent
FROM ad_combined_log_summary
WHERE year='{{ y_year }}' AND month='{{ y_month }}' AND day='{{ y_day }}'
GROUP BY delivery_region
ORDER BY impressions DESC""",
    },
    {
        "question": "어제 어떤 지역에서 광고 성과가 제일 좋았어?",
        "sql": """SELECT delivery_region,
    COUNT(*) AS impressions,
    COUNT(CASE WHEN is_click = true THEN 1 END) AS clicks,
    ROUND(COUNT(CASE WHEN is_click = true THEN 1 END) * 100.0 / COUNT(*), 2) AS ctr_percent
FROM ad_combined_log_summary
WHERE year='{{ y_year }}' AND month='{{ y_month }}' AND day='{{ y_day }}'
GROUP BY delivery_region
ORDER BY ctr_percent DESC
LIMIT 5""",
    },
    {
        "question": "기기 유형별 이번달 전환율을 보여줘",
        "sql": """SELECT device_type,
    COUNT(CASE WHEN is_click = true THEN 1 END) AS clicks,
    COUNT(CASE WHEN is_conversion = true THEN 1 END) AS conversions,
    ROUND(COUNT(CASE WHEN is_conversion = true THEN 1 END) * 100.0
          / NULLIF(COUNT(CASE WHEN is_click = true THEN 1 END), 0), 2) AS cvr_percent
FROM ad_combined_log_summary
WHERE year='{{ year }}' AND month='{{ month }}'
GROUP BY device_type
ORDER BY cvr_percent DESC""",
    },
    {
        "question": "모바일과 데스크톱 중 어느 쪽 CTR이 더 높아?",
        "sql": """SELECT device_type,
    COUNT(*) AS impressions,
    COUNT(CASE WHEN is_click = true THEN 1 END) AS clicks,
    ROUND(COUNT(CASE WHEN is_click = true THEN 1 END) * 100.0 / COUNT(*), 2) AS ctr_percent
FROM ad_combined_log_summary
WHERE year='{{ year }}' AND month='{{ month }}'
  AND device_type IN ('mobile', 'desktop')
GROUP BY device_type
ORDER BY ctr_percent DESC""",
    },
    # ── 정확한 계산식 패턴 — 비율(0~1) 단위, 올바른 분모 ────────────────────
    {
        "question": "어제 캠페인별 전환율(CVR) 상위 5개를 보여줘",
        "sql": """SELECT campaign_id,
    COUNT(CASE WHEN is_conversion = true THEN 1 END) * 1.0
    / NULLIF(COUNT(CASE WHEN is_click = true THEN 1 END), 0) AS cvr
FROM ad_combined_log_summary
WHERE year='{{ y_year }}' AND month='{{ y_month }}' AND day='{{ y_day }}'
GROUP BY campaign_id
ORDER BY cvr DESC
LIMIT 5""",
    },
    {
        "question": "2026년 3월 14일 ROAS가 가장 높은 광고주 TOP 5와 매출 금액",
        "sql": """SELECT advertiser_id,
    SUM(CASE WHEN is_conversion = true THEN conversion_value ELSE 0 END)
    / NULLIF(SUM(cost_per_impression + cost_per_click), 0) AS roas,
    SUM(CASE WHEN is_conversion = true THEN conversion_value ELSE 0 END) AS revenue
FROM ad_combined_log_summary
WHERE year='2026' AND month='03' AND day='14'
GROUP BY advertiser_id
ORDER BY roas DESC
LIMIT 5""",
    },
    {
        "question": "어제 전환당 비용(CPA)이 가장 낮은 캠페인 TOP 5",
        "sql": """SELECT campaign_id,
    SUM(cost_per_impression + cost_per_click)
    / NULLIF(COUNT(CASE WHEN is_conversion = true THEN 1 END), 0) AS cpa
FROM ad_combined_log_summary
WHERE year='{{ y_year }}' AND month='{{ y_month }}' AND day='{{ y_day }}'
GROUP BY campaign_id
HAVING COUNT(CASE WHEN is_conversion = true THEN 1 END) > 0
ORDER BY cpa ASC
LIMIT 5""",
    },
    {
        "question": "2026년 3월 14일 오전과 오후의 클릭 수 비교",
        "sql": """SELECT
    CASE WHEN CAST(hour AS INT) < 12 THEN '오전' ELSE '오후' END AS time_period,
    COUNT(CASE WHEN is_click = true THEN 1 END) AS clicks
FROM ad_combined_log
WHERE year='2026' AND month='03' AND day='14'
GROUP BY CASE WHEN CAST(hour AS INT) < 12 THEN '오전' ELSE '오후' END
ORDER BY time_period""",
    },
    {
        "question": "2026년 3월 8일부터 14일까지 7일간 일별 impression 수 추이",
        "sql": """SELECT day, COUNT(*) AS impressions
FROM ad_combined_log_summary
WHERE year='2026' AND month='03'
  AND day IN ('08','09','10','11','12','13','14')
GROUP BY day
ORDER BY day""",
    },
    {
        "question": "2026년 3월 14일 클릭은 있지만 전환이 없는 캠페인 목록",
        "sql": """SELECT campaign_id,
    COUNT(CASE WHEN is_click = true THEN 1 END) AS clicks
FROM ad_combined_log_summary
WHERE year='2026' AND month='03' AND day='14'
GROUP BY campaign_id
HAVING COUNT(CASE WHEN is_click = true THEN 1 END) > 0
  AND COUNT(CASE WHEN is_conversion = true THEN 1 END) = 0
ORDER BY clicks DESC""",
    },
    {
        "question": "어제 전체 광고 노출수, 클릭수, 전환수, 클릭률(CTR)을 보여줘",
        "sql": """SELECT
    COUNT(*) AS impressions,
    COUNT(CASE WHEN is_click = true THEN 1 END) AS clicks,
    COUNT(CASE WHEN is_conversion = true THEN 1 END) AS conversions,
    COUNT(CASE WHEN is_click = true THEN 1 END) * 1.0 / NULLIF(COUNT(*), 0) AS ctr
FROM ad_combined_log_summary
WHERE year='{{ y_year }}' AND month='{{ y_month }}' AND day='{{ y_day }}'""",
    },
    {
        "question": "2026년 3월 광고 위치별 전환율(CVR)",
        "sql": """SELECT ad_position,
    COUNT(CASE WHEN is_conversion = true THEN 1 END) * 1.0
    / NULLIF(COUNT(CASE WHEN is_click = true THEN 1 END), 0) AS cvr
FROM ad_combined_log_summary
WHERE year='2026' AND month='03'
GROUP BY ad_position
ORDER BY cvr DESC""",
    },
    {
        "question": "어제 강남구 지역 클릭 수는?",
        "sql": """SELECT COUNT(CASE WHEN is_click = true THEN 1 END) AS clicks
FROM ad_combined_log_summary
WHERE year='{{ y_year }}' AND month='{{ y_month }}' AND day='{{ y_day }}'
  AND delivery_region='강남구'""",
    },
    {
        "question": "2026년 3월 플랫폼별 일별 impression 추이",
        "sql": """SELECT day, platform, COUNT(*) AS impressions
FROM ad_combined_log_summary
WHERE year='2026' AND month='03'
GROUP BY day, platform
ORDER BY day, impressions DESC""",
    },
    # ── GROUP BY 과잉 방지 패턴 — WHERE에 고정된 파티션은 GROUP BY 생략 ────
    {
        "question": "2026년 3월 8일부터 14일까지 7일간 캠페인별 일별 평균 CTR",
        "sql": """SELECT campaign_id, AVG(daily_ctr_percent) AS avg_ctr_percent
FROM (
    SELECT day, campaign_id,
        ROUND(SUM(CAST(is_click AS INT)) * 100.0 / NULLIF(COUNT(*), 0), 2) AS daily_ctr_percent
    FROM ad_combined_log_summary
    WHERE year='2026' AND month='03'
      AND day IN ('08','09','10','11','12','13','14')
    GROUP BY day, campaign_id
) sub
GROUP BY campaign_id
ORDER BY avg_ctr_percent DESC""",
        "tables": ["ad_combined_log_summary"],
    },
    # ── CASE 레이블 단순 패턴 — 괄호·범위 설명 없이 ────────────────────────
    {
        "question": "2026년 3월 14일 오전과 오후의 클릭 수를 비교해줘",
        "sql": """SELECT
    CASE WHEN CAST(hour AS INT) < 12 THEN '오전' ELSE '오후' END AS time_period,
    COUNT(CASE WHEN is_click = true THEN 1 END) AS clicks
FROM ad_combined_log
WHERE year='2026' AND month='03' AND day='14'
GROUP BY CASE WHEN CAST(hour AS INT) < 12 THEN '오전' ELSE '오후' END
ORDER BY time_period""",
    },
    # ── HAVING 패턴 — 클릭/전환 조건을 HAVING으로 처리 ─────────────────────
    {
        "question": "어제 CTR은 높은데 전환이 없는 캠페인을 찾아줘",
        "sql": """SELECT campaign_id,
    ROUND(SUM(CAST(is_click AS INT)) * 100.0 / NULLIF(COUNT(*), 0), 2) AS ctr_percent
FROM ad_combined_log_summary
WHERE year='{{ y_year }}' AND month='{{ y_month }}' AND day='{{ y_day }}'
GROUP BY campaign_id
HAVING ROUND(SUM(CAST(is_click AS INT)) * 100.0 / NULLIF(COUNT(*), 0), 2) > 5.0
  AND COUNT(CASE WHEN is_conversion = true THEN 1 END) = 0
ORDER BY ctr_percent DESC""",
        "tables": ["ad_combined_log_summary"],
    },
    # ── WHERE is_conversion=true 직접 필터 패턴 ────────────────────────────
    {
        "question": "2026년 3월 14일 전환 타입별 총 매출과 평균 전환 가치",
        "sql": """SELECT conversion_type,
    COUNT(*) AS conversions,
    SUM(conversion_value) AS total_revenue,
    AVG(conversion_value) AS avg_value
FROM ad_combined_log_summary
WHERE year='2026' AND month='03' AND day='14'
  AND is_conversion = true
GROUP BY conversion_type
ORDER BY total_revenue DESC""",
    },
    {
        "question": "2026년 3월 8일부터 14일까지 7일간 광고주별 총 전환 매출",
        "sql": """SELECT advertiser_id, SUM(conversion_value) AS total_revenue
FROM ad_combined_log_summary
WHERE year='2026' AND month='03'
  AND day IN ('08','09','10','11','12','13','14')
  AND is_conversion = true
GROUP BY advertiser_id
ORDER BY total_revenue DESC""",
        "tables": ["ad_combined_log_summary"],
    },
    # ── 멀티메트릭 CTR percent 요약 패턴 (T021/T046 보완) ──────────────────
    {
        "question": "어제 전체 광고 노출수, 클릭수, 전환수, 클릭률(CTR)을 보여줘",
        "sql": """SELECT
    COUNT(*) AS impressions,
    SUM(CAST(is_click AS INT)) AS clicks,
    SUM(CAST(is_conversion AS INT)) AS conversions,
    ROUND(SUM(CAST(is_click AS INT)) * 100.0 / NULLIF(COUNT(*), 0), 2) AS ctr_percent
FROM ad_combined_log_summary
WHERE year = date_format(date_add('day', -1, current_date), '%Y')
  AND month = date_format(date_add('day', -1, current_date), '%m')
  AND day   = date_format(date_add('day', -1, current_date), '%d')""",
        "tables": ["ad_combined_log_summary"],
    },
    {
        "question": "2026년 3월 전체 광고 노출수, 클릭수, 전환수, CTR 요약",
        "sql": """SELECT
    COUNT(*) AS impressions,
    SUM(CAST(is_click AS INT)) AS clicks,
    SUM(CAST(is_conversion AS INT)) AS conversions,
    ROUND(SUM(CAST(is_click AS INT)) * 100.0 / NULLIF(COUNT(*), 0), 2) AS ctr_percent
FROM ad_combined_log_summary
WHERE year='2026' AND month='03'""",
        "tables": ["ad_combined_log_summary"],
    },
    # ── ORDER BY conversions 패턴 (T050 보완) ───────────────────────────────
    {
        "question": "2026년 3월 음식 카테고리별 노출수와 전환수 상위 10개",
        "sql": """SELECT
    food_category,
    COUNT(*) AS impressions,
    COUNT(CASE WHEN is_conversion = true THEN 1 END) AS conversions
FROM ad_combined_log_summary
WHERE year='2026' AND month='03'
GROUP BY food_category
ORDER BY conversions DESC
LIMIT 10""",
        "tables": ["ad_combined_log_summary"],
    },
    # ── WHERE is_conversion=true 직접 필터 (T009/T040 보완) ─────────────────
    {
        "question": "어제 총 전환 매출은 얼마야?",
        "sql": """SELECT SUM(conversion_value) AS total_revenue
FROM ad_combined_log_summary
WHERE year = date_format(date_add('day', -1, current_date), '%Y')
  AND month = date_format(date_add('day', -1, current_date), '%m')
  AND day   = date_format(date_add('day', -1, current_date), '%d')
  AND is_conversion = true""",
        "tables": ["ad_combined_log_summary"],
    },
    # ── GROUP BY year, month 패턴 (T064 보완) ───────────────────────────────
    {
        "question": "2026년 2월과 3월의 월별 전체 노출수, 클릭수, 전환수를 비교해줘",
        "sql": """SELECT
    year,
    month,
    COUNT(*) AS impressions,
    COUNT(CASE WHEN is_click = true THEN 1 END) AS clicks,
    COUNT(CASE WHEN is_conversion = true THEN 1 END) AS conversions
FROM ad_combined_log_summary
WHERE (year='2026' AND month='02') OR (year='2026' AND month='03')
GROUP BY year, month
ORDER BY year, month""",
        "tables": ["ad_combined_log_summary"],
    },
]


def reset_collections() -> None:
    """기존 ChromaDB 컬렉션 삭제 — cosine 메트릭으로 재생성 준비.

    sql-collection, documentation-collection: 삭제 후 VannaAthena init 시 cosine으로 재생성.
    ddl-collection: Phase 2 이후 미사용 — 삭제만 수행.
    Design §2.1 FR-PRO-01 기준.
    """
    import chromadb as _chromadb

    chroma_host = os.getenv("CHROMA_HOST", "chromadb.chromadb.svc.cluster.local")
    chroma_port = int(os.getenv("CHROMA_PORT", "8000"))
    client = _chromadb.HttpClient(host=chroma_host, port=chroma_port)

    for name in ["sql-collection", "documentation-collection"]:
        try:
            client.delete_collection(name)
            logger.info(f"컬렉션 삭제 완료: {name}")
        except Exception:
            logger.info(f"컬렉션 미존재 (무시): {name}")

    # ddl-collection: Phase 2 이후 미사용 — 정리 목적으로만 삭제
    try:
        client.delete_collection("ddl-collection")
        logger.info("ddl-collection 삭제 완료 (Phase 2 이후 미사용)")
    except Exception:
        pass


def initialize_vanna():
    """Vanna + ChromaDB 인스턴스 초기화 (QueryPipeline을 통한 접근)."""
    logger.info("Vanna + ChromaDB 인스턴스 초기화 중...")

    try:
        pipeline = QueryPipeline(
            vanna_instance=None,
            anthropic_api_key=os.getenv("ANTHROPIC_API_KEY", ""),
            athena_client=None,
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


# train_ddl 제거 — DDL은 rag_retriever.py의 _TABLE_DDL dict에서 직접 주입 (Design §3.2)
# def train_ddl(vanna_instance) -> None: ...


def train_documentation(vanna_instance) -> None:
    """Documentation 학습 — 항목별 개별 임베딩으로 검색 정밀도 향상."""
    logger.info("Documentation 학습 시작...")

    all_docs = [
        ("DOCS_BUSINESS_METRICS", DOCS_BUSINESS_METRICS),
        ("DOCS_ATHENA_RULES", DOCS_ATHENA_RULES),
        ("DOCS_POLICIES", DOCS_POLICIES),
        ("DOCS_NONEXISTENT_COLUMNS", DOCS_NONEXISTENT_COLUMNS),
        ("DOCS_CATEGORICAL_VALUES", DOCS_CATEGORICAL_VALUES),
        ("DOCS_GLOSSARY", DOCS_GLOSSARY),
        # DOCS_SCHEMA_MAPPER 제거 — SchemaMapper 삭제로 불필요 (Design §4.2)
        ("DOCS_NEGATIVE_EXAMPLES", DOCS_NEGATIVE_EXAMPLES),  # 신규 (Design §4.3)
    ]

    total = sum(len(docs) for _, docs in all_docs)
    count = 0

    try:
        for category, docs_list in all_docs:
            for doc in docs_list:
                count += 1
                vanna_instance.train(documentation=doc)
                logger.info(f"✓ [{category}] 문서 {count}/{total} 학습 완료")
    except Exception as e:
        logger.error(f"Documentation 학습 실패: {e}")
        raise


def _detect_tables_from_sql(sql: str) -> list[str]:
    """SQL에서 참조하는 테이블 이름 자동 감지.

    ad_combined_log_summary와 ad_combined_log(not summary)를 구분하여 반환.
    Design §3.6 테이블 분류 기준.
    """
    import re as _re
    tables: list[str] = []
    if "ad_combined_log_summary" in sql:
        tables.append("ad_combined_log_summary")
    if _re.search(r"ad_combined_log(?!_summary)", sql):
        tables.append("ad_combined_log")
    return tables if tables else ["ad_combined_log_summary"]


def train_qa_examples(vanna_instance) -> None:
    """QA 예제 학습 — tables metadata 포함하여 DDL 역추적 지원.

    Design §3.2 기준: add_question_sql(tables=...) 호출로
    ChromaDB metadata에 참조 테이블 저장 → retrieve_v2()에서 DDL 역추적에 활용.
    qa dict에 "tables" 명시 시 우선 사용, 없으면 SQL에서 자동 감지.
    """
    logger.info(f"QA 예제 학습 시작 ({len(QA_EXAMPLES)}개)...")

    try:
        for idx, qa in enumerate(QA_EXAMPLES, 1):
            tables = qa.get("tables") or _detect_tables_from_sql(qa["sql"])
            vanna_instance.add_question_sql(
                question=qa["question"],
                sql=qa["sql"],
                tables=tables,
            )
            logger.info(f"✓ QA 예제 {idx}/{len(QA_EXAMPLES)} 학습 완료 (tables={tables})")
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
        reset_collections()          # Step 1: 기존 컬렉션 삭제 (cosine 재생성 준비)
        vanna = initialize_vanna()   # Step 2: VannaAthena init → _ensure_cosine_collections()
        # train_ddl 제거 — DDL은 _TABLE_DDL dict 직접 주입 (Design §3.2)
        train_documentation(vanna)
        train_qa_examples(vanna)
        verify_training(vanna)

        logger.info("=" * 80)
        logger.info("✓ ChromaDB 시딩 완료!")
        logger.info("=" * 80)
        logger.info("학습된 컨텐츠:")
        logger.info("  - DDL: 2개 테이블 (ad_combined_log, ad_combined_log_summary)")
        logger.info(
            f"  - Documentation: {sum(len(d) for d in [DOCS_BUSINESS_METRICS, DOCS_ATHENA_RULES, DOCS_POLICIES, DOCS_NONEXISTENT_COLUMNS, DOCS_CATEGORICAL_VALUES, DOCS_GLOSSARY, DOCS_NEGATIVE_EXAMPLES])}개 항목 (7개 카테고리)"
        )
        logger.info(
            f"  - QA 예제: {len(QA_EXAMPLES)}개 (CTR/CVR/TOP-N/기간비교/지역기기 패러프레이징 포함)"
        )

    except Exception as e:
        logger.error("=" * 80)
        logger.error(f"시딩 실패: {e}")
        logger.error("=" * 80)
        raise


if __name__ == "__main__":
    main()

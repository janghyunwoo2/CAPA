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
    """CTR (Click-Through Rate) — 클릭률, 퍼센트(%) 단위
정의: (클릭 수) / (노출 수) * 100
의미: 사용자가 광고를 본 후 클릭할 확률 (%)
Athena 계산식: ROUND(SUM(CAST(is_click AS INT)) * 100.0 / COUNT(*), 2) AS ctr_percent
예시값: 2.35 (2.35%)""",

    """CVR (Conversion Rate) — 전환율, 퍼센트(%) 단위
정의: (전환 수) / (클릭 수) * 100
의미: 클릭한 사용자 중 실제 전환까지 이르는 확률 (%)
Athena 계산식: ROUND(SUM(CAST(is_conversion AS INT)) * 100.0 / NULLIF(SUM(CAST(is_click AS INT)), 0), 2) AS cvr_percent
주의: ad_combined_log_summary 테이블 필수 (conversion 데이터가 여기에만 있음)
NULLIF(분모, 0) 으로 클릭이 0인 경우 NULL 처리 필수""",

    """ROAS (Return On Ad Spend) — 광고 수익률, 퍼센트(%) 단위
정의: (전환 매출액) / (광고비 총액) * 100
의미: 광고비 100원당 얼마의 매출을 얻었는가 (%)
광고비 = cost_per_impression + cost_per_click
Athena 계산식: ROUND(SUM(conversion_value) / NULLIF(SUM(cost_per_impression + cost_per_click), 0) * 100, 2) AS roas_percent
예시값: 250.0 (광고비 대비 250% 매출, 즉 2.5배 ROAS)
주의: ad_combined_log_summary 테이블 필수 (conversion_value가 여기에만 있음)""",

    """CPA (Cost Per Acquisition) — 전환당 광고비
정의: (광고비 총액) / (전환 수)
의미: 하나의 전환을 얻기 위한 평균 광고비
Athena 계산식: ROUND(SUM(cost_per_impression + cost_per_click) / NULLIF(SUM(CAST(is_conversion AS INT)), 0), 2) AS cpa
주의: 전환이 0인 경우 NULLIF로 NULL 처리 필수""",

    """CPC (Cost Per Click) — 클릭당 광고비
정의: (광고비 총액) / (클릭 수)
의미: 하나의 클릭을 얻기 위한 평균 광고비
Athena 계산식: ROUND(SUM(cost_per_click) / NULLIF(SUM(CAST(is_click AS INT)), 0), 2) AS cpc
주의: 클릭이 0인 경우 NULLIF로 NULL 처리 필수""",

    """비즈니스 지표 공통 규칙:
- CTR, CVR, ROAS, CPA, CPC 모두 NULLIF(분모, 0) 필수 — Division by Zero 방지
- CVR, ROAS, CPA는 반드시 ad_combined_log_summary 테이블 사용 (conversion 데이터 필요)
- CTR, CPC는 ad_combined_log 또는 ad_combined_log_summary 모두 사용 가능
- 시간대별(hour) 분석은 ad_combined_log 테이블 사용 (hour 파티션 존재)""",
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
서울, 경기, 인천, 부산, 대구, 대전, 광주, 울산, 세종, 강원, 충북, 충남, 전북, 전남, 경북, 경남, 제주
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


# ========================= QA 예제 (28개) =========================

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
"""
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
"""
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
"""
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
"""
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
"""
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
"""
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
"""
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
"""
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
"""
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
"""
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
"""
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
"""
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
"""
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
"""
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
"""
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
"""
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
"""
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
"""
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
"""
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
"""
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
"""
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
"""
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
"""
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
"""
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
"""
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
"""
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
"""
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
"""
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
"""
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
"""
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
"""
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
"""
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
"""
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
"""
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
"""
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
"""
    },
]


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


def train_ddl(vanna_instance) -> None:
    """DDL 학습."""
    logger.info("DDL 학습 시작...")

    try:
        vanna_instance.train(
            ddl=DDL_AD_COMBINED_LOG,
            documentation="테이블: ad_combined_log - 광고 노출 및 클릭 이벤트 (시간 단위, hour 파티션)"
        )
        logger.info("✓ ad_combined_log DDL 학습 완료")

        vanna_instance.train(
            ddl=DDL_AD_COMBINED_LOG_SUMMARY,
            documentation="테이블: ad_combined_log_summary - 광고 성과 일일 요약 (전환 데이터 포함)"
        )
        logger.info("✓ ad_combined_log_summary DDL 학습 완료")

    except Exception as e:
        logger.error(f"DDL 학습 실패: {e}")
        raise


def train_documentation(vanna_instance) -> None:
    """Documentation 학습 — 항목별 개별 임베딩으로 검색 정밀도 향상."""
    logger.info("Documentation 학습 시작...")

    all_docs = [
        ("DOCS_BUSINESS_METRICS", DOCS_BUSINESS_METRICS),
        ("DOCS_ATHENA_RULES", DOCS_ATHENA_RULES),
        ("DOCS_POLICIES", DOCS_POLICIES),
        ("DOCS_GLOSSARY", DOCS_GLOSSARY),
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
        vanna = initialize_vanna()
        train_ddl(vanna)
        train_documentation(vanna)
        train_qa_examples(vanna)
        verify_training(vanna)

        logger.info("=" * 80)
        logger.info("✓ ChromaDB 시딩 완료!")
        logger.info("=" * 80)
        logger.info("학습된 컨텐츠:")
        logger.info("  - DDL: 2개 테이블 (ad_combined_log, ad_combined_log_summary)")
        logger.info(f"  - Documentation: {sum(len(d) for d in [DOCS_BUSINESS_METRICS, DOCS_ATHENA_RULES, DOCS_POLICIES, DOCS_GLOSSARY])}개 항목 (4개 카테고리)")
        logger.info(f"  - QA 예제: {len(QA_EXAMPLES)}개 (12개 카테고리 커버)")

    except Exception as e:
        logger.error("=" * 80)
        logger.error(f"시딩 실패: {e}")
        logger.error("=" * 80)
        raise


if __name__ == "__main__":
    main()

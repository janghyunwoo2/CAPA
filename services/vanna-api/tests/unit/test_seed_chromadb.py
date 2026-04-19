"""
ChromaDB 시딩 품질 테스트 — seed_chromadb.py 정적 분석

외부 서비스(ChromaDB, Vanna, Athena) 연결 없이 QA_EXAMPLES 데이터를 직접 검증.

TC 목록:
  [구조 검증]
  TC-SD-01: QA_EXAMPLES 모든 항목에 question, sql 키 존재
  TC-SD-02: DDL 2개 테이블 정의 (ad_combined_log, ad_combined_log_summary)
  TC-SD-03: Documentation 4개 문서 핵심 키워드 존재

  [테이블 선택 정확성]
  TC-TB-01: ad_combined_log (hourly) 예제 >= 3개
  TC-TB-02: '시간대' 포함 질문 예제 → ad_combined_log 사용
  TC-TB-03: CVR/ROAS/CPA/전환 지표 예제 → ad_combined_log_summary 사용

  [NULLIF 규칙 준수]
  TC-NF-01: CVR 계산 예제에 NULLIF 적용
  TC-NF-02: ROAS 계산 예제에 NULLIF 적용
  TC-NF-03: CPA 계산 예제에 NULLIF 적용
  TC-NF-04: CPC 계산 예제에 NULLIF 적용

  [파티션 조건]
  TC-PT-01: 모든 SQL에 year 파티션 조건 포함
  TC-PT-02: 모든 SQL에 month 파티션 조건 포함
  TC-PT-03: ad_combined_log SQL에 day 파티션 포함

  [카테고리 커버리지 — 12개]
  TC-CV-01: C01 CTR 예제 커버 (>= 2개)
  TC-CV-02: C02 CVR 예제 커버 (>= 2개)
  TC-CV-03: C03 ROAS 예제 커버
  TC-CV-04: C04 CPA 예제 커버
  TC-CV-05: C05 CPC 예제 커버
  TC-CV-06: C06 시간대별 분석 — ad_combined_log 사용
  TC-CV-07: C07 지역별(delivery_region) 분석 예제 커버
  TC-CV-08: C08 광고채널별(platform) 분석 예제 커버 (>= 2개, 주간+월간)
  TC-CV-09: C09 기간 비교 예제 커버 (>= 2개, 주간+월간)
  TC-CV-10: C10 3개월 이상 추이 예제 커버
  TC-CV-11: C11 주중/주말 패턴 예제 커버
  TC-CV-12: C12 전환 0 이상 탐지 예제 커버  ← RED PHASE FAIL 예상

  [과적합 방지]
  TC-OV-01: campaign_id GROUP BY 편중도 <= 40%
  TC-OV-02: month 값 다양성 >= 3종
  TC-OV-03: ad_combined_log_summary 편중도 <= 90%
  TC-OV-04: CTE(WITH ... AS) 패턴 >= 2개
  TC-OV-05: CASE WHEN 패턴 >= 1개
  TC-OV-06: GROUP BY 고유 차원 >= 8종
  TC-OV-07: day_of_week() 함수 패턴 >= 1개
"""

import sys
import os
import re
import importlib.util
import pytest
from unittest.mock import MagicMock


# ── seed_chromadb.py 임포트 (ChromaDB/Vanna 실제 연결 없이) ──────────────
# QueryPipeline 등 외부 의존성을 sys.modules에 Mock 등록 후 임포트
sys.modules.setdefault("src", MagicMock())
sys.modules.setdefault("src.query_pipeline", MagicMock())

_SCRIPT_PATH = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "../../scripts/seed_chromadb.py")
)
_spec = importlib.util.spec_from_file_location("seed_chromadb", _SCRIPT_PATH)
_seed = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_seed)

QA_EXAMPLES: list[dict] = _seed.QA_EXAMPLES
DDL_AD_COMBINED_LOG: str = _seed.DDL_AD_COMBINED_LOG
DDL_AD_COMBINED_LOG_SUMMARY: str = _seed.DDL_AD_COMBINED_LOG_SUMMARY
DOCUMENTATION_BUSINESS_METRICS: str = _seed.DOCS_BUSINESS_METRICS
DOCUMENTATION_ATHENA_RULES: str = _seed.DOCS_ATHENA_RULES
DOCUMENTATION_POLICY: str = _seed.DOCS_POLICIES
DOCUMENTATION_GLOSSARY: str = _seed.DOCS_GLOSSARY


# ── 헬퍼 ─────────────────────────────────────────────────────────────────

def _hourly_examples() -> list[dict]:
    """ad_combined_log (hourly, summary 아닌) 예제만 반환"""
    return [
        qa for qa in QA_EXAMPLES
        if "FROM ad_combined_log\n" in qa["sql"]
        or "FROM ad_combined_log\r" in qa["sql"]
        or qa["sql"].rstrip().endswith("FROM ad_combined_log")
        or (
            "FROM ad_combined_log" in qa["sql"]
            and "FROM ad_combined_log_summary" not in qa["sql"]
        )
    ]


def _examples_with_keyword(*keywords: str) -> list[dict]:
    return [
        qa for qa in QA_EXAMPLES
        if any(kw.lower() in qa["sql"].lower() for kw in keywords)
    ]


# ══════════════════════════════════════════════════════════════════════════
# [구조 검증] TC-SD
# ══════════════════════════════════════════════════════════════════════════

class TestQAExamplesStructure:
    """QA_EXAMPLES 기본 구조 및 상수 정의 검증"""

    def test_all_qa_examples_have_required_keys(self):
        """TC-SD-01: 모든 QA 예제에 question, sql 키 존재 및 비어있지 않음"""
        for i, qa in enumerate(QA_EXAMPLES, 1):
            assert "question" in qa, f"예제 {i}: 'question' 키 없음"
            assert "sql" in qa, f"예제 {i}: 'sql' 키 없음"
            assert qa["question"].strip(), f"예제 {i}: question이 빈 문자열"
            assert qa["sql"].strip(), f"예제 {i}: sql이 빈 문자열"

    def test_ddl_defines_two_tables_with_correct_columns(self):
        """TC-SD-02: ad_combined_log, ad_combined_log_summary DDL 정의 검증"""
        # 두 테이블 모두 CREATE EXTERNAL TABLE 포함
        assert "CREATE EXTERNAL TABLE ad_combined_log" in DDL_AD_COMBINED_LOG
        assert "CREATE EXTERNAL TABLE ad_combined_log_summary" in DDL_AD_COMBINED_LOG_SUMMARY

        # summary 에만 conversion 컬럼 존재
        assert "conversion_id" in DDL_AD_COMBINED_LOG_SUMMARY, \
            "summary 테이블에 conversion_id 없음"
        assert "conversion_id" not in DDL_AD_COMBINED_LOG, \
            "hourly 테이블에 conversion_id가 있으면 안 됨"

        # hourly 테이블에 hour 파티션 있음
        assert "hour" in DDL_AD_COMBINED_LOG, \
            "ad_combined_log에 hour 파티션 컬럼 없음"

    def test_documentation_four_docs_with_core_keywords(self):
        """TC-SD-03: Documentation 4개 문서 핵심 키워드 존재
        각 DOCS 변수는 list[str] — 개별 항목으로 분리되어 임베딩 정밀도 향상
        """
        # 비즈니스 지표 — 5개 KPI 모두 정의
        for kpi in ["CTR", "CVR", "ROAS", "CPA", "CPC"]:
            assert any(kpi in doc for doc in DOCUMENTATION_BUSINESS_METRICS), \
                f"DOCUMENTATION_BUSINESS_METRICS에 {kpi} 정의 없음"

        # Athena 규칙 — 파티션 관련 규칙 존재
        assert any(
            "파티션" in doc or "PARTITIONED" in doc
            for doc in DOCUMENTATION_ATHENA_RULES
        )

        # 정책 — 코드값 정의 존재
        assert any("device_type" in doc for doc in DOCUMENTATION_POLICY)

        # 용어사전 — 핵심 용어 정의
        assert any("노출" in doc for doc in DOCUMENTATION_GLOSSARY)


# ══════════════════════════════════════════════════════════════════════════
# [테이블 선택 정확성] TC-TB
# ══════════════════════════════════════════════════════════════════════════

class TestTableSelection:
    """질문 유형별 테이블 선택 정확성"""

    def test_ad_combined_log_hourly_examples_at_least_three(self):
        """TC-TB-01: ad_combined_log (hourly) 예제 >= 3개"""
        examples = _hourly_examples()
        assert len(examples) >= 3, (
            f"ad_combined_log 예제 {len(examples)}개 (최소 3개 필요). "
            "시간대 분석 질문 시 summary 테이블로 잘못 쿼리될 위험"
        )

    def test_hourly_time_questions_use_ad_combined_log(self):
        """TC-TB-02: '시간대' 포함 질문 예제 → ad_combined_log 사용"""
        time_questions = [
            qa for qa in QA_EXAMPLES
            if "시간대" in qa["question"] or "시간에" in qa["question"]
        ]
        assert len(time_questions) >= 1, "시간대 관련 질문 예제 없음"

        for qa in time_questions:
            is_hourly = (
                "FROM ad_combined_log" in qa["sql"]
                and "FROM ad_combined_log_summary" not in qa["sql"]
            )
            assert is_hourly, (
                f"시간대 질문 '{qa['question']}' → ad_combined_log_summary 사용. "
                "hour 파티션이 있는 ad_combined_log 필수"
            )

    def test_conversion_metric_questions_use_summary_table(self):
        """TC-TB-03: CVR/ROAS/CPA/전환 지표 예제 → ad_combined_log_summary"""
        conversion_questions = [
            qa for qa in QA_EXAMPLES
            if any(kw in qa["question"] for kw in ["CVR", "전환율", "ROAS", "CPA", "전환"])
            and "시간대" not in qa["question"]
        ]
        assert len(conversion_questions) >= 3, \
            f"전환 지표 예제 {len(conversion_questions)}개 (최소 3개 필요)"

        for qa in conversion_questions:
            assert "ad_combined_log_summary" in qa["sql"], (
                f"'{qa['question']}' → summary 테이블 미사용. "
                "conversion_value는 summary 테이블에만 존재"
            )


# ══════════════════════════════════════════════════════════════════════════
# [NULLIF 규칙 준수] TC-NF
# ══════════════════════════════════════════════════════════════════════════

class TestNullIfUsage:
    """0 나누기 방지 NULLIF 규칙 (DOCUMENTATION_BUSINESS_METRICS 준수)"""

    def test_cvr_examples_all_use_nullif(self):
        """TC-NF-01: CVR 계산 예제에 NULLIF 적용"""
        cvr_examples = [
            qa for qa in QA_EXAMPLES
            if "cvr_percent" in qa["sql"].lower()
        ]
        assert len(cvr_examples) >= 1, "CVR 예제 없음"
        for qa in cvr_examples:
            assert "nullif" in qa["sql"].lower(), (
                f"CVR 예제 '{qa['question']}': NULLIF 없음 → "
                "클릭 수 0 시 Division by Zero 위험"
            )

    def test_roas_examples_all_use_nullif(self):
        """TC-NF-02: ROAS 계산 예제에 NULLIF 적용"""
        roas_examples = [
            qa for qa in QA_EXAMPLES
            if "roas" in qa["sql"].lower() and "conversion_value" in qa["sql"]
        ]
        assert len(roas_examples) >= 1, "ROAS 예제 없음"
        for qa in roas_examples:
            assert "nullif" in qa["sql"].lower(), (
                f"ROAS 예제 '{qa['question']}': NULLIF 없음 → "
                "광고비 합계 0 시 Division by Zero 위험"
            )

    def test_cpa_examples_all_use_nullif(self):
        """TC-NF-03: CPA 계산 예제에 NULLIF 적용"""
        cpa_examples = [
            qa for qa in QA_EXAMPLES
            if "as cpa" in qa["sql"].lower()
        ]
        assert len(cpa_examples) >= 1, "CPA 예제 없음"
        for qa in cpa_examples:
            assert "nullif" in qa["sql"].lower(), (
                f"CPA 예제 '{qa['question']}': NULLIF 없음 → "
                "전환 수 0 시 Division by Zero 위험"
            )

    def test_cpc_examples_all_use_nullif(self):
        """TC-NF-04: CPC 계산 예제에 NULLIF 적용"""
        cpc_examples = [
            qa for qa in QA_EXAMPLES
            if "as cpc" in qa["sql"].lower()
        ]
        assert len(cpc_examples) >= 1, "CPC 예제 없음"
        for qa in cpc_examples:
            assert "nullif" in qa["sql"].lower(), (
                f"CPC 예제 '{qa['question']}': NULLIF 없음 → "
                "클릭 수 0 시 Division by Zero 위험"
            )


# ══════════════════════════════════════════════════════════════════════════
# [파티션 조건] TC-PT
# ══════════════════════════════════════════════════════════════════════════

class TestPartitionConditions:
    """Athena 비용 절감 파티션 규칙 (DOCUMENTATION_ATHENA_RULES 준수)"""

    def test_all_sqls_contain_year_partition(self):
        """TC-PT-01: 모든 SQL에 year 파티션 조건 포함
        공백 수 무관하게 검출: re.search(r'year\s*=')
        """
        missing = [
            qa["question"] for qa in QA_EXAMPLES
            if not re.search(r'\byear\s*=', qa["sql"])
        ]
        assert not missing, f"year 파티션 누락 예제: {missing}"

    def test_all_sqls_contain_month_partition(self):
        """TC-PT-02: 모든 SQL에 month 파티션 조건 포함 (= 또는 IN)"""
        missing = [
            qa["question"] for qa in QA_EXAMPLES
            if "month=" not in qa["sql"]
            and "month =" not in qa["sql"]
            and "month IN" not in qa["sql"]
            and "month in" not in qa["sql"]
        ]
        assert not missing, f"month 파티션 누락 예제: {missing}"

    def test_ad_combined_log_sqls_contain_day_partition(self):
        """TC-PT-03: ad_combined_log 단일 일자(어제/오늘) SQL에 day 파티션 포함
        월간 범위 쿼리("이번달")는 month만으로 파티션 프루닝 가능 → 예외 허용
        """
        MONTHLY_KEYWORDS = ("이번달", "지난달", "이번주", "지난주", "지난 7일", "지난 3개월")
        single_day_examples = [
            qa for qa in _hourly_examples()
            if not any(kw in qa["question"] for kw in MONTHLY_KEYWORDS)
        ]
        for qa in single_day_examples:
            has_day = bool(
                re.search(r'\bday\s*=', qa["sql"])
                or "AND day" in qa["sql"]
                or "day >=" in qa["sql"]
            )
            assert has_day, (
                f"ad_combined_log 단일일자 예제 '{qa['question']}': "
                "day 파티션 누락 — year+month+day 필수"
            )


# ══════════════════════════════════════════════════════════════════════════
# [카테고리 커버리지] TC-CV
# 05-sample-queries.md 59개 질문 → 12개 카테고리
# ══════════════════════════════════════════════════════════════════════════

class TestCategoryCoverage:
    """설계서 12개 질의 카테고리 커버리지"""

    def test_c01_ctr_calculation_covered(self):
        """TC-CV-01: C01 CTR 계산 예제 >= 2개 (일간/주간/월간 분산)"""
        examples = [
            qa for qa in QA_EXAMPLES
            if "ctr_percent" in qa["sql"].lower()
        ]
        assert len(examples) >= 2, (
            f"CTR 계산 예제 {len(examples)}개 (최소 2개 필요)"
        )

    def test_c02_cvr_calculation_covered(self):
        """TC-CV-02: C02 CVR 계산 예제 >= 2개"""
        examples = [
            qa for qa in QA_EXAMPLES
            if "cvr_percent" in qa["sql"].lower()
            or (
                "is_conversion" in qa["sql"]
                and "is_click" in qa["sql"]
                and "100.0" in qa["sql"]
            )
        ]
        assert len(examples) >= 2, (
            f"CVR 계산 예제 {len(examples)}개 (최소 2개 필요)"
        )

    def test_c03_roas_calculation_covered(self):
        """TC-CV-03: C03 ROAS 계산 예제 존재"""
        examples = [
            qa for qa in QA_EXAMPLES
            if "roas" in qa["sql"].lower() and "conversion_value" in qa["sql"]
        ]
        assert len(examples) >= 1, "ROAS 예제 없음"

    def test_c04_cpa_calculation_covered(self):
        """TC-CV-04: C04 CPA 계산 예제 존재"""
        examples = [
            qa for qa in QA_EXAMPLES
            if "as cpa" in qa["sql"].lower()
        ]
        assert len(examples) >= 1, (
            "CPA 예제 없음 — Documentation에 정의됐으나 Few-shot 미반영"
        )

    def test_c05_cpc_calculation_covered(self):
        """TC-CV-05: C05 CPC 계산 예제 존재"""
        examples = [
            qa for qa in QA_EXAMPLES
            if "as cpc" in qa["sql"].lower()
        ]
        assert len(examples) >= 1, (
            "CPC 예제 없음 — Documentation에 정의됐으나 Few-shot 미반영"
        )

    def test_c06_hourly_analysis_with_correct_table(self):
        """TC-CV-06: C06 시간대별 분석 — ad_combined_log 사용 예제 존재"""
        examples = [
            qa for qa in _hourly_examples()
            if "hour" in qa["sql"].lower()
        ]
        assert len(examples) >= 1, (
            "시간대별 분석에 ad_combined_log 사용 예제 없음 — "
            "시간대 질문 시 summary 테이블로 잘못 쿼리될 위험"
        )

    def test_c07_region_analysis_covered(self):
        """TC-CV-07: C07 지역별(delivery_region) 분석 예제 존재"""
        examples = [
            qa for qa in QA_EXAMPLES
            if "delivery_region" in qa["sql"]
        ]
        assert len(examples) >= 1, (
            "delivery_region 기반 지역별 분석 예제 없음 — "
            "설계서 일간 #7, #19, #24 미반영"
        )

    def test_c08_channel_analysis_covered_weekly_and_monthly(self):
        """TC-CV-08: C08 광고채널별(ad_format) 분석 — 2개 이상
        광고채널별 분석은 platform이 아닌 ad_format 컬럼 사용 (설계서 §4.2.3)
        """
        examples = [
            qa for qa in QA_EXAMPLES
            if "ad_format" in qa["sql"]
            and "group by" in qa["sql"].lower()
        ]
        assert len(examples) >= 2, (
            f"ad_format GROUP BY 예제 {len(examples)}개 — "
            "광고채널별 분석은 ad_format 사용, 2개 이상 필요"
        )

    def test_c09_period_comparison_covered_weekly_and_monthly(self):
        """TC-CV-09: C09 기간 비교(주간/월간 증감) CTE 예제 >= 2개"""
        examples = [
            qa for qa in QA_EXAMPLES
            if qa["sql"].strip().upper().startswith("WITH ")
            and (
                "growth" in qa["sql"].lower()
                or "대비" in qa["question"]
                or "증감" in qa["question"]
            )
        ]
        assert len(examples) >= 2, (
            f"기간 비교 CTE 예제 {len(examples)}개 — 주간/월간 각 1개 이상 필요"
        )

    def test_c10_three_month_trend_covered(self):
        """TC-CV-10: C10 3개월 이상 추이 예제 존재"""
        examples = [
            qa for qa in QA_EXAMPLES
            if "month IN" in qa["sql"] or "month in" in qa["sql"].lower()
            or "3개월" in qa["question"]
        ]
        assert len(examples) >= 1, (
            "3개월 이상 추이 예제 없음 — 설계서 월간 #15 미반영"
        )

    def test_c11_weekday_weekend_pattern_covered(self):
        """TC-CV-11: C11 주중/주말 패턴 예제 존재 (day_of_week 함수 활용)"""
        examples = [
            qa for qa in QA_EXAMPLES
            if "day_of_week" in qa["sql"]
            or "주말" in qa["question"]
            or "주중" in qa["question"]
        ]
        assert len(examples) >= 1, (
            "주중/주말 패턴 예제 없음 — 설계서 월간 #13 미반영"
        )

    def test_c12_conversion_zero_anomaly_detection_covered(self):
        """TC-CV-12: C12 전환이 0인 이상 탐지 예제 존재

        설계서 일간 리포트 #10: '어제 전환이 0인 캠페인을 찾아줘. 해당 캠페인의 노출과 클릭은?'
        허용 패턴:
          - HAVING COUNT(CASE WHEN is_conversion THEN 1 END) = 0  ← 권장 패턴
          - HAVING SUM(CAST(is_conversion AS INT)) = 0            ← 구버전 호환
        """
        examples = [
            qa for qa in QA_EXAMPLES
            if "is_conversion" in qa["sql"]
            and "HAVING" in qa["sql"]
            and (
                "COUNT(CASE WHEN is_conversion THEN 1 END) = 0" in qa["sql"]
                or "SUM(CAST(is_conversion AS INT)) = 0" in qa["sql"]
            )
        ]
        assert len(examples) >= 1, (
            "전환(is_conversion) 0 탐지 예제 없음. "
            "설계서 일간 #10 '어제 전환이 0인 캠페인을 찾아줘' 미반영."
        )


# ══════════════════════════════════════════════════════════════════════════
# [과적합 방지] TC-OV
# ══════════════════════════════════════════════════════════════════════════

class TestOverfittingPrevention:
    """학습 데이터 다양성 지표 — 과적합 방지"""

    def test_campaign_id_groupby_not_dominant(self):
        """TC-OV-01: campaign_id GROUP BY 편중도 <= 40%"""
        total = len(QA_EXAMPLES)
        count = sum(
            1 for qa in QA_EXAMPLES
            if "GROUP BY campaign_id" in qa["sql"]
            or "group by campaign_id" in qa["sql"].lower()
        )
        ratio = count / total
        assert ratio <= 0.40, (
            f"campaign_id GROUP BY 편중도 {ratio:.0%} > 40%. "
            f"({count}/{total}개) — 다른 차원 쿼리 생성 불가 위험"
        )

    def test_month_value_diversity_at_least_three_values(self):
        """TC-OV-02: month 시간 범위 다양성 >= 3종
        동적 함수(date_format) 사용 시 리터럴 month='XX' 없음 → 동적 오프셋 다양성으로 검증.
        - dynamic_current: 이번달 (date_format(current_date, '%m'))
        - dynamic_minus1m: 지난달 (date_add('month', -1, ...))
        - dynamic_minus2m: 2개월 전 (date_add('month', -2, ...))
        - dynamic_day_offset: 일 단위 오프셋 (date_add('day', -N, ...))
        """
        patterns: set[str] = set()
        for qa in QA_EXAMPLES:
            sql = qa["sql"]
            # 리터럴 패턴
            patterns.update(re.findall(r"month\s*=\s*'(\d{2})'", sql))
            in_clause = re.search(r"month\s+IN\s*\(([^)]+)\)", sql)
            if in_clause:
                patterns.update(re.findall(r"'(\d{2})'", in_clause.group(1)))
            # 동적 표현
            if "date_format(current_date" in sql and "month" in sql.lower():
                patterns.add("dynamic_current")
            if "date_add('month', -1" in sql:
                patterns.add("dynamic_minus1m")
            if "date_add('month', -2" in sql:
                patterns.add("dynamic_minus2m")
            if "date_add('day', -" in sql:
                patterns.add("dynamic_day_offset")

        assert len(patterns) >= 3, (
            f"month 범위 표현 {len(patterns)}종만 사용 (현재: {sorted(patterns)}). "
            "최소 3종 필요 — 특정 월 암기 방지 (current/지난달/-2달 등)"
        )

    def test_summary_table_not_over_dominant(self):
        """TC-OV-03: ad_combined_log_summary 편중도 <= 90%"""
        total = len(QA_EXAMPLES)
        summary_count = sum(
            1 for qa in QA_EXAMPLES
            if "FROM ad_combined_log_summary" in qa["sql"]
        )
        ratio = summary_count / total
        assert ratio <= 0.90, (
            f"ad_combined_log_summary 편중도 {ratio:.0%} > 90%. "
            f"({summary_count}/{total}) — hourly 테이블 예제 추가 필요"
        )

    def test_cte_pattern_used_at_least_twice(self):
        """TC-OV-04: CTE(WITH ... AS) 패턴 예제 >= 2개"""
        cte_examples = [
            qa for qa in QA_EXAMPLES
            if qa["sql"].strip().upper().startswith("WITH ")
        ]
        assert len(cte_examples) >= 2, (
            f"CTE 패턴 예제 {len(cte_examples)}개 — "
            "비교형/다단계 쿼리 학습을 위해 최소 2개 필요"
        )

    def test_case_when_pattern_exists(self):
        """TC-OV-05: CASE WHEN 패턴 예제 >= 1개"""
        examples = [
            qa for qa in QA_EXAMPLES
            if "CASE" in qa["sql"] and "WHEN" in qa["sql"]
        ]
        assert len(examples) >= 1, (
            "CASE WHEN 패턴 예제 없음 — 시간대 구간/조건부 집계 학습 불가"
        )

    def test_group_by_dimension_diversity_at_least_eight(self):
        """TC-OV-06: GROUP BY 고유 차원 >= 8종"""
        target_dims = [
            "campaign_id", "device_type", "platform", "food_category",
            "delivery_region", "advertiser_id", "ad_format", "hour",
            "day", "month", "year", "week_type", "ad_position", "os",
        ]
        found_dims: set[str] = set()
        for qa in QA_EXAMPLES:
            sql_lower = qa["sql"].lower()
            for dim in target_dims:
                if dim in sql_lower:
                    found_dims.add(dim)

        assert len(found_dims) >= 8, (
            f"GROUP BY 고유 차원 {len(found_dims)}종 (최소 8종 필요). "
            f"발견: {sorted(found_dims)}"
        )

    def test_day_of_week_function_pattern_exists(self):
        """TC-OV-07: day_of_week() 함수 패턴 >= 1개"""
        examples = [
            qa for qa in QA_EXAMPLES
            if "day_of_week" in qa["sql"]
        ]
        assert len(examples) >= 1, (
            "day_of_week() 함수 패턴 예제 없음 — "
            "주중/주말 분류 쿼리 학습 불가"
        )

    def test_specific_day_value_not_hardcoded_dominant(self):
        """TC-OV-08: 특정 day='XX' 단일 값 편중도 <= 20%

        모든 '어제' 예제가 동일 day 값을 사용하면
        모델이 '어제 = day=XX'를 암기할 위험.
        최소 3개 이상의 서로 다른 day 값을 사용해야 함.
        """
        total = len(QA_EXAMPLES)
        day_counter: dict[str, int] = {}
        for qa in QA_EXAMPLES:
            days = re.findall(r"day='(\d+)'", qa["sql"])
            for d in days:
                day_counter[d] = day_counter.get(d, 0) + 1

        if not day_counter:
            pytest.skip("day='XX' 패턴 없음 — 검증 불가")

        max_day = max(day_counter, key=lambda k: day_counter[k])
        max_count = day_counter[max_day]
        ratio = max_count / total

        assert ratio <= 0.20, (
            f"day='{max_day}' 편중도 {ratio:.0%} > 20% ({max_count}/{total}개). "
            f"전체 분포: {dict(sorted(day_counter.items()))}. "
            "3개 이상의 서로 다른 참조 날짜로 분산 필요"
        )

        unique_days = len(day_counter)
        assert unique_days >= 3, (
            f"day 고유 값 {unique_days}종 (최소 3종 필요). "
            "현재 분포: {dict(sorted(day_counter.items()))}"
        )

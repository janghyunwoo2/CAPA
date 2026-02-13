"""Airflow DAG: CAPA T2 데이터 파이프라인

이 DAG는 src/data_pipeline_t2/ 폴더 내의 모듈들을 단계적으로 실행합니다:
1. generate_logs: 샘플 광고 로그 생성 (Parquet)
2. process_metrics: 로그 집계 및 메트릭 계산
3. generate_report: 분석 리포트 생성 (CSV)
4. visualize_outputs: CTR 추이 시각화 (PNG)

데이터 흐름:
- raw logs.parquet (10K~20K 행)
- → processed metrics.parquet (집계 메트릭)
- → analysis report_top_ads.csv (상위 광고)
- → outputs/*.png (시각화)

AWS 확장 시:
- S3 경로로 변경: s3://bucket/data/(raw|processed|analysis|outputs)/
- Glue 카탈로그 등록 추가
- 병렬 처리 (동적 파티셔닝) 도입 가능
"""
from __future__ import annotations

import logging
import sys
from datetime import datetime, timedelta
from pathlib import Path

from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.utils.task_group import TaskGroup

# 파이프라인 루트 디렉토리를 sys.path에 추가 (모듈 임포트 위해)
# dags/ 디렉토리의 부모인 data_pipeline_t2/를 루트로 설정
PIPELINE_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PIPELINE_ROOT))

# 로컬 모듈 임포트 (dags/script 패키지 및 루트 모듈)
from dags.script.generate_sample_logs import AdLogGenerator
from dags.script.processor import AdDataProcessor
from dags.script.analyzer import AdAnalytics
from dags.script.visualize import plot_ctr_over_time

# 로거 설정
logger = logging.getLogger(__name__)

# DAG 기본 설정
DEFAULT_ARGS = {
    "owner": "capa-t2-pipeline",
    "depends_on_past": False,
    "email_on_failure": False,
    "email_on_retry": False,
    "retries": 1,
    "retry_delay": timedelta(minutes=1),
}

# ============================================================================
# Task 함수들 (Airflow의 PythonOperator에서 호출)
# ============================================================================


def task_generate_logs(**context) -> None:
    """1단계: 샘플 광고 로그 생성
    
    Args:
        **context: Airflow 컨텍스트 (ti, execution_date 등)
    
    Returns:
        None (부작용: /opt/airflow/data/raw/logs.parquet 생성)
    """
    logger.info("[Task 1] 샘플 로그 생성 시작...")
    gen = AdLogGenerator()  # 기본 경로 사용
    gen.generate(n=20000)  # 20K 샘플 이벤트
    logger.info("[Task 1] 샘플 로그 생성 완료: /opt/airflow/data/raw/logs.parquet")


def task_process_metrics(**context) -> None:
    """2단계: 원시 로그 → 집계 메트릭
    
    일별/광고별로 다음을 집계합니다:
    - impressions: 노출 수
    - clicks: 클릭 수
    - conversions: 전환 수
    - avg_bid_price: 평균 입찰가
    - avg_cpc: 평균 CPC 비용
    - ctr: 클릭률 (=clicks/impressions)
    - conversion_rate: 전환율 (=conversions/clicks)
    
    Args:
        **context: Airflow 컨텍스트
    
    Returns:
        None (부작용: data/processed/metrics.parquet 생성)
    """
    logger.info("[Task 2] 메트릭 처리 시작...")
    processor = AdDataProcessor()  # 기본 경로 사용
    processor.process()
    logger.info("[Task 2] 메트릭 처리 완료: /opt/airflow/data/processed/metrics.parquet")


def task_generate_report(**context) -> None:
    """3단계: 분석 리포트 생성
    
    충분한 노출이 있는 광고들(>=10) 중 CTR 상위 20개를 추출하여 CSV로 저장합니다.
    이 보고서는 마케팅팀의 의사결정에 유용합니다.
    
    Args:
        **context: Airflow 컨텍스트
    
    Returns:
        None (부작용: data/analysis/report_top_ads.csv 생성)
    """
    logger.info("[Task 3] 분석 리포트 생성 시작...")
    analyzer = AdAnalytics()  # 기본 경로 사용
    analyzer.generate_report(top_n=20)
    logger.info("[Task 3] 분석 리포트 생성 완료: /opt/airflow/data/analysis/report_top_ads.csv")


def task_visualize_outputs(**context) -> None:
    """4단계: 시각화 생성
    
    다음 2개의 PNG 차트를 생성합니다:
    - daily_ctr.png: 일별 평균 CTR 추이
    - top5_ads_ctr.png: 상위 5개 광고의 CTR 비교
    
    Args:
        **context: Airflow 컨텍스트
    
    Returns:
        None (부작용: data/outputs/*.png 생성)
    """
    logger.info("[Task 4] 시각화 생성 시작...")
    plot_ctr_over_time()  # 기본 경로 사용
    logger.info("[Task 4] 시각화 생성 완료: /opt/airflow/data/outputs/daily_ctr.png, top5_ads_ctr.png")


# ============================================================================
# DAG 정의
# ============================================================================

with DAG(
    dag_id="00_pipeline_t2_local",
    default_args=DEFAULT_ARGS,
    description="CAPA T2 로컬 데이터 파이프라인: 로그 생성 → 처리 → 분석 → 시각화",
    schedule=None,  # 수동 실행 또는 스케줄 설정 가능 (예: "0 2 * * *" = 매일 2시)
    start_date=datetime(2026, 1, 1),
    catchup=False,
    tags=["capa", "data-pipeline", "t2"],
) as dag:
    
    # =====================================================================
    # 1단계: 로그 생성
    # =====================================================================
    generate_logs = PythonOperator(
        task_id="generate_logs",
        python_callable=task_generate_logs,
        doc_md="""## 샘플 로그 생성
        
        20,000개의 가상 광고 로그를 생성합니다.
        - **impression**: 노출 (80% 확률)
        - **click**: 클릭 (15% 확률)  
        - **conversion**: 전환 (5% 확률)
        
        **출력**: `data/raw/logs.parquet`
        """,
    )
    
    # =====================================================================
    # 2단계: 메트릭 처리
    # =====================================================================
    process_metrics = PythonOperator(
        task_id="process_metrics",
        python_callable=task_process_metrics,
        doc_md="""## 메트릭 집계 및 계산
        
        원시 이벤트를 일별·광고별로 집계하여 다음을 계산합니다:
        - **impressions**: 노출 수
        - **clicks**: 클릭 수
        - **conversions**: 전환 수
        - **avg_bid_price**: 평균 입찰가
        - **avg_cpc**: 평균 CPC 비용
        - **ctr**: CTR = clicks / impressions
        - **conversion_rate**: 전환율 = conversions / clicks
        
        **입력**: `data/raw/logs.parquet`  
        **출력**: `data/processed/metrics.parquet`
        """,
    )
    
    # =====================================================================
    # 3단계: 분석 리포트 생성
    # =====================================================================
    generate_report = PythonOperator(
        task_id="generate_report",
        python_callable=task_generate_report,
        doc_md="""## 분석 리포트 생성
        
        충분한 노출(>=10)을 받은 광고들 중 CTR 상위 20개를 추출합니다(CSV).
        
        **입력**: `data/processed/metrics.parquet`  
        **출력**: `data/analysis/report_top_ads.csv`
        """,
    )
    
    # =====================================================================
    # 4단계: 시각화
    # =====================================================================
    visualize_outputs = PythonOperator(
        task_id="visualize_outputs",
        python_callable=task_visualize_outputs,
        doc_md="""## 시각화 생성
        
        2개의 PNG 차트를 생성합니다:
        1. **daily_ctr.png**: 일별 평균 CTR 추이
        2. **top5_ads_ctr.png**: 상위 5개 광고의 CTR 비교
        
        **입력**: `data/processed/metrics.parquet`  
        **출력**: `data/outputs/daily_ctr.png, top5_ads_ctr.png`
        """,
    )
    
    # =====================================================================
    # 태스크 의존성 설정: 선형 흐름
    # =====================================================================
    generate_logs >> process_metrics >> generate_report >> visualize_outputs

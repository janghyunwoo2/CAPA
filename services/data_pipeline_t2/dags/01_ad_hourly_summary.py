"""
DAG: ad_hourly_summary
주기: 매시간
역할: etl_summary_t2의 HourlyETL 호출
      impression + click → ad_combined_log 테이블 생성

데이터 흐름:
  data_interval_start (시간)
    → etl_summary_t2.HourlyETL(target_hour)
    → Athena CTAS/INSERT OVERWRITE
    → S3 Parquet (summary/ad_combined_log/)
    → 파티션 등록 완료
"""
import sys
import os
import pendulum
from pathlib import Path
from airflow import DAG
from airflow.providers.standard.operators.python import PythonOperator
from datetime import datetime, timedelta

# etl_summary_t2 모듈 import를 위해 경로 추가
ETL_PATH = str(Path(__file__).parent.parent / "etl_summary_t2")
if ETL_PATH not in sys.path:
    sys.path.insert(0, ETL_PATH)

from hourly_etl import HourlyETL

# =============================================================================
# 설정
# =============================================================================
default_args = {
    "owner": "capa",
    "depends_on_past": False,
    "retries": 2,
    "retry_delay": timedelta(minutes=5),
    "execution_timeout": timedelta(minutes=30),
}

# =============================================================================
# Task Functions
# =============================================================================

def run_hourly_etl(**context):
    """
    etl_summary_t2의 HourlyETL을 실행
    data_interval_start를 기반으로 target_hour 설정
    """
    try:
        dt = context["data_interval_start"]
        print(f"[INFO] Running HourlyETL for {dt}")
        etl = HourlyETL(target_hour=dt)
        etl.run()
        print(f"[SUCCESS] HourlyETL completed successfully")
    except Exception as e:
        print(f"[ERROR] HourlyETL failed: {str(e)}")
        raise












# =============================================================================
# DAG 정의
# =============================================================================
with DAG(
    dag_id="01_ad_hourly_summary",
    default_args=default_args,
    description="etl_summary_t2의 HourlyETL을 호출하여 hourly summary 생성",
    schedule_interval="0 * * * *",  # 매 정각
    start_date=pendulum.datetime(2026, 2, 13, tz=pendulum.timezone("Asia/Seoul")),
    catchup=False,
    max_active_runs=1,
    tags=["capa", "hourly", "ad", "etl"],
) as dag:

    # Task: HourlyETL 실행
    run_etl = PythonOperator(
        task_id="run_hourly_etl",
        python_callable=run_hourly_etl,
        provide_context=True,
    )

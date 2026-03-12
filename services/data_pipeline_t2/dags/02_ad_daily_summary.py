"""
DAG: ad_daily_summary
주기: 매일
역할: etl_summary_t2의 DailyETL 호출
      ad_combined_log 24시간 + conversion 조인
      → ad_combined_log_summary 테이블 생성

데이터 흐름:
  data_interval_start (날짜)
    → etl_summary_t2.DailyETL(target_date)
    → Athena CTAS/INSERT OVERWRITE
    → S3 Parquet (summary/ad_combined_log_summary/)
    → 파티션 등록 완료
"""
import sys
import os
import pendulum
from pathlib import Path
from airflow import DAG
from airflow.providers.standard.operators.python import PythonOperator
from airflow.sensors.external_task import ExternalTaskSensor
from datetime import datetime, timedelta

# etl_summary_t2 모듈 import를 위해 경로 추가
ETL_PATH = str(Path(__file__).parent.parent / "etl_summary_t2")
if ETL_PATH not in sys.path:
    sys.path.insert(0, ETL_PATH)

from daily_etl import DailyETL

# =============================================================================
# 설정
# =============================================================================
default_args = {
    "owner": "capa",
    "depends_on_past": False,
    "retries": 2,
    "retry_delay": timedelta(minutes=10),
    "execution_timeout": timedelta(minutes=60),
}


# =============================================================================
# Task Functions
# =============================================================================

def run_daily_etl(**context):
    """
    etl_summary_t2의 DailyETL을 실행
    data_interval_start를 기반으로 target_date 설정
    """
    try:
        dt = context["data_interval_start"]
        print(f"[INFO] Running DailyETL for {dt}")
        etl = DailyETL(target_date=dt)
        etl.run()
        print(f"[SUCCESS] DailyETL completed successfully")
    except Exception as e:
        print(f"[ERROR] DailyETL failed: {str(e)}")
        raise





# =============================================================================
# DAG 정의
# =============================================================================
with DAG(
    dag_id="02_ad_daily_summary",
    default_args=default_args,
    description="etl_summary_t2의 DailyETL을 호출하여 daily summary 생성",
    schedule_interval="0 1 * * *",  # 매일 01:00
    start_date=pendulum.datetime(2026, 2, 13, tz=pendulum.timezone("Asia/Seoul")),
    catchup=False,
    max_active_runs=1,
    tags=["capa", "daily", "ad", "etl"],
) as dag:



    # Task: DailyETL 실행
    run_etl = PythonOperator(
        task_id="run_daily_etl",
        python_callable=run_daily_etl,
        provide_context=True,
    )


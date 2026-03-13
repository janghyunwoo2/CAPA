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

# 독립 ETL 모듈 import (dags/etl_modules 내부에 위치)
from etl_modules.daily_etl import DailyETL

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
        # UTC to KST 변환
        dt_utc = context["data_interval_start"]
        dt_kst = pendulum.instance(dt_utc).in_timezone('Asia/Seoul')
        
        # 전일 날짜로 변경 (완전한 24시간 데이터를 처리하기 위함)
        target_date = dt_kst.subtract(days=1)
        print(f"[INFO] UTC time: {dt_utc}, KST time: {dt_kst}")
        print(f"[INFO] Processing previous day: {target_date}")
        print(f"[INFO] Running DailyETL for {target_date}")
        
        etl = DailyETL(target_date=target_date)
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
    schedule="0 2 * * *",  # 매일 02:00
    start_date=pendulum.datetime(2026, 2, 13, tz=pendulum.timezone("Asia/Seoul")),
    catchup=False,
    max_active_runs=1,
    tags=["capa", "daily", "ad", "etl"],
) as dag:



    # Task: DailyETL 실행
    run_etl = PythonOperator(
        task_id="run_daily_etl",
        python_callable=run_daily_etl,
    )


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

# 독립 ETL 모듈 import (dags/etl_modules 내부에 위치)
from etl_modules.hourly_etl import HourlyETL

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
        # Airflow context 디버깅
        print("[DEBUG] Airflow Context Info:")
        print(f"  - logical_date: {context.get('logical_date')}")
        print(f"  - data_interval_start: {context.get('data_interval_start')}")
        print(f"  - data_interval_end: {context.get('data_interval_end')}")
        print(f"  - execution_date: {context.get('execution_date')}")
        print(f"  - ds: {context.get('ds')}")
        print(f"  - ts: {context.get('ts')}")
        
        # data_interval_start가 처리해야 할 시간의 시작점
        # 예: 12:10 실행 → data_interval_start는 11:00이어야 함
        # 하지만 schedule이 정각이 아닌 10분으로 변경되면서 data_interval_start가 현재 시간으로 설정됨
        # 따라서 1시간을 빼서 이전 시간 데이터를 처리하도록 수정
        dt_utc = context["data_interval_start"]
        dt_kst = pendulum.instance(dt_utc).in_timezone('Asia/Seoul')
        
        # 실제 처리할 시간: data_interval_start - 1시간
        target_hour_kst = dt_kst.subtract(hours=1)
        
        print(f"\n[INFO] DAG Schedule Info:")
        print(f"  - data_interval_start (KST): {dt_kst.format('YYYY-MM-DD HH:00')}")
        print(f"  - Target hour for processing: {target_hour_kst.format('YYYY-MM-DD HH:00')} (previous hour)")
        print(f"  - Data interval (UTC): {dt_utc} ~ {context['data_interval_end']}")
        print(f"  - Data interval (KST): {dt_kst} ~ {pendulum.instance(context['data_interval_end']).in_timezone('Asia/Seoul')}")
        
        etl = HourlyETL(target_hour=target_hour_kst)
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
<<<<<<< HEAD
<<<<<<< HEAD
    schedule="10 * * * *",  # 매시간 10분
    start_date=pendulum.datetime(2026, 2, 13, tz="UTC"),  # UTC로 변경
=======
    schedule="0 * * * *",  # 매 정각
    start_date=pendulum.datetime(2026, 2, 13, tz=pendulum.timezone("Asia/Seoul")),
>>>>>>> 5ba5ed0 (Feat : airflow ETL 테스트중)
=======
    schedule="10 * * * *",  # 매시간 10분
    start_date=pendulum.datetime(2026, 2, 13, tz="UTC"),  # UTC로 변경
>>>>>>> 21d6c56 (Feat : airflow ETL 테스트 완료.)
    catchup=False,
    max_active_runs=1,
    tags=["capa", "hourly", "ad", "etl"],
) as dag:

    # Task: HourlyETL 실행
    run_etl = PythonOperator(
        task_id="run_hourly_etl",
        python_callable=run_hourly_etl,
    )

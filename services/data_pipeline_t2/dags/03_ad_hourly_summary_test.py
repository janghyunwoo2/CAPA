"""
DAG(수동 실행 전용): ad_hourly_summary_test
주기: 없음 (schedule=None) - 테스트용이므로 자동 실행 없음
역할: impressions + clicks → ad_combined_log 테이블 생성 (수동 1회 트리거용)
참고: 프로덕션 DAG(01_ad_hourly_summary)는 매시간 실행, 이 DAG는 테스트/디버깅용
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
    - 수동 실행: 현재 시간(KST) 기준으로 실행
    - 스케줄 실행(없음): data_interval_start 사용하지만 이 DAG는 수동 전용
    """
    try:
        # 현재 시간에서 1시간 전으로 설정 (수동 테스트 전용)
        current_kst = pendulum.now('Asia/Seoul')
        dt_kst = current_kst.subtract(hours=1).replace(minute=0, second=0, microsecond=0)
        
        # 디버깅을 위한 상세 로그
        print(f"[DEBUG] Current KST time: {current_kst}")
        print(f"[DEBUG] ETL Target KST time: {dt_kst} (현재 시간 - 1시간)")
        print(f"[DEBUG] Hour: {dt_kst.hour}, Date: {dt_kst.date()}")
        
        # context에서 data_interval_start가 있으면 UTC->KST 변환
        if "data_interval_start" in context and context["data_interval_start"]:
            dt_utc = context["data_interval_start"]
            print(f"[DEBUG] data_interval_start (UTC): {dt_utc}")
            # 만약 data_interval_start가 있더라도 수동 테스트에서는 현재 시간 사용
            print(f"[DEBUG] Using current KST time instead for manual test")
        
        print(f"[INFO] Running HourlyETL for {dt_kst}")
        etl = HourlyETL(target_hour=dt_kst)
        etl.run()
        print(f"[SUCCESS] HourlyETL completed successfully for hour={dt_kst.hour}")
    except Exception as e:
        print(f"[ERROR] HourlyETL failed: {str(e)}")
        raise

# =============================================================================
# DAG 정의
# =============================================================================
with DAG(
    dag_id="03_ad_hourly_summary_test",
    default_args=default_args,
    description="수동 실행: etl_summary_t2의 HourlyETL을 호출하여 hourly summary 생성 (테스트용)",
    schedule=None,  # 수동 트리거 전용
    start_date=pendulum.datetime(2026, 2, 13, tz=pendulum.timezone("Asia/Seoul")),
    catchup=False,
    max_active_runs=1,
    tags=["capa", "hourly", "ad", "etl", "test"],
) as dag:

    # Task: HourlyETL 실행
    run_etl = PythonOperator(
        task_id="run_hourly_etl",
        python_callable=run_hourly_etl,
    )

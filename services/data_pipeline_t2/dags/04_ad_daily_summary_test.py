"""
DAG(수동 실행 전용): ad_daily_summary_test
주기: 없음 (schedule=None)
역할: hourly_summary 24개 집계 + conversion 원천 로그 조인 (수동 1회 트리거용)
"""
import sys
import os
import pendulum
from pathlib import Path
from airflow import DAG
from airflow.providers.standard.operators.python import PythonOperator
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
    테스트용이므로 항상 어제 날짜(KST) 기준으로 실행
    """
    try:
        # 항상 어제 KST 날짜 사용 (수동 테스트 전용)
        dt_kst = pendulum.now('Asia/Seoul').subtract(days=1)
        
        # 디버깅을 위한 상세 로그
        print(f"[DEBUG] Yesterday KST time: {dt_kst}")
        print(f"[DEBUG] Date: {dt_kst.date()}")
        
        # context에서 data_interval_start가 있으면 정보만 출력
        if "data_interval_start" in context and context["data_interval_start"]:
            dt_utc = context["data_interval_start"]
            print(f"[DEBUG] data_interval_start (UTC): {dt_utc}")
            print(f"[DEBUG] Using yesterday KST date instead for manual test")
        
        print(f"[INFO] Running DailyETL for {dt_kst.date()}")
        etl = DailyETL(target_date=dt_kst)
        etl.run()
        print(f"[SUCCESS] DailyETL completed successfully")
    except Exception as e:
        print(f"[ERROR] DailyETL failed: {str(e)}")
        raise

# =============================================================================
# DAG 정의
# =============================================================================
with DAG(
    dag_id="04_ad_daily_summary_test",
    default_args=default_args,
    description="수동 실행: etl_summary_t2의 DailyETL을 호출하여 daily summary 생성 (테스트용)",
    schedule=None,  # 수동 트리거 전용
    start_date=pendulum.datetime(2026, 2, 13, tz=pendulum.timezone("Asia/Seoul")),
    catchup=False,
    max_active_runs=1,
    tags=["capa", "daily", "ad", "etl", "test"],
) as dag:

    # Task: DailyETL 실행
    run_etl = PythonOperator(
        task_id="run_daily_etl",
        python_callable=run_daily_etl,
    )

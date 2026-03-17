"""T3 Report Generator v3 DAG

매일 08:00 KST 실행:
- 일간 보고서: 매일
- 주간 보고서: 월요일만 (지난주 월~일)
- 월간 보고서: 매월 3일만 (전월 전체)

Slack 발송 순서: 일간 → 주간 → 월간
"""

import sys
from datetime import datetime, timedelta
from airflow import DAG
from airflow.operators.python import PythonOperator

default_args = {
    'owner': 'data-team',
    'retries': 2,
    'retry_delay': timedelta(minutes=5),
    'start_date': datetime(2026, 1, 1),
}

dag = DAG(
    dag_id='t3_report_generator_v3',
    default_args=default_args,
    description='T3 일간/주간/월간 보고서 자동 생성 및 Slack 발송',
    schedule_interval='0 23 * * *',  # UTC 23:00 = KST 08:00 (매일)
    catchup=False,
    tags=['report-generator', 't3', 'v3'],
)


def run_daily(**context):
    sys.path.insert(0, '/opt/airflow/parent/report-generator/t3_report_generator')
    from main import generate_daily_report

    date_str = datetime.now().strftime('%Y-%m-%d')
    result = generate_daily_report(date_str)

    if result['status'] != 'success':
        from airflow.exceptions import AirflowException
        raise AirflowException(f"일간 보고서 실패: {result.get('error')}")


def run_weekly(**context):
    sys.path.insert(0, '/opt/airflow/parent/report-generator/t3_report_generator')
    from main import generate_weekly_report

    # 월요일이 아니면 스킵
    if datetime.now().weekday() != 0:
        print("[주간] 월요일 아님, 스킵")
        return

    date_str = datetime.now().strftime('%Y-%m-%d')
    result = generate_weekly_report(date_str)

    if result['status'] != 'success':
        from airflow.exceptions import AirflowException
        raise AirflowException(f"주간 보고서 실패: {result.get('error')}")


def run_monthly(**context):
    sys.path.insert(0, '/opt/airflow/parent/report-generator/t3_report_generator')
    from main import generate_monthly_report

    # 3일이 아니면 스킵
    if datetime.now().day != 3:
        print("[월간] 3일 아님, 스킵")
        return

    date_str = datetime.now().strftime('%Y-%m-%d')
    result = generate_monthly_report(date_str)

    if result['status'] != 'success':
        from airflow.exceptions import AirflowException
        raise AirflowException(f"월간 보고서 실패: {result.get('error')}")


task_daily = PythonOperator(
    task_id='daily_report',
    python_callable=run_daily,
    provide_context=True,
    dag=dag,
)

task_weekly = PythonOperator(
    task_id='weekly_report',
    python_callable=run_weekly,
    provide_context=True,
    dag=dag,
)

task_monthly = PythonOperator(
    task_id='monthly_report',
    python_callable=run_monthly,
    provide_context=True,
    dag=dag,
)

# 순서 보장: 일간 → 주간 → 월간
task_daily >> task_weekly >> task_monthly

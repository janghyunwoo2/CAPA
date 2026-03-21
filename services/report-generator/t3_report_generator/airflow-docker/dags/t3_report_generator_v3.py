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
    # 통합 알림을 위해 파일만 업로드
    result = generate_daily_report(date_str, only_upload=True)

    if result['status'] == 'success':
        context['ti'].xcom_push(key='report_created', value='daily')
    else:
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
    # 통합 알림을 위해 파일만 업로드
    result = generate_weekly_report(date_str, only_upload=True)

    if result['status'] == 'success':
        context['ti'].xcom_push(key='report_created', value='weekly')
    else:
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
    # 통합 알림을 위해 파일만 업로드
    result = generate_monthly_report(date_str, only_upload=True)

    if result['status'] == 'success':
        context['ti'].xcom_push(key='report_created', value='monthly')
    else:
        from airflow.exceptions import AirflowException
        raise AirflowException(f"월간 보고서 실패: {result.get('error')}")


def notify_slack(**context):
    sys.path.insert(0, '/opt/airflow/parent/report-generator/t3_report_generator')
    from main import send_final_notification

    # XCom에서 생성된 보고서 목록 취합
    ti = context['ti']
    dag_run = context['dag_run']
    
    created_reports = []
    for task_id in ['daily_report', 'weekly_report', 'monthly_report']:
        val = ti.xcom_pull(task_ids=task_id, key='report_created')
        if val:
            created_reports.append(val)

    if not created_reports:
        print("생성된 보고서가 없어 알림을 건너뜁니다.")
        return

    date_str = datetime.now().strftime('%Y-%m-%d')
    send_final_notification(created_reports, date_str)


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

task_notify = PythonOperator(
    task_id='notify_slack',
    python_callable=notify_slack,
    provide_context=True,
    trigger_rule='all_done',  # 실패하더라도 일단 알림 시도 (또는 상황에 맞춰 변경)
    dag=dag,
)

# 순서 보장: 일간 → 주간 → 월간 → 통합 알림
task_daily >> task_weekly >> task_monthly >> task_notify

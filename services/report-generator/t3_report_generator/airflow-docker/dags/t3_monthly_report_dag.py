"""T3 월간 보고서 DAG - 매월 3일 08:00 KST 실행"""

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
    dag_id='t3_monthly_report',
    default_args=default_args,
    description='T3 월간 보고서 - 매월 3일 08:00 KST (전월 전체)',
    schedule_interval=None,  # 비활성화 → t3_report_generator_v3로 대체
    catchup=False,
    tags=['report-generator', 't3', 'monthly'],
)


def run(**context):
    import sys
    sys.path.insert(0, '/opt/airflow/parent/report-generator/t3_report_generator')
    from main import generate_monthly_report

    date_str = datetime.now().strftime('%Y-%m-%d')
    result = generate_monthly_report(date_str)

    if result['status'] != 'success':
        from airflow.exceptions import AirflowException
        raise AirflowException(f"월간 보고서 생성 실패: {result.get('error')}")

    return result


PythonOperator(
    task_id='generate_monthly_report',
    python_callable=run,
    provide_context=True,
    dag=dag,
)

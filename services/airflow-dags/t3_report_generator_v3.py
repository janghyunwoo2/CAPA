"""
T3 리포트 생성 DAG v3 — KubernetesPodOperator 버전

변경 이력:
  v3: PythonOperator → KubernetesPodOperator 전환
      전용 ECR 이미지(capa-t3-report-generator)로 독립 실행
      K8s Secret(t3-report-secret)으로 환경변수 주입
"""
from datetime import datetime, timedelta

from airflow import DAG
from airflow.providers.cncf.kubernetes.operators.pod import KubernetesPodOperator
from kubernetes.client import V1EnvFromSource, V1SecretEnvSource

ECR_IMAGE = "827913617635.dkr.ecr.ap-northeast-2.amazonaws.com/capa/airflow-kpo-t3-report:latest"
NAMESPACE = "airflow"
SA_NAME = "airflow-scheduler"

# K8s Secret에서 환경변수 일괄 주입
env_from = [
    V1EnvFromSource(
        secret_ref=V1SecretEnvSource(name="t3-report-secret")
    )
]

default_args = {
    "owner": "data-team",
    "retries": 2,
    "retry_delay": timedelta(minutes=5),
    "start_date": datetime(2026, 1, 1),
}

dag = DAG(
    dag_id="t3_report_generator_v3",
    default_args=default_args,
    description="T3 일간/주간/월간 보고서 자동 생성 및 Slack 발송",
    schedule_interval="0 23 * * *",  # UTC 23:00 = KST 08:00
    catchup=False,
    tags=["report-generator", "t3", "v3"],
)

task_daily = KubernetesPodOperator(
    task_id="daily_report",
    name="t3-daily-report",
    namespace=NAMESPACE,
    image=ECR_IMAGE,
    cmds=["python", "-c"],
    arguments=["""
import sys
sys.path.insert(0, '/app')
from datetime import datetime
from main import generate_daily_report
date_str = datetime.now().strftime('%Y-%m-%d')
result = generate_daily_report(date_str, only_upload=True)
if result['status'] != 'success':
    raise Exception(f"일간 보고서 실패: {result.get('error')}")
print(f"일간 보고서 완료: {result['date']}")
"""],
    env_from=env_from,
    service_account_name=SA_NAME,
    get_logs=True,
    is_delete_operator_pod=True,
    dag=dag,
)

task_weekly = KubernetesPodOperator(
    task_id="weekly_report",
    name="t3-weekly-report",
    namespace=NAMESPACE,
    image=ECR_IMAGE,
    cmds=["python", "-c"],
    arguments=["""
import sys
sys.path.insert(0, '/app')
from datetime import datetime
from main import generate_weekly_report
if datetime.now().weekday() != 0:
    print("[주간] 월요일 아님, 스킵")
else:
    date_str = datetime.now().strftime('%Y-%m-%d')
    result = generate_weekly_report(date_str, only_upload=True)
    if result['status'] != 'success':
        raise Exception(f"주간 보고서 실패: {result.get('error')}")
    print(f"주간 보고서 완료: {result['date']}")
"""],
    env_from=env_from,
    service_account_name=SA_NAME,
    get_logs=True,
    is_delete_operator_pod=True,
    dag=dag,
)

task_monthly = KubernetesPodOperator(
    task_id="monthly_report",
    name="t3-monthly-report",
    namespace=NAMESPACE,
    image=ECR_IMAGE,
    cmds=["python", "-c"],
    arguments=["""
import sys
sys.path.insert(0, '/app')
from datetime import datetime
from main import generate_monthly_report
if datetime.now().day != 3:
    print("[월간] 3일 아님, 스킵")
else:
    date_str = datetime.now().strftime('%Y-%m-%d')
    result = generate_monthly_report(date_str, only_upload=True)
    if result['status'] != 'success':
        raise Exception(f"월간 보고서 실패: {result.get('error')}")
    print(f"월간 보고서 완료: {result['date']}")
"""],
    env_from=env_from,
    service_account_name=SA_NAME,
    get_logs=True,
    is_delete_operator_pod=True,
    dag=dag,
)

task_notify = KubernetesPodOperator(
    task_id="notify_slack",
    name="t3-notify-slack",
    namespace=NAMESPACE,
    image=ECR_IMAGE,
    cmds=["python", "-c"],
    arguments=["""
import sys
sys.path.insert(0, '/app')
from datetime import datetime
from main import send_final_notification
date_str = datetime.now().strftime('%Y-%m-%d')
send_final_notification(['daily', 'weekly', 'monthly'], date_str)
print("Slack 통합 알림 완료")
"""],
    env_from=env_from,
    service_account_name=SA_NAME,
    get_logs=True,
    is_delete_operator_pod=True,
    trigger_rule="all_done",
    dag=dag,
)

# Task 의존성 체인
task_daily >> task_weekly >> task_monthly >> task_notify

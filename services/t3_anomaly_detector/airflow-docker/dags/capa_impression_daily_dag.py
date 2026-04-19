"""
capa_impression_daily_dag.py
- 매일 아침 08:02 (KST) 딱 1번 실행되는 정기 리포트 전용 DAG입니다.
- 이상치 여부와 상관없이 무조건 슬랙 메시지를 전송합니다. (-e TEST_MODE_FORCE_SLACK=True)
"""
from airflow import DAG
from airflow.operators.bash import BashOperator
from datetime import datetime, timedelta
import os

default_args = {
    "owner": "airflow",
    "depends_on_past": False,
    "retries": 1,
    "retry_delay": timedelta(minutes=1),
    "email_on_failure": False,
}

with DAG(
    dag_id="capa_impression_daily",
    description="매일 아침 08:02 정기 슬랙 전송 (무조건 전송)",
    schedule_interval="2 23 * * *",       # UTC 23:02 = KST 08:02 (전날 밤 11시 2분)
    start_date=datetime(2026, 3, 22),
    catchup=False,
    max_active_runs=1,
    default_args=default_args,
    tags=["daily", "impression", "monitoring"],
) as dag:

    run_daily_check = BashOperator(
        task_id="send_daily_slack_check",
        bash_command="""
            docker run --rm \
              --name impression_daily_run_{{ ts_nodash }} \
              --env-file /opt/anomaly_detector/capa-impression/.env \
              -e TEST_MODE_FORCE_SLACK=True \
              -e AWS_DEFAULT_REGION=ap-northeast-2 \
              -e TZ=Asia/Seoul \
              -v C:/Users/Dell3571/Desktop/projects/CAPA/services/t3_anomaly_detector/capa-impression/models:/app/models \
              -v C:/Users/Dell3571/Desktop/projects/CAPA/services/t3_anomaly_detector/capa-impression/output:/app/output \
              -v C:/Users/Dell3571/.aws:/root/.aws:ro \
              capa-impression-anomaly
        """,
        doc_md="""
        ### 아침 정기 슬랙 전송
        - 이 태스크는 **이상치 여부와 상관없이** 현재 상태를 슬랙으로 보고합니다.
        - `TEST_MODE_FORCE_SLACK=True` 환경 변수를 강제로 주입하여 실행합니다.
        """,
    )

"""
t3_anomaly_detector Airflow DAG (Conversion)
- 매 5분(정각 기준) 마다 capa-conversion 도커 컨테이너를 실행합니다.
"""
from airflow import DAG
from airflow.operators.bash import BashOperator
from datetime import datetime, timedelta
import os

# 호스트 PC의 t3_anomaly_detector 실제 경로
BASE_DIR = os.getenv(
    "ANOMALY_DETECTOR_BASE_DIR",
    "C:/Users/Dell3571/Desktop/projects/CAPA/services/t3_anomaly_detector"
)

default_args = {
    "owner": "airflow",
    "depends_on_past": False,
    "retries": 1,
    "retry_delay": timedelta(minutes=1),
    "email_on_failure": False,
}

with DAG(
    dag_id="capa_conversion_anomaly_detector",
    description="5분마다 Conversion 지표 이상 탐지 파이프라인 실행",
    schedule_interval="*/5 * * * *",
    start_date=datetime(2026, 3, 22),
    catchup=False,
    max_active_runs=1,
    default_args=default_args,
    tags=["anomaly", "conversion", "monitoring"],
) as dag:

    run_anomaly_detector = BashOperator(
        task_id="run_conversion_anomaly_detector",
        bash_command="""
            docker run --rm \
              --name anomaly_detector_conversion_run_{{ ts_nodash }} \
              --env-file /opt/anomaly_detector/capa-conversion/.env \
              -e AWS_DEFAULT_REGION=ap-northeast-2 \
              -e TZ=Asia/Seoul \
              -v C:/Users/Dell3571/Desktop/projects/CAPA/services/t3_anomaly_detector/capa-conversion/models:/app/models \
              -v C:/Users/Dell3571/Desktop/projects/CAPA/services/t3_anomaly_detector/capa-conversion/output:/app/output \
              -v C:/Users/Dell3571/.aws:/root/.aws:ro \
              capa-conversion
        """,
    )

"""
t3_anomaly_detector Airflow DAG
- 매 5분(정각 + 2분 기준) 마다 t3_anomaly_detector 도커 컨테이너를 실행합니다.
- 실행 시각: 02분, 07분, 12분, 17분, ..., 57분
- 컨테이너는 1회 실행 후 자동 종료됩니다.
- Airflow가 다음 주기에 다시 실행시킵니다.
"""
from airflow import DAG
from airflow.operators.bash import BashOperator
from datetime import datetime, timedelta
import os

# 호스트 PC의 t3_anomaly_detector 실제 경로 (Airflow 컨테이너 → 호스트 도커 소켓 사용)
# 이 경로는 Airflow가 실행되는 호스트 기준의 절대 경로입니다.
BASE_DIR = os.getenv(
    "ANOMALY_DETECTOR_BASE_DIR",
    "C:/Users/Dell3571/Desktop/projects/CAPA/services/t3_anomaly_detector"
)
AWS_CREDENTIALS_DIR = os.getenv(
    "AWS_CREDENTIALS_DIR",
    "C:/Users/Dell3571/.aws"
)

default_args = {
    "owner": "airflow",
    "depends_on_past": False,
    "retries": 1,
    "retry_delay": timedelta(minutes=1),
    "email_on_failure": False,
}

with DAG(
    dag_id="capa_impression_anomaly_detector",
    description="매 시 2분부터 5분 간격으로 이상 탐지 파이프라인 실행",
    schedule_interval="2-59/5 * * * *",  # 2분부터 시작해서 매 5분마다 실행
    start_date=datetime(2026, 3, 22),
    catchup=False,                    # 과거 놓친 실행은 무시
    max_active_runs=1,                # 동시에 하나의 실행만 허용
    default_args=default_args,
    tags=["anomaly", "impression", "monitoring"],
) as dag:

    run_anomaly_detector = BashOperator(
        task_id="run_impression_anomaly_detector",
        bash_command="""
            docker run --rm \
              --name anomaly_detector_airflow_run_{{ ts_nodash }} \
              --env-file /opt/anomaly_detector/capa-impression/.env \
              -e AWS_DEFAULT_REGION=ap-northeast-2 \
              -e TZ=Asia/Seoul \
              -v C:/Users/Dell3571/Desktop/projects/CAPA/services/t3_anomaly_detector/capa-impression/models:/app/models \
              -v C:/Users/Dell3571/Desktop/projects/CAPA/services/t3_anomaly_detector/capa-impression/output:/app/output \
              -v C:/Users/Dell3571/.aws:/root/.aws:ro \
              capa-impression
        """,
        doc_md="""
        ### t3_anomaly_detector 실행
        - CloudWatch에서 최근 24시간 데이터를 가져옵니다.
        - Prophet + IsolationForest로 이상 탐지를 수행합니다.
        - 결과를 PNG/HTML/JSONL로 저장합니다.
        - 실행 완료 후 컨테이너는 자동 종료됩니다.
        """,
    )

"""
DAG: t2_ad_daily_summary (KubernetesPodOperator 버전)

EKS Airflow 배포용. 매일 하루치 광고 성과 로그를 요약(DailyETL)합니다.
기존 PythonOperator(02_ad_daily_summary.py)와 동일한 비즈니스 로직을
전용 ECR 컨테이너 환경에서 독립적으로 실행합니다.
"""

import pendulum
from datetime import timedelta

from airflow import DAG
from airflow.providers.cncf.kubernetes.operators.pod import KubernetesPodOperator
from kubernetes.client import V1EnvFromSource, V1SecretEnvSource

# ── 1. 공통 상수 ─────────────────────────────────────────────────────────────
ECR_IMAGE = "827913617635.dkr.ecr.ap-northeast-2.amazonaws.com/capa/airflow-kpo-t2-etl-runner:latest"
NAMESPACE = "airflow"
SA_NAME = "airflow-scheduler"

# 환경변수 주입 (K8s Secret에서 AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY 주입)
env_from = [V1EnvFromSource(secret_ref=V1SecretEnvSource(name="t2-etl-secret"))]

# ── 2. DAG 기본 설정 ─────────────────────────────────────────────────────────
default_args = {
    "owner": "capa",
    "depends_on_past": False,
    "retries": 2,
    "retry_delay": timedelta(minutes=10),
    "execution_timeout": timedelta(minutes=60),
}

# ── 3. DAG 정의 ──────────────────────────────────────────────────────────────
with DAG(
    dag_id="t2_ad_daily_summary_v2",
    default_args=default_args,
    description="[EKS] T2 DailyETL — 일일 광고 성과 요약 (KubernetesPodOperator)",
    schedule="0 2 * * *",  # 매일 02:00 KST
    start_date=pendulum.datetime(2026, 2, 13, tz="Asia/Seoul"),
    catchup=False,
    max_active_runs=1,
    tags=["capa", "t2", "daily", "etl", "eks"],
) as dag:
    run_daily_etl = KubernetesPodOperator(
        task_id="run_daily_etl",
        name="t2-daily-etl-pod",
        namespace=NAMESPACE,
        image=ECR_IMAGE,
        # data_interval_start(UTC) → KST 변환 → ISO 8601 문자열 전달
        # (Airflow의 data_interval_start는 이미 전날 실행 구간이므로 감산하지 않습니다)
        arguments=[
            "--mode",
            "daily",
            "--target-date",
            "{{ data_interval_start.in_timezone('Asia/Seoul').isoformat() }}",
        ],
        env_from=env_from,
        service_account_name=SA_NAME,
        get_logs=True,
        is_delete_operator_pod=True,  # 운영용: Pod 자동 삭제
        log_events_on_failure=True,
        startup_timeout_seconds=180,
    )

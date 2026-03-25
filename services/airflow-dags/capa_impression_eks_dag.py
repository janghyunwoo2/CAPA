"""
capa_impression_eks_dag.py
- EKS Airflow 환경 전용 Impression 지표 이상 탐지 DAG입니다.
- KubernetesPodOperator를 사용하며, ECR 이미지를 직접 참조합니다.
"""
from airflow import DAG
from airflow.providers.cncf.kubernetes.operators.pod import KubernetesPodOperator
from datetime import datetime, timedelta
from kubernetes.client import models as k8s

default_args = {
    "owner": "airflow",
    "depends_on_past": False,
    "retries": 1,
    "retry_delay": timedelta(minutes=1),
    "email_on_failure": False,
}

# [Prod 전용 환경 변수 및 설정]
ECR_IMAGE = "827913617635.dkr.ecr.ap-northeast-2.amazonaws.com/capa-impression-anomaly:latest"

with DAG(
    dag_id="capa_impression_anomaly_detector_eks",
    description="EKS 전용 5분 간격 Impression 이상 탐지 (Pod 형식)",
    schedule_interval="2-59/5 * * * *",
    start_date=datetime(2026, 3, 25),
    catchup=False,
    max_active_runs=1,
    default_args=default_args,
    tags=["eks", "pod", "impression", "anomaly"],
) as dag:

    run_impression_anomaly = KubernetesPodOperator(
        task_id="run_impression_anomaly_detector_eks",
        image=ECR_IMAGE,
        image_pull_policy="Always",
        cmds=["python", "main.py"],
        env_vars={
            "TZ": "Asia/Seoul",
            "AWS_DEFAULT_REGION": "ap-northeast-2",
        },
        name="capa-impression-anomaly-pod",
        namespace="airflow",
        is_delete_operator_pod=True,
        get_logs=True,
    )

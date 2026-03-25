"""
capa_click_eks_dag.py
- EKS Airflow 환경 전용 Click 지표 이상 탐지 DAG입니다.
- KubernetesPodOperator를 사용하며, ECR 이미지를 직접 참조합니다.
- [주의] EKS에서는 IAM Role(IRSA)을 사용하므로, 로컬의 .aws 마운트가 필요 없습니다.
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
ECR_IMAGE = "827913617635.dkr.ecr.ap-northeast-2.amazonaws.com/capa-click-anomaly:latest"

with DAG(
    dag_id="capa_click_anomaly_detector_eks",
    description="EKS 전용 5분 간격 Click 이상 탐지 (Pod 형식)",
    schedule_interval="2-59/5 * * * *",  # 매 시 2분부터 5분 간격
    start_date=datetime(2026, 3, 25),
    catchup=False,
    max_active_runs=1,
    default_args=default_args,
    tags=["eks", "pod", "click", "anomaly"],
) as dag:

    run_click_anomaly = KubernetesPodOperator(
        task_id="run_click_anomaly_detector_eks",
        # 1. ECR 이미지 
        image=ECR_IMAGE,
        image_pull_policy="Always",
        
        # 2. 실행 명령어 (main.py로 진입)
        cmds=["python", "main.py"],
        env_vars={
            "TZ": "Asia/Seoul",
            "AWS_DEFAULT_REGION": "ap-northeast-2",
            # 필요한 경우 추가 환경 변수 주입 (S3 버킷 등)
        },
        
        # 3. Pod 설정 정보
        name="capa-click-anomaly-pod",
        namespace="airflow",           # 상황에 따라 default 또는 전용 namespace 지정
        is_delete_operator_pod=True,   # 완료 후 Pod 삭제 (권장)
        get_logs=True,                 # 에어플로우에서 파드 로그 확인 가능
        
        # 4. 리소스 및 보안 설정 (필요 시 주석 해제)
        # config_file="/home/airflow/.kube/config", 
        # in_cluster=True,              # EKS 내부라면 기본 True임
    )

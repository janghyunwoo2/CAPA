from airflow import DAG
from airflow.providers.cncf.kubernetes.operators.pod import KubernetesPodOperator
from airflow.utils.dates import days_ago
from kubernetes.client import models as k8s
from datetime import datetime

# 설정 변수
S3_BUCKET = "capa-data-lake-827913617635"
DATABASE = "capa_db"
ATHENA_OUTPUT = f"s3://{S3_BUCKET}/athena-results/"
REGION = "ap-northeast-2"

default_args = {
    "owner": "capa",
    "start_date": days_ago(1),
}

# 오늘 날짜 변수 생성
now = datetime.now()
date_str = now.strftime("%Y/%m/%d")
year, month, day = now.strftime("%Y"), now.strftime("%m"), now.strftime("%d")

# Athena 쿼리문
query = f"""
SELECT 
    campaign_id,
    COUNT(CASE WHEN event_type = 'impression' THEN 1 END) as impressions,
    COUNT(CASE WHEN event_type = 'click' THEN 1 END) as clicks,
    COUNT(CASE WHEN event_type = 'conversion' THEN 1 END) as conversions
FROM ad_events_raw
WHERE year = '{year}' AND month = '{month}' AND day = '{day}'
GROUP BY campaign_id
"""

with DAG(
    "ad_performance_k8s_pod",
    default_args=default_args,
    schedule_interval="0 2 * * *",
    catchup=False,
    tags=["capa", "k8s", "analytics"],
) as dag:
    # 1. Athena 집계 태스크 (KubernetesPodOperator)
    # 별도의 전용 분석 컨테이너 이미지가 있다면 이를 사용합니다.
    # 여기서는 예시를 위해 python 기본 이미지에서 boto3를 이용해 쿼리를 날리는 파이썬 스크립트를 인라인으로 실행합니다.
    agg_task = KubernetesPodOperator(
        task_id="athena_aggregation_pod",
        name="athena-agg-pod",
        namespace="airflow",
        image="python:3.11-slim",  # 작업에 최적화된 독립 이미지 사용 가능
        cmds=["python", "-c"],
        arguments=[
            f"""
import boto3
import time
client = boto3.client('athena', region_name='{REGION}')
response = client.start_query_execution(
    QueryString=\"\"\"{query}\"\"\",
    QueryExecutionContext={{'Database': '{DATABASE}'}},
    ResultConfiguration={{'OutputLocation': '{ATHENA_OUTPUT}'}}
)
qid = response['QueryExecutionId']
print(f"Started query: {{qid}}")
while True:
    status = client.get_query_execution(QueryExecutionId=qid)
    state = status['QueryExecution']['Status']['State']
    if state in ['SUCCEEDED', 'FAILED', 'CANCELLED']: break
    time.sleep(2)
if state != 'SUCCEEDED': raise Exception(f"Query failed: {{state}}")
print("Aggregation Success")
        """
        ],
        service_account_name="airflow-scheduler",  # IRSA 권한 상속
        get_logs=True,
        is_delete_operator_pod=True,  # 작업 완료 후 파드 자동 삭제
    )

    # 2. Report Generator 트리거 태스크 (가벼운 작업이므로 기존 연동 유지 또는 Pod화 가능)
    # 여기서는 구조적 통일성을 위해 이것도 Pod로 실행하는 예시입니다.
    report_task = KubernetesPodOperator(
        task_id="trigger_report_pod",
        name="report-trigger-pod",
        namespace="airflow",
        image="curlimages/curl:latest",  # curl 전용 경량 이미지 사용
        cmds=["curl"],
        arguments=[
            "-X",
            "POST",
            "http://report-generator.report.svc.cluster.local:8000/generate",
        ],
        is_delete_operator_pod=True,
    )

    agg_task >> report_task

"""
DAG(수동 실행 전용): ad_daily_summary_test
주기: 없음 (schedule=None)
역할: hourly_summary 24개 집계 + conversion 원천 로그 조인 (수동 1회 트리거용)
"""
import os
import sys
import pendulum
from airflow import DAG
from airflow.providers.cncf.kubernetes.operators.pod import KubernetesPodOperator
from airflow.providers.standard.operators.python import PythonOperator
from airflow.sensors.external_task import ExternalTaskSensor
from datetime import timedelta
import textwrap

# etl_summary_t2 패키지 경로 추가
ETL_PACKAGE_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'etl_summary_t2')
if ETL_PACKAGE_PATH not in sys.path:
    sys.path.insert(0, os.path.dirname(ETL_PACKAGE_PATH))

S3_BUCKET = "capa-data-lake-827913617635"
DATABASE = "capa_ad_logs"
ATHENA_OUTPUT = f"s3://{S3_BUCKET}/athena-results/"
REGION = "ap-northeast-2"
# ✅ 테이블명과 경로 일치 (summary 폴더 제거)
HOURLY_SUMMARY_PATH = f"s3://{S3_BUCKET}/ad_combined_log"
DAILY_SUMMARY_PATH = f"s3://{S3_BUCKET}/ad_combined_log_summary"

default_args = {
    "owner": "capa",
    "depends_on_past": False,
    "retries": 2,
    "retry_delay": timedelta(minutes=10),
    "execution_timeout": timedelta(minutes=60),
}

ETL_RUNNER_SCRIPT = textwrap.dedent("""
import sys
import os
sys.path.insert(0, '/opt/airflow/services/data_pipeline_t2')

from datetime import datetime, date
from dateutil.parser import parse
from etl_summary_t2.daily_etl import DailyETL
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 환경변수에서 날짜 가져오기
TARGET_DATE = os.environ['TARGET_DATE']  # 2026-03-12 형식
target_date = datetime.strptime(TARGET_DATE, '%Y-%m-%d').date()

logger.info(f"Running DailyETL for: {target_date}")

# DailyETL 실행
etl = DailyETL(target_date=target_date)
etl.run()

logger.info("DailyETL completed successfully")
""")

PARTITION_REPAIR_SCRIPT = textwrap.dedent("""
import boto3
import time
import os

REGION = os.environ.get('AWS_REGION', 'ap-northeast-2')
DATABASE = os.environ['DATABASE']
ATHENA_OUTPUT = os.environ['ATHENA_OUTPUT']
TABLE = os.environ['TABLE']

client = boto3.client('athena', region_name=REGION)

sql = f"MSCK REPAIR TABLE {DATABASE}.{TABLE}"
print(f"[Athena] Registering partitions: {sql}")
response = client.start_query_execution(
    QueryString=sql,
    QueryExecutionContext={'Database': DATABASE},
    ResultConfiguration={'OutputLocation': ATHENA_OUTPUT}
)
qid = response['QueryExecutionId']
while True:
    status = client.get_query_execution(QueryExecutionId=qid)
    state = status['QueryExecution']['Status']['State']
    if state in ['SUCCEEDED', 'FAILED', 'CANCELLED']:
        break
    time.sleep(3)

if state != 'SUCCEEDED':
    reason = status['QueryExecution']['Status'].get('StateChangeReason', 'Unknown')
    raise Exception(f"Partition repair {state}: {reason}")

print(f"[DONE] Partition repair completed for {DATABASE}.{TABLE}")
""")

def _use_kpo() -> bool:
    val = os.getenv("USE_KPO")
    if val is not None:
        return val.lower() in ("1", "true", "yes")
    return bool(os.getenv("KUBERNETES_SERVICE_HOST") and os.getenv("KUBERNETES_PORT"))

USE_KPO = _use_kpo()

def _run_daily_etl(**context):
    """etl_summary_t2의 DailyETL 실행"""
    from etl_summary_t2.daily_etl import DailyETL
    from datetime import datetime
    import logging
    
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger(__name__)
    
    # context에서 데이터 추출 (UTC)
    dt_utc = context.get('data_interval_end')
    if not dt_utc:
        raise ValueError("data_interval_end not found in context")
    
    # UTC → KST 변환 후 전날 날짜 계산 (데일리는 전날 데이터 처리)
    dt_kst = pendulum.instance(dt_utc).in_timezone('Asia/Seoul')
    target_date = dt_kst.subtract(days=1).date()
    
    logger.info(f"Running DailyETL for: {target_date}")
    
    # DailyETL 실행
    etl = DailyETL(target_date=target_date)
    etl.run()
    
    logger.info("DailyETL completed successfully")

def _run_athena_queries(database: str, output: str, region: str, queries: str, **_):
    import boto3, time
    client = boto3.client('athena', region_name=region)
    def run(sql: str):
        resp = client.start_query_execution(
            QueryString=sql,
            QueryExecutionContext={'Database': database},
            ResultConfiguration={'OutputLocation': output},
        )
        qid = resp['QueryExecutionId']
        while True:
            st = client.get_query_execution(QueryExecutionId=qid)['QueryExecution']['Status']['State']
            if st in ['SUCCEEDED','FAILED','CANCELLED']:
                break
            time.sleep(3)
        if st != 'SUCCEEDED':
            raise RuntimeError(f"Athena query {st}")
    for i, q in enumerate((queries or "").split('|||')):
        q = (q or '').strip()
        if q:
            print(f"[Athena] Step {i+1}")
            run(q)

def _repair_partitions(database: str, output: str, region: str, table: str, **_):
    import boto3, time
    client = boto3.client('athena', region_name=region)
    sql = f"MSCK REPAIR TABLE {database}.{table}"
    resp = client.start_query_execution(
        QueryString=sql,
        QueryExecutionContext={'Database': database},
        ResultConfiguration={'OutputLocation': output},
    )
    qid = resp['QueryExecutionId']
    while True:
        st = client.get_query_execution(QueryExecutionId=qid)['QueryExecution']['Status']['State']
        if st in ['SUCCEEDED','FAILED','CANCELLED']:
            break
        time.sleep(3)
    if st != 'SUCCEEDED':
        raise RuntimeError(f"Partition repair {st}")

with DAG(
    dag_id="04_ad_daily_summary_test",
    default_args=default_args,
    description="수동 실행: hourly_summary 집계 + conversion 조인하여 daily summary 생성",
    schedule=None,  # 수동 트리거 전용
    start_date=pendulum.datetime(2026, 2, 13, tz=pendulum.timezone("Asia/Seoul")),
    catchup=False,
    max_active_runs=1,
    tags=["capa", "daily", "ad", "etl", "test"],
) as dag:

    wait_for_hourly = ExternalTaskSensor(
        task_id="wait_for_hourly_summary",
        external_dag_id="03_ad_hourly_summary_test",
        external_task_id="register_partition",
        execution_delta=timedelta(hours=3),
        timeout=3600,
        poke_interval=120,
        mode="reschedule",
    )

    if USE_KPO:
        create_daily_summary = KubernetesPodOperator(
            task_id="create_daily_summary",
            name="daily-summary-etl",
            namespace="airflow",
            image="apache/airflow:3.1.7",  # ✅ etl_summary_t2 패키지가 포함된 커스텀 이미지 사용 권장
            cmds=["python", "-c"],
            arguments=[ETL_RUNNER_SCRIPT],
            env_vars={
                "AWS_REGION": REGION,
                "AWS_ACCESS_KEY_ID": "{{ var.value.aws_access_key_id }}",
                "AWS_SECRET_ACCESS_KEY": "{{ var.value.aws_secret_access_key }}",
                # 전날 날짜를 TARGET_DATE로 전달
                "TARGET_DATE": "{{ (data_interval_end - macros.timedelta(days=1)).strftime('%Y-%m-%d') }}",
            },
            service_account_name="airflow-scheduler",
            get_logs=True,
            is_delete_operator_pod=True,
            # etl_summary_t2 패키지를 포함하는 볼륨 마운트 (옵션)
            volumes=[
                {
                    "name": "etl-code",
                    "hostPath": {
                        "path": "/opt/airflow/services/data_pipeline_t2",
                        "type": "Directory"
                    }
                }
            ],
            volume_mounts=[
                {
                    "name": "etl-code", 
                    "mountPath": "/opt/airflow/services/data_pipeline_t2",
                    "readOnly": True
                }
            ],
        )

        register_partition = KubernetesPodOperator(
            task_id="register_partition",
            name="daily-register-partition",
            namespace="airflow",
            image="apache/airflow:2.9.3-python3.14.2",
            cmds=["python", "-c"],
            arguments=[PARTITION_REPAIR_SCRIPT],
            env_vars={
                "AWS_REGION": REGION,
                "DATABASE": DATABASE,
                "ATHENA_OUTPUT": ATHENA_OUTPUT,
                "TABLE": "ad_daily_summary",
            },
            service_account_name="airflow-scheduler",
            get_logs=True,
            is_delete_operator_pod=True,
        )

        trigger_report = KubernetesPodOperator(
            task_id="trigger_report",
            name="daily-report-trigger",
            namespace="airflow",
            image="curlimages/curl:latest",
            cmds=["curl"],
            arguments=[
                "-X", "POST",
                "-H", "Content-Type: application/json",
                "-d", '{"date": "{{ data_interval_start.strftime("%Y-%m-%d") }}"}',
                "http://report-generator.report.svc.cluster.local:8000/generate",
            ],
            is_delete_operator_pod=True,
        )
    else:
        # etl_summary_t2 패키지를 직접 사용
        create_daily_summary = PythonOperator(
            task_id="create_daily_summary",
            python_callable=_run_daily_etl,
        )

        # ETL이 이미 파티션을 처리하므로 register_partition은 선택적
        register_partition = PythonOperator(
            task_id="register_partition",
            python_callable=_repair_partitions,
            op_kwargs={
                "region": REGION,
                "database": DATABASE,
                "output": ATHENA_OUTPUT,
                "table": "ad_combined_log_summary",
            },
        )

        # 로컬 환경에서는 내부 K8s 서비스 접근이 불가할 수 있으므로 HTTP 트리거는 선택적으로 구성하세요.
        def _maybe_trigger_report(**context):
            import os, json
            import urllib.request
            url = os.getenv("REPORT_URL")  # 예: http://localhost:8000/generate
            if not url:
                print("[INFO] REPORT_URL not set. Skipping report trigger.")
                return
            payload = {"date": context["data_interval_start"].strftime("%Y-%m-%d")}
            data = json.dumps(payload).encode("utf-8")
            req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"}, method="POST")
            with urllib.request.urlopen(req, timeout=30) as resp:  # noqa: S310
                print("[REPORT] status:", resp.status)

        trigger_report = PythonOperator(
            task_id="trigger_report",
            python_callable=_maybe_trigger_report,
        )

    wait_for_hourly >> create_daily_summary >> register_partition >> trigger_report

"""
DAG(수동 실행 전용): ad_hourly_summary_test
주기: 없음 (schedule=None)
역할: impressions + clicks → ad_combined_log 테이블 생성 (수동 1회 트리거용)
"""
import os
import sys
import pendulum
import pytz
from airflow import DAG
from airflow.providers.cncf.kubernetes.operators.pod import KubernetesPodOperator
from airflow.providers.standard.operators.python import PythonOperator
from datetime import timedelta, timezone
import textwrap

# etl_summary_t2 패키지 경로 추가
ETL_PACKAGE_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'etl_summary_t2')
if ETL_PACKAGE_PATH not in sys.path:
    sys.path.insert(0, os.path.dirname(ETL_PACKAGE_PATH))

S3_BUCKET = "capa-data-lake-827913617635"
DATABASE = "capa_ad_logs"
ATHENA_OUTPUT = f"s3://{S3_BUCKET}/athena-results/"
REGION = "ap-northeast-2"
# ✅ 테이블명과 경로 일치
HOURLY_SUMMARY_PATH = f"s3://{S3_BUCKET}/ad_combined_log"

default_args = {
    "owner": "capa",
    "depends_on_past": False,
    "retries": 2,
    "retry_delay": timedelta(minutes=5),
    "execution_timeout": timedelta(minutes=30),
}

ETL_RUNNER_SCRIPT = textwrap.dedent("""
import sys
import os
sys.path.insert(0, '/opt/airflow/services/data_pipeline_t2')

from datetime import datetime
from dateutil.parser import parse
import pendulum
from etl_summary_t2.hourly_etl import HourlyETL
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 환경변수에서 날짜 가져오기
TARGET_HOUR = os.environ['TARGET_HOUR']  # 2026-03-12 15:00:00+09:00 형식
dt_str = parse(TARGET_HOUR)
dt_kst = pendulum.instance(dt_str).in_timezone('Asia/Seoul')

logger.info(f"Running HourlyETL for: {dt_kst.strftime('%Y-%m-%d %H:00:00')} KST")

# HourlyETL 실행
etl = HourlyETL(target_hour=dt_kst)
etl.run()

logger.info("HourlyETL completed successfully")
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

print(f"[DONE] Partition repair completed")
""")

def _use_kpo() -> bool:
    val = os.getenv("USE_KPO")
    if val is not None:
        return val.lower() in ("1", "true", "yes")
    # 자동 감지: in-cluster 환경 변수 존재 시 KPO 사용
    return bool(os.getenv("KUBERNETES_SERVICE_HOST") and os.getenv("KUBERNETES_PORT"))

USE_KPO = _use_kpo()

def _run_hourly_etl(**context):
    """etl_summary_t2의 HourlyETL 실행"""
    from etl_summary_t2.hourly_etl import HourlyETL
    from datetime import datetime
    import logging
    
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger(__name__)
    
    # context에서 데이터 추출 (UTC)
    dt_utc = context.get('data_interval_end')
    if not dt_utc:
        raise ValueError("data_interval_end not found in context")
    
    # UTC → KST 변환
    dt_kst = pendulum.instance(dt_utc).in_timezone('Asia/Seoul')
    
    logger.info(f"Running HourlyETL for: {dt_kst.strftime('%Y-%m-%d %H:00:00')} KST")
    
    # HourlyETL 실행
    etl = HourlyETL(target_hour=dt_kst)
    etl.run()
    
    logger.info("HourlyETL completed successfully")

def _run_athena_query(
    database: str,
    output: str,
    region: str,
    tmp_table: str | None = None,
    summary_path: str | None = None,
    **context
):
    """
    Athena 쿼리 실행 함수 (context 기반 동적 쿼리 생성)
    
    Args:
        database: Athena 데이터베이스
        output: Athena 결과 저장 위치
        region: AWS 리전
        tmp_table: 임시 테이블명
        summary_path: S3 summary 경로
        **context: Airflow context (data_interval_end 포함)
    """
    import boto3, time
    from datetime import timezone, timedelta
    
    # context에서 데이터 추출 (UTC)
    dt_utc = context.get('data_interval_end')
    if not dt_utc:
        raise ValueError("data_interval_end not found in context")
    
    # ✅ UTC → KST 변환 (3가지 방법)
    # 방법 1: pendulum 사용
    dt = pendulum.instance(dt_utc).in_timezone('Asia/Seoul')
    
    # 방법 2: pytz 사용 (백업)
    # dt = dt_utc.astimezone(pytz.timezone('Asia/Seoul'))
    
    # 방법 3: datetime timedelta 사용 (백업)
    # dt = dt_utc.astimezone(timezone(timedelta(hours=9)))
    
    # 동적으로 SQL 쿼리 생성 (Jinja 템플릿 대신 f-string 사용)
    query = f"""
        CREATE TABLE {database}.{tmp_table}
        WITH (
            format = 'PARQUET',
            write_compression = 'ZSTD',
            external_location = '{summary_path}/year={dt.strftime("%Y")}/month={dt.strftime("%m")}/day={dt.strftime("%d")}/hour={dt.strftime("%H")}/'
        ) AS
        SELECT
            imp.campaign_id,
            imp.device_type,
            '{dt.strftime("%Y-%m-%d-%H")}' AS dt,
            COUNT(DISTINCT imp.impression_id) AS impressions,
            COUNT(DISTINCT clk.click_id) AS clicks,
            CASE
                WHEN COUNT(DISTINCT imp.impression_id) > 0
                THEN CAST(COUNT(DISTINCT clk.click_id) AS DOUBLE)
                     / CAST(COUNT(DISTINCT imp.impression_id) AS DOUBLE) * 100
                ELSE 0.0
            END AS ctr
        FROM {database}.impressions AS imp
        LEFT JOIN {database}.clicks AS clk
            ON imp.impression_id = clk.impression_id
            AND clk.year = '{dt.strftime("%Y")}'
            AND clk.month = '{dt.strftime("%m")}'
            AND clk.day = '{dt.strftime("%d")}'
            AND clk.hour = '{dt.strftime("%H")}'
        WHERE imp.year = '{dt.strftime("%Y")}'
            AND imp.month = '{dt.strftime("%m")}'
            AND imp.day = '{dt.strftime("%d")}'
            AND imp.hour = '{dt.strftime("%H")}'
        GROUP BY imp.campaign_id, imp.device_type
    """
    
    client = boto3.client('athena', region_name=region)

    def run(sql: str, desc: str = ""):
        print(f"[Athena] {desc}")
        print(f"[SQL] {sql[:500]}")
        resp = client.start_query_execution(
            QueryString=sql,
            QueryExecutionContext={'Database': database},
            ResultConfiguration={'OutputLocation': output},
        )
        qid = resp['QueryExecutionId']
        while True:
            status = client.get_query_execution(QueryExecutionId=qid)
            st = status['QueryExecution']['Status']['State']
            if st in ['SUCCEEDED','FAILED','CANCELLED']:
                break
            time.sleep(3)
        if st != 'SUCCEEDED':
            reason = status['QueryExecution']['Status'].get('StateChangeReason', 'Unknown')
            print(f"[Athena] FAILED - Reason: {reason}")
            raise RuntimeError(f"Athena query {st}: {reason}")

    if tmp_table:
        try:
            run(f"DROP TABLE IF EXISTS {database}.{tmp_table}", "Drop tmp table")
        except Exception as e:  # noqa: BLE001
            print(f"[WARN] Drop tmp table: {e}")
    run(query, "Main query execution")
    if tmp_table:
        try:
            run(f"DROP TABLE IF EXISTS {database}.{tmp_table}", "Cleanup tmp table")
        except Exception as e:  # noqa: BLE001
            print(f"[WARN] Cleanup: {e}")

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
    dag_id="03_ad_hourly_summary_test",
    default_args=default_args,
    description="수동 실행: impression+click 조인하여 hourly summary 생성",
    schedule=None,  # 수동 트리거 전용
    start_date=pendulum.datetime(2026, 2, 13, tz=pendulum.timezone("Asia/Seoul")),
    # ✅ timezone 파라미터는 Airflow 3.1.7에서 미지원 (docker-compose + airflow.cfg로 처리)
    catchup=False,
    max_active_runs=1,
    tags=["capa", "hourly", "ad", "etl", "test"],
) as dag:
    if USE_KPO:
        create_hourly_summary = KubernetesPodOperator(
            task_id="create_hourly_summary",
            name="hourly-summary-etl",
            namespace="airflow",
            image="apache/airflow:3.1.7",  # ✅ etl_summary_t2 패키지가 포함된 커스텀 이미지 사용 권장
            cmds=["python", "-c"],
            arguments=[ETL_RUNNER_SCRIPT],
            env_vars={
                "AWS_REGION": REGION,
                "AWS_ACCESS_KEY_ID": "{{ var.value.aws_access_key_id }}",
                "AWS_SECRET_ACCESS_KEY": "{{ var.value.aws_secret_access_key }}",
                # UTC → KST 변환 후 TARGET_HOUR 전달
                "TARGET_HOUR": "{{ pendulum.instance(data_interval_end).in_timezone('Asia/Seoul').strftime('%Y-%m-%d %H:00:00+09:00') }}",
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
            name="register-partition",
            namespace="airflow",
            image="apache/airflow:3.1.7",  # ✅ 이미지 버전 업그레이드
            cmds=["python", "-c"],
            arguments=[PARTITION_REPAIR_SCRIPT],
            env_vars={
                "AWS_REGION": REGION,
                "DATABASE": DATABASE,
                "ATHENA_OUTPUT": ATHENA_OUTPUT,
                "TABLE": "ad_combined_log",
            },
            service_account_name="airflow-scheduler",
            get_logs=True,
            is_delete_operator_pod=True,
        )
    else:
        # etl_summary_t2 패키지를 직접 사용
        create_hourly_summary = PythonOperator(
            task_id="create_hourly_summary",
            python_callable=_run_hourly_etl,
        )
        
        # ETL이 이미 파티션을 처리하므로 register_partition은 선택적
        register_partition = PythonOperator(
            task_id="register_partition",
            python_callable=_repair_partitions,
            op_kwargs={
                "region": REGION,
                "database": DATABASE,
                "output": ATHENA_OUTPUT,
                "table": "ad_combined_log",
            },
        )

    create_hourly_summary >> register_partition

"""
DAG(수동 실행 - 기간 설정): ad_hourly_summary_period
주기: 없음 (schedule=None)
역할: 지정된 기간의 impressions + clicks → ad_combined_log 테이블 생성
파라미터:
  - start_date: 시작일 (YYYY-MM-DD)
  - end_date: 종료일 (YYYY-MM-DD)
  - hours: 시간 범위 (기본값: 00-23)
"""
import os
import sys
import pendulum
from airflow import DAG
from airflow.providers.cncf.kubernetes.operators.pod import KubernetesPodOperator
from airflow.providers.standard.operators.python import PythonOperator
from airflow.models.param import Param
from datetime import timedelta, datetime
import textwrap

# etl_summary_t2 패키지 경로 추가
DATA_PIPELINE_PATH = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if DATA_PIPELINE_PATH not in sys.path:
    sys.path.insert(0, DATA_PIPELINE_PATH)

S3_BUCKET = "capa-data-lake-827913617635"
DATABASE = "capa_ad_logs"
ATHENA_OUTPUT = f"s3://{S3_BUCKET}/athena-results/"
REGION = "ap-northeast-2"
HOURLY_SUMMARY_PATH = f"s3://{S3_BUCKET}/ad_combined_log"

default_args = {
    "owner": "capa",
    "depends_on_past": False,
    "retries": 2,
    "retry_delay": timedelta(minutes=5),
    "execution_timeout": timedelta(hours=4),  # S3 업로드 지연 고려하여 4시간으로 증가
}

ETL_RUNNER_SCRIPT = textwrap.dedent("""
import sys
import os
sys.path.insert(0, '/opt/airflow/services/data_pipeline_t2')

from datetime import datetime, timedelta
import pendulum
from etl_summary_t2.hourly_etl import HourlyETL
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 환경변수에서 파라미터 가져오기
START_DATE = os.environ['START_DATE']  # 2026-03-01
END_DATE = os.environ['END_DATE']      # 2026-03-02
HOURS = os.environ.get('HOURS', '0-23')

# 시간 범위 파싱
if '-' in HOURS:
    start_hour, end_hour = map(int, HOURS.split('-'))
else:
    start_hour = end_hour = int(HOURS)

# 날짜 파싱
start = pendulum.parse(START_DATE).in_timezone('Asia/Seoul')
end = pendulum.parse(END_DATE).in_timezone('Asia/Seoul')

# 기간별 ETL 실행
current = start
while current <= end:
    for hour in range(start_hour, end_hour + 1):
        dt_kst = current.set(hour=hour, minute=0, second=0, microsecond=0)
        if dt_kst <= pendulum.now('Asia/Seoul'):
            logger.info(f"Running HourlyETL for: {dt_kst.strftime('%Y-%m-%d %H:00:00')} KST")
            try:
                etl = HourlyETL(target_hour=dt_kst)
                etl.run()
                logger.info(f"Completed: {dt_kst.strftime('%Y-%m-%d %H:00:00')}")
            except Exception as e:
                logger.error(f"Failed for {dt_kst}: {str(e)}")
                # continue to next hour
    current = current.add(days=1)

logger.info("Period HourlyETL completed successfully")
""")

def _use_kpo() -> bool:
    val = os.getenv("USE_KPO")
    if val is not None:
        return val.lower() in ("1", "true", "yes")
    return bool(os.getenv("KUBERNETES_SERVICE_HOST") and os.getenv("KUBERNETES_PORT"))

USE_KPO = _use_kpo()

def _run_hourly_etl_period(**context):
    """지정된 기간의 HourlyETL 실행"""
    import sys
    import os
    
    # 함수 내부에서도 경로 추가 (Airflow 실행 환경에서 필요)
    data_pipeline_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if data_pipeline_path not in sys.path:
        sys.path.insert(0, data_pipeline_path)
    
    from etl_summary_t2.hourly_etl import HourlyETL
    import pendulum
    import logging
    
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger(__name__)
    
    # 파라미터 추출
    params = context['params']
    start_date = params.get('start_date')
    end_date = params.get('end_date')
    hours = params.get('hours', '0-23')
    
    # 시간 범위 파싱
    if '-' in hours:
        start_hour, end_hour = map(int, hours.split('-'))
    else:
        start_hour = end_hour = int(hours)
    
    # 날짜 파싱
    start = pendulum.parse(start_date).in_timezone('Asia/Seoul')
    end = pendulum.parse(end_date).in_timezone('Asia/Seoul')
    
    logger.info(f"Processing period: {start_date} to {end_date}, hours: {hours}")
    
    # 기간별 ETL 실행
    success_count = 0
    fail_count = 0
    current = start
    
    while current <= end:
        for hour in range(start_hour, end_hour + 1):
            dt_kst = current.set(hour=hour, minute=0, second=0, microsecond=0)
            # 미래 시간은 스킵
            if dt_kst <= pendulum.now('Asia/Seoul'):
                logger.info(f"Running HourlyETL for: {dt_kst.strftime('%Y-%m-%d %H:00:00')} KST")
                try:
                    etl = HourlyETL(target_hour=dt_kst)
                    etl.run()
                    success_count += 1
                    logger.info(f"✅ Completed: {dt_kst.strftime('%Y-%m-%d %H:00:00')}")
                except Exception as e:
                    fail_count += 1
                    logger.error(f"❌ Failed for {dt_kst}: {str(e)}")
                    # continue to next hour
        current = current.add(days=1)
    
    logger.info(f"Period ETL completed - Success: {success_count}, Failed: {fail_count}")
    if fail_count > 0:
        logger.warning(f"Some ETL jobs failed. Check logs for details.")

def _repair_partitions_batch(database: str, output: str, region: str, table: str, **context):
    """배치로 파티션 복구"""
    import boto3, time
    
    client = boto3.client('athena', region_name=region)
    
    # 파라미터에서 날짜 범위 추출
    params = context.get('params', {})
    start_date = params.get('start_date')
    end_date = params.get('end_date')
    
    # 전체 파티션 복구
    sql = f"MSCK REPAIR TABLE {database}.{table}"
    print(f"[Athena] Repairing all partitions for period {start_date} to {end_date}")
    
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
        raise RuntimeError(f"Partition repair {st}: {reason}")
    
    print(f"[DONE] Partition repair completed for {database}.{table}")

with DAG(
    dag_id="05_ad_hourly_summary_period",
    default_args=default_args,
    description="기간 지정 수동 실행: impression+click 조인하여 hourly summary 생성",
    schedule=None,  # 수동 트리거 전용
    start_date=pendulum.datetime(2026, 2, 13, tz=pendulum.timezone("Asia/Seoul")),
    catchup=False,
    max_active_runs=1,
    tags=["capa", "hourly", "ad", "etl", "period", "manual"],
    params={
        "start_date": Param(
            default=(pendulum.now() - timedelta(days=1)).strftime("%Y-%m-%d"),
            type='string',
            description="시작일 (YYYY-MM-DD 형식)",
            pattern=r"^\d{4}-\d{2}-\d{2}$"
        ),
        "end_date": Param(
            default=pendulum.now().strftime("%Y-%m-%d"),
            type='string',
            description="종료일 (YYYY-MM-DD 형식)",
            pattern=r"^\d{4}-\d{2}-\d{2}$"
        ),
        "hours": Param(
            default="0-23",
            type='string',
            description="처리할 시간 범위 (예: 0-23, 9-18, 12)",
            pattern=r"^(\d{1,2}|\d{1,2}-\d{1,2})$"
        ),
    }
) as dag:
    
    if USE_KPO:
        create_hourly_summary = KubernetesPodOperator(
            task_id="create_hourly_summary_period",
            name="hourly-summary-period-etl",
            namespace="airflow",
            image="apache/airflow:3.1.7",
            cmds=["python", "-c"],
            arguments=[ETL_RUNNER_SCRIPT],
            env_vars={
                "AWS_REGION": REGION,
                "AWS_ACCESS_KEY_ID": "{{ var.value.aws_access_key_id }}",
                "AWS_SECRET_ACCESS_KEY": "{{ var.value.aws_secret_access_key }}",
                "START_DATE": "{{ params.start_date }}",
                "END_DATE": "{{ params.end_date }}",
                "HOURS": "{{ params.hours }}",
            },
            service_account_name="airflow-scheduler",
            get_logs=True,
            is_delete_operator_pod=True,
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
    else:
        create_hourly_summary = PythonOperator(
            task_id="create_hourly_summary_period",
            python_callable=_run_hourly_etl_period,
        )
    
    register_partitions = PythonOperator(
        task_id="register_partitions_batch",
        python_callable=_repair_partitions_batch,
        op_kwargs={
            "region": REGION,
            "database": DATABASE,
            "output": ATHENA_OUTPUT,
            "table": "ad_combined_log",
        },
    )
    
    create_hourly_summary >> register_partitions
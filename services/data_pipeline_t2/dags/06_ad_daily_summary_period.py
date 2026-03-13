"""
DAG(수동 실행 - 기간 설정): ad_daily_summary_period
주기: 없음 (schedule=None)
역할: 지정된 기간의 hourly_summary 24개 집계 + conversion 원천 로그 조인
파라미터:
  - start_date: 시작일 (YYYY-MM-DD)
  - end_date: 종료일 (YYYY-MM-DD)
  - skip_missing_hours: 일부 시간대 데이터가 없어도 진행 (기본값: True)
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
DAILY_SUMMARY_PATH = f"s3://{S3_BUCKET}/ad_combined_log_summary"

default_args = {
    "owner": "capa",
    "depends_on_past": False,
    "retries": 2,
    "retry_delay": timedelta(minutes=10),
    "execution_timeout": timedelta(hours=4),  # 여러 날짜 처리 고려하여 4시간으로 증가
}

ETL_RUNNER_SCRIPT = textwrap.dedent("""
import sys
import os
sys.path.insert(0, '/opt/airflow/services/data_pipeline_t2')

from datetime import datetime, date, timedelta
import pendulum
from etl_summary_t2.daily_etl import DailyETL
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 환경변수에서 파라미터 가져오기
START_DATE = os.environ['START_DATE']  # 2026-03-01
END_DATE = os.environ['END_DATE']      # 2026-03-05
SKIP_MISSING = os.environ.get('SKIP_MISSING_HOURS', 'true').lower() == 'true'

# 날짜 파싱
start_date = datetime.strptime(START_DATE, '%Y-%m-%d')
end_date = datetime.strptime(END_DATE, '%Y-%m-%d')

logger.info(f"Processing daily summaries from {start_date} to {end_date}")
logger.info(f"Skip missing hours: {SKIP_MISSING}")

# 기간별 Daily ETL 실행
current_date = start_date
success_dates = []
failed_dates = []

while current_date <= end_date:
    # 오늘 날짜는 스킵 (일별 집계는 완료된 날짜만)
    if current_date.date() >= datetime.now().date():
        logger.info(f"Skipping future/today date: {current_date.date()}")
        current_date += timedelta(days=1)
        continue
        
    logger.info(f"Running DailyETL for: {current_date.date()}")
    try:
        etl = DailyETL(target_date=current_date)
        # skip_missing_hours 옵션 전달 (ETL 클래스가 지원하는 경우)
        if hasattr(etl, 'skip_missing_hours'):
            etl.skip_missing_hours = SKIP_MISSING
        etl.run()
        success_dates.append(str(current_date.date()))
        logger.info(f"✅ Completed: {current_date.date()}")
    except Exception as e:
        failed_dates.append(str(current_date.date()))
        logger.error(f"❌ Failed for {current_date.date()}: {str(e)}")
        if not SKIP_MISSING:
            raise  # skip_missing이 False면 실패 시 중단
    
    current_date += timedelta(days=1)

logger.info(f"Period DailyETL completed - Success: {len(success_dates)}, Failed: {len(failed_dates)}")
if success_dates:
    logger.info(f"Successful dates: {', '.join(success_dates)}")
if failed_dates:
    logger.warning(f"Failed dates: {', '.join(failed_dates)}")
""")

BATCH_REPORT_SCRIPT = textwrap.dedent("""
import json
import urllib.request
from datetime import datetime, timedelta

# 환경변수에서 파라미터 가져오기
START_DATE = os.environ['START_DATE']
END_DATE = os.environ['END_DATE']
REPORT_URL = os.environ.get('REPORT_URL', 'http://report-generator.report.svc.cluster.local:8000/generate')

# 날짜 범위의 각 날짜에 대해 리포트 생성 요청
start = datetime.strptime(START_DATE, '%Y-%m-%d')
end = datetime.strptime(END_DATE, '%Y-%m-%d')
current = start

print(f"Triggering reports for period: {START_DATE} to {END_DATE}")

while current <= end:
    try:
        payload = {"date": current.strftime("%Y-%m-%d")}
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(REPORT_URL, data=data, 
                                   headers={"Content-Type": "application/json"}, 
                                   method="POST")
        with urllib.request.urlopen(req, timeout=30) as resp:
            print(f"[REPORT] {current.strftime('%Y-%m-%d')} - status: {resp.status}")
    except Exception as e:
        print(f"[ERROR] Failed to trigger report for {current.strftime('%Y-%m-%d')}: {e}")
    
    current += timedelta(days=1)

print("[DONE] Report triggers completed")
""")

def _use_kpo() -> bool:
    val = os.getenv("USE_KPO")
    if val is not None:
        return val.lower() in ("1", "true", "yes")
    return bool(os.getenv("KUBERNETES_SERVICE_HOST") and os.getenv("KUBERNETES_PORT"))

USE_KPO = _use_kpo()

def _run_daily_etl_period(**context):
    """지정된 기간의 DailyETL 실행"""
    import sys
    import os
    
    # 함수 내부에서도 경로 추가 (Airflow 실행 환경에서 필요)
    data_pipeline_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if data_pipeline_path not in sys.path:
        sys.path.insert(0, data_pipeline_path)
    
    from etl_summary_t2.daily_etl import DailyETL
    from datetime import datetime, date, timedelta
    import logging
    
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger(__name__)
    
    # 파라미터 추출
    params = context['params']
    start_date = datetime.strptime(params.get('start_date'), '%Y-%m-%d')
    end_date = datetime.strptime(params.get('end_date'), '%Y-%m-%d')
    skip_missing = params.get('skip_missing_hours', True)
    
    logger.info(f"Processing daily summaries from {start_date} to {end_date}")
    logger.info(f"Skip missing hours: {skip_missing}")
    
    # 기간별 Daily ETL 실행
    current_date = start_date
    success_dates = []
    failed_dates = []
    
    while current_date <= end_date:
        # 오늘 날짜는 스킵 (일별 집계는 완료된 날짜만)
        if current_date.date() >= datetime.now().date():
            logger.info(f"Skipping future/today date: {current_date.date()}")
            current_date += timedelta(days=1)
            continue
            
        logger.info(f"Running DailyETL for: {current_date.date()}")
        try:
            etl = DailyETL(target_date=current_date)
            # skip_missing_hours 옵션 전달 (ETL 클래스가 지원하는 경우)
            if hasattr(etl, 'skip_missing_hours'):
                etl.skip_missing_hours = skip_missing
            etl.run()
            success_dates.append(str(current_date.date()))
            logger.info(f"✅ Completed: {current_date.date()}")
        except Exception as e:
            failed_dates.append(str(current_date.date()))
            logger.error(f"❌ Failed for {current_date.date()}: {str(e)}")
            if not skip_missing:
                raise  # skip_missing이 False면 실패 시 중단
        
        current_date += timedelta(days=1)
    
    logger.info(f"Period DailyETL completed - Success: {len(success_dates)}, Failed: {len(failed_dates)}")
    if failed_dates and not skip_missing:
        raise Exception(f"Some dates failed: {failed_dates}")

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

def _trigger_reports_batch(**context):
    """기간별 리포트 생성 트리거"""
    import os, json
    import urllib.request
    from datetime import datetime, timedelta
    
    params = context['params']
    start = datetime.strptime(params.get('start_date'), '%Y-%m-%d')
    end = datetime.strptime(params.get('end_date'), '%Y-%m-%d')
    
    url = os.getenv("REPORT_URL", "http://report-generator.report.svc.cluster.local:8000/generate")
    if "localhost" in url or not url:
        print("[INFO] Skipping report triggers in local environment")
        return
        
    current = start
    results = []
    
    while current <= end:
        try:
            payload = {"date": current.strftime("%Y-%m-%d")}
            data = json.dumps(payload).encode("utf-8")
            req = urllib.request.Request(url, data=data,
                                       headers={"Content-Type": "application/json"},
                                       method="POST")
            with urllib.request.urlopen(req, timeout=30) as resp:
                results.append(f"{current.strftime('%Y-%m-%d')}: {resp.status}")
        except Exception as e:
            results.append(f"{current.strftime('%Y-%m-%d')}: ERROR - {str(e)}")
        
        current += timedelta(days=1)
    
    print(f"[REPORT] Batch trigger results:\n" + "\n".join(results))

with DAG(
    dag_id="06_ad_daily_summary_period",
    default_args=default_args,
    description="기간 지정 수동 실행: hourly_summary 집계 + conversion 조인하여 daily summary 생성",
    schedule=None,  # 수동 트리거 전용
    start_date=pendulum.datetime(2026, 2, 13, tz=pendulum.timezone("Asia/Seoul")),
    catchup=False,
    max_active_runs=1,
    tags=["capa", "daily", "ad", "etl", "period", "manual"],
    params={
        "start_date": Param(
            default=(pendulum.now() - timedelta(days=7)).strftime("%Y-%m-%d"),
            type='string',
            description="시작일 (YYYY-MM-DD 형식)",
            pattern=r"^\d{4}-\d{2}-\d{2}$"
        ),
        "end_date": Param(
            default=(pendulum.now() - timedelta(days=1)).strftime("%Y-%m-%d"),
            type='string',
            description="종료일 (YYYY-MM-DD 형식, 어제까지만 가능)",
            pattern=r"^\d{4}-\d{2}-\d{2}$"
        ),
        "skip_missing_hours": Param(
            default=True,
            type='boolean',
            description="일부 시간대 데이터가 없어도 진행할지 여부"
        ),
    }
) as dag:
    
    if USE_KPO:
        create_daily_summary = KubernetesPodOperator(
            task_id="create_daily_summary_period",
            name="daily-summary-period-etl",
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
                "SKIP_MISSING_HOURS": "{{ params.skip_missing_hours | string | lower }}",
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
        
        trigger_reports = KubernetesPodOperator(
            task_id="trigger_reports_batch",
            name="trigger-reports-batch",
            namespace="airflow",
            image="python:3.14-slim",
            cmds=["python", "-c"],
            arguments=[BATCH_REPORT_SCRIPT],
            env_vars={
                "START_DATE": "{{ params.start_date }}",
                "END_DATE": "{{ params.end_date }}",
            },
            service_account_name="airflow-scheduler",
            get_logs=True,
            is_delete_operator_pod=True,
        )
    else:
        create_daily_summary = PythonOperator(
            task_id="create_daily_summary_period",
            python_callable=_run_daily_etl_period,
        )
        
        trigger_reports = PythonOperator(
            task_id="trigger_reports_batch",
            python_callable=_trigger_reports_batch,
        )
    
    register_partitions = PythonOperator(
        task_id="register_partitions_batch",
        python_callable=_repair_partitions_batch,
        op_kwargs={
            "region": REGION,
            "database": DATABASE,
            "output": ATHENA_OUTPUT,
            "table": "ad_combined_log_summary",
        },
    )
    
    create_daily_summary >> register_partitions >> trigger_reports
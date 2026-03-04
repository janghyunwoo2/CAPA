"""
DAG(수동 실행 전용): ad_daily_summary_manual
주기: 없음 (schedule=None)
역할: hourly_summary 24개 집계 + conversion 원천 로그 조인 (수동 1회 트리거용)
"""
import os
import pendulum
from airflow import DAG
from airflow.providers.cncf.kubernetes.operators.pod import KubernetesPodOperator
from airflow.providers.standard.operators.python import PythonOperator
from airflow.sensors.external_task import ExternalTaskSensor
from datetime import timedelta
import textwrap

S3_BUCKET = "capa-data-lake-827913617635"
DATABASE = "ad_log"
ATHENA_OUTPUT = f"s3://{S3_BUCKET}/athena-results/"
REGION = "ap-northeast-2"
HOURLY_SUMMARY_PATH = f"s3://{S3_BUCKET}/summary/ad_hourly_summary"
DAILY_SUMMARY_PATH = f"s3://{S3_BUCKET}/summary/ad_daily_summary"

default_args = {
    "owner": "capa",
    "depends_on_past": False,
    "retries": 2,
    "retry_delay": timedelta(minutes=10),
    "execution_timeout": timedelta(minutes=60),
}

ATHENA_RUNNER_SCRIPT = textwrap.dedent("""
import boto3
import time
import os

REGION = os.environ.get('AWS_REGION', 'ap-northeast-2')
DATABASE = os.environ['DATABASE']
ATHENA_OUTPUT = os.environ['ATHENA_OUTPUT']
QUERIES = os.environ['QUERIES'].split('|||')

client = boto3.client('athena', region_name=REGION)

def run_query(sql, step_num=0):
    sql = sql.strip()
    if not sql:
        return
    print(f"\n{'='*60}")
    print(f"[Step {step_num}] Executing query...")
    print(f"[SQL] {sql[:500]}...")
    print(f"{'='*60}")

    response = client.start_query_execution(
        QueryString=sql,
        QueryExecutionContext={'Database': DATABASE},
        ResultConfiguration={'OutputLocation': ATHENA_OUTPUT}
    )
    qid = response['QueryExecutionId']
    print(f"[Athena] Query ID: {qid}")

    while True:
        status = client.get_query_execution(QueryExecutionId=qid)
        state = status['QueryExecution']['Status']['State']
        if state in ['SUCCEEDED', 'FAILED', 'CANCELLED']:
            break
        time.sleep(3)

    if state != 'SUCCEEDED':
        reason = status['QueryExecution']['Status'].get('StateChangeReason', 'Unknown')
        raise Exception(f"Query {state}: {reason}")

    stats = status['QueryExecution'].get('Statistics', {})
    scanned = stats.get('DataScannedInBytes', 0)
    runtime = stats.get('TotalExecutionTimeInMillis', 0)
    print(f"[Athena] SUCCESS - Scanned: {scanned / 1024 / 1024:.2f} MB, Time: {runtime}ms")
    return qid

for i, query in enumerate(QUERIES):
    run_query(query, i + 1)

print("\n[DONE] All queries completed successfully")
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
    dag_id="ad_daily_summary_manual",
    default_args=default_args,
    description="수동 실행: hourly_summary 집계 + conversion 조인하여 daily summary 생성",
    schedule=None,  # 수동 트리거 전용
    start_date=pendulum.datetime(2026, 2, 13, tz=pendulum.timezone("Asia/Seoul")),
    catchup=False,
    max_active_runs=1,
    tags=["capa", "daily", "ad", "etl", "manual"],
) as dag:

    wait_for_hourly = ExternalTaskSensor(
        task_id="wait_for_hourly_summary",
        external_dag_id="ad_hourly_summary",
        external_task_id="register_partition",
        execution_delta=timedelta(hours=3),
        timeout=3600,
        poke_interval=120,
        mode="reschedule",
    )

    if USE_KPO:
        create_daily_summary = KubernetesPodOperator(
            task_id="create_daily_summary",
            name="daily-summary-athena",
            namespace="airflow",
            image="apache/airflow:2.9.3-python3.12",
            cmds=["python", "-c"],
            arguments=[ATHENA_RUNNER_SCRIPT],
            env_vars={
                "AWS_REGION": REGION,
                "DATABASE": DATABASE,
                "ATHENA_OUTPUT": ATHENA_OUTPUT,
                "QUERIES": (
                    "DROP TABLE IF EXISTS {{ params.database }}.ad_daily_summary_tmp"
                    "|||"
                    "CREATE TABLE {{ params.database }}.ad_daily_summary_tmp WITH ( format = 'PARQUET', write_compression = 'ZSTD', "
                    "external_location = '{{ params.daily_path }}/ds={{ params.target_date }}/' ) AS "
                    "WITH hourly_agg AS ( SELECT campaign_id, device_type, SUM(impressions) AS impressions, SUM(clicks) AS clicks "
                    "FROM {{ params.database }}.ad_hourly_summary WHERE dt >= '{{ params.target_date }}-00' AND dt <= '{{ params.target_date }}-23' GROUP BY campaign_id, device_type ), "
                    "conversion_agg AS ( SELECT campaign_id, device_type, COUNT(DISTINCT event_id) AS conversions FROM {{ params.database }}.ad_events_raw "
                    "WHERE event_type = 'conversion' AND year='{{ params.target_date[:4] }}' AND month='{{ params.target_date[5:7] }}' AND day='{{ params.target_date[8:10] }}' GROUP BY campaign_id, device_type ) "
                    "SELECT h.campaign_id, h.device_type, '{{ params.target_date }}' AS ds, h.impressions, h.clicks, COALESCE(c.conversions, 0) AS conversions, "
                    "CASE WHEN h.impressions > 0 THEN CAST(h.clicks AS DOUBLE) / CAST(h.impressions AS DOUBLE) * 100 ELSE 0.0 END AS ctr, "
                    "CASE WHEN h.clicks > 0 THEN CAST(COALESCE(c.conversions, 0) AS DOUBLE) / CAST(h.clicks AS DOUBLE) * 100 ELSE 0.0 END AS cvr FROM hourly_agg h LEFT JOIN conversion_agg c ON h.campaign_id = c.campaign_id AND h.device_type = c.device_type"
                    "|||"
                    "DROP TABLE IF EXISTS {{ params.database }}.ad_daily_summary_tmp"
                ),
            },
            params={
                "database": DATABASE,
                "daily_path": DAILY_SUMMARY_PATH,
                "target_date": "{{ (data_interval_end - macros.timedelta(days=1)).strftime('%Y-%m-%d') }}",
            },
            service_account_name="airflow-scheduler",
            get_logs=True,
            is_delete_operator_pod=True,
        )

        register_partition = KubernetesPodOperator(
            task_id="register_partition",
            name="daily-register-partition",
            namespace="airflow",
            image="apache/airflow:2.9.3-python3.12",
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
        create_daily_summary = PythonOperator(
            task_id="create_daily_summary",
            python_callable=_run_athena_queries,
            op_kwargs={
                "region": REGION,
                "database": DATABASE,
                "output": ATHENA_OUTPUT,
                "queries": (
                    "DROP TABLE IF EXISTS {{ params.database }}.ad_daily_summary_tmp"
                    "|||"
                    "CREATE TABLE {{ params.database }}.ad_daily_summary_tmp WITH ( format = 'PARQUET', write_compression = 'ZSTD', "
                    "external_location = '{{ params.daily_path }}/ds={{ params.target_date }}/' ) AS "
                    "WITH hourly_agg AS ( SELECT campaign_id, device_type, SUM(impressions) AS impressions, SUM(clicks) AS clicks "
                    "FROM {{ params.database }}.ad_hourly_summary WHERE dt >= '{{ params.target_date }}-00' AND dt <= '{{ params.target_date }}-23' GROUP BY campaign_id, device_type ), "
                    "conversion_agg AS ( SELECT campaign_id, device_type, COUNT(DISTINCT event_id) AS conversions FROM {{ params.database }}.ad_events_raw "
                    "WHERE event_type = 'conversion' AND year='{{ params.target_date[:4] }}' AND month='{{ params.target_date[5:7] }}' AND day='{{ params.target_date[8:10] }}' GROUP BY campaign_id, device_type ) "
                    "SELECT h.campaign_id, h.device_type, '{{ params.target_date }}' AS ds, h.impressions, h.clicks, COALESCE(c.conversions, 0) AS conversions, "
                    "CASE WHEN h.impressions > 0 THEN CAST(h.clicks AS DOUBLE) / CAST(h.impressions AS DOUBLE) * 100 ELSE 0.0 END AS ctr, "
                    "CASE WHEN h.clicks > 0 THEN CAST(COALESCE(c.conversions, 0) AS DOUBLE) / CAST(h.clicks AS DOUBLE) * 100 ELSE 0.0 END AS cvr FROM hourly_agg h LEFT JOIN conversion_agg c ON h.campaign_id = c.campaign_id AND h.device_type = c.device_type"
                    "|||"
                    "DROP TABLE IF EXISTS {{ params.database }}.ad_daily_summary_tmp"
                ),
            },
            params={
                "database": DATABASE,
                "daily_path": DAILY_SUMMARY_PATH,
                "target_date": "{{ (data_interval_end - macros.timedelta(days=1)).strftime('%Y-%m-%d') }}",
            },
        )

        register_partition = PythonOperator(
            task_id="register_partition",
            python_callable=_repair_partitions,
            op_kwargs={
                "region": REGION,
                "database": DATABASE,
                "output": ATHENA_OUTPUT,
                "table": "ad_daily_summary",
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

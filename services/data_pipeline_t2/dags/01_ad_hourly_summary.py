"""
DAG: ad_hourly_summary
주기: 매시간
역할: ad_impression + ad_click → ad_hourly_summary 테이블 생성
      imp_event_id 기준으로 impression과 click을 조인하여
      시간 단위 CTR 집계 테이블을 생성한다.

데이터 흐름:
  S3 raw logs (Kinesis → Firehose → S3)
    → Athena CTAS (impression LEFT JOIN click)
    → S3 Parquet (ad_hourly_summary/)
    → Glue 파티션 등록
"""
import os
import pendulum
from airflow import DAG
from airflow.providers.cncf.kubernetes.operators.pod import KubernetesPodOperator
from airflow.providers.standard.operators.python import PythonOperator
from datetime import datetime, timedelta
import textwrap

# =============================================================================
# 설정
# =============================================================================
S3_BUCKET = "capa-data-lake-827913617635"
DATABASE = "ad_log"
ATHENA_OUTPUT = f"s3://{S3_BUCKET}/athena-results/"
REGION = "ap-northeast-2"

# 시간 파티션 포맷: dt=YYYY-MM-DD-HH
HOURLY_SUMMARY_PATH = f"s3://{S3_BUCKET}/summary/ad_hourly_summary"

default_args = {
    "owner": "capa",
    "depends_on_past": False,
    "retries": 2,
    "retry_delay": timedelta(minutes=5),
    "execution_timeout": timedelta(minutes=30),
}

def _use_kpo() -> bool:
    val = os.getenv("USE_KPO")
    if val is not None:
        return val.lower() in ("1", "true", "yes")
    return bool(os.getenv("KUBERNETES_SERVICE_HOST") and os.getenv("KUBERNETES_PORT"))

USE_KPO = _use_kpo()

def _run_athena_query(database: str, output: str, region: str, query: str, tmp_table: str | None = None, **_):
    import boto3, time
    client = boto3.client('athena', region_name=region)
    def run(sql: str, desc: str = ""):
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

def _check_raw_s3(bucket: str, **context):
    import boto3
    s3 = boto3.client('s3')
    dt = context["data_interval_start"]
    prefix = f"raw/year={dt.strftime('%Y')}/month={dt.strftime('%m')}/day={dt.strftime('%d')}/"
    paginator = s3.get_paginator('list_objects_v2')
    page_iter = paginator.paginate(Bucket=bucket, Prefix=prefix)
    printed = 0
    for page in page_iter:
        for obj in page.get('Contents', []):
            print(obj['Key'])
            printed += 1
            if printed >= 5:
                return

def build_hourly_summary_query(data_interval_start: str) -> str:
    """
    1시간 단위 impression + click 조인 summary 쿼리 생성.

    회의록 기준:
    - impression과 click을 imp_event_id로 조인
    - is_click 플래그 생성
    - campaign_id, creative_id 등으로 GROUP BY하여 CTR 계산
    - Parquet + zstd 압축으로 저장

    Args:
        data_interval_start: Airflow data_interval_start (ISO format)
                             예: 2026-02-13T06:00:00+00:00
    """
    # Airflow의 data_interval_start를 파티션 키로 변환
    # dt=2026-02-13-06 형식
    return textwrap.dedent(f"""
        -- Idempotency: 기존 파티션 데이터 덮어쓰기 (INSERT OVERWRITE 패턴)
        -- Step 1: CTAS로 임시 테이블 생성 후 S3 경로에 직접 적재
        CREATE TABLE {DATABASE}.ad_hourly_summary_tmp
        WITH (
            format = 'PARQUET',
            write_compression = 'ZSTD',
            external_location = '{HOURLY_SUMMARY_PATH}/dt={{{{ data_interval_start.strftime("%Y-%m-%d-%H") }}}}/'
        ) AS
        SELECT
            imp.campaign_id,
            imp.device_type,
            '{{{{ data_interval_start.strftime("%Y-%m-%d-%H") }}}}' AS dt,

            -- 집계 지표
            COUNT(DISTINCT imp.event_id)    AS impressions,
            COUNT(DISTINCT clk.event_id)    AS clicks,
            CASE
                WHEN COUNT(DISTINCT imp.event_id) > 0
                THEN CAST(COUNT(DISTINCT clk.event_id) AS DOUBLE)
                     / CAST(COUNT(DISTINCT imp.event_id) AS DOUBLE) * 100
                ELSE 0.0
            END AS ctr

        FROM {DATABASE}.ad_events_raw AS imp
        LEFT JOIN {DATABASE}.ad_events_raw AS clk
            ON  imp.campaign_id = clk.campaign_id
            AND imp.user_id     = clk.user_id
            AND clk.event_type  = 'click'
            AND clk.year  = '{{{{ data_interval_start.strftime("%Y") }}}}'
            AND clk.month = '{{{{ data_interval_start.strftime("%m") }}}}'
            AND clk.day   = '{{{{ data_interval_start.strftime("%d") }}}}'

        WHERE imp.event_type = 'impression'
          AND imp.year  = '{{{{ data_interval_start.strftime("%Y") }}}}'
          AND imp.month = '{{{{ data_interval_start.strftime("%m") }}}}'
          AND imp.day   = '{{{{ data_interval_start.strftime("%d") }}}}'
          -- 시간 필터: timestamp(bigint, ms) 기준 1시간 범위
          AND imp.timestamp >= {{{{ data_interval_start.int_timestamp * 1000 }}}}
          AND imp.timestamp <  {{{{ (data_interval_start + macros.timedelta(hours=1)).int_timestamp * 1000 }}}}

        GROUP BY imp.campaign_id, imp.device_type
    """)


# =============================================================================
# Athena 실행 Python 스크립트 (KubernetesPodOperator에서 실행)
# =============================================================================
ATHENA_RUNNER_SCRIPT = textwrap.dedent("""
import boto3
import time
import sys
import os

REGION = os.environ.get('AWS_REGION', 'ap-northeast-2')
DATABASE = os.environ['DATABASE']
ATHENA_OUTPUT = os.environ['ATHENA_OUTPUT']
QUERY = os.environ['QUERY']
TMP_TABLE = os.environ.get('TMP_TABLE', '')

client = boto3.client('athena', region_name=REGION)

def run_query(sql, description=""):
    print(f"[Athena] {description}")
    print(f"[SQL] {sql[:500]}...")
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
    print(f"[Athena] SUCCESS - Scanned: {scanned / 1024 / 1024:.2f} MB")
    return qid

# 1. 기존 임시 테이블 삭제 (idempotency)
if TMP_TABLE:
    try:
        run_query(f"DROP TABLE IF EXISTS {DATABASE}.{TMP_TABLE}", "Drop tmp table")
    except Exception as e:
        print(f"[WARN] Drop tmp table failed (may not exist): {e}")

# 2. 메인 쿼리 실행
run_query(QUERY, "Main query execution")

# 3. 임시 테이블 삭제 (Glue 카탈로그 정리)
if TMP_TABLE:
    try:
        run_query(f"DROP TABLE IF EXISTS {DATABASE}.{TMP_TABLE}", "Cleanup tmp table")
    except Exception as e:
        print(f"[WARN] Cleanup failed: {e}")

print("[DONE] Hourly summary completed successfully")
""")


# =============================================================================
# 파티션 등록 스크립트
# =============================================================================
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


# =============================================================================
# DAG 정의
# =============================================================================
with DAG(
    dag_id="01_ad_hourly_summary",
    default_args=default_args,
    description="매시간 impression+click 조인하여 hourly summary 테이블 생성",
    schedule="10 * * * *",  # 10분 버퍼 후 실행 (KST)
    start_date=pendulum.datetime(2026, 2, 13, tz=pendulum.timezone("Asia/Seoul")),
    catchup=False,
    max_active_runs=1,
    tags=["capa", "hourly", "ad", "etl"],
) as dag:

    # Task 1: S3 raw 데이터 존재 확인 (KPO 또는 로컬 폴백)
    if USE_KPO:
        check_data = KubernetesPodOperator(
            task_id="check_raw_data",
            name="check-raw-data",
            namespace="airflow",
            image="amazon/aws-cli:latest",
            cmds=["sh", "-c"],
            arguments=[
                "aws s3 ls s3://{{ params.bucket }}/raw/"
                "year={{ data_interval_start.strftime('%Y') }}/"
                "month={{ data_interval_start.strftime('%m') }}/"
                "day={{ data_interval_start.strftime('%d') }}/ "
                "--recursive | head -5 && echo 'Data exists'"
            ],
            params={"bucket": S3_BUCKET},
            service_account_name="airflow-scheduler",
            get_logs=True,
            is_delete_operator_pod=True,
        )
    else:
        check_data = PythonOperator(
            task_id="check_raw_data",
            python_callable=_check_raw_s3,
            op_kwargs={"bucket": S3_BUCKET},
        )

    # Task 2: Athena로 hourly summary 생성 (CTAS)
    if USE_KPO:
        create_hourly_summary = KubernetesPodOperator(
            task_id="create_hourly_summary",
            name="hourly-summary-athena",
            namespace="airflow",
            image="apache/airflow:2.9.3-python3.14.2",
            cmds=["python", "-c"],
            arguments=[ATHENA_RUNNER_SCRIPT],
            env_vars={
                "AWS_REGION": REGION,
                "DATABASE": DATABASE,
                "ATHENA_OUTPUT": ATHENA_OUTPUT,
                "TMP_TABLE": "ad_hourly_summary_tmp",
                "QUERY": (
                    "CREATE TABLE {{ params.database }}.ad_hourly_summary_tmp "
                    "WITH ( "
                    "  format = 'PARQUET', "
                    "  write_compression = 'ZSTD', "
                    "  external_location = '{{ params.summary_path }}"
                    "/dt={{ (data_interval_end - macros.timedelta(minutes=10)).strftime(\"%Y-%m-%d-%H\") }}/' "
                    ") AS "
                    "SELECT "
                    "  imp.campaign_id, "
                    "  imp.device_type, "
                    "  '{{ (data_interval_end - macros.timedelta(minutes=10)).strftime(\"%Y-%m-%d-%H\") }}' AS dt, "
                    "  COUNT(DISTINCT imp.event_id) AS impressions, "
                    "  COUNT(DISTINCT clk.event_id) AS clicks, "
                    "  CASE "
                    "    WHEN COUNT(DISTINCT imp.event_id) > 0 "
                    "    THEN CAST(COUNT(DISTINCT clk.event_id) AS DOUBLE) "
                    "         / CAST(COUNT(DISTINCT imp.event_id) AS DOUBLE) * 100 "
                    "    ELSE 0.0 "
                    "  END AS ctr "
                    "FROM {{ params.database }}.ad_events_raw AS imp "
                    "LEFT JOIN {{ params.database }}.ad_events_raw AS clk "
                    "  ON imp.campaign_id = clk.campaign_id "
                    "  AND imp.user_id = clk.user_id "
                    "  AND clk.event_type = 'click' "
                    "  AND clk.year = '{{ (data_interval_end - macros.timedelta(minutes=10)).strftime(\"%Y\") }}' "
                    "  AND clk.month = '{{ (data_interval_end - macros.timedelta(minutes=10)).strftime(\"%m\") }}' "
                    "  AND clk.day = '{{ (data_interval_end - macros.timedelta(minutes=10)).strftime(\"%d\") }}' "
                    "WHERE imp.event_type = 'impression' "
                    "  AND imp.year = '{{ (data_interval_end - macros.timedelta(minutes=10)).strftime(\"%Y\") }}' "
                    "  AND imp.month = '{{ (data_interval_end - macros.timedelta(minutes=10)).strftime(\"%m\") }}' "
                    "  AND imp.day = '{{ (data_interval_end - macros.timedelta(minutes=10)).strftime(\"%d\") }}' "
                    "  AND imp.timestamp >= {{ ((data_interval_end - macros.timedelta(minutes=10)).replace(minute=0, second=0, microsecond=0)).int_timestamp * 1000 }} "
                    "  AND imp.timestamp < {{ (((data_interval_end - macros.timedelta(minutes=10)).replace(minute=0, second=0, microsecond=0) + macros.timedelta(hours=1))).int_timestamp * 1000 }} "
                    "GROUP BY imp.campaign_id, imp.device_type"
                ),
            },
            params={
                "database": DATABASE,
                "summary_path": HOURLY_SUMMARY_PATH,
            },
            service_account_name="airflow-scheduler",
            get_logs=True,
            is_delete_operator_pod=True,
        )
    else:
        create_hourly_summary = PythonOperator(
            task_id="create_hourly_summary",
            python_callable=_run_athena_query,
            op_kwargs={
                "region": REGION,
                "database": DATABASE,
                "output": ATHENA_OUTPUT,
                "tmp_table": "ad_hourly_summary_tmp",
                "query": (
                    "CREATE TABLE {{ params.database }}.ad_hourly_summary_tmp WITH ( format = 'PARQUET', write_compression = 'ZSTD', "
                    "external_location = '{{ params.summary_path }}/dt={{ (data_interval_end - macros.timedelta(minutes=10)).strftime(\"%Y-%m-%d-%H\") }}/' ) AS "
                    "SELECT imp.campaign_id, imp.device_type, "
                    "'{{ (data_interval_end - macros.timedelta(minutes=10)).strftime(\"%Y-%m-%d-%H\") }}' AS dt, "
                    "COUNT(DISTINCT imp.event_id) AS impressions, COUNT(DISTINCT clk.event_id) AS clicks, "
                    "CASE WHEN COUNT(DISTINCT imp.event_id) > 0 THEN CAST(COUNT(DISTINCT clk.event_id) AS DOUBLE) / CAST(COUNT(DISTINCT imp.event_id) AS DOUBLE) * 100 ELSE 0.0 END AS ctr "
                    "FROM {{ params.database }}.ad_events_raw AS imp LEFT JOIN {{ params.database }}.ad_events_raw AS clk "
                    "ON imp.campaign_id = clk.campaign_id AND imp.user_id = clk.user_id AND clk.event_type = 'click' "
                    "AND clk.year='{{ (data_interval_end - macros.timedelta(minutes=10)).strftime(\"%Y\") }}' AND clk.month='{{ (data_interval_end - macros.timedelta(minutes=10)).strftime(\"%m\") }}' AND clk.day='{{ (data_interval_end - macros.timedelta(minutes=10)).strftime(\"%d\") }}' "
                    "WHERE imp.event_type = 'impression' AND imp.year='{{ (data_interval_end - macros.timedelta(minutes=10)).strftime(\"%Y\") }}' AND imp.month='{{ (data_interval_end - macros.timedelta(minutes=10)).strftime(\"%m\") }}' AND imp.day='{{ (data_interval_end - macros.timedelta(minutes=10)).strftime(\"%d\") }}' "
                    "AND imp.timestamp >= {{ ((data_interval_end - macros.timedelta(minutes=10)).replace(minute=0, second=0, microsecond=0)).int_timestamp * 1000 }} "
                    "AND imp.timestamp < {{ (((data_interval_end - macros.timedelta(minutes=10)).replace(minute=0, second=0, microsecond=0) + macros.timedelta(hours=1))).int_timestamp * 1000 }} "
                    "GROUP BY imp.campaign_id, imp.device_type"
                ),
            },
            params={"database": DATABASE, "summary_path": HOURLY_SUMMARY_PATH},
        )

    # Task 3: Glue 파티션 등록
    if USE_KPO:
        register_partition = KubernetesPodOperator(
            task_id="register_partition",
            name="register-partition",
            namespace="airflow",
            image="apache/airflow:2.9.3-python3.14.2",
            cmds=["python", "-c"],
            arguments=[PARTITION_REPAIR_SCRIPT],
            env_vars={
                "AWS_REGION": REGION,
                "DATABASE": DATABASE,
                "ATHENA_OUTPUT": ATHENA_OUTPUT,
                "TABLE": "ad_hourly_summary",
            },
            service_account_name="airflow-scheduler",
            get_logs=True,
            is_delete_operator_pod=True,
        )
    else:
        register_partition = PythonOperator(
            task_id="register_partition",
            python_callable=_repair_partitions,
            op_kwargs={
                "region": REGION,
                "database": DATABASE,
                "output": ATHENA_OUTPUT,
                "table": "ad_hourly_summary",
            },
        )

    # Task 의존성
    check_data >> create_hourly_summary >> register_partition

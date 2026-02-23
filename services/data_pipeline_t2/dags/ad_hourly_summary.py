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
# 테스트
from airflow import DAG
from airflow.providers.cncf.kubernetes.operators.pod import KubernetesPodOperator
from airflow.operators.python import PythonOperator
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
            END AS ctr,

            -- 비용 집계
            SUM(imp.bid_price)              AS total_bid_cost,
            AVG(imp.bid_price)              AS avg_bid_price

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
    dag_id="ad_hourly_summary",
    default_args=default_args,
    description="매시간 impression+click 조인하여 hourly summary 테이블 생성",
    schedule_interval="@hourly",
    start_date=datetime(2026, 2, 13),
    catchup=False,
    max_active_runs=1,
    tags=["capa", "hourly", "ad", "etl"],
) as dag:

    # Task 1: S3 raw 데이터 존재 확인 (간단한 validation)
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

    # Task 2: Athena로 hourly summary 생성 (CTAS)
    create_hourly_summary = KubernetesPodOperator(
        task_id="create_hourly_summary",
        name="hourly-summary-athena",
        namespace="airflow",
        image="apache/airflow:2.9.3-python3.12",
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
                "/dt={{ data_interval_start.strftime(\"%Y-%m-%d-%H\") }}/' "
                ") AS "
                "SELECT "
                "  imp.campaign_id, "
                "  imp.device_type, "
                "  '{{ data_interval_start.strftime(\"%Y-%m-%d-%H\") }}' AS dt, "
                "  COUNT(DISTINCT imp.event_id) AS impressions, "
                "  COUNT(DISTINCT clk.event_id) AS clicks, "
                "  CASE "
                "    WHEN COUNT(DISTINCT imp.event_id) > 0 "
                "    THEN CAST(COUNT(DISTINCT clk.event_id) AS DOUBLE) "
                "         / CAST(COUNT(DISTINCT imp.event_id) AS DOUBLE) * 100 "
                "    ELSE 0.0 "
                "  END AS ctr, "
                "  SUM(imp.bid_price) AS total_bid_cost, "
                "  AVG(imp.bid_price) AS avg_bid_price "
                "FROM {{ params.database }}.ad_events_raw AS imp "
                "LEFT JOIN {{ params.database }}.ad_events_raw AS clk "
                "  ON imp.campaign_id = clk.campaign_id "
                "  AND imp.user_id = clk.user_id "
                "  AND clk.event_type = 'click' "
                "  AND clk.year = '{{ data_interval_start.strftime(\"%Y\") }}' "
                "  AND clk.month = '{{ data_interval_start.strftime(\"%m\") }}' "
                "  AND clk.day = '{{ data_interval_start.strftime(\"%d\") }}' "
                "WHERE imp.event_type = 'impression' "
                "  AND imp.year = '{{ data_interval_start.strftime(\"%Y\") }}' "
                "  AND imp.month = '{{ data_interval_start.strftime(\"%m\") }}' "
                "  AND imp.day = '{{ data_interval_start.strftime(\"%d\") }}' "
                "  AND imp.timestamp >= {{ data_interval_start.int_timestamp * 1000 }} "
                "  AND imp.timestamp < {{ (data_interval_start + macros.timedelta(hours=1)).int_timestamp * 1000 }} "
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

    # Task 3: Glue 파티션 등록
    register_partition = KubernetesPodOperator(
        task_id="register_partition",
        name="register-partition",
        namespace="airflow",
        image="apache/airflow:2.9.3-python3.12",
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

    # Task 의존성
    check_data >> create_hourly_summary >> register_partition

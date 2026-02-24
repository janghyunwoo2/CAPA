"""
DAG: ad_daily_summary
주기: 매일 02:00 UTC (hourly summary가 모두 완료된 이후)
역할: hourly_summary 24개 집계 + conversion 원천 로그 조인
      → ad_daily_summary 테이블 생성

전략 (효율성 근거):
  - impression+click은 이미 hourly에서 집계 완료 → 재스캔 불필요
  - hourly_summary를 SUM으로 재집계 (소량 데이터, Athena 비용 최소)
  - conversion만 원천 로그에서 읽어 campaign_id 기준 조인
  - conversion은 "늦게 발생하는 경향"이므로 daily 배치에 적합 (회의록 참조)

결과 테이블:
  ad_daily_summary: campaign_id, device_type별
    impressions, clicks, conversions, ctr, cvr
"""

from airflow import DAG
from airflow.providers.cncf.kubernetes.operators.pod import KubernetesPodOperator
from airflow.sensors.external_task import ExternalTaskSensor
from datetime import datetime, timedelta
import textwrap

# =============================================================================
# 설정
# =============================================================================
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


# =============================================================================
# Athena 실행 Python 스크립트 (재사용)
# =============================================================================
ATHENA_RUNNER_SCRIPT = textwrap.dedent("""
import boto3
import time
import os

REGION = os.environ.get('AWS_REGION', 'ap-northeast-2')
DATABASE = os.environ['DATABASE']
ATHENA_OUTPUT = os.environ['ATHENA_OUTPUT']
QUERIES = os.environ['QUERIES'].split('|||')  # 여러 쿼리를 구분자로 분리

client = boto3.client('athena', region_name=REGION)

def run_query(sql, step_num=0):
    sql = sql.strip()
    if not sql:
        return
    print(f"\\n{'='*60}")
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

print("\\n[DONE] All queries completed successfully")
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


# =============================================================================
# DAG 정의
# =============================================================================
with DAG(
    dag_id="ad_daily_summary",
    default_args=default_args,
    description="매일 hourly_summary 집계 + conversion 조인하여 daily summary 생성",
    schedule_interval="0 2 * * *",  # 매일 02:00 UTC (hourly DAG 완료 후 여유)
    start_date=datetime(2026, 2, 13),
    catchup=False,
    max_active_runs=1,
    tags=["capa", "daily", "ad", "etl"],
) as dag:

    # =========================================================================
    # Task 1: 마지막 hourly summary(23시)가 완료되었는지 확인
    # =========================================================================
    wait_for_hourly = ExternalTaskSensor(
        task_id="wait_for_hourly_summary",
        external_dag_id="ad_hourly_summary",
        external_task_id="register_partition",
        # 전날 23시 실행분이 완료되었는지 확인
        # daily DAG data_interval_start: 전날 00:00 UTC
        # hourly DAG data_interval_start: 전날 23:00 UTC
        execution_delta=timedelta(hours=3),  # daily 02:00 기준으로 hourly 23:00 = 3시간 전
        timeout=3600,  # 최대 1시간 대기
        poke_interval=120,  # 2분마다 확인
        mode="reschedule",  # 워커 슬롯 반환
    )

    # =========================================================================
    # Task 2: Daily Summary 생성
    # Step 1) 임시 테이블 정리
    # Step 2) hourly_summary 24개 재집계 + conversion 조인하여 daily summary 생성
    # Step 3) 임시 테이블 정리
    # =========================================================================
    #
    # 핵심 전략:
    #   hourly_summary에서 impression/click 집계값을 SUM으로 재집계 (소량)
    #   + conversion 원천 로그에서 해당 일자 건만 COUNT (campaign_id 기준 조인)
    #   → 원천 impression/click 로그를 다시 스캔하지 않아 Athena 비용 최소화
    #
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
                # --- Query 1: 임시 테이블 삭제 (idempotency) ---
                "DROP TABLE IF EXISTS {{ params.database }}.ad_daily_summary_tmp"
                "|||"
                # --- Query 2: Daily Summary CTAS ---
                # hourly_summary (impression+click 집계) + conversion 원천 로그 조인
                "CREATE TABLE {{ params.database }}.ad_daily_summary_tmp "
                "WITH ( "
                "  format = 'PARQUET', "
                "  write_compression = 'ZSTD', "
                "  external_location = '{{ params.daily_path }}"
                "/ds={{ data_interval_start.strftime(\"%Y-%m-%d\") }}/' "
                ") AS "
                "WITH hourly_agg AS ( "
                "  SELECT "
                "    campaign_id, "
                "    device_type, "
                "    SUM(impressions)    AS impressions, "
                "    SUM(clicks)         AS clicks "
                "  FROM {{ params.database }}.ad_hourly_summary "
                "  WHERE dt >= '{{ data_interval_start.strftime(\"%Y-%m-%d\") }}-00' "
                "    AND dt <= '{{ data_interval_start.strftime(\"%Y-%m-%d\") }}-23' "
                "  GROUP BY campaign_id, device_type "
                "), "
                "conversion_agg AS ( "
                "  SELECT "
                "    campaign_id, "
                "    device_type, "
                "    COUNT(DISTINCT event_id) AS conversions "
                "  FROM {{ params.database }}.ad_events_raw "
                "  WHERE event_type = 'conversion' "
                "    AND year  = '{{ data_interval_start.strftime(\"%Y\") }}' "
                "    AND month = '{{ data_interval_start.strftime(\"%m\") }}' "
                "    AND day   = '{{ data_interval_start.strftime(\"%d\") }}' "
                "  GROUP BY campaign_id, device_type "
                ") "
                "SELECT "
                "  h.campaign_id, "
                "  h.device_type, "
                "  '{{ data_interval_start.strftime(\"%Y-%m-%d\") }}' AS ds, "
                "  h.impressions, "
                "  h.clicks, "
                "  COALESCE(c.conversions, 0) AS conversions, "
                "  CASE WHEN h.impressions > 0 "
                "    THEN CAST(h.clicks AS DOUBLE) / CAST(h.impressions AS DOUBLE) * 100 "
                "    ELSE 0.0 END AS ctr, "
                "  CASE WHEN h.clicks > 0 "
                "    THEN CAST(COALESCE(c.conversions, 0) AS DOUBLE) / CAST(h.clicks AS DOUBLE) * 100 "
                "    ELSE 0.0 END AS cvr "
                "FROM hourly_agg h "
                "LEFT JOIN conversion_agg c "
                "  ON h.campaign_id = c.campaign_id "
                "  AND h.device_type = c.device_type"
                "|||"
                # --- Query 3: 임시 테이블 정리 ---
                "DROP TABLE IF EXISTS {{ params.database }}.ad_daily_summary_tmp"
            ),
        },
        params={
            "database": DATABASE,
            "daily_path": DAILY_SUMMARY_PATH,
        },
        service_account_name="airflow-scheduler",
        get_logs=True,
        is_delete_operator_pod=True,
    )

    # =========================================================================
    # Task 3: Glue 파티션 등록
    # =========================================================================
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

    # =========================================================================
    # Task 4: 리포트 생성 트리거 (기존 report-generator 연동)
    # =========================================================================
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

    # Task 의존성
    wait_for_hourly >> create_daily_summary >> register_partition >> trigger_report

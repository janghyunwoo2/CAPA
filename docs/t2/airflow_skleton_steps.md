# Airflow 스켈레톤: Text-to-SQL 전 준비 작업 — 단계별 구현 가이드

이 문서는 LLM 도입 전에도 구현할 수 있는 핵심 자동화(스키마 수집, 데이터 품질 검사, 미리 계산된 뷰)를 Airflow로 단계별로 구현하는 구체적 가이드입니다. 각 단계에 필요한 코드 스켈레톤, 실행 명령, 테스트 방법, 운영 고려사항을 포함합니다.

목표 작업
- 1) DB 스키마 자동 추출 및 S3 저장
- 2) 데이터 품질(Validation) 파이프라인
- 3) 복잡 조인에 대한 Pre-aggregation(Materialized view)

사전 준비
- AWS 계정: S3 버킷, Glue Catalog(선택), Athena 사용 권한
- 로컬/개발: Python 3.8+ 권장
- Airflow: 프로젝트 테스트용 `AIRFLOW_HOME` 설정

```bash
# 예: 가상환경 및 패키지 설치
python -m venv .venv
.
# Windows PowerShell: .venv\Scripts\Activate.ps1
# Unix: source .venv/bin/activate
pip install --upgrade pip
pip install apache-airflow==2.5.3 boto3 psycopg2-binary sqlalchemy pandas
```

환경 변수(예시)

```bash
export AIRFLOW_HOME=$(pwd)/src/data_pipeline_t2
export AWS_REGION=ap-northeast-2
export S3_BUCKET=capa-bucket
# DB 접속 정보 (예: Postgres)
export DB_HOST=your-db-host
export DB_PORT=5432
export DB_NAME=yourdb
export DB_USER=youruser
export DB_PASS=yourpass
```

공통 구현 규칙
- DAG 폴더: `AIRFLOW_HOME/dags/` 안에 파일을 둡니다.
- Operators: 가능하면 `PythonOperator`로 핵심 로직 구현 (작업 단위로 분리)
- 결과 저장: 스키마 JSON/CSV 및 검증 리포트는 `s3://${S3_BUCKET}/metadata/`에 저장
- 로그·비밀: Airflow Connections/Secrets 사용

1) DB 스키마 자동 추출 (Schema extraction)

목적: 운영 DB의 테이블과 컬럼 정보를 주기적으로 추출해 JSON/CSV로 저장. Text-to-SQL에서 참조하는 메타데이터가 됨.

파일: `dags/schema_extraction_dag.py` (예시)

```python
from airflow import DAG
from airflow.operators.python import PythonOperator
from datetime import datetime, timedelta
import sqlalchemy as sa
import json
import boto3
import os

DEFAULT_ARGS = {
    'owner': 'capa',
    'start_date': datetime(2025,1,1),
    'retries': 1,
    'retry_delay': timedelta(minutes=5)
}

def extract_schema(**context):
    db_url = f"postgresql://{os.environ['DB_USER']}:{os.environ['DB_PASS']}@{os.environ['DB_HOST']}:{os.environ['DB_PORT']}/{os.environ['DB_NAME']}"
    eng = sa.create_engine(db_url)
    meta = sa.MetaData()
    meta.reflect(bind=eng)
    out = {}
    for t in meta.sorted_tables:
        out[str(t)] = [{'name': c.name, 'type': str(c.type)} for c in t.columns]
    s3 = boto3.client('s3')
    key = f"metadata/schema_{context['ds_nodash']}.json"
    s3.put_object(Bucket=os.environ['S3_BUCKET'], Key=key, Body=json.dumps(out).encode('utf-8'))

with DAG('schema_extraction', default_args=DEFAULT_ARGS, schedule_interval='@daily', catchup=False) as dag:
    t = PythonOperator(task_id='extract_schema', python_callable=extract_schema)

```

실행/테스트

```bash
airflow tasks test schema_extraction extract_schema 2025-01-02
aws s3 ls s3://${S3_BUCKET}/metadata/
```

운영 고려사항
- 빈번한 스키마 변경이 있는 테이블은 제외하거나 빈도 낮춤
- 스키마 파일 버전 관리(파일명에 날짜 포함)

2) 데이터 품질 검사 (Validation)

목적: 결측치, 타입 불일치, 값 범위(비즈니스 규칙)를 자동 검사하고 리포트 생성

파일: `dags/data_quality_dag.py` (예시)

```python
from airflow import DAG
from airflow.operators.python import PythonOperator
from datetime import datetime, timedelta
import pandas as pd
import boto3
import os

DEFAULT_ARGS = {
    'owner': 'capa',
    'start_date': datetime(2025,1,1),
}

def run_quality_checks(**context):
    # 예: S3에 있는 최근 raw data CSV/Parquet 읽기 (간단 예시)
    s3 = boto3.client('s3')
    bucket = os.environ['S3_BUCKET']
    key = f"raw/logs_{context['ds_nodash']}.parquet"
    # 실제로는 smart reader (pyarrow/pandas) 사용
    # df = pd.read_parquet(f's3://{bucket}/{key}')
    # 샘플 체크
    report = {'row_count': 1000, 'null_ratio': {'user_id': 0.0}}
    s3.put_object(Bucket=bucket, Key=f"metadata/quality_{context['ds_nodash']}.json", Body=str(report))

with DAG('data_quality', default_args=DEFAULT_ARGS, schedule_interval='@daily', catchup=False) as dag:
    t = PythonOperator(task_id='run_quality_checks', python_callable=run_quality_checks)

```

테스트 및 알림

```bash
airflow tasks test data_quality run_quality_checks 2025-01-02
aws s3 cp s3://${S3_BUCKET}/metadata/quality_20250102.json -
```

운영 고려사항
- 규칙(예: 허용 null 비율, 값 범위)을 YAML/DB로 관리하고 DAG는 규칙을 로드해 검사
- 이상 시 알림: Slack/메일(예: `airflow.providers.slack.operators.slack_webhook.SlackWebhookOperator`)

3) 미리 계산된 뷰(Materialized view / Pre-aggregation)

목적: 복잡한 조인/집계를 밤시간에 미리 계산해 분석·TTS에서 간단 쿼리로 사용 가능하게 함

파일: `dags/preagg_dag.py`

```python
from airflow import DAG
from airflow.providers.amazon.aws.operators.athena import AthenaOperator
from datetime import datetime, timedelta

DEFAULT_ARGS = {'owner':'capa', 'start_date': datetime(2025,1,1)}

with DAG('preagg_daily', default_args=DEFAULT_ARGS, schedule_interval='@daily', catchup=False) as dag:
    sql = '''
    CREATE TABLE IF NOT EXISTS analytics.preagg_ads_daily
    WITH (format='PARQUET', external_location='s3://{bucket}/preagg/ads_daily/', partitioned_by = ARRAY['ds']) AS
    SELECT advertiser_id, date(event_time) as ds, count(*) as impressions, sum(case when event='click' then 1 else 0 end) as clicks
    FROM analytics.raw_logs
    WHERE date(event_time)=date('{{ ds }}')
    GROUP BY advertiser_id, date(event_time)
    '''.format(bucket=os.environ['S3_BUCKET'])

    run = AthenaOperator(task_id='create_preagg', query=sql, database='analytics', output_location=f"s3://{os.environ['S3_BUCKET']}/athena-results/")

```

검증 & Idempotency
- CTAS는 테이블이 없을 때만 생성하므로, 매일 덮어쓰려면 임시 테이블 사용 후 파티션 단위 교체 전략을 권장
- 예: `CREATE TABLE tmp AS ...` 후 `ALTER TABLE ... ADD PARTITION` 또는 S3 임시 경로에서 교체

배포(간단)

```bash
# DAG 파일을 AIRFLOW_HOME/dags/에 복사 후
airflow db init
airflow scheduler &
airflow webserver --port 8080 &
```

추가 테스트 방법
- 단위: 각 PythonOperator 함수에 대해 pytest로 입력/출력 검증
- 통합: `airflow tasks test <dag_id> <task_id> <date>`로 개별 태스크 실행
- E2E: 작은 샘플 데이터로 전체 DAG 실행(Dev S3 버킷 사용)

모니터링 & 알림
- Airflow UI + Slack/메일 알림 설정
- Athena 쿼리 비용: CloudWatch + 비용 알림
- 품질 리포트: S3에 저장한 JSON을 Redash나 간단한 시각화로 모니터링

운영 체크리스트(요약)
- DAG에 재시도·타임아웃 설정 포함
- S3 키 네이밍·버전 정책 수립
- 민감 정보(PII) 처리 규약 적용
- Glue 테이블 파티션 정책 문서화

다음 단계 제안
1. 위 예시 DAG들을 repo `dags/`에 추가 (제가 만들어 드릴 수 있음)
2. 로컬에서 각 태스크 수동 실행으로 동작 확인
3. EKS + Helm으로 Airflow 배포 시 Values파일과 IAM 역할 조정

---
작성: CAPA — Airflow 스켈레톤 단계별 구현

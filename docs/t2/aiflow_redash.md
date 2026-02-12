# Airflow ↔ Redash 연동 가이드 (CAPA)

## 한눈에 요약
- Airflow: 배치 ETL 스케줄러/오케스트레이터 (로그 생성 X)
- Redash: BI / 쿼리•대시보드 도구
- 기본 관계: Airflow가 Athena(SQL)를 통해 S3에 분석용 데이터를 생성(Parquet, 파티션)하고 Glue 테이블로 노출하면, Redash는 그 Glue/Athena를 데이터 소스로 직접 조회.

## 구성요소와 책임
- 로그 생성: `log-generator` 또는 스트리밍(Kinesis) — Airflow 관여 없음
- 원시 저장소: S3
- ETL 오케스트레이션: `Airflow` (SQL 우선, Athena 사용) — 주기적 실행, 예외 시 재시도/알림
- 결과 저장: S3(Parquet, 파티션) + `AWS Glue Tables` 메타데이터
- 시각화: `Redash` (Athena 또는 DB를 데이터 소스로 설정)

## 데이터 흐름 (권장 패턴)
1. 로그 생성기 → S3(raw)
2. Airflow DAG 스케줄 트리거
   - `check_raw_logs` (Sensor)
   - `athena_transform` (SQL / CTAS → S3/Parquet)
   - `validate_schema` (간단 체크)
   - `register_partition` (Glue 파티션 등록)
   - (옵션) `refresh_redash` (Redash API 호출)
3. Redash는 Athena에 연결해 대시보드를 조회

## Redash 연동 옵션 (3가지)

1) Redash가 직접 Athena/Glue 조회 (기본·권장)
   - Redash datasource = Athena (IAM 권한 필요)
   - 장점: 단순, Redash에서 항상 최신 데이터 조회

2) Airflow가 Redash API로 쿼리/대시보드 캐시 갱신 (선택적 자동화)
   - Airflow ETL 완료 후 Redash REST API 호출로 특정 쿼리 새로고침
   - 사용처: Redash에 쿼리 캐시가 있고, DAG 완료 직후 사용자가 즉시 최신 화면을 보게 하고 싶을 때
   - 주의사항: API 키 보안(Secrets/Connections), 호출 빈도 제한, 실패 처리(재시도/로그)

3) Airflow → 별도 DB(RDS 등) 적재 → Redash가 DB 조회
   - 사용처: 복잡한 JOIN/렌더링 쿼리가 빈번하고 응답 속도가 중요할 때
   - 단점: 추가 인프라, 데이터 동기화 책임 증가

## 구현 원칙 (CAPA 정책과 일치)
- **SQL 우선**: 변환은 Athena SQL(CTAS/INSERT)으로 기본 구현.
- **포맷**: Parquet + 파티션(예: `ds=YYYY-MM-DD`) 권장.
- **스키마**: 결과는 `AWS Glue Tables`로 노출 — Athena는 Glue 메타데이터 사용.
- **Idempotency**: 파티션 단위 쓰기 또는 임시 테이블 생성 후 원자적 교체.
- **운영**: 재시도 정책, 실패 알림(Slack/메일), 실행 로그 보존(S3/CloudWatch).
- **권한**: Redash 또는 Airflow가 Athena/Glue에 접근하는 IAM 정책 필요.

## 예시: Airflow DAG(간단한 흐름) 및 Redash 갱신
아래 예시는 `athena_transform`(SQL 실행) → `register_partition`(Glue 파티션 등록) → `refresh_redash`(Redash API 호출) 흐름을 보입니다.

```python
# dags/capa_etl_dag.py
from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.providers.amazon.aws.operators.athena import AthenaOperator
from datetime import datetime, timedelta
import os, requests, boto3

DEFAULT_ARGS = {
    "owner": "capa",
    "depends_on_past": False,
    "retries": 1,
    "retry_delay": timedelta(minutes=5),
}

with DAG(
    dag_id="capa_etl_pipeline",
    default_args=DEFAULT_ARGS,
    schedule_interval="@daily",
    start_date=datetime(2025,1,1),
    catchup=False,
) as dag:

    athena_sql = """
    CREATE TABLE IF NOT EXISTS analytics.metrics_daily
    WITH (format='PARQUET', external_location='s3://capa-bucket/metrics/', partitioned_by = ARRAY['ds']) AS
    SELECT advertiser_id, date(event_time) AS ds, COUNT(*) AS impressions
    FROM analytics.raw_logs
    WHERE date(event_time)=date('{{ ds }}')
    GROUP BY advertiser_id, date(event_time))
    """

    run_athena = AthenaOperator(
        task_id="athena_transform",
        query=athena_sql,
        database="analytics",
        output_location="s3://capa-bucket/athena-results/",
        max_tries=3,
    )

    def register_partition(ds, **context):
        glue = boto3.client("glue")
        try:
            glue.get_table(DatabaseName="analytics", Name="metrics_daily")
        except glue.exceptions.EntityNotFoundException:
            # 테이블이 없으면 별도 테이블 생성 로직 필요 (생략)
            pass
        # 실제 환경에서는 정확한 StorageDescriptor를 구성하거나
        # MSCK REPAIR TABLE을 호출하는 편이 단순함
        glue.batch_create_partition(
            DatabaseName="analytics",
            TableName="metrics_daily",
            PartitionInputList=[{
                'Values':[ds],
                'StorageDescriptor':{
                    'Columns':[],
                    'Location':f's3://capa-bucket/metrics/ds={ds}/',
                    'InputFormat':'',
                    'OutputFormat':'',
                    'SerdeInfo':{}
                }
            }]
        )

    def refresh_redash(**context):
        REDASH_URL = os.environ.get('REDASH_URL')
        API_KEY = os.environ.get('REDASH_API_KEY')
        QUERY_ID = os.environ.get('REDASH_QUERY_ID')
        if not (REDASH_URL and API_KEY and QUERY_ID):
            return
        resp = requests.post(
            f"{REDASH_URL}/api/queries/{QUERY_ID}/refresh",
            headers={"Authorization": f"Key {API_KEY}"},
            timeout=30,
        )
        resp.raise_for_status()
        return resp.json()

    reg = PythonOperator(task_id="register_partition", python_callable=register_partition, op_kwargs={'ds': '{{ ds }}'})
    refresh = PythonOperator(task_id="refresh_redash", python_callable=refresh_redash)

    run_athena >> reg >> refresh
```

> 주의: 위 코드는 예시입니다. Glue 파티션 등록 시 `StorageDescriptor`를 정확히 채우거나 `MSCK REPAIR TABLE`을 사용하는 것을 권장합니다.

## 운영 가이드(짧게)
- 파티셔닝 전략: 날짜(`ds`) 기준 권장
- 스키마 검증: 컬럼·타입 체크를 DAG에 포함
- 성능: Athena 쿼리는 파티셔닝·컬럼프루닝을 고려해 작성
- 보안: IAM 역할 최소 권한 원칙 적용, Redash API 키는 Airflow Connections/Secrets에 저장

## 결론
- CAPA에서는 Airflow가 데이터 준비(ETL)를 담당하고, Redash는 그 준비된 Glue/Athena를 읽어 대시보드를 만듭니다.
- 필요하면 Airflow가 Redash API를 호출해 쿼리/대시보드 캐시를 갱신할 수 있습니다.

---
작성: CAPA 프로젝트 문서

## 다이어그램 (간단 흐름)
아래 Mermaid 다이어그램은 전체 구성의 핵심 흐름을 보여줍니다.

```mermaid
flowchart LR
    A[로그 생성기\n(log-generator / Kinesis)] -->|원시로그| B[S3 (raw)]
    B --> C[Airflow DAG]
    C --> D[Athena (SQL) 실행]\n  D --> E[S3 (Parquet, 파티션)]
    E --> F[AWS Glue Tables (메타데이터)]
    F --> G[Redash (대시보드 조회)]
    C --> H[옵션: Redash API 호출]
```

## 운영 체크리스트 (확장)
- 배포/설정
    - Airflow: EKS+Helm 또는 관리형 환경에 배포(권장 설정: `KubernetesExecutor`, RBAC, 로그 수집)
    - Redash: Athena datasource 구성(필요 IAM 권한 확인)
- 보안/접근
    - Redash API 키와 AWS 자격증명은 Airflow Connections 또는 Secrets Manager에 저장
    - IAM 역할: 최소 권한 원칙 적용(athena:StartQueryExecution, s3:GetObject/PutObject, glue:CreatePartition 등)
- 데이터 파이프라인
    - 파티셔닝 규칙: `ds=YYYY-MM-DD` 권장
    - 파일 포맷: Parquet + 압축(Snappy 등)
    - Idempotency: 임시 테이블 사용 또는 파티션 단위 쓰기
- 검증/모니터링
    - DAG 내 스키마 검증 태스크 추가(컬럼/타입/레코드 수)
    - 실패시 알림 설정: Slack / Mail
    - 쿼리 비용 모니터링: Athena 스캔량(파티셔닝·컬럼프루닝 권장)
- 운영 절차
    - 데이터 이상 감지 시 롤백/알림 정책 정의
    - Glue 파티션 등록 정책 문서화(`MSCK REPAIR TABLE` 또는 Glue API)
    - Redash 쿼리 캐시 정책(갱신 주기, 수동/자동 새로고침 방식) 수립

## 단계형 튜토리얼 (로컬/개발 환경에서 빠르게 검증)
아래는 CAPA의 ETL 흐름을 로컬/개발 환경에서 재현해보는 최소 실행 가이드입니다. 실제 운영 환경(EKS, IAM, S3 등)은 별도 설정이 필요합니다.

1) 환경 준비

```bash
# 권장: 가상환경 생성
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install --upgrade pip
pip install apache-airflow==2.5.3 boto3 requests
```

2) Airflow 홈 설정 (예시: 프로젝트 내부 경로)

```bash
export AIRFLOW_HOME=$(pwd)/src/data_pipeline_t2  # Windows PowerShell: $env:AIRFLOW_HOME = "${PWD}\src\data_pipeline_t2"
airflow db init
airflow users create --username admin --password admin --firstname Admin --lastname User --role Admin --email admin@example.com
```

3) DAG 추가
- 파일 `dags/capa_etl_dag.py`(위 문서의 예시 코드)를 `AIRFLOW_HOME/dags/`에 복사

4) 로컬 실행(간단 검증)

```bash
# 스케줄 없이 수동으로 DAG 실행(예: 테스트용 실행)
airflow tasks test capa_etl_pipeline athena_transform 2025-01-02

# 또는 웹서버와 스케줄러 실행
airflow webserver --port 8080 &
airflow scheduler &
```

5) Athena 연결/Glue 파티션 확인(개발 테스트)
- 실제 AWS 리소스를 사용하지 않으려면 `pyathena` 대신 로컬용 SQLite/CSV를 사용해 변환 로직만 검증

6) Redash 연동 테스트(선택)

```bash
# Redash API 새로고침 예시 (환경변수 설정 필요)
export REDASH_URL=https://redash.example.com
export REDASH_API_KEY=<your_api_key>
export REDASH_QUERY_ID=123

# 로컬에서 호출 테스트 (Python 스크립트 또는 curl)
curl -X POST -H "Authorization: Key ${REDASH_API_KEY}" ${REDASH_URL}/api/queries/${REDASH_QUERY_ID}/refresh
```

## 추가 권장자료 및 다음 단계
- 운영 환경 배포: `src/airflow/helm/` values 파일 점검 및 EKS 클러스터 준비(Terraform 모듈 참조)
- 모니터링: CloudWatch 또는 Prometheus + Grafana 설정 권장
- 테스트 자동화: DAG 단위의 통합 테스트(작업 테스트용 샘플 데이터 유지)

---
문서 업데이트 완료: `docs/t2/aiflow_redash.md`


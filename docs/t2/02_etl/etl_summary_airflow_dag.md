# Airflow DAG 가이드 (etl_summary_t2 기반)

etl_summary_t2 패키지(hourly/daily ETL, Athena 유틸)를 바탕으로 Airflow에서 시간별/일별 요약 테이블을 생성하는 DAG를 구성하는 방법을 정리합니다. 본 가이드는 요구사항에 따라 hourly, daily를 각각 “별도 DAG”로 구현합니다.

- 코드 위치
  - 패키지: services/data_pipeline_t2/etl_summary_t2
    - run_etl.py: 통합 실행 엔트리포인트 (hourly/daily/backfill)
    - hourly_etl.py: 시간별 ETL (ad_combined_log 생성)
    - daily_etl.py: 일별 ETL (ad_combined_log_summary 생성)
    - athena_utils.py: Athena 실행/결과 유틸
    - config.py: 공통 설정(AWS/S3/Athena 경로)
  - 기존 예시 DAG: services/data_pipeline_t2/dags/ad_hourly_summary.py, ad_daily_summary.py

## 사전 준비

- Airflow 2.6+ (KubernetesPodOperator 또는 PythonOperator 사용 가능)
- AWS 인증: IRSA/Instance Profile/Env Vars 등으로 Athena 접근 권한 필요
- S3 버킷/Glue/Athena 데이터베이스: config.py 설정 확인
- 의존성 설치: etl_summary_t2/requirements.txt를 Airflow 실행 환경에 반영

### 의존성 설치 옵션

1) Airflow 이미지 커스텀(권장)
```dockerfile
FROM apache/airflow:2.9.3-python3.14.2
COPY services/data_pipeline_t2/etl_summary_t2 /opt/airflow/etl_summary_t2
RUN pip install --no-cache-dir -r /opt/airflow/etl_summary_t2/requirements.txt
ENV PYTHONPATH="/opt/airflow:${PYTHONPATH}"
```

2) 볼륨 마운트(로컬 개발)
- etl_summary_t2 디렉터리를 Airflow 컨테이너의 `/opt/airflow/etl_summary_t2`에 마운트
- `pip install -r /opt/airflow/etl_summary_t2/requirements.txt`

## DAG 구현 방식 A: PythonOperator로 “분리 DAG” 구현

패키지의 엔트리포인트(run_etl.py)를 import하여 PythonOperator로 실행합니다. Airflow 이미지에 코드가 포함되어 있어야 합니다. Hourly와 Daily를 각각 별도 DAG로 만듭니다.

선택 기준과 특징
- 단순/직접 실행: 워커 프로세스에서 바로 Python 함수를 호출하므로 배포와 디버깅이 쉽습니다.
- 권한/의존성: 워커 컨테이너(또는 VM)에 `etl_summary_t2` 코드, `boto3` 등 의존 패키지, AWS 권한이 모두 준비돼 있어야 합니다.
- 리소스 제어: 워커 자원을 사용하므로 `pools`, `task_concurrency`, `priority_weight`로 동시성/리소스를 제한하세요.
- 멱등성/재시도: ETL은 임시 테이블 Drop→CTAS→Repair 순으로 동작해 재시도 안정성이 높습니다.

```python
# dags/ad_combined_hourly_etl.py
from airflow import DAG
from airflow.operators.python import PythonOperator
from datetime import datetime, timedelta
from etl_summary_t2.run_etl import run_hourly

DEFAULT_ARGS = {
    "owner": "capa",
    "depends_on_past": False,
    "retries": 1,
    "retry_delay": timedelta(minutes=5),
}

with DAG(
    dag_id="ad_combined_hourly_etl",
    default_args=DEFAULT_ARGS,
    description="etl_summary_t2 기반 시간별 요약 파이프라인",
    schedule="10 * * * *",  # KST 기준 10분 버퍼
    start_date=datetime(2026, 2, 13),
    catchup=False,
    max_active_runs=1,
    tags=["capa", "etl", "hourly"],
):
    hourly = PythonOperator(
        task_id="hourly_etl",
        python_callable=lambda **ctx: run_hourly(
            # 10분 버퍼: 트리거 시각의 data_interval_end에서 10분 빼고 그 시각의 시 단위 처리
            target_hour=(ctx["data_interval_end"] - timedelta(minutes=10)).strftime("%Y-%m-%d-%H")
        ),
    )
```

설명
- 스케줄 `10 * * * *` (KST): 매 시 10분(KST)에 실행. 이 런의 권장 데이터 구간은 직전 1시간입니다.
    - 예: 14:10 KST 트리거 → 데이터 구간 [13:00, 14:00)
- 로깅: `run_hourly()`의 로그가 Airflow 태스크 로그에 바로 기록됩니다.
- 백필: `catchup=True`로 과거 구간을 자동 실행하거나, 별도 Backfill DAG/CLI를 사용하세요.

스케줄 상세 (Hourly, KST)
- 실행 시각: 매 시 10분 KST (10분 안정화 버퍼)
- 첫 실행: `start_date` 이후 첫 KST 스케줄 슬롯에서 트리거
- 누락/지연: `catchup=True`면 과거 슬롯 순차 실행, `False`면 다음 슬롯부터 실행

버퍼(10분) 적용 시 필터(예시, Jinja)
```sql
-- 파티션 필터(버퍼 기준 처리 시간대)
WHERE year = '{{ (data_interval_end - macros.timedelta(minutes=10)).strftime("%Y") }}'
    AND month = '{{ (data_interval_end - macros.timedelta(minutes=10)).strftime("%m") }}'
    AND day = '{{ (data_interval_end - macros.timedelta(minutes=10)).strftime("%d") }}'
    AND hour = '{{ (data_interval_end - macros.timedelta(minutes=10)).strftime("%H") }}'
-- 타임스탬프(ms) 범위: [해당 시 정각, 다음 시 정각)
    AND timestamp >= {{ ((data_interval_end - macros.timedelta(minutes=10)).replace(minute=0, second=0, microsecond=0)).int_timestamp * 1000 }}
    AND timestamp <  {{ (((data_interval_end - macros.timedelta(minutes=10)).replace(minute=0, second=0, microsecond=0) + macros.timedelta(hours=1))).int_timestamp * 1000 }}
```

DEFAULT_ARGS = {
    "owner": "capa",
    "depends_on_past": False,
    "retries": 1,
    "retry_delay": timedelta(minutes=5),
}

with DAG(
    dag_id="ad_combined_daily_etl",
    default_args=DEFAULT_ARGS,
    description="etl_summary_t2 기반 일별 요약 파이프라인",
    schedule="0 2 * * *",  # KST 기준 전일 집계
    start_date=datetime(2026, 2, 13),
    catchup=False,
    max_active_runs=1,
    tags=["capa", "etl", "daily"],
):
    daily = PythonOperator(
        task_id="daily_etl",
        python_callable=lambda **ctx: run_daily(
            # 전일(캘린더 날짜) 하루치 summary
            target_date=(ctx["data_interval_end"] - timedelta(hours=2)).strftime("%Y-%m-%d")
        ),
    )
```

- 장점: 단순/직관적, 로그가 Airflow에 직접 남음
- 스케줄 `0 2 * * *` (KST): 매일 02:00 KST에 실행. 전일 캘린더(00~23시) 요약 수행.
- Daily 요건: “전일(예: 2026-03-03) 하루치 hourly + 전일 하루치 conversion” 요약
    - 03-04 02:00 KST 트리거 → 대상 캘린더 날짜 = 03-03
    - 템플릿 예: `{{ (data_interval_end - macros.timedelta(days=1)).strftime('%Y-%m-%d') }}`

스케줄 상세 (Daily, KST)
- 실행 시각: 매일 02:00 KST
- 대상 날짜: 템플릿에서 전일 캘린더 날짜를 명시적으로 계산해 사용
- 첫 실행: `start_date`의 다음 KST 유효 크론 슬롯에서 시작

캘린더 전일(00~23) 집계 범위(예시)
```sql
-- hourly 결과(예: ad_combined_log) 24시간 범위
WHERE dt >= '{{ target_date }}-00' AND dt <= '{{ target_date }}-23'

-- conversion 원천 로그(전일 하루치)
WHERE year = '{{ target_date[:4] }}'
    AND month = '{{ target_date[5:7] }}'
    AND day = '{{ target_date[8:10] }}'
```

- 주의: Airflow 워커의 boto3/AWS 권한이 Athena 접근 가능해야 함

## DAG 구현 방식 B: KubernetesPodOperator로 “분리 DAG” 구현

선택 기준과 특징
- 격리/유연성: 워커와 분리된 파드에서 실행되어 라이브러리/자원 충돌을 줄입니다.
- 권한 분리: ServiceAccount(IRSA 등)로 AWS 권한을 최소 권한 원칙에 맞게 부여하기 좋습니다.
- 배포: 커스텀 이미지에 `etl_summary_t2`와 의존성(예: boto3, python-dotenv)을 포함하고, `PYTHONPATH` 설정을 확인하세요.
- 성능/비용: 파드 기동 오버헤드가 있으므로 단시간 작업은 PythonOperator가 더 효율적일 수 있습니다.

컨테이너에서 `python -m etl_summary_t2.run_etl`을 실행합니다. 의존성이 포함된 커스텀 이미지를 사용하세요. Hourly와 Daily를 각각 별도 DAG로 만듭니다.

```python
# dags/ad_combined_hourly_etl_kpo.py
from airflow import DAG
from airflow.providers.cncf.kubernetes.operators.pod import KubernetesPodOperator
from datetime import datetime, timedelta

DEFAULT_ARGS = {
    "owner": "capa",
    "retries": 1,
    "retry_delay": timedelta(minutes=5),
}

IMAGE = "<registry>/ad-etl:latest"
NAMESPACE = "airflow"
SA = "airflow-scheduler"

with DAG(
    dag_id="ad_combined_hourly_etl_kpo",
    default_args=DEFAULT_ARGS,
    description="etl_summary_t2 시간별 요약(KPO)",
    schedule="10 * * * *",  # 10분 버퍼(KST)
    start_date=datetime(2026, 2, 13),
    catchup=False,
    max_active_runs=1,
    tags=["capa", "etl", "k8s", "hourly"],
):
    hourly = KubernetesPodOperator(
        task_id="hourly_etl",
        name="hourly-etl",
        namespace=NAMESPACE,
        image=IMAGE,
        cmds=["python", "-m", "etl_summary_t2.run_etl", "hourly"],
        arguments=[
            "--target-hour",
            "{{ (data_interval_end - macros.timedelta(minutes=10)).strftime('%Y-%m-%d-%H') }}",
        ],
        env_vars={
            "AWS_DEFAULT_REGION": "ap-northeast-2",
        },
        service_account_name=SA,
        get_logs=True,
        is_delete_operator_pod=True,
    )
```

설명
- 이미지: 상단 Dockerfile 예시로 빌드 후 레지스트리에 Push, Airflow가 Pull 가능하도록 권한을 설정하세요.
- 네임스페이스/SA: 클러스터 정책에 맞는 네임스페이스, ServiceAccount(및 IRSA) 권한을 구성하세요.
- 로그: `get_logs=True`로 파드 표준출력이 Airflow에 수집됩니다.

```python
# dags/ad_combined_daily_etl_kpo.py
from airflow import DAG
from airflow.providers.cncf.kubernetes.operators.pod import KubernetesPodOperator
from datetime import datetime, timedelta

DEFAULT_ARGS = {
    "owner": "capa",
    "retries": 1,
    "retry_delay": timedelta(minutes=5),
}

IMAGE = "<registry>/ad-etl:latest"
NAMESPACE = "airflow"
SA = "airflow-scheduler"

with DAG(
    dag_id="ad_combined_daily_etl_kpo",
    default_args=DEFAULT_ARGS,
    description="etl_summary_t2 일별 요약(KPO)",
    schedule="0 2 * * *",  # 02:00 KST
    start_date=datetime(2026, 2, 13),
    catchup=False,
    max_active_runs=1,
    tags=["capa", "etl", "k8s", "daily"],
):
    daily = KubernetesPodOperator(
        task_id="daily_etl",
        name="daily-etl",
        namespace=NAMESPACE,
        image=IMAGE,
        cmds=["python", "-m", "etl_summary_t2.run_etl", "daily"],
        arguments=[
            "--target-date",
            "{{ (data_interval_end - macros.timedelta(hours=2)).strftime('%Y-%m-%d') }}",
        ],
        env_vars={
            "AWS_DEFAULT_REGION": "ap-northeast-2",
        },
        service_account_name=SA,
        get_logs=True,
        is_delete_operator_pod=True,
    )
```

- 템플릿 보정: 02:00 트리거에서 전일 캘린더 날짜를 목표로 삼으려면 `{{ (data_interval_end - macros.timedelta(hours=2)).strftime('%Y-%m-%d') }}` 같이 보정하세요.

- 장점: 워커와 격리, 의존성/권한을 이미지/ServiceAccount로 분리 관리
- 주의: 이미지 레지스트리 접근, K8s 리소스/네트워크 권한 필요

## 스케줄링 권장안 (분리 구현 필수)

- 시간별 DAG: `@hourly` (또는 `0 * * * *`)
- 일별 DAG: `0 2 * * *` (시간별 집계 완료 후 2시간 여유)

필수: Hourly와 Daily를 각각 독립 DAG로 운영합니다. 필요 시 Daily DAG에 `ExternalTaskSensor`를 추가해 전일 마지막 시간(hourly) 완료를 보장할 수 있습니다.

예시(옵션): Daily DAG에 의존성 센서 추가
```python
from airflow.sensors.external_task import ExternalTaskSensor
wait_for_hourly = ExternalTaskSensor(
    task_id="wait_for_last_hour",
    external_dag_id="ad_combined_hourly_etl",
    external_task_id="hourly_etl",
    execution_delta=timedelta(hours=3),  # 02:00 기준 전일 23:00 실행분 대기
    poke_interval=120,
    timeout=3600,
    mode="reschedule",
)
# wait_for_hourly >> daily
```

### 크론/데이터 인터벌 동작 요약 (KST)
- Hourly(버퍼 10분): `10 * * * *`
    - 트리거: 매 시 10분(KST)
    - 권장 처리 구간: `(data_interval_end - 10분)`가 속한 시의 [정각, 정각+1h)
    - 예: 14:10 KST 트리거 → 권장 처리 [13:00, 14:00)
- Daily: `0 2 * * *`
    - 트리거: 매일 02:00(KST)
    - 요약 대상: 전일(캘린더) 00~23시 → 템플릿에서 `data_interval_end - 1일` 사용

팁
- `catchup`: 과거 구간 자동 실행. 대규모 백필은 별도 Backfill DAG/KPO로 분리 권장.
- `max_active_runs`, `concurrency`, `pools`: 동시 실행량을 조절해 Athena/Glue/S3 비용과 슬롯 사용을 안정화하세요.

주의: Airflow 3.x에서는 DAG에 `timezone=pendulum.timezone('Asia/Seoul')` 지정이 가능하지만, Airflow 2.x에서는 지원되지 않습니다. 2.x에서는 `start_date`를 KST로 지정하고(예: `pendulum.timezone('Asia/Seoul')`), 필요 시 `core.default_timezone=Asia/Seoul` 설정을 사용하세요. 이 경우 `data_interval_*`도 KST 기준으로 해석됩니다.

## Airflow Variables/Connections

- Variables (선택): `AWS_DEFAULT_REGION`, `S3_BUCKET`, `ATHENA_DATABASE` 등을 변수로 관리하고 `config.py`에서 참조하도록 개선 가능
- Connections: boto3가 환경변수를 사용한다면 불필요. AWS Connection을 사용한다면 `AIRFLOW__AWS__CONN_ID` 패턴으로 연동하거나 `boto3` 세션 생성 로직 반영 필요

## 백필(Backfill) 실행 예시

KPO 방식:
```python
KubernetesPodOperator(
  task_id="backfill_daily",
  image=IMAGE,
  cmds=["python", "-m", "etl_summary_t2.run_etl", "backfill"],
  arguments=[
    "--start-date", "2026-02-16",
    "--end-date", "2026-02-22",
    "--type", "daily"
  ],
  service_account_name=SA,
)
```

CLI(로컬 테스트):
```bash
python services/data_pipeline_t2/etl_summary_t2/run_etl.py hourly --target-hour 2026-02-24-14
python services/data_pipeline_t2/etl_summary_t2/run_etl.py daily --target-date 2026-02-24
python services/data_pipeline_t2/etl_summary_t2/run_etl.py backfill --start-date 2026-02-16 --end-date 2026-02-22 --type daily
```

## Glue/Athena 파티션 등록

- etl 코드에서 `MSCK REPAIR TABLE` 쿼리를 실행합니다.
- 추가 검증 또는 강제 등록이 필요하면 Airflow 태스크로 별도 실행 가능합니다.

```python
from airflow.providers.cncf.kubernetes.operators.pod import KubernetesPodOperator

repair = KubernetesPodOperator(
  task_id="repair_partitions",
    image="apache/airflow:2.9.3-python3.14.2",
  cmds=["python", "-c"],
  arguments=[
    "import boto3,os,time;\n"
    "r=os.environ.get('AWS_REGION','ap-northeast-2');db=os.environ['DB'];out=os.environ['OUT'];tbl=os.environ['TABLE'];\n"
    "c=boto3.client('athena',region_name=r);\n"
    "q=c.start_query_execution(QueryString=f'MSCK REPAIR TABLE {db}.{tbl}',QueryExecutionContext={'Database':db},ResultConfiguration={'OutputLocation':out});\n"
    "qid=q['QueryExecutionId'];\n"
    "import time\nwhile True:\n s=c.get_query_execution(QueryExecutionId=qid);st=s['QueryExecution']['Status']['State'];\n"
    "\n"
    " if st in ['SUCCEEDED','FAILED','CANCELLED']: break; time.sleep(3);\n"
    "print(st)"
  ],
  env_vars={"AWS_REGION":"ap-northeast-2","DB":"capa_ad_logs","OUT":"s3://capa-data-lake-827913617635/athena-results/","TABLE":"ad_combined_log_summary"},
  service_account_name=SA,
)
```

## 트러블슈팅

- 권한 오류: IRSA/SA Role에 `athena:*`, `glue:*`, `s3:*`(read/write) 최소 권한 확인
- 파티션 미인식: `MSCK REPAIR TABLE` 또는 Glue Crawler 수행
- 쿼리 실패: `config.py`의 `DATABASE`, `S3_BUCKET`, 경로/테이블 일치 여부 확인
- 모듈 로드 실패: Airflow 이미지에 `etl_summary_t2` 포함/마운트 및 `PYTHONPATH` 설정 확인

### 권한 오류 상세 체크리스트
- 증상: `AccessDeniedException`, `InsufficientPermissions`, `AccessDenied: Not authorized to perform ...`
- 점검 순서:
    1) 실행 주체 확인: IRSA(ServiceAccount), Instance Profile, 환경변수 자격증명 중 어느 경로로 인증되는지 파악
    2) 최소 권한 정책 샘플(참고, 실제로는 리소스 범위를 축소해 사용 권장):
         ```json
         {
             "Version": "2012-10-17",
             "Statement": [
                 {
                     "Effect": "Allow",
                     "Action": ["athena:*"],
                     "Resource": "*"
                 },
                 {
                     "Effect": "Allow",
                     "Action": ["glue:*"],
                     "Resource": "*"
                 },
                 {
                     "Effect": "Allow",
                     "Action": ["s3:GetObject","s3:PutObject","s3:ListBucket"],
                     "Resource": [
                         "arn:aws:s3:::<YOUR-BUCKET>",
                         "arn:aws:s3:::<YOUR-BUCKET>/*"
                     ]
                 }
             ]
         }
         ```
    3) Athena 결과 경로 `ATHENA_OUTPUT` S3 권한 포함 여부 확인(버킷/프리픽스 모두)

### 파티션 미인식(쿼리 결과 없음/직전 적재분 미노출)
- 증상: 적재는 되었는데 SELECT가 빈 결과, 최근 파티션이 보이지 않음
- 즉시 조치:
    - Athena에서 수동 실행: `MSCK REPAIR TABLE <db>.<table>`
    - 또는 Airflow 태스크로 실행(본 문서의 KPO 예시 `repair_partitions` 참고)
- 추가 체크:
    - S3 경로 규칙이 Glue 테이블 파티션 스키마와 일치하는지 확인(예: `.../dt=YYYY-MM-DD-HH/`)
    - 필요 시 수동 파티션 추가(예시):
        ```sql
        ALTER TABLE <db>.<table>
        ADD IF NOT EXISTS PARTITION (dt='2026-02-24-14') LOCATION 's3://<bucket>/summary/.../dt=2026-02-24-14/';
        ```

### 쿼리 실패(CTAS/SELECT 에러)
- 증상: Athena `FAILED` with message, `HIVE_PATH_ALREADY_EXISTS`, `ACCESS_DENIED`, `SYNTAX_ERROR`
- 점검 포인트:
    - `external_location`이 가리키는 S3 경로가 비어있는지(HIVE_PATH_ALREADY_EXISTS 시 기존 데이터 정리 또는 다른 프리픽스 사용)
    - `DATABASE`/테이블 존재 여부 및 컬럼/파티션 명칭 일치
    - 소스 테이블 파티션 키와 템플릿(Jinja) 변수가 맞게 채워지는지(예: `year/month/day` vs `dt`)
- 빠른 검증 커맨드(몇 건만 확인):
    ```bash
    aws s3 ls s3://<bucket>/summary/ad_hourly_summary/ --recursive | head -20
    ```

### 모듈 로드 실패(`ModuleNotFoundError` 등)
- 증상: `ModuleNotFoundError: No module named 'etl_summary_t2'` 또는 내부 유틸 경로 불일치
- 해결:
    - 컨테이너 이미지에 코드 포함 후 `ENV PYTHONPATH=/opt/airflow:${PYTHONPATH}` 설정(본 문서 Dockerfile 예시 참고)
    - 볼륨 마운트 시 경로 일치 여부(`/opt/airflow/etl_summary_t2`) 및 `pip install -r requirements.txt` 반영 확인
    - Airflow 2.x에서는 워커/스케줄러 양쪽 환경 모두 동일 의존성 유지

### Airflow 버전별 timezone 관련 오류
- 증상: `TypeError: DAG.__init__() got an unexpected keyword argument 'timezone'`
- 원인: Airflow 2.x에서는 `DAG(..., timezone=...)` 인자를 지원하지 않음
- 해결:
    - DAG 정의에서 `timezone=` 제거
    - `start_date`를 KST로 명시: `start_date=pendulum.datetime(..., tz=pendulum.timezone("Asia/Seoul"))`
    - 필요 시 Airflow 설정에 `core.default_timezone=Asia/Seoul` 적용

### UI 접속/포트 이슈
- 증상: `http://localhost:<port>` 접속 불가
- 확인:
    - 로컬 포트포워딩(K8s): `kubectl port-forward svc/airflow-webserver 8081:8080 -n airflow` 후 `http://localhost:8081`
    - Airflow 3.x: `airflow api-server -p 8081` 사용(기존 `webserver` 명령 제거됨)
    - Airflow 2.x: `airflow webserver -p 8081` 사용 가능
    - 포트 충돌 시 다른 포트로 시도(예: 8082)


## 참고

- 기존 Athena 중심 DAG 예시: services/data_pipeline_t2/dags/ad_hourly_summary.py, ad_daily_summary.py
- etl_summary_t2/requirements.txt를 Airflow 환경에 반영해야 에러 없이 실행됩니다.

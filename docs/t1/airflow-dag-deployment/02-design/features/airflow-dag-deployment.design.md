# airflow-dag-deployment Design

## 1. 전체 아키텍처

```
┌─────────────────────────────────────────────────────────────────┐
│  로컬 개발 환경                                                   │
│                                                                   │
│  services/report-generator/t3_report_generator/                  │
│  ├── Dockerfile          ← 신규 작성                             │
│  ├── requirements.txt    ← 신규 작성                             │
│  ├── main.py                                                     │
│  ├── athena_client.py                                            │
│  ├── markdown_builder.py                                         │
│  ├── pdf_exporter.py                                             │
│  └── slack_notifier.py                                           │
│           │                                                       │
│      docker build & push                                          │
└───────────┼───────────────────────────────────────────────────────┘
            ↓
┌─────────────────────────────────────────────────────────────────┐
│  ECR                                                             │
│  827913617635.dkr.ecr.ap-northeast-2.amazonaws.com/             │
│  capa-t3-report-generator:latest                                 │
└───────────┬─────────────────────────────────────────────────────┘
            ↓ image pull
┌─────────────────────────────────────────────────────────────────┐
│  EKS (namespace: airflow)                                        │
│                                                                   │
│  Airflow Scheduler                                               │
│       │ KubernetesPodOperator                                    │
│       ├── daily_report  Pod  ─┐                                  │
│       ├── weekly_report Pod  ─┤ capa-t3-report-generator:latest  │
│       ├── monthly_report Pod ─┤ + Secret(t3-report-secret)       │
│       └── notify_slack  Pod  ─┘ + IRSA(airflow-sa)              │
│                                        │                          │
│                                   Athena 조회                    │
│                                   PDF 생성                       │
│                                   Slack 전송                     │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│  GitHub (airflow-test 브랜치)                                    │
│  services/airflow-dags/                                          │
│  └── t3_report_generator_v3.py  ← 수정본 커밋                   │
│           ↓ gitSync (60초 주기)                                  │
│  Airflow DAGs 폴더 자동 반영                                     │
└─────────────────────────────────────────────────────────────────┘
```

---

## 2. Dockerfile 설계

**경로**: `services/report-generator/t3_report_generator/Dockerfile`

```dockerfile
FROM python:3.11-slim

USER root

# weasyprint 시스템 의존성 + 한글 폰트
RUN apt-get update && apt-get install -y \
    fonts-nanum \
    libpango-1.0-0 \
    libpangocairo-1.0-0 \
    libcairo2 \
    libgobject-2.0-0 \
    libgdk-pixbuf2.0-0 \
    libffi-dev \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# 작업 디렉토리 설정
WORKDIR /app

# 의존성 먼저 설치 (레이어 캐시 활용)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 모듈 파일 복사
COPY main.py .
COPY athena_client.py .
COPY markdown_builder.py .
COPY pdf_exporter.py .
COPY slack_notifier.py .
```

**빌드 컨텍스트**: `services/report-generator/t3_report_generator/` 디렉토리 기준

---

## 3. requirements.txt 설계

**경로**: `services/report-generator/t3_report_generator/requirements.txt`

```
boto3==1.34.0
pandas==2.2.0
matplotlib==3.8.4
weasyprint==68.1
reportlab==4.0.9
slack-bolt==1.18.0
python-dotenv==1.0.0
```

> 기존 `airflow-docker/requirements.txt`와 병합하여 단일 파일로 관리

---

## 4. DAG 파일 설계

**경로**: `services/airflow-dags/t3_report_generator_v3.py`

### 4.1 변경 포인트

| 항목 | 기존 (PythonOperator) | 신규 (KubernetesPodOperator) |
|------|----------------------|------------------------------|
| import | `PythonOperator` | `KubernetesPodOperator`, `V1EnvFromSource`, `V1SecretEnvSource` |
| sys.path.insert | 있음 | 제거 (이미지 내 `/app/`에 모듈 존재) |
| 실행 방식 | `python_callable=run_daily` | `cmds=["python", "-c", "..."]` |
| 환경변수 | 직접 주입 불가 | `env_from=[K8s Secret]` |
| namespace | 없음 | `namespace="airflow"` |

### 4.2 공통 설정

```python
from airflow import DAG
from airflow.providers.cncf.kubernetes.operators.pod import KubernetesPodOperator
from kubernetes.client import V1EnvFromSource, V1SecretEnvSource
from datetime import datetime, timedelta

ECR_IMAGE = "827913617635.dkr.ecr.ap-northeast-2.amazonaws.com/capa-t3-report-generator:latest"
NAMESPACE  = "airflow"
SA_NAME    = "airflow-sa"

# Secret에서 환경변수 일괄 주입
env_from = [
    V1EnvFromSource(
        secret_ref=V1SecretEnvSource(name="t3-report-secret")
    )
]

default_args = {
    "owner": "data-team",
    "retries": 2,
    "retry_delay": timedelta(minutes=5),
    "start_date": datetime(2026, 1, 1),
}

dag = DAG(
    dag_id="t3_report_generator_v3",
    default_args=default_args,
    description="T3 일간/주간/월간 보고서 자동 생성 및 Slack 발송",
    schedule_interval="0 23 * * *",  # UTC 23:00 = KST 08:00
    catchup=False,
    tags=["report-generator", "t3", "v3"],
)
```

### 4.3 Task 설계

```python
task_daily = KubernetesPodOperator(
    task_id="daily_report",
    name="t3-daily-report",
    namespace=NAMESPACE,
    image=ECR_IMAGE,
    cmds=["python", "-c"],
    arguments=["""
import sys, os
sys.path.insert(0, '/app')
from datetime import datetime
from main import generate_daily_report
date_str = datetime.now().strftime('%Y-%m-%d')
result = generate_daily_report(date_str, only_upload=True)
if result['status'] != 'success':
    raise Exception(f"일간 보고서 실패: {result.get('error')}")
print(f"일간 보고서 완료: {result['date']}")
"""],
    env_from=env_from,
    service_account_name=SA_NAME,
    get_logs=True,
    is_delete_operator_pod=True,
    dag=dag,
)

task_weekly = KubernetesPodOperator(
    task_id="weekly_report",
    name="t3-weekly-report",
    namespace=NAMESPACE,
    image=ECR_IMAGE,
    cmds=["python", "-c"],
    arguments=["""
import sys
sys.path.insert(0, '/app')
from datetime import datetime
from main import generate_weekly_report
if datetime.now().weekday() != 0:
    print("[주간] 월요일 아님, 스킵")
else:
    date_str = datetime.now().strftime('%Y-%m-%d')
    result = generate_weekly_report(date_str, only_upload=True)
    if result['status'] != 'success':
        raise Exception(f"주간 보고서 실패: {result.get('error')}")
    print(f"주간 보고서 완료: {result['date']}")
"""],
    env_from=env_from,
    service_account_name=SA_NAME,
    get_logs=True,
    is_delete_operator_pod=True,
    dag=dag,
)

task_monthly = KubernetesPodOperator(
    task_id="monthly_report",
    name="t3-monthly-report",
    namespace=NAMESPACE,
    image=ECR_IMAGE,
    cmds=["python", "-c"],
    arguments=["""
import sys
sys.path.insert(0, '/app')
from datetime import datetime
from main import generate_monthly_report
if datetime.now().day != 3:
    print("[월간] 3일 아님, 스킵")
else:
    date_str = datetime.now().strftime('%Y-%m-%d')
    result = generate_monthly_report(date_str, only_upload=True)
    if result['status'] != 'success':
        raise Exception(f"월간 보고서 실패: {result.get('error')}")
    print(f"월간 보고서 완료: {result['date']}")
"""],
    env_from=env_from,
    service_account_name=SA_NAME,
    get_logs=True,
    is_delete_operator_pod=True,
    dag=dag,
)

task_notify = KubernetesPodOperator(
    task_id="notify_slack",
    name="t3-notify-slack",
    namespace=NAMESPACE,
    image=ECR_IMAGE,
    cmds=["python", "-c"],
    arguments=["""
import sys
sys.path.insert(0, '/app')
from datetime import datetime
from main import send_final_notification
date_str = datetime.now().strftime('%Y-%m-%d')
send_final_notification(['daily', 'weekly', 'monthly'], date_str)
print("Slack 통합 알림 완료")
"""],
    env_from=env_from,
    service_account_name=SA_NAME,
    get_logs=True,
    is_delete_operator_pod=True,
    trigger_rule="all_done",
    dag=dag,
)

# Task 순서
task_daily >> task_weekly >> task_monthly >> task_notify
```

> **Note**: XCom은 KubernetesPodOperator 간 직접 사용 불가 → notify_slack은 항상 3가지 보고서 타입을 고정 전달하고, 내부적으로 Slack 채널 파일 유무로 판단

---

## 5. K8s Secret 설계

**이름**: `t3-report-secret`
**Namespace**: `airflow`

```yaml
apiVersion: v1
kind: Secret
metadata:
  name: t3-report-secret
  namespace: airflow
type: Opaque
stringData:
  SLACK_BOT_TOKEN: "<xoxb-...>"
  SLACK_CHANNEL_ID: "<C0XXXXXXXX>"
  FIXED_DASHBOARD_URL: "<http://...>"
  # 아래는 기본값이 있으므로 선택 (기본값 변경 필요 시만 설정)
  # ATHENA_S3_OUTPUT: "s3://capa-data-lake-827913617635/athena-results/"
  # GLUE_DATABASE: "capa_ad_logs"
  # GLUE_TABLE: "ad_combined_log_summary"
  # AWS_REGION: "ap-northeast-2"
```

**생성 명령 (kubectl)**:
```powershell
kubectl create secret generic t3-report-secret `
  --from-literal=SLACK_BOT_TOKEN="<token>" `
  --from-literal=SLACK_CHANNEL_ID="<channel_id>" `
  --from-literal=FIXED_DASHBOARD_URL="<url>" `
  -n airflow
```

---

## 6. ECR 리포지토리 설계

| 항목 | 값 |
|------|-----|
| 리포지토리명 | `capa-t3-report-generator` |
| 리전 | `ap-northeast-2` |
| URI | `827913617635.dkr.ecr.ap-northeast-2.amazonaws.com/capa-t3-report-generator` |
| 이미지 태그 | `latest` |
| 이미지 스캔 | 푸시 시 자동 스캔 활성화 권장 |

**생성 명령**:
```powershell
aws ecr create-repository `
  --repository-name capa-t3-report-generator `
  --region ap-northeast-2 `
  --image-scanning-configuration scanOnPush=true
```

---

## 7. IAM / IRSA 확인 항목

`airflow-sa` 서비스 어카운트의 IAM Role에 아래 권한이 있어야 합니다.

```json
{
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "athena:StartQueryExecution",
        "athena:GetQueryExecution",
        "athena:GetQueryResults",
        "athena:StopQueryExecution"
      ],
      "Resource": "*"
    },
    {
      "Effect": "Allow",
      "Action": [
        "s3:GetObject",
        "s3:PutObject",
        "s3:ListBucket",
        "s3:GetBucketLocation"
      ],
      "Resource": [
        "arn:aws:s3:::capa-data-lake-827913617635",
        "arn:aws:s3:::capa-data-lake-827913617635/*"
      ]
    },
    {
      "Effect": "Allow",
      "Action": [
        "glue:GetDatabase",
        "glue:GetTable",
        "glue:GetPartition",
        "glue:GetPartitions"
      ],
      "Resource": "*"
    },
    {
      "Effect": "Allow",
      "Action": [
        "ecr:GetAuthorizationToken",
        "ecr:BatchCheckLayerAvailability",
        "ecr:GetDownloadUrlForLayer",
        "ecr:BatchGetImage"
      ],
      "Resource": "*"
    }
  ]
}
```

> ECR Pull 권한은 Node IAM Role에도 있으므로 별도 추가 불필요할 수 있음. 확인 필요.

---

## 8. 파일 변경 목록 (Do Phase 참조용)

| 작업 | 파일 경로 | 유형 |
|------|----------|------|
| 신규 생성 | `services/report-generator/t3_report_generator/Dockerfile` | Docker |
| 신규/수정 | `services/report-generator/t3_report_generator/requirements.txt` | Python 의존성 |
| 신규 생성 | `services/airflow-dags/t3_report_generator_v3.py` | DAG (KubernetesPodOperator 버전) |
| 수동 생성 | K8s Secret `t3-report-secret` in `airflow` namespace | K8s 리소스 |
| 수정 | `infrastructure/helm-values/airflow.yaml` | Helm Values (extraEnvFrom 추가) |

---

## 9. 배포 흐름 시퀀스

```
1. ECR 리포지토리 생성
        ↓
2. Dockerfile + requirements.txt 작성
        ↓
3. docker build (로컬)
        ↓
4. ECR 로그인 → docker push
        ↓
5. K8s Secret 생성 (kubectl)
        ↓
6. DAG 파일 수정 (PythonOperator → KubernetesPodOperator)
        ↓
7. airflow-test 브랜치에 커밋 · 푸시
        ↓
8. gitSync 자동 반영 (최대 60초)
        ↓
9. Airflow UI → DAG 로드 확인
        ↓
10. 수동 트리거 → Pod 기동 → 로그 확인 → Slack 수신
```

---

## 10. 완료 기준 (Design 관점)

- [ ] Dockerfile이 로컬에서 빌드 성공 (`docker build` 오류 없음)
- [ ] ECR에 이미지 푸시 완료 및 이미지 확인 가능
- [ ] DAG 파일이 Airflow UI에서 파싱 오류 없이 로드
- [ ] KubernetesPodOperator Pod가 `airflow` namespace에서 정상 기동
- [ ] Secret의 환경변수가 Pod 내부에서 정상 참조
- [ ] Athena 쿼리 성공 → PDF 생성 → Slack 업로드 확인

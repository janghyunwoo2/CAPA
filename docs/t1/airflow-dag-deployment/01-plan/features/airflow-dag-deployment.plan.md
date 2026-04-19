# airflow-dag-deployment Plan

## Executive Summary

| 항목 | 내용 |
|------|------|
| Feature | airflow-dag-deployment |
| 작성일 | 2026-03-21 |
| 담당자 | t1 |
| Phase | Plan |

### 4-Perspective Summary

| 관점 | 내용 |
|------|------|
| **Problem** | t3_report_generator_v3.py는 무거운 Python 의존성(weasyprint, matplotlib 등)과 다중 모듈 파일을 필요로 하나, EKS Airflow 기본 이미지에는 포함되어 있지 않다. |
| **Solution** | 전용 Docker 이미지(capa-t3-report-generator)를 ECR에 빌드·푸시하고, DAG은 KubernetesPodOperator로 각 Task마다 해당 이미지의 Pod를 실행한다. |
| **Function UX Effect** | Airflow Worker에 의존성을 설치하지 않으므로 기존 Airflow 운영 환경에 영향 없이 독립적으로 배포·운영 가능하다. |
| **Core Value** | 1회 이미지 빌드로 daily/weekly/monthly/notify 4개 Task가 동일 이미지를 재사용하며, 이후 로직 변경 시 이미지만 재빌드하면 된다. |

---

## 1. 배경 및 목표

### 1.1 현황
- EKS에 Apache Airflow 2.9.3이 실행 중 (LocalExecutor, Helm 배포)
- DAG 동기화: gitSync → `airflow-test` 브랜치 → `services/airflow-dags/` 경로
- `t3_report_generator_v3.py`는 로컬 테스트 완료 상태 (PythonOperator 기반)
- 해당 DAG은 `sys.path.insert(0, '/opt/airflow/parent/report-generator/t3_report_generator')` 방식으로 내부 모듈을 import

### 1.2 문제
| 문제 | 설명 |
|------|------|
| 모듈 파일 부재 | gitSync는 `services/airflow-dags/`만 동기화 → `main.py`, `athena_client.py` 등 모듈 없음 |
| 의존성 미설치 | `weasyprint`, `matplotlib`, `reportlab`, `pandas`, `slack-bolt` 등 기본 Airflow 이미지에 미포함 |
| 시스템 패키지 | weasyprint는 `libpango`, `libcairo`, `fonts-nanum` 등 OS 패키지 필요 |

### 1.3 목표
- `t3_report_generator_v3.py`를 **EKS Airflow에서 정상 실행**
- Airflow 기본 이미지 변경 없이 독립 배포
- 일간/주간/월간 보고서 생성 및 Slack 알림 자동화

---

## 2. 배포 전략

### 2.1 선택 방식: ECR 이미지 + KubernetesPodOperator

```
[로컬] Dockerfile 빌드
    python:3.11-slim
    + OS 패키지 (fonts-nanum, libpango, libcairo 등)
    + Python 의존성 (boto3, pandas, weasyprint, matplotlib, reportlab, slack-bolt)
    + 모듈 파일 COPY (main.py, athena_client.py, markdown_builder.py, pdf_exporter.py, slack_notifier.py)
         ↓
[ECR] 827913617635.dkr.ecr.ap-northeast-2.amazonaws.com/capa-t3-report-generator:latest
         ↓
[EKS] KubernetesPodOperator → 각 Task마다 해당 이미지의 Pod 실행
         ↓
[결과] Athena 조회 → PDF 생성 → Slack 전송
```

### 2.2 이미지 재사용 구조

```
이미지: capa-t3-report-generator:latest (1개)
    ├── task_daily   → python -c "from main import generate_daily_report; ..."
    ├── task_weekly  → python -c "from main import generate_weekly_report; ..."
    ├── task_monthly → python -c "from main import generate_monthly_report; ..."
    └── task_notify  → python -c "from main import send_final_notification; ..."
```

### 2.3 기존 방식과 비교

| 항목 | PythonOperator (기존) | KubernetesPodOperator (신규) |
|------|----------------------|------------------------------|
| 실행 위치 | Airflow Worker 프로세스 내 | 독립 K8s Pod |
| 의존성 관리 | Airflow 이미지에 포함 필요 | 전용 이미지에 포함 |
| Airflow 이미지 변경 | 필요 | 불필요 |
| 장애 격리 | Worker 프로세스 공유 | Pod 단위 격리 |
| 확장성 | Worker 리소스 공유 | Task별 독립 리소스 할당 가능 |

---

## 3. 구현 범위 (Scope)

### 3.1 신규 생성 파일

| 파일 | 경로 | 설명 |
|------|------|------|
| `Dockerfile` | `services/report-generator/t3_report_generator/` | 전용 이미지 빌드 설정 |
| `requirements.txt` | `services/report-generator/t3_report_generator/` | Python 의존성 (기존 파일 확인 후 갱신) |
| `t3_report_generator_v3.py` | `services/airflow-dags/` | KubernetesPodOperator 버전 (gitSync 대상) |

### 3.2 수정 파일

| 파일 | 경로 | 변경 내용 |
|------|------|-----------|
| `airflow.yaml` | `infrastructure/helm-values/` | extraEnvFrom으로 Secret 주입 추가 |

### 3.3 K8s 리소스 (수동 생성)

| 리소스 | 이름 | Namespace | 내용 |
|--------|------|-----------|------|
| Secret | `t3-report-secret` | `airflow` | SLACK_BOT_TOKEN, SLACK_CHANNEL_ID, FIXED_DASHBOARD_URL |

### 3.4 제외 범위

- Airflow 기본 이미지 변경 없음
- Terraform 신규 리소스 없음 (ECR 리포지토리만 AWS CLI로 생성)
- 기존 DAG 파일 (`t3_report_generator_v3.py` 원본) 구조 변경 최소화

---

## 4. 기술 스펙

### 4.1 Docker 이미지

| 항목 | 값 |
|------|-----|
| Base 이미지 | `python:3.11-slim` |
| ECR 리포지토리 | `capa-t3-report-generator` |
| ECR URI | `827913617635.dkr.ecr.ap-northeast-2.amazonaws.com/capa-t3-report-generator` |
| 태그 전략 | `latest` (초기 배포), 이후 날짜 태그 병행 권장 |
| 작업 디렉토리 | `/app` |

### 4.2 Python 의존성

| 패키지 | 버전 | 용도 |
|--------|------|------|
| boto3 | latest | Athena API 호출 |
| pandas | 2.2.0 | 쿼리 결과 처리 |
| matplotlib | 3.8.4 | 차트 생성 |
| weasyprint | 68.1 | PDF 생성 |
| reportlab | 4.0.9 | PDF 생성 보조 |
| slack-bolt | 1.18.0 | Slack 파일 업로드 |
| python-dotenv | latest | 환경변수 로드 |

### 4.3 OS 패키지 (weasyprint 의존)

```
fonts-nanum, libpango-1.0-0, libcairo2, libgobject-2.0-0,
libpangocairo-1.0-0, libffi-dev, libgdk-pixbuf2.0-0
```

### 4.4 환경변수 (K8s Secret → Pod 주입)

| 변수명 | 기본값 | 필수 여부 |
|--------|--------|----------|
| `SLACK_BOT_TOKEN` | - | 필수 |
| `SLACK_CHANNEL_ID` | - | 필수 |
| `FIXED_DASHBOARD_URL` | - | 선택 |
| `ATHENA_S3_OUTPUT` | `s3://capa-data-lake-827913617635/athena-results/` | 선택 |
| `GLUE_DATABASE` | `capa_ad_logs` | 선택 |
| `GLUE_TABLE` | `ad_combined_log_summary` | 선택 |
| `AWS_REGION` | `ap-northeast-2` | 선택 |

### 4.5 KubernetesPodOperator 공통 설정

```python
namespace       = "airflow"
image           = "827913617635.dkr.ecr.ap-northeast-2.amazonaws.com/capa-t3-report-generator:latest"
service_account_name = "airflow-sa"   # IRSA → Athena + S3 권한 상속
get_logs        = True
is_delete_operator_pod = True         # 완료 후 Pod 자동 삭제
env_from        = [K8s Secret: t3-report-secret]
```

---

## 5. 배포 단계 (Implementation Plan)

### Phase 1: 이미지 빌드 및 ECR 푸시

| 순서 | 작업 | 명령 |
|------|------|------|
| 1 | ECR 리포지토리 생성 | `aws ecr create-repository --repository-name capa-t3-report-generator --region ap-northeast-2` |
| 2 | ECR 로그인 | `aws ecr get-login-password ... \| docker login ...` |
| 3 | Dockerfile 작성 | `services/report-generator/t3_report_generator/Dockerfile` |
| 4 | 이미지 빌드 | `docker build -t capa-t3-report-generator:latest .` |
| 5 | 이미지 태그 | `docker tag capa-t3-report-generator:latest <ECR_URI>:latest` |
| 6 | ECR 푸시 | `docker push <ECR_URI>:latest` |

### Phase 2: DAG 파일 수정 및 gitSync 배포

| 순서 | 작업 | 설명 |
|------|------|------|
| 1 | DAG 수정 | PythonOperator → KubernetesPodOperator로 전환 |
| 2 | 파일 복사 | `services/airflow-dags/t3_report_generator_v3.py` |
| 3 | `airflow-test` 브랜치에 커밋·푸시 | gitSync가 자동으로 Airflow에 반영 |

### Phase 3: K8s Secret 생성

```powershell
kubectl create secret generic t3-report-secret `
  --from-literal=SLACK_BOT_TOKEN="<token>" `
  --from-literal=SLACK_CHANNEL_ID="<channel_id>" `
  --from-literal=FIXED_DASHBOARD_URL="<url>" `
  -n airflow
```

### Phase 4: 검증

| 순서 | 검증 항목 | 방법 |
|------|----------|------|
| 1 | DAG 로드 확인 | Airflow UI → DAGs 목록에 `t3_report_generator_v3` 표시 |
| 2 | DAG 수동 트리거 | Airflow UI → Trigger DAG |
| 3 | Pod 기동 확인 | `kubectl get pods -n airflow -w` |
| 4 | 로그 확인 | `kubectl logs -n airflow <pod-name>` |
| 5 | Slack 알림 수신 | 지정 채널에서 PDF 보고서 수신 확인 |

---

## 6. IRSA 권한 확인

`airflow-sa` 서비스 어카운트에 아래 IAM 권한이 필요합니다. (기존 IRSA 설정 확인 후 부족한 항목 추가)

| AWS 서비스 | 필요 권한 |
|-----------|----------|
| Athena | `athena:StartQueryExecution`, `athena:GetQueryExecution`, `athena:GetQueryResults` |
| S3 | `s3:GetObject`, `s3:PutObject`, `s3:ListBucket` (athena-results 버킷) |
| Glue | `glue:GetTable`, `glue:GetDatabase`, `glue:GetPartition` |

---

## 7. 위험 요소 및 대응

| 위험 | 가능성 | 대응 |
|------|--------|------|
| weasyprint 빌드 실패 (OS 패키지 누락) | 중 | Dockerfile에 필요한 apt 패키지 명시적 나열, 로컬 빌드 테스트 선행 |
| ECR ImagePullBackOff | 낮 | EKS Node IAM Role에 ECR Pull 권한 확인 (`ecr:GetAuthorizationToken`, `ecr:BatchGetImage`) |
| Athena 권한 오류 | 낮 | airflow-sa IRSA Role에 Athena/S3/Glue 권한 사전 확인 |
| gitSync 브랜치 미반영 | 낮 | `airflow-test` 브랜치에 정확히 커밋, gitSync wait: 60초 대기 |
| Pod OOMKill | 낮 | 필요 시 KubernetesPodOperator에 `resources` 파라미터 추가 (memory: 1Gi) |

---

## 8. 완료 기준 (Definition of Done)

- [ ] ECR에 `capa-t3-report-generator:latest` 이미지 푸시 완료
- [ ] `airflow-test` 브랜치에 수정된 DAG 파일 반영 완료
- [ ] Airflow UI에서 DAG 로드 오류 없음
- [ ] DAG 수동 트리거 시 4개 Task 모두 Success
- [ ] Slack 채널에 PDF 보고서 수신 확인

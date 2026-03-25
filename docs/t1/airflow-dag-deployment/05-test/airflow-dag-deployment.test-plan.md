# [Test Plan] airflow-dag-deployment

| 항목 | 내용 |
|------|------|
| **Feature** | airflow-dag-deployment |
| **테스트 방법** | TDD — pytest 단위 테스트 (파일 내용 파싱 방식) |
| **참고 설계서** | `docs/t1/airflow-dag-deployment/02-design/features/airflow-dag-deployment.design.md` |
| **작성일** | 2026-03-21 |
| **담당자** | t1 |

> **비고**: Airflow/Kubernetes 패키지가 로컬에 미설치된 환경을 고려해,
> DAG 파일을 import하지 않고 소스코드 문자열을 파싱하는 방식으로 검증합니다.

---

## 테스트 케이스 목록

### [DAG 파일] `services/airflow-dags/t3_report_generator_v3.py`

---

### TC-AD-01: DAG 파일 존재 확인

| 항목 | 내용 |
|------|------|
| **목적** | KubernetesPodOperator 버전 DAG 파일이 gitSync 대상 경로에 존재하는지 확인 |
| **사전 조건** | `services/airflow-dags/` 디렉토리 존재 |
| **테스트 입력** | 파일 경로: `services/airflow-dags/t3_report_generator_v3.py` |
| **기대 결과** | 파일이 존재함 |
| **검증 코드** | `assert os.path.isfile(dag_file)` |

---

### TC-AD-02: KubernetesPodOperator import 사용

| 항목 | 내용 |
|------|------|
| **목적** | PythonOperator 대신 KubernetesPodOperator를 import하고 사용하는지 확인 |
| **사전 조건** | TC-AD-01 PASS |
| **테스트 입력** | DAG 파일 소스코드 |
| **기대 결과** | `KubernetesPodOperator` 문자열 및 정확한 import 경로 포함 |
| **검증 코드** | `assert "KubernetesPodOperator" in dag_content` |

---

### TC-AD-03: ECR 이미지 URI 정확성

| 항목 | 내용 |
|------|------|
| **목적** | ECR 이미지 URI가 설계서 명세와 정확히 일치하는지 확인 |
| **사전 조건** | TC-AD-01 PASS |
| **테스트 입력** | DAG 파일 소스코드 |
| **기대 결과** | `827913617635.dkr.ecr.ap-northeast-2.amazonaws.com/capa-t3-report-generator:latest` 포함 |
| **검증 코드** | `assert ECR_URI in dag_content` |

---

### TC-AD-04: dag_id 정확성

| 항목 | 내용 |
|------|------|
| **목적** | dag_id가 설계서 명세와 일치하는지 확인 |
| **사전 조건** | TC-AD-01 PASS |
| **테스트 입력** | DAG 파일 소스코드 |
| **기대 결과** | `dag_id="t3_report_generator_v3"` 포함 |
| **검증 코드** | `assert 't3_report_generator_v3' in dag_content` |

---

### TC-AD-05: schedule_interval UTC 23:00

| 항목 | 내용 |
|------|------|
| **목적** | KST 08:00에 실행되도록 UTC 23:00 설정 확인 |
| **사전 조건** | TC-AD-01 PASS |
| **테스트 입력** | DAG 파일 소스코드 |
| **기대 결과** | `"0 23 * * *"` cron 표현식 포함 |
| **검증 코드** | `assert '"0 23 * * *"' in dag_content` |

---

### TC-AD-06: catchup=False 설정

| 항목 | 내용 |
|------|------|
| **목적** | 과거 실행 보완(backfill) 방지 설정 확인 |
| **사전 조건** | TC-AD-01 PASS |
| **테스트 입력** | DAG 파일 소스코드 |
| **기대 결과** | `catchup=False` 포함 |
| **검증 코드** | `assert "catchup=False" in dag_content` |

---

### TC-AD-07: 4개 Task ID 존재

| 항목 | 내용 |
|------|------|
| **목적** | 일간/주간/월간/알림 4개 Task가 모두 정의되어 있는지 확인 |
| **사전 조건** | TC-AD-01 PASS |
| **테스트 입력** | DAG 파일 소스코드 |
| **기대 결과** | `daily_report`, `weekly_report`, `monthly_report`, `notify_slack` 모두 포함 |
| **검증 코드** | `assert task_id in dag_content for task_id in [...]` |

---

### TC-AD-08: t3-report-secret env_from 참조

| 항목 | 내용 |
|------|------|
| **목적** | Slack 토큰 등 민감 정보를 K8s Secret에서 env_from으로 주입하는지 확인 |
| **사전 조건** | TC-AD-01 PASS |
| **테스트 입력** | DAG 파일 소스코드 |
| **기대 결과** | `t3-report-secret`, `V1SecretEnvSource`, `env_from` 포함 |
| **검증 코드** | `assert "t3-report-secret" in dag_content` |

---

### TC-AD-09: service_account_name = airflow-sa

| 항목 | 내용 |
|------|------|
| **목적** | IRSA를 통해 Athena/S3 권한을 상속받는 SA 설정 확인 |
| **사전 조건** | TC-AD-01 PASS |
| **테스트 입력** | DAG 파일 소스코드 |
| **기대 결과** | `service_account_name`, `airflow-sa` 모두 포함 |
| **검증 코드** | `assert "airflow-sa" in dag_content` |

---

### TC-AD-10: is_delete_operator_pod=True

| 항목 | 내용 |
|------|------|
| **목적** | Task 완료 후 Pod 자동 삭제 설정 확인 (리소스 낭비 방지) |
| **사전 조건** | TC-AD-01 PASS |
| **테스트 입력** | DAG 파일 소스코드 |
| **기대 결과** | `is_delete_operator_pod=True` 포함 |
| **검증 코드** | `assert "is_delete_operator_pod=True" in dag_content` |

---

### TC-AD-11: notify_slack trigger_rule="all_done"

| 항목 | 내용 |
|------|------|
| **목적** | 앞선 Task 실패와 무관하게 알림은 항상 실행되는지 확인 |
| **사전 조건** | TC-AD-01 PASS |
| **테스트 입력** | DAG 파일 소스코드 |
| **기대 결과** | `trigger_rule="all_done"` 또는 `trigger_rule='all_done'` 포함 |
| **검증 코드** | `assert 'trigger_rule="all_done"' in dag_content` |

---

### TC-AD-12: Task 의존성 체인 (>>)

| 항목 | 내용 |
|------|------|
| **목적** | daily → weekly → monthly → notify 순서로 의존성이 설정되었는지 확인 |
| **사전 조건** | TC-AD-01 PASS |
| **테스트 입력** | DAG 파일 소스코드 |
| **기대 결과** | `>>` 연산자 3회 이상 사용 |
| **검증 코드** | `assert dag_content.count(">>") >= 3` |

---

### [Dockerfile] `services/airflow-dags/docker/t3-report-generator/Dockerfile`

---

### TC-AD-13: FROM python:3.11-slim

| 항목 | 내용 |
|------|------|
| **목적** | 베이스 이미지가 설계서 명세와 일치하는지 확인 |
| **사전 조건** | Dockerfile 존재 |
| **테스트 입력** | Dockerfile 소스코드 |
| **기대 결과** | `FROM python:3.11-slim` 포함 |
| **검증 코드** | `assert "FROM python:3.11-slim" in dockerfile_content` |

---

### TC-AD-14: WORKDIR /app

| 항목 | 내용 |
|------|------|
| **목적** | 작업 디렉토리가 `/app`으로 설정되었는지 확인 |
| **사전 조건** | Dockerfile 존재 |
| **테스트 입력** | Dockerfile 소스코드 |
| **기대 결과** | `WORKDIR /app` 포함 |
| **검증 코드** | `assert "WORKDIR /app" in dockerfile_content` |

---

### TC-AD-15: weasyprint 의존 OS 패키지 6종

| 항목 | 내용 |
|------|------|
| **목적** | weasyprint 실행에 필요한 libpango/libcairo 계열 OS 패키지가 모두 설치되는지 확인 |
| **사전 조건** | Dockerfile 존재 |
| **테스트 입력** | Dockerfile 소스코드 |
| **기대 결과** | `libpango-1.0-0`, `libpangocairo-1.0-0`, `libcairo2`, `libgobject-2.0-0`, `libgdk-pixbuf2.0-0`, `libffi-dev` 모두 포함 |
| **검증 코드** | `assert pkg in dockerfile_content for pkg in REQUIRED_OS_PACKAGES` |

---

### TC-AD-16: requirements.txt COPY → pip install 순서

| 항목 | 내용 |
|------|------|
| **목적** | Docker 레이어 캐시를 활용하도록 COPY가 pip install 이전에 위치하는지 확인 |
| **사전 조건** | Dockerfile 존재 |
| **테스트 입력** | Dockerfile 소스코드 |
| **기대 결과** | `COPY requirements.txt`의 위치 인덱스 < `pip install`의 위치 인덱스 |
| **검증 코드** | `assert copy_idx < pip_idx` |

---

### [requirements.txt] `services/airflow-dags/docker/t3-report-generator/requirements.txt`

---

### TC-AD-17: weasyprint==68.1 포함

| 항목 | 내용 |
|------|------|
| **목적** | PDF 생성 핵심 패키지가 설계서 버전으로 포함되었는지 확인 |
| **사전 조건** | requirements.txt 존재 |
| **테스트 입력** | requirements.txt 내용 |
| **기대 결과** | `weasyprint==68.1` 포함 |
| **검증 코드** | `assert "weasyprint==68.1" in requirements_content` |

---

### TC-AD-18: boto3==1.34.0 포함

| 항목 | 내용 |
|------|------|
| **목적** | Athena API 호출 패키지가 설계서 버전으로 포함되었는지 확인 |
| **사전 조건** | requirements.txt 존재 |
| **테스트 입력** | requirements.txt 내용 |
| **기대 결과** | `boto3==1.34.0` 포함 |
| **검증 코드** | `assert "boto3==1.34.0" in requirements_content` |

---

### TC-AD-19: pandas==2.2.0 포함

| 항목 | 내용 |
|------|------|
| **목적** | 쿼리 결과 처리 패키지 버전 확인 |
| **사전 조건** | requirements.txt 존재 |
| **테스트 입력** | requirements.txt 내용 |
| **기대 결과** | `pandas==2.2.0` 포함 |
| **검증 코드** | `assert "pandas==2.2.0" in requirements_content` |

---

### TC-AD-20: matplotlib==3.8.4 포함

| 항목 | 내용 |
|------|------|
| **목적** | 차트 생성 패키지 버전 확인 |
| **사전 조건** | requirements.txt 존재 |
| **테스트 입력** | requirements.txt 내용 |
| **기대 결과** | `matplotlib==3.8.4` 포함 |
| **검증 코드** | `assert "matplotlib==3.8.4" in requirements_content` |

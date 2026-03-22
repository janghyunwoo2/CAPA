# [Test Result] airflow-dag-deployment

| 항목 | 내용 |
|------|------|
| **Feature** | airflow-dag-deployment |
| **테스트 실행일** | 2026-03-21 |
| **테스트 방법** | TDD — pytest 단위 테스트 (파일 내용 파싱 방식) |
| **최종 결과** | ✅ 20/20 PASS |
| **실행 시간** | 0.09s |

---

## TDD 사이클 요약

### 🔴 Red Phase

| 항목 | 내용 |
|------|------|
| **FAIL 수** | 7 FAIL + 11 ERROR = 18개 미통과 |
| **PASS 수** | 2개 (TC-AD-13, TC-AD-14) |
| **주요 원인** | DAG 파일(`t3_report_generator_v3.py`) 미존재, Dockerfile OS 패키지 6종 누락, requirements.txt 버전 불일치(weasyprint 미포함) |

### ✅ Green Phase

| 항목 | 내용 |
|------|------|
| **수정 내용** | DAG 파일 신규 생성, Dockerfile 신규 생성(KPO 전용), requirements.txt 신규 생성(KPO 전용) |
| **변경 전략** | 기존 `services/report-generator/t3_report_generator/` 파일은 타 팀원 코드이므로 수정하지 않고, `services/airflow-dags/docker/t3-report-generator/`에 KPO 전용 파일 신규 생성 |
| **최종 결과** | 20/20 PASS |

---

## 테스트 결과 테이블

| TC | Step | 스텝 역할 | 인풋 | 아웃풋 (실제값) | assert 단언 | 판정 | 왜 이렇게 나왔나 |
|----|------|-----------|------|----------------|-------------|------|-----------------|
| TC-AD-01 | - | DAG 파일 존재 확인 | `services/airflow-dags/t3_report_generator_v3.py` | 파일 존재 | `assert os.path.isfile(dag_file)` | ✅ PASS | 신규 DAG 파일 생성 완료 |
| TC-AD-02 | - | KPO import 확인 | DAG 소스코드 | `KubernetesPodOperator` 포함 | `assert "KubernetesPodOperator" in dag_content` | ✅ PASS | KPO import 및 사용 확인 |
| TC-AD-03 | - | ECR URI 정확성 | DAG 소스코드 | ECR URI 포함 | `assert ECR_URI in dag_content` | ✅ PASS | 827913617635.dkr.ecr.ap-northeast-2.amazonaws.com/capa-t3-report-generator:latest 일치 |
| TC-AD-04 | - | dag_id 정확성 | DAG 소스코드 | `t3_report_generator_v3` 포함 | `assert 't3_report_generator_v3' in dag_content` | ✅ PASS | dag_id 설계서와 일치 |
| TC-AD-05 | - | schedule_interval | DAG 소스코드 | `"0 23 * * *"` 포함 | `assert '"0 23 * * *"' in dag_content` | ✅ PASS | UTC 23:00 = KST 08:00 설정 확인 |
| TC-AD-06 | - | catchup=False | DAG 소스코드 | `catchup=False` 포함 | `assert "catchup=False" in dag_content` | ✅ PASS | backfill 방지 설정 확인 |
| TC-AD-07 | - | 4개 Task ID | DAG 소스코드 | 4개 task_id 모두 포함 | `assert task_id in dag_content` | ✅ PASS | daily/weekly/monthly/notify_slack 모두 확인 |
| TC-AD-08 | - | env_from Secret | DAG 소스코드 | `t3-report-secret`, `V1SecretEnvSource` 포함 | `assert "t3-report-secret" in dag_content` | ✅ PASS | K8s Secret 환경변수 주입 설계 확인 |
| TC-AD-09 | - | service_account_name | DAG 소스코드 | `airflow-sa` 포함 | `assert "airflow-sa" in dag_content` | ✅ PASS | IRSA SA 설정 확인 |
| TC-AD-10 | - | is_delete_operator_pod | DAG 소스코드 | `is_delete_operator_pod=True` 포함 | `assert "is_delete_operator_pod=True" in dag_content` | ✅ PASS | Pod 자동 삭제 설정 확인 |
| TC-AD-11 | - | trigger_rule all_done | DAG 소스코드 | `trigger_rule="all_done"` 포함 | `assert 'trigger_rule="all_done"' in dag_content` | ✅ PASS | notify_slack 항상 실행 설정 확인 |
| TC-AD-12 | - | Task 의존성 체인 | DAG 소스코드 | `>>` 3회 이상 | `assert dag_content.count(">>") >= 3` | ✅ PASS | daily>>weekly>>monthly>>notify 체인 확인 |
| TC-AD-13 | - | FROM python:3.11-slim | Dockerfile 소스코드 | `FROM python:3.11-slim` 포함 | `assert "FROM python:3.11-slim" in dockerfile_content` | ✅ PASS | 베이스 이미지 설계서 일치 |
| TC-AD-14 | - | WORKDIR /app | Dockerfile 소스코드 | `WORKDIR /app` 포함 | `assert "WORKDIR /app" in dockerfile_content` | ✅ PASS | 작업 디렉토리 설정 확인 |
| TC-AD-15 | - | OS 패키지 6종 | Dockerfile 소스코드 | 6종 패키지 모두 포함 | `assert pkg in dockerfile_content` | ✅ PASS | libpango/libcairo/libgobject/libgdk-pixbuf/libffi/libpangocairo 확인 |
| TC-AD-16 | - | COPY→pip 순서 | Dockerfile 소스코드 | copy_idx < pip_idx | `assert copy_idx < pip_idx` | ✅ PASS | 레이어 캐시 최적화 순서 확인 |
| TC-AD-17 | - | weasyprint==68.1 | requirements.txt | `weasyprint==68.1` 포함 | `assert "weasyprint==68.1" in requirements_content` | ✅ PASS | PDF 생성 핵심 패키지 버전 확인 |
| TC-AD-18 | - | boto3==1.34.0 | requirements.txt | `boto3==1.34.0` 포함 | `assert "boto3==1.34.0" in requirements_content` | ✅ PASS | Athena API 패키지 버전 확인 |
| TC-AD-19 | - | pandas==2.2.0 | requirements.txt | `pandas==2.2.0` 포함 | `assert "pandas==2.2.0" in requirements_content` | ✅ PASS | 데이터 처리 패키지 버전 확인 |
| TC-AD-20 | - | matplotlib==3.8.4 | requirements.txt | `matplotlib==3.8.4` 포함 | `assert "matplotlib==3.8.4" in requirements_content` | ✅ PASS | 차트 생성 패키지 버전 확인 |

---

## pytest 실행 로그

```
============================= test session starts =============================
platform win32 -- Python 3.13.5, pytest-8.3.4, pluggy-1.5.0
rootdir: C:\Users\3571\Desktop\projects\CAPA\services\airflow-dags
configfile: pytest.ini
collected 20 items

tests/unit_airflow_dag_deploy/test_airflow_dag_deploy.py::TestDagFile::test_dag_file_exists PASSED [  5%]
tests/unit_airflow_dag_deploy/test_airflow_dag_deploy.py::TestDagFile::test_uses_kubernetes_pod_operator PASSED [ 10%]
tests/unit_airflow_dag_deploy/test_airflow_dag_deploy.py::TestDagFile::test_ecr_image_uri PASSED [ 15%]
tests/unit_airflow_dag_deploy/test_airflow_dag_deploy.py::TestDagFile::test_dag_id PASSED [ 20%]
tests/unit_airflow_dag_deploy/test_airflow_dag_deploy.py::TestDagFile::test_schedule_interval_utc_23 PASSED [ 25%]
tests/unit_airflow_dag_deploy/test_airflow_dag_deploy.py::TestDagFile::test_catchup_false PASSED [ 30%]
tests/unit_airflow_dag_deploy/test_airflow_dag_deploy.py::TestDagFile::test_four_task_ids PASSED [ 35%]
tests/unit_airflow_dag_deploy/test_airflow_dag_deploy.py::TestDagFile::test_env_from_secret PASSED [ 40%]
tests/unit_airflow_dag_deploy/test_airflow_dag_deploy.py::TestDagFile::test_service_account_name PASSED [ 45%]
tests/unit_airflow_dag_deploy/test_airflow_dag_deploy.py::TestDagFile::test_is_delete_operator_pod PASSED [ 50%]
tests/unit_airflow_dag_deploy/test_airflow_dag_deploy.py::TestDagFile::test_notify_trigger_rule_all_done PASSED [ 55%]
tests/unit_airflow_dag_deploy/test_airflow_dag_deploy.py::TestDagFile::test_task_dependency_chain PASSED [ 60%]
tests/unit_airflow_dag_deploy/test_airflow_dag_deploy.py::TestDockerfile::test_base_image PASSED [ 65%]
tests/unit_airflow_dag_deploy/test_airflow_dag_deploy.py::TestDockerfile::test_workdir_app PASSED [ 70%]
tests/unit_airflow_dag_deploy/test_airflow_dag_deploy.py::TestDockerfile::test_required_os_packages PASSED [ 75%]
tests/unit_airflow_dag_deploy/test_airflow_dag_deploy.py::TestDockerfile::test_requirements_copy_before_pip PASSED [ 80%]
tests/unit_airflow_dag_deploy/test_airflow_dag_deploy.py::TestRequirements::test_weasyprint_version PASSED [ 85%]
tests/unit_airflow_dag_deploy/test_airflow_dag_deploy.py::TestRequirements::test_boto3_version PASSED [ 90%]
tests/unit_airflow_dag_deploy/test_airflow_dag_deploy.py::TestRequirements::test_pandas_version PASSED [ 95%]
tests/unit_airflow_dag_deploy/test_airflow_dag_deploy.py::TestRequirements::test_matplotlib_version PASSED [100%]

============================= 20 passed in 0.09s ==============================
```

---

TDD Do 완료. 다음 단계: `/pdca analyze airflow-dag-deployment`

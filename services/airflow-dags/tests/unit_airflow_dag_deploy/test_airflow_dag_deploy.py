"""
airflow-dag-deployment 단위 테스트

TC 목록:
  [DAG 파일]
  TC-AD-01: 파일 존재 확인
  TC-AD-02: KubernetesPodOperator import 사용
  TC-AD-03: ECR 이미지 URI 정확성
  TC-AD-04: dag_id 정확성
  TC-AD-05: schedule_interval (UTC 23:00)
  TC-AD-06: catchup=False 설정
  TC-AD-07: 4개 Task ID 존재 (daily/weekly/monthly/notify)
  TC-AD-08: t3-report-secret env_from 참조
  TC-AD-09: service_account_name = "airflow-sa"
  TC-AD-10: is_delete_operator_pod=True
  TC-AD-11: notify_slack trigger_rule="all_done"
  TC-AD-12: Task 의존성 체인 (>> 연산자)

  [Dockerfile]
  TC-AD-13: FROM python:3.11-slim
  TC-AD-14: WORKDIR /app
  TC-AD-15: OS 패키지 6종 포함 (libpango, libcairo, libgobject, libgdk-pixbuf, libffi, libpangocairo)
  TC-AD-16: requirements.txt COPY 후 pip install 순서

  [requirements.txt]
  TC-AD-17: weasyprint==68.1 포함
  TC-AD-18: boto3==1.34.0 포함
  TC-AD-19: pandas==2.2.0 포함
  TC-AD-20: matplotlib==3.8.4 포함
"""
import os
import pytest

ECR_URI = "827913617635.dkr.ecr.ap-northeast-2.amazonaws.com/capa-t3-report-generator:latest"

REQUIRED_OS_PACKAGES = [
    "libpango-1.0-0",
    "libpangocairo-1.0-0",
    "libcairo2",
    "libgobject-2.0-0",
    "libgdk-pixbuf2.0-0",
    "libffi-dev",
]


# ---------------------------------------------------------------------------
# DAG 파일 테스트
# ---------------------------------------------------------------------------


class TestDagFile:
    def test_dag_file_exists(self, dag_file: str) -> None:
        """TC-AD-01: DAG 파일이 services/airflow-dags/ 경로에 존재해야 한다"""
        assert os.path.isfile(dag_file), (
            f"DAG 파일 없음: {dag_file}\n"
            "KubernetesPodOperator 버전 DAG 파일을 생성해주세요."
        )

    def test_uses_kubernetes_pod_operator(self, dag_content: str) -> None:
        """TC-AD-02: KubernetesPodOperator를 import하고 사용해야 한다"""
        assert "KubernetesPodOperator" in dag_content, "KubernetesPodOperator import/사용 없음"
        assert "from airflow.providers.cncf.kubernetes.operators.pod import" in dag_content

    def test_ecr_image_uri(self, dag_content: str) -> None:
        """TC-AD-03: ECR 이미지 URI가 설계서와 일치해야 한다"""
        assert ECR_URI in dag_content, (
            f"ECR URI 불일치 또는 미존재\n기대값: {ECR_URI}"
        )

    def test_dag_id(self, dag_content: str) -> None:
        """TC-AD-04: dag_id가 't3_report_generator_v3'이어야 한다"""
        assert 't3_report_generator_v3' in dag_content
        assert 'dag_id="t3_report_generator_v3"' in dag_content or \
               "dag_id='t3_report_generator_v3'" in dag_content

    def test_schedule_interval_utc_23(self, dag_content: str) -> None:
        """TC-AD-05: schedule_interval이 '0 23 * * *' (UTC 23:00 = KST 08:00)이어야 한다"""
        assert '"0 23 * * *"' in dag_content or "'0 23 * * *'" in dag_content, (
            "schedule_interval이 '0 23 * * *'이 아님"
        )

    def test_catchup_false(self, dag_content: str) -> None:
        """TC-AD-06: catchup=False 설정이 있어야 한다"""
        assert "catchup=False" in dag_content

    def test_four_task_ids(self, dag_content: str) -> None:
        """TC-AD-07: 4개 Task ID (daily_report, weekly_report, monthly_report, notify_slack)"""
        for task_id in ["daily_report", "weekly_report", "monthly_report", "notify_slack"]:
            assert task_id in dag_content, f"task_id '{task_id}' 없음"

    def test_env_from_secret(self, dag_content: str) -> None:
        """TC-AD-08: t3-report-secret을 env_from으로 참조해야 한다"""
        assert "t3-report-secret" in dag_content
        assert "V1SecretEnvSource" in dag_content or "env_from" in dag_content

    def test_service_account_name(self, dag_content: str) -> None:
        """TC-AD-09: service_account_name이 'airflow-sa'이어야 한다"""
        assert "airflow-sa" in dag_content
        assert "service_account_name" in dag_content

    def test_is_delete_operator_pod(self, dag_content: str) -> None:
        """TC-AD-10: is_delete_operator_pod=True 설정이 있어야 한다"""
        assert "is_delete_operator_pod=True" in dag_content

    def test_notify_trigger_rule_all_done(self, dag_content: str) -> None:
        """TC-AD-11: notify_slack Task는 trigger_rule='all_done'이어야 한다"""
        assert 'trigger_rule="all_done"' in dag_content or \
               "trigger_rule='all_done'" in dag_content, (
            "notify_slack의 trigger_rule='all_done' 없음"
        )

    def test_task_dependency_chain(self, dag_content: str) -> None:
        """TC-AD-12: daily >> weekly >> monthly >> notify 의존성 체인이 있어야 한다"""
        assert ">>" in dag_content, "Task 의존성 >> 연산자 없음"
        # 4개 task 변수가 >> 로 연결되어 있는지 확인
        assert dag_content.count(">>") >= 3, ">> 연산자가 3개 이상이어야 함 (4개 task 체인)"


# ---------------------------------------------------------------------------
# Dockerfile 테스트
# ---------------------------------------------------------------------------


class TestDockerfile:
    def test_base_image(self, dockerfile_content: str) -> None:
        """TC-AD-13: FROM python:3.11-slim 이어야 한다"""
        assert "FROM python:3.11-slim" in dockerfile_content

    def test_workdir_app(self, dockerfile_content: str) -> None:
        """TC-AD-14: WORKDIR /app 설정이 있어야 한다"""
        assert "WORKDIR /app" in dockerfile_content

    def test_required_os_packages(self, dockerfile_content: str) -> None:
        """TC-AD-15: weasyprint 실행에 필요한 OS 패키지 6종이 apt-get 설치 목록에 있어야 한다"""
        for pkg in REQUIRED_OS_PACKAGES:
            assert pkg in dockerfile_content, (
                f"OS 패키지 누락: {pkg}\n"
                "weasyprint 실행에 필요한 libpango/libcairo 계열 패키지가 없습니다."
            )

    def test_requirements_copy_before_pip(self, dockerfile_content: str) -> None:
        """TC-AD-16: requirements.txt COPY 후 pip install 순서여야 한다"""
        copy_idx = dockerfile_content.find("COPY requirements.txt")
        pip_idx = dockerfile_content.find("pip install")
        assert copy_idx != -1, "COPY requirements.txt 없음"
        assert pip_idx != -1, "pip install 없음"
        assert copy_idx < pip_idx, "COPY requirements.txt가 pip install 이전에 있어야 함"


# ---------------------------------------------------------------------------
# requirements.txt 테스트
# ---------------------------------------------------------------------------


class TestRequirements:
    def test_weasyprint_version(self, requirements_content: str) -> None:
        """TC-AD-17: weasyprint==68.1 이 포함되어야 한다"""
        assert "weasyprint==68.1" in requirements_content, (
            "weasyprint==68.1 없음 — PDF 생성 불가"
        )

    def test_boto3_version(self, requirements_content: str) -> None:
        """TC-AD-18: boto3==1.34.0 이어야 한다"""
        assert "boto3==1.34.0" in requirements_content, (
            "boto3==1.34.0 없음 (현재 구버전 사용 중)"
        )

    def test_pandas_version(self, requirements_content: str) -> None:
        """TC-AD-19: pandas==2.2.0 이어야 한다"""
        assert "pandas==2.2.0" in requirements_content

    def test_matplotlib_version(self, requirements_content: str) -> None:
        """TC-AD-20: matplotlib==3.8.4 이어야 한다"""
        assert "matplotlib==3.8.4" in requirements_content

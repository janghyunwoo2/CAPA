"""
airflow-dag-deployment 단위 테스트 공통 설정

DAG 파일 import 없이 파일 내용(소스코드)을 직접 파싱하는 방식으로 검증합니다.
Airflow/Kubernetes 패키지가 로컬에 설치되지 않아도 동작합니다.
"""
import os
import pytest


@pytest.fixture(scope="session")
def services_dir() -> str:
    """services/ 디렉토리 절대 경로"""
    here = os.path.dirname(os.path.abspath(__file__))
    return os.path.abspath(os.path.join(here, "..", "..", ".."))


@pytest.fixture(scope="session")
def dag_file(services_dir: str) -> str:
    return os.path.join(services_dir, "airflow-dags", "t3_report_generator_v3.py")


@pytest.fixture(scope="session")
def dockerfile(services_dir: str) -> str:
    return os.path.join(
        services_dir,
        "airflow-dags",
        "docker",
        "t3-report-generator",
        "Dockerfile",
    )


@pytest.fixture(scope="session")
def requirements_file(services_dir: str) -> str:
    return os.path.join(
        services_dir,
        "airflow-dags",
        "docker",
        "t3-report-generator",
        "requirements.txt",
    )


@pytest.fixture(scope="session")
def dag_content(dag_file: str) -> str:
    with open(dag_file, "r", encoding="utf-8") as f:
        return f.read()


@pytest.fixture(scope="session")
def dockerfile_content(dockerfile: str) -> str:
    with open(dockerfile, "r", encoding="utf-8") as f:
        return f.read()


@pytest.fixture(scope="session")
def requirements_content(requirements_file: str) -> str:
    with open(requirements_file, "r", encoding="utf-8") as f:
        return f.read()

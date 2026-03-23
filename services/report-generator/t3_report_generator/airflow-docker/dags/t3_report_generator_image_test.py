"""T3 Report Generator 이미지 방식 테스트 DAG

빌드된 'capa-report:t3' 도커 이미지를 직접 실행하는 방식의 테스트입니다.
실제 EKS 서비스 배포 방식(KubernetesPodOperator)과 가장 유사한 방식입니다.
"""

import os
from datetime import datetime, timedelta
from airflow import DAG
from airflow.providers.docker.operators.docker import DockerOperator

default_args = {
    'owner': 'data-team',
    'retries': 0,
    'start_date': datetime(2026, 3, 1),
}

dag = DAG(
    dag_id='t3_report_generator_image_test',
    default_args=default_args,
    description='도커 이미지를 직접 실행하여 리포트 생성 테스트',
    schedule_interval=None, # 수동 실행 전용
    catchup=False,
    tags=['test', 'docker-image'],
)

# .env 파일에서 환경변수를 읽어와 에어플로우 컨테이너 내부에 주입합니다.
# (DockerOperator의 environment 인자로 전달)
def get_env_vars():
    env_vars = {}
    env_path = '/opt/airflow/parent/report-generator/t3_report_generator/airflow-docker/.env'
    if os.path.exists(env_path):
        with open(env_path, 'r') as f:
            for line in f:
                if line.strip() and not line.startswith('#'):
                    key, val = line.strip().split('=', 1)
                    env_vars[key] = val
    return env_vars

task_image_test = DockerOperator(
    task_id='run_t3_report_image',
    image='capa-report:t3',
    container_name='t3_image_test_run',
    api_version='auto',
    auto_remove=True,
    # ENTRYPOINT ["python", "main.py"] 가 설정되어 있으므로 뒤의 인자만 넘깁니다.
    command="2026-03-23 daily",
    docker_url="unix://var/run/docker.sock",
    network_mode="bridge",
    environment=get_env_vars(), # .env 파일의 모든 내용을 컨테이너에 전달
    dag=dag,
)

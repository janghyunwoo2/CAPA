"""T3 Report Generator v3 Image-mode DAG

배포용 'capa-report:t3' 도커 이미지를 사용하여 일간/주간/월간 보고서를 생성합니다.
에어플로우의 ShortCircuitOperator를 활용하여 리포트 실행 주기를 제어하며,
로컬 테스트를 위해 DockerOperator를 사용하거나 EKS 배포를 위해 KubernetesPodOperator로 쉽게 전환할 수 있습니다.
"""

import os
from datetime import datetime, timedelta
from airflow import DAG
from airflow.providers.docker.operators.docker import DockerOperator
from airflow.operators.python import ShortCircuitOperator
from airflow.utils.trigger_rule import TriggerRule

default_args = {
    'owner': 'data-team',
    'retries': 2,
    'retry_delay': timedelta(minutes=5),
    'start_date': datetime(2026, 3, 1),
}

dag = DAG(
    dag_id='t3_report_generator_v3_image',
    default_args=default_args,
    description='이미지 기반 일간/주간/월간 보고서 자동 생성 및 통합 알림 (EKS 대응형)',
    schedule_interval='0 23 * * *',  # UTC 23:00 = KST 08:00 (매일)
    catchup=False,
    tags=['report-generator', 't3', 'v3', 'image-mode', 'eks-ready'],
)

# .env 파일에서 환경변수를 읽어와 컨테이너 내부에 주입합니다.
# 실제 EKS 배포 시에는 Kubernetes의 Secrets/ConfigMap을 사용하는 'env_from' 방식으로 변경을 권장합니다.
def get_env_vars():
    env_vars = {}
    env_path = '/opt/airflow/parent/report-generator/t3_report_generator/airflow-docker/.env'
    if os.path.exists(env_path):
        with open(env_path, 'r') as f:
            for line in f:
                if line.strip() and not line.startswith('#'):
                    # "=" 문자가 여러 개 포함되어 있을 경우를 대비하여 1번만 split
                    if '=' in line:
                        key, val = line.strip().split('=', 1)
                        env_vars[key] = val
    return env_vars

# [헬퍼] 도커 실행용 기본 설정값
docker_settings = {
    'image': 'capa-report:t3',
    'api_version': 'auto',
    'auto_remove': True,
    'docker_url': 'unix://var/run/docker.sock',
    'network_mode': 'bridge',
    'mount_tmp_dir': False, # 로컬 마운트 오류 방지
    'environment': get_env_vars(),
}

# --- 1. 일간 보고서 생성 (매일 실행) ---
task_daily = DockerOperator(
    task_id='daily_report',
    # Dockerfile에 ENTRYPOINT ["python", "main.py"] 가 이미 설정되어 있으므로,
    # 뒤에 붙을 인자(date, type, flag)만 넘깁니다.
    command="{{ ds }} daily --only-upload",
    **docker_settings,
    dag=dag,
)

# --- 2. 주간 보고서 생성 (월요일 체크) ---
def is_monday(**context):
    execution_date = context['execution_date']
    # Airflow execution_date는 KST 기준 전날일 수 있으므로 로직 확인 필요
    # 여기서는 '오늘 날짜' 또는 '실행 주중의 기준'에 맞춰 월요일 여부를 판단합니다.
    # 단순화를 위해 context의 ds 기준이 월요일인지 체크하는 방식으로 구현 가능합니다.
    return datetime.strptime(context['ds'], '%Y-%m-%d').weekday() == 0

check_weekly = ShortCircuitOperator(
    task_id='check_weekly_report',
    python_callable=is_monday,
    ignore_downstream_trigger_rules=False, # 후속 태스크(알림)의 트리거 규칙 존중
    dag=dag,
)

task_weekly = DockerOperator(
    task_id='weekly_report',
    command="{{ ds }} weekly --only-upload",
    **docker_settings,
    dag=dag,
)

# --- 3. 월간 보고서 생성 (3일 체크) ---
def is_third_day(**context):
    return datetime.strptime(context['ds'], '%Y-%m-%d').day == 3

check_monthly = ShortCircuitOperator(
    task_id='check_monthly_report',
    python_callable=is_third_day,
    ignore_downstream_trigger_rules=False, # 후속 태스크(알림)의 트리거 규칙 존중
    dag=dag,
)

task_monthly = DockerOperator(
    task_id='monthly_report',
    command="{{ ds }} monthly --only-upload",
    **docker_settings,
    dag=dag,
)

# --- 4. 통합 알림 전송 (항상 실행) ---
# 모든 리포트 태스크가 비즈니스 로직에 의해 건너뛰었거나 성공했더라도
# 오늘 생성된 것들에 대해 "알림"만 한 번더 수행합니다.
task_notify = DockerOperator(
    task_id='notify_slack',
    command="{{ ds }} notify",
    # NONE_FAILED: 하위 작업들이 모두 성공하거나 스킵되었을 때 실행됨 (스킵돼도 실행됨)
    trigger_rule=TriggerRule.NONE_FAILED, 
    **docker_settings,
    dag=dag,
)

# --- 실행 순서 구성 ---
# 일간 리포트 완료 후 주간/월간 체크가 병렬로 진행
# 모든 체크 및 작업이 (성공 또는 스킵) 완료된 후 통합 알림 수행
task_daily >> [check_weekly, check_monthly, task_notify]
check_weekly >> task_weekly >> task_notify
check_monthly >> task_monthly >> task_notify

"""
[!] EKS 배포 팁:
실제 EKS에서는 'DockerOperator'대신 'KubernetesPodOperator'를 사용해야 합니다.
이미지 속성 ('image')은 ECR 주소로 바꾸고, 'is_delete_operator_pod=True' 옵션을 추가하면 됩니다.
"""

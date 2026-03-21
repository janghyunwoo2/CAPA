"""
T3 Report Generator DAG

매일 아침 08:00에 T3 보고서를 생성합니다.
- 일간 데이터: 매일 포함
- 주간 데이터: 월요일에만 포함
- 월간 데이터: 1일에만 포함
"""

import sys
import subprocess
from datetime import datetime, timedelta
from pathlib import Path

from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.exceptions import AirflowException

# =====================================================================
# DAG 설정
# =====================================================================
default_args = {
    'owner': 'data-team',
    'retries': 2,
    'retry_delay': timedelta(minutes=5),
    'start_date': datetime(2026, 1, 1),
}

dag = DAG(
    dag_id='t3_report_generator',
    default_args=default_args,
    description='[비활성화] t3_daily/weekly/monthly_report 로 대체됨',
    schedule_interval=None,  # 비활성화
    catchup=False,
    tags=['report-generator', 't3', 'deprecated'],
)

# =====================================================================
# 태스크 함수
# =====================================================================

def run_report_generator_task(**context):
    """T3 보고서 생성 - main.py 호출"""

    # execution_date 기준으로 리포트 생성
    # KST 기준 현재 시간에서 날짜 추출 (docker-compose에 TZ 설정 완료됨)
    # 08:00 KST 실행 시 date_str은 실행 당일 날짜(예: 2026-03-17)가 됩니다.
    # main.py 내부에서 다시하루를 빼서 '어제' 데이터를 조회하므로 logic이 맞습니다.
    now = datetime.now()
    date_str = now.strftime('%Y-%m-%d')

    print(f"[T3 Report Generator] 시작: {date_str}")

    try:
        # T3 Report Generator main.py 실행
        # 경로: /opt/airflow/parent/report-generator/t3_report_generator/main.py
        cmd = [
            'python',
            '/opt/airflow/parent/report-generator/t3_report_generator/main.py',
            date_str,
        ]

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=600,  # 10분 타임아웃
        )

        # 로그 출력
        if result.stdout:
            print("[STDOUT]")
            print(result.stdout)

        if result.stderr:
            print("[STDERR]")
            print(result.stderr)

        # 실패 처리
        if result.returncode != 0:
            raise AirflowException(
                f"Report generation failed with return code {result.returncode}\n"
                f"Error: {result.stderr}"
            )

        print(f"[T3 Report Generator] 완료: {date_str}")

        return {
            'status': 'success',
            'date': date_str,
            'timestamp': datetime.now().isoformat(),
        }

    except subprocess.TimeoutExpired:
        raise AirflowException("Report generation timed out (10분 초과)")
    except Exception as e:
        raise AirflowException(f"Unexpected error: {str(e)}")


# =====================================================================
# 작업 정의
# =====================================================================

task_generate_report = PythonOperator(
    task_id='generate_t3_report',
    python_callable=run_report_generator_task,
    provide_context=True,
    dag=dag,
)

# 작업 실행 순서 (현재는 1개 작업만 있음)
task_generate_report

"""Data Quality DAG

이 DAG는 데이터 품질을 체크하고 품질 보고서를 생성합니다.
null 비율, 데이터 타입 오류, 중복 체크 등 다양한 품질 지표를 추적합니다.
"""
from airflow import DAG
# 최신 표준 경로에서 Operator를 가져옵니다.
from airflow.providers.standard.operators.python import PythonOperator
from airflow.providers.amazon.aws.hooks.s3 import S3Hook
from datetime import datetime, timedelta
import json
import boto3
import pandas as pd
import os
import logging
from typing import Dict, Any

logger = logging.getLogger(__name__)

# 기본 설정 (변수명 유지)
DEFAULT_ARGS = {
    'owner': 'capa',
    'start_date': datetime(2025, 1, 1),
    'retries': 1,
    'retry_delay': timedelta(minutes=5),
    'depends_on_past': False,
    'email_on_failure': False,
}

def run_quality_checks(**context) -> Dict[str, Any]:
    """Run data quality checks and generate report
    
    데이터 품질을 검사하고 보고서를 S3에 업로드합니다.
    """
    try:
        # [수정] 최신 Airflow 표준 날짜 객체와 날짜 문자열(ds)을 가져옵니다.
        execution_date = context.get('logical_date')
        ds = context.get('ds')
        
        logger.info(f"데이터 품질 검사 시작 날짜: {ds}")
        
        # 샘플 품질 검사 데이터 (변수명 유지)
        quality_report = {
            'execution_date': execution_date.isoformat() if execution_date else ds,
            'report_date': ds,
            'row_count': 1000,
            'total_checks': 10,
            'passed_checks': 8,
            'failed_checks': 2,
            'null_ratio': {
                'user_id': 0.0,
                'email': 0.05,
                'created_at': 0.01,
                'updated_at': 0.02,
            },
            'unique_violations': {'user_id': 0, 'email': 3},
            'data_type_errors': {'age': 2, 'created_at': 1},
            'value_range_checks': {
                'age': {'min': 18, 'max': 99, 'out_of_range_count': 5},
                'price': {'min': 0, 'max': 10000, 'out_of_range_count': 0}
            },
            'completeness_score': 0.95,
            'accuracy_score': 0.98,
            'consistency_score': 0.97,
            'timeliness_score': 0.99,
            'overall_quality_score': 0.97,
            'timestamp': datetime.now().isoformat(),
        }
        
        if quality_report['failed_checks'] > 0:
            logger.warning(f"품질 검사 실패 항목 발견: {quality_report['failed_checks']}개")
        
        # [S3 업로드 로직]
        # Airflow UI의 Connections에서 만든 'athena' 설정을 사용합니다.
        s3_hook = S3Hook(aws_conn_id='athena')
        
        # [수정] 환경변수가 없으면 'ad_events_raw'를 기본 버킷으로 사용합니다.
        bucket = os.environ.get('S3_BUCKET', 'capa-logs-dev-ap-northeast-2')
        
        # 날짜가 포함된 파일명 생성 (예: quality_20260213.json)
        ds_nodash = context.get('ds_nodash')
        key = f"metadata/quality_{ds_nodash}.json"
        
        # S3에 문자열(JSON) 형태로 업로드
        s3_hook.load_string(
            string_data=json.dumps(quality_report, indent=2),
            key=key,
            bucket_name=bucket,
            replace=True
        )
        
        logger.info(f"품질 보고서 업로드 완료: s3://{bucket}/{key}")
        return quality_report
        
    except Exception as e:
        # 들여쓰기 주의: except 블록 안쪽으로 들어와 있어야 합니다.
        logger.error(f"데이터 품질 검사 중 오류 발생: {str(e)}")
        raise

def check_specific_table(table_name: str, **context) -> Dict[str, Any]:
    """특정 테이블에 대한 상세 품질 검사"""
    logger.info(f"테이블 상세 검사 수행 중: {table_name}")
    return {
        'table_name': table_name,
        'check_date': context.get('ds'),
        'row_count': 5000,
        'column_count': 15,
        'null_columns': ['optional_field1', 'optional_field2'],
        'primary_key_duplicates': 0,
        'foreign_key_violations': 0,
    }

# DAG 정의
with DAG(
    dag_id='01_data_quality',
    default_args=DEFAULT_ARGS,
    description='Run data quality checks and generate reports',
    schedule='@daily',
    catchup=False,
    tags=['quality', 'validation', 'capa']
) as dag:
    
    # 1. 메인 품질 검사 태스크
    main_quality_check = PythonOperator(
        task_id='run_quality_checks',
        python_callable=run_quality_checks,
    )
    
    # 2. 개별 테이블 검사 태스크들
    check_users_table = PythonOperator(
        task_id='check_users_table',
        python_callable=check_specific_table,
        op_kwargs={'table_name': 'users'},
    )
    
    check_orders_table = PythonOperator(
        task_id='check_orders_table',
        python_callable=check_specific_table,
        op_kwargs={'table_name': 'orders'},
    )
    
    # 순서 설정: 메인 검사 완료 후 개별 테이블 검사 시작
    main_quality_check >> [check_users_table, check_orders_table]
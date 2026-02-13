"""Data Quality DAG

이 DAG는 데이터 품질을 체크하고 품질 보고서를 생성합니다.
null 비율, 데이터 타입 오류, 중복 체크 등 다양한 품질 지표를 추적합니다.
"""
from airflow import DAG
from airflow.operators.python import PythonOperator
from datetime import datetime, timedelta
import json
import boto3
import pandas as pd
import os
import logging
from typing import Dict, Any

logger = logging.getLogger(__name__)

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
    
    Args:
        **context: Airflow context
    
    Returns:
        dict: 품질 검사 결과 보고서
    """
    try:
        execution_date = context['execution_date']
        ds = context['ds']
        
        # 실제 환경에서는 S3나 DB에서 데이터를 읽어서 검사
        # 여기서는 샘플 품질 검사 결과를 생성
        logger.info(f"Running data quality checks for {ds}")
        
        # 샘플 품질 검사 결과
        quality_report = {
            'execution_date': execution_date.isoformat(),
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
            'unique_violations': {
                'user_id': 0,
                'email': 3,
            },
            'data_type_errors': {
                'age': 2,  # 숫자가 아닌 값
                'created_at': 1,  # 잘못된 날짜 형식
            },
            'value_range_checks': {
                'age': {
                    'min': 18,
                    'max': 99,
                    'out_of_range_count': 5,
                },
                'price': {
                    'min': 0,
                    'max': 10000,
                    'out_of_range_count': 0,
                }
            },
            'completeness_score': 0.95,  # 95% 완전성
            'accuracy_score': 0.98,      # 98% 정확도
            'consistency_score': 0.97,   # 97% 일관성
            'timeliness_score': 0.99,    # 99% 적시성
            'overall_quality_score': 0.97,  # 전체 품질 점수
            'timestamp': datetime.now().isoformat(),
        }
        
        # 품질 검사 실패 시 경고
        if quality_report['failed_checks'] > 0:
            logger.warning(f"Quality checks failed: {quality_report['failed_checks']} out of {quality_report['total_checks']}")
        
        # S3에 보고서 업로드
        s3 = boto3.client('s3')
        bucket = os.environ.get('S3_BUCKET', 'test-bucket')
        key = f"metadata/quality_{context['ds_nodash']}.json"
        
        s3.put_object(
            Bucket=bucket,
            Key=key,
            Body=json.dumps(quality_report, indent=2).encode('utf-8')
        )
        
        logger.info(f"Quality report uploaded to s3://{bucket}/{key}")
        logger.info(f"Overall quality score: {quality_report['overall_quality_score']}")
        
        # 품질 점수가 임계값 미만이면 경고
        if quality_report['overall_quality_score'] < 0.95:
            logger.warning("Data quality is below threshold (0.95)")
        
        return quality_report
        
    except Exception as e:
        logger.error(f"Data quality check failed: {str(e)}")
        raise


def check_specific_table(table_name: str, **context) -> Dict[str, Any]:
    """특정 테이블에 대한 상세 품질 검사
    
    Args:
        table_name: 검사할 테이블 이름
        **context: Airflow context
    
    Returns:
        dict: 테이블별 상세 품질 검사 결과
    """
    logger.info(f"Running detailed quality check for table: {table_name}")
    
    # 실제로는 테이블 데이터를 읽어서 검사
    # 여기서는 샘플 결과 반환
    return {
        'table_name': table_name,
        'check_date': context['ds'],
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
    tags=['quality', 'validation', 'capa'],
    doc_md="""
    ## Data Quality DAG
    
    이 DAG는 데이터 품질을 검사하고 품질 보고서를 생성합니다.
    
    ### 품질 검사 항목
    - **완전성(Completeness)**: null 값 비율 체크
    - **정확성(Accuracy)**: 데이터 타입, 값 범위 검증
    - **일관성(Consistency)**: 중복 데이터, 참조 무결성 검증
    - **적시성(Timeliness)**: 데이터 최신성 검증
    
    ### 출력
    - S3: `s3://{bucket}/metadata/quality_YYYYMMDD.json`
    - 전체 품질 점수 및 세부 메트릭
    
    ### 환경변수
    - `S3_BUCKET`: 결과를 저장할 S3 버킷
    """
) as dag:
    
    # 메인 품질 검사 태스크
    main_quality_check = PythonOperator(
        task_id='run_quality_checks',
        python_callable=run_quality_checks,
    )
    
    # 특정 테이블들에 대한 상세 검사 (옵션)
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
    
    # 태스크 의존성 설정
    main_quality_check >> [check_users_table, check_orders_table]
"""Schema Extraction DAG

이 DAG는 데이터베이스에서 스키마 정보를 추출하여 S3에 JSON 형태로 저장합니다.
일일 배치로 실행되며, 데이터베이스 메타데이터를 추적하는 데 사용됩니다.
"""
from airflow import DAG
from airflow.operators.python import PythonOperator
from datetime import datetime, timedelta
import sqlalchemy as sa
import json
import boto3
import os
import logging

logger = logging.getLogger(__name__)

DEFAULT_ARGS = {
    'owner': 'capa',
    'start_date': datetime(2025, 1, 1),
    'retries': 1,
    'retry_delay': timedelta(minutes=5),
    'depends_on_past': False,
    'email_on_failure': False,
}


def extract_schema(**context):
    """Extract schema from database and save to S3
    
    데이터베이스의 모든 테이블과 컬럼 정보를 추출하여
    S3에 JSON 형태로 저장합니다.
    
    Args:
        **context: Airflow context
    
    Returns:
        dict: 업로드된 S3 키와 추출된 테이블 수
    """
    try:
        # 환경변수에서 DB 정보 가져오기
        db_user = os.environ.get('DB_USER', 'testuser')
        db_pass = os.environ.get('DB_PASS', 'testpass')
        db_host = os.environ.get('DB_HOST', 'localhost')
        db_port = os.environ.get('DB_PORT', '5432')
        db_name = os.environ.get('DB_NAME', 'testdb')
        
        # Database connection
        db_url = f"postgresql://{db_user}:{db_pass}@{db_host}:{db_port}/{db_name}"
        logger.info(f"Connecting to database: {db_host}:{db_port}/{db_name}")
        
        eng = sa.create_engine(db_url)
        meta = sa.MetaData()
        meta.reflect(bind=eng)
        
        # Build schema dictionary
        schema_data = {}
        for table in meta.sorted_tables:
            columns = []
            for column in table.columns:
                columns.append({
                    'name': column.name,
                    'type': str(column.type),
                    'nullable': column.nullable,
                    'primary_key': column.primary_key,
                })
            schema_data[str(table.name)] = columns
        
        logger.info(f"Extracted schema for {len(schema_data)} tables")
        
        # Upload to S3
        s3 = boto3.client('s3')
        bucket = os.environ.get('S3_BUCKET', 'test-bucket')
        key = f"metadata/schema_{context['ds_nodash']}.json"
        
        s3.put_object(
            Bucket=bucket,
            Key=key,
            Body=json.dumps(schema_data, indent=2).encode('utf-8')
        )
        
        logger.info(f"Schema uploaded to s3://{bucket}/{key}")
        
        return {
            'uploaded_key': key,
            'table_count': len(schema_data),
            'execution_date': context['ds']
        }
        
    except Exception as e:
        logger.error(f"Schema extraction failed: {str(e)}")
        raise


# DAG 정의
with DAG(
    dag_id='03_schema_extraction',
    default_args=DEFAULT_ARGS,
    description='Extract database schema and save to S3',
    schedule='@daily',
    catchup=False,
    tags=['metadata', 'schema', 'capa'],
    doc_md="""
    ## Schema Extraction DAG
    
    이 DAG는 매일 데이터베이스 스키마를 추출하여 S3에 저장합니다.
    
    ### 주요 기능
    - PostgreSQL 데이터베이스 연결
    - 모든 테이블과 컬럼 정보 추출
    - JSON 형태로 S3 업로드
    
    ### 환경변수
    - `DB_USER`: 데이터베이스 사용자
    - `DB_PASS`: 데이터베이스 비밀번호
    - `DB_HOST`: 데이터베이스 호스트
    - `DB_PORT`: 데이터베이스 포트
    - `DB_NAME`: 데이터베이스 이름
    - `S3_BUCKET`: S3 버킷 이름
    """
) as dag:
    
    extract_schema_task = PythonOperator(
        task_id='extract_schema',
        python_callable=extract_schema,
    )
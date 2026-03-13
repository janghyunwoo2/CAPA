"""
Athena 쿼리 실행 유틸리티
쿼리 실행, 상태 확인, 결과 조회 등의 공통 기능 제공
"""

import time
import logging
from typing import Dict, List, Optional
import boto3
from botocore.exceptions import ClientError
import json

from .config import (
    AWS_REGION, DATABASE, ATHENA_OUTPUT_LOCATION, ATHENA_TEMP_RESULTS_PATH,
    QUERY_TIMEOUT_SECONDS, MAX_RETRIES, RETRY_DELAY_SECONDS
)

logger = logging.getLogger(__name__)


class AthenaQueryExecutor:
    """Athena 쿼리 실행 및 관리 클래스"""
    
    def __init__(self):
        self.client = boto3.client('athena', region_name=AWS_REGION)
        
    def execute_query(self, query: str, database: str = DATABASE) -> str:
        """
        Athena 쿼리 실행 및 완료까지 대기
        
        Args:
            query: 실행할 SQL 쿼리
            database: 사용할 데이터베이스
            
        Returns:
            쿼리 실행 ID
            
        Raises:
            Exception: 쿼리 실행 실패 시
        """
        for attempt in range(MAX_RETRIES):
            try:
                # 쿼리 시작 (메타데이터를 athena-results/ 경로에 축적)
                response = self.client.start_query_execution(
                    QueryString=query,
                    QueryExecutionContext={'Database': database},
                    ResultConfiguration={'OutputLocation': ATHENA_TEMP_RESULTS_PATH}
                )
                
                query_id = response['QueryExecutionId']
                logger.info(f"Query started with ID: {query_id}")
                
                # 쿼리 완료 대기
                if self._wait_for_query_completion(query_id):
                    return query_id
                else:
                    raise Exception(f"Query {query_id} failed or timed out")
                    
            except ClientError as e:
                logger.error(f"Attempt {attempt + 1} failed: {str(e)}")
                if attempt < MAX_RETRIES - 1:
                    time.sleep(RETRY_DELAY_SECONDS)
                else:
                    raise
                    
    def _wait_for_query_completion(self, query_id: str) -> bool:
        """
        쿼리 완료까지 대기
        
        Args:
            query_id: 쿼리 실행 ID
            
        Returns:
            성공 여부
        """
        start_time = time.time()
        
        while time.time() - start_time < QUERY_TIMEOUT_SECONDS:
            try:
                response = self.client.get_query_execution(
                    QueryExecutionId=query_id
                )
                
                status = response['QueryExecution']['Status']['State']
                
                if status == 'SUCCEEDED':
                    stats = response['QueryExecution'].get('Statistics', {})
                    data_scanned = stats.get('DataScannedInBytes', 0) / (1024 * 1024)
                    execution_time = stats.get('TotalExecutionTimeInMillis', 0) / 1000
                    
                    logger.info(
                        f"Query succeeded - Data scanned: {data_scanned:.2f} MB, "
                        f"Execution time: {execution_time:.2f} seconds"
                    )
                    return True
                    
                elif status in ['FAILED', 'CANCELLED']:
                    error_msg = response['QueryExecution']['Status'].get(
                        'StateChangeReason', 'Unknown error'
                    )
                    logger.error(f"Query {status}: {error_msg}")
                    return False
                    
                else:
                    # QUEUED or RUNNING
                    time.sleep(2)
                    
            except ClientError as e:
                logger.error(f"Error checking query status: {str(e)}")
                return False
                
        logger.error(f"Query timed out after {QUERY_TIMEOUT_SECONDS} seconds")
        return False
        
    def get_query_results(self, query_id: str) -> List[Dict]:
        """
        쿼리 결과 조회
        
        Args:
            query_id: 쿼리 실행 ID
            
        Returns:
            결과 리스트 (각 행은 딕셔너리)
        """
        try:
            paginator = self.client.get_paginator('get_query_results')
            pages = paginator.paginate(QueryExecutionId=query_id)
            
            results = []
            headers = None
            
            for page in pages:
                rows = page['ResultSet']['Rows']
                
                # 첫 페이지에서 헤더 추출
                if headers is None and rows:
                    headers = [col['VarCharValue'] for col in rows[0]['Data']]
                    rows = rows[1:]  # 헤더 제외
                    
                # 데이터 행 처리
                for row in rows:
                    values = [col.get('VarCharValue', '') for col in row['Data']]
                    results.append(dict(zip(headers, values)))
                    
            return results
            
        except ClientError as e:
            logger.error(f"Error getting query results: {str(e)}")
            return []
    
    def execute_query_to_s3(self, query: str, database: str = DATABASE) -> str:
        """
        Athena 쿼리를 실행하고 결과를 임시 경로에 저장
        
        ✅ 메타데이터와 데이터 경로를 분리하여 이상한 테이블 생성 방지
        
        Args:
            query: 실행할 SQL 쿼리
            database: 사용할 데이터베이스
            
        Returns:
            쿼리 실행 ID
            
        Raises:
            Exception: 쿼리 실행 실패 시
            
        Note:
            - ResultConfiguration은 ATHENA_TEMP_RESULTS_PATH로 설정 (메타데이터용)
            - 실제 데이터는 외부 테이블 정의에서 처리
            - MSCK REPAIR 시 메타데이터 오염 방지
        """
        for attempt in range(MAX_RETRIES):
            try:
                # ✅ ResultConfiguration을 임시 경로로 설정 (메타데이터 오염 방지)
                response = self.client.start_query_execution(
                    QueryString=query,
                    QueryExecutionContext={'Database': database},
                    ResultConfiguration={'OutputLocation': ATHENA_TEMP_RESULTS_PATH}  # ✅ 임시 경로 사용
                )
                
                query_id = response['QueryExecutionId']
                logger.info(f"Query started with ID: {query_id} - Metadata will be saved to {ATHENA_TEMP_RESULTS_PATH}")
                
                # 쿼리 완료 대기
                if self._wait_for_query_completion(query_id):
                    logger.info(f"✅ Query completed successfully")
                    return query_id
                else:
                    raise Exception(f"Query {query_id} failed or timed out")
                    
            except ClientError as e:
                logger.error(f"Attempt {attempt + 1} failed: {str(e)}")
                if attempt < MAX_RETRIES - 1:
                    time.sleep(RETRY_DELAY_SECONDS)
                else:
                    raise

def create_external_table(table_name: str, schema: str, location: str, 
                         partition_keys: Optional[List[tuple]] = None) -> str:
    """
    외부 테이블 생성 쿼리 생성
    
    Args:
        table_name: 테이블명
        schema: 컬럼 정의
        location: S3 위치
        partition_keys: 파티션 키 리스트 [(name, type), ...]
        
    Returns:
        CREATE TABLE 쿼리
    """
    query = f"""
    CREATE EXTERNAL TABLE IF NOT EXISTS {DATABASE}.{table_name} (
        {schema}
    )
    """
    
    if partition_keys:
        partition_clause = ", ".join([f"{key} {dtype}" for key, dtype in partition_keys])
        query += f"PARTITIONED BY ({partition_clause})\n"
        
    query += f"""
    STORED AS PARQUET
    LOCATION '{location}'
    TBLPROPERTIES ('compression'='zstd')
    """
    
    return query.strip()


def repair_table_partitions(table_name: str) -> str:
    """
    테이블 파티션 복구 쿼리 생성 (새 파티션 자동 발견)
    
    Args:
        table_name: 테이블명
        
    Returns:
        MSCK REPAIR TABLE 쿼리
    """
    return f"MSCK REPAIR TABLE {DATABASE}.{table_name}"


def drop_table_if_exists(table_name: str) -> str:
    """
    테이블 삭제 쿼리 생성
    
    Args:
        table_name: 테이블명
        
    Returns:
        DROP TABLE 쿼리
    """
    return f"DROP TABLE IF EXISTS {DATABASE}.{table_name}"
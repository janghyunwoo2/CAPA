import boto3
import pandas as pd
import time
import os
from datetime import datetime

# ============ [대조용] 파티션 컬럼(hour) 기준 집계 스크립트 ============
REGION = 'ap-northeast-2'
DATABASE = 'capa_ad_logs'
S3_OUTPUT = 's3://capa-athena-result-jh/anomaly_detection_conversion_partition/'
DATA_DIR = os.path.dirname(os.path.abspath(__file__))

# 2026년 2월 전 구간
START_DATE = '2026-02-01 00:00:00'
END_DATE = '2026-02-28 23:59:59'

# [구분] 파티션 기반 파일명
OUTPUT_FILE = os.path.join(DATA_DIR, 'historical_conversion_data_202602_1h_partition_basis.csv')

def run_athena_query(query):
    athena = boto3.client('athena', region_name=REGION)
    response = athena.start_query_execution(
        QueryString=query,
        QueryExecutionContext={'Database': DATABASE},
        ResultConfiguration={'OutputLocation': S3_OUTPUT}
    )
    query_id = response['QueryExecutionId']
    while True:
        res = athena.get_query_execution(QueryExecutionId=query_id)
        status = res['QueryExecution']['Status']['State']
        if status in ['SUCCEEDED', 'FAILED', 'CANCELLED']: break
        time.sleep(3)
    if status != 'SUCCEEDED':
        raise Exception(f"Athena query failed: {status}")
    
    paginator = athena.get_paginator('get_query_results')
    pages = paginator.paginate(QueryExecutionId=query_id)
    results = []
    page_count = 0
    for page in pages:
        rows = page['ResultSet']['Rows']
        start_idx = 1 if page_count == 0 else 0
        for i in range(start_idx, len(rows)):
            results.append([col.get('VarCharValue', '0') for col in rows[i]['Data']])
        page_count += 1
    return pd.DataFrame(results, columns=['ts', 'conversion_count'])

def generate_partition_basis_data():
    print(f"[{datetime.now()}] 아테나 쿼리 실행 중 (Hour 파티션 컬럼 기준 집계)...")
    
    # [차이점] timestamp 필드가 아닌 year, month, day, hour 문자열 조합 사용
    query = """
    SELECT
        year || '-' || month || '-' || day || ' ' || hour || ':00:00' as ts,
        COUNT(*) as conversion_count
    FROM conversions
    WHERE year='2026' AND month='02'
    GROUP BY 1
    ORDER BY ts
    """
    
    try:
        df = run_athena_query(query)
        df['ts'] = pd.to_datetime(df['ts'])
        df['conversion_count'] = df['conversion_count'].astype(int)
        
        # 1시간 단위 보간
        full_range = pd.date_range(start=START_DATE, end='2026-02-28 23:00:00', freq='1H')
        df_full = pd.DataFrame({'ts': full_range})
        df_final = pd.merge(df_full, df, on='ts', how='left').fillna(0)
        df_final['conversion_count'] = df_final['conversion_count'].astype(int)
        df_final.rename(columns={'ts': 'timestamp'}, inplace=True)
        
        df_final.to_csv(OUTPUT_FILE, index=False)
        print(f"[{datetime.now()}] 성공! 파티션 기반 파일 저장됨: {OUTPUT_FILE}")
    except Exception as e:
        print(f"❌ 실패: {e}")

if __name__ == "__main__":
    generate_partition_basis_data()

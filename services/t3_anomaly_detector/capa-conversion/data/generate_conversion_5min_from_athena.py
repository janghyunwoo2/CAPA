import boto3
import pandas as pd
import time
import os
from datetime import datetime

# ============ [1] 설정 (클릭 지표와 동일 규격 적용) ============
REGION = 'ap-northeast-2'
DATABASE = 'capa_ad_logs'  # 수정됨
S3_OUTPUT = 's3://capa-athena-result-jh/anomaly_detection_conversion/'
DATA_DIR = os.path.dirname(os.path.abspath(__file__))

# 2026년 2월 전 구간 (28일)
START_DATE = '2026-02-01 00:00:00'
END_DATE = '2026-02-28 23:59:59'

# 파일명 통일 규칙 적용
OUTPUT_FILE = os.path.join(DATA_DIR, 'historical_conversion_data_202602_from_athena.csv')

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
        if status in ['SUCCEEDED', 'FAILED', 'CANCELLED']:
            break
        time.sleep(3)
    
    if status != 'SUCCEEDED':
        reason = res['QueryExecution']['Status'].get('StateChangeReason', 'Unknown error')
        raise Exception(f"Athena query failed ({status}): {reason}")
    
    # 결과 수집 (Paginator 활용)
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
            
    header = [col['Name'] for col in page['ResultSet']['ResultSetMetadata']['ColumnInfo']]
    return pd.DataFrame(results, columns=header)

def generate_conversion_data():
    print(f"[{datetime.now()}] 아테나 쿼리 실행 중 (Conversion 2026-02 나노초 규격 대응)...")
    
    # [수정] 테이블명은 conversions로 추정, 시간 필드는 timestamp(나노초) 사용
    query = """
    SELECT
        date_format(from_unixtime(floor(CAST(timestamp AS DOUBLE) / 1000000000.0 / 300) * 300), '%Y-%m-%d %H:%i:%s') as ts,
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
        
        # 5분 단위 빈 구간 0으로 채우기 (Zero-filling)
        full_range = pd.date_range(start=START_DATE, end='2026-02-28 23:55:00', freq='5min')
        df_full = pd.DataFrame({'ts': full_range})
        df_final = pd.merge(df_full, df, on='ts', how='left').fillna(0)
        df_final['conversion_count'] = df_final['conversion_count'].astype(int)
        df_final.rename(columns={'ts': 'timestamp'}, inplace=True)
        
        df_final.to_csv(OUTPUT_FILE, index=False)
        print(f"[{datetime.now()}] 성공! 파일 저장됨: {OUTPUT_FILE}")
        print(f"총 데이터 Row 수: {len(df_final)} (8,064건 권장)")
    except Exception as e:
        print(f"❌ 데이터 생성 실패: {e}")

if __name__ == "__main__":
    generate_conversion_data()

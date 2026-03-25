import boto3
import pandas as pd
import time
import os
from datetime import datetime

# ============ [1] 설정 (1시간 주기 최적화 규격) ============
REGION = 'ap-northeast-2'
DATABASE = 'capa_ad_logs'
S3_OUTPUT = 's3://capa-athena-result-jh/anomaly_detection_conversion_1h/'
DATA_DIR = os.path.dirname(os.path.abspath(__file__))

# 2026년 2월 전 구간 (28일)
START_DATE = '2026-02-01 00:00:00'
END_DATE = '2026-02-28 23:59:59'

# 1시간 주기 파일명
OUTPUT_FILE = os.path.join(DATA_DIR, 'historical_conversion_data_202602_1h.csv')

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
            
    # 헤더 고정 (ts, conversion_count)
    return pd.DataFrame(results, columns=['ts', 'conversion_count'])

def generate_conversion_data_1h():
    print(f"[{datetime.now()}] 아테나 쿼리 실행 중 (Conversion 2026-02 1시간 주기)...")
    
    # [최종 고도화] 파티션 지연(26H) 대응: 넓은 범위를 스캔하되 실제 timestamp(KST)로 필터링/그룹핑
    query = """
    WITH base_data AS (
        SELECT 
            -- 나노초(10^9)를 초로 변환 후 KST(+9시간=32400초) 적용
            from_unixtime(CAST(timestamp AS DOUBLE) / 1000000000.0 + 32400) as kst_ts
        FROM conversions
        WHERE 
            -- 파티션 지연을 고려하여 1/30 ~ 3/2 구간 전체 스캔
            (year='2026' AND month='01' AND day>='30') OR 
            (year='2026' AND month='02') OR 
            (year='2026' AND month='03' AND day<='02')
    )
    SELECT
        date_format(date_trunc('hour', kst_ts), '%Y-%m-%d %H:%i:%s') as ts,
        COUNT(*) as conversion_count
    FROM base_data
    WHERE kst_ts BETWEEN from_iso8601_timestamp('2026-02-01T00:00:00') 
                     AND from_iso8601_timestamp('2026-02-28T23:59:59')
    GROUP BY 1
    ORDER BY ts
    """
    
    try:
        df = run_athena_query(query)
        df['ts'] = pd.to_datetime(df['ts'])
        df['conversion_count'] = df['conversion_count'].astype(int)
        
        # 1시간 단위 빈 구간 0으로 채우기
        full_range = pd.date_range(start=START_DATE, end='2026-02-28 23:00:00', freq='1H')
        df_full = pd.DataFrame({'ts': full_range})
        df_final = pd.merge(df_full, df, on='ts', how='left').fillna(0)
        df_final['conversion_count'] = df_final['conversion_count'].astype(int)
        df_final.rename(columns={'ts': 'timestamp'}, inplace=True)
        
        df_final.to_csv(OUTPUT_FILE, index=False)
        print(f"[{datetime.now()}] 성공! 파일 저장됨: {OUTPUT_FILE}")
        print(f"총 데이터 Row 수: {len(df_final)} (24*28=672건 예상)")
    except Exception as e:
        print(f"❌ 데이터 생성 실패: {e}")

if __name__ == "__main__":
    generate_conversion_data_1h()

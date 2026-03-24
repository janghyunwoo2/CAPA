import boto3
import csv
import time
import os

# [1] 설정
REGION = 'ap-northeast-2'
DATABASE = 'capa_ad_logs'
S3_OUTPUT = 's3://capa-athena-results/queries/'
DATA_DIR = os.path.dirname(os.path.abspath(__file__))
os.makedirs(DATA_DIR, exist_ok=True)
output_file = os.path.join(DATA_DIR, 'historical_data_202602_from_athena.csv')

# Athena 클라이언트
athena = boto3.client('athena', region_name=REGION)

# [2] 최종 5분 단위 그룹화 쿼리 (2월 데이터 나노초 규격 대응)
# 2월 데이터는 1770956516000000000 (19자리, 나노초) 형식이므로 10억으로 나누어 초 단위 변환
query = """
SELECT
    date_format(from_unixtime(floor(CAST(timestamp AS DOUBLE) / 1000000000.0 / 300) * 300), '%Y-%m-%d %H:%i:%s') as ts,
    COUNT(*) as impression_count
FROM impressions
WHERE year='2026' AND month='02'
GROUP BY 1
ORDER BY ts
"""

print(f"[1/4] Athena 쿼리 실행 시작... (2월 나노초 규격 대응)")
response = athena.start_query_execution(
    QueryString=query,
    QueryExecutionContext={'Database': DATABASE},
    ResultConfiguration={'OutputLocation': S3_OUTPUT}
)

query_id = response['QueryExecutionId']
print(f"[2/4] 쿼리 ID: {query_id}")

# [3] 쿼리 완료 대기
while True:
    result = athena.get_query_execution(QueryExecutionId=query_id)
    status = result['QueryExecution']['Status']['State']

    if status == 'SUCCEEDED':
        print("[3/4] 쿼리 완료! 정상 수집된 데이터를 가져옵니다.")
        break
    elif status == 'FAILED':
        reason = result['QueryExecution']['Status'].get('StateChangeReason', 'Unknown')
        print(f"❌ 쿼리 실패: {reason}")
        exit(1)
    
    time.sleep(5)

# [4] 결과 페이징 및 저장
paginator = athena.get_paginator('get_query_results')
pages = paginator.paginate(QueryExecutionId=query_id)

rows = [['timestamp', 'impression_count']]
total_count = 0

clean_dict = {}
for i, page in enumerate(pages):
    start_idx = 1 if i == 0 else 0 # 첫 페이지만 헤더 스킵
    for row in page['ResultSet']['Rows'][start_idx:]:
        vals = [col.get('VarCharValue', '') for col in row['Data']]
        if vals[0]:
            clean_dict[vals[0]] = int(vals[1])

# [Zero-filling] 2월 전체 윈도우 보간 (28일 = 8064개 윈도우)
from datetime import datetime, timedelta
start_dt = datetime(2026, 2, 1, 0, 0, 0)
end_dt = datetime(2026, 3, 1, 0, 0, 0)
current_dt = start_dt

while current_dt < end_dt:
    ts_str = current_dt.strftime('%Y-%m-%d %H:%M:%S')
    val = clean_dict.get(ts_str, 0)
    rows.append([ts_str, val])
    total_count += 1
    current_dt += timedelta(minutes=5)

# CSV 저장
with open(output_file, 'w', newline='', encoding='utf-8') as f:
    writer = csv.writer(f)
    writer.writerows(rows)

print(f"[4/4] 작업이 완료되었습니다! 🎉")
print(f"📍 저장 위치: {output_file}")
print(f"📊 총 윈도우 수: {total_count}개 (약 8,000~9,000개 예상)")

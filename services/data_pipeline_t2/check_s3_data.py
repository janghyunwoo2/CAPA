import boto3
from datetime import datetime
import pytz

s3 = boto3.client('s3', region_name='ap-northeast-2')
bucket = 'capa-data-lake-827913617635'

# 오늘 날짜 (KST 기준)
kst = pytz.timezone('Asia/Seoul')
today = datetime.now(kst).strftime('%Y/%m/%d')
prefix = f'summary/ad_combined_log/{today}/'

print(f'확인할 경로: s3://{bucket}/{prefix}')
response = s3.list_objects_v2(Bucket=bucket, Prefix=prefix, MaxKeys=20)

if 'Contents' in response:
    print(f'\n✅ 찾은 파일 개수: {len(response["Contents"])}')
    for obj in response['Contents']:
        size_mb = obj['Size'] / (1024 * 1024)
        print(f'  - {obj["Key"]} ({size_mb:.2f} MB)')
else:
    print('\n❌ 파일이 없습니다.')
    
# 전날 데이터도 확인
yesterday = (datetime.now(kst) - timedelta(days=1)).strftime('%Y/%m/%d')
prefix_yesterday = f'summary/ad_combined_log/{yesterday}/'
print(f'\n어제 데이터 확인: {prefix_yesterday}')
response_yesterday = s3.list_objects_v2(Bucket=bucket, Prefix=prefix_yesterday, MaxKeys=5)

if 'Contents' in response_yesterday:
    print(f'✅ 어제 파일 개수: {len(response_yesterday["Contents"])}')
else:
    print('❌ 어제 파일 없음')

import boto3
import logging
from datetime import datetime, timedelta, timezone

# 로깅 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# [1] 설정 변수 정의 (딕셔너리 형태의 오류 수정)
namespace = 'AWS/Kinesis'
metric_name = 'IncomingRecords'
dimension_name = 'StreamName'
dimension_value = 'capa-knss-imp-00' # kinesis stream name: capa-knss-imp-00, capa-knss-clk-00, capa-knss-cvs-00

# 시간 설정 (KST 기준: 3월 1일부터 현재까지)
PERIOD_SECONDS = 300  # 5분 단위
kst = timezone(timedelta(hours=9))
start_time = datetime(2026, 3, 23, 0, 0, 0, tzinfo=kst)  # KST 명시
end_time = datetime.now(tz=kst)  # KST 현재시간

# [2] CloudWatch 클라이언트 초기화
# 리전이 필요하다면 region_name='ap-northeast-2' 추가 가능
cloudwatch_client = boto3.client('cloudwatch', region_name='ap-northeast-2')

print(f"--- CloudWatch 지표 조회 시작 (3/1 ~ 현재, 결과는 KST 기준) ---")
print(f"Namespace: {namespace}, Metric: {metric_name}, Stream: {dimension_value}")

try:
    # [3] 메트릭 데이터 조회
    response = cloudwatch_client.get_metric_data(
        MetricDataQueries=[
            {
                'Id': 'm1',
                'MetricStat': {
                    'Metric': {
                        'Namespace': namespace,
                        'MetricName': metric_name,
                        'Dimensions': [
                            {
                                'Name': dimension_name,
                                'Value': dimension_value
                            },
                        ]
                    },
                    'Period': PERIOD_SECONDS,
                    'Stat': 'Sum',
                },
                'ReturnData': True,
            },
        ],
        StartTime=start_time,
        EndTime=end_time,
        ScanBy='TimestampDescending'
    )

    # [4] 결과 존재 여부 확인 및 출력
    results = response.get('MetricDataResults', [])
    if results and results[0].get('Timestamps'):
        timestamps = results[0]['Timestamps']
        values = results[0]['Values']
        
        print(f"\n조회 성공! 총 {len(timestamps)}개의 데이터 포인트를 찾았습니다.\n")
        
        # 각 윈도우별 데이터 출력 (KST 기준)
        for ts, val in zip(timestamps, values):
            print(f"{ts.strftime('%Y-%m-%d %H:%M:%S')} KST: {int(val)} Records")
    else:
        print("\n조회된 데이터가 없습니다. 스트림 이름이나 기간을 확인해 주세요.")

except Exception as e:
    print(f"\n❌ 오류 발생: {e}")

print("\n--- 조회 종료 ---")
# 작업 07: Log Generator 배포

> **Phase**: 2 (E2E 연결 테스트)  
> **담당**: Backend Developer  
> **예상 소요**: 10분  
> **선행 작업**: 06_eks_cluster.md

---

## 1. 목표

광고 로그 샘플 데이터를 생성하여 Kinesis Stream에 전송하는 Log Generator를 배포합니다.

---

## 2. Log Generator 구조

```python
# services/log-generator/generator.py
import json
import boto3
import time
import random
from datetime import datetime

kinesis = boto3.client('kinesis', region_name='ap-northeast-2')

def generate_ad_event():
    """광고 이벤트 샘플 생성"""
    event_type = random.choice(['impression', 'click', 'conversion'])
    
    return {
        'event_id': f"evt_{int(time.time() * 1000)}",
        'event_type': event_type,
        'timestamp': int(time.time()),
        'campaign_id': f"camp_{random.randint(1,10)}",
        'user_id': f"user_{random.randint(1,1000)}",
        'device_type': random.choice(['mobile', 'desktop', 'tablet']),
        'bid_price': round(random.uniform(0.1, 5.0), 2)
    }

def send_to_kinesis(stream_name):
    """Kinesis에 전송"""
    while True:
        event = generate_ad_event()
        
        try:
            response = kinesis.put_record(
                StreamName=stream_name,
                Data=json.dumps(event),
                PartitionKey=event['user_id']
            )
            print(f"✅ Sent: {event['event_type']} - Shard: {response['ShardId']}")
        except Exception as e:
            print(f"❌ Error: {e}")
        
        time.sleep(1)  # 1초마다 1개 전송

if __name__ == "__main__":
    send_to_kinesis('capa-stream')
```

---

## 3. 실행 단계

### 3.1 로컬에서 실행 (권장 - MVP)

```powershell
# 1. 폴더 생성 및 이동
cd services
mkdir -p log-generator
cd log-generator

# 2. generator.py 생성 (위 코드 복사)

# 3. 필요한 패키지 설치
pip install boto3

# 4. 실행
python generator.py

# 예상 출력:
# ✅ Sent: impression - Shard: shardId-000000000000
# ✅ Sent: click - Shard: shardId-000000000000
# ...
```

### 3.2 Docker로 실행 (선택)

**Dockerfile**:
```dockerfile
FROM python:3.11-slim

WORKDIR /app

RUN pip install boto3

COPY generator.py .

CMD ["python", "generator.py"]
```

**빌드 및 실행**:
```powershell
docker build -t capa-log-generator .
docker run -e AWS_REGION=ap-northeast-2 capa-log-generator
```

---

## 4. 검증 방법

### 4.1 Kinesis Stream Metrics 확인

```powershell
# CloudWatch Metrics 조회
aws cloudwatch get-metric-statistics `
    --namespace AWS/Kinesis `
    --metric-name IncomingRecords `
    --dimensions Name=StreamName,Value=capa-stream `
    --start-time (Get-Date).AddMinutes(-5).ToUniversalTime().ToString("yyyy-MM-ddTHH:mm:ss") `
    --end-time (Get-Date).ToUniversalTime().ToString("yyyy-MM-ddTHH:mm:ss") `
    --period 60 `
    --statistics Sum

# 예상: Datapoints에 IncomingRecords 값 존재
```

### 4.2 S3에 파일 생성 확인 (1분 후)

```powershell
# S3 파일 확인 (Firehose buffering 60초 후)
aws s3 ls s3://capa-data-lake-<ACCOUNT_ID>/raw/ --recursive

# 예상 출력:
# 2026-02-11 21:30:00  1234 raw/year=2026/month=02/day=11/xxx.parquet
```

### 4.3 성공 기준

- [ ] Log Generator 실행 중
- [ ] Kinesis IncomingRecords > 0
- [ ] S3에 Parquet 파일 생성됨 (1~2분 후)
- [ ] 로그 출력에 `✅ Sent` 메시지 표시

---

## 5. 실패 시 대응

| 오류 | 원인 | 해결 방법 |
|------|------|-----------|
| `ResourceNotFoundException` | Kinesis Stream 없음 | 05_data_pipeline_기본.md 확인 |
| `AccessDenied` | AWS 자격 증명 문제 | `aws configure` 확인 |
| `ProvisionedThroughputExceededException` | 너무 빠른 전송 | `time.sleep()` 값 증가 |

---

## 6. 다음 단계

✅ **Log Generator 실행 및 Kinesis 전송 확인** → `08_athena_데이터_검증.md`로 이동

---

## 7. 결과 기록

**실행자**: _______________  
**실행 일시**: _______________  
**결과**: ⬜ 성공 / ⬜ 실패  

**Kinesis Metrics**:
- IncomingRecords: ______/min
- 실행 시간: ______분

**S3 파일**:
```
(aws s3 ls 출력 결과)
```

**메모**:
```
(실행 로그, 발생한 이슈 기록)
```

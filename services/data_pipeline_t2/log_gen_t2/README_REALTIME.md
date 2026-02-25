# 실시간 광고 로그 생성기

## 개요
실제 서비스와 유사한 불규칙한 트래픽 패턴으로 광고 이벤트(노출, 클릭, 전환)를 생성하여 AWS Kinesis Data Streams로 전송하는 실시간 로그 생성기입니다.

## 주요 특징
- ⚡ 실시간 이벤트 스트리밍
- 📊 자연스러운 트래픽 패턴 (시간대별/요일별 변동)
- 👥 사용자 행동 시뮬레이션
- 🔄 비동기 처리로 높은 성능
- 📈 실시간 통계 모니터링

## 실행 방법

### 1. 환경 설정
```bash
# 가상환경 생성 및 활성화
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# 의존성 설치
pip install -r requirements_realtime.txt

# 환경변수 설정
cp .env.example .env
# .env 파일을 편집하여 AWS 자격증명 입력
```

### 2. Kinesis Stream 생성
```bash
# AWS CLI로 스트림 생성
aws kinesis create-stream \
  --stream-name capa-ad-logs-stream \
  --shard-count 1 \
  --region ap-northeast-2
```

### 3. 실행
```bash
# 실시간 로그 생성기 실행
python realtime_ad_log_generator.py
```

## 트래픽 패턴

### 시간대별 가중치
- 새벽 (00-06시): 20%
- 아침 (06-09시): 80%
- 오전 (09-11시): 60%
- 점심 (11-14시): 200%
- 오후 (14-17시): 70%
- 저녁 (17-21시): 250%
- 밤 (21-24시): 120%

### 특별 패턴
- 주말 트래픽 50% 증가
- 5% 확률로 3-5배 트래픽 스파이크
- 포아송 분포 기반 자연스러운 변동

## 통계 출력 예시
```
📊 통계 (최근 60초):
  노출: 1,234 (누적: 45,678)
  클릭: 148 (CTR: 12.00%)
  전환: 12 (CVR: 8.11%)
  Kinesis 전송: 1,394 성공, 0 실패
  초당 평균: 23.2 events/sec
  활성 세션: 342
```

## Docker 실행 (선택사항)

### Dockerfile
```dockerfile
FROM python:3.9-slim

WORKDIR /app

COPY requirements_realtime.txt .
RUN pip install --no-cache-dir -r requirements_realtime.txt

COPY realtime_ad_log_generator.py .
COPY .env .

CMD ["python", "realtime_ad_log_generator.py"]
```

### 실행
```bash
docker build -t realtime-log-generator .
docker run --env-file .env realtime-log-generator
```

## 모니터링

### CloudWatch 메트릭
자동으로 다음 메트릭이 Kinesis로 전송됩니다:
- `IncomingRecords`: 수신된 레코드 수
- `IncomingBytes`: 수신된 데이터 크기
- `PutRecord.Success`: 성공한 전송
- `PutRecord.Latency`: 전송 지연 시간

### 로그 확인
```bash
# CloudWatch Logs에서 확인
aws logs tail /aws/kinesis/capa-ad-logs-stream --follow
```

## 주의사항
1. AWS 자격증명이 올바르게 설정되어야 합니다
2. Kinesis Stream이 미리 생성되어 있어야 합니다
3. 높은 트래픽 생성 시 AWS 비용에 주의하세요
4. 프로덕션 환경에서는 ECS/Fargate로 배포를 권장합니다
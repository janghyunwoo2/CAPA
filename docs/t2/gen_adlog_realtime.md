# 실시간 광고 로그 생성기 통합 가이드

실시간 트래픽 패턴으로 광고 이벤트(노출/클릭/전환)를 생성해 Kinesis(단일 스트림 또는 이벤트별 3스트림)로 전송합니다. 기존 `gen_adlog_realtime.md`, `gen_adlog_realtime_design.md`, `gen_adlog_realtime_st.md`의 중복을 제거하고 하나로 통합했습니다.

## 1) 주요 특징
- 실시간 이벤트 스트리밍(비동기 처리)
- 시간대/요일/스파이크 반영한 자연스러운 트래픽(포아송 분포)
- 사용자 여정 기반 행동 시뮬레이션(노출→클릭→전환)
- 주기적 통계 출력 및 CloudWatch 지표로 모니터링

## 2) 설치와 환경

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

.env 예시(모드 선택형):
```
AWS_ACCESS_KEY_ID=...
AWS_SECRET_ACCESS_KEY=...
AWS_DEFAULT_REGION=ap-northeast-2

# 단일 스트림 모드(설정 시 우선)
KINESIS_STREAM_NAME=capa-ad-logs-stream

# 3스트림 모드(단일 스트림 미설정 시 사용)
KINESIS_IMPRESSION=capa-knss-imp-00
KINESIS_CLICK=capa-knss-clk-00
KINESIS_CONVERSION=capa-knss-cvs-00

# 생성기 파라미터(선택)
BASE_EVENTS_PER_SECOND=10
STATS_INTERVAL_SECONDS=60
ENABLE_DEBUG=false
```

Kinesis 생성(예시):
```bash
aws kinesis create-stream --stream-name capa-ad-logs-stream --shard-count 1 --region ap-northeast-2
```

## 3) 실행

```powershell
python main.py
```

Docker(선택):
```dockerfile
FROM python:3.9-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
CMD ["python", "main.py"]
```
```bash
docker build -t realtime-log-generator .
docker run --env-file .env realtime-log-generator
```

## 4) 트래픽/행동 모델(요약)

- 시간대 가중치: 새벽 20% · 점심 200% · 저녁 250% 등
- 주말 가중치: 평일 대비 +50%
- 랜덤 스파이크: 5% 확률로 3~5배 증가
- 분 단위 변동성: ±20%
- 이벤트 수: 초당 기대치 → 포아송 분포로 실제 생성량 샘플링
- 사용자 여정: 노출 후 일정 확률/지연으로 클릭, 이어서 전환

## 5) 모니터링

- 주기 통계(예):
  - 노출/클릭/전환, CTR/CVR, 초당 평균
- CloudWatch(대표 메트릭): IncomingRecords/Bytes, PutRecord.Success/Latency
```bash
aws logs tail /aws/kinesis/<stream-name> --follow
```

## 6) Firehose→S3(선택)

- 버퍼: 5MB 또는 60초 주기 전송
- 동적 파티셔닝: 타임스탬프 기반
- 변환: JSON→Parquet, 압축 적용

## 7) 주의/권장 사항

- AWS 자격증명/권한과 스트림 생성 상태 확인
- 고부하 테스트 시 비용 유의, 필요 시 샤드 확장
- 운영 배포는 ECS/Fargate 권장

## 8) 생성 이벤트 예시(요약)

- Impression: 위치/포맷/디바이스/지역/세션 등 컨텍스트 포함
- Click: 좌표/랜딩 URL/CPC 비용
- Conversion: 유형/가치/수량/귀속 윈도우

상세 스키마는 코드 및 샘플(JSON) 주석을 참고하세요.
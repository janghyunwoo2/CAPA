# Real-time Ad Log Generator

AWS Kinesis Data Streams(3개: imp/click/conv)로 광고 로그를 실시간 전송하는 생성기입니다.

## 특징

- ad_log_generator.py의 완전한 데이터 구조 유지
- main.py의 실시간 로직 적용 (1초에 1개씩 생성)
- CTR 10%, CVR 20% 확률 기반 이벤트 생성
- AWS 자격증명은 상위 디렉토리의 .env 파일에서 자동으로 로드

## 필요한 환경 변수

상위 디렉토리 (`services/data_pipeline_t2/.env`)에 다음 환경 변수가 설정되어 있어야 합니다:

```bash
AWS_ACCESS_KEY_ID=your_access_key
AWS_SECRET_ACCESS_KEY=your_secret_key
AWS_DEFAULT_REGION=ap-northeast-2

# 이벤트별 Kinesis Stream 이름
KINESIS_IMPRESSION=capa-knss-imp-00
KINESIS_CLICK=capa-knss-clk-00
KINESIS_CONVERSION=capa-knss-cvs-00
```

## 설치

```bash
# Python 가상환경 생성 및 활성화
python -m venv .venv
. .venv/Scripts/Activate.ps1  # Windows PowerShell

# 의존성 설치
pip install -r requirements.txt
# 또는
pip install faker boto3 python-dotenv
```

## 실행

### 로컬 실행

```bash
python main.py
```

### Docker 실행 (선택)

```bash
# Docker 이미지 빌드
docker build -t realtime-log-generator .

# 실행 (상위 .env 파일 마운트)
# Windows PowerShell 예시
docker run --rm -v "${PWD}\..\..\.env":/app/../../.env realtime-log-generator
```

## 생성되는 로그 구조

### 1. Impression (노출)
```json
{
  "event_id": "uuid",
  "timestamp": 1234567890000,
  "impression_id": "uuid",
  "user_id": "user_000001",
  "ad_id": "ad_0001",
  "campaign_id": "campaign_01",
  "advertiser_id": "advertiser_01",
  "platform": "web",
  "device_type": "mobile",
  "os": "ios",
  "delivery_region": "강남구",
  "user_lat": 37.123456,
  "user_long": 126.123456,
  "store_id": "store_0001",
  "food_category": "korean",
  "ad_position": "home_top_rolling",
  "ad_format": "display",
  "user_agent": "Mozilla/5.0...",
  "ip_address": "192.168.1.0",
  "session_id": "uuid",
  "keyword": "keyword_001",
  "cost_per_impression": 0.05
}
```

### 2. Click (클릭)
```json
{
  "event_id": "uuid",
  "timestamp": 1234567890000,
  "click_id": "uuid",
  "impression_id": "uuid",
  "user_id": "user_000001",
  "ad_id": "ad_0001",
  "campaign_id": "campaign_01",
  "advertiser_id": "advertiser_01",
  "platform": "web",
  "device_type": "mobile",
  "click_position_x": 365,
  "click_position_y": 45,
  "landing_page_url": "https://store.example.com/advertiser_01/store_0001",
  "cost_per_click": 2.50
}
```

### 3. Conversion (전환)
```json
{
  "event_id": "uuid",
  "timestamp": 1234567890000,
  "conversion_id": "uuid",
  "click_id": "uuid",
  "impression_id": "uuid",
  "user_id": "user_000001",
  "ad_id": "ad_0001",
  "campaign_id": "campaign_01",
  "advertiser_id": "advertiser_01",
  "conversion_type": "purchase",
  "conversion_value": 35000.0,
  "product_id": "prod_00001",
  "quantity": 2,
  "store_id": "store_0001",
  "delivery_region": "강남구",
  "attribution_window": "1day"
}
```

## 동작 방식

1. 매초마다 1개의 노출(impression) 이벤트 생성
2. 10% 확률로 클릭 이벤트 발생 (0.5-2초 딜레이)
3. 클릭이 발생한 경우, 20% 확률로 전환 이벤트 발생 (1-5초 딜레이)
4. 모든 이벤트는 즉시 Kinesis(imp/click/conv 스트림)로 전송

## 중지

`Ctrl+C`를 눌러 프로그램을 중지할 수 있습니다. 중지 시 전송 통계가 출력됩니다.
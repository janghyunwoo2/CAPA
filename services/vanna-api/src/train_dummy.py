import requests
import json
import logging
import sys

# 로깅 설정
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Vanna API의 URL
API_URL = "http://localhost:8000/train"


def send_training_data(data: dict):
    headers = {"Content-Type": "application/json"}
    try:
        response = requests.post(API_URL, headers=headers, json=data)
        response.raise_for_status()
        logger.info(
            f"성공적으로 전송됨: {json.dumps(data, ensure_ascii=False)[:50]}... 응답: {response.json()}"
        )
    except requests.exceptions.RequestException as e:
        logger.error(f"전송 실패: {e}")
        if hasattr(e, "response") and e.response is not None:
            logger.error(f"상세 응답: {e.response.text}")


def main():
    logger.info("Vanna AI 더미(학습) 데이터 주입을 시작합니다...")

    train_items = [
        # 1. 스키마 (DDL)
        {
            "ddl": """
            CREATE EXTERNAL TABLE ad_events_raw (
                event_id string, 
                event_type string, 
                timestamp bigint, 
                campaign_id string, 
                user_id string, 
                device_type string, 
                bid_price double
            ) PARTITIONED BY (
                year string, 
                month string, 
                day string
            ) STORED AS PARQUET LOCATION 's3://capa-data-lake-xxx/raw/';
            """
        },
        # 2. 비즈니스 용어 설명 (Documentation)
        {
            "documentation": "ad_events_raw 테이블은 광고 노출(impression), 클릭(click), 전환(conversion) 이벤트를 저장하며, event_type 컬럼으로 구분합니다. bid_price는 각 광고 이벤트의 비용(매출)을 의미합니다."
        },
        {
            "documentation": "CTR(클릭률)은 (event_type='click'인 갯수) / (event_type='impression'인 갯수) 로 계산합니다. ROAS는 (전환 매출) / (광고비) 로 계산합니다."
        },
        # 3. SQL 예제 (SQL Examples)
        {"sql": "SELECT SUM(bid_price) FROM ad_events_raw"},
        {
            "sql": "SELECT campaign_id, COUNT(*) as clicks FROM ad_events_raw WHERE event_type = 'click' GROUP BY campaign_id ORDER BY clicks DESC"
        },
        {
            "sql": "SELECT event_type, COUNT(*) as event_count FROM ad_events_raw GROUP BY event_type"
        },
    ]

    for item in train_items:
        send_training_data(item)

    logger.info("학습 데이터 주입이 완료되었습니다.")


if __name__ == "__main__":
    main()

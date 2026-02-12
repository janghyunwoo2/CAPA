import time
import json
import random
import uuid
import boto3
import os
from datetime import datetime
from faker import Faker

# faker 초기화
fake = Faker()

# Kinesis 설정
STREAM_NAME = os.getenv("STREAM_NAME", "capa-stream")
REGION = os.getenv("AWS_REGION", "ap-northeast-2")

try:
    kinesis_client = boto3.client("kinesis", region_name=REGION)
except Exception as e:
    print(f"Failed to create Kinesis client: {e}")
    kinesis_client = None


class AdLogGenerator:
    def __init__(self):
        self.users = [str(uuid.uuid4()) for _ in range(100)]  # 100명의 가상 유저
        self.shops = [str(uuid.uuid4()) for _ in range(20)]  # 20개의 가상 가게
        self.placements = ["main_banner", "search_top", "list_middle", "sidebar"]
        self.fake = Faker()  # Initialize Faker as an instance variable

    def generate_impression(self):
        user_id = self.fake.uuid4()
        campaign_id = self.fake.uuid4()

        # 1. Device Type (Platform)
        device_type = random.choice(["iOS", "Android", "Web"])

        # 2. Bid Price
        bid_price = round(random.uniform(10.0, 2000.0), 2)

        # 3. Timestamp (BigInt, milliseconds)
        timestamp = int(datetime.now().timestamp() * 1000)

        # 4. Construct Payload (Strictly matching Glue Schema)
        impression = {
            "event_id": self.fake.uuid4(),
            "event_type": "impression",
            "timestamp": timestamp,
            "campaign_id": campaign_id,
            "user_id": user_id,
            "device_type": device_type,
            "bid_price": bid_price,
        }
        return impression

    def generate_click(self, impression):
        # Derive from impression to maintain consistency (where possible)
        # But strictly follow Glue Schema
        timestamp = int(datetime.now().timestamp() * 1000)

        click = {
            "event_id": self.fake.uuid4(),
            "event_type": "click",
            "timestamp": timestamp,
            "campaign_id": impression["campaign_id"],
            "user_id": impression["user_id"],
            "device_type": impression["device_type"],
            "bid_price": impression["bid_price"],  # Pass through for schema consistency
        }
        return click

    def generate_conversion(self, click):
        timestamp = int(datetime.now().timestamp() * 1000)

        conversion = {
            "event_id": self.fake.uuid4(),
            "event_type": "conversion",
            "timestamp": timestamp,
            "campaign_id": click["campaign_id"],
            "user_id": click["user_id"],
            "device_type": click["device_type"],
            "bid_price": click["bid_price"],  # Pass through
        }
        return conversion

    def send_to_kinesis(self, record: dict):
        if not kinesis_client:
            print(json.dumps(record), flush=True)
            return

        try:
            response = kinesis_client.put_record(
                StreamName=STREAM_NAME,
                Data=json.dumps(record)
                + "\n",  # Athena/Firehose often prefers newline delimited JSON
                PartitionKey=record["user_id"],
            )
            print(
                f"[OK] Sent: {record['event_type']} - Shard: {response['ShardId']}",
                flush=True,
            )
        except Exception as e:
            print(f"[ERROR] Error sending to Kinesis: {e}", flush=True)

    def run(self):
        print(
            f"Starting Ad Log Generator (Target: {STREAM_NAME})...",
            flush=True,
        )

        while True:
            # 1. 노출 발생
            impr = self.generate_impression()
            self.send_to_kinesis(impr)

            # 2. 클릭 확률 (CTR: 10% 가정)
            if random.random() < 0.10:
                time.sleep(random.uniform(0.5, 2.0))  # 클릭 딜레이
                click = self.generate_click(impr)
                self.send_to_kinesis(click)

                # 3. 전환 확률 (CVR: 20% 가정)
                if random.random() < 0.20:
                    time.sleep(random.uniform(1.0, 5.0))  # 전환 딜레이
                    conv = self.generate_conversion(click)
                    self.send_to_kinesis(conv)

            # 기본 대기 (1초에 하나씩)
            time.sleep(1.0)


if __name__ == "__main__":
    generator = AdLogGenerator()
    generator.run()

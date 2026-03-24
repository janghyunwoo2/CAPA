import time
import json
import random
import uuid
from datetime import datetime
from faker import Faker

# faker 초기화
fake = Faker()


class AdLogGenerator:
    def __init__(self):
        self.users = [str(uuid.uuid4()) for _ in range(100)]  # 100명의 가상 유저
        self.shops = [str(uuid.uuid4()) for _ in range(20)]  # 20개의 가상 가게
        self.placements = ["main_banner", "search_top", "list_middle", "sidebar"]

    def generate_impression(self) -> dict:
        """광고 노출 로그 생성"""
        impression_id = str(uuid.uuid4())
        user_id = random.choice(self.users)
        shop_id = random.choice(self.shops)

        log = {
            "event_type": "impression",
            "event_id": impression_id,
            "timestamp": datetime.now().isoformat(),
            "user_id": user_id,
            "ad_id": str(uuid.uuid4()),  # Creative ID
            "campaign_id": str(uuid.uuid4()),
            "shop_id": shop_id,
            "placement": random.choice(self.placements),
            "platform": random.choice(["Android", "iOS", "Web"]),
            "bid_price": round(random.uniform(100, 2000), 2),
        }
        return log

    def generate_click(self, impression_log: dict) -> dict:
        """노출 로그 기반 클릭 로그 생성"""
        log = {
            "event_type": "click",
            "event_id": str(uuid.uuid4()),
            "timestamp": datetime.now().isoformat(),
            "user_id": impression_log["user_id"],
            "ad_id": impression_log["ad_id"],
            "impression_id": impression_log["event_id"],
            "shop_id": impression_log["shop_id"],
            "clickspot_x": random.randint(0, 300),
            "clickspot_y": random.randint(0, 100),
            # Second Price Auction 등을 고려하여 입찰가보다 같거나 낮게 책정
            "cpc_cost": round(
                min(
                    impression_log["bid_price"],
                    random.uniform(
                        impression_log["bid_price"] * 0.5, impression_log["bid_price"]
                    ),
                ),
                2,
            ),
        }
        return log

    def generate_conversion(self, click_log: dict) -> dict:
        """클릭 로그 기반 전환 로그 생성"""
        action = random.choice(["view_menu", "add_to_cart", "order"])

        log = {
            "event_type": "conversion",
            "event_id": str(uuid.uuid4()),
            "timestamp": datetime.now().isoformat(),
            "user_id": click_log["user_id"],
            "shop_id": click_log["shop_id"],
            "click_id": click_log["event_id"],
            "ad_id": click_log["ad_id"],
            "action_type": action,
            "item_count": random.randint(1, 5),
        }

        if action == "order":
            log["total_amount"] = round(random.uniform(15000, 50000), 0)

        return log

    def run(self):
        print(
            "Starting Ad Log Generator (Impression -> Click -> Conversion)...",
            flush=True,
        )
        print("Logs will be printed in JSON format.", flush=True)

        while True:
            # 1. 노출 발생
            impr = self.generate_impression()
            print(json.dumps(impr), flush=True)

            # 2. 클릭 확률 (CTR: 10% 가정)
            if random.random() < 0.10:
                time.sleep(random.uniform(0.5, 2.0))  # 클릭 딜레이
                click = self.generate_click(impr)
                print(json.dumps(click), flush=True)

                # 3. 전환 확률 (CVR: 20% 가정)
                if random.random() < 0.20:
                    time.sleep(random.uniform(1.0, 5.0))  # 전환 딜레이
                    conv = self.generate_conversion(click)
                    print(json.dumps(conv), flush=True)

            # 기본 대기 (너무 빠르지 않게)
            time.sleep(random.uniform(0.1, 0.5))


if __name__ == "__main__":
    generator = AdLogGenerator()
    generator.run()

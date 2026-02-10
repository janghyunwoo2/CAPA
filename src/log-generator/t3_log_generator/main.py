"""
최소+확장 구조 광고 로그 생성기
====================================
기본은 최소 필드로 가볍게, 필요하면 주석 해제로 확장 가능

기본 필드:
- Impression: 8개
- Click: 7개  
- Conversion: 7개

확장 필드 (주석 처리):
- 세션 추적, 디바이스 정보, 지역 정보 등
"""

import time
import json
import random
import uuid
from datetime import datetime
from faker import Faker

fake = Faker("ko_KR")


# =============================================================================
# 설정 (확장 기능 on/off)
# =============================================================================

class Config:
    """확장 기능을 켜고 끌 수 있는 설정"""
    
    # === 마스터 데이터 크기 ===
    USERS_COUNT = 200
    SHOPS_COUNT = 30
    
    # === 확장 필드 활성화 (True로 바꾸면 해당 필드 추가) ===
    ENABLE_SESSION = False       # session_id 추가
    ENABLE_DEVICE_INFO = False   # platform, device_type, os 추가
    ENABLE_GEO_INFO = False      # geo_region, geo_city 추가
    ENABLE_ADVANCED = False      # 기타 고급 필드 추가


# =============================================================================
# 기본 데이터
# =============================================================================

SHOP_CATEGORIES = {
    "치킨": {"bid_range": (800, 2000), "ctr_base": 0.08},
    "피자": {"bid_range": (700, 1800), "ctr_base": 0.07},
    "한식": {"bid_range": (500, 1500), "ctr_base": 0.06},
    "중식": {"bid_range": (600, 1600), "ctr_base": 0.06},
    "카페": {"bid_range": (200, 800), "ctr_base": 0.05},
    "분식": {"bid_range": (300, 1000), "ctr_base": 0.09},
}

REGIONS = {
    "서울": ["강남구", "서초구", "마포구", "송파구"],
    "경기": ["성남시", "수원시", "용인시", "고양시"],
    "부산": ["해운대구", "부산진구", "동래구"],
}


# =============================================================================
# 마스터 데이터
# =============================================================================

class MasterData:
    """미리 만들어둔 유저/가게 목록"""
    
    def __init__(self):
        random.seed(42)  # 재현 가능하도록
        
        # === 유저 (기본) ===
        self.users = []
        for _ in range(Config.USERS_COUNT):
            user = {"user_id": str(uuid.uuid4())}
            
            # 확장: 지역 정보
            if Config.ENABLE_GEO_INFO:
                region = random.choice(list(REGIONS.keys()))
                user["region"] = region
                user["city"] = random.choice(REGIONS[region])
            
            self.users.append(user)
        
        # === 가게 (기본 + 카테고리) ===
        self.shops = []
        for _ in range(Config.SHOPS_COUNT):
            category = random.choice(list(SHOP_CATEGORIES.keys()))
            shop = {
                "shop_id": str(uuid.uuid4()),
                "shop_name": f"{fake.last_name()}{random.choice(['네', '의', ''])} {category}",
                "category": category,
            }
            self.shops.append(shop)
        
        random.seed()  # 시드 해제


# =============================================================================
# 로그 생성기
# =============================================================================

class AdLogGenerator:
    """광고 로그 생성기 (최소+확장 구조)"""
    
    def __init__(self):
        self.master = MasterData()
        self._active_sessions = {}  # 세션 관리용
    
    def _get_session_id(self, user_id: str) -> str:
        """세션 ID 관리 (확장 기능)"""
        if not Config.ENABLE_SESSION:
            return None
        
        if user_id not in self._active_sessions or random.random() < 0.05:
            self._active_sessions[user_id] = str(uuid.uuid4())
        return self._active_sessions[user_id]
    
    def _get_ctr(self, category: str) -> float:
        """카테고리별 CTR 계산"""
        base_ctr = SHOP_CATEGORIES.get(category, {}).get("ctr_base", 0.06)
        return base_ctr * random.uniform(0.8, 1.2)  # ±20% 변동
    
    def _get_cvr(self, action_type: str) -> float:
        """action_type별 CVR"""
        cvr_map = {
            "view_menu": 0.40,
            "add_to_cart": 0.15,
            "order": 0.05,
        }
        return cvr_map.get(action_type, 0.10)
    
    def generate_impression(self) -> dict:
        """Impression (노출) 로그 생성"""
        user = random.choice(self.master.users)
        shop = random.choice(self.master.shops)
        category = shop["category"]
        
        # 입찰가
        bid_range = SHOP_CATEGORIES[category]["bid_range"]
        bid_price = round(random.uniform(*bid_range), 2)
        
        # === 기본 필드 (항상 포함) ===
        log = {
            "event_type": "impression",
            "event_id": str(uuid.uuid4()),
            "timestamp": datetime.now().isoformat(),
            "user_id": user["user_id"],
            "ad_id": str(uuid.uuid4()),
            "shop_id": shop["shop_id"],
            "category": category,
            "bid_price": bid_price,
        }
        
        # === 확장 필드 (설정에 따라 추가) ===
        
        # 세션 추적
        if Config.ENABLE_SESSION:
            log["session_id"] = self._get_session_id(user["user_id"])
        
        # 디바이스 정보
        if Config.ENABLE_DEVICE_INFO:
            platform = random.choices(
                ["Android", "iOS", "Web"],
                weights=[0.55, 0.35, 0.10],
                k=1
            )[0]
            log["platform"] = platform
            log["device_type"] = random.choice(["mobile", "tablet"]) if platform != "Web" else "desktop"
        
        # 지역 정보
        if Config.ENABLE_GEO_INFO and "region" in user:
            log["geo_region"] = user["region"]
            log["geo_city"] = user["city"]
        
        # 고급 필드
        if Config.ENABLE_ADVANCED:
            log["campaign_id"] = str(uuid.uuid4())
            log["win_price"] = round(bid_price * random.uniform(0.6, 1.0), 2)
            log["is_viewable"] = random.choices([True, False], weights=[0.75, 0.25], k=1)[0]
        
        # 내부용 (로그에는 미포함)
        log["_category"] = category
        return log
    
    def generate_click(self, impression_log: dict) -> dict:
        """Click (클릭) 로그 생성"""
        cpc_cost = round(
            impression_log["bid_price"] * random.uniform(0.5, 1.0),
            2
        )
        
        # === 기본 필드 ===
        log = {
            "event_type": "click",
            "event_id": str(uuid.uuid4()),
            "timestamp": datetime.now().isoformat(),
            "impression_id": impression_log["event_id"],
            "user_id": impression_log["user_id"],
            "shop_id": impression_log["shop_id"],
            "cpc_cost": cpc_cost,
        }
        
        # === 확장 필드 ===
        
        if Config.ENABLE_SESSION and "session_id" in impression_log:
            log["session_id"] = impression_log["session_id"]
        
        if Config.ENABLE_ADVANCED:
            log["clickspot_x"] = random.randint(0, 360)
            log["clickspot_y"] = random.randint(0, 640)
            log["click_delay_ms"] = random.randint(500, 15000)
        
        return log
    
    def generate_conversion(self, click_log: dict) -> dict:
        """Conversion (전환) 로그 생성"""
        action_type = random.choices(
            ["view_menu", "add_to_cart", "order"],
            weights=[0.55, 0.30, 0.15],
            k=1
        )[0]
        
        # 금액 설정
        amount_ranges = {
            "view_menu": (0, 0),
            "add_to_cart": (8000, 35000),
            "order": (15000, 50000),
        }
        amount_range = amount_ranges[action_type]
        total_amount = round(random.uniform(*amount_range), 0) if amount_range[1] > 0 else 0
        
        # === 기본 필드 ===
        log = {
            "event_type": "conversion",
            "event_id": str(uuid.uuid4()),
            "timestamp": datetime.now().isoformat(),
            "click_id": click_log["event_id"],
            "user_id": click_log["user_id"],
            "shop_id": click_log["shop_id"],
            "action_type": action_type,
            "total_amount": total_amount,
        }
        
        # === 확장 필드 ===
        
        if Config.ENABLE_SESSION and "session_id" in click_log:
            log["session_id"] = click_log["session_id"]
        
        if Config.ENABLE_ADVANCED:
            log["item_count"] = random.randint(1, 5)
            log["conversion_delay_ms"] = random.randint(3000, 300000)
        
        return log
    
    def run(self):
        """메인 실행 루프"""
        print(
            "Starting Ad Log Generator (Minimal + Extensible)...",
            flush=True,
        )
        print("Logs will be printed in JSON format.", flush=True)
        
        while True:
            # 1. 노출 로그
            impr = self.generate_impression()
            category = impr.pop("_category")
            print(json.dumps(impr, ensure_ascii=False), flush=True)
            
            # 2. CTR에 따라 클릭
            ctr = self._get_ctr(category)
            if random.random() < ctr:
                time.sleep(random.uniform(0.3, 1.5))
                click = self.generate_click(impr)
                print(json.dumps(click, ensure_ascii=False), flush=True)
                
                # 3. CVR에 따라 전환
                action = random.choices(
                    ["view_menu", "add_to_cart", "order"],
                    weights=[0.55, 0.30, 0.15],
                    k=1
                )[0]
                cvr = self._get_cvr(action)
                if random.random() < cvr:
                    time.sleep(random.uniform(0.5, 3.0))
                    conv = self.generate_conversion(click)
                    print(json.dumps(conv, ensure_ascii=False), flush=True)
            
            # 기본 대기
            time.sleep(random.uniform(0.1, 0.5))


if __name__ == "__main__":
    generator = AdLogGenerator()
    generator.run()

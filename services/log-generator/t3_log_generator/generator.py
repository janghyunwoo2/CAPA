"""
Ad Log Generator - 광고 로그 생성기 (순수 로직)
"""

import random
import uuid
from datetime import datetime
from typing import Dict
from faker import Faker

fake = Faker("ko_KR")


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
    
    def __init__(self, users_count: int = 200, shops_count: int = 30):
        random.seed(42)  # 재현 가능하도록
        
        # 유저 생성
        self.users = []
        for _ in range(users_count):
            self.users.append({"user_id": str(uuid.uuid4())})
        
        # 가게 생성
        self.shops = []
        for _ in range(shops_count):
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
    """광고 로그 생성기 (순수 로직만)"""
    
    def __init__(self, users_count: int = 200, shops_count: int = 30):
        self.master = MasterData(users_count, shops_count)
        self._active_sessions = {}
    
    def _get_ctr(self, category: str) -> float:
        """카테고리별 CTR 계산"""
        base_ctr = SHOP_CATEGORIES.get(category, {}).get("ctr_base", 0.06)
        return base_ctr * random.uniform(0.8, 1.2)
    
    def _get_cvr(self, action_type: str) -> float:
        """action_type별 CVR"""
        cvr_map = {
            "view_menu": 0.40,
            "add_to_cart": 0.15,
            "order": 0.05,
        }
        return cvr_map.get(action_type, 0.10)
    
    def generate_impression(self) -> Dict:
        """Impression (노출) 로그 생성"""
        user = random.choice(self.master.users)
        shop = random.choice(self.master.shops)
        category = shop["category"]
        
        # 입찰가
        bid_range = SHOP_CATEGORIES[category]["bid_range"]
        bid_price = round(random.uniform(*bid_range), 2)
        
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
        
        # 내부용 (로그에는 미포함, 나중에 제거)
        log["_category"] = category
        return log
    
    def generate_click(self, impression_log: Dict) -> Dict:
        """Click (클릭) 로그 생성"""
        cpc_cost = round(
            impression_log["bid_price"] * random.uniform(0.5, 1.0),
            2
        )
        
        log = {
            "event_type": "click",
            "event_id": str(uuid.uuid4()),
            "timestamp": datetime.now().isoformat(),
            "impression_id": impression_log["event_id"],
            "user_id": impression_log["user_id"],
            "shop_id": impression_log["shop_id"],
            "cpc_cost": cpc_cost,
        }
        
        return log
    
    def generate_conversion(self, click_log: Dict) -> Dict:
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
        
        return log
    
    def should_click(self, category: str) -> bool:
        """클릭 여부 결정"""
        ctr = self._get_ctr(category)
        return random.random() < ctr
    
    def should_convert(self, action_type: str) -> bool:
        """전환 여부 결정"""
        cvr = self._get_cvr(action_type)
        return random.random() < cvr

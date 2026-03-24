"""
Ad Log Generator - 광고 로그 생성기 (순수 로직)
ad_log_generator.py의 데이터 구조 유지, main.py의 로직 적용
"""

import random
import uuid
from datetime import datetime
from typing import Dict
from faker import Faker

# Faker 초기화
fake = Faker('ko_KR')

# =============================================================================
# 기본 데이터 (ad_log_generator.py에서 가져옴)
# =============================================================================

USERS = [f"user_{i:06d}" for i in range(1, 100001)]
ADS = [f"ad_{i:04d}" for i in range(1, 1001)]
CAMPAIGNS = [f"campaign_{i:02d}" for i in range(1, 6)]
ADVERTISERS = [f"advertiser_{i:02d}" for i in range(1, 31)]
STORES = [f"store_{i:04d}" for i in range(1, 5001)]
PLATFORMS = ["web", "app_ios", "app_android", "tablet_ios", "tablet_android"]
DEVICE_TYPES = ["mobile", "tablet", "desktop", "others"]
OS_TYPES = ["ios", "android", "macos", "windows"]
REGIONS = ["강남구", "서초구", "마포구", "송파구", "영등포구", "종로구", "중구", 
           "용산구", "성동구", "광진구", "동대문구", "중랑구", "성북구", "강북구",
           "도봉구", "노원구", "은평구", "서대문구", "구로구", "금천구", "관악구",
           "동작구", "양천구", "강서구", "강동구"]
FOOD_CATEGORIES = ["korean", "chinese", "japanese", "asian", "western",
                    "pork", "pizza", "chicken", "steam/soup","bunsik",
                    "cafe/dessert", "burger", "pasta", "seafood"]
AD_POSITIONS = ["home_top_rolling", "list_top_fixed", "search_ai_recommend", "checkout_bottom"]
AD_FORMATS = ["display", "native", "video", "discount_coupon"]
KEYWORDS = [f"keyword_{i:03d}" for i in range(1, 501)]
PRODUCTS = [f"prod_{i:05d}" for i in range(1, 10001)]
CONVERSION_TYPES = ["purchase", "signup", "download", "view_content", "add_to_cart"]


# =============================================================================
# 로그 생성기 (main.py 로직 기반)
# =============================================================================

class AdLogGenerator:
    """광고 로그 생성기"""
    
    def __init__(self):
        self.faker = Faker('ko_KR')
        self.advertiser_store_mapping = self._create_advertiser_store_mapping()
        
    def _create_advertiser_store_mapping(self) -> Dict[str, list]:
        """광고주와 상점의 매핑을 생성합니다."""
        mapping = {}
        store_idx = 0
        
        # advertiser_01 ~ advertiser_10: 각 50개 상점
        for i in range(1, 11):
            advertiser = f"advertiser_{i:02d}"
            mapping[advertiser] = STORES[store_idx:store_idx+50]
            store_idx += 50
            
        # advertiser_11 ~ advertiser_25: 각 100개 상점
        for i in range(11, 26):
            advertiser = f"advertiser_{i:02d}"
            mapping[advertiser] = STORES[store_idx:store_idx+100]
            store_idx += 100
            
        # advertiser_26 ~ advertiser_30: 각 200개 상점
        for i in range(26, 31):
            advertiser = f"advertiser_{i:02d}"
            mapping[advertiser] = STORES[store_idx:store_idx+200]
            store_idx += 200
            
        return mapping
    
    def generate_impression(self) -> Dict:
        """노출 로그 생성 (ad_log_generator.py 구조 유지)"""
        advertiser = random.choice(ADVERTISERS)
        store = random.choice(self.advertiser_store_mapping[advertiser])
        
        impression = {
            "event_id": str(uuid.uuid4()),
            "timestamp": int(datetime.now().timestamp() * 1000),  # milliseconds
            "impression_id": str(uuid.uuid4()),
            "user_id": random.choice(USERS),
            "ad_id": random.choice(ADS),
            "campaign_id": random.choice(CAMPAIGNS),
            "advertiser_id": advertiser,
            "platform": random.choice(PLATFORMS),
            "device_type": random.choice(DEVICE_TYPES),
            "os": random.choice(OS_TYPES),
            "delivery_region": random.choice(REGIONS),
            "user_lat": round(random.uniform(37.4, 37.7), 6),
            "user_long": round(random.uniform(126.8, 127.1), 6),
            "store_id": store,
            "food_category": random.choice(FOOD_CATEGORIES),
            "ad_position": random.choice(AD_POSITIONS),
            "ad_format": random.choice(AD_FORMATS),
            "user_agent": self.faker.user_agent(),
            "ip_address": f"{random.randint(1,255)}.{random.randint(0,255)}.{random.randint(0,255)}.0",
            "session_id": str(uuid.uuid4()),
            "keyword": random.choice(KEYWORDS),
            "cost_per_impression": round(random.uniform(0.005, 0.10), 3)
        }
        
        # 내부 참조용 데이터 저장 (전송하지 않음)
        impression['_internal'] = {
            'ad_format': impression['ad_format'],
            'store_id': store,
            'advertiser_id': advertiser,
            'delivery_region': impression['delivery_region']
        }
        
        return impression
    
    def generate_click(self, impression: Dict) -> Dict:
        """클릭 로그 생성"""
        click = {
            "event_id": str(uuid.uuid4()),

            "timestamp": int(datetime.now().timestamp() * 1000),
            "click_id": str(uuid.uuid4()),
            "impression_id": impression['impression_id'],
            "user_id": impression['user_id'],
            "ad_id": impression['ad_id'],
            "campaign_id": impression['campaign_id'],
            "advertiser_id": impression['advertiser_id'],
            "platform": impression['platform'],
            "device_type": impression['device_type'],
            "click_position_x": random.randint(0, 728),
            "click_position_y": random.randint(0, 90),
            "landing_page_url": f"https://store.example.com/{impression['advertiser_id']}/{impression['_internal']['store_id']}",
            "cost_per_click": round(random.uniform(0.1, 5.0), 2)
        }
        
        # 내부 참조용 데이터 전달
        click['_internal'] = impression['_internal']
        
        return click
    
    def generate_conversion(self, click: Dict) -> Dict:
        """전환 로그 생성"""
        conversion_type = random.choice(CONVERSION_TYPES)
        
        conversion = {
            "event_id": str(uuid.uuid4()),

            "timestamp": int(datetime.now().timestamp() * 1000),
            "conversion_id": str(uuid.uuid4()),
            "click_id": click['click_id'],
            "impression_id": click['impression_id'],
            "user_id": click['user_id'],
            "ad_id": click['ad_id'],
            "campaign_id": click['campaign_id'],
            "advertiser_id": click['advertiser_id'],
            "conversion_type": conversion_type,
            "conversion_value": round(random.uniform(1.0, 10000.0), 2),
            "product_id": random.choice(PRODUCTS),
            "quantity": random.randint(1, 10),
            "store_id": click['_internal']['store_id'],
            "delivery_region": click['_internal']['delivery_region'],
            "attribution_window": random.choice(['1day', '7day', '30day'])
        }
        
        return conversion
    
    def should_click(self, ad_format: str, delivery_region: str = "") -> bool:
        """CTR 확률 계산 (ad_log_generator.py와 동일한 패턴 적용)"""
        # ad_format별 CTR 범위
        ctr_ranges = {
            "display": (0.01, 0.03),
            "native": (0.02, 0.04),
            "video": (0.03, 0.05),
            "discount_coupon": (0.025, 0.045)
        }
        
        # 기본 CTR 계산
        min_ctr, max_ctr = ctr_ranges.get(ad_format, (0.02, 0.04))
        ctr = random.uniform(min_ctr, max_ctr)
        
        # 강남/서초 지역 가중치 (1.2배)
        if delivery_region in ["강남구", "서초구"]:
            ctr = ctr * 1.2
        
        return random.random() < ctr
    
    def should_convert(self) -> bool:
        """CVR 확률 계산 (ad_log_generator.py와 동일한 패턴 적용)"""
        # conversion_type별 CVR 범위
        cvr_ranges = {
            "view_content": (0.05, 0.10),
            "add_to_cart": (0.03, 0.07),
            "signup": (0.02, 0.05),
            "download": (0.02, 0.05),
            "purchase": (0.01, 0.03)
        }
        
        # 랜덤하게 conversion_type 선택
        conversion_type = random.choice(list(cvr_ranges.keys()))
        min_cvr, max_cvr = cvr_ranges[conversion_type]
        cvr = random.uniform(min_cvr, max_cvr)
        
        return random.random() < cvr
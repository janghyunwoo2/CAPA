"""
Ad Log Generator - 가중치 적용 버전 (Weighted Distribution)

각 컬럼 값에 비율(가중치)을 부여하여 현실적인 데이터 분포를 생성합니다.
전체 데이터 생성량은 기존과 동일하게 유지됩니다.

변경 포인트:
  - random.choice() → random.choices(population, weights=..., k=1)[0]
  - 각 컬럼별 가중치는 random.uniform()으로 약간의 노이즈를 적용해 고정 편향을 방지
  - 전체 합이 100%가 되도록 정규화(normalize) 처리
"""

import random
import uuid
from datetime import datetime
from typing import Dict, List

from faker import Faker

# Faker 초기화
fake = Faker('ko_KR')

# =============================================================================
# 기본 데이터 (generator.py와 동일)
# =============================================================================

USERS = [f"user_{i:06d}" for i in range(1, 100001)]
ADS = [f"ad_{i:04d}" for i in range(1, 1001)]
CAMPAIGNS = [f"campaign_{i:02d}" for i in range(1, 6)]
ADVERTISERS = [f"advertiser_{i:02d}" for i in range(1, 31)]
STORES = [f"store_{i:04d}" for i in range(1, 5001)]
PLATFORMS = ["web", "app_ios", "app_android", "tablet_ios", "tablet_android"]
DEVICE_TYPES = ["mobile", "tablet", "desktop", "others"]
OS_TYPES = ["ios", "android", "macos", "windows"]
REGIONS = [
    "강남구", "서초구", "마포구", "송파구", "영등포구", "종로구", "중구",
    "용산구", "성동구", "광진구", "동대문구", "중랑구", "성북구", "강북구",
    "도봉구", "노원구", "은평구", "서대문구", "구로구", "금천구", "관악구",
    "동작구", "양천구", "강서구", "강동구",
]
FOOD_CATEGORIES = [
    "korean", "chinese", "japanese", "asian", "western",
    "pork", "pizza", "chicken", "steam/soup", "bunsik",
    "cafe/dessert", "burger", "pasta", "seafood",
]
AD_POSITIONS = ["home_top_rolling", "list_top_fixed", "search_ai_recommend", "checkout_bottom"]
AD_FORMATS = ["display", "native", "video", "discount_coupon"]
KEYWORDS = [f"keyword_{i:03d}" for i in range(1, 501)]
PRODUCTS = [f"prod_{i:05d}" for i in range(1, 10001)]
CONVERSION_TYPES = ["purchase", "signup", "download", "view_content", "add_to_cart"]


# =============================================================================
# 가중치 설정 (기준: 각 컬럼 합계 = 100%)
# 값에 random.uniform 노이즈를 곱해 매 실행마다 분포가 미세하게 달라짐
# =============================================================================

def _normalize(weights: List[float]) -> List[float]:
    """가중치 리스트를 확률 합계 1.0으로 정규화합니다."""
    total = sum(weights)
    return [w / total for w in weights]


def _jitter(base: float, noise: float = 0.15) -> float:
    """기준값에 ±noise 범위의 random.uniform 노이즈를 적용합니다."""
    return base * random.uniform(1.0 - noise, 1.0 + noise)


# ---------- PLATFORMS 가중치 ----------
# 배달앱 특성상 모바일 앱 중심 (app_ios + app_android > 60%)
PLATFORM_WEIGHTS_BASE = {
    "web": 15.0,
    "app_ios": 30.0,
    "app_android": 35.0,
    "tablet_ios": 12.0,
    "tablet_android": 8.0,
}

# ---------- DEVICE_TYPES 가중치 ----------
# 모바일이 압도적 (80%)
DEVICE_TYPE_WEIGHTS_BASE = {
    "mobile": 80.0,
    "tablet": 15.0,
    "desktop": 4.0,
    "others": 1.0,
}

# ---------- OS_TYPES 가중치 ----------
# iOS/Android가 대부분
OS_TYPE_WEIGHTS_BASE = {
    "ios": 38.0,
    "android": 48.0,
    "macos": 8.0,
    "windows": 6.0,
}

# ---------- REGIONS 가중치 ----------
# 강남/서초/송파(강남3구) 집중, 마포/영등포 중간, 나머지 분산
REGION_WEIGHTS_BASE = {
    "강남구": 12.0,
    "서초구": 10.0,
    "송파구": 9.0,
    "마포구": 7.0,
    "영등포구": 6.0,
    "용산구": 5.0,
    "종로구": 4.5,
    "중구": 4.0,
    "성동구": 3.5,
    "광진구": 3.0,
    "강서구": 3.0,
    "양천구": 2.5,
    "동작구": 2.5,
    "관악구": 2.5,
    "은평구": 2.0,
    "서대문구": 2.0,
    "노원구": 2.0,
    "강북구": 2.0,
    "도봉구": 1.8,
    "성북구": 1.8,
    "동대문구": 1.8,
    "중랑구": 1.5,
    "구로구": 1.5,
    "금천구": 1.3,
    "강동구": 3.3,
}

# ---------- FOOD_CATEGORIES 가중치 ----------
# 한식/치킨/피자 상위권, 시즌성 고려
FOOD_CATEGORY_WEIGHTS_BASE = {
    "korean": 20.0,
    "chicken": 18.0,
    "pizza": 12.0,
    "burger": 10.0,
    "chinese": 8.0,
    "cafe/dessert": 7.0,
    "bunsik": 6.0,
    "western": 5.0,
    "japanese": 4.0,
    "pork": 3.5,
    "pasta": 2.5,
    "asian": 1.5,
    "steam/soup": 1.0,
    "seafood": 1.0,
}

# ---------- AD_POSITIONS 가중치 ----------
# 홈 상단 롤링이 가장 많은 트래픽, checkout은 전환 의도 높음
AD_POSITION_WEIGHTS_BASE = {
    "home_top_rolling": 45.0,
    "list_top_fixed": 30.0,
    "search_ai_recommend": 15.0,
    "checkout_bottom": 10.0,
}

# ---------- AD_FORMATS 가중치 ----------
# display 비중 높음, discount_coupon은 특수 케이스
AD_FORMAT_WEIGHTS_BASE = {
    "display": 40.0,
    "native": 30.0,
    "video": 20.0,
    "discount_coupon": 10.0,
}

# ---------- CONVERSION_TYPES 가중치 ----------
# view_content가 가장 많고, purchase는 드묾
CONVERSION_TYPE_WEIGHTS_BASE = {
    "view_content": 35.0,
    "add_to_cart": 28.0,
    "purchase": 20.0,
    "signup": 10.0,
    "download": 7.0,
}

# ---------- CAMPAIGNS 가중치 ----------
# campaign_01/02가 주력 캠페인, 나머지 보조
CAMPAIGN_WEIGHTS_BASE = {
    "campaign_01": 35.0,
    "campaign_02": 28.0,
    "campaign_03": 18.0,
    "campaign_04": 12.0,
    "campaign_05": 7.0,
}


def _build_weighted(
    keys: List[str],
    weights_base: Dict[str, float],
    noise: float = 0.1,
) -> tuple[List[str], List[float]]:
    """
    키 목록과 기준 가중치 딕셔너리로부터
    노이즈가 적용된 정규화 가중치를 반환합니다.
    """
    raw = [_jitter(weights_base[k], noise) for k in keys]
    normalized = _normalize(raw)
    return keys, normalized


def _weighted_choice(
    keys: List[str],
    weights_base: Dict[str, float],
    noise: float = 0.1,
) -> str:
    """가중치 기반 단일 랜덤 선택."""
    population, weights = _build_weighted(keys, weights_base, noise)
    return random.choices(population, weights=weights, k=1)[0]


# =============================================================================
# 로그 생성기 (가중치 적용)
# =============================================================================

class AdLogGeneratorWeighted:
    """광고 로그 생성기 — 가중치 분포 버전"""

    def __init__(self) -> None:
        self.faker = Faker('ko_KR')
        self.advertiser_store_mapping = self._create_advertiser_store_mapping()

    def _create_advertiser_store_mapping(self) -> Dict[str, list]:
        """광고주와 상점의 매핑을 생성합니다."""
        mapping: Dict[str, list] = {}
        store_idx = 0

        # advertiser_01 ~ advertiser_10: 각 50개 상점
        for i in range(1, 11):
            advertiser = f"advertiser_{i:02d}"
            mapping[advertiser] = STORES[store_idx:store_idx + 50]
            store_idx += 50

        # advertiser_11 ~ advertiser_25: 각 100개 상점
        for i in range(11, 26):
            advertiser = f"advertiser_{i:02d}"
            mapping[advertiser] = STORES[store_idx:store_idx + 100]
            store_idx += 100

        # advertiser_26 ~ advertiser_30: 각 200개 상점
        for i in range(26, 31):
            advertiser = f"advertiser_{i:02d}"
            mapping[advertiser] = STORES[store_idx:store_idx + 200]
            store_idx += 200

        return mapping

    # -------------------------------------------------------------------------
    # 가중치 선택 헬퍼
    # -------------------------------------------------------------------------

    def _pick_platform(self) -> str:
        return _weighted_choice(PLATFORMS, PLATFORM_WEIGHTS_BASE)

    def _pick_device_type(self) -> str:
        return _weighted_choice(DEVICE_TYPES, DEVICE_TYPE_WEIGHTS_BASE)

    def _pick_os(self) -> str:
        return _weighted_choice(OS_TYPES, OS_TYPE_WEIGHTS_BASE)

    def _pick_region(self) -> str:
        return _weighted_choice(REGIONS, REGION_WEIGHTS_BASE)

    def _pick_food_category(self) -> str:
        return _weighted_choice(FOOD_CATEGORIES, FOOD_CATEGORY_WEIGHTS_BASE)

    def _pick_ad_position(self) -> str:
        return _weighted_choice(AD_POSITIONS, AD_POSITION_WEIGHTS_BASE)

    def _pick_ad_format(self) -> str:
        return _weighted_choice(AD_FORMATS, AD_FORMAT_WEIGHTS_BASE)

    def _pick_campaign(self) -> str:
        return _weighted_choice(CAMPAIGNS, CAMPAIGN_WEIGHTS_BASE)

    def _pick_conversion_type(self) -> str:
        return _weighted_choice(CONVERSION_TYPES, CONVERSION_TYPE_WEIGHTS_BASE)

    # -------------------------------------------------------------------------
    # 로그 생성
    # -------------------------------------------------------------------------

    def generate_impression(self) -> Dict:
        """노출 로그 생성 (가중치 분포 적용)"""
        advertiser = random.choice(ADVERTISERS)
        store = random.choice(self.advertiser_store_mapping[advertiser])

        ad_format = self._pick_ad_format()
        delivery_region = self._pick_region()

        impression = {
            "event_id": str(uuid.uuid4()),
            "timestamp": int(datetime.now().timestamp() * 1000),
            "impression_id": str(uuid.uuid4()),
            "user_id": random.choice(USERS),
            "ad_id": random.choice(ADS),
            "campaign_id": self._pick_campaign(),
            "advertiser_id": advertiser,
            "platform": self._pick_platform(),
            "device_type": self._pick_device_type(),
            "os": self._pick_os(),
            "delivery_region": delivery_region,
            "user_lat": round(random.uniform(37.4, 37.7), 6),
            "user_long": round(random.uniform(126.8, 127.1), 6),
            "store_id": store,
            "food_category": self._pick_food_category(),
            "ad_position": self._pick_ad_position(),
            "ad_format": ad_format,
            "user_agent": self.faker.user_agent(),
            "ip_address": (
                f"{random.randint(1,255)}."
                f"{random.randint(0,255)}."
                f"{random.randint(0,255)}.0"
            ),
            "session_id": str(uuid.uuid4()),
            "keyword": random.choice(KEYWORDS),
            "cost_per_impression": round(random.uniform(0.005, 0.10), 3),
        }

        impression["_internal"] = {
            "ad_format": ad_format,
            "store_id": store,
            "advertiser_id": advertiser,
            "delivery_region": delivery_region,
        }

        return impression

    def generate_click(self, impression: Dict) -> Dict:
        """클릭 로그 생성 (impression 데이터 그대로 이어받음)"""
        click = {
            "event_id": str(uuid.uuid4()),
            "timestamp": int(datetime.now().timestamp() * 1000),
            "click_id": str(uuid.uuid4()),
            "impression_id": impression["impression_id"],
            "user_id": impression["user_id"],
            "ad_id": impression["ad_id"],
            "campaign_id": impression["campaign_id"],
            "advertiser_id": impression["advertiser_id"],
            "platform": impression["platform"],
            "device_type": impression["device_type"],
            "click_position_x": random.randint(0, 728),
            "click_position_y": random.randint(0, 90),
            "landing_page_url": (
                f"https://store.example.com/"
                f"{impression['advertiser_id']}/"
                f"{impression['_internal']['store_id']}"
            ),
            "cost_per_click": round(random.uniform(0.1, 5.0), 2),
        }

        click["_internal"] = impression["_internal"]
        return click

    def generate_conversion(self, click: Dict) -> Dict:
        """전환 로그 생성 (가중치 conversion_type 적용)"""
        conversion_type = self._pick_conversion_type()

        conversion = {
            "event_id": str(uuid.uuid4()),
            "timestamp": int(datetime.now().timestamp() * 1000),
            "conversion_id": str(uuid.uuid4()),
            "click_id": click["click_id"],
            "impression_id": click["impression_id"],
            "user_id": click["user_id"],
            "ad_id": click["ad_id"],
            "campaign_id": click["campaign_id"],
            "advertiser_id": click["advertiser_id"],
            "conversion_type": conversion_type,
            "conversion_value": round(random.uniform(1.0, 10000.0), 2),
            "product_id": random.choice(PRODUCTS),
            "quantity": random.randint(1, 10),
            "store_id": click["_internal"]["store_id"],
            "delivery_region": click["_internal"]["delivery_region"],
            "attribution_window": random.choice(["1day", "7day", "30day"]),
        }

        return conversion

    def should_click(self, ad_format: str, delivery_region: str = "") -> bool:
        """
        CTR 확률 계산 — ad_position 가중치에 따라 CTR도 차등 적용.
        ad_format 기반 기준 CTR + 지역 보정.
        """
        ctr_ranges = {
            "display": (0.01, 0.03),
            "native": (0.02, 0.04),
            "video": (0.03, 0.05),
            "discount_coupon": (0.025, 0.045),
        }

        min_ctr, max_ctr = ctr_ranges.get(ad_format, (0.02, 0.04))
        ctr = random.uniform(min_ctr, max_ctr)

        # 강남3구 CTR 보정 (1.2배)
        if delivery_region in ["강남구", "서초구", "송파구"]:
            ctr *= 1.2
        # 마포·영등포 CTR 보정 (1.1배)
        elif delivery_region in ["마포구", "영등포구"]:
            ctr *= 1.1

        return random.random() < ctr

    def should_convert(self) -> bool:
        """CVR 확률 계산 — 가중치 conversion_type 기반 CVR 산출."""
        cvr_ranges = {
            "view_content": (0.05, 0.10),
            "add_to_cart": (0.03, 0.07),
            "signup": (0.02, 0.05),
            "download": (0.02, 0.05),
            "purchase": (0.01, 0.03),
        }

        # 가중치 기반으로 conversion_type 선택 → 해당 CVR 구간 적용
        conversion_type = self._pick_conversion_type()
        min_cvr, max_cvr = cvr_ranges[conversion_type]
        cvr = random.uniform(min_cvr, max_cvr)

        return random.random() < cvr

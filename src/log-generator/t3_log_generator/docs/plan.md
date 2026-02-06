# 광고 로그 생성기 - 최소+확장 구조

## 개요

배달/커머스 광고 플랫폼의 광고 로그 더미 데이터를 생성합니다.  
**기본은 가볍게, 필요하면 Config 설정으로 확장** 가능한 구조입니다.

---

## 데이터 흐름

```
Impression (노출) → Click (클릭) → Conversion (전환)
```

- **CTR**: 카테고리별 5~9% (±20% 변동)
- **CVR**: action_type별 5~40%

---

## 로그 스키마

### Impression (노출) - 기본 8개 필드

| 필드 | 타입 | 설명 |
|------|------|------|
| event_type | string | "impression" 고정 |
| event_id | string(UUID) | 이벤트 고유 ID |
| timestamp | string(ISO) | 발생 시각 |
| user_id | string(UUID) | 유저 ID |
| ad_id | string(UUID) | 광고 소재 ID |
| shop_id | string(UUID) | 가게 ID |
| category | string | 가게 카테고리 (치킨/피자/한식 등) |
| bid_price | float | 입찰가 (원) |

### Click (클릭) - 기본 7개 필드

| 필드 | 타입 | 설명 |
|------|------|------|
| event_type | string | "click" 고정 |
| event_id | string(UUID) | 클릭 이벤트 ID |
| timestamp | string(ISO) | 클릭 시각 |
| impression_id | string(UUID) | 연결된 노출 ID |
| user_id | string(UUID) | 유저 ID |
| shop_id | string(UUID) | 가게 ID |
| cpc_cost | float | 클릭 비용 (원) |

### Conversion (전환) - 기본 7개 필드

| 필드 | 타입 | 설명 |
|------|------|------|
| event_type | string | "conversion" 고정 |
| event_id | string(UUID) | 전환 이벤트 ID |
| timestamp | string(ISO) | 전환 시각 |
| click_id | string(UUID) | 연결된 클릭 ID |
| user_id | string(UUID) | 유저 ID |
| shop_id | string(UUID) | 가게 ID |
| action_type | string | view_menu / add_to_cart / order |
| total_amount | float | 결제 금액 (원) |

---

## 확장 필드 (Config 설정)

### ENABLE_SESSION = True
- Impression/Click/Conversion에 `session_id` 추가

### ENABLE_DEVICE_INFO = True
- Impression에 `platform`, `device_type` 추가

### ENABLE_GEO_INFO = True
- Impression에 `geo_region`, `geo_city` 추가

### ENABLE_ADVANCED = True
- Impression: `campaign_id`, `win_price`, `is_viewable`
- Click: `clickspot_x`, `clickspot_y`, `click_delay_ms`
- Conversion: `item_count`, `conversion_delay_ms`

---

## 카테고리별 특성

| 카테고리 | 입찰가 범위 | 기본 CTR |
|---------|------------|---------|
| 치킨 | 800~2,000원 | 8% |
| 피자 | 700~1,800원 | 7% |
| 한식 | 500~1,500원 | 6% |
| 중식 | 600~1,600원 | 6% |
| 카페 | 200~800원 | 5% |
| 분식 | 300~1,000원 | 9% |

---

## 실행 방법

```bash
# uv
uv run main.py

# pip
pip install faker
python main.py

# Docker
docker build -t ad-log-gen .
docker run ad-log-gen
```

---

## 확장 방법

`main.py` 파일의 `Config` 클래스 수정:

```python
class Config:
    ENABLE_SESSION = True  # ← False를 True로 변경
```

재실행하면 `session_id` 필드가 추가됩니다!

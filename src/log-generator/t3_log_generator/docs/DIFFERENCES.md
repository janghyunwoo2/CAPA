# 기존 vs 최소+확장 구조 비교

## 📊 전체 비교표

| 항목 | 기존 (log-generator) | 최소+확장 (t3_log_generator) |
|------|---------------------|------------------------------|
| **코드 라인 수** | 115줄 | 300줄 |
| **Impression 필드** | 10개 | 8개 (확장 시 15개) |
| **Click 필드** | 9개 | 7개 (확장 시 10개) |
| **Conversion 필드** | 7개 | 7개 (확장 시 10개) |
| **CTR** | 고정 10% | 카테고리별 5~9% |
| **CVR** | 고정 20% | action_type별 5~40% |
| **확장성** | 어려움 | **쉬움** (Config 설정) |

---

## 1️⃣ 필드 수 비교

### 기본 모드

| 로그 타입 | 기존 | 최소+확장 |
|----------|------|----------|
| Impression | 10개 | **8개** |
| Click | 9개 | **7개** |
| Conversion | 7개 | **7개** |

**최소+확장이 더 가볍습니다!**

### 확장 모드 (모든 기능 ON)

| 로그 타입 | 최소+확장 (확장 시) |
|----------|-------------------|
| Impression | 15개 |
| Click | 10개 |
| Conversion | 10개 |

---

## 2️⃣ Impression 필드 비교

### 기존 (10개)
```json
{
  "event_type": "impression",
  "event_id": "...",
  "timestamp": "...",
  "user_id": "...",
  "ad_id": "...",
  "campaign_id": "...",
  "shop_id": "...",
  "placement": "...",
  "platform": "...",
  "bid_price": 1200.0
}
```

### 최소+확장 - 기본 (8개)
```json
{
  "event_type": "impression",
  "event_id": "...",
  "timestamp": "...",
  "user_id": "...",
  "ad_id": "...",
  "shop_id": "...",
  "category": "치킨",
  "bid_price": 1200.0
}
```

**차이점:**
- ❌ `campaign_id`, `placement`, `platform` 제거
- ✅ `category` 추가 (CTR 차등 계산용)

### 최소+확장 - 확장 시 (15개)
```python
# Config에서 설정
ENABLE_SESSION = True
ENABLE_DEVICE_INFO = True
ENABLE_GEO_INFO = True
ENABLE_ADVANCED = True
```

추가되는 필드:
- `session_id`
- `platform`, `device_type`
- `geo_region`, `geo_city`
- `campaign_id`, `win_price`, `is_viewable`

---

## 3️⃣ CTR (클릭률) 비교

### 기존
```python
if random.random() < 0.10:  # 고정 10%
    # 클릭 발생
```
- 모든 광고 동일한 10% CTR

### 최소+확장
```python
def _get_ctr(self, category):
    base_ctr = {
        "치킨": 0.08,
        "카페": 0.05,
        "분식": 0.09,
    }[category]
    return base_ctr * random.uniform(0.8, 1.2)
```
- **카테고리별 차등 CTR**
- 치킨 8%, 카페 5%, 분식 9%
- ±20% 랜덤 변동

---

## 4️⃣ CVR (전환율) 비교

### 기존
```python
if random.random() < 0.20:  # 고정 20%
    # 전환 발생
```
- 모든 action_type 동일한 20% CVR

### 최소+확장
```python
def _get_cvr(self, action_type):
    return {
        "view_menu": 0.40,
        "add_to_cart": 0.15,
        "order": 0.05,
    }[action_type]
```
- **action_type별 차등 CVR**
- 메뉴 보기 40%, 장바구니 15%, 주문 5%

---

## 5️⃣ 마스터 데이터 비교

### 기존
```python
self.users = [str(uuid.uuid4()) for _ in range(100)]
self.shops = [str(uuid.uuid4()) for _ in range(20)]
```
- 유저 100명, 가게 20개
- UUID만 저장

### 최소+확장
```python
# 기본
self.users = [{"user_id": "..."} for _ in range(200)]
self.shops = [
    {
        "shop_id": "...",
        "shop_name": "김씨네 치킨",
        "category": "치킨"
    }
    for _ in range(30)
]

# 확장 (ENABLE_GEO_INFO = True)
self.users = [
    {
        "user_id": "...",
        "region": "서울",
        "city": "강남구"
    }
    for _ in range(200)
]
```
- 유저 200명, 가게 30개
- **카테고리 정보 포함** (기본)
- 지역 정보는 확장 시 추가

---

## 6️⃣ 확장성 비교

### 기존
필드를 추가하려면:
1. 코드 직접 수정
2. 여러 곳을 동시에 수정해야 함
3. 실수하기 쉬움

### 최소+확장
필드를 추가하려면:
1. **Config 설정만 변경**
2. 코드 수정 불필요
3. 안전하고 쉬움

```python
# 이것만 바꾸면 됨!
class Config:
    ENABLE_SESSION = True  # False → True
```

---

## 7️⃣ 코드 구조 비교

### 기존
```python
class AdLogGenerator:
    def __init__(self): ...
    def generate_impression(self): ...
    def generate_click(self): ...
    def generate_conversion(self): ...
    def run(self): ...
```
- 단일 클래스 (115줄)

### 최소+확장
```python
class Config:
    # 확장 기능 on/off

class MasterData:
    # 마스터 데이터 생성

class AdLogGenerator:
    def _get_session_id(self): ...
    def _get_ctr(self): ...
    def _get_cvr(self): ...
    def generate_impression(self): ...
    def generate_click(self): ...
    def generate_conversion(self): ...
    def run(self): ...
```
- 3개 클래스 (300줄)
- 더 체계적인 구조

---

## 8️⃣ 장단점 비교

### 기존 (log-generator)

**장점:**
- ✅ 매우 간단 (115줄)
- ✅ 빠르게 이해 가능

**단점:**
- ❌ CTR/CVR 고정 (비현실적)
- ❌ 필드 확장 어려움
- ❌ 카테고리 구분 없음

### 최소+확장 (t3_log_generator)

**장점:**
- ✅ 기본은 가볍게 (8개 필드)
- ✅ 카테고리별 CTR 차등 (현실적)
- ✅ action_type별 CVR 차등
- ✅ **확장 쉬움** (Config 설정)
- ✅ 언제든 필드 추가 가능

**단점:**
- ❌ 코드가 조금 더 김 (300줄)

---

## 🎯 어떤 걸 써야 할까?

### 기존 (log-generator) 추천
- 빠른 프로토타입
- 파이프라인 연결만 확인

### 최소+확장 (t3_log_generator) 추천 ⭐
- **프로젝트 메인으로 사용**
- CTR/CVR 분석 필요
- 나중에 확장 가능성
- 카테고리별 성과 비교

---

## 💡 결론

**최소+확장 구조**가 더 좋은 이유:

1. ✅ **기본은 더 가볍다** (8개 vs 10개 필드)
2. ✅ **현실적이다** (카테고리별 CTR, action_type별 CVR)
3. ✅ **확장이 쉽다** (Config 설정만 바꾸면 됨)
4. ✅ **유연하다** (필요한 것만 켜서 사용)

→ **t3_log_generator 사용 권장!** 🎉
